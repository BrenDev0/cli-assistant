import inspect
import asyncio

from src.core import frontend, mode
from src.core.context import CURRENT_TASK
from src.core.frontend import Decision
from src.tools.files.tools import preview_update
from .registry import (
    TOOL_REGISTRY,
    UpdateFile,
    MovePath,
    DeleteFile,
    DeleteDir,
    ClickBrowserElement,
    TypeInBrowser,
    SendWhatsappMessage,
)

# Creating something new is cheap to undo and gets no prompt. Changing or removing
# something that already exists does. MovePath is on this side of the line because it
# unlinks the source; CopyPath only ever adds, so it is not gated.
#
# The browser tools that act rather than look are gated for a stronger reason: they
# reach outside this machine. Opening and reading a page is navigation, but a click, a
# keystroke or a sent message lands somewhere the user cannot take it back from.
REQUIRE_APPROVAL = {
    cls.__name__
    for cls in (
        UpdateFile, MovePath, DeleteFile, DeleteDir,
        ClickBrowserElement, TypeInBrowser, SendWhatsappMessage,
    )
}

DENIED = (
    "The user denied this tool call. Do not retry it. Tell them what you were about to "
    "do and ask how they would like to proceed."
)

REDIRECTED = (
    "The user denied this tool call and gave this instruction instead: {feedback}\n"
    "Do not retry the original call. Follow their instruction."
)


# Approval is a conversation with a person, so it happens one at a time even though the
# work around it is concurrent. A model can ask for three deletions in one message and
# _append_tool_results gathers them, so without this every tool announces itself the
# instant it starts: you get "starting delete A", the question about A, then "starting
# delete B" and "starting delete C" printed on top of it, and your answer to A lands
# underneath questions it was never about. Holding the lock across the announcement AND
# the question keeps each one whole.
_APPROVAL = asyncio.Lock()

PREVIEWS = {"UpdateFile": preview_update}

# What a gated call is about to do, spelled out for the approval prompt. The rail
# item above it elides long arguments to keep its line intact, which is fine for a
# file path and useless for the text of a message being sent on the user's behalf.
DETAILS = {
    "SendWhatsappMessage":
        lambda to, message: f"to {to}{chr(10)}{message}",
    "ClickBrowserElement": lambda text: f"click: {text}",
    "TypeInBrowser": lambda text, then_enter=False: (
        f"type: {text}" + (" (then enter)" if then_enter else "")
    ),
}


def _preview(tool_name: str, params: dict):
    """The diff a gated tool would produce, for the approval prompt to show. Best effort
    -- a preview that cannot be built must never stop the call being offered."""
    return _build(PREVIEWS.get(tool_name), params)


def _detail(tool_name: str, params: dict):
    return _build(DETAILS.get(tool_name), params)


def _build(builder, params: dict):
    if builder is None:
        return None

    try:
        return builder(**params)
    except Exception:
        return None


async def executor(tool_name: str, params: dict):
    if tool_name not in TOOL_REGISTRY.keys():
        raise ValueError(f"tool {tool_name} not in registry")

    tool = TOOL_REGISTRY[tool_name]

    # a background worker has nobody at the keyboard -- prompting there would hang the
    # task behind a question the user never sees
    if tool_name in REQUIRE_APPROVAL and not CURRENT_TASK.get():
        preview = _preview(tool_name, params)

        async with _APPROVAL:
            frontend.tool_started(tool_name, params)

            # shown either way: in auto mode it is the only account of what changed, and
            # watching the edits go by is the point of not being asked about them
            if preview:
                frontend.file_changed(*preview)

            detail = _detail(tool_name, params)
            if detail:
                frontend.tool_detail(detail)

            decision = (
                Decision(True) if mode.auto()
                else await frontend.approve(tool_name, params)
            )

        if not decision.approved:
            return REDIRECTED.format(feedback=decision.feedback) if decision.feedback else DENIED
    else:
        frontend.tool_started(tool_name, params)

    try:
        if inspect.iscoroutinefunction(tool):
            return await tool(**params)

        return await asyncio.to_thread(tool, **params)
    except Exception as exc:
        # re-raised so _append_tool_results can hand the model the error to recover from
        frontend.tool_failed(tool_name, exc)
        raise
