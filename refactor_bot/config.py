"""
Configuration management for refactor-bot.

Handles loading, saving, and validation of configuration from .refactor-bot.config.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ClaudeConfig(BaseModel):
    """Configuration for Claude Code CLI integration."""

    binary: str = Field(default="claude", description="Path to Claude Code binary")
    allowed_tools: str = Field(
        default="Read,Edit,Bash,Grep,Glob",
        description="Tools to allow (--allowedTools flag)",
    )
    tools: str = Field(
        default="Read,Edit,Bash,Grep,Glob",
        description="Tools to expose (--tools flag)",
    )
    max_turns_patcher: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Max turns for patcher agent (high since Claude may need multiple internal turns)",
    )
    max_turns_planner: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Max turns for planner agent",
    )


class Config(BaseModel):
    """Main configuration for refactor-bot."""

    # Diff and batch limits
    diff_budget_loc: int = Field(
        default=300,
        ge=10,
        le=1000,
        description="Maximum lines of code changed per batch",
    )
    max_batches: int = Field(
        default=200,
        ge=1,
        le=500,
        description="Maximum number of batches to generate",
    )
    max_files_per_batch: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum files per batch (smaller = less tokens per call)",
    )
    retry_per_batch: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Number of retries per batch on failure",
    )
    run_full_verifier_every: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Run full verifier every N batches",
    )

    # Verifier commands
    build_command: Optional[str] = Field(
        default=None,
        description="Build command (optional)",
    )
    fast_verifier: list[str] = Field(
        default_factory=lambda: ["npm test"],
        description="Fast verification commands (required)",
    )
    full_verifier: list[str] = Field(
        default_factory=lambda: ["npm test", "npm run typecheck"],
        description="Full verification commands",
    )
    lint_command: Optional[str] = Field(
        default=None,
        description="Lint command (recommended)",
    )
    typecheck_command: Optional[str] = Field(
        default=None,
        description="Type check command (recommended)",
    )

    # Scope configuration
    scope_excludes: list[str] = Field(
        default_factory=lambda: [
            "**/dist/**",
            "**/build/**",
            "**/.venv/**",
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/.git/**",
        ],
        description="Glob patterns to exclude from scope",
    )
    scope_includes: list[str] = Field(
        default_factory=list,
        description="Glob patterns to include in scope (empty = all)",
    )

    # Safety options
    allow_public_api_changes: bool = Field(
        default=False,
        description="Allow changes to public API contracts",
    )
    allow_lockfile_changes: bool = Field(
        default=False,
        description="Allow changes to lockfiles",
    )
    allow_formatting_only: bool = Field(
        default=True,
        description="Allow formatting-only batches",
    )

    # Claude configuration
    claude: ClaudeConfig = Field(
        default_factory=ClaudeConfig,
        description="Claude Code CLI configuration",
    )

    # Planning options
    use_llm_planner: bool = Field(
        default=True,
        description="Use Claude to refine the naive plan (disable to save tokens)",
    )

    # Context budget
    max_prompt_chars: int = Field(
        default=150000,
        ge=10000,
        le=500000,
        description="Maximum characters in prompt body (Claude supports ~200k tokens)",
    )
    max_file_excerpt_lines: int = Field(
        default=3000,
        ge=100,
        le=10000,
        description="Maximum total lines of file excerpts",
    )
    max_ledger_entries: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum ledger entries in context",
    )

    @classmethod
    def load(cls, repo_path: Path) -> "Config":
        """Load configuration from repo's .refactor-bot.config.json."""
        config_path = repo_path / ".refactor-bot.config.json"
        if config_path.exists():
            with open(config_path, "r") as f:
                data = json.load(f)
            return cls.model_validate(data)
        return cls()

    @classmethod
    def load_or_create(cls, repo_path: Path) -> "Config":
        """Load configuration or create default if not exists."""
        config_path = repo_path / ".refactor-bot.config.json"
        if config_path.exists():
            return cls.load(repo_path)
        else:
            config = cls()
            config.save(repo_path)
            return config

    def save(self, repo_path: Path) -> Path:
        """Save configuration to repo's .refactor-bot.config.json."""
        config_path = repo_path / ".refactor-bot.config.json"
        with open(config_path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)
        return config_path

    def detect_verifiers(self, repo_path: Path) -> "Config":
        """Auto-detect verification commands based on project files."""
        # Detect Node.js/npm
        if (repo_path / "package.json").exists():
            try:
                with open(repo_path / "package.json") as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                if "test" in scripts:
                    self.fast_verifier = ["npm test"]
                if "lint" in scripts:
                    self.lint_command = "npm run lint"
                if "typecheck" in scripts or "type-check" in scripts:
                    self.typecheck_command = "npm run typecheck"
                if "build" in scripts:
                    self.build_command = "npm run build"
                # Build full verifier
                self.full_verifier = [cmd for cmd in [
                    "npm test" if "test" in scripts else None,
                    "npm run lint" if "lint" in scripts else None,
                    "npm run typecheck" if "typecheck" in scripts else None,
                ] if cmd]
            except (json.JSONDecodeError, KeyError):
                pass

        # Detect Python/pytest
        if (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists():
            self.fast_verifier = ["pytest"]
            self.full_verifier = ["pytest", "mypy ."]
            if (repo_path / "pyproject.toml").exists():
                try:
                    import tomllib
                    with open(repo_path / "pyproject.toml", "rb") as f:
                        toml = tomllib.load(f)
                    if "tool" in toml:
                        if "ruff" in toml["tool"]:
                            self.lint_command = "ruff check ."
                        if "black" in toml["tool"]:
                            self.lint_command = "black --check ."
                        if "mypy" in toml["tool"]:
                            self.typecheck_command = "mypy ."
                except Exception:
                    pass

        # Detect Makefile
        if (repo_path / "Makefile").exists():
            try:
                with open(repo_path / "Makefile") as f:
                    content = f.read()
                if "test:" in content:
                    self.fast_verifier = ["make test"]
                if "lint:" in content:
                    self.lint_command = "make lint"
                if "build:" in content:
                    self.build_command = "make build"
            except Exception:
                pass

        # Detect Cargo (Rust)
        if (repo_path / "Cargo.toml").exists():
            self.fast_verifier = ["cargo test"]
            self.full_verifier = ["cargo test", "cargo clippy"]
            self.build_command = "cargo build"

        # Detect Go
        if (repo_path / "go.mod").exists():
            self.fast_verifier = ["go test ./..."]
            self.full_verifier = ["go test ./...", "go vet ./..."]
            self.build_command = "go build ./..."

        return self


# Default paths
REFACTOR_BOT_HOME = Path.home() / ".refactor-bot"
BACKUPS_DIR = REFACTOR_BOT_HOME / "backups"
WORKTREES_DIR = REFACTOR_BOT_HOME / "worktrees"
LOGS_DIR = REFACTOR_BOT_HOME / "logs"


def ensure_directories() -> None:
    """Ensure all required directories exist."""
    for directory in [REFACTOR_BOT_HOME, BACKUPS_DIR, WORKTREES_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
