"""
Backup and rollback functionality for refactor-bot.

Provides two rollback mechanisms:
1. Git safety branch + worktree
2. Full backup artifacts (bundle + tar.gz)
"""

from __future__ import annotations

import shutil
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from git import Repo, InvalidGitRepositoryError

from refactor_bot.config import BACKUPS_DIR, ensure_directories
from refactor_bot.util import is_git_repo, get_repo_name, format_size


@dataclass
class BackupInfo:
    """Information about a backup."""

    run_id: str
    repo_name: str
    backup_path: Path
    bundle_path: Optional[Path]
    archive_path: Optional[Path]
    created_at: datetime
    size_bytes: int

    def __str__(self) -> str:
        return (
            f"Backup {self.run_id}\n"
            f"  Repository: {self.repo_name}\n"
            f"  Path: {self.backup_path}\n"
            f"  Size: {format_size(self.size_bytes)}\n"
            f"  Created: {self.created_at.isoformat()}"
        )


class BackupManager:
    """Manages backup creation and restoration for refactor-bot."""

    def __init__(self, repo_path: Path, run_id: str):
        self.repo_path = repo_path.resolve()
        self.run_id = run_id
        self.repo_name = get_repo_name(repo_path)
        self.backup_path = BACKUPS_DIR / self.repo_name / self.run_id
        self.bundle_path: Optional[Path] = None
        self.archive_path: Optional[Path] = None

    def create_backup(self) -> BackupInfo:
        """
        Create a full backup of the repository.

        Creates both a git bundle (if git repo) and a tar.gz archive.
        """
        ensure_directories()

        # Create backup directory
        self.backup_path.mkdir(parents=True, exist_ok=True)

        # Create git bundle if this is a git repo
        if is_git_repo(self.repo_path):
            self.bundle_path = self._create_git_bundle()

        # Always create a tar.gz archive as fallback
        self.archive_path = self._create_archive()

        # Calculate total size
        total_size = 0
        if self.bundle_path and self.bundle_path.exists():
            total_size += self.bundle_path.stat().st_size
        if self.archive_path and self.archive_path.exists():
            total_size += self.archive_path.stat().st_size

        # Save metadata
        self._save_metadata()

        return BackupInfo(
            run_id=self.run_id,
            repo_name=self.repo_name,
            backup_path=self.backup_path,
            bundle_path=self.bundle_path,
            archive_path=self.archive_path,
            created_at=datetime.now(),
            size_bytes=total_size,
        )

    def _create_git_bundle(self) -> Path:
        """Create a git bundle backup."""
        bundle_path = self.backup_path / "backup.bundle"

        try:
            repo = Repo(self.repo_path)
            repo.git.bundle("create", str(bundle_path), "--all")
            return bundle_path
        except Exception as e:
            raise RuntimeError(f"Failed to create git bundle: {e}")

    def _create_archive(self) -> Path:
        """Create a tar.gz archive backup."""
        archive_path = self.backup_path / "backup.tar.gz"

        def exclude_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
            """Filter out unnecessary files from the archive."""
            excluded = [
                ".git",
                "node_modules",
                "__pycache__",
                ".venv",
                "venv",
                ".tox",
                "dist",
                "build",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            ]
            for pattern in excluded:
                if pattern in tarinfo.name.split("/"):
                    return None
            return tarinfo

        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(
                    self.repo_path,
                    arcname=self.repo_name,
                    filter=exclude_filter,
                )
            return archive_path
        except Exception as e:
            raise RuntimeError(f"Failed to create archive: {e}")

    def _save_metadata(self) -> None:
        """Save backup metadata to a JSON file."""
        import json

        metadata = {
            "run_id": self.run_id,
            "repo_name": self.repo_name,
            "repo_path": str(self.repo_path),
            "created_at": datetime.now().isoformat(),
            "has_bundle": self.bundle_path is not None,
            "has_archive": self.archive_path is not None,
        }

        metadata_path = self.backup_path / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    def restore_from_bundle(self, target_path: Optional[Path] = None) -> Path:
        """
        Restore repository from git bundle.

        Args:
            target_path: Where to restore. If None, restores to original location.

        Returns:
            Path to restored repository.
        """
        if not self.bundle_path or not self.bundle_path.exists():
            # Try to find bundle in backup path
            bundle = self.backup_path / "backup.bundle"
            if not bundle.exists():
                raise FileNotFoundError("No git bundle found in backup")
            self.bundle_path = bundle

        target = target_path or self.repo_path

        if target.exists():
            # Backup existing before overwrite
            backup_existing = target.parent / f"{target.name}.pre-restore"
            if backup_existing.exists():
                shutil.rmtree(backup_existing)
            shutil.move(str(target), str(backup_existing))

        try:
            # Clone from bundle
            Repo.clone_from(
                str(self.bundle_path),
                str(target),
            )
            return target
        except Exception as e:
            # Restore the original if clone failed
            if backup_existing.exists():
                shutil.move(str(backup_existing), str(target))
            raise RuntimeError(f"Failed to restore from bundle: {e}")

    def restore_from_archive(self, target_path: Optional[Path] = None) -> Path:
        """
        Restore repository from tar.gz archive.

        Args:
            target_path: Where to restore. If None, restores to original location.

        Returns:
            Path to restored repository.
        """
        if not self.archive_path or not self.archive_path.exists():
            # Try to find archive in backup path
            archive = self.backup_path / "backup.tar.gz"
            if not archive.exists():
                raise FileNotFoundError("No archive found in backup")
            self.archive_path = archive

        target = target_path or self.repo_path.parent

        if self.repo_path.exists():
            # Backup existing before overwrite
            backup_existing = self.repo_path.parent / f"{self.repo_path.name}.pre-restore"
            if backup_existing.exists():
                shutil.rmtree(backup_existing)
            shutil.move(str(self.repo_path), str(backup_existing))

        try:
            with tarfile.open(self.archive_path, "r:gz") as tar:
                tar.extractall(target)
            return target / self.repo_name
        except Exception as e:
            # Restore the original if extraction failed
            if backup_existing.exists():
                shutil.move(str(backup_existing), str(self.repo_path))
            raise RuntimeError(f"Failed to restore from archive: {e}")

    def cleanup(self) -> None:
        """Remove the backup files."""
        if self.backup_path.exists():
            shutil.rmtree(self.backup_path)

    @classmethod
    def list_backups(cls, repo_name: Optional[str] = None) -> list[BackupInfo]:
        """List all available backups, optionally filtered by repo name."""
        import json

        ensure_directories()
        backups = []

        if repo_name:
            search_path = BACKUPS_DIR / repo_name
            if not search_path.exists():
                return []
            repos = [search_path]
        else:
            repos = [d for d in BACKUPS_DIR.iterdir() if d.is_dir()]

        for repo_dir in repos:
            for backup_dir in repo_dir.iterdir():
                if not backup_dir.is_dir():
                    continue

                metadata_path = backup_dir / "metadata.json"
                if not metadata_path.exists():
                    continue

                try:
                    with open(metadata_path) as f:
                        metadata = json.load(f)

                    bundle_path = backup_dir / "backup.bundle"
                    archive_path = backup_dir / "backup.tar.gz"

                    size = 0
                    if bundle_path.exists():
                        size += bundle_path.stat().st_size
                    if archive_path.exists():
                        size += archive_path.stat().st_size

                    backups.append(BackupInfo(
                        run_id=metadata["run_id"],
                        repo_name=metadata["repo_name"],
                        backup_path=backup_dir,
                        bundle_path=bundle_path if bundle_path.exists() else None,
                        archive_path=archive_path if archive_path.exists() else None,
                        created_at=datetime.fromisoformat(metadata["created_at"]),
                        size_bytes=size,
                    ))
                except (json.JSONDecodeError, KeyError):
                    continue

        # Sort by creation date, newest first
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    @classmethod
    def get_backup(cls, run_id: str) -> Optional[BackupInfo]:
        """Get a specific backup by run ID."""
        all_backups = cls.list_backups()
        for backup in all_backups:
            if backup.run_id == run_id:
                return backup
        return None


def rollback(run_id: str, use_bundle: bool = True) -> Path:
    """
    Rollback a repository to a specific backup.

    Args:
        run_id: The run ID of the backup to restore
        use_bundle: If True, prefer git bundle; if False, use archive

    Returns:
        Path to the restored repository
    """
    backup = BackupManager.get_backup(run_id)
    if not backup:
        raise ValueError(f"No backup found with run_id: {run_id}")

    manager = BackupManager(Path(backup.backup_path), run_id)
    manager.bundle_path = backup.bundle_path
    manager.archive_path = backup.archive_path

    if use_bundle and backup.bundle_path:
        return manager.restore_from_bundle()
    elif backup.archive_path:
        return manager.restore_from_archive()
    else:
        raise ValueError("No valid backup files found")
