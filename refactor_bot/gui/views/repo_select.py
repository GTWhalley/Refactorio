"""
Repository selection view.
"""

import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional
import threading

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, RepoState, app_state
from refactor_bot.gui.components.file_tree import FileTree


class RepoSelectView(ctk.CTkFrame):
    """
    Repository selection view with directory browser and recent repos.
    """

    def __init__(self, master, on_navigate: Callable[[AppView], None], **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create view widgets."""
        # Main container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=24)

        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 24))

        title = ctk.CTkLabel(
            header,
            text="Select Repository",
            font=(theme.fonts.family, theme.fonts.size_title, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Choose a repository to refactor",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        # Main content - two columns
        content = ctk.CTkFrame(container, fg_color="transparent")
        content.pack(fill="both", expand=True)

        # Left column - Selection
        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 12))

        # Browse section
        browse_card = ctk.CTkFrame(
            left_col,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )
        browse_card.pack(fill="x", pady=(0, 16))

        browse_content = ctk.CTkFrame(browse_card, fg_color="transparent")
        browse_content.pack(fill="x", padx=20, pady=20)

        browse_label = ctk.CTkLabel(
            browse_content,
            text="Browse for Repository",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        browse_label.pack(anchor="w")

        browse_desc = ctk.CTkLabel(
            browse_content,
            text="Select a directory containing your project",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        browse_desc.pack(anchor="w", pady=(4, 16))

        # Path input
        path_frame = ctk.CTkFrame(browse_content, fg_color="transparent")
        path_frame.pack(fill="x")

        self.path_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="Enter path or click Browse...",
            height=44,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            **theme.get_input_style(),
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.path_entry.bind("<Return>", lambda e: self._validate_and_select())

        browse_btn = ctk.CTkButton(
            path_frame,
            text="Browse",
            width=100,
            height=44,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("secondary"),
            command=self._browse_directory,
        )
        browse_btn.pack(side="right")

        # Drag and drop hint
        drop_hint = ctk.CTkLabel(
            browse_content,
            text="Or drag and drop a folder here",
            font=(theme.fonts.family, theme.fonts.size_xs),
            text_color=theme.colors.text_muted,
        )
        drop_hint.pack(anchor="w", pady=(8, 0))

        # Validation status
        self.validation_frame = ctk.CTkFrame(
            left_col,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )
        # Initially hidden
        self.validation_content = ctk.CTkFrame(self.validation_frame, fg_color="transparent")
        self.validation_content.pack(fill="x", padx=20, pady=20)

        self.validation_icon = ctk.CTkLabel(
            self.validation_content,
            text="",
            font=(theme.fonts.family, 24),
        )
        self.validation_icon.pack(side="left")

        self.validation_info = ctk.CTkFrame(self.validation_content, fg_color="transparent")
        self.validation_info.pack(side="left", fill="x", expand=True, padx=(12, 0))

        self.validation_title = ctk.CTkLabel(
            self.validation_info,
            text="",
            font=(theme.fonts.family, theme.fonts.size_md, "bold"),
            text_color=theme.colors.text_primary,
        )
        self.validation_title.pack(anchor="w")

        self.validation_details = ctk.CTkLabel(
            self.validation_info,
            text="",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        self.validation_details.pack(anchor="w", pady=(2, 0))

        self.select_btn = ctk.CTkButton(
            self.validation_content,
            text="Select",
            width=100,
            height=40,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("primary"),
            command=self._confirm_selection,
        )
        self.select_btn.pack(side="right")

        # Right column - File preview
        right_col = ctk.CTkFrame(content, fg_color="transparent", width=350)
        right_col.pack(side="right", fill="both", padx=(12, 0))
        right_col.pack_propagate(False)

        preview_label = ctk.CTkLabel(
            right_col,
            text="File Preview",
            font=(theme.fonts.family, theme.fonts.size_md, "bold"),
            text_color=theme.colors.text_secondary,
        )
        preview_label.pack(anchor="w", pady=(0, 8))

        self.file_tree = FileTree(right_col)
        self.file_tree.pack(fill="both", expand=True)

    def _browse_directory(self) -> None:
        """Open directory browser."""
        directory = filedialog.askdirectory(
            title="Select Repository Directory",
            initialdir=str(Path.home()),
        )
        if directory:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, directory)
            self._validate_and_select()

    def _validate_and_select(self) -> None:
        """Validate the selected path."""
        path_str = self.path_entry.get().strip()
        if not path_str:
            return

        path = Path(path_str)

        def validate():
            is_valid = True
            errors = []
            is_git = False
            file_count = 0
            branch = ""

            if not path.exists():
                is_valid = False
                errors.append("Directory does not exist")
            elif not path.is_dir():
                is_valid = False
                errors.append("Path is not a directory")
            else:
                # Check for git
                git_dir = path / ".git"
                is_git = git_dir.exists()

                # Count files
                try:
                    file_count = sum(1 for _ in path.rglob("*") if _.is_file())
                except Exception:
                    file_count = 0

                # Get branch if git
                if is_git:
                    try:
                        from git import Repo
                        repo = Repo(path)
                        branch = repo.active_branch.name
                    except Exception:
                        branch = "unknown"

            # Update UI on main thread
            self.after(0, lambda: self._show_validation(
                path, is_valid, errors, is_git, file_count, branch
            ))

        threading.Thread(target=validate, daemon=True).start()

    def _show_validation(
        self,
        path: Path,
        is_valid: bool,
        errors: list,
        is_git: bool,
        file_count: int,
        branch: str,
    ) -> None:
        """Show validation results."""
        self.validation_frame.pack(fill="x", pady=(0, 16))

        if is_valid:
            self.validation_icon.configure(text="✓")
            self.validation_title.configure(
                text=path.name,
                text_color=theme.colors.text_primary,
            )

            details = []
            if is_git:
                details.append(f"Git repo on branch: {branch}")
            details.append(f"{file_count} files")

            self.validation_details.configure(text=" • ".join(details))
            self.validation_frame.configure(fg_color=theme.colors.success_bg)
            self.select_btn.configure(state="normal")

            # Show file tree
            self.file_tree.load_directory(path, max_depth=2)

            # Store the validated path
            self._validated_path = path
            self._is_git = is_git
            self._branch = branch
            self._file_count = file_count

        else:
            self.validation_icon.configure(text="✗")
            self.validation_title.configure(
                text="Invalid Directory",
                text_color=theme.colors.error,
            )
            self.validation_details.configure(text=", ".join(errors))
            self.validation_frame.configure(fg_color=theme.colors.error_bg)
            self.select_btn.configure(state="disabled")
            self.file_tree.clear()

    def _confirm_selection(self) -> None:
        """Confirm repository selection and navigate."""
        if hasattr(self, "_validated_path"):
            # Update app state
            app_state.repo = RepoState(
                path=self._validated_path,
                name=self._validated_path.name,
                is_git=self._is_git,
                branch=self._branch,
                file_count=self._file_count,
            )

            # Navigate to configuration
            self.on_navigate(AppView.CONFIGURATION)
