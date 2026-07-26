# Building systeme.io stores with Claude

Describe the funnel you want in plain English; Claude designs it and builds
it in your real systeme.io account.

```bash
npm run store -- "Build a lead magnet funnel for a free Medicare enrollment
                  checklist aimed at people turning 65"
```

It plans the funnel, creates it, writes every page — headline, copy, opt-in
form, testimonials, FAQ, footer — and prints the dashboard link when it's
done.

This is separate from the Notion CRM automations in the rest of this repo.
Nothing here reads or writes your CRM, and the daily checks don't need it.

## How it connects

```
you  →  npm run store  →  Anthropic (Claude)  →  systeme.io MCP server  →  your account
              ^                    ^                       ^
        your request        ANTHROPIC_API_KEY       SYSTEME_MCP_KEY
```

Claude never reaches systeme.io from this computer. It connects to
systeme.io's own MCP server — the same connection systeme.io documents for
the Claude app — and this script just drives it from the command line so it
can run unattended, repeatably, and with guard rails.

That means the systeme.io tools run on Anthropic's side, so **whatever tools
you switch off here genuinely cannot be called**, no matter what Claude
decides mid-run.

## Setup (about five minutes)

**1. Get your systeme.io MCP key.** In systeme.io: **Settings → Public API
keys → MCP keys → create a key**, then copy it.

**2. Get an Anthropic API key.** At
[console.anthropic.com](https://console.anthropic.com) → **API keys**. This
is a pay-as-you-go developer key and is *not* the same thing as a Claude
Pro/Max subscription — a subscription won't work here. Add a few dollars of
credit under Billing.

**3. Put both in `.env`** (create the file in the project root if it isn't
there yet):

```
ANTHROPIC_API_KEY=sk-ant-...
SYSTEME_MCP_KEY=your-mcp-key
```

**4. Install and check.**

```bash
npm install
npm run store:check
```

`store:check` is read-only. It confirms both keys work, connects to your
account, and prints your existing funnels back to you. If that works,
everything works.

## Using it

```bash
# See what it would do, touching nothing
npm run store -- --dry-run "Build a webinar registration funnel for agents"

# Build for real
npm run store -- "Build a lead magnet funnel for a free Medicare
                  enrollment checklist for people turning 65"

# Ask about what's already there
npm run store -- "List my funnels and tell me which have empty pages"

# Work on an existing funnel
npm run store -- "Add a thank-you page to my 'email collector' funnel"
```

| Option | What it does |
|---|---|
| `--dry-run` | Only systeme.io's read-only tools are switched on. It can plan and describe, but it cannot write — enforced by the connection, not by asking nicely. |
| `--allow-deletes` | Switches the delete/remove tools back on. Off by default. |
| `--effort=LEVEL` | `low`, `medium`, `high`, `xhigh` (default), `max`. Lower is cheaper and faster; higher thinks harder about layout and copy. |
| `--turns=N` | Give up after N rounds. Default 40. |

### What it costs

A full two-page funnel is typically a few hundred thousand tokens once
you count systeme.io's page schema and the design work — on the order of
**$1–3 at Opus 5 pricing**. Every run prints its token count at the end.
`--effort=medium` cuts that noticeably; use `--dry-run` while you're
iterating on the wording of your request, since it does less work.

### Safety

Three things are true by default, and two of them are enforced by the
connection rather than by instructions:

- **Delete and remove tools are switched off** (`remove_contact`,
  `remove_contact_tag`, `remove_tag`, `delete_coupon`). You have to pass
  `--allow-deletes` to reach them.
- **`--dry-run` cannot write anything.** Only the `get_*` and `describe_*`
  tools are enabled.
- Claude is also told not to delete, not to modify funnels it wasn't asked
  about, and not to email anyone or send a newsletter unless that's the
  request. That's an instruction, not a lock — the two above are the locks.

If Anthropic ever rejects the per-tool settings, the run **stops** rather
than quietly continuing without the guard rails.

### Made-up testimonials

Claude will write testimonials, star ratings, and statistics if the page
design calls for them and you haven't supplied real ones. It's told to flag
whatever it invented in its closing summary. **Read that list and replace
those before you send traffic to the page** — invented reviews on a live
Medicare page are a compliance problem, not a placeholder.

## What's in here

| File | What it is |
|---|---|
| `store.js` | The command you run |
| `check.js` | The read-only health check |
| `internal/config.js` | Keys, defaults, and the connection URL |
| `internal/tools.js` | Which systeme.io tools are allowed on a run |
| `internal/prompt.js` | The brief Claude works from |
| `internal/agent.js` | Runs the conversation and adds up the bill |
| `tests/run-tests.js` | Offline tests — no keys, no charges |

Run `npm run store:test` any time; it never touches the network.

## Page types it can build

systeme.io accepts six page types, and each one has its own rules about how
many sections it can have and which blocks fit in them:

| Page type | Sections | Good for |
|---|---|---|
| `squeeze` | 6–10 | The main opt-in landing page |
| `opt_in_thank_you_page` | 2–3 | What they see after signing up |
| `link_in_bio` | 1 | A social profile link page |
| `info_page` | 2–12 | Long-form info, policies, guides |
| `inline` | 1–2 | A form embedded in another page |
| `popup` | 1–2 | A form in an overlay |

Claude asks systeme.io for the exact, current schema before designing each
page, so this list stays right even if systeme.io adds block types.

## Known limits

- **The funnel is created as a draft in your account.** Review it in the
  dashboard before pointing traffic at it. Nothing here publishes or buys a
  domain.
- **Images are placeholders.** Page designs describe the image they want and
  systeme.io fills in a stock placeholder. Swap in your own in the editor.
- **It builds pages, not products.** Payment settings, order bumps, and
  course content aren't part of the page-design tools.
- **Existing pages can't be edited in place.** systeme.io's page-content
  tool replaces a whole page body; it has no partial-edit mode. Ask for a
  new page rather than a tweak to an existing one.
