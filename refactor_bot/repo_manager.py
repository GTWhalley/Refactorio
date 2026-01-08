"""
Repository management for refactor-bot.

Handles git operations, worktree creation, and repository validation.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from git import Repo, InvalidGitRepositoryError, GitCommandError
from rich.console import Console

from refactor_bot.config import WORKTREES_DIR, ensure_directories
from refactor_bot.util import generate_run_id, is_git_repo

console = Console()


@dataclass
class RepoInfo:
    """Information about a repository."""

    path: Path
    name: str
    is_git: bool
    current_branch: Optional[str]
    has_uncommitted_changes: bool
    remote_url: Optional[str]
    commit_hash: Optional[str]
    file_count: int


class RepoManager:
    """Manages repository operations for refactor-bot."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path.resolve()
        self.run_id = generate_run_id()
        self.worktree_path: Optional[Path] = None
        self.safety_branch: Optional[str] = None
        self._repo: Optional[Repo] = None

    @property
    def repo(self) -> Optional[Repo]:
        """Get the git.Repo object if this is a git repository."""
        if self._repo is None and is_git_repo(self.repo_path):
            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError:
                self._repo = None
        return self._repo

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate that the repository is ready for refactoring.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check path exists
        if not self.repo_path.exists():
            errors.append(f"Repository path does not exist: {self.repo_path}")
            return False, errors

        if not self.repo_path.is_dir():
            errors.append(f"Repository path is not a directory: {self.repo_path}")
            return False, errors

        # Check it's not empty
        if not any(self.repo_path.iterdir()):
            errors.append(f"Repository directory is empty: {self.repo_path}")
            return False, errors

        # If it's a git repo, check for issues
        if is_git_repo(self.repo_path):
            try:
                repo = Repo(self.repo_path)

                # Check for uncommitted changes (warning, not error)
                if repo.is_dirty(untracked_files=True):
                    errors.append(
                        "Repository has uncommitted changes. "
                        "Consider committing or stashing before refactoring."
                    )

                # Check we're not in a detached HEAD state
                if repo.head.is_detached:
                    errors.append(
                        "Repository is in detached HEAD state. "
                        "Please checkout a branch before refactoring."
                    )

            except InvalidGitRepositoryError:
                errors.append("Directory appears to be a git repo but is corrupted.")
                return False, errors
            except Exception as e:
                errors.append(f"Error accessing git repository: {e}")
                return False, errors

        return len(errors) == 0, errors

    def get_info(self) -> RepoInfo:
        """Get detailed information about the repository."""
        file_count = sum(1 for _ in self.repo_path.rglob("*") if _.is_file())

        if self.repo:
            try:
                current_branch = self.repo.active_branch.name
            except TypeError:
                current_branch = None

            try:
                remote_url = self.repo.remotes.origin.url if self.repo.remotes else None
            except Exception:
                remote_url = None

            try:
                commit_hash = self.repo.head.commit.hexsha[:8]
            except Exception:
                commit_hash = None

            return RepoInfo(
                path=self.repo_path,
                name=self.repo_path.name,
                is_git=True,
                current_branch=current_branch,
                has_uncommitted_changes=self.repo.is_dirty(untracked_files=True),
                remote_url=remote_url,
                commit_hash=commit_hash,
                file_count=file_count,
            )
        else:
            return RepoInfo(
                path=self.repo_path,
                name=self.repo_path.name,
                is_git=False,
                current_branch=None,
                has_uncommitted_changes=False,
                remote_url=None,
                commit_hash=None,
                file_count=file_count,
            )

    def create_safety_branch(self) -> str:
        """Create a safety branch before making changes."""
        if not self.repo:
            raise ValueError("Cannot create safety branch: not a git repository")

        self.safety_branch = f"refactor-bot/{self.run_id}"

        try:
            # Create the branch from current HEAD
            self.repo.create_head(self.safety_branch)
            return self.safety_branch
        except GitCommandError as e:
            raise RuntimeError(f"Failed to create safety branch: {e}")

    def create_worktree(self) -> Path:
        """
        Create a git worktree for safe refactoring.

        For non-git repos, creates a copy instead.
        """
        ensure_directories()

        self.worktree_path = WORKTREES_DIR / self.run_id

        if self.repo:
            # Create a worktree for git repos
            if not self.safety_branch:
                self.create_safety_branch()

            try:
                self.repo.git.worktree(
                    "add",
                    str(self.worktree_path),
                    self.safety_branch,
                )
            except GitCommandError as e:
                raise RuntimeError(f"Failed to create worktree: {e}")
        else:
            # For non-git repos, copy the directory and init git
            shutil.copytree(
                self.repo_path,
                self.worktree_path,
                ignore=shutil.ignore_patterns(
                    ".git",
                    "node_modules",
                    "__pycache__",
                    ".venv",
                    "venv",
                    ".tox",
                    "dist",
                    "build",
                ),
            )

            # Initialize a git repo in the copy for tracking
            new_repo = Repo.init(self.worktree_path)
            new_repo.index.add("*")
            new_repo.index.commit("Initial commit (refactor-bot baseline)")
            self._repo = new_repo

        return self.worktree_path

    def checkpoint_commit(self, batch_id: str, goal: str) -> str:
        """Create a checkpoint commit after a successful batch."""
        if not self.worktree_path:
            raise ValueError("No worktree created")

        worktree_repo = Repo(self.worktree_path)

        # Stage all changes
        worktree_repo.index.add("*")

        # Create commit
        message = f"checkpoint: {batch_id} - {goal}"
        commit = worktree_repo.index.commit(message)

        return commit.hexsha

    def get_checkpoint_commits(self) -> list[tuple[str, str, str]]:
        """Get all checkpoint commits in the worktree."""
        if not self.worktree_path:
            return []

        worktree_repo = Repo(self.worktree_path)
        checkpoints = []

        for commit in worktree_repo.iter_commits():
            if commit.message.startswith("checkpoint:"):
                checkpoints.append((
                    commit.hexsha[:8],
                    commit.message.strip(),
                    commit.committed_datetime.isoformat(),
                ))

        return checkpoints

    def revert_to_checkpoint(self, commit_hash: str) -> None:
        """Revert the worktree to a specific checkpoint."""
        if not self.worktree_path:
            raise ValueError("No worktree created")

        worktree_repo = Repo(self.worktree_path)

        try:
            worktree_repo.git.reset("--hard", commit_hash)
        except GitCommandError as e:
            raise RuntimeError(f"Failed to revert to checkpoint: {e}")

    def revert_to_baseline(self) -> None:
        """Revert the worktree to the initial baseline state."""
        if not self.worktree_path:
            raise ValueError("No worktree created")

        worktree_repo = Repo(self.worktree_path)

        # Find the first commit (baseline)
        commits = list(worktree_repo.iter_commits())
        if commits:
            baseline = commits[-1]
            worktree_repo.git.reset("--hard", baseline.hexsha)

    def cleanup_worktree(self) -> None:
        """Remove the worktree after refactoring is complete or cancelled."""
        if self.worktree_path and self.worktree_path.exists():
            # If this was a git worktree, remove it properly
            if self.repo and self.safety_branch:
                try:
                    self.repo.git.worktree("remove", str(self.worktree_path), "--force")
                except GitCommandError:
                    # Fallback to manual removal
                    shutil.rmtree(self.worktree_path, ignore_errors=True)
            else:
                shutil.rmtree(self.worktree_path, ignore_errors=True)

        self.worktree_path = None

    def merge_to_main(self) -> bool:
        """
        Merge the refactored worktree back to the main repository.

        Returns True if successful.
        """
        if not self.repo or not self.worktree_path:
            raise ValueError("Cannot merge: missing repository or worktree")

        worktree_repo = Repo(self.worktree_path)

        try:
            # Get the current branch in the worktree
            worktree_branch = worktree_repo.active_branch.name

            # Push the worktree changes to the safety branch in main repo
            # (they should already be on the same branch)

            # Switch main repo to original branch and merge
            original_branch = self.repo.active_branch

            # Fetch changes from worktree
            # The worktree is on the safety branch, so just need to merge in main repo

            self.repo.git.merge(self.safety_branch)
            return True

        except GitCommandError as e:
            raise RuntimeError(f"Failed to merge changes: {e}")

    def get_diff_from_baseline(self) -> str:
        """Get the full diff from baseline to current state."""
        if not self.worktree_path:
            return ""

        worktree_repo = Repo(self.worktree_path)

        # Find baseline (first commit)
        commits = list(worktree_repo.iter_commits())
        if len(commits) < 2:
            return ""

        baseline = commits[-1]
        return worktree_repo.git.diff(baseline.hexsha, "HEAD")
