// Every constant the scripts depend on lives here. If a rule changes,
// this is the one file to touch.
//
// Data source IDs come from env vars since every buyer gets different
// ones after duplicating the template - see README, "Finding your IDs."

require("dotenv").config();

// IDs come from env vars (local .env or GitHub secrets), falling back
// to data-sources.json, which the browser-only "One-time setup"
// workflow commits. Env always wins so a secret can override the file.
let saved = {};
try {
  saved = require("./data-sources.json");
} catch {
  // no file yet - setup hasn't run, or env vars are being used instead
}
const id = (name) => process.env[name] || saved[name];

module.exports = {
  DATA_SOURCES: {
    CLIENTS: id("CLIENTS_DATA_SOURCE_ID"),
    LEADS: id("LEADS_DATA_SOURCE_ID"),
    SOA_RECORDS: id("SOA_RECORDS_DATA_SOURCE_ID"),
    APPOINTMENTS: id("APPOINTMENTS_DATA_SOURCE_ID"),
    POLICIES: id("POLICIES_DATA_SOURCE_ID"),
    CARRIER_REFERENCE: id("CARRIER_REFERENCE_DATA_SOURCE_ID"),
    TASKS: id("TASKS_DATA_SOURCE_ID"),
  },

  // SOA compliance
  SOA_VALIDITY_MONTHS: 12,
  // CMS's CY2027 rule drops the 48-hour SOA-to-appointment minimum, but per
  // their own May 2026 FAQ memo that applies to marketing/communications
  // starting Oct 1 2026, not the June 1 2026 "regulatory effective date."
  // Appointments before this cutoff still need the old 48-hour gap checked.
  // Re-verify against current CMS guidance - this stuff changes.
  NEW_SOA_RULE_CUTOFF: new Date("2026-10-01T00:00:00Z"),
  OLD_RULE_MIN_HOURS: 48,

  // Enrollment windows (months are 0-indexed)
  AEP: { startMonth: 9, startDay: 15, endMonth: 11, endDay: 7 }, // Oct 15 - Dec 7
  OEP: { startMonth: 0, startDay: 1, endMonth: 2, endDay: 31 }, // Jan 1 - Mar 31
  IEP_WINDOW_MONTHS: 3, // before/after the 65th birthday month

  // Chargeback risk
  CHARGEBACK_WARNING_BUFFER_DAYS: 30, // "Approaching Window End" threshold

  // T65 prospecting - window is intentionally a bit wide so a weekly or
  // even monthly run still catches everyone around the 6-month mark
  T65_LOOKAHEAD_DAYS_MIN: 150,
  T65_LOOKAHEAD_DAYS_MAX: 210,
};
