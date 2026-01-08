"""
File tree component for repository browsing.
"""

import customtkinter as ctk
from pathlib import Path
from typing import Callable, Optional

from refactor_bot.gui.theme import theme


class FileTreeItem(ctk.CTkFrame):
    """A single item in the file tree."""

    def __init__(
        self,
        master,
        name: str,
        is_directory: bool = False,
        level: int = 0,
        is_expanded: bool = False,
        on_click: Optional[Callable] = None,
        on_expand: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            height=28,
            **kwargs
        )
        self.pack_propagate(False)

        self.name = name
        self.is_directory = is_directory
        self.level = level
        self.is_expanded = is_expanded
        self.on_click = on_click
        self.on_expand = on_expand

        self._create_widgets()
        self._bind_events()

    def _create_widgets(self) -> None:
        """Create tree item widgets."""
        # Indent based on level
        indent = self.level * 16

        # Container for content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=(indent, 0))

        # Expand arrow (for directories)
        if self.is_directory:
            arrow = "▼" if self.is_expanded else "▶"
            self.expand_btn = ctk.CTkLabel(
                content,
                text=arrow,
                font=(theme.fonts.family, 10),
                text_color=theme.colors.text_muted,
                width=16,
            )
            self.expand_btn.pack(side="left")
            self.expand_btn.bind("<Button-1>", self._on_expand_click)
        else:
            spacer = ctk.CTkFrame(content, width=16, fg_color="transparent")
            spacer.pack(side="left")

        # Icon
        icon = "📁" if self.is_directory else self._get_file_icon()
        self.icon_label = ctk.CTkLabel(
            content,
            text=icon,
            font=(theme.fonts.family, theme.fonts.size_sm),
            width=20,
        )
        self.icon_label.pack(side="left")

        # Name
        self.name_label = ctk.CTkLabel(
            content,
            text=self.name,
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_primary,
            anchor="w",
        )
        self.name_label.pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _get_file_icon(self) -> str:
        """Get icon based on file extension."""
        ext = Path(self.name).suffix.lower()
        icons = {
            ".py": "🐍",
            ".js": "📜",
            ".ts": "📘",
            ".json": "📋",
            ".md": "📝",
            ".txt": "📄",
            ".yaml": "⚙️",
            ".yml": "⚙️",
            ".toml": "⚙️",
            ".rs": "🦀",
            ".go": "🔵",
        }
        return icons.get(ext, "📄")

    def _bind_events(self) -> None:
        """Bind mouse events."""
        for widget in [self, self.name_label, self.icon_label]:
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", self._on_click)

    def _on_enter(self, event) -> None:
        """Handle mouse enter."""
        self.configure(fg_color=theme.colors.bg_light)

    def _on_leave(self, event) -> None:
        """Handle mouse leave."""
        self.configure(fg_color="transparent")

    def _on_click(self, event) -> None:
        """Handle click."""
        if self.on_click:
            self.on_click(self)

    def _on_expand_click(self, event) -> None:
        """Handle expand click."""
        if self.on_expand:
            self.on_expand(self)

    def set_expanded(self, expanded: bool) -> None:
        """Set expanded state."""
        self.is_expanded = expanded
        if self.is_directory and hasattr(self, "expand_btn"):
            self.expand_btn.configure(text="▼" if expanded else "▶")


class FileTree(ctk.CTkScrollableFrame):
    """
    Scrollable file tree for repository browsing.
    """

    def __init__(
        self,
        master,
        on_select: Optional[Callable[[Path], None]] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=theme.dimensions.border_radius,
            **kwargs
        )

        self.on_select = on_select
        self.items: list[FileTreeItem] = []
        self._expanded_dirs: set[str] = set()
        self._root_path: Optional[Path] = None

    def load_directory(self, path: Path, max_depth: int = 3) -> None:
        """Load a directory into the tree."""
        self._root_path = path
        self.clear()
        self._add_directory_contents(path, level=0, max_depth=max_depth)

    def _add_directory_contents(
        self,
        path: Path,
        level: int,
        max_depth: int,
        parent_path: str = "",
    ) -> None:
        """Recursively add directory contents."""
        if level > max_depth:
            return

        try:
            entries = sorted(
                path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            return

        for entry in entries:
            # Skip hidden files and common excludes
            if entry.name.startswith("."):
                continue
            if entry.name in ["node_modules", "__pycache__", "venv", ".venv", "dist", "build"]:
                continue

            rel_path = f"{parent_path}/{entry.name}" if parent_path else entry.name
            is_expanded = rel_path in self._expanded_dirs

            item = FileTreeItem(
                self,
                name=entry.name,
                is_directory=entry.is_dir(),
                level=level,
                is_expanded=is_expanded,
                on_click=lambda i, p=entry: self._on_item_click(i, p),
                on_expand=lambda i, p=entry, rp=rel_path: self._on_item_expand(i, p, rp),
            )
            item.pack(fill="x")
            self.items.append(item)

            # Add children if expanded
            if entry.is_dir() and is_expanded:
                self._add_directory_contents(
                    entry,
                    level + 1,
                    max_depth,
                    rel_path,
                )

    def _on_item_click(self, item: FileTreeItem, path: Path) -> None:
        """Handle item click."""
        if not item.is_directory and self.on_select:
            self.on_select(path)

    def _on_item_expand(self, item: FileTreeItem, path: Path, rel_path: str) -> None:
        """Handle expand/collapse."""
        if item.is_expanded:
            self._expanded_dirs.discard(rel_path)
        else:
            self._expanded_dirs.add(rel_path)

        # Reload tree to reflect change
        if self._root_path:
            self.load_directory(self._root_path)

    def clear(self) -> None:
        """Clear all items."""
        for item in self.items:
            item.destroy()
        self.items.clear()
