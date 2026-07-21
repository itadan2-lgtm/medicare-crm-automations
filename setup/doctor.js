// `npm run doctor` - checks the whole setup and says, in plain English,
// what's working and what to do about anything that isn't. Run it
// whenever something seems off; it never changes any data.

const fs = require("fs");
const path = require("path");

const ENV_PATH = path.join(__dirname, "..", ".env");

const { DATABASES } = require("./shared");

const ok = (msg) => console.log(`  ✔ ${msg}`);
const bad = (msg) => console.log(`  ✖ ${msg}`);
const note = (msg) => console.log(`    ${msg}`);

async function main() {
  console.log("\nChecking your setup...\n");
  let problems = 0;

  // 1. Settings - .env if present, plus whatever One-time setup saved
  if (fs.existsSync(ENV_PATH)) {
    ok("Settings file exists.");
    require("dotenv").config({ path: ENV_PATH });
  }
  let saved = {};
  try {
    saved = require("../automations/internal/data-sources.json");
  } catch {}

  // 2. Notion key
  if (!process.env.NOTION_API_KEY) {
    if (Object.keys(saved).length > 0) {
      bad("This computer doesn't have your Notion key yet.");
      note("Your databases are already set up (the One-time setup workflow");
      note("saved them), so the GitHub runs are fine. To run checks from");
      note("this computer too, run `npm run setup` and paste your key.");
    } else {
      bad("No settings found yet.");
      note("Run `npm run setup` - it asks a few questions and creates them.");
    }
    console.log("");
    process.exitCode = 1;
    return;
  }

  const { Client } = require("@notionhq/client");
  const notion = new Client({ auth: process.env.NOTION_API_KEY });
  try {
    await notion.users.me({});
    ok("Notion accepts your key.");
  } catch (err) {
    if (err.code === "unauthorized") {
      bad("Notion rejected your key.");
      note("It may have been revoked or copied incompletely. Run `npm run");
      note("setup` and paste it again from notion.so/my-integrations.");
    } else {
      bad(`Couldn't reach Notion (${err.message}).`);
      note("Check your internet connection and run this again.");
    }
    console.log("");
    process.exitCode = 1;
    return;
  }

  // 3. Each database (env first, then whatever One-time setup saved)
  for (const [title, envVar] of Object.entries(DATABASES)) {
    const id = process.env[envVar] || saved[envVar];
    if (!id) {
      bad(`"${title}" isn't set up yet.`);
      note("Run `npm run setup` and paste your Home page link when asked.");
      problems++;
      continue;
    }
    try {
      await notion.dataSources.query({ data_source_id: id, page_size: 1 });
      ok(`Can read "${title}".`);
    } catch (err) {
      bad(`Can't read "${title}".`);
      note(`In Notion, open that database, click its ••• menu -> "Connections"`);
      note(`-> "Add connections" -> your integration. Then run this check again.`);
      problems++;
    }
  }

  // 4. Alerts
  if (process.env.SENDGRID_API_KEY && process.env.ALERT_EMAIL_TO) {
    ok(`Email alerts will go to ${process.env.ALERT_EMAIL_TO}.`);
  } else {
    ok("Email alerts are off (that's fine - results still show in run logs).");
  }
  if (process.env.TWILIO_ACCOUNT_SID && process.env.ALERT_SMS_TO) {
    ok(`Text alerts will go to ${process.env.ALERT_SMS_TO}.`);
  } else {
    ok("Text alerts are off.");
  }

  console.log("");
  if (problems === 0) {
    console.log("Everything looks good. Try a real check: npm run soa-check\n");
  } else {
    console.log(`${problems} thing${problems === 1 ? "" : "s"} to fix above, then run this again.\n`);
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.log(`\nThe check itself hit an error: ${err.message}`);
  console.log("Run it again in a moment; if it keeps happening, run `npm run setup`.\n");
  process.exitCode = 1;
});
