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

const { DATABASES, extractPageId, findDataSources, searchDataSources } = require("./shared");

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

  let found;
  let duplicates = [];

  if (link) {
    // A link was pasted - walk that page directly.
    const pageId = extractPageId(link);
    if (!pageId) {
      report("### ❌ That link didn't look like a Notion page");
      report(
        "In Notion, open your CRM's **Home** page, click **Share** (top right) → **Copy link**, " +
          "and paste the whole link into the box when you run this workflow. Or leave the box " +
          "empty - the setup can usually find your databases on its own."
      );
      process.exitCode = 1;
      return;
    }
    try {
      found = await findDataSources(notion, pageId);
    } catch (err) {
      report("### ❌ Notion wouldn't show me that page");
      report(
        "Almost always this means the page isn't connected to your integration yet. " +
          "On the Home page in Notion, click the **•••** menu (top right) → **Connect to** → " +
          "pick your integration. Then run this workflow again."
      );
      process.exitCode = 1;
      return;
    }
  } else {
    // No link - ask Notion what the integration can see and match by name.
    ({ found, duplicates } = await searchDataSources(notion));
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
  } else if (missing.length === 7 && !link) {
    report("### ⚠️ Couldn't see any of your databases yet");
    report(
      "Two easy explanations:\n" +
        "1. **The integration isn't connected yet.** In Notion, open your CRM's **Home** page, " +
        "click the **•••** menu (top right) → **Connect to** → pick your integration.\n" +
        "2. **You connected it seconds ago.** Notion can take a minute to catch up - just run " +
        "this workflow again shortly.\n\n" +
        "Still stuck? Run the workflow again and paste the link to your Home page " +
        "(Share → Copy link in Notion) into the box - that looks the page up directly."
    );
    process.exitCode = 1;
  } else {
    report(`### ⚠️ Found ${7 - missing.length} of 7 databases - almost there`);
    report("Still missing:\n" + missing.map((t) => `- ${t}`).join("\n"));
    if (duplicates.length > 0) {
      report(
        "Some of these exist **more than once** in what's shared with the integration " +
          `(${duplicates.map((t) => `“${t}”`).join(", ")}) - maybe a second copy of the ` +
          "template. Run this workflow again and paste the link to the Home page of the copy " +
          "you actually use (Share → Copy link) - that picks the right ones."
      );
    } else {
      report(
        "Connecting the Home page usually covers everything inside it, but these didn't pick " +
          "it up. In Notion, open each missing database, click its **•••** menu → " +
          "**Connect to** → your integration. Then run this workflow again - " +
          "what was already found is saved."
      );
    }
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
