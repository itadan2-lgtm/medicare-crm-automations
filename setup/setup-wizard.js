// The guided setup: `npm run setup`.
//
// Asks plain-English questions, checks each answer against Notion as
// it's typed in (so a bad key is caught right away, not three steps
// later), finds the 7 data source IDs automatically, and writes .env
// itself. Nobody should have to hand-edit a config file to use this.
//
// Everything here uses only what ships with Node plus the deps npm
// install already pulled in.

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const readline = require("readline/promises");

const ENV_PATH = path.join(__dirname, "..", ".env");

const DATABASES = {
  "Clients": "CLIENTS_DATA_SOURCE_ID",
  "Leads (Intake)": "LEADS_DATA_SOURCE_ID",
  "SOA Records": "SOA_RECORDS_DATA_SOURCE_ID",
  "Appointments": "APPOINTMENTS_DATA_SOURCE_ID",
  "Policies / Commissions": "POLICIES_DATA_SOURCE_ID",
  "Carrier Reference (Chargeback Windows)": "CARRIER_REFERENCE_DATA_SOURCE_ID",
  "Tasks / Follow-ups": "TASKS_DATA_SOURCE_ID",
};

// ---------- little helpers ----------

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

async function ask(question, { fallback = "" } = {}) {
  const suffix = fallback ? ` (press Enter to keep what you had)` : "";
  const answer = (await rl.question(`${question}${suffix}\n> `)).trim();
  return answer || fallback;
}

async function askYesNo(question, defaultYes = false) {
  const hint = defaultYes ? "Y/n" : "y/N";
  const answer = (await rl.question(`${question} [${hint}] `)).trim().toLowerCase();
  if (!answer) return defaultYes;
  return answer.startsWith("y");
}

function say(text = "") {
  console.log(text);
}

function readExistingEnv() {
  if (!fs.existsSync(ENV_PATH)) return {};
  const values = {};
  for (const line of fs.readFileSync(ENV_PATH, "utf8").split("\n")) {
    const match = line.match(/^([A-Z_]+)=(.*)$/);
    if (match) values[match[1]] = match[2].trim();
  }
  return values;
}

function extractPageId(input) {
  const match = input.replace(/-/g, "").match(/([0-9a-f]{32})/i);
  if (!match) return null;
  const raw = match[1];
  return `${raw.slice(0, 8)}-${raw.slice(8, 12)}-${raw.slice(12, 16)}-${raw.slice(16, 20)}-${raw.slice(20)}`;
}

// ---------- the steps ----------

async function stepNotionKey(existing) {
  const { Client } = require("@notionhq/client");
  say("STEP 1 OF 4 — Your Notion secret key");
  say("");
  say("If you don't have one yet: open notion.so/my-integrations in your");
  say('browser, click "New integration", name it anything, and copy the');
  say('secret it shows you (it starts with "ntn_" or "secret_").');
  say("");

  for (;;) {
    const key = await ask("Paste your Notion secret key here:", {
      fallback: existing.NOTION_API_KEY,
    });
    if (!key) {
      say("\nThat was empty - paste the whole key and press Enter.\n");
      continue;
    }
    const notion = new Client({ auth: key });
    try {
      await notion.users.me({});
      say("\n✔ That key works.\n");
      return key;
    } catch (err) {
      if (err.code === "unauthorized") {
        say("\nNotion didn't accept that key. Usually this means part of it");
        say("got cut off while copying. Go back to notion.so/my-integrations,");
        say('open your integration, click "Show" next to the secret, and copy');
        say("the whole thing again.\n");
      } else {
        say(`\nCouldn't reach Notion (${err.message}). If your internet is`);
        say("fine, wait a moment and try pasting it again.\n");
      }
    }
  }
}

