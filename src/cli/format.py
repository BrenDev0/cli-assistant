import sys

MAX_VALUE_CHARS = 44


def _supports_unicode() -> bool:
    try:
        "▸✗·❯◆─".encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


UNICODE = _supports_unicode()
CALL, FAIL, INFO = ("▸", "✗", "·") if UNICODE else (">", "x", ".")
PROMPT, REPLY, RULE = ("❯", "◆", "─") if UNICODE else (">", "*", "-")
DOT = "·" if UNICODE else "|"


def elide(text: str, limit: int = MAX_VALUE_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = limit // 3
    return f"{text[:head]}...{text[-(limit - head - 3):]}"


def fmt_value(value) -> str:
    if isinstance(value, str):
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
