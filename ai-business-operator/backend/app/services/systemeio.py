"""The single door to systeme.io.

Two interfaces, two keys, one shared rate-limit budget:

  MCP        X-MCP-Key    contacts, tags, contact fields, newsletters
  Public API X-API-Key    funnels, steps, pages, products, coupons, payments

Every outbound call to systeme.io goes through this client — it owns retries, the
rate-limit budget, and DRY_RUN. Ad-hoc httpx calls elsewhere bypass all three.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

Interface = Literal["mcp", "api"]


class SystemeIOError(RuntimeError):
    """A systeme.io call failed in a way retrying will not fix."""


class RateLimitExhausted(SystemeIOError):
    pass


@dataclass
class RateLimit:
    """Latest values from X-RateLimit-Remaining / X-RateLimit-Refill.

    MCP and the Public API share this budget, so the browser agent's traffic counts
    against it too — hence MAX_BROWSER_SESSIONS.
    """

    remaining: int | None = None
    refill_seconds: int | None = None

    def update(self, headers: httpx.Headers) -> None:
        raw_remaining = headers.get("X-RateLimit-Remaining")
        raw_refill = headers.get("X-RateLimit-Refill")
        # An unparseable header keeps the previous value rather than raising —
        # a malformed rate-limit hint must not fail an otherwise good response.
        if raw_remaining is not None:
            with contextlib.suppress(ValueError):
                self.remaining = int(raw_remaining)
        if raw_refill is not None:
            with contextlib.suppress(ValueError):
                self.refill_seconds = int(raw_refill)


class SystemeIOClient:
    def __init__(
        self,
        *,
        api_key: str,
        mcp_key: str,
        api_base: str,
        mcp_base: str,
        dry_run: bool = True,
        max_retries: int = 4,
        rate_limit_floor: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.mcp_key = mcp_key
        self.api_base = api_base.rstrip("/")
        self.mcp_base = mcp_base.rstrip("/")
        self.dry_run = dry_run
        self.max_retries = max_retries
        self.rate_limit_floor = rate_limit_floor
        self.rate_limit = RateLimit()
        self._client = httpx.AsyncClient(timeout=30.0, transport=transport)

    @classmethod
    def from_env(cls, transport: httpx.AsyncBaseTransport | None = None) -> SystemeIOClient:
        s = get_settings()
        return cls(
            api_key=s.systemeio_api_key,
            mcp_key=s.systemeio_mcp_key,
            api_base=s.systemeio_api_base,
            mcp_base=s.systemeio_mcp_base,
            dry_run=s.dry_run,
            max_retries=s.max_retries,
            rate_limit_floor=s.rate_limit_floor,
            transport=transport,
        )

    async def __aenter__(self) -> SystemeIOClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- Transport ---------------------------------------------------------

    def _headers(self, interface: Interface) -> dict[str, str]:
        if interface == "mcp":
            if not self.mcp_key:
                raise SystemeIOError("SYSTEMEIO_MCP_KEY is not set")
            # Header rather than ?mcpKey= — query strings end up in access logs.
            return {"X-MCP-Key": self.mcp_key, "Content-Type": "application/json"}
        if not self.api_key:
            raise SystemeIOError("SYSTEMEIO_API_KEY is not set")
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        interface: Interface = "api",
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base = self.mcp_base if interface == "mcp" else self.api_base
        url = f"{base}/{path.lstrip('/')}"
        is_write = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}

        if self.dry_run and is_write:
            log.info(
                "systemeio.dry_run",
                extra={"method": method, "url": url, "interface": interface, "body": json_body},
            )
            return {"dry_run": True, "method": method, "url": url, "body": json_body}

        await self._respect_budget()

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    url,
                    headers=self._headers(interface),
                    json=json_body,
                    params=params,
                )
            except httpx.TransportError as exc:
                last_error = exc
                await self._backoff(attempt)
                continue

            self.rate_limit.update(response.headers)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else self._backoff_seconds(attempt)
                )
                log.warning(
                    "systemeio.rate_limited",
                    extra={"url": url, "attempt": attempt, "sleep_seconds": delay},
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code == 401:
                # MCP keys expire within 90 days and return a generic 401 that reads
                # like a code bug. Say so here so nobody loses an afternoon to it.
                raise SystemeIOError(
                    f"401 from systeme.io ({interface}). Check the key is set and unexpired — "
                    "MCP keys expire within 90 days."
                )

            if response.status_code >= 500:
                last_error = SystemeIOError(f"{response.status_code} from {url}")
                await self._backoff(attempt)
                continue

            if response.status_code >= 400:
                raise SystemeIOError(f"{response.status_code} from {url}: {response.text[:300]}")

            if not response.content:
                return {}
            payload = response.json()
            return payload if isinstance(payload, dict) else {"data": payload}

        raise RateLimitExhausted(
            f"Gave up on {method} {url} after {self.max_retries + 1} attempts"
        ) from last_error

    async def _respect_budget(self) -> None:
        """Pause before spending the last of the window rather than eating a 429."""
        remaining = self.rate_limit.remaining
        if remaining is not None and remaining <= self.rate_limit_floor:
            delay = self.rate_limit.refill_seconds or 5
            log.info("systemeio.budget_pause", extra={"remaining": remaining, "sleep": delay})
            await asyncio.sleep(delay)

    def _backoff_seconds(self, attempt: int) -> float:
        return min(2**attempt, 30) + random.uniform(0, 1)  # noqa: S311 - jitter, not crypto

    async def _backoff(self, attempt: int) -> None:
        await asyncio.sleep(self._backoff_seconds(attempt))

    # --- MCP: contacts, tags, newsletters ----------------------------------

    async def mcp_create_contact(
        self, email: str, fields: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"email": email}
        if fields:
            body["fields"] = fields
        return await self._request("POST", "/contacts", interface="mcp", json_body=body)

    async def mcp_get_contact(self, contact_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/contacts/{contact_id}", interface="mcp")

    async def mcp_list_contacts(self, limit: int = 50) -> dict[str, Any]:
        return await self._request("GET", "/contacts", interface="mcp", params={"limit": limit})

    async def mcp_create_tag(self, name: str) -> dict[str, Any]:
        return await self._request("POST", "/tags", interface="mcp", json_body={"name": name})

    async def mcp_assign_tag(self, contact_id: str, tag_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/contacts/{contact_id}/tags", interface="mcp", json_body={"tagId": tag_id}
        )

    async def mcp_list_contact_fields(self) -> dict[str, Any]:
        return await self._request("GET", "/contact_fields", interface="mcp")

    async def mcp_create_newsletter(self, subject: str, body: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/newsletters", interface="mcp", json_body={"subject": subject, "body": body}
        )

    # --- Public API: funnels, pages, products ------------------------------

    async def create_funnel(self, name: str, locale: str = "en") -> dict[str, Any]:
        return await self._request("POST", "/funnels", json_body={"name": name, "locale": locale})

    async def list_funnels(self) -> dict[str, Any]:
        return await self._request("GET", "/funnels")

    async def create_funnel_step(self, funnel_id: str, step_type: str, name: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/funnelSteps",
            json_body={"funnelId": funnel_id, "type": step_type, "name": name},
        )

    async def get_page(self, page_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/page-editor/{page_id}")

    async def save_page_content(
        self, page_id: str, content: dict[str, Any], *, merge: bool = True
    ) -> dict[str, Any]:
        """Write page content.

        PUT /page-editor *replaces* the page rather than patching it, so the default
        is read-then-merge. Pass merge=False only when you genuinely intend to
        discard whatever is there.
        """
        body = dict(content)
        if merge:
            existing = await self.get_page(page_id)
            body = {**existing, **content}
        return await self._request("PUT", "/page-editor", json_body={"pageId": page_id, **body})

    async def create_product(
        self, name: str, price_cents: int, currency: str = "USD"
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/products",
            json_body={"name": name, "price": price_cents, "currency": currency},
        )

    async def create_coupon(self, code: str, percent_off: int) -> dict[str, Any]:
        return await self._request(
            "POST", "/coupons", json_body={"code": code, "percentOff": percent_off}
        )

    async def get_funnel_stats(self, funnel_id: str) -> dict[str, Any]:
        # TODO(phase-6): confirm the stats path against the dev docs; the analytics
        # agent treats a 404 here as "no data yet" rather than an error.
        return await self._request("GET", f"/funnels/{funnel_id}/stats")
