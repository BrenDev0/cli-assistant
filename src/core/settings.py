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
    # Optional, like TAVILY_API_KEY below: a missing pair disables the CRM tools and says
    # so at startup rather than raising a pydantic ValidationError before main() runs. As
    # required fields these made a first install impossible for anyone who did not already
    # have a GoHighLevel token -- the app died at import, so there was no prompt to read
    # the error in and nothing to run the setup against.
    GHL_PIT: str = ""
    GHL_LOCATION_ID: str = ""
    MCP_VERSION: str = "2025-06-18"
    # optional: a missing key fails on the first web call, not at startup
    TAVILY_API_KEY: str = ""
    # Optional. Set it and the browser tools attach to a Chrome you already have
    # open -- your real one, with your sessions -- instead of launching their own.
    # That Chrome has to have been started with --remote-debugging-port=<this>.
    CHROME_DEBUG_PORT: str = ""

    def has_ghl(self) -> bool:
        return bool(self.GHL_PIT and self.GHL_LOCATION_ID)



settings = Settings() # type: ignore[call-arg]
