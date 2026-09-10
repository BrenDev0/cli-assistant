from uuid import uuid4
import asyncio
import re
import shutil

from src.core import frontend
from src.core.context import CURRENT_TASK

TASKS: dict[str, dict] = {}
_RUNNING: set[asyncio.Task] = set()


def _slug(text: str, limit: int = 40) -> str:
    """Kebab-case folder name from a task description."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned[:limit].rstrip("-") or "task"


def deliver(task_folder: str, destination: str) -> str:
    """Copy a task's output into a folder the user can reach.

    Copy, not move: the task folder stays intact as the record of what was produced, so a
    delivery can be repeated or checked afterwards. Done by the runtime rather than by the
    model -- file contents never pass through anyone's context, so what lands in the
    project is byte-for-byte what the worker wrote.
    """
    from src.tools.files.tools import _safe_path, _shown
    from src.core.workspace import tasks_dir

    source = tasks_dir() / task_folder
    if not source.is_dir():
        return f"Nothing to deliver -- .the_way/tasks/{task_folder}/ does not exist."

    files = sorted(p for p in source.rglob("*") if p.is_file())
    if not files:
        return f"Nothing to deliver -- .the_way/tasks/{task_folder}/ is empty."

    target = _safe_path(destination)
    target.mkdir(parents=True, exist_ok=True)

    delivered = []
    for path in files:
        relative = path.relative_to(source)
        destination_path = target / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination_path)
        delivered.append(str(relative).replace("\\", "/"))

    return f"Delivered to {_shown(target)}/: {', '.join(delivered)}"


async def start_background_task(
    description: str,
    instructions: str,
    deliver_to: str | None = None,
):
    task_id = uuid4().hex[:8]
    # id suffix keeps two similarly-described tasks from writing into the same folder
    task_folder = f"{_slug(description)}-{task_id}"

    TASKS[task_id] = {
        "id": task_id,
        "description": description,
        # recorded so the folder can be looked up by id later -- the generated name is
        # long and easy to mistype, and a wrong guess reads as "the file does not exist"
        "folder": task_folder,
        "deliver_to": deliver_to,
        "status": "running",
        "result": None,
        "reported": False
    }

    async def run():
    
        CURRENT_TASK.set(task_id)

        from src.assistants.background_task.assistant import BackgroundTaskAssistant
        from src.assistants.background_task.config import MAX_ITERATIONS, MODEL, SCHEMAS, TEMPERATURE
        from src.core.agents.langchain.agent import LangchainAgent

        agent = LangchainAgent(
            model=MODEL,
            tools=SCHEMAS,
            temperature=TEMPERATURE,
            max_iterations=MAX_ITERATIONS
        )
        return await BackgroundTaskAssistant(agent=agent).work(task_folder, instructions)

        

    frontend.task_started(task_id, description)
    task = asyncio.create_task(run())
    _RUNNING.add(task)
    task.add_done_callback(lambda t: _finish(task_id, t))

    started = (
        f"Started background task {task_id}: {description}. "
        f"Working files go to .the_way/tasks/{task_folder}/"
    )
    if deliver_to:
        return f"{started}, and the finished files will be delivered to {deliver_to}/ automatically."

    return (
        f"{started}. No delivery folder was set, so the output will stay in "
        f".the_way/tasks/ where the user cannot easily open it -- tell them that, and "
        f"ask where they want it so you can call DeliverTask with id {task_id}."
    )



def _finish(task_id: str, t: asyncio.Task):
    _RUNNING.discard(t)
    rec = TASKS[task_id]

    if t.cancelled():
        rec["status"] = "cancelled"
    elif t.exception():
        rec["status"] = "failed"
        rec["result"] = f"{type(t.exception()).__name__}: {t.exception()}"
    else:
        from src.assistants.background_task.assistant import FAILURE_MARKER

        result = t.result()
        rec["result"] = result

        rec["status"] = "failed" if str(result).startswith(FAILURE_MARKER) else "done"

        # deliver only on success -- copying a half-finished deliverable into the user's
        # project is worse than leaving it in the task folder, because it looks finished
        if rec["status"] == "done" and rec["deliver_to"]:
            try:
                rec["result"] = f"{result}\n{deliver(rec['folder'], rec['deliver_to'])}"
            except Exception as exc:
                rec["result"] = (
                    f"{result}\nDelivery to {rec['deliver_to']}/ FAILED "
                    f"({type(exc).__name__}: {exc}). The files are still in "
                    f".the_way/tasks/{rec['folder']}/ -- tell the user the delivery "
                    f"failed and offer to retry it with DeliverTask."
                )


    detail = str(rec["result"] or "").strip().splitlines()
    frontend.task_finished(
        task_id, rec["description"], rec["status"], detail[0][:120] if detail else ""
    )



def drain_completed() -> str:
    """Tasks that finished since the last drain, marked reported so each is announced once.

    Not a tool -- the chat loop calls this every turn so completions surface on their own,
    rather than sitting silent until the model thinks to ask.
    """
    lines = []
    for task in TASKS.values():
        if task["status"] != "running" and not task["reported"]:
            task["reported"] = True
            lines.append(
                f"[{task['id']}] {task['description']} -- {task['status']}: {task['result']}"
            )

    return "\n".join(lines)


async def check_background_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return f"Task with id {task_id} not found"

    response = (
        f"Task status is {task['status']}. "
        f"Working folder: .the_way/tasks/{task['folder']}/"
    )

    if task["result"]:
        response += f"\nThe result of the task is: {task['result']}"
        task["reported"] = True

    return response


def deliver_task(task_id: str, destination: str) -> str:
    task = TASKS.get(task_id)
    if not task:
        known = ", ".join(TASKS) or "none"
        return (
            f"Task with id {task_id} not found. Known task ids this session: {known}. "
            "Do not guess a folder name -- ask the user which task they mean."
        )

    if task["status"] == "running":
        return f"Task {task_id} is still running. Wait for it to finish before delivering."

    if task["status"] != "done":
        return (
            f"Task {task_id} ended as '{task['status']}', so there may be no finished "
            f"deliverable to copy. Attempting delivery anyway: "
            f"{deliver(task['folder'], destination)}"
        )

    return deliver(task["folder"], destination)