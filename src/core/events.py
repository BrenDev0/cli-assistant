import sys
from contextvars import ContextVar

import click
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import ANSI

CURRENT_TASK: ContextVar[str | None] = ContextVar("current_task", default=None)

MAX_VALUE_CHARS = 44
TASK_COLORS = ("magenta", "cyan", "green", "yellow", "blue", "bright_magenta")


def _supports_unicode() -> bool:
    try:
        "▸✗·❯◆─".encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


UNICODE = _supports_unicode()
CALL, FAIL, INFO = ("▸", "✗", "·") if UNICODE else (">", "x", ".")

TASK_ACTIVITY: dict[str, str] = {}


def set_activity(task_id: str, activity: str) -> None:
    TASK_ACTIVITY[task_id] = activity


def clear_activity(task_id: str) -> None:
    TASK_ACTIVITY.pop(task_id, None)


def _elide(text: str, limit: int = MAX_VALUE_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = limit // 3
    return f"{text[:head]}...{text[-(limit - head - 3):]}"


def _fmt_value(value) -> str:
    if isinstance(value, str):
        if len(value) <= MAX_VALUE_CHARS:
            return value
        if "/" in value or "\\" in value:
            return _elide(value)
        return f"{len(value):,} chars"

    if isinstance(value, (int, float, bool)) or value is None:
        return str(value)

    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}={_fmt_value(v)}" for k, v in value.items()) + "}"

    if isinstance(value, (list, tuple)):
        return f"[{len(value)} items]"

    return _elide(repr(value))


def _tag() -> str:
    task_id = CURRENT_TASK.get()
    if not task_id:
        return ""
    color = TASK_COLORS[sum(task_id.encode()) % len(TASK_COLORS)]
    return click.style(f"{task_id} ", fg=color)


def _line(glyph: str, glyph_color: str, body: str) -> None:
    text = f"{click.style(glyph, fg=glyph_color)} {_tag()}{body}"
    try:
        # ANSI() so escapes are parsed, not printed literally, under patch_stdout
        print_formatted_text(ANSI(text))
    except Exception:
        # no console (piped, CI, cygwin) -- logging must never take the app down
        click.echo(text)


def format_call(name: str, params: dict) -> str:
    args = ", ".join(f"{key}={_fmt_value(value)}" for key, value in params.items())
    return f"{name}({args})"


def emit_tool_start(name: str, params: dict) -> None:
    task_id = CURRENT_TASK.get()
    if task_id:
        TASK_ACTIVITY[task_id] = name
        return

    args = click.style(", ", fg="bright_black").join(
        f"{click.style(key, fg='bright_black')}"
        f"{click.style('=', fg='bright_black')}"
        f"{_fmt_value(value)}"
        for key, value in params.items()
    )
    body = (
        click.style(name, fg="cyan", bold=True)
        + click.style("(", fg="bright_black")
        + args
        + click.style(")", fg="bright_black")
    )
    _line(CALL, "bright_black", body)


def emit_tool_error(name: str, exc: Exception) -> None:
    task_id = CURRENT_TASK.get()
    if task_id:
        TASK_ACTIVITY[task_id] = f"{name} {FAIL}"
        return

    body = (
        click.style(name, fg="red", bold=True)
        + click.style(f" {type(exc).__name__}: ", fg="red")
        + click.style(_elide(str(exc), 100), fg="bright_black")
    )
    _line(FAIL, "red", body)


def emit_tokens(total: int) -> None:
    _line(INFO, "bright_black", click.style(f"{total:,} tokens", fg="bright_black"))
