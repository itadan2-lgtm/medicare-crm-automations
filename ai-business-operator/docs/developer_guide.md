# Developer guide

## Prerequisites

Docker + Docker Compose, Python 3.11, Node 20.

## First run

```bash
cp .env.example .env
# Set at minimum: JWT_SECRET, ANTHROPIC_API_KEY
# Leave DRY_RUN=true until you have a throwaway systeme.io account.

make up          # postgres, redis, backend, one worker
make migrate     # apply infra/sql/001_init.sql
make test        # backend test suite
```

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

Frontend:

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
```

## Working without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]"
uvicorn app.main:app --reload --app-dir backend
python -m agents.worker --agent research_agent    # in another shell
```

You still need Postgres and Redis; `docker compose -f infra/docker-compose.yml up -d postgres redis`
gets you those alone.

## Make targets

| Target | Does |
|---|---|
| `make up` / `make down` | Start / stop the local stack |
| `make logs` | Tail all service logs |
| `make migrate` | Apply the schema to the running database |
| `make test` | `pytest` for the backend and agents |
| `make lint` | `ruff check` + `mypy` |
| `make fmt` | `ruff format` |
| `make worker AGENT=copy_agent` | Run a single agent worker in the foreground |
| `make psql` | Open a shell on the database |

## Adding an agent

1. Add its row to `AGENTS.md` — purpose, inputs, outputs, allowed tools, memory, failures.
2. Add the matching entry to `agents/registry.py` (the enforced copy of that contract).
3. `mkdir agents/<name>_agent` with `agent.py` (subclass `BaseAgent`) and `prompts.json`.
4. Implement `build_prompt()` and `parse_output()`. Validate the output against a Pydantic
   model — never trust the shape of an LLM response.
5. Add a unit test with a fake LLM returning a fixed string; assert the parsed output.
6. Register the task types it handles in `backend/app/services/orchestrator.py`.

## Adding a systeme.io call

Everything goes in `backend/app/services/systemeio.py`. Add the method there, respect
`DRY_RUN`, and add a fixture-backed test. Ad-hoc `httpx` calls to systeme.io elsewhere will be
rejected in review — the client owns retries, rate limits, and the dry-run switch.

## Conventions

- `ruff format` before committing; `make lint` must be clean.
- Type hints on anything crossing a module boundary.
- Structured logs: `log.info("task.claimed", extra={"task_id": tid, "agent": name})`.
- Never log a key, token, or password. The redaction filter is a safety net, not permission.
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).

## Debugging

**A task is stuck in `pending`** — check `depends_on`; it stays unclaimable until every
dependency is `done`. `make psql` then:

```sql
SELECT id, task_type, status, depends_on FROM tasks WHERE project_id = 1 ORDER BY id;
```

**A task is in `awaiting_approval`** — that is the human gate working. Approve it in the
dashboard or `POST /tasks/{id}/approve`.

**Playwright fails on a selector** — a screenshot and trace land in `PLAYWRIGHT_ARTIFACT_DIR`.
Re-run headed: `PLAYWRIGHT_HEADLESS=false make browser-agent`. If the fix is a CSS selector,
stop — use `get_by_role`/`get_by_label` instead; CSS selectors break on every systeme.io release.

**401 from systeme.io** — check which key the call used. MCP keys expire within 90 days and an
expired key returns a generic 401 that reads like a code bug.
