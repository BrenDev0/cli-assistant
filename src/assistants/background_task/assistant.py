from pathlib import Path

from .prompt import SYSTEM_PROMPT
from src.core.agents.types import Agent

from src.core.workspace import tasks_dir

# work() reports failure by returning, not raising, so the coroutine completes normally.
# _finish looks for this prefix to tell a failed run from a successful one.
FAILURE_MARKER = "TASK FAILED"


class BackgroundTaskAssistant:
    """Delegates to an injected Agent with the orchestrator's tools minus the background
    ones, and turns a (task_folder, instructions) request into finished files under
    .my_assistant/tasks/<task_folder>/ plus a short report of what it produced.

    Its return value is a *report*, not a payload: the artifacts stay on disk so they
    never round-trip through the orchestrator's context."""

    def __init__(self, agent: Agent):
        self._agent = agent

    async def work(self, task_folder: str, instructions: str) -> str:
        path = f".my_assistant/tasks/{task_folder}/"

        messages = [
            ("system", SYSTEM_PROMPT),
            ("user", f"Task folder: {path}\n\nTask:\n{instructions}"),
        ]

        try:
            report = await self._agent.invoke(messages)
        except RuntimeError as exc:
            return (
                f"{FAILURE_MARKER} — the worker ran out of steps before finishing ({exc}). "
                f"{self._produced(task_folder)} Tell the user plainly that it did not "
                f"complete; do not describe it as finished."
            )
        except Exception as exc:
            return (
                f"{FAILURE_MARKER} — {type(exc).__name__}: {exc}. "
                f"{self._produced(task_folder)} Tell the user plainly that it did not "
                f"complete; do not describe it as finished."
            )

        # the worker's own report is not evidence a file exists -- check the disk
        return f"{self._produced(task_folder)}\n{report}"

    def _produced(self, task_folder: str) -> str:
        directory = tasks_dir() / task_folder
        files = sorted(p.name for p in directory.rglob("*") if p.is_file()) if directory.exists() else []

        if not files:
            return f"NO FILES were written to .my_assistant/tasks/{task_folder}/."

        return f"Files in .my_assistant/tasks/{task_folder}/: {', '.join(files)}."
