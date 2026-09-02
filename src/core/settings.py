from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import src as _src_package

REPO_ROOT = Path(_src_package.__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env"
    )

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GHL_PIT: str
    GHL_LOCATION_ID: str
    MCP_VERSION: str = "2025-06-18"
    # optional: a missing key fails on the first web call, not at startup
    TAVILY_API_KEY: str = ""



settings = Settings() # type: ignore[call-arg]
