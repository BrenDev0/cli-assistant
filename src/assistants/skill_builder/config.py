from src.tools.files.schemas import ReadFile, SearchFile, CreateDir, CreateFile, UpdateFile
from src.core.settings import settings

SCHEMAS = [ReadFile, SearchFile, CreateFile, CreateDir, UpdateFile]
API_KEY = settings.OPENAI_API_KEY
MODEL = "gpt-4o"
TEMPERATURE = 0.0
