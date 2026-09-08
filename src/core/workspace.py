from pathlib import Path

# Global, machine-wide: skills and conversation history live here so they follow the user
# between projects instead of vanishing whenever they cd somewhere else.
ASSISTANT_PREFIX = ".my_assistant"
ASSISTANT_HOME = Path.home() / ASSISTANT_PREFIX

# Where the user's own files live. A runtime lookup, not an import-time constant, so a
# project can be chosen after import -- and so a future web frontend can scope it per
# session rather than per process.
_project_root: Path = Path.cwd().resolve()


def assistant_home() -> Path:
    return ASSISTANT_HOME


def skills_dir() -> Path:
    return ASSISTANT_HOME / "skills"


def history_dir() -> Path:
    return ASSISTANT_HOME / "history"


def tasks_dir() -> Path:
    return ASSISTANT_HOME / "tasks"


def data_dir() -> Path:
    """Fetched datasets. Global rather than project-local because a dataset is a snapshot
    of the user's CRM, not of the project they happened to be sitting in when they pulled
    it -- the same 1,800 contacts should not be re-fetched once per folder."""
    return ASSISTANT_HOME / "data"


def project_root() -> Path:
    return _project_root


def use_project(path: str | Path) -> Path:
    global _project_root
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"Project path is not a directory: {resolved}")
    _project_root = resolved
    return resolved
