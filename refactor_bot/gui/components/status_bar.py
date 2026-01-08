"""
Status bar component for the bottom of the application.
"""

import customtkinter as ctk
from typing import Optional

from refactor_bot.gui.theme import theme


class StatusBar(ctk.CTkFrame):
    """
    Status bar showing current status, progress, and time.
    """

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            height=32,
            fg_color=theme.colors.bg_darkest,
            corner_radius=0,
            **kwargs
        )

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create status bar widgets."""
        # Left section - status message
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        self.status_label.pack(side="left", padx=16)

        # Right section - info
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.pack(side="right", padx=16)

        # Repo indicator
        self.repo_label = ctk.CTkLabel(
            right_frame,
            text="No repository selected",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        self.repo_label.pack(side="right")

        # Separator
        sep = ctk.CTkLabel(
            right_frame,
            text=" │ ",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.border,
        )
        sep.pack(side="right")

        # Progress info
        self.progress_label = ctk.CTkLabel(
            right_frame,
            text="",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        self.progress_label.pack(side="right")

    def set_status(self, message: str, status_type: str = "info") -> None:
        """Set the status message."""
        colors = {
            "info": theme.colors.text_secondary,
            "success": theme.colors.success,
            "warning": theme.colors.warning,
            "error": theme.colors.error,
        }
        color = colors.get(status_type, theme.colors.text_secondary)
        self.status_label.configure(text=message, text_color=color)

    def set_repo(self, repo_name: Optional[str]) -> None:
        """Set the current repository name."""
        if repo_name:
            self.repo_label.configure(
                text=f"📁 {repo_name}",
                text_color=theme.colors.text_secondary,
            )
        else:
            self.repo_label.configure(
                text="No repository selected",
                text_color=theme.colors.text_muted,
            )

    def set_progress(self, current: int, total: int) -> None:
        """Set the progress indicator."""
        if total > 0:
            self.progress_label.configure(
                text=f"Batch {current}/{total}",
                text_color=theme.colors.text_secondary,
            )
        else:
            self.progress_label.configure(text="")
