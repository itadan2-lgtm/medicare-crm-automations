/**
 * systeme/tests/run-tests.js - offline tests for the store tools.
 *
 * No network, no API keys, no charges: everything here checks the parts that
 * decide what gets sent - the connection URL, the tool safety gates, and the
 * command-line parsing. Run with: npm run store:test
 */

const assert = require("assert");

const { buildMcpUrl, redact, load, DEFAULT_MCP_BASE } = require("../internal/config");
const {
  buildToolset,
  READ_ONLY_TOOLS,
  DESTRUCTIVE_TOOLS,
  isToolConfigRejection,
} = require("../internal/tools");
const { toolNameOf, isFailedToolResult } = require("../internal/agent");
const { SYSTEM_PROMPT } = require("../internal/prompt");
const { parseArgs } = require("../store");

let pass = 0,
  fail = 0;
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

console.log("\nconfig.js, buildMcpUrl()");
test("puts the key on the URL the way systeme.io expects", () => {
  const url = new URL(buildMcpUrl("abc123"));
  assert.strictEqual(url.origin + url.pathname, DEFAULT_MCP_BASE);
  assert.strictEqual(url.searchParams.get("mcpKey"), "abc123");
});

test("a missing key explains where to get one", () => {
  assert.throws(() => buildMcpUrl(""), /MCP keys/);
  assert.throws(() => buildMcpUrl(undefined), /MCP keys/);
});

test("a key pasted with a space is caught, not sent", () => {
  assert.throws(() => buildMcpUrl("abc 123"), /space/);
});

test("surrounding whitespace is forgiven", () => {
  assert.strictEqual(new URL(buildMcpUrl("  abc123\n")).searchParams.get("mcpKey"), "abc123");
});

test("a custom base URL keeps its own query parameters", () => {
  const url = new URL(buildMcpUrl("k", "https://example.test/mcp?tenant=7"));
  assert.strictEqual(url.searchParams.get("tenant"), "7");
  assert.strictEqual(url.searchParams.get("mcpKey"), "k");
});

console.log("\nconfig.js, redact()");
test("hides the key but keeps the host readable", () => {
  const shown = redact(buildMcpUrl("supersecret"));
  assert.ok(!shown.includes("supersecret"), "the key leaked into the printable URL");
  assert.ok(shown.includes("mcp.systeme.io"));
});

test("never throws on a malformed URL", () => {
  assert.strictEqual(redact("not a url"), "(unreadable URL)");
});

console.log("\nconfig.js, load()");
test("rejects an effort level the API would reject", () => {
  const before = process.env.STORE_EFFORT;
  process.env.STORE_EFFORT = "turbo";
  assert.throws(() => load(), /turbo/);
  if (before === undefined) delete process.env.STORE_EFFORT;
  else process.env.STORE_EFFORT = before;
});

test("defaults to Opus 5 at xhigh effort", () => {
  const config = load();
  assert.strictEqual(config.model, "claude-opus-5");
  assert.strictEqual(config.effort, "xhigh");
});

console.log("\ntools.js, buildToolset()");
test("dry run turns everything off, then re-enables only read tools", () => {
  const toolset = buildToolset({ serverName: "systeme", readOnly: true });
  assert.strictEqual(toolset.default_config.enabled, false);
  const enabled = toolset.configs.filter((c) => c.enabled).map((c) => c.name);
  assert.deepStrictEqual(enabled.sort(), [...READ_ONLY_TOOLS].sort());
});

test("dry run cannot reach a single write tool", () => {
  const toolset = buildToolset({ serverName: "systeme", readOnly: true });
  const names = toolset.configs.map((c) => c.name);
  for (const writeTool of ["create_funnel", "save_funnel_page_content", ...DESTRUCTIVE_TOOLS]) {
    assert.ok(!names.includes(writeTool), `${writeTool} was reachable in a dry run`);
  }
});

