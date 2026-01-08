"""
Patch application for refactor-bot.

Handles validation and application of unified diff patches.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from refactor_bot.util import parse_unified_diff_stats


class PatchError(Exception):
    """Base exception for patch-related errors."""

    pass


class PatchValidationError(PatchError):
    """Patch failed validation."""

    pass


class PatchApplicationError(PatchError):
    """Patch failed to apply."""

    pass


@dataclass
class PatchStats:
    """Statistics about a patch."""

    lines_added: int
    lines_removed: int
    files_touched: list[str]

    @property
    def total_changed(self) -> int:
        return self.lines_added + self.lines_removed


@dataclass
class PatchResult:
    """Result of applying a patch."""

    success: bool
    stats: Optional[PatchStats] = None
    error_message: Optional[str] = None
    original_diff: str = ""


class PatchValidator:
    """Validates patches before application."""

    def __init__(
        self,
        repo_path: Path,
        scope_globs: list[str],
        diff_budget_loc: int,
        allow_binary: bool = False,
    ):
        self.repo_path = repo_path
        self.scope_globs = scope_globs
        self.diff_budget_loc = diff_budget_loc
        self.allow_binary = allow_binary

    def validate(self, patch_diff: str) -> tuple[bool, Optional[str], PatchStats]:
        """
        Validate a patch against constraints.

        Returns:
            (is_valid, error_message, stats)
        """
        if not patch_diff.strip():
            return False, "Empty patch", PatchStats(0, 0, [])

        # Parse stats
        lines_added, lines_removed, files_touched = parse_unified_diff_stats(patch_diff)
        stats = PatchStats(lines_added, lines_removed, files_touched)

        # Check diff budget
        if stats.total_changed > self.diff_budget_loc:
            return (
                False,
                f"Patch exceeds diff budget: {stats.total_changed} > {self.diff_budget_loc}",
                stats,
            )

        # Check files are in scope
        if self.scope_globs:
            import fnmatch

            for file in files_touched:
                in_scope = False
                for pattern in self.scope_globs:
                    if fnmatch.fnmatch(file, pattern):
                        in_scope = True
                        break
                if not in_scope:
                    return (
                        False,
                        f"File out of scope: {file} not matching {self.scope_globs}",
                        stats,
                    )

        # Check for binary changes
        if not self.allow_binary and "Binary files" in patch_diff:
            return False, "Binary file changes not allowed", stats

        # Check patch can be applied (dry-run)
        can_apply, error = self._check_applies(patch_diff)
        if not can_apply:
            return False, f"Patch would not apply cleanly: {error}", stats

        return True, None, stats

    def _check_applies(self, patch_diff: str) -> tuple[bool, Optional[str]]:
        """Check if patch would apply cleanly using git apply --check."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch_diff)
            patch_file = f.name

        try:
            result = subprocess.run(
                ["git", "apply", "--check", patch_file],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True, None
            return False, result.stderr.strip()

        except Exception as e:
            return False, str(e)

        finally:
            Path(patch_file).unlink(missing_ok=True)


class PatchApplicator:
    """Applies patches to the repository."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def apply(self, patch_diff: str) -> PatchResult:
        """
        Apply a patch to the repository.

        Returns:
            PatchResult indicating success or failure
        """
        if not patch_diff.strip():
            return PatchResult(
                success=False,
                error_message="Empty patch",
                original_diff=patch_diff,
            )

        # Parse stats first
        lines_added, lines_removed, files_touched = parse_unified_diff_stats(patch_diff)
        stats = PatchStats(lines_added, lines_removed, files_touched)

        # Write patch to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch_diff)
            patch_file = f.name

        try:
            # Apply with git apply
            result = subprocess.run(
                ["git", "apply", patch_file],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return PatchResult(
                    success=False,
                    stats=stats,
                    error_message=result.stderr.strip(),
                    original_diff=patch_diff,
                )

            return PatchResult(
                success=True,
                stats=stats,
                original_diff=patch_diff,
            )

        except Exception as e:
            return PatchResult(
                success=False,
                stats=stats,
                error_message=str(e),
                original_diff=patch_diff,
            )

        finally:
            Path(patch_file).unlink(missing_ok=True)

    def apply_with_fallback(self, patch_diff: str) -> PatchResult:
        """
        Apply a patch, falling back to Python patch library if git fails.
        """
        # Try git apply first
        result = self.apply(patch_diff)
        if result.success:
            return result

        # Try Python-based patching as fallback
        try:
            return self._apply_python(patch_diff)
        except Exception as e:
            return PatchResult(
                success=False,
                error_message=f"Both git apply and Python patch failed: {e}",
                original_diff=patch_diff,
            )

    def _apply_python(self, patch_diff: str) -> PatchResult:
        """
        Apply patch using Python-based parsing.

        This is a simple implementation that handles basic unified diffs.
        """
        lines_added, lines_removed, files_touched = parse_unified_diff_stats(patch_diff)
        stats = PatchStats(lines_added, lines_removed, files_touched)

        current_file = None
        hunks: dict[str, list[tuple[int, list[str], list[str]]]] = {}

        lines = patch_diff.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # New file header
            if line.startswith("+++ b/"):
                current_file = line[6:]
                if current_file not in hunks:
                    hunks[current_file] = []
                i += 1
                continue

            # Hunk header
            if line.startswith("@@") and current_file:
                # Parse @@ -start,count +start,count @@
                import re

                match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if match:
                    old_start = int(match.group(1))
                    new_start = int(match.group(2))

                    # Collect hunk lines
                    old_lines = []
                    new_lines = []
                    i += 1

                    while i < len(lines):
                        hunk_line = lines[i]
                        if hunk_line.startswith("@@") or hunk_line.startswith("diff "):
                            break
                        if hunk_line.startswith("-"):
                            old_lines.append(hunk_line[1:])
                        elif hunk_line.startswith("+"):
                            new_lines.append(hunk_line[1:])
                        elif hunk_line.startswith(" "):
                            old_lines.append(hunk_line[1:])
                            new_lines.append(hunk_line[1:])
                        i += 1

                    hunks[current_file].append((old_start, old_lines, new_lines))
                    continue

            i += 1

        # Apply hunks to files
        for file_path, file_hunks in hunks.items():
            full_path = self.repo_path / file_path

            if not full_path.exists():
                # New file - just write the new content
                new_content = []
                for _, _, new_lines in file_hunks:
                    new_content.extend(new_lines)
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "w") as f:
                    f.write("\n".join(new_content))
                continue

            # Existing file - apply hunks
            with open(full_path, "r") as f:
                original = f.readlines()

            # Sort hunks by line number (reverse to apply from bottom up)
            file_hunks.sort(key=lambda h: h[0], reverse=True)

            for start_line, old_lines, new_lines in file_hunks:
                # Convert to 0-indexed
                idx = start_line - 1

                # Remove old lines
                for _ in old_lines:
                    if idx < len(original):
                        original.pop(idx)

                # Insert new lines
                for j, new_line in enumerate(new_lines):
                    original.insert(idx + j, new_line + "\n")

            with open(full_path, "w") as f:
                f.writelines(original)

        return PatchResult(
            success=True,
            stats=stats,
            original_diff=patch_diff,
        )

    def revert(self, patch_diff: str) -> PatchResult:
        """Revert a previously applied patch."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch_diff)
            patch_file = f.name

        try:
            result = subprocess.run(
                ["git", "apply", "--reverse", patch_file],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return PatchResult(
                    success=False,
                    error_message=result.stderr.strip(),
                    original_diff=patch_diff,
                )

            return PatchResult(success=True, original_diff=patch_diff)

        except Exception as e:
            return PatchResult(
                success=False,
                error_message=str(e),
                original_diff=patch_diff,
            )

        finally:
            Path(patch_file).unlink(missing_ok=True)


def apply_patch(
    repo_path: Path,
    patch_diff: str,
    scope_globs: list[str],
    diff_budget_loc: int,
) -> PatchResult:
    """
    Convenience function to validate and apply a patch.

    Args:
        repo_path: Path to the repository
        patch_diff: The unified diff to apply
        scope_globs: Allowed file patterns
        diff_budget_loc: Maximum lines of change

    Returns:
        PatchResult
    """
    # Validate first
    validator = PatchValidator(repo_path, scope_globs, diff_budget_loc)
    is_valid, error, stats = validator.validate(patch_diff)

    if not is_valid:
        return PatchResult(
            success=False,
            stats=stats,
            error_message=error,
            original_diff=patch_diff,
        )

    # Apply
    applicator = PatchApplicator(repo_path)
    return applicator.apply_with_fallback(patch_diff)
