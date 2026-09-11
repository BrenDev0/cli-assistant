import json

import tiktoken
from langchain_core.utils.function_calling import convert_to_openai_tool

from src.assistants.orchestrator.config import MODEL, SCHEMAS
from src.core.agents.langchain.agent import AVAILABLE_MODELS, LangchainAgent, provider_for
from src.core.agents.types import Message
from src.core.lang import t

from src import voice

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
    labels = [t(f"tokens.{name}")
              for name in ("schemas", "prefix", "history", "total")]
    pad = max(len(label) for label in labels)

    return (
        f"{labels[0]:<{pad}} {counts['tools']:>9,}\n"
        f"  {labels[1]:<{pad}} {counts['prefix']:>9,}\n"
        f"  {labels[2]:<{pad}} {counts['history']:>9,}"
        f"  ({counts['turns']} {t('tokens.messages')})\n"
        f"  {labels[3]:<{pad}} {counts['total']:>9,}"
        f"  ({t('tokens.floor', floor=f'{floor:,}')})"
    )


async def compress(messages: list[Message], model: str = MODEL) -> tuple[list[Message], str]:
    """Replace the conversation tail with a summary, keeping the static prefix intact."""
    history = messages[HISTORY_START:]
    if not history:
        return messages, t("cmd.nothing_to_compress")

    before = count_tokens(messages, model)

    transcript = "\n\n".join(f"{_text(m)}" for m in history if _text(m).strip())

    # tools=None: the summariser must not start calling tools mid-summary, and invoke()
    # would otherwise run a full agent loop over an 18-tool binding
    # stream=False as well: a summary is bookkeeping, not a reply, and streaming it would
    # print the whole transcript summary over the conversation it just replaced
    summariser = LangchainAgent(model=model, temperature=0.0, tools=None, stream=False)
    summary = await summariser.invoke([
        ("system", COMPRESS_PROMPT),
        ("user", transcript),
    ])

    compressed = messages[:HISTORY_START] + [
        ("system", f"Summary of the conversation so far:\n{summary}")
    ]
    after = count_tokens(compressed, model)
    saved = before["total"] - after["total"]

    return compressed, t(
        "cmd.compressed",
        before=before["turns"],
        from_=f"{before['total']:,}",
        to=f"{after['total']:,}",
        saved=f"{saved:,}",
    )


def switch_model(agent: LangchainAgent, requested: str) -> LangchainAgent:
    """A new agent bound to the new model. `messages` is untouched -- LangChain message
    objects are provider-agnostic, so history survives the switch."""
    replacement = LangchainAgent(
        model=requested,
        temperature=agent._temperature,
        tools=agent._tools,
    )
    ui.notice(t("cmd.model_switched", model=requested,
               provider=provider_for(requested)))
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
            ui.notice(t("cmd.model_current", model=current,
                      available=", ".join(AVAILABLE_MODELS)))
            return messages, agent

        try:
            agent = switch_model(agent, parts[1]) if agent else agent
        except ValueError as exc:
            ui.error(str(exc))
        return messages, agent

    if name in ("/compress", "/compact"):
        ui.notice(t("cmd.compressing"))
        messages, report = await compress(messages, current)
        ui.notice(report)
        return messages, agent

    if name == "/tokens":
        ui.notice(tokens_report(messages, current))
        return messages, agent

    if name == "/voice":
        try:
            on = await voice.toggle()
        except Exception as exc:
            ui.error(t("voice.unavailable", error=exc))
            return messages, agent

        ui.notice(t("voice.on" if on else "voice.off"))
        return messages, agent

    if name == "/auto":
        # shift+tab is the shortcut, but some terminals never deliver BackTab to the
        # application, and a mode you cannot reach is a mode you do not have
        from src.core import mode
        on = mode.toggle_auto()
        ui.notice(t("auto.on" if on else "auto.off"))
        return messages, agent

    if name == "/browser":
        from src.tools.browser.tools import browser_status
        ui.notice(browser_status())
        return messages, agent

    if name == "/clear":
        dropped = len(messages) - HISTORY_START
        ui.notice(t("cmd.cleared", count=dropped))
        return messages[:HISTORY_START], agent

    if name == "/help":
        ui.notice(t("cmd.help"))
        return messages, agent

    ui.error(t("cmd.unknown", name=name))
    return messages, agent
