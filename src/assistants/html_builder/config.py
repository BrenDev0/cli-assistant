from src.tools.registry import SCHEMAS as all_tools
from src.tools.files.schemas import ReadFile, SearchFile

# The builder must not spawn workers, author skills, recurse into itself, or delete
# anything -- a page builder has no business removing files. Filtered into a new list
# rather than removed from all_tools, which is the same object the orchestrator is bound to.
EXCLUDED = {
    "StartBackgroundTask",
    "CheckBackgroundTask",
    "DeliverTask",
    "BuildSkill",
    "BuildHtmlPage",
    "CopyPath",
    "MovePath",
    "DeleteFile",
    "DeleteDir",
}

SCHEMAS = [schema for schema in all_tools if schema.__name__ not in EXCLUDED]

# The art-direction pass only needs to look for a brand override; it writes nothing.
DESIGNER_SCHEMAS = [ReadFile, SearchFile]

# Design quality tracks model quality here more sharply than in any other assistant -- the
# difference between these two is visible in the output. The preferred model is used when
# its key is present, otherwise the fallback, so a missing ANTHROPIC_API_KEY degrades the
# page instead of failing the tool.
PREFERRED_MODEL = "claude-sonnet-5"
FALLBACK_MODEL = "gpt-5.5"

# High for the director (design choices should vary between pages, not converge on one
# safe look), low for the builder (it is executing a decision, not making one).
DESIGNER_TEMPERATURE = 0.9
BUILDER_TEMPERATURE = 0.3

DESIGNER_MAX_ITERATIONS = 4

# A page, a read-back, and a real revision pass -- plus room for web lookups when the
# brief needs real content.
MAX_ITERATIONS = 25
