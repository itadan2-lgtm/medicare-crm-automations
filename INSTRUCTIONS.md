# Instructions

**Prefer pictures?** Open `Setup-Guide.html` in this same folder — same steps, illustrated. This file is the plain-text version, easier to search and copy commands from.

**Already set up and wondering how to use it day to day?** Open `How-To-Use-Guide.html` — the everyday workflow: leads, appointments, SOAs, policies, and what every status color means. (The same guide also lives inside the Notion template, at the top of the Home page.)

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
Go to notion.so/my-integrations -> New integration. **Pick the same
workspace your CRM is in** (if you have more than one, this is the #1
thing people get wrong - the integration won't show up later
otherwise). Name it whatever, and copy the secret it gives you.

Then connect it to your CRM, once: open your Home page, ••• menu ->
**Connections** -> **Add connections** -> pick your integration.
(Notion used to call this "Connect to"; it's now "Connections." Start
typing your integration's name - the list is empty until you do.) The
databases inside the Home page come along with it. (If setup later
reports one as missing, open just that database and connect it the
same way, then run setup again.)

**3. Finish setup - two ways to do it. Pick one.**

**The browser way (recommended - no terminal, nothing to install).**
Everything happens on github.com; a phone browser works fine:

1. Get your own copy on GitHub (free account is fine). Open the
   template at
   https://github.com/itadan2-lgtm/medicare-crm-automations -> click
   the green "Use this template" -> Create a new repository -> name it
   anything, keep it Private -> Create. That copies everything in one
   click, no download needed.
   (No button, or prefer to add the files by hand? Unzip
   `medicare-crm-automations.zip`, make a new private repo, and upload
   the files yourself - be sure to include the hidden `.github` folder;
   reveal hidden files first on Mac with Cmd+Shift+period, on Windows
   via File Explorer -> View -> Show -> Hidden items.)
2. Add your Notion secret to GitHub, once: repo -> Settings -> Secrets
   and variables -> Actions -> New repository secret. Name it
   `NOTION_API_KEY`, paste the secret from step 2 as the value.
3. Actions tab -> **One-time setup** -> Run workflow -> green Run
   button. That's it - it finds your databases through the connection
   you made in step 2. Leave the branch dropdown and the optional link
   box alone (the run's summary will say so if it ever needs the link).
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

**4. Turn on email alerts (optional, free, recommended).** This sends
the morning digest and compliance flags to your inbox so you never
have to open GitHub to check. It's free through SendGrid. To get the
key:

  1. Sign up free at sendgrid.com (free tier = 100 emails/day, plenty).
  2. Verify your sender: Settings -> Sender Authentication -> Verify a
     Single Sender -> use your own email and confirm their email.
  3. Create the key: Settings -> API Keys -> Create API Key -> Full
     Access -> Create -> copy it right away (shown only once).
  4. Add three GitHub secrets (same screen as `NOTION_API_KEY`):
     `SENDGRID_API_KEY` = the key, `ALERT_EMAIL_TO` = where alerts go,
     `ALERT_EMAIL_FROM` = the address you just verified.

> **The first alert almost always lands in your Spam folder - this is
> normal.** Because SendGrid sends "from" your everyday email address
> (like a Gmail one) but through its own servers, your inbox can't verify
> it the first time and quietly files it under Spam. It is NOT lost.
> Do this once and it's fixed forever:
>   1. Open your Spam/Junk folder and find the "Medicare CRM" email.
>   2. Mark it **Not spam** (Gmail: the "Not spam" button at the top).
>   3. Make future ones skip spam - in Gmail: Settings -> Filters and
>      Blocked Addresses -> Create a new filter -> Subject: `Medicare CRM`
>      -> Create filter -> tick **"Never send it to Spam"** -> Create
>      filter. (Other inboxes: add the sender to your contacts / safe
>      senders.)
> After that, every morning's alert goes straight to your inbox.

Skip this and results just stay in each run's log.

*Prefer texts?* Twilio sends SMS for a few cents each (not free). From
the Twilio Console, copy your Account SID and Auth Token from the
dashboard and buy a phone number under Phone Numbers, then add
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, and
`ALERT_SMS_TO` as secrets. Otherwise skip it - email is plenty.

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
