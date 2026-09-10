from src.core.agents.langchain.agent import LangchainAgent
from src.assistants.orchestrator.config import MODEL, SCHEMAS, TEMPERATURE
from src.assistants.orchestrator.prompt import SYSTEM_PROMPT
from src.tools.skills.tools import list_skills
import asyncio
from datetime import datetime
import click
from src.tools.ghl.tools import initialize_ghl_operations, catalog_text
from src.tools.background.tools import drain_completed, _RUNNING
from src.tools.ghl.tools import GHL
from src.tools.web.tools import initialize_web_client
from src.tools.history.tools import record, start_session
from src.core import frontend, lang, mode, workspace
from src.core.lang import t
from src import voice
from src.cli import commands, keys, ui
from src.cli.frontend import CliFrontend
from src.cli.inputbox import InputBox
from prompt_toolkit.patch_stdout import patch_stdout

# Holds everything that changes turn to turn — the clock and the skills listing.
# Kept after the static system prompt and GHL catalog so those stay a cacheable prefix,
# and rewritten rather than appended so it never goes stale or grows the conversation.
CONTEXT_MESSAGE_INDEX = 2

# Injected on the turn a task finishes, then immediately downgraded to TASK_RELAYED. Both
# forms carry the same verified output; only the first one asks for it to be reported.
TASK_NOTICE = (
    "A background task finished while the user was typing. The result below is the "
    "worker's complete, disk-verified output. Report it in THIS reply and nowhere else: "
    "do not extend, embellish, or substitute your own content, and if the result does not "
    "contain the requested deliverable, say so plainly.\n{news}"
)

TASK_RELAYED = (
    "[already reported to the user — do not announce this again] A background task "
    "finished earlier and its result was passed on. Kept only so you can refer back to "
    "the file paths in it:\n{news}"
)


# Sits in the per-turn slot rather than the system prompt so that toggling /voice takes
# effect on the very next turn, and so the cacheable prefix never changes.
VOICE_STYLE = (
    "This reply will be spoken out loud, not read. Write it the way you would say it: "
    "plain sentences only. No markdown, no bullet points, no numbered lists, no headings, "
    "no bold or asterisks -- all of it gets read aloud as punctuation or garbled. "
    "Keep it short, usually two or three sentences, and stop when the answer is done. "
    "If you are offering choices, say them in a sentence instead of listing them. "
    "Do not read out file paths, urls, or ids unless the user asked for one."
)


def context_message() -> str:
    now = datetime.now().astimezone()
    message = (
        f"Current date and time: {now:%A, %Y-%m-%d %H:%M} {now.tzname()} (UTC{now:%z}). "
        f"Treat this as the present moment when interpreting relative dates.\n\n"
        f"Available skills:\n{list_skills()}"
    )

    if voice.is_on():
        message += f"\n\n{VOICE_STYLE}"

    # the assistant answers in the language the app was started in; english needs
    # no instruction, being what the system prompt is already written in
    answer_in = lang.reply_language()
    if answer_in:
        message += f"{chr(10)}{chr(10)}{answer_in}"

    return message


async def chat_loop():
    cli = CliFrontend()
    frontend.use(cli)

    # before anything can create the new workspace and make the old one look abandoned.
    # Reported after the banner so startup does not open with a maintenance message.
    moved_workspace = workspace.adopt_legacy_home()

    llm = LangchainAgent(
        model=MODEL,
        temperature=TEMPERATURE,
        tools=SCHEMAS
    )

    # Both optional integrations fail the same way: a warning at startup, the rest of the
    # assistant still usable. A missing key is a first-run state, not a broken install.
    try:
        await initialize_ghl_operations()
    except Exception as exc:
        ui.error(t("error.ghl", error=exc))

    try:
        initialize_web_client()
    except RuntimeError as exc:
        ui.error(t("error.web", error=exc))

    messages = [
        ("system", SYSTEM_PROMPT),
        ("system", f"How to use GoHighLevel:\n{catalog_text()}"),
        ("system", ""),  # placeholder, filled in each turn below
    ]

    session_id = start_session()

    ui.banner(len(SCHEMAS), len(GHL["mcp_tools"] or ()), MODEL, session_id)

    if moved_workspace:
        ui.notice(moved_workspace)


    # callables, not their results: the box re-evaluates them on every redraw, so the
    # glyph follows /voice and the border follows a resize
    cli.model = llm._model
    box = InputBox(
        left=lambda: ui.listening_left() if voice.is_on() else ui.prompt_left(),
        status=lambda: ui.bottom_edge(cli.model, voice.is_on(), mode.auto()),
        tasks=lambda: cli.tasks,
        extra_bindings=keys.bindings(),
    )
    cli.read_line = box.next

    # patch_stdout for the whole session, not per prompt: the box is on screen the whole
    # time now, and anything printed has to be routed above it rather than into it
    async with box:
        with patch_stdout():
            await turns(box, cli, llm, messages)


async def turns(box, cli, llm, messages) -> None:
    while True:
        try:
            if voice.is_on():
                user_input, spoken = await voice.listen(box.next)
            else:
                user_input, spoken = await box.next(), False

        except Exception as e:
            ui.error(f"{type(e).__name__}: {e}")
            continue

        if user_input is None:
            ui.notice(t("goodbye"))
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # the box erases itself, so the accepted line has to be put back
        ui.heard(user_input) if spoken else ui.echo_input(user_input)

        if user_input.lower() in ("exit", "quit"):
            if _RUNNING:
                ui.error(t("tasks.abandoning", count=len(_RUNNING)))
            ui.notice(t("goodbye"))
            break

        if user_input.startswith("/"):
            messages, llm = await commands.handle(user_input, messages, llm)
            if llm:
                cli.model = llm._model
            continue

        messages[CONTEXT_MESSAGE_INDEX] = ("system", context_message())
        messages.append(("user", user_input))
        record("user", user_input)

        news = drain_completed()
        if news:
            messages.append(("system", TASK_NOTICE.format(news=news)))

        messages = commands.trim_history(messages)

        # The notice is the last message going in, and invoke() only ever appends after
        # it, so this index still points at it once the turn is over.
        notice_index = len(messages) - 1 if news else None

        cli.begin_turn()

        speaker = voice.Speaker() if voice.is_on() else None
        cli.on_reply = speaker.feed if speaker else None

        try:
            result = await llm.invoke(messages)
        except Exception as e:
            ui.error(f"{type(e).__name__}: {e}")
            # left as a live notice: the turn that was meant to relay it never ran
            continue
        finally:
            cli.on_reply = None

        if speaker:
            try:
                await speaker.finish()
            except Exception as e:
                ui.error(t("voice.failed", error=f"{type(e).__name__}: {e}"))

        # Spent. Left as-is it is a standing order to relay, read again on every later
        # turn -- which is why a finished task gets announced a second and third time
        # while the user is already talking about something else.
        if notice_index is not None:
            messages[notice_index] = ("system", TASK_RELAYED.format(news=news))

        record("assistant", result)


def _run(language: str) -> None:
    lang.use(language)
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        ui.notice(t("goodbye"))


@click.command()
def chat() -> None:
    _run("en")


@click.command()
def chat_es() -> None:
    """Same assistant, Spanish interface -- installed as theway_es."""
    _run("es")


if __name__ == "__main__":
    chat()