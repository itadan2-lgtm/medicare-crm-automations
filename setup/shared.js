// Shared bits for the setup tools - the one place the template's
// database names and Notion-link parsing live, so the wizard, the
// cloud setup, the doctor, and find-ids can't drift apart.

const DATABASES = {
  "Clients": "CLIENTS_DATA_SOURCE_ID",
  "Leads (Intake)": "LEADS_DATA_SOURCE_ID",
  "SOA Records": "SOA_RECORDS_DATA_SOURCE_ID",
  "Appointments": "APPOINTMENTS_DATA_SOURCE_ID",
  "Policies / Commissions": "POLICIES_DATA_SOURCE_ID",
  "Carrier Reference (Chargeback Windows)": "CARRIER_REFERENCE_DATA_SOURCE_ID",
  "Tasks / Follow-ups": "TASKS_DATA_SOURCE_ID",
};

// Pulls the 32-hex page id out of a pasted Notion link (or a bare id).
// Returns null when the input doesn't contain one.
function extractPageId(input) {
  const match = String(input).replace(/-/g, "").match(/([0-9a-f]{32})/i);
  if (!match) return null;
  const raw = match[1];
  return `${raw.slice(0, 8)}-${raw.slice(8, 12)}-${raw.slice(12, 16)}-${raw.slice(16, 20)}-${raw.slice(20)}`;
}

// Walks every block on the page - paging past the first 100, so a
// heavily customized Home page still finds everything - and returns
// { "<database title>": "<data source id>" } for each database on it.
async function findDataSources(notion, pageId) {
  const found = {};
  let cursor;
  do {
    const res = await notion.blocks.children.list({
      block_id: pageId,
      page_size: 100,
      start_cursor: cursor,
    });
    for (const block of res.results) {
      if (block.type !== "child_database") continue;
      const db = await notion.databases.retrieve({ database_id: block.id });
      const dataSourceId = db.data_sources?.[0]?.id;
      if (dataSourceId) found[block.child_database.title] = dataSourceId;
    }
    cursor = res.has_more ? res.next_cursor : undefined;
  } while (cursor);
  return found;
}

module.exports = { DATABASES, extractPageId, findDataSources };
