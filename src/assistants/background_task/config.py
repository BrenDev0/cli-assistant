from src.core.settings import settings
from src.tools.registry import SCHEMAS as all_tools

# Workers must not spawn workers. Filtered into a new list rather than removed from
# all_tools, which is the same object the orchestrator is bound to.
EXCLUDED = {"StartBackgroundTask", "CheckBackgroundTask"}

SCHEMAS = [schema for schema in all_tools if schema.__name__ not in EXCLUDED]
API_KEY = settings.OPENAI_API_KEY
MODEL = "gpt-4o"
TEMPERATURE = 0.5
