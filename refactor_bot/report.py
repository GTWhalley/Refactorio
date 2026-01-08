"""
Report generation for refactor-bot.

Generates final reports summarizing refactoring results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from refactor_bot.ledger import TaskLedger, BatchStatus
from refactor_bot.planner import RefactorPlan
from refactor_bot.util import format_duration


@dataclass
class RefactorReport:
    """Final report for a refactoring run."""

    run_id: str
    repo_path: str
    repo_name: str
    started_at: str
    completed_at: str
    duration_seconds: float

    # Results
    batches_total: int
    batches_completed: int
    batches_failed: int
    batches_skipped: int
    batches_noop: int

    # Changes
    lines_added: int
    lines_removed: int
    files_touched: list[str]

    # Backup info
    backup_path: str
    worktree_path: str
    final_commit: Optional[str]

    # Status
    success: bool
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "repo_path": self.repo_path,
            "repo_name": self.repo_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "batches": {
                "total": self.batches_total,
                "completed": self.batches_completed,
                "failed": self.batches_failed,
                "skipped": self.batches_skipped,
                "noop": self.batches_noop,
            },
            "changes": {
                "lines_added": self.lines_added,
                "lines_removed": self.lines_removed,
                "files_touched": self.files_touched,
            },
            "backup_path": self.backup_path,
            "worktree_path": self.worktree_path,
            "final_commit": self.final_commit,
            "success": self.success,
            "error_message": self.error_message,
        }

    def save(self, path: Path) -> None:
        """Save report to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "RefactorReport":
        """Load report from JSON file."""
        with open(path) as f:
            data = json.load(f)

        return cls(
            run_id=data["run_id"],
            repo_path=data["repo_path"],
            repo_name=data["repo_name"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            duration_seconds=data["duration_seconds"],
            batches_total=data["batches"]["total"],
            batches_completed=data["batches"]["completed"],
            batches_failed=data["batches"]["failed"],
            batches_skipped=data["batches"]["skipped"],
            batches_noop=data["batches"]["noop"],
            lines_added=data["changes"]["lines_added"],
            lines_removed=data["changes"]["lines_removed"],
            files_touched=data["changes"]["files_touched"],
            backup_path=data["backup_path"],
            worktree_path=data["worktree_path"],
            final_commit=data.get("final_commit"),
            success=data["success"],
            error_message=data.get("error_message"),
        )


class ReportGenerator:
    """Generates reports from refactoring data."""

    def __init__(
        self,
        run_id: str,
        repo_path: Path,
        ledger: TaskLedger,
        plan: Optional[RefactorPlan] = None,
    ):
        self.run_id = run_id
        self.repo_path = repo_path
        self.ledger = ledger
        self.plan = plan

    def generate(
        self,
        started_at: datetime,
        backup_path: Path,
        worktree_path: Path,
        final_commit: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> RefactorReport:
        """Generate the final report."""
        completed_at = datetime.now()
        stats = self.ledger.get_statistics()

        # Collect all touched files
        files_touched = set()
        for entry in self.ledger.entries:
            if entry.status == BatchStatus.COMPLETED:
                files_touched.update(entry.files_touched)

        success = stats["failed"] == 0 and error_message is None

        return RefactorReport(
            run_id=self.run_id,
            repo_path=str(self.repo_path),
            repo_name=self.repo_path.name,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_seconds=(completed_at - started_at).total_seconds(),
            batches_total=self.plan.batches.__len__() if self.plan else stats["total_batches"],
            batches_completed=stats["completed"],
            batches_failed=stats["failed"],
            batches_skipped=stats["skipped"],
            batches_noop=stats["noop"],
            lines_added=stats["total_lines_added"],
            lines_removed=stats["total_lines_removed"],
            files_touched=sorted(files_touched),
            backup_path=str(backup_path),
            worktree_path=str(worktree_path),
            final_commit=final_commit,
            success=success,
            error_message=error_message,
        )

    def format_terminal_report(self, report: RefactorReport) -> str:
        """Format report for terminal display."""
        lines = [
            "",
            "╔══════════════════════════════════════════════════════════════════╗",
            "║                      REFACTORING REPORT                          ║",
            "╠══════════════════════════════════════════════════════════════════╣",
            f"║  Run ID: {report.run_id:<55} ║",
            f"║  Repository: {report.repo_name:<51} ║",
            f"║  Duration: {format_duration(report.duration_seconds):<53} ║",
            "╠══════════════════════════════════════════════════════════════════╣",
            "║  BATCH RESULTS                                                   ║",
            "╟──────────────────────────────────────────────────────────────────╢",
        ]

        # Batch results
        completed_pct = (
            report.batches_completed / report.batches_total * 100
            if report.batches_total > 0
            else 0
        )
        lines.append(
            f"║  Total:     {report.batches_total:<54} ║"
        )
        lines.append(
            f"║  Completed: {report.batches_completed:<4} ({completed_pct:.0f}%){' ' * 45} ║"
        )
        lines.append(
            f"║  Failed:    {report.batches_failed:<54} ║"
        )
        lines.append(
            f"║  Skipped:   {report.batches_skipped:<54} ║"
        )
        lines.append(
            f"║  No-op:     {report.batches_noop:<54} ║"
        )

        lines.extend([
            "╠══════════════════════════════════════════════════════════════════╣",
            "║  CHANGES                                                         ║",
            "╟──────────────────────────────────────────────────────────────────╢",
            f"║  Lines added:   +{report.lines_added:<51} ║",
            f"║  Lines removed: -{report.lines_removed:<51} ║",
            f"║  Files touched: {len(report.files_touched):<52} ║",
        ])

        # List files (truncated if too many)
        if report.files_touched:
            lines.append("╟──────────────────────────────────────────────────────────────────╢")
            for file in report.files_touched[:10]:
                truncated = file if len(file) <= 60 else "..." + file[-57:]
                lines.append(f"║    {truncated:<62} ║")
            if len(report.files_touched) > 10:
                lines.append(
                    f"║    ... and {len(report.files_touched) - 10} more files{' ' * 44} ║"
                )

        lines.extend([
            "╠══════════════════════════════════════════════════════════════════╣",
            "║  BACKUP                                                          ║",
            "╟──────────────────────────────────────────────────────────────────╢",
        ])

        backup_display = report.backup_path
        if len(backup_display) > 60:
            backup_display = "..." + backup_display[-57:]
        lines.append(f"║  {backup_display:<64} ║")

        # Status
        lines.append("╠══════════════════════════════════════════════════════════════════╣")
        if report.success:
            lines.append("║  STATUS: ✓ SUCCESS                                               ║")
        else:
            lines.append("║  STATUS: ✗ FAILED                                                ║")
            if report.error_message:
                error_display = report.error_message[:60]
                lines.append(f"║  Error: {error_display:<57} ║")

        lines.append("╚══════════════════════════════════════════════════════════════════╝")
        lines.append("")

        return "\n".join(lines)

    def format_markdown_report(self, report: RefactorReport) -> str:
        """Format report as Markdown."""
        lines = [
            "# Refactoring Report",
            "",
            f"**Run ID:** `{report.run_id}`",
            f"**Repository:** {report.repo_name}",
            f"**Started:** {report.started_at}",
            f"**Completed:** {report.completed_at}",
            f"**Duration:** {format_duration(report.duration_seconds)}",
            "",
            "## Batch Results",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Total | {report.batches_total} |",
            f"| Completed | {report.batches_completed} |",
            f"| Failed | {report.batches_failed} |",
            f"| Skipped | {report.batches_skipped} |",
            f"| No-op | {report.batches_noop} |",
            "",
            "## Changes",
            "",
            f"- **Lines added:** +{report.lines_added}",
            f"- **Lines removed:** -{report.lines_removed}",
            f"- **Files touched:** {len(report.files_touched)}",
            "",
        ]

        if report.files_touched:
            lines.append("### Modified Files")
            lines.append("")
            for file in report.files_touched:
                lines.append(f"- `{file}`")
            lines.append("")

        lines.extend([
            "## Backup",
            "",
            f"Backup stored at: `{report.backup_path}`",
            "",
            "## Status",
            "",
        ])

        if report.success:
            lines.append("**Status:** ✓ Success")
        else:
            lines.append("**Status:** ✗ Failed")
            if report.error_message:
                lines.extend([
                    "",
                    "**Error:**",
                    f"```",
                    report.error_message,
                    "```",
                ])

        return "\n".join(lines)
