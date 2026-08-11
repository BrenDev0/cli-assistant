from pydantic import BaseModel, Field

class CreateDir(BaseModel):
    "Create a new directory(and missing parent directories) in a given path"
    dir_path: str = Field(description="The path of the directory to create")

class CreateFile(BaseModel):
    """Create a new file at the given path optionally with initial text contet"""
    file_path: str = Field(description="the path of the file to create")
    content: str = Field(description="Opotional initial content")
    overwrite: bool = Field(default=False, description="if true, overwite the file if it already exists; if false (default) an error is raised")

class ReadFile(BaseModel):
    """Get the contents of a given file"""
    file_path: str = Field(description="The path to the file we want to read")

class UpdateFile(BaseModel):
    """Update an existing file by replacing an exact substring with new text"""
    file_path: str = Field(description="The path of the file to update")
    old_string: str = Field(description="The exact existing text to replace; must match exactly, including whitespace")
    new_string: str = Field(description="The text to replace old_string with")
    replace_all: bool = Field(default=False, description="If true, replace every occurrence of old_string; if false (default), old_string must be unique in the file")

class SearchFile(BaseModel):
    """Search for a file by name"""
    file_name: str = Field(description="The name of the file that we need to search for")
