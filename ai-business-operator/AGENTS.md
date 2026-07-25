# AGENTS.md — subagent definitions

The contract for every agent in the system: purpose, inputs, outputs, allowed tools, memory
scope, failure handling, and what it triggers. `agents/registry.py` is generated from this
document by hand — **if you change a row here, change the registry in the same commit.**

Coordination model: the CEO agent writes tasks; specialists claim them from the `tasks` table,
work, write outputs back, and emit `task_completed`. No direct agent-to-agent calls.

---

## ceo_agent — Orchestrator

- **Purpose**: project lead and planner. Turns a user goal into a dependency-ordered task graph,
  reassigns failed work, and holds the only authority to release `awaiting_approval` tasks once
  a human has signed off.
- **Inputs**: user goal, project config, completion events from every other agent.
- **Outputs**: task assignments, the global plan, project status.
- **Allowed tools**: `task_queue`, `db_read`, `db_write`, `llm`.
- **Memory**: read/write across all categories.
- **Failure handling**: on a specialist error, retry once with the error appended to the prompt;
  on a second failure, mark the project `blocked` and surface it in the dashboard.
- **Triggers**: everything.

## research_agent — Market Research

- **Purpose**: analyse the market, audience, and competitors for a niche.
- **Inputs**: niche keyword, industry signals, optional competitor list.
- **Outputs**: market report — demographics, pain points, existing offers, price bands, angles.
- **Allowed tools**: `web_search`, `llm`, `memory_read`, `memory_write`.
- **Memory**: writes `customer_pain`, `niche`, `competitor`; reads prior research for the niche.
- **Failure handling**: if search returns nothing usable, downgrade to LLM-only synthesis and
  flag `confidence: low` in the output rather than fabricating citations.
- **Triggers**: `market_research_done` → product, branding, copy.

## product_agent — Product Creation

- **Purpose**: design and draft the digital product (ebook, course, template, checklist).
- **Inputs**: market report, user preferences, format constraints.
- **Outputs**: product outline plus drafted content (markdown, later rendered to PDF).
- **Allowed tools**: `llm`, `memory_read`, `memory_write`, `file_write`.
- **Memory**: `product_history` — what has been built and how it performed.
- **Failure handling**: long drafts are chunked per section; a failed section is retried alone,
  not the whole document.
- **Triggers**: `product_drafted` → funnel, copy.

## branding_agent — Branding

- **Purpose**: generate brand identity — name, positioning line, palette, logo prompt.
- **Inputs**: market report, product theme, offer info.
- **Outputs**: brand name candidates, colour palette, typography direction, image-gen prompt.
- **Allowed tools**: `llm`, `image_gen`, `memory_read`, `memory_write`.
- **Memory**: `brand_style` — reusable palettes and naming patterns.
- **Failure handling**: if image generation fails, still return the text identity; the logo is a
  non-blocking asset.
- **Triggers**: `branding_done` → copy, funnel.

## copy_agent — Copywriting

- **Purpose**: write marketing copy — headlines, landing and sales page bodies, CTAs, bullets.
- **Inputs**: offer details, audience, brand voice, funnel step being written.
- **Outputs**: structured copy blocks keyed by page section.
- **Allowed tools**: `llm`, `memory_read`, `memory_write`.
- **Memory**: `headline`, `cta`, `copy_block` — including which ones converted.
- **Failure handling**: output is schema-validated; a malformed response is re-requested once
  with the validation error attached.
- **Triggers**: `copy_done` → funnel, email.

## funnel_agent — Funnel Design

- **Purpose**: design the funnel structure — opt-in, sales page, checkout, upsell, thank-you.
- **Inputs**: product, copy blocks, audience, price point.
- **Outputs**: funnel plan — ordered steps, step types, template choice, per-step copy mapping.
- **Allowed tools**: `llm`, `db_read`, `memory_read`, `memory_write`.
- **Memory**: `funnel_pattern` — structures that have worked per niche.
- **Failure handling**: validates every step type against the systeme.io supported set before
  emitting; an unsupported type is replaced and noted.
- **Triggers**: `funnel_planned` → browser, automation.

## email_agent — Email Sequences

- **Purpose**: write welcome and follow-up sequences with send delays.
- **Inputs**: product info, funnel plan, audience, brand voice.
- **Outputs**: ordered emails (subject, body, delay hours).
- **Allowed tools**: `llm`, `memory_read`, `memory_write`.
- **Memory**: `email_performance` — open and click rates by subject pattern.
- **Failure handling**: per-email retry; a partial sequence is still persisted and flagged.
- **Triggers**: `emails_drafted` → automation.

## automation_agent — Automations

- **Purpose**: define tags, triggers, and delays that wire the funnel to the email sequences.
- **Inputs**: funnel steps, email sequence, contact lists.
- **Outputs**: automation flow definition (JSON) ready for the systeme.io MCP/API.
- **Allowed tools**: `systemeio_mcp`, `db_read`, `llm`.
- **Memory**: `automation_rule`.
- **Failure handling**: idempotent by tag name — re-running must not create duplicate tags.
- **Triggers**: `automations_ready` → browser (publish), analytics.

## browser_agent — Browser Automation

- **Purpose**: drive the systeme.io UI for anything the APIs do not expose — page editor layout,
  funnel step design, template selection.
- **Inputs**: funnel plan, page copy, brand assets.
- **Outputs**: executed UI steps, resulting systeme.io resource IDs, screenshots on failure.
- **Allowed tools**: `playwright`, `systemeio_api`. **No database access, no LLM.**
- **Memory**: none. Stateless by design — it is the most exposed component.
- **Failure handling**: screenshot + trace on failure, one retry, then report to the CEO. Never
  swallows an error silently.
- **Triggers**: `pages_built` → analytics. Publishing steps require human approval first.

## analytics_agent — Analytics

- **Purpose**: monitor funnel results — visitors, opt-ins, conversions, revenue.
- **Inputs**: systeme.io stats, internal task and funnel data.
- **Outputs**: metric reports and plain-language recommendations.
- **Allowed tools**: `systemeio_api`, `db_read`, `metrics`, `llm`.
- **Memory**: `analytics_snapshot`.
- **Failure handling**: missing data windows are reported as gaps, never interpolated.
- **Triggers**: `analytics_ready` → optimization.

## optimization_agent — Optimization

- **Purpose**: propose and sequence A/B tests and funnel tweaks.
- **Inputs**: analytics data, conversion rates, prior experiment results.
- **Outputs**: ranked improvement suggestions (new headline, price, sequence timing).
- **Allowed tools**: `llm`, `db_read`, `memory_read`, `memory_write`.
- **Memory**: `experiment_result` — including losers, so they are not re-proposed.
- **Failure handling**: refuses to propose a change when the sample size is below
  `MIN_SAMPLE_SIZE`; says so instead of guessing.
- **Triggers**: `optimization_proposed` → CEO (which requires human approval to apply).

---

## Tool vocabulary

| Tool | Grants |
|---|---|
| `llm` | Claude / GPT completion calls |
| `web_search` | Outbound search for research |
| `image_gen` | Logo and asset generation |
| `db_read` / `db_write` | Postgres access, scoped to the agent's own project |
| `memory_read` / `memory_write` | Vector memory query and insert |
| `task_queue` | Create and reassign tasks (CEO only) |
| `systemeio_mcp` | Contacts, tags, contact fields, newsletters |
| `systemeio_api` | Funnels, steps, pages, products, coupons, payments |
| `playwright` | Headless browser control |
| `metrics` | Prometheus / SQL analytics reads |
| `file_write` | Write to the project artifact directory only |
