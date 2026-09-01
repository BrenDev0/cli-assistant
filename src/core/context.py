from contextvars import ContextVar

# Set inside a background task's own coroutine, never before create_task(): asyncio copies
# the current context at creation, so setting it earlier would tag the caller's work too.
CURRENT_TASK: ContextVar[str | None] = ContextVar("current_task", default=None)
