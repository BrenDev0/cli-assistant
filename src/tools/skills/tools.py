from pathlib import Path

PROJECT_ROOT = Path.cwd().resolve()


def list_skills() -> str:
    skills_dir = PROJECT_ROOT / ".my_assistant" / "skills"
    if not skills_dir.exists():
        return "No skills found."

    entries = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        name, description = _parse_frontmatter(path.read_text())
        entries.append(f"{name or path.parent.name}: {description or '(no description)'}")

    return "\n".join(entries) if entries else "No skills found."


def _parse_frontmatter(content: str) -> tuple[str | None, str | None]:
    """Pull just the name:/description: lines out of a SKILL.md's --- frontmatter
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


async def build_skill(skill_name: str, description: str) -> str:
    # Deferred import: registry.py imports this module at load time, and
    # assistants.skill_builder ultimately imports agents.langchain.agent, which itself
    # imports src.tools.executor -> src.tools.registry. Importing it here at module scope
    # would loop back into registry.py while it's still mid-import. Deferring until this
    # function actually runs (a real tool call, well after startup) avoids the cycle.
    from src.assistants.skill_builder.assistant import SkillBuilderAssistant
    from src.core.agents.langchain.agent import LangchainAgent
    from src.assistants.skill_builder.config import MODEL, SCHEMAS, TEMPERATURE, API_KEY
    agent = LangchainAgent(
        model=MODEL,
        tools=SCHEMAS,
        temperature=TEMPERATURE,
        api_key=API_KEY
    )
    return await SkillBuilderAssistant(agent=agent).build(skill_name, description)