async function stepFindIds(notionKey, existing) {
  const { Client } = require("@notionhq/client");
  const notion = new Client({ auth: notionKey });

  say("STEP 2 OF 4 — Point me at your CRM");
  say("");
  say("Open your CRM's Home page in Notion, click Share -> Copy link,");
  say("and paste that link here. Before that works, the Home page has to");
  say("be connected to your integration: on the Home page click the •••");
  say('menu (top right) -> "Connect to" -> pick your integration.');
  say("");

  for (;;) {
    const link = await ask("Paste the link to your Home page:");
    const pageId = extractPageId(link);
    if (!pageId) {
      say("\nThat doesn't look like a Notion link. Use Share -> Copy link on");
      say("the Home page and paste the whole thing.\n");
      continue;
    }

    let blocks;
    try {
      blocks = await notion.blocks.children.list({ block_id: pageId, page_size: 100 });
    } catch (err) {
      say("\nNotion wouldn't show me that page. Almost always this means the");
      say("integration isn't connected yet: on the Home page, click the •••");
      say('menu -> "Connect to" -> pick your integration. Then paste the');
      say("link again.\n");
      continue;
    }

    const found = {};
    for (const block of blocks.results.filter((b) => b.type === "child_database")) {
      const db = await notion.databases.retrieve({ database_id: block.id });
      const dataSourceId = db.data_sources?.[0]?.id;
      if (dataSourceId) found[block.child_database.title] = dataSourceId;
    }

    const ids = {};
    const missing = [];
    for (const [title, envVar] of Object.entries(DATABASES)) {
      if (found[title]) ids[envVar] = found[title];
      else missing.push(title);
    }

    if (missing.length === 0) {
      say(`\n✔ Found all 7 databases.\n`);
      return ids;
    }

    say(`\nFound ${7 - missing.length} of 7 databases. Still missing:`);
    for (const title of missing) say(`  - ${title}`);
    say("");
    say("Each database has to be connected to your integration one by one");
    say("(Notion doesn't pass it down automatically). Open each missing one,");
    say('click its ••• menu -> "Connect to" -> your integration.');
    say("");
    const keepGoing = missing.length < 7 && (await askYesNo("Continue with just these for now? (You can re-run setup later.)"));
    if (keepGoing) {
      for (const [, envVar] of Object.entries(DATABASES)) {
        if (!ids[envVar] && existing[envVar]) ids[envVar] = existing[envVar];
      }
      say("");
      return ids;
    }
    say("Fix the connections in Notion, then paste the link again.\n");
  }
}

async function stepEmail(existing) {
  say("STEP 3 OF 4 — Alerts (optional)");
  say("");
  say("The scripts can email you (and optionally text you) when they");
  say("find something - a compliance flag, an approaching deadline.");
  say("Skip this and they'll still run; results just stay in the run logs.");
  say("");

  const values = {};

  if (await askYesNo("Do you want email alerts?", Boolean(existing.SENDGRID_API_KEY))) {
    say("\nEmail goes through SendGrid (free tier is plenty). From your");
    say("SendGrid account: Settings -> API Keys -> Create API Key.\n");
    values.SENDGRID_API_KEY = await ask("Paste your SendGrid API key:", { fallback: existing.SENDGRID_API_KEY });
    values.ALERT_EMAIL_TO = await ask("What email address should alerts go TO?", { fallback: existing.ALERT_EMAIL_TO });
    values.ALERT_EMAIL_FROM = await ask("What address should they come FROM? (must be verified in SendGrid)", { fallback: existing.ALERT_EMAIL_FROM });
    say("");
  } else {
    say("");
  }

  if (await askYesNo("Do you want text-message alerts too?", Boolean(existing.TWILIO_ACCOUNT_SID))) {
    say("\nTexts go through Twilio. From your Twilio console you need the");
    say("Account SID, Auth Token, and your Twilio phone number.\n");
    values.TWILIO_ACCOUNT_SID = await ask("Twilio Account SID:", { fallback: existing.TWILIO_ACCOUNT_SID });
    values.TWILIO_AUTH_TOKEN = await ask("Twilio Auth Token:", { fallback: existing.TWILIO_AUTH_TOKEN });
    values.TWILIO_FROM_NUMBER = await ask("Your Twilio phone number (like +15551234567):", { fallback: existing.TWILIO_FROM_NUMBER });
    values.ALERT_SMS_TO = await ask("What number should texts go TO?", { fallback: existing.ALERT_SMS_TO });
    say("");
  } else {
    say("");
  }

  return values;
}

