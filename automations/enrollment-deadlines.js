// Tags every client with whichever enrollment window applies to them
// right now: AEP, OEP, IEP, or None.
//
// Never auto-sets SEP - it's event-triggered, nothing in DOB/plan data
// signals it - and never clears one you set by hand either. That stays
// a manual flag, manual clear.
//
//   AEP   Oct 15 - Dec 7    everyone
//   OEP   Jan 1 - Mar 31    only clients already enrolled (Status = Client)
//   IEP   +/- 3 months of the 65th birthday month, once, around turning 65
//
// If CMS ever moves these dates, update lib/config.js.

const { queryAll, readProp, setProp, notion } = require("./internal/notion-client");
const { nthBirthday, addMonths, isWithin } = require("./internal/dates");
const cfg = require("./internal/config");

function windowDates(year, w) {
  return {
    start: new Date(Date.UTC(year, w.startMonth, w.startDay)),
    end: new Date(Date.UTC(year, w.endMonth, w.endDay)),
  };
}

// given a DOB, status, and "now", what should the tag be?
function computeTag(dob, status, now = new Date()) {
  if (dob) {
    const bday65 = nthBirthday(dob, 65);
    const iepStart = addMonths(bday65, -cfg.IEP_WINDOW_MONTHS);
    const iepEnd = addMonths(bday65, cfg.IEP_WINDOW_MONTHS);
    if (isWithin(now, iepStart, iepEnd)) return "IEP";
  }

  const year = now.getUTCFullYear();
  const aep = windowDates(year, cfg.AEP);
  if (isWithin(now, aep.start, aep.end)) return "AEP";

  if (status === "Client") {
    const oep = windowDates(year, cfg.OEP);
    if (isWithin(now, oep.start, oep.end)) return "OEP";
  }

  return "None";
}

async function run() {
  if (!cfg.DATA_SOURCES.CLIENTS) {
    console.error("CLIENTS_DATA_SOURCE_ID is not set, see .env.example");
    process.exitCode = 1;
    return;
  }

  const clients = await queryAll(cfg.DATA_SOURCES.CLIENTS);
  console.log(`Evaluating enrollment windows for ${clients.length} client(s)...`);

  let updated = 0;
  const now = new Date();

  for (const page of clients) {
    const currentTag = readProp(page, "Election Period Tag");
    if (currentTag === "SEP") continue; // manually set, never auto-overwrite

    const dob = readProp(page, "DOB")?.start ?? null;
    const status = readProp(page, "Status");
    const newTag = computeTag(dob, status, now);

    if (newTag !== currentTag) {
      await notion.pages.update({
        page_id: page.id,
        properties: { "Election Period Tag": setProp.select(newTag) },
      });
      updated += 1;
    }
  }

  console.log(`Done. ${updated} client(s) re-tagged.`);
  return { script: "Enrollment deadlines", checked: clients.length, updated };
}

if (require.main === module) {
  run().catch((err) => {
    console.error("enrollment-deadlines.js failed:", err);
    process.exitCode = 1;
  });
}

module.exports = { computeTag, run };
