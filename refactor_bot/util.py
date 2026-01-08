"""
Utility functions for refactor-bot.
"""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


def generate_run_id() -> str:
    """Generate a unique run ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{timestamp}_{short_uuid}"


def generate_session_id() -> str:
    """Generate a unique session ID for Claude calls.

    Returns a proper UUID string with dashes (e.g., '550e8400-e29b-41d4-a716-446655440000')
    which is required by Claude Code CLI.
    """
    return str(uuid.uuid4())


def file_hash(path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def dir_hash(path: Path, excludes: Optional[list[str]] = None) -> str:
    """Calculate a hash representing the state of a directory."""
    import fnmatch

    excludes = excludes or []
    hasher = hashlib.sha256()

    for file_path in sorted(path.rglob("*")):
        if file_path.is_file():
            rel_path = file_path.relative_to(path)
            # Check excludes
            skip = False
            for pattern in excludes:
                if fnmatch.fnmatch(str(rel_path), pattern):
                    skip = True
                    break
            if skip:
                continue

            hasher.update(str(rel_path).encode())
            hasher.update(file_hash(file_path).encode())

    return hasher.hexdigest()


def run_command(
    cmd: str | list[str],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    capture_output: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a shell command with proper error handling."""
    if isinstance(cmd, str):
        shell = True
    else:
        shell = False

    return subprocess.run(
        cmd,
        cwd=cwd,
        timeout=timeout,
        capture_output=capture_output,
        text=True,
        shell=shell,
        check=check,
    )


def is_git_repo(path: Path) -> bool:
    """Check if a directory is a git repository."""
    git_dir = path / ".git"
    return git_dir.exists() and git_dir.is_dir()


def get_repo_name(path: Path) -> str:
    """Get a clean repository name from path."""
    return path.resolve().name


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format duration to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def truncate_string(s: str, max_length: int = 80, suffix: str = "...") -> str:
    """Truncate a string to a maximum length."""
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def count_lines(content: str) -> int:
    """Count the number of lines in a string."""
    return content.count("\n") + (1 if content and not content.endswith("\n") else 0)


def parse_unified_diff_stats(diff: str) -> tuple[int, int, list[str]]:
    """Parse a unified diff and return (lines_added, lines_removed, files_touched)."""
    lines_added = 0
    lines_removed = 0
    files = set()

    for line in diff.split("\n"):
        if line.startswith("+++ b/"):
            files.add(line[6:])
        elif line.startswith("--- a/"):
            files.add(line[6:])
        elif line.startswith("+") and not line.startswith("+++"):
            lines_added += 1
        elif line.startswith("-") and not line.startswith("---"):
            lines_removed += 1

    return lines_added, lines_removed, sorted(files)
