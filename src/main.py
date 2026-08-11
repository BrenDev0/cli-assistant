from src.agents.langchain.assistant import LangchainAssistant
from src.tools.registry import SCHEMAS
from src.tools.foundations.tools import list_foundations
import asyncio
from .settings import settings
import click

SYSTEM_PROMPT = (
    "You are a helpful assistant and will help the user with thier requests. "
    "When asked to create, build, or update something concrete — a file, a folder, a "
    "foundation — you must actually perform it using the available tools. Never just "
    "describe or paste the content in your reply without also creating it via a tool call; "
    "a request to 'create'/'build'/'make' something is not satisfied by showing it in chat. "
    "Before each of your turns you will be shown the current list of available foundations "
    "(reusable, previously-authored instructions for specific tasks) in a separate system "
    "message. If one of them matches the user's request, read_file its FOUNDATION.md and "
    "follow its instructions before acting."
)

# Index into `messages` that always holds the freshest foundations listing — refreshed every
# turn (not appended) so it never goes stale and never grows the conversation unbounded.
FOUNDATIONS_MESSAGE_INDEX = 1


async def chat_loop():
    llm = LangchainAssistant(
        model="gpt-4o",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.0,
        tools=SCHEMAS
    )

    messages = [
        ("system", SYSTEM_PROMPT),
        ("system", ""),  # placeholder, filled in each turn below
    ]

    click.echo("Assistant ready. Type 'exit', or 'quit' to stop\n")

    while True:
        try:
            user_input = click.prompt("You", default="", show_default=False).strip()
        except (KeyboardInterrupt, EOFError):
            click.echo("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            click.echo("Good bye")
            break

        messages[FOUNDATIONS_MESSAGE_INDEX] = (
            "system", f"Available foundations:\n{list_foundations()}"
        )
        messages.append(("user", user_input))

        try:
            result = await llm.invoke(messages)
        except Exception as e:
            click.echo(click.style(text=f"Error {e}", fg='red'))
            continue
        click.echo(click.style(text=f"Assistant: {result}\n", italic=True, fg='cyan'))


@click.command()
def chat():
    asyncio.run(chat_loop())


if __name__ == "__main__":
    chat()