# Roadmap

Seven phases, ~12 weeks. Phases 4 onward parallelise across agent teams once the foundation is
stable.

## Phase 1 — Architecture & planning (1–2 weeks) — ✅ complete

Deliverable: the architecture specification, agent designs, DB schema, security model, and this
repository scaffold.
**Accept**: design reviewed and signed off, no major gaps.

## Phase 2 — Core backend & foundation (2–3 weeks) — 🚧 in progress

- Repo and CI ✅
- FastAPI skeleton with user/project auth ✅ (scaffolded)
- Postgres + Redis configured ✅
- Schema and migrations — SQL init ✅, Alembic revisions ⬜
- Basic dashboard: login, project list ✅ (scaffolded)

**Milestone**: user login, project creation.
**Accept**: `docker compose up` runs backend + DB locally, tests pass.

## Phase 3 — Agent framework & orchestration (2 weeks)

- Task model and claim queue ✅ (scaffolded)
- Orchestrator: goal → initial task graph 🚧 (rules in place, decomposition stubbed)
- Claude API integration via `anthropic` ✅ (client scaffolded)
- Base worker fetching tasks and invoking the LLM ✅
- `CLAUDE.md` system prompts ✅

**Milestone**: orchestrator spawns a task, an agent processes it.
**Accept**: research agent returns a mock report for a sample query.

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

## Scaffold status

What exists here is structure, contracts, and wiring. Deliberately stubbed, each marked
`TODO(phase-N)` in the source:

| Stub | Phase |
|---|---|
| Goal → task-graph decomposition (currently a fixed template) | 3 |
| Per-agent prompt engineering and output parsing | 4 |
| Web search tool for the research agent | 4 |
| Vector memory retrieval tuning | 4 |
| systeme.io write paths beyond funnel/step/page creation | 5 |
| Playwright page-editor scripts (skeletons only) | 5 |
| Analytics metric computation | 6 |
| Alembic migrations, Helm charts, Terraform | 2 / 7 |
