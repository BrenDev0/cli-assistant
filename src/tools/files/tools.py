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
    print(f"reading file... {file_path}")
    return _safe_path(file_path).read_text()

def search_file(file_name: str, basse_dir: str = "."):
    print(f"searching for file... {file_name} (in {basse_dir})")
    matches = _safe_path(basse_dir).rglob(f"*{file_name}*")
    return [str(match) for match in matches]

def create_dir(dir_path: str):
    print(f"creating directory... {dir_path}")
    _safe_path(dir_path).mkdir(parents=True, exist_ok=True)
    return str(Path(dir_path).resolve())


def create_file(file_path: str, content: str = "", overwrite: bool = False) -> str:
    print(f"creating file... {file_path}")
    path = _safe_path(file_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"File already exits: {path}. Pass overwrite=True to replace it")

    path.write_text(content)
    return str(path.resolve())


def update_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    print(f"updating file... {file_path}")
    path = _safe_path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    content = path.read_text()
    count = content.count(old_string)
    if count == 0:
        raise ValueError(f"old_string not found in {path}")
    if count > 1 and not replace_all:
        raise ValueError(
            f"old_string is not unique in {path} ({count} matches). "
            "Pass replace_all=True or make old_string more specific"
        )

    new_content = content.replace(old_string, new_string, -1 if replace_all else 1)
    path.write_text(new_content)
    return str(path.resolve())




    