test("a normal run allows building but blocks deleting", () => {
  const toolset = buildToolset({ serverName: "systeme" });
  assert.strictEqual(toolset.default_config.enabled, true);
  const disabled = toolset.configs.filter((c) => !c.enabled).map((c) => c.name);
  assert.deepStrictEqual(disabled.sort(), [...DESTRUCTIVE_TOOLS].sort());
});

test("--allow-deletes is the only way to reach a delete tool", () => {
  const toolset = buildToolset({ serverName: "systeme", allowDeletes: true });
  assert.strictEqual(toolset.configs, undefined);
  assert.strictEqual(toolset.mcp_server_name, "systeme");
});

test("the read-only list stayed read-only", () => {
  for (const name of READ_ONLY_TOOLS) {
    assert.ok(
      /^(get|describe)_/.test(name),
      `"${name}" is in the read-only list but doesn't look read-only`
    );
  }
});

console.log("\ntools.js, isToolConfigRejection()");
test("spots the API refusing per-tool settings", () => {
  const err = new Error("400 Bad Request: unexpected field `configs`");
  err.status = 400;
  assert.strictEqual(isToolConfigRejection(err), true);
});

test("an ordinary error is not mistaken for one", () => {
  const err = new Error("connection reset");
  assert.strictEqual(isToolConfigRejection(err), false);
});

console.log("\nagent.js, block readers");
test("reads a tool name off a tool-use block", () => {
  assert.strictEqual(toolNameOf({ type: "mcp_tool_use", name: "create_funnel" }), "create_funnel");
  assert.strictEqual(toolNameOf({ type: "text", text: "hi" }), null);
  assert.strictEqual(toolNameOf(null), null);
});

test("notices a failed tool result", () => {
  assert.strictEqual(isFailedToolResult({ type: "mcp_tool_result", is_error: true }), true);
  assert.strictEqual(isFailedToolResult({ type: "mcp_tool_result", is_error: false }), false);
  assert.strictEqual(isFailedToolResult({ type: "text" }), false);
});

console.log("\nprompt.js");
test("states the step that would otherwise be skipped", () => {
  assert.ok(SYSTEM_PROMPT.includes("save_funnel_page_content"));
  assert.ok(/not finished until every step has saved page content/.test(SYSTEM_PROMPT));
});

test("carries the layout rules that cause rejected saves", () => {
  assert.ok(/add up to exactly 12/.test(SYSTEM_PROMPT));
  assert.ok(/h1 headline is only allowed inside a hero/.test(SYSTEM_PROMPT));
  assert.ok(/[Aa]t most one Form per page/.test(SYSTEM_PROMPT));
});

test("tells Claude not to delete or email anyone unasked", () => {
  assert.ok(/Do not delete or remove anything/.test(SYSTEM_PROMPT));
  assert.ok(/Do not email anyone/.test(SYSTEM_PROMPT));
});

console.log("\nstore.js, parseArgs()");
test("joins the request back into one sentence", () => {
  const opts = parseArgs(["Build", "a", "funnel"]);
  assert.strictEqual(opts.instruction, "Build a funnel");
  assert.strictEqual(opts.dryRun, false);
  assert.strictEqual(opts.allowDeletes, false);
});

test("reads the flags", () => {
  const opts = parseArgs(["--dry-run", "--effort=medium", "--turns=5", "List", "funnels"]);
  assert.strictEqual(opts.dryRun, true);
  assert.strictEqual(opts.effort, "medium");
  assert.strictEqual(opts.turns, 5);
  assert.strictEqual(opts.instruction, "List funnels");
});

test("deleting is never on by accident", () => {
  assert.strictEqual(parseArgs(["do", "a", "thing"]).allowDeletes, false);
  assert.strictEqual(parseArgs(["--allow-deletes", "x"]).allowDeletes, true);
});

test("a typo'd option stops the run instead of being ignored", () => {
  assert.throws(() => parseArgs(["--dryrun", "x"]), /--dryrun/);
});

test("no request at all asks for help rather than guessing", () => {
  assert.strictEqual(parseArgs([]).instruction, "");
});

console.log(`\n${pass} passed, ${fail} failed\n`);
if (fail > 0) process.exitCode = 1;
