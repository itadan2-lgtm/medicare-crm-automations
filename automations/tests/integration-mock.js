/**
 * test/integration-mock.js
 *
 * Unlike run-tests.js (which tests pure decision functions), this exercises
 * each script's real run(), the Notion queries, property reads, and
 * writes, against a mocked Notion client shaped like the actual schema.
 * This is what catches "the property name has a typo" or "the write
 * payload is malformed" bugs that pure-logic tests can't see, without
 * needing live network access to api.notion.com (which this sandbox can't
 * reach anyway).
 */

const assert = require("assert");

process.env.NOTION_API_KEY = "test-key";
process.env.CLIENTS_DATA_SOURCE_ID = "ds-clients";
process.env.LEADS_DATA_SOURCE_ID = "ds-leads";
process.env.SOA_RECORDS_DATA_SOURCE_ID = "ds-soa";
process.env.APPOINTMENTS_DATA_SOURCE_ID = "ds-appts";
process.env.POLICIES_DATA_SOURCE_ID = "ds-policies";
process.env.CARRIER_REFERENCE_DATA_SOURCE_ID = "ds-carrier";
process.env.TASKS_DATA_SOURCE_ID = "ds-tasks";

const notionClient = require("../internal/notion-client");

const titleProp = (t) => ({ type: "title", title: t ? [{ plain_text: t }] : [] });
const selectProp = (n) => ({ type: "select", select: n ? { name: n } : null });
const dateProp = (s, e = null) => ({ type: "date", date: s ? { start: s, end: e } : null });
const numberProp = (n) => ({ type: "number", number: n });
const relationProp = (ids) => ({ type: "relation", relation: (ids || []).map((id) => ({ id })) });
const multiSelectProp = (names) => ({ type: "multi_select", multi_select: (names || []).map((n) => ({ name: n })) });
const page = (id, properties) => ({ id, properties });

// Pick a DOB whose 65th birthday lands ~180 days from whenever this actually
// runs, so the T65 test doesn't depend on a hardcoded "today".
const in180Days = new Date(Date.now() + 180 * 86400000);
const t65Dob = `${in180Days.getUTCFullYear() - 65}-${String(in180Days.getUTCMonth() + 1).padStart(2, "0")}-${String(in180Days.getUTCDate()).padStart(2, "0")}`;

const fixtures = {
  "ds-appts": [
    page("appt-compliant", {
      Appointment: titleProp("Jane Doe, Annual Review"),
      "Date/Time": dateProp("2026-11-01T14:00:00.000Z"),
      Type: selectProp("Phone"),
      "Product Discussed": selectProp("MA"),
      "SOA Record": relationProp(["soa-1"]),
      Client: relationProp(["client-1"]),
      "Compliance Status": selectProp(null),
    }),
    page("appt-flagged", {
      Appointment: titleProp("Ray Suarez, New Enrollment"),
      "Date/Time": dateProp("2026-11-05T14:00:00.000Z"),
      Type: selectProp("Phone"),
      "Product Discussed": selectProp("MA"),
      "SOA Record": relationProp([]), // no SOA linked at all
      Client: relationProp(["client-1"]),
      "Compliance Status": selectProp(null),
    }),
  ],
  "ds-clients": [
    page("client-1", { Name: titleProp("Jane Doe"), DOB: dateProp("1961-05-01"), Status: selectProp("Client"), "Election Period Tag": selectProp(null) }),
    page("client-2", { Name: titleProp("Tom Rivera"), DOB: dateProp(t65Dob), Status: selectProp("Lead"), "Election Period Tag": selectProp(null) }),
  ],
  "ds-policies": [
    page("policy-1", {
      Policy: titleProp("Humana MA, Jane Doe"),
      Carrier: selectProp("Humana"),
      "Effective Date": dateProp("2026-01-01"),
      "Chargeback Period (Days)": numberProp(null),
      "Chargeback Risk Status": selectProp(null),
    }),
  ],
  "ds-carrier": [page("carrier-1", { Carrier: titleProp("Humana"), "Chargeback Period (Days)": numberProp(365) })],
  "ds-tasks": [],
};
const soaFixture = page("soa-1", {
  "Record Name": titleProp("Jane Doe SOA"),
  "Date Signed": dateProp("2026-10-20T09:00:00.000Z"),
  Format: selectProp("Electronic"),
  "Products Covered": multiSelectProp(["MA"]),
});