function writeEnv(values) {
  const lines = [
    "# Written by `npm run setup`. Re-run that command any time to change",
    "# these - no need to edit this file by hand.",
    "",
    `NOTION_API_KEY=${values.NOTION_API_KEY || ""}`,
    "",
  ];
  for (const envVar of Object.values(DATABASES)) {
    lines.push(`${envVar}=${values[envVar] || ""}`);
  }
  lines.push(
    "",
    `SENDGRID_API_KEY=${values.SENDGRID_API_KEY || ""}`,
    `ALERT_EMAIL_TO=${values.ALERT_EMAIL_TO || ""}`,
    `ALERT_EMAIL_FROM=${values.ALERT_EMAIL_FROM || ""}`,
    "",
    `TWILIO_ACCOUNT_SID=${values.TWILIO_ACCOUNT_SID || ""}`,
    `TWILIO_AUTH_TOKEN=${values.TWILIO_AUTH_TOKEN || ""}`,
    `TWILIO_FROM_NUMBER=${values.TWILIO_FROM_NUMBER || ""}`,
    `ALERT_SMS_TO=${values.ALERT_SMS_TO || ""}`,
    "",
    `WEBHOOK_SECRET=${values.WEBHOOK_SECRET || ""}`,
    ""
  );
  fs.writeFileSync(ENV_PATH, lines.join("\n"), { mode: 0o600 });
}

// ---------- main ----------

async function main() {
  say("");
  say("=====================================================");
  say("  Medicare CRM automations - guided setup");
  say("=====================================================");
  say("");
  say("This takes about 5 minutes. You'll need two browser tabs open:");
  say("your Notion CRM, and notion.so/my-integrations.");
  say("");
  say("Nothing is sent anywhere except to Notion itself. Answers are");
  say("saved to a private file (.env) on this computer.");
  say("");

  const existing = readExistingEnv();
  if (existing.NOTION_API_KEY) {
    say("Looks like you've run setup before - I'll offer your previous");
    say("answers as defaults so you can just press Enter to keep them.");
    say("");
  }

  const notionKey = await stepNotionKey(existing);
  const ids = await stepFindIds(notionKey, existing);
  const alerts = await stepEmail(existing);

  const values = {
    NOTION_API_KEY: notionKey,
    ...ids,
    ...alerts,
    // carry forward anything skipped this run
    SENDGRID_API_KEY: alerts.SENDGRID_API_KEY ?? existing.SENDGRID_API_KEY,
    ALERT_EMAIL_TO: alerts.ALERT_EMAIL_TO ?? existing.ALERT_EMAIL_TO,
    ALERT_EMAIL_FROM: alerts.ALERT_EMAIL_FROM ?? existing.ALERT_EMAIL_FROM,
    TWILIO_ACCOUNT_SID: alerts.TWILIO_ACCOUNT_SID ?? existing.TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN: alerts.TWILIO_AUTH_TOKEN ?? existing.TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER: alerts.TWILIO_FROM_NUMBER ?? existing.TWILIO_FROM_NUMBER,
    ALERT_SMS_TO: alerts.ALERT_SMS_TO ?? existing.ALERT_SMS_TO,
    WEBHOOK_SECRET: existing.WEBHOOK_SECRET || crypto.randomBytes(24).toString("hex"),
  };

  writeEnv(values);

  say("STEP 4 OF 4 — Done. Here's what happens next.");
  say("");
  say("✔ Your settings are saved. To try a real check right now, run:");
  say("");
  say("    npm run doctor     (confirms everything is connected)");
  say("    npm run soa-check  (a real compliance check on your data)");
  say("");
  say("To make the checks run automatically every morning, the same");
  say("settings need to go into GitHub once. In your GitHub repo:");
  say("Settings -> Secrets and variables -> Actions -> New repository");
  say("secret. Add each of these names, copying its value from the .env");
  say("file in this folder (open it with any text editor):");
  say("");
  const secretNames = ["NOTION_API_KEY", ...Object.values(DATABASES)];
  for (const name of secretNames) say(`    ${name}`);
  say("");
  say("(Plus the SendGrid/Twilio ones if you set up alerts.)");
  say("The illustrated Setup-Guide.html walks through that screen too.");
  say("");
}

main()
  .catch((err) => {
    say("");
    say(`Something went wrong: ${err.message}`);
    say("Run `npm run setup` to try again - your progress so far is saved.");
    process.exitCode = 1;
  })
  .finally(() => rl.close());
