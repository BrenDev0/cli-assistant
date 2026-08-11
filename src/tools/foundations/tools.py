from pathlib import Path

PROJECT_ROOT = Path.cwd().resolve()


def list_foundations() -> str:
    foundations_dir = PROJECT_ROOT / "my_assistant" / "foundations"
    if not foundations_dir.exists():
        return "No foundations found."

    entries = []
    for path in sorted(foundations_dir.glob("*/FOUNDATION.md")):
        name, description = _parse_frontmatter(path.read_text())
        entries.append(f"{name or path.parent.name}: {description or '(no description)'}")

    return "\n".join(entries) if entries else "No foundations found."


def _parse_frontmatter(content: str) -> tuple[str | None, str | None]:
    """Pull just the name:/description: lines out of a FOUNDATION.md's --- frontmatter
    block, without needing a YAML dependency for a format this simple."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None

    name = description = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip()
    return name, description


async def build_foundation(foundation_name: str, description: str) -> str:
    # Deferred import: registry.py imports this module at load time, and
    # agents.foundation_builder ultimately imports agents.langchain.assistant, which itself
    # imports src.tools.executor -> src.tools.registry. Importing it here at module scope
    # would loop back into registry.py while it's still mid-import. Deferring until this
    # function actually runs (a real tool call, well after startup) avoids the cycle.
    from src.agents.foundation_builder.assistant import FoundationBuilderAssistant

    return await FoundationBuilderAssistant().build(foundation_name, description)
