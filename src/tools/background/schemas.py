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
    deliver_to: str | None = Field(
        default=None,
        description=(
            "Folder in the user's project where the finished files should be delivered, "
            "for example 'reports' or 'ghl_client_report'. The worker always does its "
            "work in .my_assistant/tasks/, which the user cannot easily reach; whatever "
            "you name here is copied there automatically the moment the task succeeds, "
            "so the deliverable lands somewhere the user can actually open. ASK the user "
            "which folder they want before starting any task that produces files they "
            "will want to see, and pass their answer here. Leave it unset only for work "
            "with no deliverable."
        ),
    )


class CheckBackgroundTask(BaseModel):
    """Check the status and result of a background task by its id"""
    task_id: str = Field(description="Task id returned by StartBackgroundTask, for example '3f2a1b9c'")


class DeliverTask(BaseModel):
    """Copy a finished background task's files out of .my_assistant/tasks/ and into a
    folder in the user's project, where they can actually open them.

    Use this whenever the user asks for a task's output to be moved, copied, or put
    somewhere -- it looks the task folder up by id, so you never have to retype the long
    generated folder name, and it copies the bytes on disk rather than re-creating files
    from content you would have to remember. Never satisfy 'move the files' by reading
    them and calling create_file."""
    task_id: str = Field(description="Task id from StartBackgroundTask or the completion notice, for example '3f2a1b9c'")
    destination: str = Field(description="Folder in the current project to copy the files into, for example 'ghl_client_report'. Created if it does not exist.")
