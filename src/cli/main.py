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
from src.core import frontend
from src.cli import commands, ui
from src.cli.frontend import CliFrontend
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

# Holds everything that changes turn to turn — the clock and the skills listing.
# Kept after the static system prompt and GHL catalog so those stay a cacheable prefix,
# and rewritten rather than appended so it never goes stale or grows the conversation.
CONTEXT_MESSAGE_INDEX = 2


def context_message() -> str:
    now = datetime.now().astimezone()
    return (
        f"Current date and time: {now:%A, %Y-%m-%d %H:%M} {now.tzname()} (UTC{now:%z}). "
        f"Treat this as the present moment when interpreting relative dates.\n\n"
        f"Available skills:\n{list_skills()}"
    )


async def chat_loop():
    cli = CliFrontend()
    frontend.use(cli)

    llm = LangchainAgent(
        model=MODEL,
        temperature=TEMPERATURE,
        tools=SCHEMAS
    )

    await initialize_ghl_operations()

    try:
        initialize_web_client()
    except RuntimeError as exc:
        ui.error(f"web tools unavailable — {exc}")

    messages = [
        ("system", SYSTEM_PROMPT),
        ("system", f"Available GoHighLevel operations:\n{catalog_text()}"),
        ("system", ""),  # placeholder, filled in each turn below
    ]

    start_session()

    ui.banner(len(SCHEMAS), len(GHL["catalog"]), MODEL)

   
    session = PromptSession(
        bottom_toolbar=lambda: ui.status_bar(cli.activity),
        style=ui.STYLE,
        refresh_interval=0.5,
    )

    while True:
        try:
           
            with patch_stdout():
                user_input = (await session.prompt_async(ui.prompt_message())).strip()

        except (KeyboardInterrupt, EOFError):
            ui.notice("goodbye")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            if _RUNNING:
                ui.error(f"{len(_RUNNING)} background task(s) still running — abandoning them")
            ui.notice("goodbye")
            break

        if user_input.startswith("/"):
            messages, llm = await commands.handle(user_input, messages, llm)
            continue

        messages[CONTEXT_MESSAGE_INDEX] = ("system", context_message())
        messages.append(("user", user_input))
        record("user", user_input)

    
        if news := drain_completed():
            messages.append(("system",
            f"A background task finished. The result below is the worker's complete output. "
            f"Relay it to the user as-is; do not extend, embellish, or substitute your own "
            f"content. If the result does not contain the requested deliverable, say so plainly.\n{news}"
        ))

        messages = commands.trim_history(messages)

        try:
            result = await llm.invoke(messages)
        except Exception as e:
            ui.error(f"{type(e).__name__}: {e}")
            continue

        record("assistant", result)
        ui.assistant(result)


@click.command()
def chat():

    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        ui.notice("goodbye")


if __name__ == "__main__":
    chat()