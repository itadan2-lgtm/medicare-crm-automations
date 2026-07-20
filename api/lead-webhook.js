// This one's not run by GitHub Actions like the other 4 scripts. A
// webhook needs to be listening 24/7 to catch a submission the moment
// it happens, and a scheduled job can't do that, so this runs as a
// Vercel serverless function instead (free tier covers it fine). See
// README, "Deploying the lead webhook."
//
// Point your form tool (Tally, Typeform, a plain <form>) at:
//   https://<your-vercel-project>.vercel.app/api/lead-webhook
// with header:  x-webhook-secret: <WEBHOOK_SECRET>

const { Client } = require("@notionhq/client");

const notion = new Client({ auth: process.env.NOTION_API_KEY });

// The Leads ID comes from the env var if set, otherwise from the
// data-sources.json that the "One-time setup" workflow commits - which
// deploys along with this function, so most people only need to set
// NOTION_API_KEY and WEBHOOK_SECRET in Vercel.
let LEADS_ID = process.env.LEADS_DATA_SOURCE_ID;
if (!LEADS_ID) {
  try {
    LEADS_ID = require("../automations/internal/data-sources.json").LEADS_DATA_SOURCE_ID;
  } catch {
    // no saved file - the error response below explains what to do
  }
}

function pick(body, keys) {
  for (const k of keys) {
    if (body[k] !== undefined && body[k] !== null && body[k] !== "") return body[k];
  }
  return null;
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Use POST" });
    return;
  }

  if (process.env.WEBHOOK_SECRET) {
    const provided = req.headers["x-webhook-secret"];
    if (provided !== process.env.WEBHOOK_SECRET) {
      res.status(401).json({ error: "Invalid or missing x-webhook-secret header" });
      return;
    }
  }

  const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};

  // Accepts a few common field-name variants so most form tools work
  // without custom mapping (Tally/Typeform-style payloads, or a plain form).
  const name = pick(body, ["name", "Name", "full_name", "fullName"]);
  const email = pick(body, ["email", "Email"]);
  const phone = pick(body, ["phone", "Phone", "phone_number"]);
  const source = pick(body, ["source", "Source"]) || "Web/Online Lead";

  if (!name) {
    res.status(400).json({ error: "Missing required field: name" });
    return;
  }

  if (!LEADS_ID) {
    res.status(500).json({ error: "Server misconfigured: run the One-time setup workflow or set LEADS_DATA_SOURCE_ID" });
    return;
  }

  try {
    const properties = {
      Name: { title: [{ type: "text", text: { content: String(name).slice(0, 2000) } }] },
      "Date Added": { date: { start: new Date().toISOString().slice(0, 10) } },
      Status: { select: { name: "New" } },
      Source: { select: { name: source } },
    };
    if (email) properties.Email = { email };
    if (phone) properties.Phone = { phone_number: String(phone) };

    const page = await notion.pages.create({
      parent: { data_source_id: LEADS_ID },
      properties,
    });

    res.status(200).json({ ok: true, leadId: page.id });
  } catch (err) {
    console.error("lead-webhook failed:", err);
    res.status(502).json({ error: "Failed to create lead in Notion", detail: err.message });
  }
};
