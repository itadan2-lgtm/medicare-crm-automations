// Which systeme.io tools Claude is allowed to touch on a given run.
//
// This is the real safety boundary, not a suggestion in the prompt: the
// tools run on Anthropic's side, so a tool that isn't enabled here can't be
// called at all, no matter what the model decides to do.

// Everything that only looks. `describe_*` are systeme.io's own build
// instructions - they hand Claude the page schema it must fill in.
const READ_ONLY_TOOLS = [
  "describe_funnels",
  "describe_funnel_page_schema",
  "describe_page_content_guide",
  "get_funnels",
  "get_funnel",
  "get_funnel_steps",
  "get_funnel_step",
  "get_contacts",
  "get_contact",
  "get_contact_fields",
  "get_tags",
  "get_tag",
  "get_coupons",
  "get_coupon",
  "get_newsletters",
  "get_newsletter",
];

// Tools that remove something. Building a store never needs these, and an
// agent with a wrong idea about your contact list is not a mistake you can
// undo, so they stay off unless you ask for them by name.
const DESTRUCTIVE_TOOLS = [
  "remove_contact",
  "remove_contact_tag",
  "remove_tag",
  "delete_coupon",
];

// Builds the `tools` entry for the Messages API.
//
//   readOnly     - nothing but the list above (used by --dry-run and check)
//   allowDeletes - re-enables DESTRUCTIVE_TOOLS (used by --allow-deletes)
function buildToolset({ serverName, readOnly = false, allowDeletes = false }) {
  if (readOnly) {
    return {
      type: "mcp_toolset",
      mcp_server_name: serverName,
      default_config: { enabled: false },
      configs: READ_ONLY_TOOLS.map((name) => ({ name, enabled: true })),
    };
  }
  if (allowDeletes) {
    return { type: "mcp_toolset", mcp_server_name: serverName };
  }
  return {
    type: "mcp_toolset",
    mcp_server_name: serverName,
    default_config: { enabled: true },
    configs: DESTRUCTIVE_TOOLS.map((name) => ({ name, enabled: false })),
  };
}

// True when an API error looks like "this server doesn't accept per-tool
// config". Worth telling apart from ordinary errors: it means the guard
// rails above aren't being applied, which the caller must not paper over.
function isToolConfigRejection(err) {
  const message = String(err && err.message ? err.message : err).toLowerCase();
  if (!message.includes("400") && err?.status !== 400) return false;
  return (
    message.includes("configs") ||
    message.includes("default_config") ||
    message.includes("mcp_toolset")
  );
}

module.exports = {
  READ_ONLY_TOOLS,
  DESTRUCTIVE_TOOLS,
  buildToolset,
  isToolConfigRejection,
};
