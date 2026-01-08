"""
Dependency analysis for refactor-bot.

Analyzes import statements and builds dependency graphs between modules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Import:
    """Represents an import statement."""

    module: str  # The imported module/file
    names: list[str]  # Specific names imported (empty for full module import)
    file_path: str  # File containing the import
    line_number: int
    is_relative: bool = False
    alias: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "names": self.names,
            "file": self.file_path,
            "line": self.line_number,
            "is_relative": self.is_relative,
            "alias": self.alias,
        }


@dataclass
class DependencyNode:
    """A node in the dependency graph representing a module/file."""

    path: str
    imports: list[str] = field(default_factory=list)  # Files this module imports
    imported_by: list[str] = field(default_factory=list)  # Files that import this module
    external_deps: list[str] = field(default_factory=list)  # External packages used

    @property
    def fan_in(self) -> int:
        """Number of modules that depend on this one."""
        return len(self.imported_by)

    @property
    def fan_out(self) -> int:
        """Number of modules this one depends on."""
        return len(self.imports)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "imports": self.imports,
            "imported_by": self.imported_by,
            "external_deps": self.external_deps,
            "fan_in": self.fan_in,
            "fan_out": self.fan_out,
        }


# Language-specific import patterns
IMPORT_PATTERNS: dict[str, list[tuple[str, bool]]] = {
    "python": [
        # from x import y, z
        (r"^from\s+([\w.]+)\s+import\s+(.+)$", True),
        # import x, y
        (r"^import\s+([\w., ]+)$", False),
    ],
    "javascript": [
        # import x from 'y'
        (r"^import\s+(?:(\w+)(?:\s*,\s*)?)?(?:\{([^}]+)\})?\s*from\s*['\"]([^'\"]+)['\"]", True),
        # import 'y'
        (r"^import\s*['\"]([^'\"]+)['\"]", False),
        # const x = require('y')
        (r"(?:const|let|var)\s+(?:(\w+)|\{([^}]+)\})\s*=\s*require\(['\"]([^'\"]+)['\"]\)", True),
    ],
    "typescript": [
        # Same as JavaScript
        (r"^import\s+(?:(\w+)(?:\s*,\s*)?)?(?:\{([^}]+)\})?\s*from\s*['\"]([^'\"]+)['\"]", True),
        (r"^import\s*['\"]([^'\"]+)['\"]", False),
        # import type { x } from 'y'
        (r"^import\s+type\s+\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", True),
    ],
    "rust": [
        # use crate::x::y
        (r"^use\s+((?:crate|super|self)?(?:::\w+)+)(?:::(?:\{([^}]+)\}|\*|(\w+)))?", True),
        # extern crate x
        (r"^extern\s+crate\s+(\w+)", False),
    ],
    "go": [
        # import "x"
        (r'^import\s+"([^"]+)"', False),
        # import ( "x" "y" )
        (r'^\s+"([^"]+)"', False),
    ],
}

# Extension to language mapping
EXTENSION_MAP = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
}


class DependencyAnalyzer:
    """Analyzes dependencies between modules in a codebase."""

    def __init__(self, repo_path: Path, excludes: Optional[list[str]] = None):
        self.repo_path = repo_path
        self.excludes = excludes or [
            "**/node_modules/**",
            "**/.git/**",
            "**/dist/**",
            "**/build/**",
            "**/__pycache__/**",
            "**/.venv/**",
        ]
        self.imports: list[Import] = []
        self.nodes: dict[str, DependencyNode] = {}

    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect the programming language from file extension."""
        return EXTENSION_MAP.get(file_path.suffix.lower())

    def _is_relative_import(self, module: str, language: str) -> bool:
        """Check if an import is relative (internal to the project)."""
        if language == "python":
            return module.startswith(".")
        elif language in ("javascript", "typescript"):
            return module.startswith(".") or module.startswith("/")
        elif language == "rust":
            return module.startswith(("crate", "super", "self"))
        elif language == "go":
            # Go uses full package paths; local ones usually contain the module name
            return not module.startswith("github.com") and "/" in module
        return False

    def _resolve_import(self, module: str, from_file: Path, language: str) -> Optional[str]:
        """Try to resolve an import to an actual file path."""
        if language == "python":
            if module.startswith("."):
                # Relative import
                parts = module.lstrip(".").split(".")
                levels = len(module) - len(module.lstrip("."))
                base = from_file.parent
                for _ in range(levels - 1):
                    base = base.parent
                target = base / "/".join(parts)

                # Try with .py extension
                for ext in [".py", "/__init__.py"]:
                    candidate = self.repo_path / (str(target) + ext)
                    if candidate.exists():
                        return str(candidate.relative_to(self.repo_path))
            else:
                # Absolute import - try to find in repo
                parts = module.split(".")
                target = "/".join(parts)
                for ext in [".py", "/__init__.py"]:
                    candidate = self.repo_path / (target + ext)
                    if candidate.exists():
                        return str(candidate.relative_to(self.repo_path))

        elif language in ("javascript", "typescript"):
            if module.startswith("."):
                base = from_file.parent
                target = (base / module).resolve()

                # Try different extensions
                for ext in ["", ".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.ts"]:
                    candidate = Path(str(target) + ext)
                    if candidate.exists():
                        try:
                            return str(candidate.relative_to(self.repo_path))
                        except ValueError:
                            continue

        return None

    def _extract_imports_from_file(self, file_path: Path, language: str) -> list[Import]:
        """Extract all imports from a file."""
        imports = []
        patterns = IMPORT_PATTERNS.get(language, [])

        if not patterns:
            return imports

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return imports

        rel_path = str(file_path.relative_to(self.repo_path))

        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue

            for pattern, extracts_names in patterns:
                match = re.match(pattern, line)
                if match:
                    groups = match.groups()

                    if language == "python":
                        if extracts_names:
                            # from x import y
                            module = groups[0]
                            names = [n.strip() for n in groups[1].split(",")]
                        else:
                            # import x
                            module = groups[0].split(",")[0].strip()
                            names = []

                    elif language in ("javascript", "typescript"):
                        if extracts_names and len(groups) >= 3:
                            # import default, { named } from 'module'
                            default_import = groups[0]
                            named_imports = groups[1]
                            module = groups[2]
                            names = []
                            if default_import:
                                names.append(default_import)
                            if named_imports:
                                names.extend([n.strip() for n in named_imports.split(",")])
                        else:
                            module = groups[0]
                            names = []

                    elif language == "rust":
                        module = groups[0]
                        names = []
                        if len(groups) > 1 and groups[1]:
                            names = [n.strip() for n in groups[1].split(",")]

                    elif language == "go":
                        module = groups[0]
                        names = []

                    else:
                        continue

                    is_relative = self._is_relative_import(module, language)

                    imports.append(Import(
                        module=module,
                        names=names,
                        file_path=rel_path,
                        line_number=line_num,
                        is_relative=is_relative,
                    ))
                    break

        return imports

    def analyze(self) -> "DependencyGraph":
        """Analyze all files and build the dependency graph."""
        import fnmatch

        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = str(file_path.relative_to(self.repo_path))

            # Check excludes
            skip = False
            for pattern in self.excludes:
                if fnmatch.fnmatch(rel_path, pattern.replace("**", "*")):
                    skip = True
                    break
            if skip:
                continue

            language = self._detect_language(file_path)
            if not language:
                continue

            # Ensure node exists
            if rel_path not in self.nodes:
                self.nodes[rel_path] = DependencyNode(path=rel_path)

            # Extract imports
            file_imports = self._extract_imports_from_file(file_path, language)
            self.imports.extend(file_imports)

            for imp in file_imports:
                resolved = self._resolve_import(imp.module, file_path, language)

                if resolved:
                    # Internal dependency
                    self.nodes[rel_path].imports.append(resolved)

                    # Create node for imported file if not exists
                    if resolved not in self.nodes:
                        self.nodes[resolved] = DependencyNode(path=resolved)
                    self.nodes[resolved].imported_by.append(rel_path)
                else:
                    # External dependency
                    if not imp.is_relative:
                        self.nodes[rel_path].external_deps.append(imp.module)

        return DependencyGraph(self.nodes, self.imports)