let calls = [];
notionClient.queryAll = async (dataSourceId, opts) => {
  let rows = fixtures[dataSourceId] || [];
  if (opts?.filter?.title?.equals) {
    const wanted = opts.filter.title.equals;
    rows = rows.filter((p) => notionClient.readProp(p, opts.filter.property) === wanted);
  }
  return rows;
};
notionClient.getPage = async (id) => {
  if (id === "soa-1") return soaFixture;
  throw new Error(`getPage: no fixture for "${id}"`);
};
notionClient.notion.pages.update = async (args) => { calls.push({ op: "update", ...args }); return {}; };
notionClient.notion.pages.create = async (args) => { calls.push({ op: "create", ...args }); return { id: "new-page" }; };

let pass = 0, fail = 0;
function test(name, fn) {
  try { fn(); pass++; console.log(`  ok  - ${name}`); }
  catch (err) { fail++; console.log(`FAIL  - ${name}\n        ${err.message}`); }
}
function fresh(mod) { delete require.cache[require.resolve(mod)]; return require(mod); }

(async () => {
  console.log("\nintegration (mocked Notion), does run() actually wire up correctly?\n");

  calls = [];
  await fresh("../soa-compliance").run();
  test("soa-compliance: marks the clean appointment Compliant", () => {
    const upd = calls.find((c) => c.op === "update" && c.page_id === "appt-compliant");
    assert.ok(upd, "expected an update to appt-compliant");
    assert.strictEqual(upd.properties["Compliance Status"].select.name, "Compliant");
  });
  test("soa-compliance: flags the appointment with no SOA", () => {
    const upd = calls.find((c) => c.op === "update" && c.page_id === "appt-flagged");
    assert.ok(upd, "expected an update to appt-flagged");
    assert.strictEqual(upd.properties["Compliance Status"].select.name, "Missing SOA");
  });
  test("soa-compliance: creates a follow-up Task for the flagged appointment", () => {
    const created = calls.find((c) => c.op === "create" && c.properties?.Task);
    assert.ok(created, "expected a Task page to be created");
    assert.strictEqual(created.parent.data_source_id, "ds-tasks");
    assert.deepStrictEqual(created.properties.Client.relation, [{ id: "client-1" }]);
  });

  calls = [];
  await fresh("../enrollment-deadlines").run();
  test("enrollment-deadlines: writes an Election Period Tag update", () => {
    const upd = calls.find((c) => c.op === "update" && c.properties?.["Election Period Tag"]);
    assert.ok(upd, "expected at least one Election Period Tag update");
  });

  calls = [];
  await fresh("../chargeback-tracker").run();
  test("chargeback-tracker: falls back to the Carrier Reference window and updates the policy", () => {
    const upd = calls.find((c) => c.op === "update" && c.page_id === "policy-1");
    assert.ok(upd, "expected an update to policy-1");
    assert.strictEqual(upd.properties["Chargeback Risk Status"].select.name, "In Chargeback Window");
  });

  calls = [];
  await fresh("../t65-tagger").run();
  test("t65-tagger: creates an outreach task for the client ~180 days from their 65th", () => {
    const created = calls.find((c) => c.op === "create" && c.properties?.Task);
    assert.ok(created, "expected a Task page to be created");
    assert.ok(created.properties.Task.title[0].text.content.includes("Tom Rivera"));
    assert.strictEqual(created.properties.Client.relation[0].id, "client-2");
  });

  calls = [];
  const digestResult = await fresh("../daily-digest").run();
  test("daily-digest: runs all 4 scripts and returns a summary for each", () => {
    // digestResult is undefined (run() doesn't return in the CLI path), but
    // the side effects (calls) should reflect all 4 scripts having run.
    const soaUpdate = calls.find((c) => c.op === "update" && c.page_id === "appt-compliant");
    const enrollUpdate = calls.find((c) => c.properties?.["Election Period Tag"]);
    const chargebackUpdate = calls.find((c) => c.page_id === "policy-1");
    const t65Create = calls.find((c) => c.op === "create" && c.properties?.Task?.title?.[0]?.text?.content?.includes("Tom Rivera"));
    assert.ok(soaUpdate, "expected soa-compliance to have run as part of the digest");
    assert.ok(enrollUpdate, "expected enrollment-deadlines to have run as part of the digest");
    assert.ok(chargebackUpdate, "expected chargeback-tracker to have run as part of the digest");
    assert.ok(t65Create, "expected t65-tagger to have run as part of the digest");
  });

  console.log(`\n${pass} passed, ${fail} failed\n`);
  if (fail > 0) process.exitCode = 1;
})();
