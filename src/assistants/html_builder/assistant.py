from .prompt import BUILDER_PROMPT, DESIGNER_PROMPT
from src.core.agents.types import Agent

# _safe_path rather than a second path-resolution rule of our own: the whole point of the
# one in files.tools is that a path string means the same place everywhere.
from src.tools.files.tools import _safe_path

FAILURE_MARKER = "HTML BUILD FAILED"

NO_BRIEF = (
    "(The art-direction pass did not produce a brief. Follow the house design system "
    "exactly, and make the concrete choices it leaves open yourself -- typefaces, the "
    "palette hex values, and the section structure -- before writing any markup.)"
)


class HtmlBuilderAssistant:
    """Builds one professional-grade HTML page in two passes.

    Pass 1 is art direction with no file-writing tools: it commits to typefaces, hex
    values, layout and a signature detail in writing. Pass 2 executes that brief.

    The split is deliberate and is not the same as splitting design into its own agent.
    Design and markup are one artifact -- a separate design *agent* would write CSS blind
    to a DOM that does not exist yet, and every class name would become a contract between
    two agents that cannot see each other's work. What actually needs separating is the
    *decision*: a model that styles a page one tag at a time is choosing implicitly, and
    implicit choices collapse to the median of the training data, which is what "plain"
    is. So the decision gets its own pass, in the same assistant, for the price of one
    cheap call.
    """

    def __init__(self, designer: Agent, builder: Agent):
        self._designer = designer
        self._builder = builder

    async def build(
        self,
        output_path: str,
        page_type: str,
        brief: str,
        style_direction: str | None = None,
    ) -> str:
        from .design import archetype_guidance

        request = f"Page type: {page_type}\nOutput file: {output_path}\n\nBrief:\n{brief}"
        if style_direction:
            request += f"\n\nStyle direction from the user (treat as binding):\n{style_direction}"

        design_brief = await self._direct(request, archetype_guidance(page_type))

        build_request = (
            f"{request}\n\n=== DESIGN BRIEF (execute this) ===\n{design_brief}\n\n"
            f"{archetype_guidance(page_type)}"
        )

        try:
            report = await self._builder.invoke(
                [("system", BUILDER_PROMPT), ("user", build_request)]
            )
        except RuntimeError as exc:
            return (
                f"{FAILURE_MARKER} -- the builder ran out of steps ({exc}). "
                f"{self._written(output_path)} Tell the user plainly that the page is "
                "unfinished; do not describe it as done."
            )
        except Exception as exc:
            return (
                f"{FAILURE_MARKER} -- {type(exc).__name__}: {exc}. "
                f"{self._written(output_path)} Tell the user plainly that the page is "
                "unfinished; do not describe it as done."
            )

        # the builder's own report is not evidence the file exists -- check the disk
        return f"{self._written(output_path)}\n{report}"

    async def _direct(self, request: str, archetype: str) -> str:
        """The design brief, or a standing instruction to decide for itself. A failed
        art-direction pass costs quality; it must not cost the page."""
        try:
            return await self._designer.invoke(
                [("system", DESIGNER_PROMPT), ("user", f"{request}\n\n{archetype}")]
            )
        except Exception:
            return NO_BRIEF

    def _written(self, output_path: str) -> str:
        try:
            path = _safe_path(output_path)
        except Exception:
            return f"Could not verify '{output_path}' -- it is outside the allowed roots."

        if not path.is_file():
            return f"NO FILE was written at {output_path}."

        return f"Wrote {output_path} ({path.stat().st_size:,} bytes)."
