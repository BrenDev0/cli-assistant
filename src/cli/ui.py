import click
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import ANSI, HTML
from prompt_toolkit.styles import Style

from .format import DOT, INFO, PROMPT, REPLY, RULE, UNICODE

ACCENT = "bright_cyan"

# noreverse strips prompt_toolkit's default reverse-video block, so an idle bar is an
# invisible blank row rather than a solid stripe
STYLE = Style.from_dict({"bottom-toolbar": "noreverse bg:default fg:ansibrightblack"})


def line(text: str) -> None:
    try:
        # ANSI() so escapes are parsed, not printed literally, under patch_stdout
        print_formatted_text(ANSI(text))
    except Exception:
        # no console (piped, CI, cygwin) -- output must never take the app down
        click.echo(text)


def banner(tool_count: int, operation_count: int, model: str) -> None:
    click.echo()
    click.echo("  " + click.style("my_assistant", fg=ACCENT, bold=True))
    click.echo("  " + click.style(RULE * 46, fg="bright_black"))
    click.echo("  " + click.style(
        f"{tool_count} tools {DOT} {operation_count} GHL operations {DOT} {model}",
        fg="bright_black",
    ))
    click.echo("  " + click.style("type 'exit' or 'quit' to leave", fg="bright_black"))
    click.echo()


def prompt_message() -> HTML:
    return HTML(f"<b><ansibrightcyan>{PROMPT}</ansibrightcyan></b> ")


def status_bar(activity: dict[str, str]) -> HTML:
    if not activity:
        return HTML("")

    separator = f" {DOT} "
    parts = separator.join(f"{task_id} {what}" for task_id, what in activity.items())
    return HTML(f"<ansibrightblack>{parts}</ansibrightblack>")


def assistant(text: str) -> None:
    lines = (text or "").strip().splitlines() or [""]
    click.echo(click.style(f"{REPLY} ", fg="bright_magenta") + lines[0])
    for rest in lines[1:]:
        click.echo(f"  {rest}")
    click.echo()


def notice(text: str) -> None:
    click.echo(click.style(f"{INFO} {text}", fg="bright_black"))


def error(text: str) -> None:
    click.echo(click.style(f"! {text}", fg="red"))
