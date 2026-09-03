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

class ListDir(BaseModel):
    """List the contents of a directory, showing sub-directories (with a trailing /) and
    files with their sizes. Use this to see what is inside a folder before reading
    anything -- read_file only works on files, never on directories."""
    dir_path: str = Field(default=".", description="Directory to list, relative to the project root. Defaults to the project root itself")

class SearchFile(BaseModel):
    """Find files and folders anywhere under base_dir. Every word of the query must appear
    somewhere in the path, so 'progreso report' finds a report.md inside a folder named
    after progreso. Folders come back with a trailing / -- list those with ListDir rather
    than reading them. Build directories (.venv, node_modules, __pycache__, .git) are
    skipped. Prefer two or three distinctive words over a full filename."""
    file_name: str = Field(description="Words to look for in the path, for example 'progreso report' or 'schemas'")
    base_dir: str = Field(default=".", description="Directory to search under, relative to the project root. Narrow this when you know roughly where to look")

class CopyPath(BaseModel):
    """Copy a file or a whole directory to another location, leaving the original in
    place. Use this to put a copy of something where the user wants it -- NEVER read a
    file and re-create it at the new path. Re-creating round-trips the contents through
    your context, where they can be truncated or replaced with something you did not
    read; copying moves the bytes on disk and cannot corrupt them."""
    source: str = Field(description="The existing file or directory to copy from")
    destination: str = Field(
        description="Where to copy to. If source is a file and destination is an existing "
        "directory, the file is copied into it under the same name. Parent directories "
        "are created as needed."
    )
    overwrite: bool = Field(default=False, description="If true, replace anything already at the destination; if false (default) an error is raised")

class MovePath(BaseModel):
    """Move or rename a file or a whole directory. The original no longer exists at the
    old path afterwards. Use this rather than reading a file and re-creating it elsewhere,
    which risks writing content you never actually read. If the user may still want the
    original where it is, use CopyPath instead."""
    source: str = Field(description="The existing file or directory to move")
    destination: str = Field(
        description="The new path. If source is a file and destination is an existing "
        "directory, the file is moved into it under the same name. Parent directories "
        "are created as needed."
    )
    overwrite: bool = Field(default=False, description="If true, replace anything already at the destination; if false (default) an error is raised")

class DeleteFile(BaseModel):
    """Delete an existing file"""
    file_path: str = Field(description="The path of the file to delete")

class DeleteDir(BaseModel):
    """Delete an existing directory"""
    dir_path: str = Field(description="The path of the directory to delete")
    recursive: bool = Field(default=False, description="If true, delete the directory and all its contents; if false (default), the directory must be empty or an error is raised")
