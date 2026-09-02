import asyncio
import html

import click
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.patch_stdout import patch_stdout

from src.core.frontend import Decision

from . import ui
from .format import CALL, FAIL, INFO, OK, fmt_value, format_call

TASK_COLORS = ("magenta", "cyan", "green", "yellow", "blue", "bright_magenta")


class CliFrontend:
    def __init__(self):
        self.activity: dict[str, str] = {}
        # serialised: _append_tool_results gathers tool calls concurrently, and two
        # prompts competing for the same terminal would interleave into nonsense
        self._lock = asyncio.Lock()
        self._session: PromptSession | None = None

    def _tag(self, task_id: str | None) -> str:
        if not task_id:
            return ""
        color = TASK_COLORS[sum(task_id.encode()) % len(TASK_COLORS)]
        return click.style(f"{task_id} ", fg=color)

    def _line(self, glyph: str, glyph_color: str, body: str, task_id: str | None) -> None:
        ui.line(f"{click.style(glyph, fg=glyph_color)} {self._tag(task_id)}{body}")

    def tool_started(self, name: str, params: dict, task_id: str | None) -> None:
        if task_id:
            self.activity[task_id] = name
            return

        args = click.style(", ", fg="bright_black").join(
            f"{click.style(key, fg='bright_black')}"
            f"{click.style('=', fg='bright_black')}"
            f"{fmt_value(value)}"
            for key, value in params.items()
        )
        body = (
            click.style(name, fg="cyan", bold=True)
            + click.style("(", fg="bright_black")
            + args
            + click.style(")", fg="bright_black")
        )
        self._line(CALL, "bright_black", body, task_id)

    def tool_failed(self, name: str, exc: Exception, task_id: str | None) -> None:
        if task_id:
            self.activity[task_id] = f"{name} {FAIL}"
            return

        body = (
            click.style(name, fg="red", bold=True)
            + click.style(f" {type(exc).__name__}: ", fg="red")
            + click.style(str(exc)[:100], fg="bright_black")
        )
        self._line(FAIL, "red", body, task_id)

    def tokens(self, total: int, task_id: str | None) -> None:
        self._line(INFO, "bright_black",
                   click.style(f"{total:,} tokens", fg="bright_black"), task_id)

    def task_started(self, task_id: str, description: str) -> None:
        self.activity[task_id] = "starting"

    def task_finished(self, task_id: str, description: str, status: str, detail: str) -> None:
        self.activity.pop(task_id, None)

        glyph, colour = (OK, "green") if status == "done" else (FAIL, "red")
        body = click.style(description, bold=True)
        if detail:
            body += click.style(f" — {detail}", fg="bright_black")

        self._line(glyph, colour, body, task_id)

    async def approve(self, name: str, params: dict) -> Decision:
        if self._session is None:
            self._session = PromptSession()

        summary = format_call(name, params)

        async with self._lock:
            with patch_stdout():
                print_formatted_text(
                    HTML(f"<ansiyellow><b>?</b></ansiyellow> {html.escape(summary)}")
                )
                print_formatted_text(HTML(
                    "  <b><ansibrightcyan>[y]</ansibrightcyan></b> <ansibrightblack>yes</ansibrightblack>"
                    "   <b><ansibrightcyan>[n]</ansibrightcyan></b> <ansibrightblack>no</ansibrightblack>"
                    "   <b><ansibrightcyan>[t]</ansibrightcyan></b> <ansibrightblack>tell it what to do</ansibrightblack>"
                ))

                answer = (await self._session.prompt_async(ui.prompt_message())).strip().lower()

                if answer in ("y", "yes"):
                    return Decision(True)

                if answer in ("t", "tell"):
                    feedback = (await self._session.prompt_async(
                        HTML("<ansibrightblack>what should it do instead?</ansibrightblack> ")
                    )).strip()
                    return Decision(False, feedback)

        return Decision(False)
