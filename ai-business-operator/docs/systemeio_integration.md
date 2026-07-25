# systeme.io integration

Two separate interfaces with two separate keys. Getting this wrong is the most common cause of
confusing 401s, so start here.

| | MCP | Public API |
|---|---|---|
| Header | `X-MCP-Key: {key}` | `X-API-Key: {key}` |
| Base | `SYSTEMEIO_MCP_BASE` | `SYSTEMEIO_API_BASE` |
| Covers | Contacts, tags, contact fields, newsletters | Funnels, funnel steps, pages, products, coupons, payments |
| Key lifetime | Expires — 90 days maximum | Longer-lived, still rotate |

Anything covered by neither is the browser agent's job.

## 1. Getting keys

1. systeme.io → **Settings → MCP & API Keys**.
2. Create one MCP key and one Public API key.
3. Put them in `.env` as `SYSTEMEIO_MCP_KEY` and `SYSTEMEIO_API_KEY`.
4. **Record the MCP key's expiry date.** It is capped at 90 days. Set a calendar reminder for
   day 75 — an expired key surfaces as a generic 401 and looks like a code bug.

Keys are read server-side only. They must never appear in a `NEXT_PUBLIC_*` variable, a frontend
bundle, a log line, or a commit.

## 2. MCP operations

Contacts (CRUD), tags (CRUD), contact fields (list), newsletters (create/update). The key can
also be passed as `?mcpKey=` in the URL, but prefer the header — query strings end up in access
logs.

```python
from app.services.systemeio import SystemeIOClient

async with SystemeIOClient.from_env() as client:
    contact = await client.mcp_create_contact(email="lead@example.com", fields={"first_name": "Ada"})
    await client.mcp_assign_tag(contact_id=contact["id"], tag_name="fitness-optin")
```

## 3. Public API operations

```python
funnel = await client.create_funnel(name="Home Fitness Launch", locale="en")
step = await client.create_funnel_step(funnel_id=funnel["id"], step_type="optin", name="Opt-in")
await client.save_page_content(page_id=step["page_id"], content=page_json)
```

Endpoints in use:

| Purpose | Method / path |
|---|---|
| Create funnel | `POST /funnels` |
| List funnels | `GET /funnels` |
| Add funnel step | `POST /funnelSteps` |
| Save page content | `PUT /page-editor` (**replaces** content — read first, then merge) |
| Products | `POST /products`, `GET /products` |
| Coupons | `POST /coupons` |

`PUT /page-editor` replacing rather than patching is the single sharpest edge here. The client
enforces read-then-merge to avoid silently discarding a page.

## 4. Rate limits

MCP and the Public API **share** a rate-limit budget. Every response carries:

- `X-RateLimit-Remaining` — requests left in the window
- `X-RateLimit-Refill` — seconds until the window refills

`SystemeIOClient` reads both after each call, exposes them as `client.rate_limit`, and:

- sleeps proactively when `remaining` drops below `RATE_LIMIT_FLOOR` (default 3),
- on `429`, honours `Retry-After` when present, otherwise backs off exponentially with jitter,
  up to `MAX_RETRIES` (default 4).

Because the budget is shared, the browser agent counts against it too — hence
`MAX_BROWSER_SESSIONS`.

## 5. What the API can't do

Page **layout and design** in the funnel editor, funnel step template selection, and some
funnel-type creation paths are UI-only. The pattern is:

1. Create the funnel and steps via the Public API (fast, reliable, returns IDs).
2. Hand the IDs to the browser agent, which opens the editor and does the visual work.
3. Store the resulting systeme.io IDs in `funnels` / `funnel_steps` so the system can find its
   own work later.

Never do step 1 in Playwright because step 2 needs it — the API path is an order of magnitude
more reliable.

## 6. Testing

`DRY_RUN=true` (the default) makes every write log its method, path, and body instead of
sending it. Unit tests use `httpx.MockTransport` with recorded fixtures in
`backend/tests/fixtures/systemeio/`. Do not point tests at a live account; use a dedicated
throwaway account for manual integration checks and never a production one.
