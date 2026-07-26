// `npm run store -- "what you want"` - the one command.
//
//   npm run store -- "Build a lead magnet funnel for a free Medicare
//                     enrollment checklist aimed at people turning 65"
//
// It designs the funnel, creates it in your systeme.io account, writes every
// page, and prints the dashboard link when it's done.

const { load, buildMcpUrl } = require("./internal/config");
const { SYSTEM_PROMPT } = require("./internal/prompt");
const { runAgent } = require("./internal/agent");

const HELP = `
Build and manage systeme.io funnels in plain English.

  npm run store -- "<what you want>"

Examples
  npm run store -- "Build a lead magnet funnel for a free Medicare
                    enrollment checklist for people turning 65"
  npm run store -- "Add a thank-you page to my 'email collector' funnel"
  npm run store -- "List my funnels and tell me which ones have empty pages"

Options
  --dry-run         Look, plan, and describe - but change nothing. Enforced
                    by only switching on systeme.io's read-only tools, so it
                    can't write even if it decides to.
  --allow-deletes   Permit the delete/remove tools. Off by default.
  --effort=LEVEL    low | medium | high | xhigh | max   (default xhigh)
  --turns=N         Give up after N rounds (default 40)
  --help            This text
`.trim();

function parseArgs(argv) {
  const opts = { dryRun: false, allowDeletes: false, help: false };
  const words = [];
  for (const arg of argv) {
    if (arg === "--help" || arg === "-h") opts.help = true;
    else if (arg === "--dry-run") opts.dryRun = true;
    else if (arg === "--allow-deletes") opts.allowDeletes = true;
    else if (arg.startsWith("--effort=")) opts.effort = arg.slice(9).toLowerCase();
    else if (arg.startsWith("--turns=")) opts.turns = Number(arg.slice(8));
    else if (arg.startsWith("--")) throw new Error(`I don't know the option "${arg}". Try --help.`);
    else words.push(arg);
  }
  opts.instruction = words.join(" ").trim();
  return opts;
}

// Keeps streamed text and tool lines from running into each other.
function makeWriter() {
  let atLineStart = true;
  return {
    text(s) {
      if (!s) return;
      process.stdout.write(s);
      atLineStart = s.endsWith("\n");
    },
    line(s) {
      if (!atLineStart) process.stdout.write("\n");
      process.stdout.write(`${s}\n`);
      atLineStart = true;
    },
    blank() {
      if (!atLineStart) process.stdout.write("\n");
      process.stdout.write("\n");
      atLineStart = true;
    },
  };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));

  if (opts.help || !opts.instruction) {
    console.log(`\n${HELP}\n`);
    if (!opts.instruction && !opts.help) process.exitCode = 1;
    return;
  }

  const config = load();
  if (opts.effort) config.effort = opts.effort;
  if (opts.turns) config.maxTurns = opts.turns;

  // Check both keys before announcing anything - "working in your account"
  // followed by "you have no key" reads like something already happened.
  if (!config.anthropicKey) {
    throw new Error(
      "No Anthropic API key yet. Get one at console.anthropic.com -> API " +
        "keys, then put it in .env as ANTHROPIC_API_KEY.\n" +
        "Run `npm run store:check` to check both keys at once."
    );
  }
  buildMcpUrl(config.mcpKey, config.mcpBase);

  const out = makeWriter();
  out.blank();
  if (opts.dryRun) {
    out.line("Dry run - reading your account and planning, changing nothing.");
  } else if (opts.allowDeletes) {
    out.line("Running with delete tools ENABLED. Removals are permanent.");
  } else {
    out.line("Working in your systeme.io account (delete tools are off).");
  }
  out.blank();

  const result = await runAgent({
    config,
    instruction: opts.instruction,
    system: SYSTEM_PROMPT,
    readOnly: opts.dryRun,
    allowDeletes: opts.allowDeletes,
    onEvent(e) {
      if (e.type === "text") out.text(e.text);
      else if (e.type === "tool") out.line(`  → ${e.name}`);
      else if (e.type === "tool_failed") out.line("  ! that call came back with an error");
    },
  });

  out.blank();
  const billed = result.usage.input + result.usage.output;
  out.line(
    `Done in ${result.turns} round${result.turns === 1 ? "" : "s"}, ` +
      `${result.toolsUsed.length} systeme.io call${result.toolsUsed.length === 1 ? "" : "s"}, ` +
      `about ${billed.toLocaleString()} tokens.`
  );
  if (result.failedTools > 0) {
    out.line(
      `${result.failedTools} systeme.io call${result.failedTools === 1 ? "" : "s"} failed - ` +
        "read the summary above before assuming the funnel is complete."
    );
    process.exitCode = 1;
  }
  if (result.truncated) {
    out.line("It ran out of room mid-answer. Re-run with a narrower request.");
    process.exitCode = 1;
  }
  out.line("Your funnels: https://systeme.io/dashboard/funnels");
  out.blank();
}

// Only run when invoked directly - the tests import parseArgs from here.
if (require.main === module) {
  main().catch((err) => {
    console.log(`\n${err.message}\n`);
    process.exitCode = 1;
  });
}

module.exports = { parseArgs };
