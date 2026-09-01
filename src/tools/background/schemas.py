from pydantic import BaseModel, Field


class StartBackgroundTask(BaseModel):
    """Run a long-running task in the background so the conversation can continue.

    Use this for work that spans many operations or would take more than a few
    seconds -- bulk lookups, audits, multi-step research. Do not use it for work
    the user is waiting on right now; answer those directly instead.
    """
    description: str = Field(description="Short label for the task, shown to the user while it runs, for example 'Audit all contacts for missing email addresses'")
    instructions: str = Field(
    description=(
        "Complete, self-contained instructions for the background worker. The worker "
        "starts with a fresh context and cannot see this conversation, so restate "
        "everything: the subject and scope, plus any constraint established earlier -- "
        "the language to write in, tone, target audience, output format, length, and "
        "which files or records to use. If the user has been writing in a language "
        "other than English, state that language explicitly."
    )
)


class CheckBackgroundTask(BaseModel):
    """Check the status and result of a background task by its id"""
    task_id: str = Field(description="Task id returned by StartBackgroundTask, for example '3f2a1b9c'")
