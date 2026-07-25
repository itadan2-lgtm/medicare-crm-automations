# Security model

Built to the OWASP guidance for agentic AI systems. The threat that matters most here is not a
classic web exploit — it is an agent doing something expensive, public, and irreversible because
a prompt told it to.

## 1. Authentication

**Users** authenticate to the dashboard with JWT (`HS256`, `JWT_EXPIRE_MINUTES`). Every API call
carries the token; there are no unauthenticated endpoints except `/health`.

**Agents** never use a user's token. Each worker gets a scoped internal service token naming its
agent identity and permitted tools. A worker's token cannot call the approval endpoints —
only a human session can.

## 2. Least privilege

Every agent declares `allowed_tools` in `AGENTS.md`, mirrored in `agents/registry.py` and
enforced in `BaseAgent.use_tool()`, which raises `ToolNotPermitted` for anything outside the set.
Concretely:

- The **browser agent** has Playwright and the systeme.io API. No database, no LLM key, no
  memory. It is the most exposed process, so it holds the least.
- **Content agents** (copy, product, branding, email) have the LLM and memory. No systeme.io
  credentials, no shell, no database writes outside their own task row.
- Only the **CEO agent** can create tasks or release an approval hold.

Widening a toolset to make something work is a design smell — emit an event instead.

## 3. The human gate

`REQUIRE_HUMAN_APPROVAL=true` by default. Task types in `HUMAN_APPROVAL_REQUIRED` —
publishing a funnel, sending a broadcast, creating a payment or coupon — park in
`awaiting_approval` and appear in the dashboard for review. There is no auto-approve
configuration and no code path that releases a hold without an authenticated human session.

This is the single most important control in the system. A compromised or merely confused agent
can waste tokens; it cannot publish a page or charge a card.

## 4. Prompt injection and untrusted content

Research and analytics agents ingest text from the open web. Treat all of it as hostile input:

- Fetched content is wrapped in explicit delimiters and labelled untrusted in the prompt.
- Agent outputs are **schema-validated** before anything acts on them. A funnel plan naming an
  unsupported step type is rejected, not attempted.
- No agent output is ever passed to a shell, an `eval`, or a raw SQL string.
- Anything an agent says that resembles an instruction ("ignore previous", "publish now") is
  data, not a command — only the orchestrator's own logic creates tasks.

## 5. Inter-agent trust

Redis events carry an HMAC-SHA256 signature over the canonical JSON body. Subscribers drop
unsigned or mis-signed events. Trust levels are explicit: a specialist agent's claim that work
finished is accepted for its own task only — it cannot assert state about another agent's work.

Circuit breakers: an agent failing more than `AGENT_ERROR_THRESHOLD` times in
`AGENT_ERROR_WINDOW` is quarantined and its tasks halted, rather than allowed to burn the
rate-limit budget or the token spend.

## 6. Secrets

- Environment variables in development; a secrets manager (AWS Secrets Manager, Vault, or
  Kubernetes Secrets) in staging and production. Never in an image layer, never in a commit.
- systeme.io keys load into the backend and browser-agent processes only.
- Logs are structured and pass through a redaction filter that masks anything matching a key,
  token, password, or bearer pattern. Prompts containing user data are logged at `DEBUG` only,
  and `DEBUG` is off outside development.
- MCP keys expire within 90 days — rotate at day 75. Rotation is a config change, not a deploy.

## 7. Transport and web

HTTPS everywhere, HSTS at the ingress. Standard dashboard protections: `SameSite=Lax` cookies,
CSRF tokens on state-changing form posts, output escaping (React handles this — do not reach for
`dangerouslySetInnerHTML` to render agent-generated copy; render it as text or sanitise it).

## 8. Pipeline

CI runs secret scanning (gitleaks), dependency audit (`pip-audit`, `npm audit`), and static
analysis (`bandit`, `semgrep`) on every push. A failing secret scan blocks the merge. Images are
built from pinned bases and scanned before they reach a registry.

## 9. Incident checklist

1. Set `DRY_RUN=true` and scale workers to zero — stops outbound effects immediately.
2. Rotate the systeme.io MCP and API keys, and `JWT_SECRET` (this invalidates all sessions and
   all in-flight event signatures, which is the point).
3. Read `tasks` for `status='done'` rows in the incident window — that is the full record of
   what the system actually did.
4. Check the systeme.io account directly for funnels, contacts, or broadcasts the system does
   not have a task row for.
