// Runs one request against your systeme.io account.
//
// The shape here is deliberately small: your Anthropic key pays for Claude,
// Claude calls systeme.io's MCP server, and systeme.io does the work. The
// tool calls run on Anthropic's side, not this computer, so there is no
// local tool loop to maintain - this file just streams the conversation,
// resumes it when the server pauses a long turn, and adds up the bill.

const Anthropic = require("@anthropic-ai/sdk");

const { buildMcpUrl } = require("./config");
const { buildToolset, isToolConfigRejection } = require("./tools");

// Name Claude uses to refer to the server. Internal to one request.
const SERVER_NAME = "systeme";

// Lets Claude connect to a remote MCP server from the Messages API.
const MCP_BETA = "mcp-client-2025-11-20";
const FALLBACK_BETA = "server-side-fallback-2026-07-01";

// Pulls a readable tool name off a streamed block, whatever the block is
// called. Written loosely on purpose: the useful signal is "a tool ran and
// here's its name", and that shouldn't break if a block type is renamed.
function toolNameOf(block) {
  if (!block || typeof block !== "object") return null;
  if (typeof block.type === "string" && block.type.endsWith("tool_use")) {
    return block.name || "(unnamed tool)";
  }
  return null;
}

function isFailedToolResult(block) {
  return Boolean(
    block && typeof block.type === "string" && block.type.endsWith("tool_result") && block.is_error
  );
}

// Turns an SDK error into something worth reading at 9pm.
function explain(err) {
  const status = err && err.status;
  if (status === 401) {
    return new Error(
      "Anthropic rejected your API key. Check ANTHROPIC_API_KEY in .env " +
        "against console.anthropic.com -> API keys."
    );
  }
  if (status === 402 || /credit balance/i.test(err?.message || "")) {
    return new Error(
      "Your Anthropic account is out of credit. Top it up at " +
        "console.anthropic.com -> Billing, then run this again."
    );
  }
  if (status === 429) {
    return new Error("Anthropic is rate-limiting you. Wait a minute and run this again.");
  }
  if (isToolConfigRejection(err)) {
    return new Error(
      "Anthropic refused the per-tool safety settings this script sends " +
        "(the ones that keep delete tools switched off). Rather than run " +
        "without them, it stopped. Re-run with --allow-deletes only if you " +
        "genuinely intend to let it delete things.\n  Original error: " +
        err.message
    );
  }
  return err;
}

/**
 * @param {object} opts
 * @param {object} opts.config       from config.load()
 * @param {string} opts.instruction  what you want done, in plain English
 * @param {string} opts.system       the system prompt
 * @param {boolean} [opts.readOnly]  look but don't touch
 * @param {boolean} [opts.allowDeletes]
 * @param {(e: {type: string, text?: string, name?: string, turn?: number}) => void} [opts.onEvent]
 */
async function runAgent({
  config,
  instruction,
  system,
  readOnly = false,
  allowDeletes = false,
  onEvent = () => {},
}) {
  if (!config.anthropicKey) {
    throw new Error(
      "No Anthropic API key yet. Get one at console.anthropic.com -> API " +
        "keys, then put it in .env as ANTHROPIC_API_KEY."
    );
  }

  const client = new Anthropic({ apiKey: config.anthropicKey });
  const messages = [{ role: "user", content: instruction }];

  const params = {
    model: config.model,
    max_tokens: config.maxTokens,
    system,
    thinking: { type: "adaptive" },
    output_config: { effort: config.effort },
    betas: [MCP_BETA],
    mcp_servers: [
      { type: "url", name: SERVER_NAME, url: buildMcpUrl(config.mcpKey, config.mcpBase) },
    ],
    tools: [buildToolset({ serverName: SERVER_NAME, readOnly, allowDeletes })],
    messages,
  };

  if (config.useFallbacks) {
    params.betas.push(FALLBACK_BETA);
    params.fallbacks = "default";
  }

  const usage = { input: 0, output: 0 };
  const toolsUsed = [];
  let failedTools = 0;

  for (let turn = 1; turn <= config.maxTurns; turn++) {
    onEvent({ type: "turn", turn });

    let message;
    try {
      const stream = client.beta.messages.stream(params);
      for await (const event of stream) {
        if (event.type === "content_block_start") {
          const name = toolNameOf(event.content_block);
          if (name) {
            toolsUsed.push(name);
            onEvent({ type: "tool", name });
          }
          // Live notice only. The count comes from the finished message
          // below, which is the complete record - counting here as well
          // would report the same failure twice.
          if (isFailedToolResult(event.content_block)) onEvent({ type: "tool_failed" });
        } else if (
          event.type === "content_block_delta" &&
          event.delta &&
          event.delta.type === "text_delta"
        ) {
          onEvent({ type: "text", text: event.delta.text });
        }
      }
      message = await stream.finalMessage();
    } catch (err) {
      throw explain(err);
    }

    usage.input += message.usage?.input_tokens || 0;
    usage.output += message.usage?.output_tokens || 0;

    for (const block of message.content || []) {
      if (isFailedToolResult(block)) failedTools++;
    }

    if (message.stop_reason === "refusal") {
      throw new Error(
        "Claude declined this request" +
          (message.stop_details?.explanation ? `: ${message.stop_details.explanation}` : ".") +
          "\nNothing was changed in your systeme.io account."
      );
    }

    messages.push({ role: "assistant", content: message.content });

    // A long run of systeme.io calls can hit the server's per-turn limit.
    // Sending the conversation straight back picks up where it left off -
    // deliberately with no extra "continue" message, which would confuse it.
    if (message.stop_reason === "pause_turn") continue;

    // Only possible if a tool that runs on *this* computer got into the
    // request. Nothing here defines one, so this means the request was
    // built wrong - and looping would hang forever waiting for a result.
    if (message.stop_reason === "tool_use") {
      throw new Error(
        "Claude asked this computer to run a tool, which this script has no " +
          "way to do. That's a bug in the request, not something you did."
      );
    }

    return {
      message,
      usage,
      turns: turn,
      toolsUsed,
      failedTools,
      truncated: message.stop_reason === "max_tokens",
    };
  }

  throw new Error(
    `Stopped after ${config.maxTurns} rounds without finishing. Anything ` +
      "already created is still in your account - open the funnels page to " +
      "see where it got to. Re-run with a narrower request, or raise " +
      "STORE_MAX_TURNS in .env."
  );
}

module.exports = { runAgent, SERVER_NAME, MCP_BETA, toolNameOf, isFailedToolResult };
