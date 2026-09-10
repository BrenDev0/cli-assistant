import shutil
import time
from html import escape

import click
from prompt_toolkit import print_formatted_text
from prompt_toolkit.application import get_app_or_none
from prompt_toolkit.formatted_text import ANSI, HTML

from src.core.lang import t
from src.core.workspace import assistant_home, project_root

from . import diff as diff_lines
from .format import (
    BOX_BOTTOM_LEFT, BOX_BOTTOM_RIGHT, BOX_H, BOX_TOP_LEFT, BOX_TOP_RIGHT, BOX_V,
    DOT, INFO, MIC, PROMPT, RAIL, RAIL_END, RAIL_ITEM, REPLY, TOOL_COLUMN, UNICODE,
)

ACCENT = "bright_green"
STRUCTURE = "bright_black"

# prompt_toolkit renders HTML, not click styles, so the prompt carries its own names
GREEN = "ansigreen"
GREEN_BRIGHT = "ansibrightgreen"

TITLE = "THE WAY"
BYLINE = "by xplorers"

# 5x5 block letters, drawn rather than pulled from figlet so the banner needs no
# dependency and no font file. Only the letters TITLE actually uses are defined.
GLYPH_HEIGHT = 5
GLYPHS = {
    "T": ("█████", "  █  ", "  █  ", "  █  ", "  █  "),
    "H": ("█   █", "█   █", "█████", "█   █", "█   █"),
    "E": ("█████", "█    ", "████ ", "█    ", "█████"),
    "W": ("█   █", "█   █", "█ █ █", "██ ██", "█   █"),
    "A": (" ███ ", "█   █", "█████", "█   █", "█   █"),
    "Y": ("█   █", " █ █ ", "  █  ", "  █  ", "  █  "),
    " ": (" ", " ", " ", " ", " "),
}

# neon green falling to dark down the rows
LOGO_COLORS = (46, 40, 34, 28, 22)

BYLINE_COLOR = "bright_magenta"


def line(text: str) -> None:
    try:
        # ANSI() so escapes are parsed, not printed literally, under patch_stdout
        print_formatted_text(ANSI(text))
    except Exception:
        # no console (piped, CI, cygwin) -- output must never take the app down
        click.echo(text)


def _short_path(path) -> str:
    home = assistant_home().parent
    text = str(path)
    return f"~{text[len(str(home)):]}" if text.startswith(str(home)) else text


def logo_rows(text: str) -> list[str]:
    """One string per row of block letters. Falls back to the plain spaced name if the
    title gains a letter with no glyph, so changing TITLE can never break startup."""
    if any(character not in GLYPHS for character in text):
        return [" ".join(text)]

    rows = [
        " ".join(GLYPHS[character][row] for character in text)
        for row in range(GLYPH_HEIGHT)
    ]
    return rows if UNICODE else [row.replace("█", "#") for row in rows]


def banner(tool_count: int, ghl_tool_count: int, model: str, session: str) -> None:
    click.echo()

    for text, colour in zip(logo_rows(TITLE), LOGO_COLORS):
        click.echo("   " + click.style(text, fg=colour, bold=True))

    click.echo()
    click.echo("   " + click.style(BYLINE, fg=BYLINE_COLOR, bold=True))
    click.echo()

    fields = (
        (t("banner.model"), model),
        (t("banner.tools"), t("banner.tool_count",
                              local=tool_count, ghl=ghl_tool_count, dot=DOT)),
        (t("banner.session"), session),
        (t("banner.cwd"), _short_path(project_root())),
    )
    label_width = max(len(label) for label, _ in fields) + 1

    for label, value in fields:
        click.echo(
            "   " + click.style(f"{label:<{label_width}}", fg=STRUCTURE)
            + click.style(value, fg="white")
        )

    click.echo()
    click.echo("   " + click.style(t("banner.hint", dot=DOT), fg=STRUCTURE))
    click.echo()


def rule_width() -> int:
    """Interior width of the border, between the two corners. Measured off the real
    terminal rather than width(), whose floor would run it past the edge of a narrow
    window, and kept a column short of the last cell, which wraps some terminals."""
    return max(_columns() - 5, 12)


# The three rows of the input box. Widths are fixed here rather than in the layout so
# the corners, edges and status all land on the same columns: LEFT_WIDTH is exactly
# "  " + edge + " " + glyph + " ".
LEFT_WIDTH = 6


def input_left(glyph: str, colour: str) -> HTML:
    return HTML(f"  <{GREEN}>{BOX_V}</{GREEN}> <b><{colour}>{glyph}</{colour}></b> ")


def prompt_left() -> HTML:
    return input_left(PROMPT, GREEN_BRIGHT)


def listening_left() -> HTML:
    return input_left(MIC, "ansibrightmagenta")


def input_right() -> HTML:
    return HTML(f"<{GREEN}>{BOX_V}</{GREEN}>")


def top_edge() -> HTML:
    edge = BOX_H * rule_width()
    return HTML(f"  <{GREEN}>{BOX_TOP_LEFT}{edge}{BOX_TOP_RIGHT}</{GREEN}>")


