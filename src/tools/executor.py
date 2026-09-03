import inspect
import asyncio

from src.core import frontend
from src.core.context import CURRENT_TASK
from .registry import (
    TOOL_REGISTRY,
    UpdateFile,
    MovePath,
    DeleteFile,
    DeleteDir,
)

# Creating something new is cheap to undo and gets no prompt. Changing or removing
# something that already exists does. MovePath is on this side of the line because it
# unlinks the source; CopyPath only ever adds, so it is not gated.
REQUIRE_APPROVAL = {
    cls.__name__
    for cls in (UpdateFile, MovePath, DeleteFile, DeleteDir)
}

DENIED = (
    "The user denied this tool call. Do not retry it. Tell them what you were about to "
    "do and ask how they would like to proceed."
)

REDIRECTED = (
    "The user denied this tool call and gave this instruction instead: {feedback}\n"
    "Do not retry the original call. Follow their instruction."
)


async def executor(tool_name: str, params: dict):
    if tool_name not in TOOL_REGISTRY.keys():
        raise ValueError(f"tool {tool_name} not in registry")

    tool = TOOL_REGISTRY[tool_name]
    frontend.tool_started(tool_name, params)

    # a background worker has nobody at the keyboard -- prompting there would hang the
    # task behind a question the user never sees
    if tool_name in REQUIRE_APPROVAL and not CURRENT_TASK.get():
        decision = await frontend.approve(tool_name, params)
        if not decision.approved:
            return REDIRECTED.format(feedback=decision.feedback) if decision.feedback else DENIED

    try:
        if inspect.iscoroutinefunction(tool):
            return await tool(**params)

        return await asyncio.to_thread(tool, **params)
    except Exception as exc:
        # re-raised so _append_tool_results can hand the model the error to recover from
        frontend.tool_failed(tool_name, exc)
        raise
