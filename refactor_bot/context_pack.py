"""
Context pack builder for refactor-bot.

Builds small, focused context packets for LLM calls without
overwhelming the context window.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from refactor_bot.config import Config
from refactor_bot.indexer.symbols import SymbolExtractor, Symbol
from refactor_bot.indexer.deps import DependencyGraph

if TYPE_CHECKING:
    from refactor_bot.planner import RefactorPlan, Batch
    from refactor_bot.ledger import TaskLedger


@dataclass
class ContextBudget:
    """Tracks context budget usage."""

    max_chars: int
    max_file_lines: int
    max_ledger_entries: int

    used_chars: int = 0
    used_file_lines: int = 0
    used_ledger_entries: int = 0

    @property
    def remaining_chars(self) -> int:
        return self.max_chars - self.used_chars

    @property
    def remaining_file_lines(self) -> int:
        return self.max_file_lines - self.used_file_lines

    def can_add_chars(self, count: int) -> bool:
        return self.used_chars + count <= self.max_chars

    def can_add_lines(self, count: int) -> bool:
        return self.used_file_lines + count <= self.max_file_lines

    def add_chars(self, count: int) -> bool:
        if not self.can_add_chars(count):
            return False
        self.used_chars += count
        return True

    def add_lines(self, count: int) -> bool:
        if not self.can_add_lines(count):
            return False
        self.used_file_lines += count
        return True


class ContextPackBuilder:
    """
    Builds context packets for LLM calls.

    Ensures context stays within budget limits while including
    the most relevant information.
    """

    def __init__(
        self,
        repo_path: Path,
        config: Config,
        symbols: Optional[SymbolExtractor] = None,
        deps: Optional[DependencyGraph] = None,
        ledger: Optional["TaskLedger"] = None,
    ):
        self.repo_path = repo_path
        self.config = config
        self.symbols = symbols
        self.deps = deps
        self.ledger = ledger

    def _create_budget(self) -> ContextBudget:
        """Create a new context budget from config."""
        return ContextBudget(
            max_chars=self.config.max_prompt_chars,
            max_file_lines=self.config.max_file_excerpt_lines,
            max_ledger_entries=self.config.max_ledger_entries,
        )

    def _read_file_excerpt(
        self,
        file_path: str,
        budget: ContextBudget,
        start_line: int = 1,
        max_lines: int = 100,
    ) -> Optional[str]:
        """Read an excerpt from a file within budget."""
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return None

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return None

        # Adjust for available budget
        available_lines = min(max_lines, budget.remaining_file_lines)
        if available_lines <= 0:
            return None

        end_line = min(start_line + available_lines - 1, len(lines))
        excerpt_lines = lines[start_line - 1 : end_line]
        excerpt = "".join(excerpt_lines)

        if not budget.add_chars(len(excerpt)):
            return None
        if not budget.add_lines(len(excerpt_lines)):
            return None

        return f"```{file_path}:{start_line}-{end_line}\n{excerpt}```"

    def _get_symbol_summary(self, file_path: str) -> str:
        """Get a summary of symbols in a file."""
        if not self.symbols:
            return ""

        symbols = self.symbols.get_file_symbols(file_path)
        if not symbols:
            return ""

        lines = [f"Symbols in {file_path}:"]
        for symbol in symbols[:20]:  # Limit to 20 symbols
            lines.append(f"  - {symbol.symbol_type.value}: {symbol.name} (line {symbol.line_number})")

        return "\n".join(lines)

    def _get_dependency_info(self, file_path: str) -> str:
        """Get dependency information for a file."""
        if not self.deps:
            return ""

        node = self.deps.nodes.get(file_path)
        if not node:
            return ""

        lines = [f"Dependencies for {file_path}:"]
        if node.imports:
            lines.append(f"  Imports ({len(node.imports)}):")
            for imp in node.imports[:10]:
                lines.append(f"    - {imp}")

        if node.imported_by:
            lines.append(f"  Imported by ({len(node.imported_by)}):")
            for dep in node.imported_by[:10]:
                lines.append(f"    - {dep}")

        if node.external_deps:
            lines.append(f"  External deps: {', '.join(node.external_deps[:10])}")

        return "\n".join(lines)

    def _get_scope_files(self, scope_globs: list[str]) -> list[str]:
        """Get all files matching the scope globs."""
        import fnmatch

        matching_files = []

        for pattern in scope_globs:
            # Check if it's a direct file path (from batch splitting)
            full_path = self.repo_path / pattern
            if full_path.exists() and full_path.is_file():
                matching_files.append(pattern)
                continue

            # Otherwise treat as glob pattern
            if self.symbols:
                for file_path in self.symbols.files:
                    if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(file_path, pattern.replace("**", "*")):
                        if file_path not in matching_files:
                            matching_files.append(file_path)

        return matching_files

    def _read_full_file(self, file_path: str, budget: ContextBudget) -> Optional[str]:
        """Read the full content of a file within budget."""
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return None

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return None

        # Check if we can fit this file
        file_block = f"### {file_path}\n```\n{content}\n```"

        if not budget.can_add_chars(len(file_block)):
            # Try to fit at least part of the file
            available = budget.remaining_chars - 100  # Leave room for header
            if available > 500:
                truncated = content[:available]
                file_block = f"### {file_path} (truncated)\n```\n{truncated}\n[...truncated...]\n```"
                budget.add_chars(len(file_block))
                return file_block
            return None

        budget.add_chars(len(file_block))
        lines = content.count('\n') + 1
        budget.add_lines(lines)

        return file_block

    def _get_recent_ledger_entries(self, budget: ContextBudget) -> str:
        """Get recent ledger entries within budget."""
        if not self.ledger:
            return ""

        entries = self.ledger.get_recent(self.config.max_ledger_entries)
        if not entries:
            return ""

        lines = ["Recent refactoring activity:"]
        for entry in entries:
            summary = f"  - [{entry.batch_id}] {entry.status}: {entry.goal}"
            if budget.can_add_chars(len(summary)):
                lines.append(summary)
                budget.add_chars(len(summary))
            else:
                break

        return "\n".join(lines)

    def build_planner_context(
        self,
        naive_plan: "RefactorPlan",
        architecture_snapshot: str = "",
    ) -> str:
        """Build context for the planner agent."""
        budget = self._create_budget()
        sections = []

        # 1. Introduction
        intro = (
            "You are refining a refactoring plan for a codebase. "
            "Review the naive plan below and improve it by:\n"
            "- Reordering batches for safety (lowest risk first)\n"
            "- Combining or splitting batches as appropriate\n"
            "- Ensuring each batch is atomic and verifiable\n"
            "- Adding any missed opportunities for improvement\n\n"
            "Constraints:\n"
            f"- Maximum batches: {self.config.max_batches}\n"
            f"- Maximum LOC per batch: {self.config.diff_budget_loc}\n"
            f"- Public API changes allowed: {self.config.allow_public_api_changes}\n"
        )
        sections.append(intro)
        budget.add_chars(len(intro))

        # 2. Architecture snapshot
        if architecture_snapshot and budget.can_add_chars(len(architecture_snapshot)):
            sections.append(f"## Architecture Overview\n{architecture_snapshot}")
            budget.add_chars(len(architecture_snapshot))

        # 3. Codebase statistics
        if self.symbols:
            stats = (
                f"## Codebase Statistics\n"
                f"- Files indexed: {len(self.symbols.files)}\n"
                f"- Symbols found: {len(self.symbols.symbols)}\n"
            )
            sections.append(stats)
            budget.add_chars(len(stats))

        # 4. Dependency hotspots
        if self.deps:
            hotspots = self.deps.get_hotspots(min_fan_in=3)[:10]
            if hotspots:
                hotspot_lines = ["## High-Impact Files (many dependents)"]
                for node in hotspots:
                    hotspot_lines.append(f"- {node.path} (fan-in: {node.fan_in})")
                hotspot_text = "\n".join(hotspot_lines)
                sections.append(hotspot_text)
                budget.add_chars(len(hotspot_text))

        # 5. Naive plan
        plan_json = json.dumps(naive_plan.to_dict(), indent=2)
        if budget.can_add_chars(len(plan_json)):
            sections.append(f"## Naive Plan\n```json\n{plan_json}\n```")
            budget.add_chars(len(plan_json))

        return "\n\n".join(sections)

    def build_patcher_context(
        self,
        batch: "Batch",
        previous_batches: list["Batch"] = None,
    ) -> str:
        """Build context for the patcher agent."""
        budget = self._create_budget()
        sections = []

        # 1. Batch instructions
        batch_info = (
            f"## Current Batch: {batch.id}\n"
            f"Goal: {batch.goal}\n"
            f"Scope: {', '.join(batch.scope_globs)}\n"
            f"Allowed operations: {', '.join(batch.allowed_operations)}\n"
            f"Diff budget: {batch.diff_budget_loc} lines\n"
            f"Notes: {batch.notes}\n\n"
            "Generate a unified diff patch that accomplishes this goal. "
            "If uncertain or if changes would exceed scope, return status='noop'."
        )
        sections.append(batch_info)
        budget.add_chars(len(batch_info))

        # 2. Files in scope - include FULL content of all scope files
        # The patcher needs complete file contents to generate accurate diffs
        scope_files = self._get_scope_files(batch.scope_globs)
        sections.append(f"## Files in Scope ({len(scope_files)} files)")

        for file_path in scope_files:
            # Read FULL file content (not just excerpt)
            full_content = self._read_full_file(file_path, budget)
            if full_content:
                sections.append(full_content)
            else:
                # If we can't fit the full file, at least note it
                sections.append(f"[File {file_path} truncated due to context limits]")

        # 3. Recent activity
        ledger_info = self._get_recent_ledger_entries(budget)
        if ledger_info:
            sections.append(ledger_info)

        # 4. Previous batch results (if any)
        if previous_batches:
            prev_lines = ["## Previous Batches"]
            for prev in previous_batches[-3:]:  # Last 3 batches
                prev_lines.append(f"- [{prev.id}] {prev.status}: {prev.goal}")
            prev_text = "\n".join(prev_lines)
            if budget.can_add_chars(len(prev_text)):
                sections.append(prev_text)

        return "\n\n".join(sections)

    def build_critic_context(
        self,
        batch: "Batch",
        patch_diff: str,
    ) -> str:
        """Build context for the critic agent."""
        budget = self._create_budget()
        sections = []

        # 1. Review instructions
        instructions = (
            "## Patch Review\n"
            "Review the following patch and determine if it should be applied.\n\n"
            "Decide:\n"
            "- 'accept': Patch is good, apply it\n"
            "- 'reject': Patch is bad, do not apply\n"
            "- 'shrink_scope': Patch is too broad, needs smaller scope\n"
            "- 'shrink_diff': Patch touches too many lines, needs reduction\n"
            "- 'noop': No changes needed, skip this batch\n"
        )
        sections.append(instructions)
        budget.add_chars(len(instructions))

        # 2. Batch info
        batch_info = (
            f"## Batch: {batch.id}\n"
            f"Goal: {batch.goal}\n"
            f"Allowed operations: {', '.join(batch.allowed_operations)}\n"
            f"Diff budget: {batch.diff_budget_loc} lines\n"
        )
        sections.append(batch_info)
        budget.add_chars(len(batch_info))

        # 3. The patch itself
        if budget.can_add_chars(len(patch_diff)):
            sections.append(f"## Proposed Patch\n```diff\n{patch_diff}\n```")
            budget.add_chars(len(patch_diff))

        return "\n\n".join(sections)
