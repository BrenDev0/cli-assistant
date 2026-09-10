import sys

MAX_VALUE_CHARS = 44


def _supports_unicode() -> bool:
    try:
        # every glyph the ui actually draws, the banner's block letter included
        "▸✗·❯◆◉│├╰╭╮╯─█".encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


UNICODE = _supports_unicode()
CALL, FAIL, INFO = ("▸", "✗", "·") if UNICODE else (">", "x", ".")
OK = "✓" if UNICODE else "+"
PROMPT, REPLY = ("❯", "◆") if UNICODE else (">", "*")
MIC = "◉" if UNICODE else "o"

# the rail down the left of a turn: every tool call hangs off it and the token line closes it
RAIL, RAIL_ITEM, RAIL_END = ("│", "├─", "╰─") if UNICODE else ("|", "|-", "\\-")

# the border around the input, whose bottom edge carries the status
BOX_TOP_LEFT, BOX_TOP_RIGHT = ("╭", "╮") if UNICODE else ("+", "+")
BOX_BOTTOM_LEFT, BOX_BOTTOM_RIGHT = ("╰", "╯") if UNICODE else ("+", "+")
BOX_H, BOX_V = ("─", "│") if UNICODE else ("-", "|")

TOOL_COLUMN = 14
DOT = "·" if UNICODE else "|"


def elide(text: str, limit: int = MAX_VALUE_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = limit // 3
    return f"{text[:head]}...{text[-(limit - head - 3):]}"


def fmt_value(value) -> str:
    if isinstance(value, str):
        # checked before the length test: a short multi-line value would still break the
        # line it is printed on, and file content is full of slashes, so the path branch
        # below was eliding whole html documents down to their last few lines
        if "\n" in value or "\r" in value:
            return f"{len(value):,} chars"
        if len(value) <= MAX_VALUE_CHARS:
            return value
        if "/" in value or "\\" in value:
            return elide(value)
        return f"{len(value):,} chars"

    if isinstance(value, (int, float, bool)) or value is None:
        return str(value)

    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}={fmt_value(v)}" for k, v in value.items()) + "}"

    if isinstance(value, (list, tuple)):
        return f"[{len(value)} items]"

    return elide(repr(value))


def format_call(name: str, params: dict) -> str:
    args = ", ".join(f"{key}={fmt_value(value)}" for key, value in params.items())
    return f"{name}({args})"
