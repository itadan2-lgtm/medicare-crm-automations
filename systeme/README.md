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
| `--playbook=NAME` | Build to house rules instead of generic best practice. See below. |
| `--save=FILE` | Write everything it says to a file — worth using whenever the run produces copy you have to paste somewhere. |
| `--dry-run` | Only systeme.io's read-only tools are switched on. It can plan and describe, but it cannot write — enforced by the connection, not by asking nicely. |
| `--allow-deletes` | Switches the delete/remove tools back on. Off by default. |
| `--effort=LEVEL` | `low`, `medium`, `high`, `xhigh` (default), `max`. Lower is cheaper and faster; higher thinks harder about layout and copy. |
| `--turns=N` | Give up after N rounds. Default 40. |

## Playbooks

Generic landing-page advice — six to ten sections, testimonials, an FAQ, a
stats band — is wrong for some jobs. An opt-in page converts better with one
email field and nothing else on it. A playbook is a markdown file of house
rules that **overrides** the general guidance wherever the two disagree.

```bash
npm run store -- --playbook=lead-magnet --save=emails.md \
  "A free doctor-visit prep checklist for women in perimenopause"
```

Shipped with one: **`lead-magnet`**, which encodes the free-plan lead magnet
build — a bare one-section opt-in page, a thank-you page that does the
inbox-check and one soft sell, no countdowns or invented statistics, a check
of your remaining free-plan funnel slots, and the four-email sequence
written out for you to paste in.

Add your own by dropping a `.md` file into `systeme/playbooks/` — no code
change needed. `--playbook` also accepts a path to a file anywhere, for a
one-off brief you don't want to check in.

The one thing a playbook can't override is systeme.io's own page limits
(columns summing to 12, and so on) — those aren't matters of style.

### The email sequence has to be built by hand

systeme.io's tools cover funnels, pages, contacts, tags and newsletters.
**There is no workflow or automation tool**, so nothing here can build the
nurture sequence. The `lead-magnet` playbook writes all four emails out
instead — subject lines, bodies, and the wait between each — for you to
paste into Automations → Workflows → Create, triggered on the opt-in form
being submitted. Use `--save=emails.md` so you're not scraping them out of
a terminal.

The whole sequence goes in that **one** workflow, waits included. The free
plan gives you one workflow and one automation rule, and a workflow takes
unlimited actions in any order — so the rule stays free for something that
actually needs it later, rather than being spent on a tagging step.

Two other things it can't do, and will tell you about: uploading your
download file (do that in Contacts → Files, then paste the URL into email 1),
and adding a dropdown to the opt-in form — the form only supports email,
first name, last name and phone, so a segmentation question has to be added
in the page editor by hand.

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
| `internal/playbook.js` | Loads house rules from `playbooks/` |
| `internal/agent.js` | Runs the conversation and adds up the bill |
| `internal/validate.js` | systeme.io's page rules, in code |
| `check-designs.js` | Checks every design in `designs/` offline |
| `playbooks/*.md` | House rules, one file per kind of funnel |
| `designs/*.json` | Hand-written page designs, ready to save |
| `tests/run-tests.js` | Offline tests — no keys, no charges |

Run `npm run store:test` any time; it never touches the network.

## Writing a page design by hand

Sometimes you want to art-direct a page yourself rather than describe it.
Drop a JSON file into `systeme/designs/`, named `<name>.<page_type>.json`,
and check it before it goes anywhere near your account:

```bash
npm run store:designs
```

That runs offline and free. It catches the things systeme.io rejects — a row
whose columns add up to 11, an `h1` outside the hero section, a block type
that page type doesn't accept, a second form, a missing nullable field — and
tells you which section and row, which the API's own error doesn't.

Then hand the file to the builder:

```bash
npm run store -- "Save systeme/designs/checklist-optin.squeeze.json
                  to the Opt-in page of my Checklist funnel"
```

Three designs ship with the repo, for the perimenopause checklist funnel:
the opt-in page, the thank-you page, and a standalone appointment-prep info
page.

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
- **No workflows, no email automation, no file uploads.** See the playbook
  section above for what to do by hand.
