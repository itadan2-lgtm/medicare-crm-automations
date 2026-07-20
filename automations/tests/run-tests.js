/**
 * test/run-tests.js, dependency-free unit tests for the pure logic
 * functions (no Notion API calls, so these run instantly and offline).
 * Run with: npm test
 */

const assert = require("assert");

const { evaluateCompliance } = require("../soa-compliance");
const { computeTag } = require("../enrollment-deadlines");
const { computeRiskStatus } = require("../chargeback-tracker");
const { isInT65Window, iepStartDate } = require("../t65-tagger");

let pass = 0, fail = 0;
function test(name, fn) {
  try {
    fn();
    pass++;
    console.log(`  ok  - ${name}`);
  } catch (err) {
    fail++;
    console.log(`FAIL  - ${name}`);
    console.log(`        ${err.message}`);
  }
}

console.log("\nsoa-compliance.js, evaluateCompliance()");
test("missing SOA is flagged", () => {
  const r = evaluateCompliance({ dateTime: "2026-08-01T10:00:00Z", type: "Phone" }, null);
  assert.strictEqual(r.label, "Missing SOA");
});

test("SOA signed after the appointment is flagged", () => {
  const r = evaluateCompliance(
    { dateTime: "2026-08-01T10:00:00Z", type: "Phone" },
    { dateSigned: "2026-08-02", format: "Electronic", productsCovered: ["MA"] }
  );
  assert.strictEqual(r.label, "SOA after appointment");
});

test("in-person + verbal-only SOA is flagged", () => {
  const r = evaluateCompliance(
    { dateTime: "2026-08-10T10:00:00Z", type: "In-person" },
    { dateSigned: "2026-08-05", format: "Verbal", productsCovered: ["MA"] }
  );
  assert.strictEqual(r.label, "Needs written SOA");
});

test("SOA older than 12 months is flagged expired", () => {
  const r = evaluateCompliance(
    { dateTime: "2026-08-10T10:00:00Z", type: "Phone" },
    { dateSigned: "2025-06-01", format: "Electronic", productsCovered: ["MA"] }
  );
  assert.strictEqual(r.label, "SOA expired");
});

test("BEFORE Oct 1 2026: less than 48h gap is flagged (old rule)", () => {
  const r = evaluateCompliance(
    { dateTime: "2026-09-15T10:00:00Z", type: "Phone" },
    { dateSigned: "2026-09-14T18:00:00Z", format: "Electronic", productsCovered: ["MA"] } // 16h gap
  );
  assert.strictEqual(r.label, "Less than 48hrs since signed (pre-Oct 2026 rule)");
});

test("BEFORE Oct 1 2026: 48h+ gap is compliant (old rule satisfied)", () => {
  const r = evaluateCompliance(
    { dateTime: "2026-09-15T10:00:00Z", type: "Phone" },
    { dateSigned: "2026-09-12T09:00:00Z", format: "Electronic", productsCovered: ["MA"] } // 73h gap
  );
  assert.strictEqual(r.label, "Compliant");
});

test("ON/AFTER Oct 1 2026: same-day SOA is compliant (new rule)", () => {
  const r = evaluateCompliance(
    { dateTime: "2026-10-15T14:00:00Z", type: "Phone" },
    { dateSigned: "2026-10-15T09:00:00Z", format: "Electronic", productsCovered: ["MA"] } // 5h gap, but new rule applies
  );
  assert.strictEqual(r.label, "Compliant");
});

test("product not covered by SOA is flagged", () => {
  const r = evaluateCompliance(
    { dateTime: "2026-10-15T14:00:00Z", type: "Phone", productDiscussed: "PDP" },
    { dateSigned: "2026-10-01T09:00:00Z", format: "Electronic", productsCovered: ["MA"] }
  );
  assert.strictEqual(r.label, "Product not covered");
});

