import json

import tiktoken
from langchain_core.utils.function_calling import convert_to_openai_tool

from src.assistants.orchestrator.config import MODEL, SCHEMAS
from src.core.agents.langchain.agent import AVAILABLE_MODELS, LangchainAgent, provider_for
from src.core.agents.types import Message

from . import ui

# messages[0:3] are the static prompt, the GHL catalog, and the per-turn context slot.
# Everything from here on is conversation, and the only part safe to rewrite.
HISTORY_START = 3

KEEP_TURNS = 10
TRIM_MARKER = "[earlier turns trimmed]"


def _role(message: Message) -> str:
    if isinstance(message, tuple):
        return str(message[0])
    if isinstance(message, dict):
        return str(message.get("role", ""))
    return ""


def trim_history(messages: list[Message]) -> list[Message]:
    """Keep the last KEEP_TURNS user turns, cutting only at user-message boundaries.

    Slicing by raw message count would orphan a tool result from the assistant message
    that requested it, which the API rejects outright. User messages are the only safe
    cut points.
    """
    history = [m for m in messages[HISTORY_START:]
               if not (_role(m) == "system" and TRIM_MARKER in str(_text(m)))]

    turns = [i for i, m in enumerate(history) if _role(m) == "user"]
    if len(turns) <= KEEP_TURNS:
        return messages[:HISTORY_START] + history

    start = turns[-KEEP_TURNS]
    dropped = len(turns) - KEEP_TURNS
    marker = ("system",
              f"{TRIM_MARKER} {dropped} earlier exchange(s) are no longer shown here. "
              f"They are saved -- call SearchConversationHistory to recall anything from "
              f"them rather than guessing.")

    return messages[:HISTORY_START] + [marker] + history[start:]

COMPRESS_PROMPT = """Summarise this conversation so it can replace the original transcript.
Another assistant will continue the conversation reading only your summary, so preserve
anything it would need and drop anything it would not.

Always keep, verbatim where they are identifiers:
- background task ids and what each task was doing
- file paths that were created or modified
- constraints the user stated: language, tone, format, audience, deadlines
- decisions made and the reasoning behind them
- questions the user asked that were never answered
- what the user is currently working on

Drop: tool call mechanics, retries, intermediate reasoning, and any content that was
superseded later.

Write it as compact notes, not prose. No preamble."""


def _encoder(model: str = MODEL):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # anthropic models and ids newer than tiktoken's table -- approximate, not exact
        return tiktoken.get_encoding("o200k_base")


def _text(message: Message) -> str:
    if isinstance(message, tuple):
        return str(message[1])
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return str(getattr(message, "content", message))


def count_tokens(messages: list[Message], model: str = MODEL) -> dict[str, int]:
    enc = _encoder(model)
    tools = len(enc.encode(json.dumps([convert_to_openai_tool(s) for s in SCHEMAS])))
    prefix = sum(len(enc.encode(_text(m))) for m in messages[:HISTORY_START])
    history = sum(len(enc.encode(_text(m))) for m in messages[HISTORY_START:])

    return {
        "tools": tools,
        "prefix": prefix,
        "history": history,
        "total": tools + prefix + history,
        "turns": len(messages) - HISTORY_START,
    }


def tokens_report(messages: list[Message], model: str = MODEL) -> str:
    counts = count_tokens(messages, model)
    floor = counts["tools"] + counts["prefix"]
    return (
        f"tool schemas   {counts['tools']:>7,}\n"
        f"  static prefix  {counts['prefix']:>7,}\n"
        f"  history        {counts['history']:>7,}  ({counts['turns']} messages)\n"
        f"  total          {counts['total']:>7,}  (floor {floor:,} cannot be compressed)"
    )


async def compress(messages: list[Message], model: str = MODEL) -> tuple[list[Message], str]:
    """Replace the conversation tail with a summary, keeping the static prefix intact."""
    history = messages[HISTORY_START:]
    if not history:
        return messages, "nothing to compress"

    before = count_tokens(messages, model)

    transcript = "\n\n".join(f"{_text(m)}" for m in history if _text(m).strip())

    # tools=None: the summariser must not start calling tools mid-summary, and invoke()
    # would otherwise run a full agent loop over an 18-tool binding
    summariser = LangchainAgent(model=model, temperature=0.0, tools=None)
    summary = await summariser.invoke([
        ("system", COMPRESS_PROMPT),
        ("user", transcript),
    ])

    compressed = messages[:HISTORY_START] + [
        ("system", f"Summary of the conversation so far:\n{summary}")
    ]
    after = count_tokens(compressed, model)
    saved = before["total"] - after["total"]

    return compressed, (
        f"compressed {before['turns']} messages -> summary, "
        f"{before['total']:,} -> {after['total']:,} tokens (saved {saved:,})"
    )


def switch_model(agent: LangchainAgent, requested: str) -> LangchainAgent:
    """A new agent bound to the new model. `messages` is untouched -- LangChain message
    objects are provider-agnostic, so history survives the switch."""
    replacement = LangchainAgent(
        model=requested,
        temperature=agent._temperature,
        tools=agent._tools,
    )
    ui.notice(f"model -> {requested} ({provider_for(requested)})")
    return replacement


async def handle(
    command: str,
    messages: list[Message],
    agent: LangchainAgent | None = None,
) -> tuple[list[Message], LangchainAgent | None]:
    """Returns (messages, agent). Unknown /commands are reported, not sent to the model."""
    parts = command.split()
    name = parts[0].lower()
    current = agent._model if agent else MODEL

    if name == "/model":
        if len(parts) < 2:
            ui.notice(f"current: {current}\n  available: {', '.join(AVAILABLE_MODELS)}")
            return messages, agent

        try:
            agent = switch_model(agent, parts[1]) if agent else agent
        except ValueError as exc:
            ui.error(str(exc))
        return messages, agent

    if name in ("/compress", "/compact"):
        ui.notice("compressing...")
        messages, report = await compress(messages, current)
        ui.notice(report)
        return messages, agent

    if name == "/tokens":
        ui.notice(tokens_report(messages, current))
        return messages, agent

    if name == "/clear":
        dropped = len(messages) - HISTORY_START
        ui.notice(f"cleared {dropped} messages")
        return messages[:HISTORY_START], agent

    if name == "/help":
        ui.notice(
            "/compress  summarise the conversation and drop the transcript\n"
            "  /tokens    show what is filling the context\n"
            "  /clear     drop the conversation entirely\n"
            "  /model     show or switch the model\n"
            "  exit       leave"
        )
        return messages, agent

    ui.error(f"unknown command {name} — try /help")
    return messages, agent