@dataclass
class DependencyGraph:
    """Represents the complete dependency graph of a codebase."""

    nodes: dict[str, DependencyNode]
    imports: list[Import]

    def to_dict(self) -> dict:
        """Convert graph to a dictionary for JSON serialization."""
        return {
            "version": "1.0",
            "node_count": len(self.nodes),
            "import_count": len(self.imports),
            "nodes": {path: node.to_dict() for path, node in self.nodes.items()},
        }

    def save(self, output_path: Path) -> Path:
        """Save the dependency graph to a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        return output_path

    def get_hotspots(self, min_fan_in: int = 5) -> list[DependencyNode]:
        """
        Get high-impact files (many dependents).

        These are risky to modify as changes affect many other files.
        """
        hotspots = [
            node for node in self.nodes.values()
            if node.fan_in >= min_fan_in
        ]
        return sorted(hotspots, key=lambda n: n.fan_in, reverse=True)

    def get_leaves(self) -> list[DependencyNode]:
        """Get files with no dependents (safe to modify)."""
        return [node for node in self.nodes.values() if node.fan_in == 0]

    def get_external_dependencies(self) -> list[tuple[str, int]]:
        """Get all external dependencies with usage count."""
        dep_count: dict[str, int] = {}
        for node in self.nodes.values():
            for dep in node.external_deps:
                dep_count[dep] = dep_count.get(dep, 0) + 1

        return sorted(dep_count.items(), key=lambda x: x[1], reverse=True)

    def get_dependency_chain(self, file_path: str) -> list[str]:
        """Get all files that would be affected by changing a file."""
        affected = set()
        to_visit = [file_path]

        while to_visit:
            current = to_visit.pop(0)
            if current in affected:
                continue
            affected.add(current)

            node = self.nodes.get(current)
            if node:
                to_visit.extend(node.imported_by)

        affected.discard(file_path)
        return sorted(affected)
