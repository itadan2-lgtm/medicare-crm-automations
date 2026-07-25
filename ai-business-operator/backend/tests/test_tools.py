"""Tool provisioning and the memory hooks around a task run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agents.memory_hooks import persist_output, recall_context, recall_query
from agents.tools import (
    ArtifactWriter,
    MemoryReader,
    MemoryWriter,
    NullSearch,
    build_search,
    build_toolset,
)
from app.config import Settings


class FakeStore:
    """Stands in for PgVectorStore without a database."""

    def __init__(self, hits: list[str] | None = None) -> None:
        self._hits = hits or []
        self.written: list[tuple[str, str]] = []

    async def recall(self, *, query: str, category: str | None, project_id: int | None, top_k: int):
        from vector_memory.store import MemoryHit

        return [
            MemoryHit(id=i, content=text, category=category or "x", similarity=0.9)
            for i, text in enumerate(self._hits)
        ]

    async def remember(self, *, content: str, category: str, **_kwargs: Any) -> int:
        self.written.append((category, content))
        return len(self.written)


# --- Provisioning ----------------------------------------------------------


async def test_toolset_matches_what_the_agent_may_hold() -> None:
    """Nothing is provisioned that use_tool() would refuse."""
    from agents.registry import get_spec

    settings = Settings(anthropic_api_key="", openai_api_key="")
    for name in ("copy_agent", "research_agent", "browser_agent", "analytics_agent"):
        tools = await build_toolset(name, project_id=1, session=None, settings=settings)
        try:
            assert set(tools) <= get_spec(name).allowed_tools, (
                f"{name} was handed a tool it may not use"
            )
        finally:
            from agents.tools import release_toolset

            await release_toolset(tools)


async def test_content_agent_gets_no_systemeio_client() -> None:
    tools = await build_toolset("copy_agent", project_id=1, settings=Settings())
    assert "systemeio_api" not in tools
    assert "systemeio_mcp" not in tools


async def test_research_agent_gets_search() -> None:
    tools = await build_toolset("research_agent", project_id=1, settings=Settings())
    assert "web_search" in tools


async def test_memory_tools_need_a_session() -> None:
    """Without a session, memory is absent rather than broken — the worker logs it
    and the agent runs without prior context."""
    tools = await build_toolset("copy_agent", project_id=1, session=None, settings=Settings())
    assert "memory_read" not in tools


# --- Search ----------------------------------------------------------------


async def test_null_search_returns_nothing_rather_than_raising() -> None:
    """A missing optional key must not block the pipeline."""
    assert await NullSearch()("home fitness") == []


def test_build_search_selects_by_key_presence() -> None:
    from agents.tools import BraveSearch

    assert isinstance(build_search(""), NullSearch)
    assert isinstance(build_search("key-123"), BraveSearch)


# --- Artifact writing ------------------------------------------------------


def test_artifact_writer_scopes_to_the_project(tmp_path: Path) -> None:
    writer = ArtifactWriter(tmp_path, project_id=7)
    path = Path(writer.write("draft.md", "hello"))
    assert path.read_text() == "hello"
    assert "project-7" in str(path)


def test_artifact_writer_blocks_traversal(tmp_path: Path) -> None:
    """A model-generated filename must not escape the project directory."""
    writer = ArtifactWriter(tmp_path, project_id=7)
    with pytest.raises(PermissionError):
        writer.write("../../etc/passwd", "nope")


def test_artifact_writer_allows_nested_paths(tmp_path: Path) -> None:
    writer = ArtifactWriter(tmp_path, project_id=7)
    path = Path(writer.write("sections/intro.md", "text"))
    assert path.read_text() == "text"


# --- Memory permissions ----------------------------------------------------


async def test_memory_reader_rejects_undeclared_category() -> None:
    reader = MemoryReader(FakeStore(), "copy_agent", project_id=1)
    with pytest.raises(PermissionError, match="may not read"):
        await reader("query", category="customer_pain")  # research's category, not copy's


async def test_memory_reader_allows_declared_category() -> None:
    reader = MemoryReader(FakeStore(["Stop losing hours"]), "copy_agent", project_id=1)
    assert await reader("fitness", category="headline") == ["Stop losing hours"]


async def test_memory_writer_rejects_undeclared_category() -> None:
    writer = MemoryWriter(FakeStore(), "copy_agent", project_id=1)
    with pytest.raises(PermissionError, match="may not write"):
        await writer("something", category="funnel_pattern")


async def test_memory_recall_spans_projects_by_default() -> None:
    """Cross-project recall is the point: what converted before should inform now."""
    store = FakeStore(["prior headline"])
    reader = MemoryReader(store, "copy_agent", project_id=1)
    assert await reader("fitness", category="headline") == ["prior headline"]


# --- Hooks -----------------------------------------------------------------


def test_recall_query_prefers_goal_then_falls_back() -> None:
    assert recall_query({"goal": "fitness ebook"}) == "fitness ebook"
    assert recall_query({"niche": "home fitness"}) == "home fitness"
    assert recall_query({"research_market": {"audience": "busy parents"}}) == "busy parents"


async def test_recall_context_enriches_the_input() -> None:
    tools = {"memory_read": MemoryReader(FakeStore(["a pain"]), "research_agent", 1)}
    enriched = await recall_context("research_agent", {"goal": "fitness"}, tools)
    assert enriched["prior_research"] == ["a pain", "a pain", "a pain"]  # three categories
    assert enriched["goal"] == "fitness"


async def test_recall_context_without_memory_is_a_no_op() -> None:
    task_input = {"goal": "fitness"}
    assert await recall_context("research_agent", task_input, {}) == task_input


async def test_recall_failure_does_not_break_the_run() -> None:
    """Memory is an enhancement, not a dependency."""

    class Exploding:
        async def __call__(self, *_a: Any, **_k: Any) -> list[str]:
            raise RuntimeError("vector store down")

    enriched = await recall_context("research_agent", {"goal": "x"}, {"memory_read": Exploding()})
    assert enriched == {"goal": "x"}


async def test_persist_output_writes_declared_fields() -> None:
    store = FakeStore()
    tools = {"memory_write": MemoryWriter(store, "research_agent", 1)}
    stored = await persist_output(
        "research_agent", {"pain_points": ["no time", "no motivation"]}, tools
    )
    assert stored == 2
    assert store.written == [("customer_pain", "no time"), ("customer_pain", "no motivation")]


async def test_persist_output_skips_empty_values() -> None:
    store = FakeStore()
    tools = {"memory_write": MemoryWriter(store, "copy_agent", 1)}
    assert await persist_output("copy_agent", {"headline": "", "cta": "Go"}, tools) == 1


async def test_persist_failure_does_not_fail_the_task() -> None:
    class Exploding:
        async def __call__(self, *_a: Any, **_k: Any) -> int:
            raise RuntimeError("disk full")

    assert (
        await persist_output(
            "research_agent", {"pain_points": ["x"]}, {"memory_write": Exploding()}
        )
        == 0
    )
