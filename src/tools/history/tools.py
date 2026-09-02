import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from src.core.workspace import history_dir

HISTORY = {"session": None}

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "what", "when", "was", "were",
    "you", "your", "can", "did", "does", "have", "has", "had", "are", "about",
    "from", "not", "but", "all", "any", "how", "our", "out", "get", "let",
}


def start_session() -> str:
    session = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:4]}"
    HISTORY["session"] = session
    return session


def record(role: str, content: str) -> None:
    """Append one message to this session's transcript. Never raises -- losing a
    transcript line must not take down the conversation."""
    if not content or not content.strip() or HISTORY["session"] is None:
        return

    try:
        history_dir().mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "role": role,
            "content": content,
        }
        path = history_dir() / f"{HISTORY['session']}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w.rstrip("s") for w in words if len(w) > 2 and w not in STOPWORDS}


def _load() -> list[dict]:
    if not history_dir().exists():
        return []

    entries = []
    for path in sorted(history_dir().glob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry["session"] = path.stem
            entries.append(entry)
    return entries


def search_conversation_history(query: str, limit: int = 10) -> str:
    entries = _load()
    if not entries:
        return "No saved conversation history yet."

    wanted = _tokens(query)
    if not wanted:
        return "Query had no searchable words. Use specific terms from what you are looking for."

    # rarer words are worth more: a term in half the messages barely narrows anything
    frequency = {}
    for entry in entries:
        for word in _tokens(entry.get("content", "")):
            frequency[word] = frequency.get(word, 0) + 1

    scored = []
    for entry in entries:
        overlap = wanted & _tokens(entry.get("content", ""))
        if overlap:
            score = sum(1 / frequency[word] for word in overlap)
            scored.append((score, entry))

    if not scored:
        return f"Nothing in the saved history matches '{query}'."

    scored.sort(key=lambda pair: -pair[0])

    lines = []
    for _, entry in scored[:limit]:
        content = entry.get("content", "").replace("\n", " ")
        if len(content) > 400:
            content = content[:400] + "..."
        lines.append(f"[{entry.get('ts', '?')}] {entry.get('role', '?')}: {content}")

    return "\n".join(lines)
