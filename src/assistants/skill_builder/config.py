from src.tools.files.schemas import ReadFile, SearchFile, CreateDir, CreateFile, UpdateFile

SCHEMAS = [ReadFile, SearchFile, CreateFile, CreateDir, UpdateFile]
# Deliberately the cheapest of the four. Writing a SKILL.md is templated work against a
# layout the prompt spells out exactly -- there is no reasoning here worth paying for.
MODEL = "gpt-5.4-mini"
TEMPERATURE = 0.0
