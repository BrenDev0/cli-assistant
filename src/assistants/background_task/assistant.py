from .prompt import SYSTEM_PROMPT
from src.core.agents.types import Agent


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
        except RuntimeError:
            # invoke() raises this at its iteration cap -- whatever files it wrote before
            # running out are still on disk, so point at them rather than reporting nothing.
            return (
                f"Worker hit its iteration limit before finishing. Partial output may "
                f"exist under {path} -- inspect it before retrying."
            )
        except Exception as exc:
            return (
                f"Worker failed ({type(exc).__name__}: {exc}). "
                f"Check {path} for partial output."
            )

        return f"Files written under {path}\n{report}"
