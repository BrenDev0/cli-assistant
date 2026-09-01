from uuid import uuid4
import asyncio
import re

from src.core.events import CURRENT_TASK, clear_activity, set_activity

TASKS: dict[str, dict] = {}
_RUNNING: set[asyncio.Task] = set()


def _slug(text: str, limit: int = 40) -> str:
    """Kebab-case folder name from a task description."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned[:limit].rstrip("-") or "task"


async def start_background_task(
    description: str,
    instructions: str
):
    task_id = uuid4().hex[:8]
    # id suffix keeps two similarly-described tasks from writing into the same folder
    task_folder = f"{_slug(description)}-{task_id}"

    TASKS[task_id] = {
        "id": task_id,
        "description": description,
        "status": "running",
        "result": None,
        "reported": False
    }

    async def run():
        # set inside run(), not before create_task: the context is copied at creation,
        # so setting it earlier would tag the orchestrator's calls too
        CURRENT_TASK.set(task_id)

        # imported here, not at module scope: registry.py imports this module, so a
        # top-level import of anything that reads the registry would be circular
        from src.assistants.background_task.assistant import BackgroundTaskAssistant
        from src.assistants.background_task.config import MODEL, SCHEMAS, TEMPERATURE, API_KEY
        from src.core.agents.langchain.agent import LangchainAgent

        agent = LangchainAgent(
            model=MODEL,
            tools=SCHEMAS,
            temperature=TEMPERATURE,
            api_key=API_KEY
        )
        return await BackgroundTaskAssistant(agent=agent).work(task_folder, instructions)

        

    set_activity(task_id, "starting")
    task = asyncio.create_task(run())
    _RUNNING.add(task)
    task.add_done_callback(lambda t: _finish(task_id, t))
    return (
        f"Started background task {task_id}: {description}. "
        f"Output will be written to .my_assistant/tasks/{task_folder}/"
    )



def _finish(task_id: str, t: asyncio.Task):
    _RUNNING.discard(t)
    clear_activity(task_id)
    rec = TASKS[task_id]
    if t.cancelled():
        rec["status"] = "cancelled"
    elif t.exception():
        rec["status"] = "failed"
        rec["result"] = f"{type(t.exception()).__name__}: {t.exception()}"
    else:
        rec["status"] = "done"
        rec["result"] = t.result()



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

    response = f"Task status is {task['status']}"

    if task["result"]:
        response += f" the result of the task is: {task['result']}"
        task["reported"] = True

    return response