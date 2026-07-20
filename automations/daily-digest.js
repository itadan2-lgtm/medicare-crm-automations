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

async function run() {
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
