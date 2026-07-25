"""systeme.io client behaviour, driven by a mock transport.

Tests never touch a live account. `httpx.MockTransport` stands in for the service.
"""

from __future__ import annotations

import httpx
import pytest

from app.services.systemeio import RateLimitExhausted, SystemeIOClient, SystemeIOError


def make_client(handler: object, *, dry_run: bool = False, **kwargs: object) -> SystemeIOClient:
    return SystemeIOClient(
        api_key="test-api-key",
        mcp_key="test-mcp-key",
        api_base="https://api.example.test/api",
        mcp_base="https://mcp.example.test",
        dry_run=dry_run,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


async def test_dry_run_does_not_send_writes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("DRY_RUN must not send a write request")

    async with make_client(handler, dry_run=True) as client:
        result = await client.create_funnel("Home Fitness Launch")

    assert result["dry_run"] is True
    assert result["method"] == "POST"


async def test_dry_run_still_allows_reads() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"funnels": []})

    async with make_client(handler, dry_run=True) as client:
        assert await client.list_funnels() == {"funnels": []}


async def test_mcp_and_api_use_different_headers() -> None:
    seen: dict[str, httpx.Headers] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[str(request.url)] = request.headers
        return httpx.Response(200, json={"ok": True})

    async with make_client(handler) as client:
        await client.mcp_list_contacts()
        await client.list_funnels()

    mcp_headers = seen["https://mcp.example.test/contacts?limit=50"]
    api_headers = seen["https://api.example.test/api/funnels"]

    assert mcp_headers["X-MCP-Key"] == "test-mcp-key"
    assert "X-API-Key" not in mcp_headers
    assert api_headers["X-API-Key"] == "test-api-key"
    assert "X-MCP-Key" not in api_headers


async def test_rate_limit_headers_are_recorded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"funnels": []},
            headers={"X-RateLimit-Remaining": "42", "X-RateLimit-Refill": "60"},
        )

    async with make_client(handler) as client:
        await client.list_funnels()
        assert client.rate_limit.remaining == 42
        assert client.rate_limit.refill_seconds == 60


async def test_429_is_retried_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "slow down"})
        return httpx.Response(200, json={"funnels": []})

    async with make_client(handler) as client:
        assert await client.list_funnels() == {"funnels": []}
    assert calls["n"] == 2


async def test_persistent_429_gives_up() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "slow down"})

    async with make_client(handler, max_retries=1) as client:
        with pytest.raises(RateLimitExhausted):
            await client.list_funnels()


async def test_401_mentions_key_expiry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    async with make_client(handler) as client:
        with pytest.raises(SystemeIOError, match="90 days"):
            await client.list_funnels()


async def test_missing_key_fails_before_any_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not reach the network without a key")

    client = SystemeIOClient(
        api_key="",
        mcp_key="",
        api_base="https://api.example.test/api",
        mcp_base="https://mcp.example.test",
        dry_run=False,
        transport=httpx.MockTransport(handler),
    )
    async with client:
        with pytest.raises(SystemeIOError, match="SYSTEMEIO_API_KEY"):
            await client.list_funnels()


async def test_save_page_content_merges_by_default() -> None:
    """PUT /page-editor replaces the page, so the client reads first and merges.

    Without this, writing a headline would silently discard the rest of the page.
    """
    sent: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"headline": "old", "sections": ["hero", "pricing"]})
        sent["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True})

    async with make_client(handler) as client:
        await client.save_page_content("page-1", {"headline": "new"})

    body = str(sent["body"])
    assert '"headline":"new"' in body.replace(" ", "")
    assert "pricing" in body  # the untouched section survived
