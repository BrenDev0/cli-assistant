import re
import shutil
from pathlib import Path
from src.core.workspace import ASSISTANT_PREFIX, assistant_home, project_root


def _split_root(user_path: str) -> tuple[Path, Path]:
    """A leading '.my_assistant/' always means the global workspace, whatever project is
    active. Everything else is project-relative. One rule, so the same path string means
    the same place from any directory."""
    parts = [p for p in str(user_path).replace("\\", "/").split("/") if p not in ("", ".")]

    if parts and parts[0] == ASSISTANT_PREFIX:
        return assistant_home(), Path(*parts[1:]) if parts[1:] else Path()

    return project_root(), Path(*parts) if parts else Path()


def _safe_path(user_path: str) -> Path:
    """Resolve against the right root and refuse to escape it."""
    root, relative = _split_root(user_path)
    candidate = (root / relative).resolve()

    if not candidate.is_relative_to(root):
        raise ValueError(
            f"Path '{user_path}' resolves outside the allowed directory ({root})"
        )
    return candidate


# utf-8-sig first so a BOM is stripped rather than left in the text; then the Windows
# default a file may have been written with before we started forcing utf-8. latin-1
# maps every byte, so the chain cannot fail -- which is why binary is rejected up front
# rather than being silently decoded into garbage.
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def _read_text(path: Path) -> str:
    raw = path.read_bytes()

    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")

    if b"\x00" in raw[:4096]:
        raise ValueError(
            f"'{_shown(path)}' looks like a binary file, not text (it contains null "
            f"bytes). Reading it would produce garbage, so it was not decoded."
        )

    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace")


def _shown(path: Path) -> str:
    """The inverse of _split_root: paths come back in the same form the model sends them.
    Absolute paths in return values teach the model to send absolute paths back."""
    if path.is_relative_to(assistant_home()):
        return f"{ASSISTANT_PREFIX}/{path.relative_to(assistant_home())}".replace("\\", "/")

    return str(path.relative_to(project_root())).replace("\\", "/")


def read_file(file_path: str):
    path = _safe_path(file_path)

    # on Windows open() on a directory raises PermissionError, which reads as a
    # filesystem problem and sends the model chasing permissions
    if path.is_dir():
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
        raise IsADirectoryError(
            f"'{file_path}' is a directory, not a file. It contains: "
            f"{', '.join(entries) or '(empty)'}. Read one of those instead."
        )

    return _read_text(path)


def list_dir(dir_path: str = "."):
    path = _safe_path(dir_path)
    if not path.exists():
        raise FileNotFoundError(f"Directory does not exist: {dir_path}")
    if not path.is_dir():
        raise NotADirectoryError(f"'{dir_path}' is a file, not a directory. Use read_file")

    entries = []
    for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if child.is_dir():
            entries.append(f"{child.name}/")
        else:
            entries.append(f"{child.name}  ({child.stat().st_size:,} bytes)")

    return "\n".join(entries) or "(empty directory)"


IGNORED_DIRS = {
    ".venv", "venv", "env", "node_modules", "__pycache__", ".git",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".idea", ".vscode", ".next", "target",
}

SEARCH_LIMIT = 50


def search_file(file_name: str, base_dir: str = "."):
    """Find files and folders whose path contains every word of the query.

    Matches against the whole relative path, not just the filename, so 'progreso report'
    finds tasks/<slug-with-progreso>/report.md -- the words can live in different path
    segments.
    """
    root = _safe_path(base_dir)
    terms = [t for t in re.split(r"[^a-z0-9]+", file_name.lower()) if t]
    if not terms:
        return "Give something to search for -- a filename, a word from one, or a folder name."

    hits = []
    scanned = 0
    for path in root.rglob("*"):
        inner = path.relative_to(root).parts
        if any(part in IGNORED_DIRS for part in inner):
            continue

        scanned += 1
        relative = _shown(path)
        haystack = relative.lower()
        if not all(term in haystack for term in terms):
            continue

        # a hit on the filename itself beats one that only matched a parent folder
        name_hits = sum(1 for term in terms if term in path.name.lower())
        hits.append((-name_hits, len(relative), relative, path.is_dir()))

    if not hits:
        return (
            f"Nothing under '{base_dir}' matches all of {terms}. "
            f"Searched {scanned} entries, skipping {', '.join(sorted(IGNORED_DIRS))}. "
            f"Try fewer or different words, or list a folder with list_dir."
        )

    hits.sort()
    lines = [f"{relative}/" if is_dir else relative
             for _, _, relative, is_dir in hits[:SEARCH_LIMIT]]

    if len(hits) > SEARCH_LIMIT:
        lines.append(f"... and {len(hits) - SEARCH_LIMIT} more; narrow the query or set base_dir")

    return "\n".join(lines)


def create_dir(dir_path: str):
    path = _safe_path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return _shown(path)


def create_file(file_path: str, content: str = "", overwrite: bool = False) -> str:
    path = _safe_path(file_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"File already exits: {path}. Pass overwrite=True to replace it")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return _shown(path)


def update_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    path = _safe_path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    content = _read_text(path)
    count = content.count(old_string)
    if count == 0:
        raise ValueError(f"old_string not found in {path}")
    if count > 1 and not replace_all:
        raise ValueError(
            f"old_string is not unique in {path} ({count} matches). "
            "Pass replace_all=True or make old_string more specific"
        )

    new_content = content.replace(old_string, new_string, -1 if replace_all else 1)
    path.write_text(new_content, encoding="utf-8")
    return _shown(path)


def delete_file(file_path: str) -> str:
    path = _safe_path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if path.is_dir():
        raise IsADirectoryError(f"'{path}' is a directory, not a file. Use delete_dir instead")

    path.unlink()
    return _shown(path)


def delete_dir(dir_path: str, recursive: bool = False) -> str:
    path = _safe_path(dir_path)
    if not path.exists():
        raise FileNotFoundError(f"Directory does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"'{path}' is not a directory. Use delete_file instead")
    if path == project_root():
        raise ValueError("Refusing to delete the project root directory")

    if recursive:
        shutil.rmtree(path)
    else:
        try:
            path.rmdir()
        except OSError as e:
            raise OSError(
                f"Directory not empty: {path}. Pass recursive=True to delete it and its contents"
            ) from e

    return _shown(path)

