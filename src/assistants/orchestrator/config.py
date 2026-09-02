from src.tools.registry import SCHEMAS  # noqa: F401 — re-exported for callers of this config

# Unlike skill_builder's restricted list, the orchestrator is the first point of
# contact with the user and gets every registered tool (imported above).
MODEL = "gpt-4o"
TEMPERATURE = 0.0
