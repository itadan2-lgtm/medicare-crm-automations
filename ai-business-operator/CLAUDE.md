# CLAUDE.md — AI Business Operator

Project context and working rules for Claude Code. Read this before touching anything.

## What this system is

An autonomous multi-agent platform that takes a one-line business goal ("launch a home-fitness
ebook business") and produces a live systeme.io funnel: market research → product → brand →
copy → funnel structure → email sequences → automations → published pages → analytics →
optimization.

## Architecture rules (do not violate without updating `docs/architecture.md`)

1. **Agents never call each other directly.** Coordination happens through the `tasks` table and
   Redis events. If you find yourself importing one agent from another, you are modelling it
   wrong — emit an event and let the orchestrator enqueue the dependent task.
2. **The orchestrator is the only thing that creates tasks.** Agents return outputs and emit
   `task_completed`; they do not enqueue work for their peers.
3. **Least privilege, checked twice.** Every agent declares `allowed_tools` in `AGENTS.md`,
   mirrored in `agents/registry.py`. `agents/tools.py` builds only those; `BaseAgent.use_tool()`
   refuses anything else. Do not widen a toolset to make a test pass.
3a. **An LLM-proposed plan is never executed unvalidated.** `services/planning.py` checks it
   against the registry and the approval gate; a rejected plan falls back to `LAUNCH_PLAN`.
   Do not add a path that skips `validate_plan`.
4. **Secrets stay server-side.** systeme.io MCP/API keys load from the environment into the
   backend and browser-agent processes only. Nothing prefixed `NEXT_PUBLIC_` may contain a key.
5. **Publishing and payments require a human.** Any task whose type is in
   `HUMAN_APPROVAL_REQUIRED` parks in `awaiting_approval`. Do not add an auto-approve path.
6. **systeme.io writes go through `backend/app/services/systemeio.py`.** No ad-hoc `httpx` calls
   to systeme.io anywhere else — the client owns retries, rate-limit headers, and `DRY_RUN`.

## Layout

```
backend/app/       FastAPI app, ORM models, routers, orchestrator, systeme.io client
agents/            BaseAgent + worker loop + one folder per specialist
browser_agent/     Playwright scripts (semantic locators only)
vector_memory/     Embeddings + pgvector long-term memory
frontend/          Next.js dashboard
infra/             compose, SQL init, k8s, terraform
docs/              Architecture, developer guide, integration, security, roadmap
```

## Conventions

- **Python 3.11**, FastAPI, async SQLAlchemy 2.0, Pydantic v2. Format with `ruff format`, lint
  with `ruff check`, type-check with `mypy backend/app`.
- **Type hints are mandatory** on anything crossing a module boundary.
- **Structured logging only.** `log.info("task.claimed", extra={"task_id": ..., "agent": ...})`.
  Never log a key, token, password, or full prompt containing user data.
- **Tests live beside their component** (`backend/tests/`, `agents/*/tests/`). Mock the LLM with
  a deterministic fake — never hit a real API in unit tests.
- **Migrations**: `infra/sql/001_init.sql` is the reference DDL and the compose init script.
  Schema changes go through Alembic revisions (`make migration M="..."`), never edits to that
  file. Review what autogenerate produces — it misses constraints and partial indexes.
- **Integration tests need real Postgres.** They skip without `TEST_DATABASE_URL`. Do not
  replace them with a sqlite stand-in: `SKIP LOCKED`, array containment, and pgvector distance
  operators are exactly what they exist to check.

## Task and event contract

Task rows and Redis event payloads are defined once, in `backend/app/schemas.py`. If you change
a field, change it there and update `docs/architecture.md` in the same commit. Statuses:
`pending → claimed → working → done | error | awaiting_approval`.

## When you are stuck on systeme.io

The Public API covers funnels, funnel steps, pages, products, coupons, payments. MCP covers
contacts, tags, contact fields, newsletters. **Anything else — page template design, funnel step
layout — is Playwright's job.** Check `docs/systemeio_integration.md` before assuming an
endpoint exists; guessing at endpoints has been the biggest time sink on this project.

## Definition of done

A change is done when: types check, `ruff` is clean, tests pass, no secret is logged or
committed, and the relevant doc under `docs/` reflects the new behaviour.
