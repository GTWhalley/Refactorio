"""
Refactoring planner for refactor-bot.

Generates ordered batches of refactoring tasks based on codebase analysis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from refactor_bot.config import Config
from refactor_bot.indexer.symbols import SymbolExtractor
from refactor_bot.indexer.deps import DependencyAnalyzer, DependencyGraph


class BatchOperation(str, Enum):
    """Types of operations allowed in a batch."""

    FORMAT = "format"
    REMOVE_UNUSED_IMPORTS = "remove_unused_imports"
    REMOVE_DEAD_CODE = "remove_dead_code"
    RENAME = "rename"
    EXTRACT_FUNCTION = "extract_function"
    EXTRACT_CLASS = "extract_class"
    MOVE_MODULE = "move_module"
    SPLIT_MODULE = "split_module"
    ADD_TYPES = "add_types"
    ADD_TESTS = "add_tests"
    REFACTOR_INTERNAL = "refactor_internal"
    ASYNC_CONVERSION = "async_conversion"
    ARCHITECTURE = "architecture"


class VerifierLevel(str, Enum):
    """Verification level required for a batch."""

    FAST = "fast"
    FULL = "full"


@dataclass
class Batch:
    """A single refactoring batch."""

    id: str
    goal: str
    scope_globs: list[str]
    allowed_operations: list[str]
    diff_budget_loc: int
    risk_score: int  # 0-100
    verifier_level: VerifierLevel
    notes: str = ""
    dependencies: list[str] = field(default_factory=list)  # IDs of batches that must run first
    status: str = "pending"  # pending, in_progress, completed, failed, skipped

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "scope_globs": self.scope_globs,
            "allowed_operations": self.allowed_operations,
            "diff_budget_loc": self.diff_budget_loc,
            "risk_score": self.risk_score,
            "verifier_level": self.verifier_level.value,
            "notes": self.notes,
            "dependencies": self.dependencies,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Batch":
        return cls(
            id=data["id"],
            goal=data["goal"],
            scope_globs=data["scope_globs"],
            allowed_operations=data["allowed_operations"],
            diff_budget_loc=data["diff_budget_loc"],
            risk_score=data["risk_score"],
            verifier_level=VerifierLevel(data["verifier_level"]),
            notes=data.get("notes", ""),
            dependencies=data.get("dependencies", []),
            status=data.get("status", "pending"),
        )


@dataclass
class RefactorPlan:
    """A complete refactoring plan."""

    batches: list[Batch]
    total_estimated_loc: int = 0
    created_at: str = ""
    repo_path: str = ""

    def to_dict(self) -> dict:
        return {
            "batches": [b.to_dict() for b in self.batches],
            "total_estimated_loc": self.total_estimated_loc,
            "created_at": self.created_at,
            "repo_path": self.repo_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RefactorPlan":
        return cls(
            batches=[Batch.from_dict(b) for b in data["batches"]],
            total_estimated_loc=data.get("total_estimated_loc", 0),
            created_at=data.get("created_at", ""),
            repo_path=data.get("repo_path", ""),
        )

    def save(self, path: Path) -> None:
        """Save plan to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "RefactorPlan":
        """Load plan from JSON file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))


class Planner:
    """
    Generates refactoring plans based on codebase analysis.

    Uses heuristics to create a naive plan, which can optionally
    be refined by the LLM PlannerAgent.
    """

    def __init__(
        self,
        repo_path: Path,
        config: Config,
        symbol_extractor: Optional[SymbolExtractor] = None,
        dependency_graph: Optional[DependencyGraph] = None,
    ):
        self.repo_path = repo_path
        self.config = config
        self.symbols = symbol_extractor
        self.deps = dependency_graph
        self._batch_counter = 0

    def _next_batch_id(self) -> str:
        """Generate the next batch ID."""
        self._batch_counter += 1
        return f"batch-{self._batch_counter:03d}"

    def _estimate_risk(self, files: list[str]) -> int:
        """
        Estimate risk score (0-100) for modifying given files.

        Higher scores indicate more risky changes.
        """
        if not self.deps:
            return 50  # Default moderate risk

        total_fan_in = 0
        for file in files:
            node = self.deps.nodes.get(file)
            if node:
                total_fan_in += node.fan_in

        # Scale: 0-5 fan_in = low risk, 5-20 = medium, 20+ = high
        if total_fan_in <= 5:
            return 20
        elif total_fan_in <= 20:
            return 50
        else:
            return min(80, 50 + total_fan_in)

    def _get_files_by_language(self) -> dict[str, list[str]]:
        """Group files by programming language."""
        if not self.symbols:
            return {}

        by_lang: dict[str, list[str]] = {}
        for rel_path, file_info in self.symbols.files.items():
            lang = file_info.language or "unknown"
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append(rel_path)

        return by_lang

    def generate_naive_plan(self) -> RefactorPlan:
        """
        Generate a naive refactoring plan using heuristics.

        Order (per spec Section 10.2):
        1. Formatting-only pass
        2. Import cleanup / dead-code removal
        3. Renames / small extracts / module splits
        4. Add/strengthen tests
        5. Larger internal restructures
        6. Big transforms (async, architecture)
        """
        from datetime import datetime

        batches: list[Batch] = []
        files_by_lang = self._get_files_by_language()

        # 1. Formatting pass (if enabled)
        # Only format actual code files, not config/data/resource files
        formattable_langs = {
            "python", "javascript", "typescript", "rust", "go", "java",
            "gdscript", "c", "cpp", "csharp", "swift", "kotlin", "ruby",
            "php", "lua", "shell", "bash",
        }
        if self.config.allow_formatting_only:
            for lang, files in files_by_lang.items():
                if files and lang in formattable_langs:
                    batches.append(Batch(
                        id=self._next_batch_id(),
                        goal=f"Format all {lang} files",
                        scope_globs=[f"**/*.{self._lang_extension(lang)}"],
                        allowed_operations=[BatchOperation.FORMAT.value],
                        diff_budget_loc=100,
                        risk_score=5,
                        verifier_level=VerifierLevel.FAST,
                        notes="Formatting only - no logic changes",
                    ))

        # 2. Import cleanup and dead code removal
        for lang, files in files_by_lang.items():
            if files and lang in ("python", "javascript", "typescript"):
                batches.append(Batch(
                    id=self._next_batch_id(),
                    goal=f"Remove unused imports in {lang} files",
                    scope_globs=[f"**/*.{self._lang_extension(lang)}"],
                    allowed_operations=[
                        BatchOperation.REMOVE_UNUSED_IMPORTS.value,
                        BatchOperation.REMOVE_DEAD_CODE.value,
                    ],
                    diff_budget_loc=150,
                    risk_score=15,
                    verifier_level=VerifierLevel.FAST,
                    notes="Safe removal of clearly unused code",
                ))

        # 3. Identify potential renames and extractions based on hotspots
        if self.deps:
            hotspots = self.deps.get_hotspots(min_fan_in=3)
            for node in hotspots[:5]:  # Top 5 hotspots
                batches.append(Batch(
                    id=self._next_batch_id(),
                    goal=f"Review and potentially refactor high-impact file: {node.path}",
                    scope_globs=[node.path],
                    allowed_operations=[
                        BatchOperation.RENAME.value,
                        BatchOperation.EXTRACT_FUNCTION.value,
                        BatchOperation.ADD_TYPES.value,
                    ],
                    diff_budget_loc=self.config.diff_budget_loc,
                    risk_score=self._estimate_risk([node.path]),
                    verifier_level=VerifierLevel.FULL,
                    notes=f"High fan-in ({node.fan_in}): many files depend on this",
                ))

        # 4. Safe refactors on leaf nodes (no dependents)
        if self.deps:
            leaves = self.deps.get_leaves()
            if leaves:
                leaf_paths = [n.path for n in leaves[:10]]
                batches.append(Batch(
                    id=self._next_batch_id(),
                    goal="Refactor leaf modules (no dependents)",
                    scope_globs=leaf_paths,
                    allowed_operations=[
                        BatchOperation.RENAME.value,
                        BatchOperation.EXTRACT_FUNCTION.value,
                        BatchOperation.REFACTOR_INTERNAL.value,
                    ],
                    diff_budget_loc=self.config.diff_budget_loc,
                    risk_score=20,
                    verifier_level=VerifierLevel.FAST,
                    notes="Safe to modify - no other files depend on these",
                ))

        # Sort by risk score (lowest first)
        batches.sort(key=lambda b: b.risk_score)

        # Limit to max_batches
        batches = batches[: self.config.max_batches]

        total_loc = sum(b.diff_budget_loc for b in batches)

        return RefactorPlan(
            batches=batches,
            total_estimated_loc=total_loc,
            created_at=datetime.now().isoformat(),
            repo_path=str(self.repo_path),
        )

    def _lang_extension(self, lang: str) -> str:
        """Get file extension for a language."""
        extensions = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "rust": "rs",
            "go": "go",
            "java": "java",
            "gdscript": "gd",
            "godot_scene": "tscn",
            "godot_resource": "tres",
            "gdshader": "gdshader",
            "cfg": "cfg",
            "import": "import",
            "json": "json",
            "yaml": "yaml",
            "toml": "toml",
            "md": "md",
            "txt": "txt",
            "c": "c",
            "cpp": "cpp",
            "h": "h",
            "hpp": "hpp",
            "csharp": "cs",
            "swift": "swift",
            "kotlin": "kt",
            "ruby": "rb",
            "php": "php",
            "lua": "lua",
            "shell": "sh",
            "bash": "bash",
        }
        return extensions.get(lang, "*")

    def refine_with_llm(
        self,
        plan: RefactorPlan,
        claude_driver,
        architecture_snapshot: str = "",
    ) -> RefactorPlan:
        """
        Refine the naive plan using the LLM PlannerAgent.

        The LLM can reorder, combine, split, or add batches,
        but cannot exceed the configured limits.
        """
        from refactor_bot.context_pack import ContextPackBuilder

        # Build context for the planner
        context_builder = ContextPackBuilder(
            repo_path=self.repo_path,
            config=self.config,
        )

        context = context_builder.build_planner_context(
            naive_plan=plan,
            architecture_snapshot=architecture_snapshot,
        )

        # Call the planner agent
        response = claude_driver.call_planner(context)

        if not response.success or not response.structured_output:
            # Fall back to naive plan
            return plan

        # Parse refined plan
        try:
            refined_batches = [
                Batch.from_dict(b)
                for b in response.structured_output.get("batches", [])
            ]

            # Validate constraints
            if len(refined_batches) > self.config.max_batches:
                refined_batches = refined_batches[: self.config.max_batches]

            for batch in refined_batches:
                if batch.diff_budget_loc > self.config.diff_budget_loc:
                    batch.diff_budget_loc = self.config.diff_budget_loc

            return RefactorPlan(
                batches=refined_batches,
                total_estimated_loc=sum(b.diff_budget_loc for b in refined_batches),
                created_at=plan.created_at,
                repo_path=plan.repo_path,
            )

        except Exception:
            # Fall back to naive plan on any error
            return plan
