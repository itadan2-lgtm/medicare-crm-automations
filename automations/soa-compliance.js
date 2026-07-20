// Checks each upcoming appointment's linked SOA against CMS rules and
// writes the result to Compliance Status.
//
// The part that trips people up: before Oct 1 2026, SOA has to be signed
// at least 48h before the appointment (old rule, a couple of documented
// exceptions we don't model here - see README). Oct 1 2026 on, same-day
// SOA is fine. Source is CMS's May 2026 FAQ memo - reconfirm before
// trusting this, CMS revises guidance more than people expect.
//
// Workflow aid, not legal advice.

const { queryAll, getPage, readProp, setProp, notion } = require("./internal/notion-client");
const { sendAlert } = require("./internal/notify");
const { hoursBetween, monthsBetween, daysBetween } = require("./internal/dates");
const cfg = require("./internal/config");

// exported on its own so tests can run this without touching Notion
function evaluateCompliance(appt, soa, now = new Date()) {
  if (!soa) {
    return { label: "Missing SOA", reason: "No SOA record is linked to this appointment." };
  }
  if (!soa.dateSigned) {
    return { label: "Missing SOA", reason: "Linked SOA record has no Date Signed." };
  }
  if (!appt.dateTime) {
    return { label: "Missing SOA", reason: "Appointment has no Date/Time set, cannot evaluate." };
  }
  if (new Date(soa.dateSigned) > new Date(appt.dateTime)) {
    return { label: "SOA after appointment", reason: "SOA was signed after the appointment took place." };
  }
  if (appt.type === "In-person" && soa.format === "Verbal") {
    return { label: "Needs written SOA", reason: "In-person appointments require a written (or electronic) SOA, verbal is not sufficient." };
  }
  if (monthsBetween(soa.dateSigned, appt.dateTime) > cfg.SOA_VALIDITY_MONTHS) {
    return { label: "SOA expired", reason: `SOA is older than ${cfg.SOA_VALIDITY_MONTHS} months relative to the appointment date.` };
  }

  // 48-hour check only applies pre-transition
  if (new Date(appt.dateTime) < cfg.NEW_SOA_RULE_CUTOFF) {
    const gapHours = hoursBetween(soa.dateSigned, appt.dateTime);
    if (gapHours < cfg.OLD_RULE_MIN_HOURS) {
      return {
        label: "Less than 48hrs since signed (pre-Oct 2026 rule)",
        reason: `This appointment is before Oct 1, 2026, so the old 48-hour rule still applies. Only ${gapHours.toFixed(1)}h between SOA signature and appointment.`,
      };
    }
  }

  if (appt.productDiscussed && soa.productsCovered && !soa.productsCovered.includes(appt.productDiscussed)) {
    return { label: "Product not covered", reason: `SOA does not list "${appt.productDiscussed}" among its covered products.` };
  }

  return { label: "Compliant", reason: null };
}

async function resolveSOA(soaRelationIds) {
  if (!soaRelationIds || soaRelationIds.length === 0) return null;
  const soaPage = await getPage(soaRelationIds[0]);
  return {
    dateSigned: readProp(soaPage, "Date Signed")?.start ?? null,
    format: readProp(soaPage, "Format"),
    productsCovered: readProp(soaPage, "Products Covered") || [],
  };
}

async function ensureFollowUpTask(clientRelationIds, appointmentTitle, reason) {
  if (!cfg.DATA_SOURCES.TASKS || !clientRelationIds?.length) return;
  const taskTitle = `Fix SOA issue, ${appointmentTitle}`;

  // Avoid creating duplicate tasks if one is already open for this appointment.
  const existing = await queryAll(cfg.DATA_SOURCES.TASKS, {
    filter: { property: "Task", title: { equals: taskTitle } },
  });
  const stillOpen = existing.find((t) => readProp(t, "Status") !== "Done");
  if (stillOpen) return;

  await notion.pages.create({
    parent: { data_source_id: cfg.DATA_SOURCES.TASKS },
    properties: {
      Task: setProp.title(taskTitle),
      Client: setProp.relation(clientRelationIds),
      "Due Date": setProp.date(new Date().toISOString().slice(0, 10)),
      Status: setProp.status("Not Started"),
      Priority: setProp.select("High"),
    },
  });
}

async function run() {
  if (!cfg.DATA_SOURCES.APPOINTMENTS) {
    console.error("APPOINTMENTS_DATA_SOURCE_ID is not set, see .env.example");
    process.exitCode = 1;
    return;
  }

  const lookbackDays = 3; // also re-check appointments logged a few days ago
  const since = new Date(Date.now() - lookbackDays * 24 * 3600 * 1000).toISOString();

  const appointments = await queryAll(cfg.DATA_SOURCES.APPOINTMENTS, {
    filter: { property: "Date/Time", date: { on_or_after: since } },
    sorts: [{ property: "Date/Time", direction: "ascending" }],
  });

  console.log(`Checking ${appointments.length} appointment(s)...`);
  let flagged = 0;

  for (const page of appointments) {
    const appt = {
      title: readProp(page, "Appointment") || "(untitled appointment)",
      dateTime: readProp(page, "Date/Time")?.start ?? null,
      type: readProp(page, "Type"),
      productDiscussed: readProp(page, "Product Discussed"),
    };
    const soaIds = readProp(page, "SOA Record");
    const clientIds = readProp(page, "Client");
    const soa = await resolveSOA(soaIds);

    const previousStatus = readProp(page, "Compliance Status");
    const result = evaluateCompliance(appt, soa);

    if (result.label !== previousStatus) {
      await notion.pages.update({
        page_id: page.id,
        properties: { "Compliance Status": setProp.select(result.label) },
      });
    }

    if (result.label !== "Compliant") {
      flagged += 1;
      await ensureFollowUpTask(clientIds, appt.title, result.reason);
      // Only alert on a genuinely new/changed flag, not every run.
      if (result.label !== previousStatus) {
        await sendAlert({
          subject: `SOA compliance flag: ${appt.title}`,
          message: `${result.label}, ${result.reason}`,
        });
      }
    }
  }

  console.log(`Done. ${flagged} appointment(s) flagged out of ${appointments.length}.`);
  return { script: "SOA compliance", checked: appointments.length, flagged };
}

if (require.main === module) {
  run().catch((err) => {
    console.error("soa-compliance.js failed:", err);
    process.exitCode = 1;
  });
}

module.exports = { evaluateCompliance, run };
