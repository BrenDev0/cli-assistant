from src.tools.files.tools import (
    read_file,
    search_file,
    create_file,
    create_dir,
    update_file,
    delete_file,
    delete_dir
)
from src.tools.skills.tools import build_skill, list_skills
from src.tools.ghl.tools import describe_operation, execute_ghl_operation
from src.tools.background.tools import start_background_task, check_background_task
from .files.schemas import CreateDir, CreateFile, SearchFile, ReadFile, UpdateFile, DeleteFile, DeleteDir
from .skills.schemas import BuildSkill, ListSkills
from .ghl.schemas import DescribeGhlOperation, ExecuteGhlOperation
from .background.schemas import StartBackgroundTask, CheckBackgroundTask

TOOLS = {
    ReadFile: read_file,
    SearchFile: search_file,
    CreateFile: create_file,
    CreateDir: create_dir,
    UpdateFile: update_file,
    DeleteFile: delete_file,
    DeleteDir: delete_dir,
    BuildSkill: build_skill,
    ListSkills: list_skills,
    DescribeGhlOperation: describe_operation,
    ExecuteGhlOperation: execute_ghl_operation,
    StartBackgroundTask: start_background_task,
    CheckBackgroundTask: check_background_task
}

TOOL_REGISTRY = {cls.__name__: fn for cls, fn in TOOLS.items()}

SCHEMAS = list(TOOLS.keys())