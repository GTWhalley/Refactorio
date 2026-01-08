"""
Symbol extraction for refactor-bot.

Extracts function, class, and other symbol definitions from source code
using ripgrep-based pattern matching.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from refactor_bot.util import file_hash


class SymbolType(str, Enum):
    """Types of symbols that can be extracted."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    TYPE = "type"
    CONSTANT = "constant"
    VARIABLE = "variable"
    ENUM = "enum"
    MODULE = "module"
    IMPORT = "import"
    EXPORT = "export"


@dataclass
class Symbol:
    """Represents a code symbol (function, class, etc.)."""

    name: str
    symbol_type: SymbolType
    file_path: str
    line_number: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent: Optional[str] = None  # For methods, the class name
    exported: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.symbol_type.value,
            "file": self.file_path,
            "line": self.line_number,
            "signature": self.signature,
            "docstring": self.docstring,
            "parent": self.parent,
            "exported": self.exported,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Symbol":
        return cls(
            name=data["name"],
            symbol_type=SymbolType(data["type"]),
            file_path=data["file"],
            line_number=data["line"],
            signature=data.get("signature"),
            docstring=data.get("docstring"),
            parent=data.get("parent"),
            exported=data.get("exported", False),
        )


@dataclass
class FileInfo:
    """Information about a source file."""

    path: str
    relative_path: str
    hash: str
    size_bytes: int
    line_count: int
    language: Optional[str] = None
    symbols: list[Symbol] = field(default_factory=list)


