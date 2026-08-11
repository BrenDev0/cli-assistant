from pydantic import BaseModel, Field

class ListFoundations(BaseModel):
    """List the foundations currently available under my_assistant/foundations/, showing
    each one's name and one-line description. Call this to check what foundations exist
    before deciding whether one applies to the user's request."""

class BuildFoundation(BaseModel):
    """Create or update a "foundation": a self-contained folder of instructions
    (and optional supporting files) that an AI assistant can read later to reliably
    perform a specific recurring task. Use this when asked to create/build/package a
    skill, workflow, or reusable capability. Returns a short summary of what was
    created or changed."""
    foundation_name: str = Field(
        description="A short, filesystem-safe, kebab-case name, e.g. 'pdf-report-generator'. "
        "Used verbatim as the folder name under my_assistant/foundations/<foundation_name>/. "
        "Reuse the exact same foundation_name to update an existing foundation rather than "
        "create a duplicate."
    )
    description: str = Field(
        description="A detailed brief of what the foundation should do, when to use it, and "
        "any specific steps, conventions, or supporting files it needs. More detail -> better "
        "FOUNDATION.md."
    )
