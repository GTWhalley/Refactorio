"""
Verification system for refactor-bot.

Handles running tests, linting, type checking, and other verification commands.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from refactor_bot.config import Config
from refactor_bot.util import format_duration


class VerifierLevel(str, Enum):
    """Level of verification to run."""

    FAST = "fast"
    FULL = "full"


class VerificationStatus(str, Enum):
    """Status of a verification result."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class CommandResult:
    """Result of running a single verification command."""

    command: str
    status: VerificationStatus
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    started_at: datetime

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASSED

    def summary(self) -> str:
        status_icon = {
            VerificationStatus.PASSED: "✓",
            VerificationStatus.FAILED: "✗",
            VerificationStatus.SKIPPED: "○",
            VerificationStatus.ERROR: "!",
        }
        return (
            f"{status_icon[self.status]} {self.command} "
            f"({format_duration(self.duration_seconds)})"
        )


@dataclass
class VerificationResult:
    """Result of running a full verification suite."""

    level: VerifierLevel
    commands: list[CommandResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @property
    def passed(self) -> bool:
        return all(cmd.passed for cmd in self.commands)

    @property
    def failed_commands(self) -> list[CommandResult]:
        return [cmd for cmd in self.commands if not cmd.passed]

    @property
    def total_duration(self) -> float:
        return sum(cmd.duration_seconds for cmd in self.commands)

    def summary(self) -> str:
        passed = sum(1 for cmd in self.commands if cmd.passed)
        total = len(self.commands)
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Verification {status}: {passed}/{total} commands passed "
            f"({format_duration(self.total_duration)})"
        )


class Verifier:
    """Runs verification commands against a repository."""

    def __init__(self, repo_path: Path, config: Config):
        self.repo_path = repo_path
        self.config = config
        self.results_dir = repo_path / ".refactor-bot" / "verification"
        self.baseline_result: Optional[VerificationResult] = None

    def run_command(self, command: str, timeout: int = 300) -> CommandResult:
        """Run a single verification command."""
        started_at = datetime.now()
        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            duration = time.time() - start_time
            status = (
                VerificationStatus.PASSED
                if result.returncode == 0
                else VerificationStatus.FAILED
            )

            return CommandResult(
                command=command,
                status=status,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=duration,
                started_at=started_at,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return CommandResult(
                command=command,
                status=VerificationStatus.ERROR,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                duration_seconds=duration,
                started_at=started_at,
            )

        except Exception as e:
            duration = time.time() - start_time
            return CommandResult(
                command=command,
                status=VerificationStatus.ERROR,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=duration,
                started_at=started_at,
            )

    def run_fast(self) -> VerificationResult:
        """Run fast verification (tests + lint)."""
        result = VerificationResult(
            level=VerifierLevel.FAST,
            started_at=datetime.now(),
        )

        for command in self.config.fast_verifier:
            cmd_result = self.run_command(command)
            result.commands.append(cmd_result)

            # Stop on first failure for fast verification
            if not cmd_result.passed:
                break

        result.completed_at = datetime.now()
        return result

    def run_full(self) -> VerificationResult:
        """Run full verification (all checks)."""
        result = VerificationResult(
            level=VerifierLevel.FULL,
            started_at=datetime.now(),
        )

        for command in self.config.full_verifier:
            cmd_result = self.run_command(command)
            result.commands.append(cmd_result)

        result.completed_at = datetime.now()
        return result

    def run_baseline(self) -> VerificationResult:
        """Run baseline verification and store the result."""
        result = self.run_full()
        self.baseline_result = result
        self._save_result(result, "baseline")
        return result

    def run_level(self, level: VerifierLevel) -> VerificationResult:
        """Run verification at the specified level."""
        if level == VerifierLevel.FAST:
            return self.run_fast()
        else:
            return self.run_full()

    def _save_result(self, result: VerificationResult, name: str) -> Path:
        """Save verification result to disk."""
        import json

        self.results_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "level": result.level.value,
            "passed": result.passed,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "total_duration": result.total_duration,
            "commands": [
                {
                    "command": cmd.command,
                    "status": cmd.status.value,
                    "exit_code": cmd.exit_code,
                    "duration_seconds": cmd.duration_seconds,
                    "started_at": cmd.started_at.isoformat(),
                }
                for cmd in result.commands
            ],
        }

        output_path = self.results_dir / f"{name}.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        # Also save stdout/stderr for each command
        for i, cmd in enumerate(result.commands):
            stdout_path = self.results_dir / f"{name}_{i}_stdout.txt"
            stderr_path = self.results_dir / f"{name}_{i}_stderr.txt"
            with open(stdout_path, "w") as f:
                f.write(cmd.stdout)
            with open(stderr_path, "w") as f:
                f.write(cmd.stderr)

        return output_path

    @classmethod
    def detect_commands(cls, repo_path: Path) -> dict[str, list[str]]:
        """
        Auto-detect verification commands based on project files.

        Returns a dict with 'fast' and 'full' command lists.
        """
        fast = []
        full = []

        # Node.js / npm
        package_json = repo_path / "package.json"
        if package_json.exists():
            try:
                import json

                with open(package_json) as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})

                if "test" in scripts:
                    fast.append("npm test")
                    full.append("npm test")
                if "lint" in scripts:
                    full.append("npm run lint")
                if "typecheck" in scripts:
                    full.append("npm run typecheck")
                elif "type-check" in scripts:
                    full.append("npm run type-check")

            except (json.JSONDecodeError, KeyError):
                pass

        # Python / pytest
        if (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists():
            if not fast:
                fast.append("pytest")
            if not full:
                full.extend(["pytest", "ruff check .", "mypy ."])

        # Rust / Cargo
        if (repo_path / "Cargo.toml").exists():
            if not fast:
                fast.append("cargo test")
            if not full:
                full.extend(["cargo test", "cargo clippy -- -D warnings"])

        # Go
        if (repo_path / "go.mod").exists():
            if not fast:
                fast.append("go test ./...")
            if not full:
                full.extend(["go test ./...", "go vet ./..."])

        # Makefile
        makefile = repo_path / "Makefile"
        if makefile.exists() and not fast:
            try:
                with open(makefile) as f:
                    content = f.read()
                if "test:" in content:
                    fast.append("make test")
                    full.append("make test")
                if "lint:" in content:
                    full.append("make lint")
            except Exception:
                pass

        # Fallback
        if not fast:
            fast.append("echo 'No test command detected'")
        if not full:
            full = fast.copy()

        return {"fast": fast, "full": full}


def run_verification(
    repo_path: Path,
    config: Config,
    level: VerifierLevel = VerifierLevel.FAST,
) -> VerificationResult:
    """Convenience function to run verification."""
    verifier = Verifier(repo_path, config)
    return verifier.run_level(level)
