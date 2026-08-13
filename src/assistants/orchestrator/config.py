from src.tools.registry import SCHEMAS  # noqa: F401 — re-exported for callers of this config
from src.core.settings import settings

# Unlike skill_builder's restricted list, the orchestrator is the first point of
# contact with the user and gets every registered tool (imported above).
API_KEY = settings.OPENAI_API_KEY
MODEL = "gpt-4o"
TEMPERATURE = 0.0
