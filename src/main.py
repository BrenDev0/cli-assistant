from src.core.agents.langchain.agent import LangchainAgent
from src.assistants.orchestrator.config import MODEL, SCHEMAS, TEMPERATURE, API_KEY
from src.assistants.orchestrator.prompt import SYSTEM_PROMPT
from src.tools.skills.tools import list_skills
import asyncio
import click

# Index into `messages` that always holds the freshest skills listing — refreshed every
# turn (not appended) so it never goes stale and never grows the conversation unbounded.
SKILLS_MESSAGE_INDEX = 1


async def chat_loop():
    llm = LangchainAgent(
        model=MODEL,
        api_key=API_KEY,
        temperature=TEMPERATURE,
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

        messages[SKILLS_MESSAGE_INDEX] = (
            "system", f"Available skills:\n{list_skills()}"
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