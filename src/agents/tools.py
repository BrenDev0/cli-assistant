from pydantic import BaseModel, Field
import inspect
import asyncio
from pathlib import Path
PROJECT_ROOT = Path.cwd().resolve()

def _safe_path(user_path: str) -> Path:
    """Resolve user_path against PROJECT_ROOT and refuse to leave it."""
    candidate = (PROJECT_ROOT / user_path).resolve()
    if not candidate.is_relative_to(PROJECT_ROOT):
        raise ValueError(
            f"Path '{user_path}' resolves outside the allowed directory ({PROJECT_ROOT})"
        )
    return candidate


def read_file(file_path: str):
    print("reading file...")
    return _safe_path(file_path).read_text()

def search_file(file_name: str, basse_dir: str = "."):
    print("searching for file....")
    matches = _safe_path(basse_dir).rglob(f"*{file_name}*")
    return [str(match) for match in matches]

def create_dir(dir_path: str):
    print("creating directory...")
    _safe_path(dir_path).mkdir(parents=True, exist_ok=True)
    return str(Path(dir_path).resolve())


def create_file(file_path: str, content: str = "", overwrite: bool = False) -> str:
    print("creating file...")
    path = _safe_path(file_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"File already exits: {path}. Pass overwrite=True to replace it")

    path.write_text(content)
    return str(path.resolve())

class CreateDir(BaseModel):
    "Create a new directory(and missing parent directories) in a given path"
    dir_path: str = Field(description="The path of the directory to create")

class CreateFile(BaseModel):
    """Create a new file at the given path optionally with initial text contet"""
    file_path: str = Field(description="the path of the file to create")
    content: str = Field(description="Opotional initial content")
    overwrite: bool = Field(default=False, description="if true, overwite the file if it already exists; if false (default) an error is raised")

class ReadFile(BaseModel):
    """Get the contents of a given file"""
    file_path: str = Field(description="The path to the file we want to read")

class SearchFile(BaseModel):
    """Search for a file by name"""
    file_name: str = Field(description="The name of the file that we need to search for")


TOOL_REGISTRY = {
    "ReadFile": read_file,
    "SearchFile": search_file,
    "CreateFile": create_file,
    "CreateDir": create_dir
}


async def executor(tool_name: str, params: dict):
    if tool_name not in TOOL_REGISTRY.keys():
        raise ValueError(f"tool {tool_name} not in registry")

    tool = TOOL_REGISTRY[tool_name]

    if inspect.iscoroutinefunction(tool):
        return await tool(**params)

    return await asyncio.to_thread(tool, **params)


    


