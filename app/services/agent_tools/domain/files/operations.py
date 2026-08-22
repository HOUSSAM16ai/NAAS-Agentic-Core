"""
File Operations Domain Tools
==========================

Strictly focused on file operations.
Uses `tool_model` for cleaner definition.
"""

import os

import aiofiles

from app.services.agent_tools.tool_model import Tool, ToolConfig
from app.services.agent_tools.utils import _safe_path

# Constants
MAX_WRITE_BYTES = 5_000_000
MAX_READ_BYTES = 100_000

# ======================================================================================
# Handlers
# ======================================================================================


async def write_file_handler(path: str, content: str, **kwargs) -> dict[str, object]:
    """Write content to a file."""
    if not isinstance(content, str):
        raise ValueError("Content must be a string")

    abs_path = _safe_path(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {"written": abs_path, "bytes": len(content)}


async def read_file_handler(path: str, max_bytes: int = 20000, **kwargs) -> dict[str, object]:
    """Read content from a file."""
    abs_path = _safe_path(path)

    if not os.path.exists(abs_path):
        return {"error": "File not found", "path": abs_path}

    async with aiofiles.open(abs_path, encoding="utf-8", errors="replace") as f:
        content = await f.read(max_bytes)

    return {"content": content, "path": abs_path, "truncated": len(content) == max_bytes}


async def list_dir_handler(path: str = ".", **kwargs) -> dict[str, object]:
    """List directory contents."""
    abs_path = _safe_path(path)
    if not os.path.isdir(abs_path):
        return {"error": "Not a directory", "path": abs_path}

    entries = os.listdir(abs_path)
    return {"entries": sorted(entries), "path": abs_path}


async def delete_file_handler(path: str, confirm: bool = False, **kwargs) -> dict[str, object]:
    """Delete a file."""
    if not confirm:
        return {"error": "Confirmation required", "path": path}

    abs_path = _safe_path(path)
    if not os.path.exists(abs_path):
        return {"error": "File not found", "path": abs_path}

    os.remove(abs_path)
    return {"deleted": True, "path": abs_path}


# ======================================================================================
# Tool Classes
# ======================================================================================


class WriteFileTool(Tool):
    def __init__(self):
        super().__init__(
            ToolConfig(
                name="write_file",
                description="Write content to a file.",
                category="fs",
                aliases=["write", "create_file"],
                handler=write_file_handler,
            )
        )


class ReadFileTool(Tool):
    def __init__(self):
        super().__init__(
            ToolConfig(
                name="read_file",
                description="Read content from a file.",
                category="fs",
                aliases=["read", "cat"],
                handler=read_file_handler,
            )
        )


class ListDirTool(Tool):
    def __init__(self):
        super().__init__(
            ToolConfig(
                name="list_dir",
                description="List directory contents.",
                category="fs",
                aliases=["ls", "dir"],
                handler=list_dir_handler,
            )
        )


class DeleteFileTool(Tool):
    def __init__(self):
        super().__init__(
            ToolConfig(
                name="delete_file",
                description="Delete a file.",
                category="fs",
                aliases=["rm", "delete"],
                handler=delete_file_handler,
            )
        )
