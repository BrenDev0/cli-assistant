from pydantic import BaseModel, Field

class ListSkills(BaseModel):
    """List the skills currently available under .the_way/skills/, showing
    each one's name and one-line description. Call this to check what skills exist
    before deciding whether one applies to the user's request."""

class BuildSkill(BaseModel):
    """Create or update a "skill": a self-contained folder of instructions
    (and optional supporting files) that an AI assistant can read later to reliably
    perform a specific recurring task. Use this when asked to create/build/package a
    skill, workflow, or reusable capability. Returns a short summary of what was
    created or changed."""
    skill_name: str = Field(
        description="A short, filesystem-safe, kebab-case name, e.g. 'pdf-report-generator'. "
        "Used verbatim as the folder name under .the_way/skills/<skill_name>/. "
        "Reuse the exact same skill_name to update an existing skill rather than "
        "create a duplicate."
    )
    description: str = Field(
        description="A detailed brief of what the skill should do, when to use it, and "
        "any specific steps, conventions, or supporting files it needs. More detail -> better "
        "SKILL.md."
    )
