// Run this once after duplicating the template and connecting your
// integration. It walks the Home page, finds the 7 databases, and prints
// a ready-to-paste .env block instead of you hunting down data source IDs
// by hand.
//
// Usage:
//   NOTION_API_KEY=secret_xxx node scripts/find-data-source-ids.js <home-page-url-or-id>

const { Client } = require("@notionhq/client");
const { DATABASES: EXPECTED, extractPageId, findDataSources } = require("./shared");

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
  if (!pageId) {
    console.error(`Couldn't find a page id in "${input}". Paste the full Notion URL or just the id.`);
    process.exit(1);
  }

  const found = await findDataSources(notion, pageId);

  if (Object.keys(found).length === 0) {
    console.error("No databases found on that page. Did you connect your integration to it (••• menu > Connections > Add connections)? It also must be in the same workspace as your CRM.");
    process.exit(1);
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
