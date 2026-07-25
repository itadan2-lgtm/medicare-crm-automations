"""Tool provisioning.

`BaseAgent.use_tool()` enforces the registry's `allowed_tools`; this module is what
actually builds those tools. The two work together: the registry says what an agent
*may* hold, `build_toolset` decides what it *does* hold, and it never hands over
anything the registry did not authorise.

That double check is deliberate. A mistake here — passing the systeme.io client to
the copy agent, say — is caught by `use_tool()` rather than silently widening what a
content agent can reach.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from agents.registry import get_spec

log = logging.getLogger(__name__)


# --- Web search ------------------------------------------------------------


class SearchProvider(Protocol):
    async def __call__(self, query: str, *, limit: int = 5) -> list[str]: ...


class NullSearch:
    """No search configured.

    Returns nothing rather than raising: the research agent handles empty signals by
    falling back to model knowledge and reporting `confidence: low`, which is honest.
    Raising here would block the pipeline over a missing optional key.
    """

    async def __call__(self, query: str, *, limit: int = 5) -> list[str]:
        log.warning(
            "search.not_configured",
            extra={"hint": "Set SEARCH_API_KEY to enable web research", "query": query[:80]},
        )
        return []


class BraveSearch:
    """Brave Search API. Results are untrusted text — the research agent wraps them
    in `<untrusted_content>` before they reach a prompt."""

    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def __call__(self, query: str, *, limit: int = 5) -> list[str]:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.ENDPOINT,
                headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
                params={"q": query, "count": limit},
            )
            if response.status_code != 200:
                log.warning(
                    "search.failed",
                    extra={"status": response.status_code, "query": query[:80]},
                )
                return []
            results = response.json().get("web", {}).get("results", [])

        return [
            f"{item.get('title', '')}\n{item.get('description', '')}\n{item.get('url', '')}"
            for item in results[:limit]
        ]


def build_search(api_key: str = "") -> SearchProvider:
    return BraveSearch(api_key) if api_key else NullSearch()


# --- Artifact writing ------------------------------------------------------


class ArtifactWriter:
    """Scoped file writer.

    Agents write drafts and assets; they do not get a general filesystem. Every path
    is resolved and checked to be inside the project's own artifact directory, so a
    traversal in a model-generated filename cannot escape it.
    """

    def __init__(self, root: Path, project_id: int) -> None:
        self.root = (root / f"project-{project_id}").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, relative_path: str, content: str) -> str:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise PermissionError(
                f"Refusing to write outside the project directory: {relative_path}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        log.info("artifact.written", extra={"path": str(target)})
        return str(target)


# --- Memory adapters -------------------------------------------------------


class MemoryReader:
    """Similarity search restricted to the categories the agent declares."""

    def __init__(self, store: Any, agent_name: str, project_id: int | None) -> None:
        self._store = store
        self._agent = agent_name
        self._project_id = project_id
        self._categories = get_spec(agent_name).memory_categories

    async def __call__(
        self, query: str, *, category: str | None = None, top_k: int = 5, all_projects: bool = True
    ) -> list[str]:
        if category and category not in self._categories:
            raise PermissionError(
                f"{self._agent} may not read memory category {category!r}. "
                f"Declared: {', '.join(sorted(self._categories)) or 'none'}"
            )
        hits = await self._store.recall(
            query=query,
            category=category,
            # Cross-project recall is the point of long-term memory: what converted
            # for a previous fitness funnel should inform the next one.
            project_id=None if all_projects else self._project_id,
            top_k=top_k,
        )
        return [hit.content for hit in hits]


class MemoryWriter:
    def __init__(self, store: Any, agent_name: str, project_id: int | None) -> None:
        self._store = store
        self._agent = agent_name
        self._project_id = project_id
        self._categories = get_spec(agent_name).memory_categories

    async def __call__(
        self, content: str, *, category: str, important: bool = False, **metadata: Any
    ) -> int:
        if category not in self._categories:
            raise PermissionError(
                f"{self._agent} may not write memory category {category!r}. "
                f"Declared: {', '.join(sorted(self._categories)) or 'none'}"
            )
        return await self._store.remember(
            content=content,
            category=category,
            project_id=self._project_id,
            agent_name=self._agent,
            metadata=metadata,
            important=important,
        )


# --- Assembly --------------------------------------------------------------


async def build_toolset(
    agent_name: str,
    *,
    project_id: int | None = None,
    session: AsyncSession | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    """Build exactly the tools an agent is authorised to hold.

    Anything the registry does not list is never constructed — an unconfigured
    dependency for a tool the agent cannot use should not cost a connection or a
    warning.
    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    spec = get_spec(agent_name)
    allowed = spec.allowed_tools
    tools: dict[str, Any] = {}

    if "web_search" in allowed:
        tools["web_search"] = build_search(getattr(settings, "search_api_key", ""))

    if {"memory_read", "memory_write"} & allowed:
        if session is None:
            log.warning("tools.memory_unavailable", extra={"agent": agent_name})
        else:
            from vector_memory.embeddings import build_embedder
            from vector_memory.store import PgVectorStore

            store = PgVectorStore(
                session,
                build_embedder(
                    api_key=settings.openai_api_key,
                    model=settings.embedding_model,
                    dimensions=settings.embedding_dimensions,
                ),
                ttl_days=settings.memory_ttl_days,
            )
            if "memory_read" in allowed:
                tools["memory_read"] = MemoryReader(store, agent_name, project_id)
            if "memory_write" in allowed:
                tools["memory_write"] = MemoryWriter(store, agent_name, project_id)

    if {"systemeio_mcp", "systemeio_api"} & allowed:
        from app.services.systemeio import SystemeIOClient

        client = SystemeIOClient.from_env()
        # Both names resolve to the same client; the registry is what decides which
        # interface an agent is entitled to call.
        for name in {"systemeio_mcp", "systemeio_api"} & allowed:
            tools[name] = client

    if "db_read" in allowed and session is not None:
        tools["db_read"] = session

    if "file_write" in allowed:
        artifact_root = Path(getattr(settings, "artifact_dir", "./artifacts"))
        tools["file_write"] = ArtifactWriter(artifact_root, project_id or 0)

    if "metrics" in allowed:
        from prometheus_client import REGISTRY as PROM_REGISTRY

        tools["metrics"] = PROM_REGISTRY

    # image_gen and task_queue are provisioned by their owners (branding worker and
    # the orchestrator respectively) rather than here.
    missing = allowed - tools.keys() - {"llm", "image_gen", "task_queue", "playwright", "db_write"}
    if missing:
        log.info(
            "tools.unprovisioned",
            extra={"agent": agent_name, "tools": sorted(missing)},
        )

    return tools


async def release_toolset(tools: dict[str, Any]) -> None:
    """Close anything that holds a connection."""
    for name in ("systemeio_api", "systemeio_mcp"):
        client = tools.get(name)
        if client is not None and hasattr(client, "aclose"):
            await client.aclose()
            break  # both names point at the same client
