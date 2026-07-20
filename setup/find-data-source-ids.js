// Run this once after duplicating the template and connecting your
// integration. It walks the Home page, finds the 7 databases, and prints
// a ready-to-paste .env block instead of you hunting down data source IDs
// by hand.
//
// Usage:
//   NOTION_API_KEY=secret_xxx node scripts/find-data-source-ids.js <home-page-url-or-id>

const { Client } = require("@notionhq/client");

const EXPECTED = {
  "Clients": "CLIENTS_DATA_SOURCE_ID",
  "Leads (Intake)": "LEADS_DATA_SOURCE_ID",
  "SOA Records": "SOA_RECORDS_DATA_SOURCE_ID",
  "Appointments": "APPOINTMENTS_DATA_SOURCE_ID",
  "Policies / Commissions": "POLICIES_DATA_SOURCE_ID",
  "Carrier Reference (Chargeback Windows)": "CARRIER_REFERENCE_DATA_SOURCE_ID",
  "Tasks / Follow-ups": "TASKS_DATA_SOURCE_ID",
};

function extractPageId(input) {
  const match = input.replace(/-/g, "").match(/([0-9a-f]{32})/i);
  if (!match) throw new Error(`Couldn't find a page id in "${input}". Paste the full Notion URL or just the id.`);
  const raw = match[1];
  return `${raw.slice(0, 8)}-${raw.slice(8, 12)}-${raw.slice(12, 16)}-${raw.slice(16, 20)}-${raw.slice(20)}`;
}

async function main() {
  const input = process.argv[2];
  if (!input) {
    console.error("Usage: node scripts/find-data-source-ids.js <home-page-url-or-id>");
    process.exit(1);
  }
  if (!process.env.NOTION_API_KEY) {
    console.error("Set NOTION_API_KEY first (see README step 2).");
    process.exit(1);
  }

  const notion = new Client({ auth: process.env.NOTION_API_KEY });
  const pageId = extractPageId(input);

  const children = await notion.blocks.children.list({ block_id: pageId, page_size: 100 });
  const databaseBlocks = children.results.filter((b) => b.type === "child_database");

  if (databaseBlocks.length === 0) {
    console.error("No databases found on that page. Did you connect your integration to it (••• menu > Connect to)?");
    process.exit(1);
  }

  const found = {};
  for (const block of databaseBlocks) {
    const title = block.child_database.title;
    const db = await notion.databases.retrieve({ database_id: block.id });
    const dataSourceId = db.data_sources?.[0]?.id;
    found[title] = dataSourceId;
  }

  console.log("\nPaste this into your .env (or add as GitHub/Vercel secrets):\n");
  for (const [title, envVar] of Object.entries(EXPECTED)) {
    const id = found[title];
    if (id) {
      console.log(`${envVar}=${id}`);
    } else {
      console.log(`# ${envVar}= -- couldn't find a database titled "${title}", check it's connected to your integration`);
    }
  }
  console.log("");
}

main().catch((err) => {
  console.error("find-data-source-ids failed:", err.message);
  process.exit(1);
});
