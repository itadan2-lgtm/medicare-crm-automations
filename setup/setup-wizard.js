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

const { DATABASES, extractPageId, findDataSources, searchDataSources } = require("./shared");

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

  say("STEP 2 OF 4 — Finding your databases");
  say("");

  // Usually no questions needed: ask Notion what the integration can
  // see. Only fall back to asking for a link when that's not enough.
  try {
    const { found, duplicates } = await searchDataSources(notion);
    if (duplicates.length === 0) {
      const ids = {};
      for (const [title, envVar] of Object.entries(DATABASES)) {
        if (found[title]) ids[envVar] = found[title];
      }
      if (Object.keys(ids).length === 7) {
        say("✔ Found all 7 databases on my own - nothing to paste.\n");
        return ids;
      }
    }
  } catch {
    // search hiccup - the link flow below works without it
  }

  say("I couldn't find everything by myself, so let's point me at it.");
  say("Open your CRM's Home page in Notion, click Share -> Copy link,");
  say("and paste that link here. Before that works, the Home page has to");
  say("be connected to your integration: on the Home page click the •••");
  say('menu (top right) -> "Connect to" -> pick your integration.');
  say("(Connected it just now? Notion can take a minute to catch up.)");
  say("");

  for (;;) {
    const link = await ask("Paste the link to your Home page:");
    const pageId = extractPageId(link);
    if (!pageId) {
      say("\nThat doesn't look like a Notion link. Use Share -> Copy link on");
      say("the Home page and paste the whole thing.\n");
      continue;
    }

    let found;
    try {
      found = await findDataSources(notion, pageId);
    } catch (err) {
      say("\nNotion wouldn't show me that page. Almost always this means the");
      say("integration isn't connected yet: on the Home page, click the •••");
      say('menu -> "Connect to" -> pick your integration. Then paste the');
      say("link again.\n");
      continue;
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
    say("Connecting the Home page usually covers everything inside it, but");
    say("these didn't pick it up. Open each missing one in Notion, click");
    say('its ••• menu -> "Connect to" -> your integration.');
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
    // an explicit "no" turns email off, even if it was on before
    values.SENDGRID_API_KEY = "";
    values.ALERT_EMAIL_TO = "";
    values.ALERT_EMAIL_FROM = "";
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
    // same for texts - "no" means off
    values.TWILIO_ACCOUNT_SID = "";
    values.TWILIO_AUTH_TOKEN = "";
    values.TWILIO_FROM_NUMBER = "";
    values.ALERT_SMS_TO = "";
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
  try {
    require.resolve("@notionhq/client");
  } catch {
    say("");
    say("One step first: run `npm install` (it downloads the pieces this");
    say("needs, takes about a minute), then run `npm run setup` again.");
    say("");
    process.exitCode = 1;
    return;
  }

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
    say("Nothing was changed. Run `npm run setup` to start again - if a");
    say("previous run finished, those answers will be offered as defaults.");
    process.exitCode = 1;
  })
  .finally(() => rl.close());
