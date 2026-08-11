from src.tools.files.tools import (
    read_file,
    search_file,
    create_file,
    create_dir,
    update_file
)
from src.tools.foundations.tools import build_foundation, list_foundations
from .files.schemas import CreateDir, CreateFile, SearchFile, ReadFile, UpdateFile
from .foundations.schemas import BuildFoundation, ListFoundations

TOOLS = {
    ReadFile: read_file,
    SearchFile: search_file,
    CreateFile: create_file,
    CreateDir: create_dir,
    UpdateFile: update_file,
    BuildFoundation: build_foundation,
    ListFoundations: list_foundations
}

TOOL_REGISTRY = {cls.__name__: fn for cls, fn in TOOLS.items()}

SCHEMAS = list(TOOLS.keys())