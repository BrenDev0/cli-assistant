from src.agents.langchain.assistant import LangchainAssistant
from src.agents.tools import ReadFile, SearchFile, CreateDir, CreateFile
import asyncio
from ..settings import settings
import click

async def chat_loop():
    tools = [
        SearchFile,
        ReadFile, 
        CreateFile,
        CreateDir
    ]
    llm = LangchainAssistant(
        model="gpt-4o",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.0,
        tools=tools
    )

    messages = [
        (
            "system", "You are a helpful assistant and will help the user with thier requests"
        ),
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