test("fully compliant case", () => {
  const r = evaluateCompliance(
    { dateTime: "2026-11-01T14:00:00Z", type: "In-person", productDiscussed: "MA" },
    { dateSigned: "2026-10-20T09:00:00Z", format: "Written", productsCovered: ["MA", "PDP"] }
  );
  assert.strictEqual(r.label, "Compliant");
});

console.log("\nenrollment-deadlines.js, computeTag()");
test("client turning 65 in ~2 months is tagged IEP", () => {
  const now = new Date("2026-08-01T00:00:00Z");
  const dob = "1961-10-01"; // turns 65 on 2026-10-01, IEP window = Jul 1 - Jan 1
  assert.strictEqual(computeTag(dob, "Lead", now), "IEP");
});

test("during AEP with no relevant DOB is tagged AEP", () => {
  const now = new Date("2026-11-01T00:00:00Z");
  assert.strictEqual(computeTag("1950-05-05", "Lead", now), "AEP");
});

test("during OEP, enrolled client is tagged OEP", () => {
  const now = new Date("2026-02-01T00:00:00Z");
  assert.strictEqual(computeTag("1950-05-05", "Client", now), "OEP");
});

test("during OEP, a non-enrolled lead is NOT tagged OEP", () => {
  const now = new Date("2026-02-01T00:00:00Z");
  assert.strictEqual(computeTag("1950-05-05", "Lead", now), "None");
});

test("outside every window is tagged None", () => {
  const now = new Date("2026-05-15T00:00:00Z");
  assert.strictEqual(computeTag("1950-05-05", "Client", now), "None");
});

test("IEP takes priority even during the AEP calendar window", () => {
  const now = new Date("2026-11-15T00:00:00Z"); // inside AEP (Oct15-Dec7)
  const dob = "1961-12-01"; // turns 65 2026-12-01 -> IEP window Sep1-Mar1, overlaps AEP
  assert.strictEqual(computeTag(dob, "Lead", now), "IEP");
});

console.log("\nchargeback-tracker.js, computeRiskStatus()");
test("well inside the window is 'In Chargeback Window'", () => {
  const now = new Date("2026-07-01T00:00:00Z");
  assert.strictEqual(computeRiskStatus("2026-06-01", 365, now), "In Chargeback Window");
});

test("inside the closing buffer is 'Approaching Window End'", () => {
  const now = new Date("2026-07-01T00:00:00Z");
  assert.strictEqual(computeRiskStatus("2025-07-10", 365, now), "Approaching Window End");
});

test("window fully passed is 'Safe'", () => {
  const now = new Date("2026-07-01T00:00:00Z");
  assert.strictEqual(computeRiskStatus("2024-01-01", 365, now), "Safe");
});

test("missing window days returns null (skip, don't guess)", () => {
  assert.strictEqual(computeRiskStatus("2026-01-01", null), null);
});

console.log("\nt65-tagger.js, isInT65Window() / iepStartDate()");
test("someone turning 65 in ~6 months is in the T65 window", () => {
  const now = new Date("2026-07-01T00:00:00Z");
  const dob = "1962-01-01"; // turns 65 on 2027-01-01, ~184 days out
  assert.strictEqual(isInT65Window(dob, now), true);
});

test("someone turning 65 in 30 days is NOT in the T65 window (too soon, already IEP)", () => {
  const now = new Date("2026-07-01T00:00:00Z");
  const dob = "1961-07-31";
  assert.strictEqual(isInT65Window(dob, now), false);
});

test("someone turning 65 in 300 days is NOT in the T65 window (too far out)", () => {
  const now = new Date("2026-07-01T00:00:00Z");
  const dob = "1961-04-26";
  assert.strictEqual(isInT65Window(dob, now), false);
});

test("no DOB never triggers", () => {
  assert.strictEqual(isInT65Window(null), false);
});

test("IEP start date is 3 months before the 65th birthday", () => {
  const d = iepStartDate("1961-10-15");
  assert.strictEqual(d.toISOString().slice(0, 10), "2026-07-15");
});

console.log(`\n${pass} passed, ${fail} failed\n`);
if (fail > 0) process.exitCode = 1;
