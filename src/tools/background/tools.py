from uuid import uuid4
import asyncio
TASKS: dict[str, dict] = {}
_RUNNING: set[asyncio.Task] = set()

async def start_background_task(
    description: str,
    instructions: str 
):
    task_id = uuid4().hex[:8]
    TASKS[task_id] = {
        "id": task_id,
        "description": description,
        "status": "running",
        "result": None,
        "reported": False
    }

    async def run():
        print(f"task started, description: {description}, instructions: {instructions}")
        await asyncio.sleep(60)
    
        return "stub task completed"

    task = asyncio.create_task(run())
    _RUNNING.add(task)
    task.add_done_callback(lambda t: _finish(task_id, t))
    return f"Started background task {task_id}: {description}"



def _finish(task_id: str, t: asyncio.Task):
    _RUNNING.discard(t)
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