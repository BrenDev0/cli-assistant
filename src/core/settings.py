from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import src as _src_package

REPO_ROOT = Path(_src_package.__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env"
    )

    OPENAI_API_KEY: str



settings = Settings() # type: ignore[call-arg]
