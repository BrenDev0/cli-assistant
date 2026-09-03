def _model() -> str:
    """The preferred model when its provider key is present, otherwise the fallback. A
    missing ANTHROPIC_API_KEY should cost the page some polish, not fail the tool."""
    from src.assistants.html_builder.config import FALLBACK_MODEL, PREFERRED_MODEL
    from src.core.agents.langchain.agent import key_for

    try:
        key_for(PREFERRED_MODEL)
        return PREFERRED_MODEL
    except ValueError:
        return FALLBACK_MODEL


async def build_html_page(
    output_path: str,
    page_type: str,
    brief: str,
    style_direction: str | None = None,
) -> str:
    from src.assistants.html_builder.assistant import HtmlBuilderAssistant
    from src.assistants.html_builder.config import (
        BUILDER_TEMPERATURE,
        DESIGNER_MAX_ITERATIONS,
        DESIGNER_SCHEMAS,
        DESIGNER_TEMPERATURE,
        MAX_ITERATIONS,
        SCHEMAS,
    )
    from src.core.agents.langchain.agent import LangchainAgent

    model = _model()

    designer = LangchainAgent(
        model=model,
        tools=DESIGNER_SCHEMAS,
        temperature=DESIGNER_TEMPERATURE,
        max_iterations=DESIGNER_MAX_ITERATIONS,
    )
    builder = LangchainAgent(
        model=model,
        tools=SCHEMAS,
        temperature=BUILDER_TEMPERATURE,
        max_iterations=MAX_ITERATIONS,
    )

    return await HtmlBuilderAssistant(designer=designer, builder=builder).build(
        output_path=output_path,
        page_type=page_type,
        brief=brief,
        style_direction=style_direction,
    )
