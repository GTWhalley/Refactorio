"""
Security review module for Refactorio.

Provides post-refactor security scanning using Claude to identify
potential vulnerabilities in changed code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from refactor_bot.claude_driver import ClaudeDriver, ClaudeResponse


class Severity(str, Enum):
    """Severity levels for security findings."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    """Categories of security vulnerabilities."""
    INJECTION = "injection"
    AUTH = "auth"
    DATA_EXPOSURE = "data_exposure"
    CRYPTO = "crypto"
    INPUT_VALIDATION = "input_validation"
    RACE_CONDITION = "race_condition"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    OTHER = "other"


class OverallRisk(str, Enum):
    """Overall risk assessment levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class SecurityFinding:
    """A single security finding."""
    severity: Severity
    category: Category
    file: str
    line: int
    title: str
    description: str
    recommendation: str
    cwe: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "SecurityFinding":
        return cls(
            severity=Severity(data["severity"]),
            category=Category(data["category"]),
            file=data["file"],
            line=data["line"],
            title=data["title"],
            description=data["description"],
            recommendation=data["recommendation"],
            cwe=data.get("cwe"),
        )

    def to_dict(self) -> dict:
        result = {
            "severity": self.severity.value,
            "category": self.category.value,
            "file": self.file,
            "line": self.line,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
        }
        if self.cwe:
            result["cwe"] = self.cwe
        return result


@dataclass
class SecuritySummary:
    """Summary of security findings by severity."""
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0

    @property
    def total(self) -> int:
        return self.high + self.medium + self.low + self.info

    @classmethod
    def from_dict(cls, data: dict) -> "SecuritySummary":
        return cls(
            high=data.get("high", 0),
            medium=data.get("medium", 0),
            low=data.get("low", 0),
            info=data.get("info", 0),
        )

    def to_dict(self) -> dict:
        return {
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
            "info": self.info,
            "total": self.total,
        }


@dataclass
class SecurityReviewResult:
    """Result of a security review."""
    success: bool
    findings: list[SecurityFinding] = field(default_factory=list)
    summary: SecuritySummary = field(default_factory=SecuritySummary)
    overall_risk: OverallRisk = OverallRisk.NONE
    notes: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_response(cls, response: ClaudeResponse) -> "SecurityReviewResult":
        """Create a SecurityReviewResult from a Claude response."""
        if not response.success:
            return cls(
                success=False,
                error_message=response.error_message,
            )

        output = response.structured_output
        if not output:
            return cls(
                success=False,
                error_message="No structured output from security review",
            )

        findings = [
            SecurityFinding.from_dict(f)
            for f in output.get("findings", [])
        ]

        summary = SecuritySummary.from_dict(output.get("summary", {}))
        overall_risk = OverallRisk(output.get("overall_risk", "none"))

        return cls(
            success=True,
            findings=findings,
            summary=summary,
            overall_risk=overall_risk,
            notes=output.get("notes"),
        )

    @classmethod
    def from_error(cls, error: str) -> "SecurityReviewResult":
        return cls(success=False, error_message=error)

    def has_blocking_issues(self, block_on_high: bool = True) -> bool:
        """Check if there are issues that should block the merge."""
        if block_on_high and self.summary.high > 0:
            return True
        if self.overall_risk == OverallRisk.CRITICAL:
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary.to_dict(),
            "overall_risk": self.overall_risk.value,
            "notes": self.notes,
            "error_message": self.error_message,
        }

    def save(self, path: Path) -> None:
        """Save the review result to a JSON file."""
        path.write_text(json.dumps(self.to_dict(), indent=2))