TASK_ID_WIDTH = 8
TASK_ELAPSED_WIDTH = 5

# Every column except the description, plus the spaces between them, so what is left
# over is what the description gets. Counted against the border's interior: an edge, a
# space, the id, a space, the description, a space, the activity, a space, the elapsed
# time, a space, the other edge.
TASK_FIXED = 5 + TASK_ID_WIDTH + TOOL_COLUMN + TASK_ELAPSED_WIDTH
TASK_FIXED_NARROW = 4 + TASK_ID_WIDTH + TOOL_COLUMN

MIN_WHAT_WIDTH = 6


def tasks_panel(tasks: dict[str, dict]) -> HTML:
    """A box of its own above the input, listing every running background task and what
    each one is doing. Live because the input box redraws on a timer, so a worker's
    progress shows without it having to interrupt the conversation to say so."""
    interior = rule_width()

    # the elapsed column is the first thing to go: on a narrow terminal knowing which
    # task is running and what it is doing beats knowing how long it has been at it
    timed = interior - TASK_FIXED >= MIN_WHAT_WIDTH
    room = interior - (5 if timed else 4) - TASK_ID_WIDTH
    if timed:
        room -= TASK_ELAPSED_WIDTH

    doing_width = min(TOOL_COLUMN, max(room - MIN_WHAT_WIDTH, 4))
    what_width = max(room - doing_width, MIN_WHAT_WIDTH)

    title = f' {t("tasks.running", count=len(tasks))} '
    header = BOX_H + title + BOX_H * max(interior - 1 - len(title), 0)
    rows = [f"  <{GREEN}>{BOX_TOP_LEFT}{header}{BOX_TOP_RIGHT}</{GREEN}>"]

    for task_id, task in tasks.items():
        # padded before escaping, never after: &lt; is four characters of markup and one
        # column on screen, so padding the escaped text makes the row come out short
        identifier = escape(_clip(task_id, TASK_ID_WIDTH).ljust(TASK_ID_WIDTH))
        what = escape(_clip(task["what"], what_width).ljust(what_width))
        doing = escape(_clip(task["doing"], doing_width).ljust(doing_width))

        elapsed = ""
        if timed:
            seconds = int(time.monotonic() - task["started"])
            spent = f"{seconds}s".rjust(TASK_ELAPSED_WIDTH)
            elapsed = f"<ansibrightblack>{spent}</ansibrightblack> "

        rows.append(
            f"  <{GREEN}>{BOX_V}</{GREEN}> "
            f"<ansibrightblack>{identifier}</ansibrightblack> "
            f"<b>{what}</b> "
            f"<{GREEN_BRIGHT}>{doing}</{GREEN_BRIGHT}> "
            f"{elapsed}"
            f"<{GREEN}>{BOX_V}</{GREEN}>"
        )

    edge = BOX_H * interior
    rows.append(f"  <{GREEN}>{BOX_BOTTOM_LEFT}{edge}{BOX_BOTTOM_RIGHT}</{GREEN}>")

    return HTML("\n".join(rows))


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def bottom_edge(model: str, voice_on: bool, auto_on: bool) -> HTML:
    """The box's bottom border with the model and the modes set into it.

    Both states of each mode are spelled out rather than showing a badge only when one
    is on: an absent word is not something you can read the current mode off at a glance.
    """
    fields = [
        (model, "ansibrightblack"),
        (t("mode.auto"), "ansiyellow") if auto_on
        else (t("mode.approve"), "ansibrightblack"),
        (t("mode.voice"), "ansibrightmagenta") if voice_on
        else (t("mode.text"), "ansibrightblack"),
    ]
    separator = f" {DOT} "

    # a narrow terminal cannot hold every field, and dropping from the end loses the
    # least important rather than overflowing the border
    while len(fields) > 1 and len(_plain(fields, separator)) > rule_width() - 3:
        fields.pop()

    styled = f"<{GREEN}>{separator}</{GREEN}>".join(
        f"<{colour}>{text}</{colour}>" for text, colour in fields
    )

    # 3 accounts for the dash after the corner and the space either side of the status
    fill = max(rule_width() - 3 - len(_plain(fields, separator)), 0)

    return HTML(
        f"  <{GREEN}>{BOX_BOTTOM_LEFT}{BOX_H}</{GREEN}> {styled} "
        f"<{GREEN}>{BOX_H * fill}{BOX_BOTTOM_RIGHT}</{GREEN}>"
    )


def _plain(fields: list[tuple[str, str]], separator: str) -> str:
    return separator.join(text for text, _ in fields)


# everything below goes through line(): during an approval prompt, output is routed
# through patch_stdout, which prints raw escape codes rather than interpreting them
def rail_item(body: str) -> None:
    line("  " + click.style(RAIL_ITEM, fg=STRUCTURE) + " " + body)


def rail_body(body: str) -> None:
    line("  " + click.style(RAIL, fg=STRUCTURE) + " " + body)


