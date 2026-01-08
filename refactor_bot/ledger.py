"""
Task ledger for refactor-bot.

Provides append-only logging of refactoring activity in JSONL format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class BatchStatus(str, Enum):
    """Status of a batch execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOOP = "noop"
    BLOCKED = "blocked"


@dataclass
class LedgerEntry:
    """A single entry in the task ledger."""

    timestamp: str
    batch_id: str
    goal: str
    status: BatchStatus
    files_touched: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    checkpoint_hash: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    verification_passed: bool = True
    retry_count: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "batch_id": self.batch_id,
            "goal": self.goal,
            "status": self.status.value,
            "files_touched": self.files_touched,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "checkpoint_hash": self.checkpoint_hash,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "verification_passed": self.verification_passed,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LedgerEntry":
        return cls(
            timestamp=data["timestamp"],
            batch_id=data["batch_id"],
            goal=data["goal"],
            status=BatchStatus(data["status"]),
            files_touched=data.get("files_touched", []),
            lines_added=data.get("lines_added", 0),
            lines_removed=data.get("lines_removed", 0),
            checkpoint_hash=data.get("checkpoint_hash"),
            error_message=data.get("error_message"),
            duration_seconds=data.get("duration_seconds", 0.0),
            verification_passed=data.get("verification_passed", True),
            retry_count=data.get("retry_count", 0),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, line: str) -> "LedgerEntry":
        return cls.from_dict(json.loads(line))


class TaskLedger:
    """
    Append-only ledger for tracking refactoring progress.

    Stores entries in JSONL format for easy parsing and streaming.
    """

    def __init__(self, ledger_path: Path):
        self.ledger_path = ledger_path
        self.entries: list[LedgerEntry] = []
        self._load()

    def _load(self) -> None:
        """Load existing entries from disk."""
        if not self.ledger_path.exists():
            return

        try:
            with open(self.ledger_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self.entries.append(LedgerEntry.from_json(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass

    def append(self, entry: LedgerEntry) -> None:
        """Append a new entry to the ledger."""
        self.entries.append(entry)

        # Ensure directory exists
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to file
        with open(self.ledger_path, "a") as f:
            f.write(entry.to_json() + "\n")

    def record_start(self, batch_id: str, goal: str) -> LedgerEntry:
        """Record the start of a batch execution."""
        entry = LedgerEntry(
            timestamp=datetime.now().isoformat(),
            batch_id=batch_id,
            goal=goal,
            status=BatchStatus.IN_PROGRESS,
        )
        self.append(entry)
        return entry

    def record_success(
        self,
        batch_id: str,
        goal: str,
        files_touched: list[str],
        lines_added: int,
        lines_removed: int,
        checkpoint_hash: str,
        duration_seconds: float,
    ) -> LedgerEntry:
        """Record successful batch completion."""
        entry = LedgerEntry(
            timestamp=datetime.now().isoformat(),
            batch_id=batch_id,
            goal=goal,
            status=BatchStatus.COMPLETED,
            files_touched=files_touched,
            lines_added=lines_added,
            lines_removed=lines_removed,
            checkpoint_hash=checkpoint_hash,
            duration_seconds=duration_seconds,
            verification_passed=True,
        )
        self.append(entry)
        return entry

    def record_failure(
        self,
        batch_id: str,
        goal: str,
        error_message: str,
        duration_seconds: float,
        retry_count: int = 0,
    ) -> LedgerEntry:
        """Record batch failure."""
        entry = LedgerEntry(
            timestamp=datetime.now().isoformat(),
            batch_id=batch_id,
            goal=goal,
            status=BatchStatus.FAILED,
            error_message=error_message,
            duration_seconds=duration_seconds,
            verification_passed=False,
            retry_count=retry_count,
        )
        self.append(entry)
        return entry

    def record_noop(
        self,
        batch_id: str,
        goal: str,
        reason: str = "",
    ) -> LedgerEntry:
        """Record a noop (no changes needed)."""
        entry = LedgerEntry(
            timestamp=datetime.now().isoformat(),
            batch_id=batch_id,
            goal=goal,
            status=BatchStatus.NOOP,
            error_message=reason if reason else None,
        )
        self.append(entry)
        return entry

    def record_skipped(
        self,
        batch_id: str,
        goal: str,
        reason: str = "",
    ) -> LedgerEntry:
        """Record a skipped batch."""
        entry = LedgerEntry(
            timestamp=datetime.now().isoformat(),
            batch_id=batch_id,
            goal=goal,
            status=BatchStatus.SKIPPED,
            error_message=reason if reason else None,
        )
        self.append(entry)
        return entry

    def get_recent(self, count: int = 10) -> list[LedgerEntry]:
        """Get the most recent entries."""
        return self.entries[-count:]

    def get_by_batch(self, batch_id: str) -> list[LedgerEntry]:
        """Get all entries for a specific batch."""
        return [e for e in self.entries if e.batch_id == batch_id]

    def get_last_checkpoint(self) -> Optional[str]:
        """Get the last successful checkpoint hash."""
        for entry in reversed(self.entries):
            if entry.checkpoint_hash and entry.status == BatchStatus.COMPLETED:
                return entry.checkpoint_hash
        return None

    def get_statistics(self) -> dict:
        """Get statistics about the refactoring run."""
        completed = [e for e in self.entries if e.status == BatchStatus.COMPLETED]
        failed = [e for e in self.entries if e.status == BatchStatus.FAILED]
        noop = [e for e in self.entries if e.status == BatchStatus.NOOP]
        skipped = [e for e in self.entries if e.status == BatchStatus.SKIPPED]

        total_lines_added = sum(e.lines_added for e in completed)
        total_lines_removed = sum(e.lines_removed for e in completed)
        total_files = len(set(f for e in completed for f in e.files_touched))
        total_duration = sum(e.duration_seconds for e in self.entries)

        return {
            "total_batches": len(set(e.batch_id for e in self.entries)),
            "completed": len(completed),
            "failed": len(failed),
            "noop": len(noop),
            "skipped": len(skipped),
            "total_lines_added": total_lines_added,
            "total_lines_removed": total_lines_removed,
            "total_files_touched": total_files,
            "total_duration_seconds": total_duration,
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary."""
        stats = self.get_statistics()
        lines = [
            "=== Refactoring Summary ===",
            f"Batches: {stats['completed']} completed, {stats['failed']} failed, "
            f"{stats['noop']} noop, {stats['skipped']} skipped",
            f"Changes: +{stats['total_lines_added']} -{stats['total_lines_removed']} lines",
            f"Files touched: {stats['total_files_touched']}",
            f"Total time: {stats['total_duration_seconds']:.1f}s",
        ]
        return "\n".join(lines)