class SecurityReviewer:
    """
    Security reviewer that scans changed code for vulnerabilities.

    Uses Claude to analyze code changes and identify potential security issues.
    """

    def __init__(
        self,
        claude_driver: ClaudeDriver,
        repo_path: Path,
    ):
        self.claude_driver = claude_driver
        self.repo_path = repo_path

    def review_changes(
        self,
        changed_files: list[str],
        context_summary: Optional[str] = None,
    ) -> SecurityReviewResult:
        """
        Review changed files for security vulnerabilities.

        Args:
            changed_files: List of file paths that were changed
            context_summary: Optional summary of what the changes were for

        Returns:
            SecurityReviewResult with findings
        """
        if not changed_files:
            return SecurityReviewResult(
                success=True,
                notes="No files to review",
            )

        # Build context with changed file contents
        context = self._build_context(changed_files, context_summary)

        # Call Claude security reviewer
        response = self.claude_driver.call_security(context)

        return SecurityReviewResult.from_response(response)

    def _build_context(
        self,
        changed_files: list[str],
        context_summary: Optional[str] = None,
    ) -> str:
        """Build the context prompt for security review."""
        parts = ["# Security Review Request\n"]

        if context_summary:
            parts.append(f"## Context\n{context_summary}\n")

        parts.append("## Changed Files\n")
        parts.append(f"Total files to review: {len(changed_files)}\n")

        # Include file contents
        total_lines = 0
        max_lines = 2000  # Budget for context

        for file_path in changed_files:
            full_path = self.repo_path / file_path
            if not full_path.exists():
                continue

            try:
                content = full_path.read_text()
                lines = content.split("\n")

                # Check budget
                if total_lines + len(lines) > max_lines:
                    # Truncate this file
                    remaining = max_lines - total_lines
                    if remaining > 50:
                        lines = lines[:remaining]
                        content = "\n".join(lines)
                        parts.append(f"\n### {file_path} (truncated)\n```\n{content}\n```\n")
                        total_lines = max_lines
                    break

                parts.append(f"\n### {file_path}\n```\n{content}\n```\n")
                total_lines += len(lines)

            except Exception as e:
                parts.append(f"\n### {file_path}\nError reading file: {e}\n")

        parts.append("\n## Instructions\n")
        parts.append(
            "Review the above code changes for security vulnerabilities. "
            "Focus on:\n"
            "- Injection vulnerabilities (SQL, command, XSS)\n"
            "- Authentication and authorization issues\n"
            "- Data exposure and sensitive data handling\n"
            "- Cryptographic weaknesses\n"
            "- Input validation issues\n"
            "- Race conditions\n"
            "\n"
            "Return your findings in the required JSON schema format."
        )

        return "\n".join(parts)


def format_security_report(result: SecurityReviewResult) -> str:
    """Format a security review result for terminal display."""
    lines = []
    lines.append("=" * 60)
    lines.append("SECURITY REVIEW REPORT")
    lines.append("=" * 60)

    if not result.success:
        lines.append(f"\nError: {result.error_message}")
        return "\n".join(lines)

    # Summary
    lines.append(f"\nOverall Risk: {result.overall_risk.value.upper()}")
    lines.append(f"\nFindings Summary:")
    lines.append(f"  High:   {result.summary.high}")
    lines.append(f"  Medium: {result.summary.medium}")
    lines.append(f"  Low:    {result.summary.low}")
    lines.append(f"  Info:   {result.summary.info}")
    lines.append(f"  Total:  {result.summary.total}")

    if result.notes:
        lines.append(f"\nNotes: {result.notes}")

    # Individual findings
    if result.findings:
        lines.append("\n" + "-" * 60)
        lines.append("DETAILED FINDINGS")
        lines.append("-" * 60)

        for i, finding in enumerate(result.findings, 1):
            lines.append(f"\n[{i}] {finding.severity.value.upper()}: {finding.title}")
            lines.append(f"    File: {finding.file}:{finding.line}")
            lines.append(f"    Category: {finding.category.value}")
            if finding.cwe:
                lines.append(f"    CWE: {finding.cwe}")
            lines.append(f"    Description: {finding.description}")
            lines.append(f"    Recommendation: {finding.recommendation}")
    else:
        lines.append("\nNo security vulnerabilities identified.")

    lines.append("\n" + "=" * 60)

    return "\n".join(lines)
