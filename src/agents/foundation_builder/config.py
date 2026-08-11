from src.tools.files.schemas import ReadFile, SearchFile, CreateDir, CreateFile, UpdateFile

# Restricted toolset for the sub-assistant, imported directly from files/ rather than from
# src.tools.registry (registry.py is what eventually imports this package, via tools/foundations/
# tools.py, so nothing in this package should import back from registry.py).
SCHEMAS = [ReadFile, SearchFile, CreateFile, CreateDir, UpdateFile]

MODEL = "gpt-4o"  # matches the model main.py hardcodes for the outer assistant
