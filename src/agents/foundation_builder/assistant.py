from src.agents.langchain.assistant import LangchainAssistant
from src.settings import settings
from .config import MODEL, SCHEMAS
from .prompt import SYSTEM_PROMPT


class FoundationBuilderAssistant:
    """Owns a scoped LangchainAssistant bound only to file tools, and knows how to
    turn a (foundation_name, description) request into a finished
    my_assistant/foundations/<name>/ folder."""

    def __init__(self):
        self._llm = LangchainAssistant(
            model=MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.0,
            tools=SCHEMAS,
        )

    async def build(self, foundation_name: str, description: str) -> str:
        messages = [
            ("system", SYSTEM_PROMPT),
            ("user", f"Foundation name: {foundation_name}\n\nBrief:\n{description}"),
        ]

        try:
            summary = await self._llm.invoke(messages)
        except RuntimeError:
            return (
                f"build_foundation: sub-assistant didn't finish '{foundation_name}' within its "
                f"iteration limit. Partial files may exist under "
                f"my_assistant/foundations/{foundation_name}/ — retry with the same "
                "foundation_name to resume/repair."
            )
        except Exception as exc:
            return (
                f"build_foundation: failed while authoring '{foundation_name}' "
                f"({type(exc).__name__}: {exc}). Check "
                f"my_assistant/foundations/{foundation_name}/ for partial output."
            )

        return f"Foundation '{foundation_name}' created/updated at my_assistant/foundations/{foundation_name}/.\n{summary}"