def rail_close(body: str) -> None:
    line("  " + click.style(RAIL_END, fg=STRUCTURE) + " " + body)
    line("")


def turn_footer(body: str) -> None:
    line("  " + click.style(body, fg=STRUCTURE))
    line("")


def rail_question(question: str) -> None:
    choices = "   ".join(
        click.style(f"[{key}]", fg=ACCENT, bold=True) + click.style(f" {label}", fg=STRUCTURE)
        for key, label in (("y", t("ask.yes")), ("n", t("ask.no")), ("t", t("ask.tell")))
    )
    rail_body("")
    rail_body(click.style(question, fg="yellow", bold=True) + "   " + choices)


def approval_prompt() -> HTML:
    return HTML(
        f"  <ansibrightblack>{RAIL}</ansibrightblack> "
        f"<b><ansibrightgreen>{PROMPT}</ansibrightgreen></b> "
    )


def feedback_prompt() -> HTML:
    return HTML(
        f"  <ansibrightblack>{RAIL}</ansibrightblack> "
        f"<ansibrightblack>what should it do instead?</ansibrightblack> "
    )


def tool_name(name: str) -> str:
    return click.style(f"{name:<{TOOL_COLUMN}}", fg=ACCENT, bold=True)


# "  " + rail glyph + " " from rail_body, plus the two-space indent added below
RAIL_BODY_PREFIX = 6


def file_changed(path: str, before: str, after: str) -> None:
    lines = diff_lines.render(before, after, width() - RAIL_BODY_PREFIX)
    if not lines:
        return

    counts = diff_lines.summary(before, after)
    rail_item(click.style(f"{path:<{TOOL_COLUMN + 24}}", fg="white") + counts)
    for entry in lines:
        rail_body("  " + entry)


REPLY_INDENT = "    "

# A streamed reply arrives in fragments that split words anywhere, so wrapping holds the
# pending word and the column across calls rather than working a chunk at a time.
#
# It also holds the line: patch_stdout is installed for the whole session now, and its
# proxy only flushes what it is given on a newline. Writing the reply a fragment at a
# time left the diamond and the text sitting in that buffer while the token line, which
# ends in a newline, went out ahead of them. So a line is built here and printed whole.
WRAP = {"line": "", "column": 0, "word": "", "space": False, "first": True}


def _reset_wrap() -> None:
    WRAP.update(line="", column=0, word="", space=False, first=True)


def _columns() -> int:
    """The running app's width when there is one, so the borders drawn as strings agree
    with the layout that sizes itself; shutil otherwise, for plain printed output."""
    app = get_app_or_none()
    if app is not None:
        return app.output.get_size().columns

    return shutil.get_terminal_size((80, 24)).columns


def width() -> int:
    """Printable width for wrapped text. Floored, because wrapping a reply into a
    20-column ribbon is worse than letting the terminal soft-wrap it."""
    return max(_columns() - 2, 40)


def _open_line() -> None:
    """Start a line: the diamond for the first one, a matching indent for the rest.
    Both are four columns wide, so wrapped text stays under the text above it."""
    if WRAP["first"]:
        WRAP["first"] = False
        WRAP["line"] = "  " + click.style(f"{REPLY} ", fg="bright_magenta")
    else:
        WRAP["line"] = REPLY_INDENT

    WRAP["column"] = 4
    WRAP["space"] = False


def _break_line() -> None:
    line(WRAP["line"])
    WRAP["line"] = ""
    WRAP["column"] = 0


def _flush_word() -> None:
    word = WRAP["word"]
    if not word:
        return

    WRAP["word"] = ""

    if not WRAP["line"]:
        _open_line()

    gap = 1 if WRAP["space"] else 0

    if WRAP["column"] + gap + len(word) > width():
        _break_line()
        _open_line()
        gap = 0

    WRAP["line"] += (" " * gap) + word
    WRAP["column"] += gap + len(word)
    WRAP["space"] = False


def reply_chunk(text: str, first: bool) -> None:
    if first:
        _reset_wrap()

    for character in text:
        if not character.isspace():
            WRAP["word"] += character
            continue

        _flush_word()

        if character == "\n":
            # an empty buffer here is a blank line in the reply, and printing it keeps
            # the paragraph break the model wrote
            if not WRAP["line"] and not WRAP["first"]:
                line("")
            else:
                _break_line()
        else:
            WRAP["space"] = True


def reply_end() -> None:
    _flush_word()

    if WRAP["line"]:
        _break_line()

    _reset_wrap()


def echo_input(text: str) -> None:
    """What the erased box leaves behind: the line as typed, unframed, so a finished
    turn is one plain row of scrollback."""
    line("  " + click.style(f"{PROMPT} ", fg=ACCENT, bold=True) + text)


def heard(text: str) -> None:
    line("  " + click.style(f"{MIC} ", fg="bright_magenta") + text)


def notice(text: str) -> None:
    line("  " + click.style(f"{INFO} {text}", fg=STRUCTURE))


def error(text: str) -> None:
    line("  " + click.style(f"! {text}", fg="red"))
