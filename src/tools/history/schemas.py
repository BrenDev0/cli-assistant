from pydantic import BaseModel, Field


class SearchConversationHistory(BaseModel):
    """Search saved transcripts of this and previous conversations.

    Only the most recent exchanges stay in your context. Call this whenever the user
    refers to something discussed earlier that you cannot see -- "the report we did",
    "like we agreed", "the client from last week" -- or asks what was decided before.
    Prefer it over guessing: the earlier turns are on disk, not lost.
    """
    query: str = Field(description="Distinctive words from what you are looking for, for example 'progreso landing page price' rather than 'the thing we discussed'")
    limit: int = Field(default=10, description="Maximum number of matching messages to return")
