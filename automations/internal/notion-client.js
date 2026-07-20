// Wrapper around @notionhq/client v5.
//
// Notion split databases into "data sources" in API version 2025-09-03.
// notion.databases.query() doesn't exist anymore, everything queries
// through notion.dataSources.query(). Every ID in .env is a data source
// id, not a database id - see README if that distinction is new to you.

const { Client } = require("@notionhq/client");
require("dotenv").config();

const notion = new Client({ auth: process.env.NOTION_API_KEY });

// Queries a full data source, paging through results automatically.
async function queryAll(dataSourceId, { filter, sorts } = {}) {
  const results = [];
  let cursor = undefined;
  do {
    const res = await notion.dataSources.query({
      data_source_id: dataSourceId,
      filter,
      sorts,
      start_cursor: cursor,
      page_size: 100,
    });
    results.push(...res.results);
    cursor = res.has_more ? res.next_cursor : undefined;
  } while (cursor);
  return results;
}

// Fetches one page by id - used to resolve relation properties.
async function getPage(pageId) {
  return notion.pages.retrieve({ page_id: pageId });
}

// Pulls a plain JS value out of a Notion property, whatever its type.
// Empty properties come back as null instead of throwing.
function readProp(page, name) {
  const prop = page.properties?.[name];
  if (!prop) return null;
  switch (prop.type) {
    case "title":
      return prop.title.map((t) => t.plain_text).join("") || null;
    case "rich_text":
      return prop.rich_text.map((t) => t.plain_text).join("") || null;
    case "select":
      return prop.select?.name ?? null;
    case "multi_select":
      return prop.multi_select.map((o) => o.name);
    case "status":
      return prop.status?.name ?? null;
    case "date":
      return prop.date ? { start: prop.date.start, end: prop.date.end } : null;
    case "number":
      return prop.number;
    case "email":
      return prop.email;
    case "phone_number":
      return prop.phone_number;
    case "checkbox":
      return prop.checkbox;
    case "relation":
      return prop.relation.map((r) => r.id);
    default:
      return null;
  }
}

// Builds the property payload shapes pages.update() expects.
const setProp = {
  select: (name) => ({ select: name ? { name } : null }),
  multiSelect: (names) => ({ multi_select: (names || []).map((n) => ({ name: n })) }),
  status: (name) => ({ status: name ? { name } : null }),
  date: (isoStart, isoEnd = null) => ({ date: isoStart ? { start: isoStart, end: isoEnd } : null }),
  relation: (pageIds) => ({ relation: (pageIds || []).map((id) => ({ id })) }),
  title: (text) => ({ title: [{ type: "text", text: { content: String(text).slice(0, 2000) } }] }),
  richText: (text) => ({ rich_text: [{ type: "text", text: { content: String(text).slice(0, 2000) } }] }),
  number: (n) => ({ number: n }),
};

module.exports = { notion, queryAll, getPage, readProp, setProp };
