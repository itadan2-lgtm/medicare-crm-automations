// Scans Clients for anyone turning 65 in roughly the next 5-7 months and
// creates a "T65 outreach" task due at the start of their IEP window
// (3 months before their 65th birthday), so they get contacted before
// someone else does.
//
// Only sees people who already have a Clients row with a DOB filled in -
// existing clients, referrals, family members you've logged. Not a
// purchased T65 list. If you buy one from a data provider, run it
// through the lead webhook first, convert those to Clients, and this
// picks them up from there.

const { queryAll, readProp, setProp, notion } = require("./internal/notion-client");
const { nthBirthday, addMonths, daysBetween } = require("./internal/dates");
const cfg = require("./internal/config");

/** Pure function: should this DOB trigger a T65 task today? */
function isInT65Window(dobIso, now = new Date()) {
  if (!dobIso) return false;
  const bday65 = nthBirthday(dobIso, 65);
  const daysUntil = daysBetween(now, bday65);
  return daysUntil >= cfg.T65_LOOKAHEAD_DAYS_MIN && daysUntil <= cfg.T65_LOOKAHEAD_DAYS_MAX;
}

function iepStartDate(dobIso) {
  const bday65 = nthBirthday(dobIso, 65);
  return addMonths(bday65, -3);
}

async function run() {
  if (!cfg.DATA_SOURCES.CLIENTS || !cfg.DATA_SOURCES.TASKS) {
    console.error("CLIENTS_DATA_SOURCE_ID and TASKS_DATA_SOURCE_ID must be set, see .env.example");
    process.exitCode = 1;
    return;
  }

  const clients = await queryAll(cfg.DATA_SOURCES.CLIENTS);
  const now = new Date();
  let created = 0;

  for (const page of clients) {
    const dob = readProp(page, "DOB")?.start ?? null;
    if (!isInT65Window(dob, now)) continue;

    const name = readProp(page, "Name") || "(unnamed client)";
    const taskTitle = `T65 outreach: ${name}`;

    const existing = await queryAll(cfg.DATA_SOURCES.TASKS, {
      filter: { property: "Task", title: { equals: taskTitle } },
    });
    if (existing.length > 0) continue; // already created, don't duplicate

    await notion.pages.create({
      parent: { data_source_id: cfg.DATA_SOURCES.TASKS },
      properties: {
        Task: setProp.title(taskTitle),
        Client: setProp.relation([page.id]),
        "Due Date": setProp.date(iepStartDate(dob).toISOString().slice(0, 10)),
        Status: setProp.select("Not Started"),
        Priority: setProp.select("Medium"),
      },
    });
    created += 1;
  }

  console.log(`Done. ${created} T65 outreach task(s) created.`);
  return { script: "T65 tagger", checked: clients.length, created };
}

if (require.main === module) {
  run().catch((err) => {
    console.error("t65-tagger.js failed:", err);
    process.exitCode = 1;
  });
}

module.exports = { isInT65Window, iepStartDate, run };
