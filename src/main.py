from src.core.agents.langchain.agent import LangchainAgent
from src.assistants.orchestrator.config import MODEL, SCHEMAS, TEMPERATURE, API_KEY
from src.assistants.orchestrator.prompt import SYSTEM_PROMPT
from src.tools.skills.tools import list_skills
import asyncio
import click
from src.tools.ghl.tools import initialize_ghl_operations, catalog_text
from src.tools.background.tools import drain_completed, _RUNNING
from src.tools.ghl.tools import GHL
from src.core import ui
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

SKILLS_MESSAGE_INDEX = 2


async def chat_loop():
    llm = LangchainAgent(
        model=MODEL,
        api_key=API_KEY,
        temperature=TEMPERATURE,
        tools=SCHEMAS
    )

    await initialize_ghl_operations()

    messages = [
        ("system", SYSTEM_PROMPT),
        ("system", f"Available GoHighLevel operations:\n{catalog_text()}"),
        ("system", ""),  # placeholder, filled in each turn below
    ]

    ui.banner(len(SCHEMAS), len(GHL["catalog"]), MODEL)

    # refresh_interval so the status bar ticks while you sit still; prompt_toolkit
    # otherwise only redraws on keystrokes
    session = PromptSession(
        bottom_toolbar=ui.status_bar,
        style=ui.STYLE,
        refresh_interval=0.5,
    )

    while True:
        try:
            # patch_stdout() redirects writes from background tasks above the prompt line
            # and redraws it, so a print landing mid-typing no longer eats your input.
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

        messages[SKILLS_MESSAGE_INDEX] = (
            "system", f"Available skills:\n{list_skills()}"
        )
        messages.append(("user", user_input))

    
        if news := drain_completed():
            messages.append(("system",
            f"A background task finished. The result below is the worker's complete output. "
            f"Relay it to the user as-is; do not extend, embellish, or substitute your own "
            f"content. If the result does not contain the requested deliverable, say so plainly.\n{news}"
        ))

        try:
            result = await llm.invoke(messages)
        except Exception as e:
            ui.error(f"{type(e).__name__}: {e}")
            continue
        ui.assistant(result)


@click.command()
def chat():
    # Ctrl+C lands on the main thread, which is inside the event loop — not inside the
    # coroutine's try/except, since click.prompt now runs in a worker thread.
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        ui.notice("goodbye")


if __name__ == "__main__":
    chat()