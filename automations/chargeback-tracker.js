// Works out how far into its chargeback window each policy is and flags
// risk status accordingly. Windows aren't hardcoded - they're read from
// the Carrier Reference table so you can edit them as contracts change,
// with a per-policy override if that policy's own "Chargeback Period
// (Days)" field is filled in.
//
//   In Chargeback Window     more than the buffer days left
//   Approaching Window End   inside the buffer, still exposed
//   Safe                     window's passed, commission is vested

const { queryAll, readProp, setProp, notion } = require("./internal/notion-client");
const { sendAlert } = require("./internal/notify");
const { daysBetween } = require("./internal/dates");
const cfg = require("./internal/config");

function computeRiskStatus(effectiveDateIso, windowDays, now = new Date()) {
  if (windowDays == null || !effectiveDateIso) return null; // can't assess without both
  const daysSince = daysBetween(effectiveDateIso, now);
  const daysRemaining = windowDays - daysSince;
  if (daysRemaining <= 0) return "Safe";
  if (daysRemaining <= cfg.CHARGEBACK_WARNING_BUFFER_DAYS) return "Approaching Window End";
  return "In Chargeback Window";
}

async function loadCarrierWindows() {
  if (!cfg.DATA_SOURCES.CARRIER_REFERENCE) return {};
  const rows = await queryAll(cfg.DATA_SOURCES.CARRIER_REFERENCE);
  const map = {};
  for (const row of rows) {
    const carrier = readProp(row, "Carrier");
    const days = readProp(row, "Chargeback Period (Days)");
    if (carrier && days != null) map[carrier.trim().toLowerCase()] = days;
  }
  return map;
}

async function run() {
  if (!cfg.DATA_SOURCES.POLICIES) {
    console.error("POLICIES_DATA_SOURCE_ID is not set, see .env.example");
    process.exitCode = 1;
    return;
  }

  const carrierWindows = await loadCarrierWindows();
  const policies = await queryAll(cfg.DATA_SOURCES.POLICIES);
  console.log(`Evaluating chargeback risk for ${policies.length} polic${policies.length === 1 ? "y" : "ies"}...`);

  let updated = 0;
  let skipped = 0;

  for (const page of policies) {
    const effectiveDate = readProp(page, "Effective Date")?.start ?? null;
    const perPolicyDays = readProp(page, "Chargeback Period (Days)");
    const carrier = readProp(page, "Carrier");
    const windowDays = perPolicyDays ?? (carrier ? carrierWindows[carrier.trim().toLowerCase()] : undefined);

    const newStatus = computeRiskStatus(effectiveDate, windowDays);
    if (!newStatus) {
      skipped += 1;
      continue; // no effective date and/or no known window for this carrier
    }

    const previousStatus = readProp(page, "Chargeback Risk Status");
    if (newStatus !== previousStatus) {
      await notion.pages.update({
        page_id: page.id,
        properties: { "Chargeback Risk Status": setProp.select(newStatus) },
      });
      updated += 1;

      if (newStatus === "Approaching Window End") {
        await sendAlert({
          subject: `Chargeback window closing soon`,
          message: `${readProp(page, "Policy") || "A policy"} is entering its final ${cfg.CHARGEBACK_WARNING_BUFFER_DAYS} days of chargeback exposure.`,
        });
      }
    }
  }

  console.log(`Done. ${updated} updated, ${skipped} skipped (missing effective date or carrier window, fill in Carrier Reference).`);
  return { script: "Chargeback tracker", checked: policies.length, updated, skipped };
}

if (require.main === module) {
  run().catch((err) => {
    console.error("chargeback-tracker.js failed:", err);
    process.exitCode = 1;
  });
}

module.exports = { computeRiskStatus, run };
