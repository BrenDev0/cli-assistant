from src.tools.registry import SCHEMAS  # noqa: F401 — re-exported for callers of this config

# Runs on every turn, so cost here multiplies with conversation length -- but its job is
# instruction-following, not deep reasoning: pick the right tool, do it in this turn, relay
# what the manifest actually said. That is exactly where gpt-4o kept failing, and it failed
# at temperature 0.0, so sampling was never the lever. One tier below the background
# worker, because a mistake here shows up in the next line of chat and gets corrected.
MODEL = "gpt-5.4"

# Inert while MODEL is a gpt-5 tier -- those fix their own sampling and ACCEPTS_TEMPERATURE
# omits the parameter. Kept because it applies the moment this points at a 4.x model again.
TEMPERATURE = 0.0
