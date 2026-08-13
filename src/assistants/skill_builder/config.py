from src.tools.files.schemas import ReadFile, SearchFile, CreateDir, CreateFile, UpdateFile
from src.core.settings import settings
# Restricted toolset for the sub-assistant, imported directly from files/ rather than from
# src.tools.registry (registry.py is what eventually imports this package, via tools/skills/
# tools.py, so nothing in this package should import back from registry.py).
SCHEMAS = [ReadFile, SearchFile, CreateFile, CreateDir, UpdateFile]
API_KEY = settings.OPENAI_API_KEY
MODEL = "gpt-4o"
TEMPERATURE = 0.0
