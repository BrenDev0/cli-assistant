import asyncio
import time
from typing import Awaitable, Callable

import click

from src.core.frontend import Decision
from src.core.lang import STRINGS, t

from . import ui
from .format import DOT, FAIL, OK, TOOL_COLUMN, fmt_value

# which tools have a question of their own; anything else gets the generic one
ALL_ASKS = {key for key in STRINGS["en"] if key.startswith("ask.")}

# both languages accepted whichever the app was started in, because the keys are
# what people actually press and "s" is as natural to reach for as "y"
YES = {"y", "yes", "s", "si", "sí"}
TELL = {"t", "tell", "d", "decir"}

TASK_COLORS = ("magenta", "cyan", "green", "yellow", "blue", "bright_magenta")


class CliFrontend:
    def __init__(self):
        # what the panel above the input box shows: one entry per running background
        # task, holding its description, whatever it is doing right now, and when it
        # started. Kept here rather than read off TASKS so the panel needs no lock and
        # no knowledge of the worker's internals.
        self.tasks: dict[str, dict] = {}
        # set per turn by the chat loop when voice is on, so spoken output can start on
        # the first finished sentence instead of the last token
        self.on_reply: Callable[[str], None] | None = None
        # set by the chat loop to the input box's reader, so an approval is answered in
        # the same box everything else is typed into
        self.read_line: Callable[[], Awaitable[str | None]] | None = None
        # kept here rather than read off the agent: the box's status is built once, and
        # /model replaces the agent object it would otherwise be holding on to
        self.model = ""
        self._replying = False
        self._rail_count = 0
        self._turn_start = 0.0
        # serialised: _append_tool_results gathers tool calls concurrently, and two
        # questions competing for the same input would interleave into nonsense
        self._lock = asyncio.Lock()

    def _doing(self, task_id: str, what: str) -> None:
        """A tool call from inside a worker. The task may not be registered yet if the
        worker got going before task_started landed, so the entry is created either way."""
        entry = self.tasks.setdefault(
            task_id, {"what": task_id, "doing": "", "started": time.monotonic()}
        )
        entry["doing"] = what

    def _tag(self, task_id: str | None) -> str:
        if not task_id:
            return ""
        color = TASK_COLORS[sum(task_id.encode()) % len(TASK_COLORS)]
        return click.style(f"{task_id} ", fg=color)

    def _line(self, glyph: str, glyph_color: str, body: str, task_id: str | None) -> None:
        ui.line(f"{click.style(glyph, fg=glyph_color)} {self._tag(task_id)}{body}")

    def tool_started(self, name: str, params: dict, task_id: str | None) -> None:
        if task_id:
            self._doing(task_id, name)
            return

        ui.rail_item(ui.tool_name(name) + self._args(params))
        self._rail_count += 1

    def _args(self, params: dict) -> str:
        """Styled key=value pairs, cut off before they wrap and break the rail."""
        budget = ui.width() - TOOL_COLUMN - 6
        pieces = []
        used = 0

        for key, value in params.items():
            plain = f"{key}={fmt_value(value)}"
            if used + len(plain) > budget:
                pieces.append(click.style("...", fg="bright_black"))
                break

            pieces.append(
                click.style(f"{key}=", fg="bright_black") + fmt_value(value)
            )
            used += len(plain) + 2

        return click.style(", ", fg="bright_black").join(pieces)

    def tool_failed(self, name: str, exc: Exception, task_id: str | None) -> None:
        if task_id:
            # clipped here rather than in the panel, so the marker survives the column
            # instead of being the character that gets cut
            self._doing(task_id, f"{name[:TOOL_COLUMN - 2]} {FAIL}")
            return

        ui.rail_item(
            click.style(f"{name:<{TOOL_COLUMN}}", fg="red", bold=True)
            + click.style(f"{FAIL} {type(exc).__name__}: ", fg="red")
            + click.style(str(exc)[:100], fg="bright_black")
        )
        self._rail_count += 1

    def begin_turn(self) -> None:
        self._turn_start = time.perf_counter()
        self._rail_count = 0

    def tokens(self, total: int, task_id: str | None) -> None:
        if task_id:
            return

        elapsed = time.perf_counter() - self._turn_start
        ui.turn_footer(f"{total:,} tokens {DOT} {elapsed:.1f}s")

    def reply_chunk(self, text: str, task_id: str | None) -> None:
        if task_id:
            return

        # the rail carried this turn's tool calls; the reply is what it was leading to
        if not self._replying and self._rail_count:
            elapsed = time.perf_counter() - self._turn_start
            ui.rail_close(f"{self._rail_count} tool calls {DOT} {elapsed:.1f}s")
            self._rail_count = 0

        ui.reply_chunk(text, first=not self._replying)
        self._replying = True

        if self.on_reply:
            self.on_reply(text)

    def reply_finished(self, task_id: str | None) -> None:
        if task_id or not self._replying:
            return

        self._replying = False
        ui.reply_end()

    def file_changed(self, path: str, before: str, after: str, task_id: str | None) -> None:
        if task_id:
            return

        ui.file_changed(path, before, after)

    def tool_detail(self, text: str, task_id: str | None) -> None:
        if task_id:
            return

        for row in text.split(chr(10)):
            ui.rail_body(click.style(row, fg='white'))

    def task_started(self, task_id: str, description: str) -> None:
        self.tasks[task_id] = {
            "what": description,
            "doing": "starting",
            "started": time.monotonic(),
        }

    def task_finished(self, task_id: str, description: str, status: str, detail: str) -> None:
        self.tasks.pop(task_id, None)

        glyph, colour = (OK, "green") if status == "done" else (FAIL, "red")
        body = click.style(description, bold=True)
        if detail:
            body += click.style(f" — {detail}", fg="bright_black")

        self._line(glyph, colour, body, task_id)

    async def approve(self, name: str, params: dict) -> Decision:
        # answered in the input box at the bottom, not a prompt of its own: only one
        # application can hold the terminal, and the box holds it for the whole session
        if self.read_line is None:
            return Decision(False, "There is no one at the keyboard to approve this.")

        async with self._lock:
            # the rail item and the diff above already said what this is, so the
            # question only has to ask -- repeating the call read as a second one
            question = f"ask.{name}"
            ui.rail_question(t(question if question in ALL_ASKS else "ask.default"))

            answer = ((await self.read_line()) or "").strip().lower()

            if answer in YES:
                return Decision(True)

            if answer in TELL:
                ui.rail_body(click.style(t("ask.instead"), fg="bright_black"))
                feedback = ((await self.read_line()) or "").strip()
                return Decision(False, feedback)

        return Decision(False)
