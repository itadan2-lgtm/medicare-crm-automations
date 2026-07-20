# Instructions

**Prefer pictures?** Open `Setup-Guide.html` in this same folder — same steps, illustrated. This file is the plain-text version, easier to search and copy commands from.

Five scripts that turn the Notion CRM from "a place to store data" into
something that actually watches deadlines and compliance for you. They
run on your own free-tier accounts, nothing here needs paid hosting.

This is a workflow aid, not legal advice. The SOA rule logic especially
should get re-checked against current CMS guidance before you trust it
blindly - rules change, sometimes more than once a year.

**Licensed for single-user use.** See `LICENSE.md` before sharing this
with anyone else.

## What's in this folder

You will not need to open most of this. Here's the map:

| Folder | What it is | Do you need to open it? |
|---|---|---|
| `setup/` | Guided setup + health check | Yes, step 3 below |
| `automations/` | The 4 daily scripts | Only if something's not working |
| `automations/internal/` | Shared code the scripts lean on | No |
| `automations/tests/` | Proof the logic works (30 checks) | No, but `npm test` is reassuring |
| `api/` | The 1 script that runs differently (see why below) | Only when deploying it |
| `.github/` | Tells GitHub to run things daily | No |

## What runs where

| Script | Runs on | Schedule |
|---|---|---|
| `automations/daily-digest.js` | GitHub Actions | daily |
| `api/lead-webhook.js` | Vercel | instantly, per form submission |

`daily-digest.js` runs all 4 checks (SOA compliance, enrollment deadlines, chargeback tracker, T65 tagger) back to back and sends **one** summary email/text at the end — "2 checked, 1 flagged," per script — instead of four separate notifications. Individual compliance flags still alert the moment they're found; the digest is the end-of-day rollup on top of that. Run any single check on its own with `npm run soa-check` etc. if you ever need to.

The webhook's different - it has to be listening the second someone submits your intake form, which a once-a-day job can't do. That one deploys to Vercel instead. Both free, both things you already have access to with a GitHub account. (This is also why `api/` can't be renamed or moved - Vercel looks for that exact folder name.)

## Setup

**1. Duplicate the Notion template**, if you haven't. Everything below
refers to your copy - your IDs will be different from any screenshots.

**2. Create a Notion integration.**
Go to notion.so/my-integrations -> New integration. Name it whatever.
Copy the secret it gives you. Then connect it to your CRM, once: open
your Home page, ••• menu -> Connect to -> your integration. The
databases inside the Home page come along with it. (If setup later
reports one as missing, open just that database and connect it the
same way, then run setup again.)

**3. Finish setup - two ways to do it. Pick one.**

**The browser way (recommended - no terminal, nothing to install).**
Everything happens on github.com; a phone browser works fine:

1. Get your own copy of this project on GitHub (free account is fine).
   Given a template link? Open it -> Use this template -> Create a new
   repository (keep it Private). Given a zip? github.com -> + -> New
   repository (private) -> "uploading an existing file" -> drag in
   everything from the unzipped folder.
2. Add your Notion secret to GitHub, once: repo -> Settings -> Secrets
   and variables -> Actions -> New repository secret. Name it
   `NOTION_API_KEY`, paste the secret from step 2 as the value.
3. Actions tab -> **One-time setup** -> Run workflow -> paste the link
   to your CRM's Home page (in Notion: Share -> Copy link) -> Run.
   Leave the branch dropdown alone - the preselected one is correct,
   and the run will stop and tell you if it's ever set wrong.
4. Open the run when it finishes. Its Summary page says, in plain
   English, whether everything connected - and if not, exactly what to
   fix and that you can just run it again.

That's it. The workflow finds all 7 database IDs itself and saves them
to the repo (`automations/internal/data-sources.json` - they're not
secrets, they're useless without your key). The daily checks start
running on their own from the next morning.

**The computer way** (if you'd rather run things locally, or want to
tinker):
```bash
npm install
npm run setup
```
A guided assistant asks a few plain-English questions - your Notion
secret, your Home page link, whether you want alerts - checks each
answer as you go, and writes the settings file for you. `npm run
doctor` reports the health of the whole setup any time. The fully
manual route (`npm run find-ids`, hand-edit `.env` per `.env.example`)
still works too.

**4. Want email or text alerts?** Add these as additional GitHub
secrets, same screen as `NOTION_API_KEY`: `SENDGRID_API_KEY`,
`ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM` for email (SendGrid free tier is
plenty); `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_FROM_NUMBER`, `ALERT_SMS_TO` for texts (Twilio charges a few
cents per text - the only thing here that isn't free). Skip this and
results just stay in each run's log.

**5. Turn on the daily checks.**
`.github/workflows/daily-checks.yml` runs automatically once secrets are
set (8am ET by default, edit the cron line to change it). You can also
trigger it by hand from the Actions tab -> Daily Compliance & Deadline
Checks -> Run workflow, which is the fastest way to confirm it's wired up
before trusting it unattended.

**6. Deploy the lead webhook** (optional, only if you want auto-import).
Push this repo to your own GitHub, then vercel.com -> New Project ->
import it. Vercel finds `api/lead-webhook.js` automatically, no config
needed. Add just `NOTION_API_KEY` and `WEBHOOK_SECRET` (any random
string; the form has to send it back in a header) in Vercel's
Environment Variables - the database IDs deploy with the repo if you
ran the One-time setup workflow. Your endpoint is
`https://<your-project>.vercel.app/api/lead-webhook` - point Tally,
Typeform, or a plain form at that, with header
`x-webhook-secret: <your WEBHOOK_SECRET>`.

**7. Test it.**
```bash
npm run doctor     # plain-English health check of the whole setup
npm test           # offline logic tests, should say 24 passed + 6 passed
npm run soa-check  # a real check against your actual Notion data
```

## Updating the rules

`automations/internal/config.js` holds every date and threshold this
depends on - the SOA rule cutoff, AEP/OEP dates, the chargeback buffer,
the T65 window. If CMS changes something or a plan year shifts, that's
the one file to touch.

The SOA 48-hour cutoff is currently Oct 1 2026, based on CMS's May 2026
FAQ memo. AEP (Oct 15 - Dec 7) and OEP (Jan 1 - Mar 31) have been stable
for years but worth a glance each fall anyway.

## Known limitations

- SEP is event-triggered (a move, losing other coverage) and can't be
  inferred from DOB or plan data, so the enrollment script never sets or
  clears it. That stays manual.
- T65 tagger only sees people already in Clients with a DOB filled in. No
  external T65 list support - if you buy one, route it through the lead
  webhook first, convert to Clients, then this picks it up.
- The old 48-hour SOA rule has a couple of narrow documented exceptions
  (walk-in enrollment events, etc.) that this script doesn't model. Treat
  a flag as "go double check," not a final verdict.
