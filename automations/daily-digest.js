// Runs all 4 daily scripts and sends ONE summary email/text at the end,
// instead of each script sending its own separate "done" notification.
// Individual compliance/chargeback flags still alert immediately when they
// happen (see soa-compliance.js and chargeback-tracker.js) - this digest
// is the "here's what happened today" rollup on top of that, not a
// replacement for it.
//
// This is what GitHub Actions runs. If you want to run a single script on
// its own instead, use npm run soa-check / enrollment-deadlines / etc.

const soaCompliance = require("./soa-compliance");
const enrollmentDeadlines = require("./enrollment-deadlines");
const chargebackTracker = require("./chargeback-tracker");
const t65Tagger = require("./t65-tagger");
const { sendAlert } = require("./internal/notify");
const cfg = require("./internal/config");

async function run() {
  // If setup isn't finished, don't fail the scheduled run - just skip
  // cleanly. Otherwise a brand-new copy would email "workflow failed"
  // every morning until the buyer connects everything, which is alarming.
  const ds = cfg.DATA_SOURCES;
  const ready = process.env.NOTION_API_KEY && (ds.CLIENTS || ds.APPOINTMENTS || ds.POLICIES || ds.SOA_RECORDS);
  if (!ready) {
    console.log(
      "Setup isn't finished yet - no Notion key or database IDs found.\n" +
        "Run the 'One-time setup' workflow (Actions tab) to connect your CRM,\n" +
        "then the daily checks will start working. Skipping today - this is\n" +
        "not a failure, just nothing to check yet."
    );
    return; // exit 0 on purpose
  }

  const results = [];
  const scripts = [soaCompliance, enrollmentDeadlines, chargebackTracker, t65Tagger];

  for (const script of scripts) {
    try {
      const summary = await script.run();
      if (summary) results.push(summary);
    } catch (err) {
      results.push({ script: script.name || "unknown", error: err.message });
    }
  }

  const lines = results.map((r) => {
    if (r.error) return `${r.script}: failed (${r.error})`;
    return Object.entries(r)
      .filter(([k]) => k !== "script")
      .map(([k, v]) => `${v} ${k}`)
      .join(", ")
      .replace(/^/, `${r.script}: `);
  });

  const totalFlags = results.reduce((sum, r) => sum + (r.flagged || 0), 0);
  const hadFailure = results.some((r) => r.error);

  const subject = hadFailure
    ? "Daily check ran with errors"
    : totalFlags > 0
    ? `Daily check: ${totalFlags} item(s) need attention`
    : "Daily check: all clear";

  await sendAlert({ subject, message: lines.join(" | ") });
  console.log(`\nDaily digest:\n${lines.join("\n")}`);

  if (hadFailure) process.exitCode = 1;
}

if (require.main === module) {
  run().catch((err) => {
    console.error("daily-digest.js failed:", err);
    process.exitCode = 1;
  });
}

module.exports = { run };
