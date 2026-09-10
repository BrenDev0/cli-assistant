import difflib

import click

CONTEXT_LINES = 3
MAX_LINES = 40

# dark 256-colour washes rather than the plain red/green backgrounds, which are too loud
# to read white text on. Padded to the full width so a change reads as one solid band.
ADDED_BG = 22
REMOVED_BG = 52


def _hunk_start(header: str) -> tuple[int, int]:
    """First old and new line number out of a '@@ -12,7 +12,9 @@' header."""
    old, new = header.split()[1], header.split()[2]
    return int(old[1:].split(",")[0]), int(new[1:].split(",")[0])


def _band(number: int, marker: str, body: str, background: int, band_width: int) -> str:
    text = f"{number:>6} {marker} {body}".expandtabs(4)
    return click.style(
        text[:band_width].ljust(band_width), fg="bright_white", bg=background
    )


def render(before: str, after: str, band_width: int = 76) -> list[str]:
    changes = list(difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        n=CONTEXT_LINES,
        lineterm="",
    ))

    lines: list[str] = []
    old_no = new_no = 0

    # [2:] drops the --- and +++ filename headers, which name temp paths here anyway
    for change in changes[2:]:
        if change.startswith("@@"):
            old_no, new_no = _hunk_start(change)
            if lines:
                lines.append(click.style(f"{'':>6}   ...", fg="bright_black"))
            continue

        body = change[1:]

        if change.startswith("-"):
            lines.append(_band(old_no, "-", body, REMOVED_BG, band_width))
            old_no += 1
        elif change.startswith("+"):
            lines.append(_band(new_no, "+", body, ADDED_BG, band_width))
            new_no += 1
        else:
            lines.append(
                click.style(f"{new_no:>6}   {body}".expandtabs(4)[:band_width],
                            fg="bright_black")
            )
            old_no += 1
            new_no += 1

    if len(lines) > MAX_LINES:
        hidden = len(lines) - MAX_LINES
        lines = lines[:MAX_LINES]
        lines.append(click.style(f"{'':>6}   ... {hidden} more lines", fg="bright_black"))

    return lines


def summary(before: str, after: str) -> str:
    added = removed = 0

    for change in difflib.unified_diff(
        before.splitlines(), after.splitlines(), n=0, lineterm=""
    ):
        if change.startswith("+") and not change.startswith("+++"):
            added += 1
        elif change.startswith("-") and not change.startswith("---"):
            removed += 1

    parts = []
    if added:
        parts.append(click.style(f"+{added}", fg="green"))
    if removed:
        parts.append(click.style(f"-{removed}", fg="red"))

    return " ".join(parts)
