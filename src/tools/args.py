"""Tool implementations with Pydantic schemas."""
import os
import subprocess
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional

# Tool Schemas
class ReadFileArgs(BaseModel):
    file_path: str = Field(
        ..., max_length=512,
        description="Path to the file to read.",
        pattern=r"^[a-zA-Z0-9_./\\-]+$"
    )

class ListDirArgs(BaseModel):
    dir_path: str = Field(
        ".", max_length=512,
        description="Path to the directory to list.",
        pattern=r"^[a-zA-Z0-9_./\\-]+$"
    )

class WriteFileArgs(BaseModel):
    file_path: str = Field(
        ..., max_length=512,
        description="Path to the file to write.",
        pattern=r"^[a-zA-Z0-9_./\\-]+$"
    )
    content: str = Field(..., max_length=50000, description="The content to write to the file.")

class ShellExecArgs(BaseModel):
    command: str = Field(..., max_length=2000, description="The shell command to execute.")

class UpdateScratchpadArgs(BaseModel):
    key: str = Field(..., max_length=256, description="The key to update.")
    value: str = Field(..., max_length=10000, description="The value to store.")

class GitArgs(BaseModel):
    command: str = Field(
        ..., max_length=2000,
        description="Git subcommand with arguments.",
        pattern=r"^[a-zA-Z0-9_\-./\\ ]+$"
    )
    message: Optional[str] = Field(None, max_length=2000, description="Commit message.")

class DocSearchArgs(BaseModel):
    query: str = Field(..., max_length=500, description="The query to search for.")

class ClarificationArgs(BaseModel):
    question: str = Field(..., max_length=2000, description="The question to ask the user.")

# ── New Tool Schemas (Set 3) ──

class CodeSearchArgs(BaseModel):
    pattern: str = Field(..., max_length=500, description="The regex pattern to search for.")
    path: str = Field(".", max_length=512, description="The directory path to search in.")

class FilePatchArgs(BaseModel):
    file_path: str = Field(
        ..., max_length=512,
        description="The file to apply the patch to.",
        pattern=r"^[a-zA-Z0-9_./\\-]+$"
    )
    search_text: str = Field(..., max_length=10000, description="The exact text block to find.")
    replace_text: str = Field(..., max_length=10000, description="The replacement text.")

class UrlFetchArgs(BaseModel):
    url: str = Field(
        ..., max_length=2048,
        description="The URL to fetch via HTTP GET."
    )
    timeout: int = Field(10, ge=1, le=120, description="Timeout in seconds for the request.")

# ── Workspace root for sandboxed operations ──
