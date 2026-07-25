# Roadmap

Seven phases, ~12 weeks. Phases 4 onward parallelise across agent teams once the foundation is
stable.

## Phase 1 — Architecture & planning (1–2 weeks) — ✅ complete

Deliverable: the architecture specification, agent designs, DB schema, security model, and this
repository scaffold.
**Accept**: design reviewed and signed off, no major gaps.

## Phase 2 — Core backend & foundation (2–3 weeks) — ✅ complete

- Repo and CI ✅
- FastAPI skeleton with user/project auth ✅
- Postgres + Redis configured ✅
- Schema and migrations — SQL init ✅, Alembic revisions ✅
- Basic dashboard: login, project list ✅

**Milestone**: user login, project creation. ✅
**Accept**: `docker compose up` runs backend + DB locally, tests pass. ✅

## Phase 3 — Agent framework & orchestration (2 weeks) — ✅ complete

- Task model and claim queue ✅ — `FOR UPDATE SKIP LOCKED`, dependency-gated,
  proven under concurrency by integration test
- Orchestrator: goal → task graph ✅ — CEO agent proposes, `services/planning.py`
  validates against the registry, fixed template as fallback
- Claude API integration via `anthropic` ✅
- Base worker fetching tasks and invoking the LLM ✅
- Tool provisioning ✅ — each agent receives exactly what the registry authorises
- Long-term memory wired into the worker loop ✅ — recall before the prompt,
  persist after a successful run
- `CLAUDE.md` system prompts ✅

**Milestone**: orchestrator spawns a task, an agent processes it. ✅
**Accept**: research agent returns a report for a sample query. ✅ (real API key
required; the path is covered end to end with a deterministic fake)

## Phase 4 — Core agents (3–4 weeks)

- Flesh out research, product, branding, copy, email, funnel, automation agents
- Real prompt templates and output parsing per agent
- Agents persist outputs to the database
- Vector memory in use: write findings and headlines, query on retrieval
- Event-driven chaining: research completion triggers product, branding, copy

**Milestone**: research retrieves market info; copy generates a landing headline; data flows
through the task graph.
**Accept**: given "fitness niche", the system produces a product idea, brand name, and a first
draft landing page title.

## Phase 5 — systeme.io integration (2–3 weeks)

- MCP and Public API clients complete, with rate-limit handling
- Browser agent creates funnel pages via Playwright
- Automation agent populates tags and email automations
- systeme.io IDs stored against local funnels and steps

**Milestone**: a test funnel created in systeme.io end-to-end; one email sequence published.
**Accept**: automated creation of an opt-in + sales page funnel in a real (throwaway) account.

## Phase 6 — Analytics & optimization (1–2 weeks)

- Analytics agent fetches funnel stats and computes metrics
- Optimization agent proposes headline and price changes
- Approved suggestions written back to the funnel

**Milestone**: a conversion report; an element updated from an agent suggestion.
**Accept**: agent notices a low opt-in rate, proposes a new headline, human approves, funnel
updates.

## Phase 7 — Testing, QA & deployment (2 weeks)

- Complete unit, integration, and E2E suites
- Finalise README and API docs
- Security review against the OWASP agent guidance
- Final images, deployment manifests, production rollout

**Milestone**: all tests pass, no critical bugs, deployed with monitoring.
**Accept**: production launch; one sample business built end-to-end.

---

## Current status

Phases 1–3 are done. The orchestration core is real and tested: task claiming,
dependency gating, output propagation, the approval gate, plan validation, tool
provisioning, and memory recall/persistence all have coverage, with the
database-dependent parts run against live Postgres and pgvector.

Still stubbed, each marked `TODO(phase-N)` in the source:

| Stub | Phase |
|---|---|
| Per-agent prompt engineering and output-quality tuning | 4 |
| Web search — provider is wired, needs a `SEARCH_API_KEY` and result tuning | 4 |
| Vector memory retrieval tuning (IVFFlat lists, probes, top-k per category) | 4 |
| systeme.io write paths beyond funnel/step/page creation | 5 |
| Playwright selectors — written from documented UI copy, unverified against live | 5 |
| Analytics metric computation | 6 |
| Helm charts, Terraform | 7 |

## What running it for real still needs

- `ANTHROPIC_API_KEY` — without it, planning falls back to the fixed template and
  agents cannot run at all.
- `OPENAI_API_KEY` — without it, embeddings fall back to a hash stand-in whose
  similarity results are meaningless. Storage and retrieval work; recall does not.
- A throwaway systeme.io account, `DRY_RUN=false`, and a pass over the Playwright
  selectors in `browser_agent/playwright_scripts/`.
