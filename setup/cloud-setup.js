// The browser-only setup. Runs inside GitHub Actions ("One-time setup"
// workflow), never on the buyer's computer. They paste their Home page
// link into the Run workflow form; this finds the 7 data source IDs and
// saves them to automations/internal/data-sources.json, which the
// workflow then commits. IDs aren't secrets - they're useless without
// the Notion key, which stays in GitHub Secrets.
//
// Everything this prints lands in the run's summary page, so write for
// someone who has never seen a terminal.

const fs = require("fs");
const path = require("path");

const OUT_PATH = path.join(__dirname, "..", "automations", "internal", "data-sources.json");

const DATABASES = {
  "Clients": "CLIENTS_DATA_SOURCE_ID",
  "Leads (Intake)": "LEADS_DATA_SOURCE_ID",
  "SOA Records": "SOA_RECORDS_DATA_SOURCE_ID",
  "Appointments": "APPOINTMENTS_DATA_SOURCE_ID",
  "Policies / Commissions": "POLICIES_DATA_SOURCE_ID",
  "Carrier Reference (Chargeback Windows)": "CARRIER_REFERENCE_DATA_SOURCE_ID",
  "Tasks / Follow-ups": "TASKS_DATA_SOURCE_ID",
};

// Goes to the pretty summary panel on the run page (and the log).
const summaryLines = [];
function report(line = "") {
  console.log(line);
  summaryLines.push(line);
}
function flushSummary() {
  if (process.env.GITHUB_STEP_SUMMARY) {
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, summaryLines.join("\n\n") + "\n");
  }
}

function extractPageId(input) {
  const match = input.replace(/-/g, "").match(/([0-9a-f]{32})/i);
  if (!match) return null;
  const raw = match[1];
  return `${raw.slice(0, 8)}-${raw.slice(8, 12)}-${raw.slice(12, 16)}-${raw.slice(16, 20)}-${raw.slice(20)}`;
}

async function main() {
  const { Client } = require("@notionhq/client");
  const key = process.env.NOTION_API_KEY;
  const link = (process.env.HOME_PAGE_LINK || "").trim();

  report("## Setting up your CRM automations");

  if (!key) {
    report("### ❌ First, add your Notion key");
    report(
      "GitHub doesn't have your Notion secret key yet. Add it once:\n" +
        "1. In this repo, click **Settings** (top menu) → **Secrets and variables** → **Actions**.\n" +
        "2. Click **New repository secret**.\n" +
        "3. Name: `NOTION_API_KEY` — Value: the secret from notion.so/my-integrations.\n" +
        "4. Come back to the **Actions** tab and run **One-time setup** again."
    );
    process.exitCode = 1;
    return;
  }

  const notion = new Client({ auth: key });
  try {
    await notion.users.me({});
    report("✔ Your Notion key works.");
  } catch (err) {
    if (err.code === "unauthorized") {
      report("### ❌ Notion didn't accept your key");
      report(
        "Usually part of it got cut off while copying. Go to notion.so/my-integrations, " +
          "open your integration, click **Show** next to the secret and copy the whole thing. " +
          "Then update it here: **Settings → Secrets and variables → Actions → NOTION_API_KEY → Update**, " +
          "and run this again."
      );
    } else {
      report(`### ❌ Couldn't reach Notion (${err.message})`);
      report("This is usually temporary - run this workflow again in a minute.");
    }
    process.exitCode = 1;
    return;
  }

  const pageId = link ? extractPageId(link) : null;
  if (!pageId) {
    report("### ❌ That link didn't look like a Notion page");
    report(
      "In Notion, open your CRM's **Home** page, click **Share** (top right) → **Copy link**, " +
        "and paste the whole link into the box when you run this workflow."
    );
    process.exitCode = 1;
    return;
  }

  let blocks;
  try {
    blocks = await notion.blocks.children.list({ block_id: pageId, page_size: 100 });
  } catch (err) {
    report("### ❌ Notion wouldn't show me that page");
    report(
      "Almost always this means the page isn't connected to your integration yet. " +
        "On the Home page in Notion, click the **•••** menu (top right) → **Connect to** → " +
        "pick your integration. Then run this workflow again with the same link."
    );
    process.exitCode = 1;
    return;
  }

  const found = {};
  for (const block of blocks.results.filter((b) => b.type === "child_database")) {
    const db = await notion.databases.retrieve({ database_id: block.id });
    const dataSourceId = db.data_sources?.[0]?.id;
    if (dataSourceId) found[block.child_database.title] = dataSourceId;
  }

  const saved = fs.existsSync(OUT_PATH) ? JSON.parse(fs.readFileSync(OUT_PATH, "utf8")) : {};
  const missing = [];
  for (const [title, envVar] of Object.entries(DATABASES)) {
    if (found[title]) saved[envVar] = found[title];
    else if (!saved[envVar]) missing.push(title);
  }

  if (Object.keys(saved).length > 0) {
    fs.writeFileSync(OUT_PATH, JSON.stringify(saved, null, 2) + "\n");
  }

  if (missing.length === 0) {
    report("✔ Found and saved all 7 databases.");
    report("### ✅ Setup is done");
    report(
      "The daily checks now run automatically every morning. To watch one run right now: " +
        "**Actions** tab → **Daily Compliance & Deadline Checks** → **Run workflow**.\n\n" +
        "Want email or text alerts too? Add these the same way you added the Notion key " +
        "(Settings → Secrets and variables → Actions): `SENDGRID_API_KEY`, `ALERT_EMAIL_TO`, " +
        "`ALERT_EMAIL_FROM` for email; `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, " +
        "`TWILIO_FROM_NUMBER`, `ALERT_SMS_TO` for texts. Without them, results just stay " +
        "in each run's log."
    );
  } else {
    report(`### ⚠️ Found ${7 - missing.length} of 7 databases - almost there`);
    report("Still missing:\n" + missing.map((t) => `- ${t}`).join("\n"));
    report(
      "Each database has to be connected to your integration one by one (Notion doesn't " +
        "pass it down from the Home page). In Notion, open each missing database, click its " +
        "**•••** menu → **Connect to** → your integration. Then run this workflow again - " +
        "what was already found is saved."
    );
    process.exitCode = 1;
  }
}

main()
  .catch((err) => {
    report(`### ❌ Something went wrong: ${err.message}`);
    report("Run the workflow again - if it keeps happening, the run log above has details.");
    process.exitCode = 1;
  })
  .finally(flushSummary);
