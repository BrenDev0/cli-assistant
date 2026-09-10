from typing import NamedTuple, Protocol, runtime_checkable

from src.core.context import CURRENT_TASK


class Decision(NamedTuple):
    approved: bool
    feedback: str = ""


@runtime_checkable
class Frontend(Protocol):
    """How the core reports progress and asks for permission, without knowing whether a
    terminal, a browser, or nothing at all is on the other end."""

    def tool_started(self, name: str, params: dict, task_id: str | None) -> None: ...
    def tool_failed(self, name: str, exc: Exception, task_id: str | None) -> None: ...
    def tokens(self, total: int, task_id: str | None) -> None: ...
    def reply_chunk(self, text: str, task_id: str | None) -> None: ...
    def reply_finished(self, task_id: str | None) -> None: ...
    def file_changed(self, path: str, before: str, after: str, task_id: str | None) -> None: ...
    def task_started(self, task_id: str, description: str) -> None: ...
    def task_finished(self, task_id: str, description: str, status: str, detail: str) -> None: ...
    async def approve(self, name: str, params: dict) -> Decision: ...


class HeadlessFrontend:
    """Silent, and approves everything. The default so imports and tests work with no
    frontend installed -- callers that need a human gate must install one."""

    def tool_started(self, name: str, params: dict, task_id: str | None) -> None: ...
    def tool_failed(self, name: str, exc: Exception, task_id: str | None) -> None: ...
    def tokens(self, total: int, task_id: str | None) -> None: ...
    def reply_chunk(self, text: str, task_id: str | None) -> None: ...
    def reply_finished(self, task_id: str | None) -> None: ...
    def file_changed(self, path: str, before: str, after: str, task_id: str | None) -> None: ...
    def task_started(self, task_id: str, description: str) -> None: ...
    def task_finished(self, task_id: str, description: str, status: str, detail: str) -> None: ...

    async def approve(self, name: str, params: dict) -> Decision:
        return Decision(True)


_active: Frontend = HeadlessFrontend()


def use(frontend: Frontend) -> None:
    global _active
    _active = frontend


def tool_started(name: str, params: dict) -> None:
    _active.tool_started(name, params, CURRENT_TASK.get())


def tool_failed(name: str, exc: Exception) -> None:
    _active.tool_failed(name, exc, CURRENT_TASK.get())


def tokens(total: int) -> None:
    _active.tokens(total, CURRENT_TASK.get())


def reply_chunk(text: str) -> None:
    _active.reply_chunk(text, CURRENT_TASK.get())


def reply_finished() -> None:
    _active.reply_finished(CURRENT_TASK.get())


def file_changed(path: str, before: str, after: str) -> None:
    _active.file_changed(path, before, after, CURRENT_TASK.get())


def task_started(task_id: str, description: str) -> None:
    _active.task_started(task_id, description)


def task_finished(task_id: str, description: str, status: str, detail: str = "") -> None:
    _active.task_finished(task_id, description, status, detail)


async def approve(name: str, params: dict) -> Decision:
    return await _active.approve(name, params)
