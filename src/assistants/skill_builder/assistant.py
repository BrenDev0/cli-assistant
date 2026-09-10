from .prompt import SYSTEM_PROMPT
from src.core.agents.types import Agent


class SkillBuilderAssistant:
    """Delegates to an injected Agent scoped to file tools only, and knows how to
    turn a (skill_name, description) request into a finished
    .the_way/skills/<name>/ folder."""

    def __init__(self, agent: Agent):
        self._agent = agent

    async def build(self, skill_name: str, description: str) -> str:
        messages = [
            ("system", SYSTEM_PROMPT),
            ("user", f"Skill name: {skill_name}\n\nBrief:\n{description}"),
        ]

        try:
            summary = await self._agent.invoke(messages)
        except RuntimeError:
            return (
                f"build_skill: sub-assistant didn't finish '{skill_name}' within its "
                f"iteration limit. Partial files may exist under "
                f".the_way/skills/{skill_name}/ — retry with the same "
                "skill_name to resume/repair."
            )
        except Exception as exc:
            return (
                f"build_skill: failed while authoring '{skill_name}' "
                f"({type(exc).__name__}: {exc}). Check "
                f".the_way/skills/{skill_name}/ for partial output."
            )

        return f"Skill '{skill_name}' created/updated at .the_way/skills/{skill_name}/.\n{summary}"
