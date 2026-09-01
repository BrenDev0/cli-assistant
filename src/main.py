from src.core.agents.langchain.agent import LangchainAgent
from src.assistants.orchestrator.config import MODEL, SCHEMAS, TEMPERATURE, API_KEY
from src.assistants.orchestrator.prompt import SYSTEM_PROMPT
from src.tools.skills.tools import list_skills
import asyncio
import click
from src.tools.ghl.tools import initialize_ghl_operations, catalog_text
from src.tools.background.tools import drain_completed, _RUNNING

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

    click.echo("Assistant ready. Type 'exit', or 'quit' to stop\n")

    while True:
        try:
            user_input = (await asyncio.to_thread(
                click.prompt, "You", default="", show_default=False
            )).strip()
            
        except (KeyboardInterrupt, EOFError):
            click.echo("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            if _RUNNING:
                click.echo(f"Warning: {len(_RUNNING)} background task(s) still running — abandoning them.")
            click.echo("Good bye")
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
            click.echo(click.style(text=f"Error {e}", fg='red'))
            continue
        click.echo(click.style(text=f"Assistant: {result}\n", italic=True, fg='cyan'))


@click.command()
def chat():
    # Ctrl+C lands on the main thread, which is inside the event loop — not inside the
    # coroutine's try/except, since click.prompt now runs in a worker thread.
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        click.echo("\nGoodbye!")


if __name__ == "__main__":
    chat()