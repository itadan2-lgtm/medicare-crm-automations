// Everything the systeme.io store tools need to know about your setup.
// Two keys, and that's it:
//
//   ANTHROPIC_API_KEY  - pays for Claude's thinking (console.anthropic.com)
//   SYSTEME_MCP_KEY    - lets Claude into your systeme.io account
//
// Claude never talks to systeme.io directly from this computer. It calls
// systeme.io's own MCP server, which is the same connection the systeme.io
// help pages describe for the Claude desktop app - we just drive it from a
// script instead of a chat window.

// quiet: dotenv v17 prints a tips banner otherwise, which buries the
// plain-English output these tools are trying to give you.
require("dotenv").config({ quiet: true });

// systeme.io's official remote MCP server. The key rides along as a query
// parameter (their design, not ours), which is why redact() exists below -
// this URL must never be printed or logged as-is.
const DEFAULT_MCP_BASE = "https://mcp.systeme.io/mcp";

const DEFAULTS = {
  model: "claude-opus-5",
  // Building a funnel is long-horizon agentic work - many tool calls, and a
  // page design that has to hold together end to end. xhigh is the setting
  // Anthropic recommends for exactly this shape of task.
  effort: "xhigh",
  maxTokens: 64000,
  // One "turn" is one round trip to Claude. A full funnel (plan, create,
  // one page design per step) fits comfortably; the cap is only here so a
  // confused run can't loop forever on your credit card.
  maxTurns: 40,
};

const EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"];

// Builds the URL Claude connects to. Throws with a plain-English fix rather
// than letting a blank key turn into a confusing 401 later.
function buildMcpUrl(key, base = DEFAULT_MCP_BASE) {
  const trimmed = String(key || "").trim();
  if (!trimmed) {
    throw new Error(
      "No systeme.io MCP key yet. In systeme.io: Settings -> Public API keys " +
        "-> MCP keys -> create one, then put it in .env as SYSTEME_MCP_KEY."
    );
  }
  if (/\s/.test(trimmed)) {
    throw new Error(
      "Your SYSTEME_MCP_KEY has a space in it, so it was probably copied " +
        "with something extra. Copy just the key and paste it again."
    );
  }
  const url = new URL(base);
  url.searchParams.set("mcpKey", trimmed);
  return url.toString();
}

// Safe to print. Keeps the host visible so connection problems are still
// diagnosable, hides the key itself.
function redact(url) {
  try {
    const parsed = new URL(url);
    if (parsed.searchParams.has("mcpKey")) parsed.searchParams.set("mcpKey", "****");
    return parsed.toString();
  } catch {
    return "(unreadable URL)";
  }
}

// Reads settings, applies defaults, and complains about bad values now
// instead of halfway through a run.
function load() {
  const effort = (process.env.STORE_EFFORT || DEFAULTS.effort).toLowerCase();
  if (!EFFORT_LEVELS.includes(effort)) {
    throw new Error(
      `STORE_EFFORT is "${effort}", which isn't one of: ${EFFORT_LEVELS.join(", ")}.`
    );
  }
  const maxTurns = Number(process.env.STORE_MAX_TURNS || DEFAULTS.maxTurns);
  if (!Number.isInteger(maxTurns) || maxTurns < 1) {
    throw new Error(`STORE_MAX_TURNS must be a whole number of 1 or more.`);
  }

  return {
    anthropicKey: process.env.ANTHROPIC_API_KEY || "",
    mcpKey: process.env.SYSTEME_MCP_KEY || "",
    mcpBase: process.env.SYSTEME_MCP_URL || DEFAULT_MCP_BASE,
    model: process.env.STORE_MODEL || DEFAULTS.model,
    effort,
    maxTokens: Number(process.env.STORE_MAX_TOKENS || DEFAULTS.maxTokens),
    maxTurns,
    // Off by default. When on, Anthropic silently retries on a second model
    // if a safety classifier declines a request. Marketing copy almost never
    // trips those, so this stays opt-in rather than adding a moving part.
    useFallbacks: process.env.STORE_FALLBACKS === "1",
  };
}

module.exports = { DEFAULT_MCP_BASE, DEFAULTS, EFFORT_LEVELS, buildMcpUrl, redact, load };