# Language-specific regex patterns for symbol extraction
SYMBOL_PATTERNS: dict[str, list[tuple[SymbolType, str]]] = {
    "python": [
        (SymbolType.FUNCTION, r"^def\s+(\w+)\s*\("),
        (SymbolType.CLASS, r"^class\s+(\w+)\s*[\(:]"),
        (SymbolType.METHOD, r"^\s+def\s+(\w+)\s*\("),
        (SymbolType.CONSTANT, r"^([A-Z][A-Z_0-9]+)\s*="),
    ],
    "javascript": [
        (SymbolType.FUNCTION, r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\("),
        (SymbolType.FUNCTION, r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\("),
        (SymbolType.FUNCTION, r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function"),
        (SymbolType.CLASS, r"^(?:export\s+)?class\s+(\w+)"),
        (SymbolType.CONSTANT, r"^(?:export\s+)?const\s+([A-Z][A-Z_0-9]+)\s*="),
    ],
    "typescript": [
        (SymbolType.FUNCTION, r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)"),
        (SymbolType.FUNCTION, r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\("),
        (SymbolType.CLASS, r"^(?:export\s+)?class\s+(\w+)"),
        (SymbolType.INTERFACE, r"^(?:export\s+)?interface\s+(\w+)"),
        (SymbolType.TYPE, r"^(?:export\s+)?type\s+(\w+)\s*="),
        (SymbolType.ENUM, r"^(?:export\s+)?enum\s+(\w+)"),
    ],
    "rust": [
        (SymbolType.FUNCTION, r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"),
        (SymbolType.CLASS, r"^(?:pub\s+)?struct\s+(\w+)"),
        (SymbolType.INTERFACE, r"^(?:pub\s+)?trait\s+(\w+)"),
        (SymbolType.ENUM, r"^(?:pub\s+)?enum\s+(\w+)"),
        (SymbolType.TYPE, r"^(?:pub\s+)?type\s+(\w+)\s*="),
        (SymbolType.CONSTANT, r"^(?:pub\s+)?const\s+(\w+):"),
    ],
    "go": [
        (SymbolType.FUNCTION, r"^func\s+(\w+)\s*\("),
        (SymbolType.METHOD, r"^func\s+\([^)]+\)\s+(\w+)\s*\("),
        (SymbolType.CLASS, r"^type\s+(\w+)\s+struct"),
        (SymbolType.INTERFACE, r"^type\s+(\w+)\s+interface"),
        (SymbolType.CONSTANT, r"^const\s+(\w+)\s*="),
        (SymbolType.VARIABLE, r"^var\s+(\w+)\s+"),
    ],
    "java": [
        (SymbolType.CLASS, r"^(?:public\s+)?(?:abstract\s+)?class\s+(\w+)"),
        (SymbolType.INTERFACE, r"^(?:public\s+)?interface\s+(\w+)"),
        (SymbolType.ENUM, r"^(?:public\s+)?enum\s+(\w+)"),
        (SymbolType.METHOD, r"^\s+(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\("),
    ],
    # Godot GDScript
    "gdscript": [
        (SymbolType.CLASS, r"^class_name\s+(\w+)"),
        (SymbolType.CLASS, r"^class\s+(\w+)"),
        (SymbolType.FUNCTION, r"^func\s+(\w+)\s*\("),
        (SymbolType.METHOD, r"^\t+func\s+(\w+)\s*\("),
        (SymbolType.VARIABLE, r"^(?:@export\s+)?var\s+(\w+)"),
        (SymbolType.VARIABLE, r"^(?:@onready\s+)?var\s+(\w+)"),
        (SymbolType.CONSTANT, r"^const\s+(\w+)\s*="),
        (SymbolType.CONSTANT, r"^enum\s+(\w+)\s*\{"),
        (SymbolType.FUNCTION, r"^signal\s+(\w+)"),
    ],
}

# File extension to language mapping
EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".scala": "scala",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    # Godot
    ".gd": "gdscript",
    ".tscn": "godot_scene",
    ".tres": "godot_resource",
    ".gdshader": "gdshader",
}


class SymbolExtractor:
    """Extracts symbols from source code files."""

    def __init__(self, repo_path: Path, excludes: Optional[list[str]] = None):
        self.repo_path = repo_path
        self.excludes = excludes or [
            "**/node_modules/**",
            "**/.git/**",
            "**/dist/**",
            "**/build/**",
            "**/__pycache__/**",
            "**/.venv/**",
            "**/venv/**",
        ]
        self.files: dict[str, FileInfo] = {}
        self.symbols: list[Symbol] = []

    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect the programming language from file extension."""
        return EXTENSION_MAP.get(file_path.suffix.lower())

    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _extract_symbols_from_file(self, file_path: Path, language: str) -> list[Symbol]:
        """Extract symbols from a single file using regex patterns."""
        symbols = []
        patterns = SYMBOL_PATTERNS.get(language, [])

        if not patterns:
            return symbols

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return symbols

        rel_path = str(file_path.relative_to(self.repo_path))

        for line_num, line in enumerate(lines, start=1):
            for symbol_type, pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    name = match.group(1)

                    # Check if exported
                    exported = "export" in line.lower() or (
                        language == "python" and not name.startswith("_")
                    )

                    symbols.append(Symbol(
                        name=name,
                        symbol_type=symbol_type,
                        file_path=rel_path,
                        line_number=line_num,
                        signature=line.strip(),
                        exported=exported,
                    ))

        return symbols

    def _run_ripgrep(self, pattern: str, file_type: Optional[str] = None) -> list[dict]:
        """Run ripgrep with a pattern and return matches."""
        cmd = ["rg", "--json", "-n", pattern]

        if file_type:
            cmd.extend(["--type", file_type])

        for exclude in self.excludes:
            cmd.extend(["--glob", f"!{exclude}"])

        cmd.append(str(self.repo_path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            matches = []
            for line in result.stdout.split("\n"):
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("type") == "match":
                            matches.append(data)
                    except json.JSONDecodeError:
                        continue

            return matches

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def index_files(self) -> dict[str, FileInfo]:
        """Index all source files in the repository."""
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = str(file_path.relative_to(self.repo_path))

            # Check excludes
            skip = False
            for pattern in self.excludes:
                import fnmatch
                if fnmatch.fnmatch(rel_path, pattern.replace("**", "*")):
                    skip = True
                    break
            if skip:
                continue

            language = self._detect_language(file_path)
            if not language:
                # Still index files without known language if they're text files
                # This helps with Godot scene files, configs, etc.
                if file_path.suffix.lower() in ['.tscn', '.tres', '.cfg', '.import', '.gdshader']:
                    language = file_path.suffix.lower().lstrip('.')
                else:
                    continue

            try:
                file_info = FileInfo(
                    path=str(file_path),
                    relative_path=rel_path,
                    hash=file_hash(file_path),
                    size_bytes=file_path.stat().st_size,
                    line_count=self._count_lines(file_path),
                    language=language,
                )

                # Extract symbols
                file_info.symbols = self._extract_symbols_from_file(file_path, language)
                self.symbols.extend(file_info.symbols)

                self.files[rel_path] = file_info

            except Exception:
                continue

        return self.files

    def get_symbol_registry(self) -> dict:
        """Generate the SYMBOL_REGISTRY.json content."""
        registry = {
            "version": "1.0",
            "file_count": len(self.files),
            "symbol_count": len(self.symbols),
            "symbols_by_type": {},
            "symbols": [s.to_dict() for s in self.symbols],
        }

        # Count by type
        for symbol in self.symbols:
            type_name = symbol.symbol_type.value
            registry["symbols_by_type"][type_name] = (
                registry["symbols_by_type"].get(type_name, 0) + 1
            )

        return registry

    def save_registry(self, output_dir: Path) -> Path:
        """Save the symbol registry to a JSON file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "SYMBOL_REGISTRY.json"

        with open(output_path, "w") as f:
            json.dump(self.get_symbol_registry(), f, indent=2)

        return output_path

    def get_file_tree(self) -> dict:
        """Generate a tree structure of all indexed files."""
        tree: dict = {}

        for rel_path in sorted(self.files.keys()):
            parts = rel_path.split("/")
            current = tree

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Add file info
            file_info = self.files[rel_path]
            current[parts[-1]] = {
                "_file": True,
                "language": file_info.language,
                "lines": file_info.line_count,
                "symbols": len(file_info.symbols),
            }

        return tree

    def find_symbol(self, name: str) -> list[Symbol]:
        """Find symbols by name (exact or partial match)."""
        results = []
        name_lower = name.lower()

        for symbol in self.symbols:
            if name_lower in symbol.name.lower():
                results.append(symbol)

        return results

    def get_file_symbols(self, file_path: str) -> list[Symbol]:
        """Get all symbols in a specific file."""
        return [s for s in self.symbols if s.file_path == file_path]
