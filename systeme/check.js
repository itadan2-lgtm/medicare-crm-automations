// `npm run store:check` - proves the whole chain works before you trust it
// with a real build: your Anthropic key, your systeme.io MCP key, and the
// connection between them. Read-only; it never changes anything.

const fs = require("fs");
const path = require("path");

const { load, buildMcpUrl, redact } = require("./internal/config");
const { runAgent } = require("./internal/agent");

const ENV_PATH = path.join(__dirname, "..", ".env");

const ok = (msg) => console.log(`  ✔ ${msg}`);
const bad = (msg) => console.log(`  ✖ ${msg}`);
const note = (msg) => console.log(`    ${msg}`);

const PROBE =
  "List every funnel in this account. For each one give just the name and " +
  "the id, one per line. If there are none, say so. No other commentary.";

async function main() {
  console.log("\nChecking the systeme.io store connection...\n");

  if (fs.existsSync(ENV_PATH)) ok("Settings file exists.");
  else note("No .env file yet - reading settings from the environment.");

  const config = load();

  if (!config.anthropicKey) {
    bad("No Anthropic API key.");
    note("Get one at console.anthropic.com -> API keys, then add it to .env");
    note("as ANTHROPIC_API_KEY. This is what pays for Claude's thinking.");
    console.log("");
    process.exitCode = 1;
    return;
  }
  ok("Anthropic API key is set.");

  try {
    const url = buildMcpUrl(config.mcpKey, config.mcpBase);
    ok(`systeme.io MCP key is set (${redact(url)}).`);
  } catch (err) {
    bad(err.message);
    note("In systeme.io: Settings -> Public API keys -> MCP keys -> create a");
    note("key, copy it, and add it to .env as SYSTEME_MCP_KEY.");
    console.log("");
    process.exitCode = 1;
    return;
  }

  console.log("");
  console.log("  Asking Claude to read your funnel list (this costs a few cents)...");
  console.log("");

  const probeConfig = { ...config, effort: "low", maxTokens: 4000, maxTurns: 4 };
  let result;
  try {
    result = await runAgent({
      config: probeConfig,
      instruction: PROBE,
      system: "You are checking a connection. Answer briefly and factually.",
      readOnly: true,
    });
  } catch (err) {
    bad("Couldn't complete the check.");
    for (const line of String(err.message).split("\n")) note(line);
    console.log("");
    process.exitCode = 1;
    return;
  }

  if (result.failedTools > 0) {
    bad("Claude reached systeme.io but the call came back with an error.");
    note("That usually means the MCP key is wrong, expired, or was revoked.");
    note("Make a fresh one in systeme.io (Settings -> Public API keys -> MCP");
    note("keys) and update SYSTEME_MCP_KEY in .env.");
    console.log("");
    process.exitCode = 1;
    return;
  }

  ok("Claude can read your systeme.io account. Here's what it found:");
  console.log("");
  const answer = (result.message.content || [])
    .filter((b) => b.type === "text")
    .map((b) => b.text)
    .join("")
    .trim();
  for (const line of (answer || "(no answer came back)").split("\n")) {
    console.log(`    ${line}`);
  }

  console.log("");
  console.log("Everything's connected. Try a real build:");
  console.log('  npm run store -- "Build a lead magnet funnel for <your offer>"');
  console.log("");
}

main().catch((err) => {
  console.log(`\nThe check itself hit an error: ${err.message}\n`);
  process.exitCode = 1;
});
