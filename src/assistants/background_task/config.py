from src.tools.registry import SCHEMAS as all_tools

# Workers must not spawn workers. Filtered into a new list rather than removed from
# all_tools, which is the same object the orchestrator is bound to.
EXCLUDED = {"StartBackgroundTask", "CheckBackgroundTask", "DeliverTask"}

SCHEMAS = [schema for schema in all_tools if schema.__name__ not in EXCLUDED]
# The strongest model in the project, and deliberately a tier above the orchestrator. This
# is the only agent that runs unsupervised -- executor.py skips approval when CURRENT_TASK
# is set, so nobody is at the keyboard to catch a bad write. It also runs the deepest loop
# (MAX_ITERATIONS below), where a wrong turn at step 4 poisons the remaining 26, and it
# writes the artifact the client actually opens. Model quality is the only guardrail on
# that path. It runs a handful of times a day rather than once per turn, so the cost of
# the upgrade lands per deliverable, not per message -- and a stronger model converging in
# 8 iterations instead of 25 gives much of it back.
MODEL = "gpt-5.5"

# Inert on a gpt-5 tier; see ACCEPTS_TEMPERATURE in the agent.
TEMPERATURE = 0.5

MAX_ITERATIONS = 50
