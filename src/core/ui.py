import asyncio
import html
from typing import NamedTuple

import click
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.patch_stdout import patch_stdout

from prompt_toolkit.styles import Style

from src.core.events import CALL, INFO, TASK_ACTIVITY, UNICODE

PROMPT, REPLY, RULE = ("❯", "◆", "─") if UNICODE else (">", "*", "-")

ACCENT = "bright_cyan"


def banner(tool_count: int, operation_count: int, model: str) -> None:
    click.echo()
    click.echo("  " + click.style("my_assistant", fg=ACCENT, bold=True))
    click.echo("  " + click.style(RULE * 46, fg="bright_black"))
    click.echo(
        "  "
        + click.style(
            f"{tool_count} tools {'·' if UNICODE else '|'} "
            f"{operation_count} GHL operations {'·' if UNICODE else '|'} {model}",
            fg="bright_black",
        )
    )
    click.echo("  " + click.style("type 'exit' or 'quit' to leave", fg="bright_black"))
    click.echo()


def prompt_message() -> HTML:
    return HTML(f"<b><ansibrightcyan>{PROMPT}</ansibrightcyan></b> ")


# noreverse strips prompt_toolkit's default reverse-video block, so an idle bar is
# an invisible blank row rather than a solid stripe
STYLE = Style.from_dict({"bottom-toolbar": "noreverse bg:default fg:ansibrightblack"})


def status_bar() -> HTML:
    if not TASK_ACTIVITY:
        return HTML("")

    separator = " · " if UNICODE else " | "
    parts = separator.join(
        f"{task_id} {activity}" for task_id, activity in TASK_ACTIVITY.items()
    )
    return HTML(f"<ansibrightblack>{CALL} {parts}</ansibrightblack>")


def assistant(text: str) -> None:
    lines = (text or "").strip().splitlines() or [""]
    click.echo(click.style(f"{REPLY} ", fg="bright_magenta") + lines[0])
    for line in lines[1:]:
        click.echo(f"  {line}")
    click.echo()


# serialised: _append_tool_results gathers tool calls concurrently, and two prompts
# competing for the same terminal would interleave into nonsense
_APPROVAL_LOCK = asyncio.Lock()
_APPROVAL_SESSION: PromptSession | None = None


class Decision(NamedTuple):
    approved: bool
    feedback: str = ""


async def approve(summary: str) -> Decision:
    global _APPROVAL_SESSION
    if _APPROVAL_SESSION is None:
        _APPROVAL_SESSION = PromptSession()

    async with _APPROVAL_LOCK:
        with patch_stdout():
            print_formatted_text(
                HTML(f"<ansiyellow><b>?</b></ansiyellow> {html.escape(summary)}")
            )
            print_formatted_text(HTML(
                "  <b><ansibrightcyan>[y]</ansibrightcyan></b> <ansibrightblack>yes</ansibrightblack>"
                "   <b><ansibrightcyan>[n]</ansibrightcyan></b> <ansibrightblack>no</ansibrightblack>"
                "   <b><ansibrightcyan>[t]</ansibrightcyan></b> <ansibrightblack>tell it what to do</ansibrightblack>"
            ))

            answer = (await _APPROVAL_SESSION.prompt_async(prompt_message())).strip().lower()

            if answer in ("y", "yes"):
                return Decision(True)

            if answer in ("t", "tell"):
                feedback = (await _APPROVAL_SESSION.prompt_async(
                    HTML("<ansibrightblack>what should it do instead?</ansibrightblack> ")
                )).strip()
                return Decision(False, feedback)

    return Decision(False)


def notice(text: str) -> None:
    click.echo(click.style(f"{INFO} {text}", fg="bright_black"))


def error(text: str) -> None:
    click.echo(click.style(f"! {text}", fg="red"))
