"""
History view for viewing past refactoring runs and rollback.
"""

import customtkinter as ctk
from typing import Callable, Optional

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, app_state
from refactor_bot.backup import BackupManager, BackupInfo


class HistoryItem(ctk.CTkFrame):
    """A single history item."""

    def __init__(
        self,
        master,
        backup: BackupInfo,
        on_select: Optional[Callable] = None,
        on_rollback: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.border_radius,
            **kwargs
        )

        self.backup = backup
        self.on_select = on_select
        self.on_rollback = on_rollback

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create item widgets."""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=12)

        # Left - Info
        info_frame = ctk.CTkFrame(content, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        # Run ID and date
        header = ctk.CTkFrame(info_frame, fg_color="transparent")
        header.pack(fill="x")

        id_label = ctk.CTkLabel(
            header,
            text=self.backup.run_id,
            font=(theme.fonts.family_mono, theme.fonts.size_md, "bold"),
            text_color=theme.colors.text_primary,
        )
        id_label.pack(side="left")

        date_label = ctk.CTkLabel(
            header,
            text=self.backup.created_at.strftime("%Y-%m-%d %H:%M"),
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        date_label.pack(side="left", padx=(16, 0))

        # Details
        details = ctk.CTkFrame(info_frame, fg_color="transparent")
        details.pack(fill="x", pady=(4, 0))

        repo_label = ctk.CTkLabel(
            details,
            text=f"📁 {self.backup.repo_name}",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        repo_label.pack(side="left")

        # Size
        from refactor_bot.util import format_size
        size_label = ctk.CTkLabel(
            details,
            text=f"💾 {format_size(self.backup.size_bytes)}",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        size_label.pack(side="left", padx=(16, 0))

        # Backup type indicators
        if self.backup.bundle_path:
            bundle_label = ctk.CTkLabel(
                details,
                text="Git Bundle ✓",
                font=(theme.fonts.family, theme.fonts.size_xs),
                text_color=theme.colors.success,
            )
            bundle_label.pack(side="left", padx=(16, 0))

        if self.backup.archive_path:
            archive_label = ctk.CTkLabel(
                details,
                text="Archive ✓",
                font=(theme.fonts.family, theme.fonts.size_xs),
                text_color=theme.colors.success,
            )
            archive_label.pack(side="left", padx=(8, 0))

        # Right - Actions
        actions_frame = ctk.CTkFrame(content, fg_color="transparent")
        actions_frame.pack(side="right")

        rollback_btn = ctk.CTkButton(
            actions_frame,
            text="Rollback",
            width=100,
            height=32,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_button_style("danger"),
            command=lambda: self.on_rollback(self.backup) if self.on_rollback else None,
        )
        rollback_btn.pack()


class HistoryView(ctk.CTkFrame):
    """
    History view showing past refactoring runs with rollback capability.
    """

    def __init__(self, master, on_navigate: Callable[[AppView], None], **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self._backups: list[BackupInfo] = []
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
            text="History",
            font=(theme.fonts.family, theme.fonts.size_title, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(side="left")

        refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            width=80,
            height=36,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_button_style("outline"),
            command=self.load_history,
        )
        refresh_btn.pack(side="right")

        # Filter section
        filter_frame = ctk.CTkFrame(
            container,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.border_radius,
        )
        filter_frame.pack(fill="x", pady=(0, 16))

        filter_content = ctk.CTkFrame(filter_frame, fg_color="transparent")
        filter_content.pack(fill="x", padx=16, pady=12)

        filter_label = ctk.CTkLabel(
            filter_content,
            text="Filter by repository:",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        filter_label.pack(side="left")

        self.filter_entry = ctk.CTkEntry(
            filter_content,
            placeholder_text="Enter repository name...",
            width=300,
            height=32,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_input_style(),
        )
        self.filter_entry.pack(side="left", padx=(8, 0))
        self.filter_entry.bind("<Return>", lambda e: self.load_history())

        # Stats
        self.stats_label = ctk.CTkLabel(
            filter_content,
            text="",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        self.stats_label.pack(side="right")

        # History list
        self.list_frame = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent",
        )
        self.list_frame.pack(fill="both", expand=True)

        # Empty state
        self.empty_label = ctk.CTkLabel(
            self.list_frame,
            text="No backups found.\nRun a refactoring to create your first backup.",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_muted,
            justify="center",
        )

        # Rollback confirmation dialog
        self._create_rollback_dialog()

    def _create_rollback_dialog(self) -> None:
        """Create the rollback confirmation dialog."""
        self.dialog_overlay = ctk.CTkFrame(
            self,
            fg_color=("gray90", "gray10"),
        )

        dialog = ctk.CTkFrame(
            self.dialog_overlay,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
            width=400,
        )
        dialog.place(relx=0.5, rely=0.5, anchor="center")

        dialog_content = ctk.CTkFrame(dialog, fg_color="transparent")
        dialog_content.pack(fill="both", padx=24, pady=24)

        # Warning icon
        icon = ctk.CTkLabel(
            dialog_content,
            text="⚠️",
            font=(theme.fonts.family, 32),
        )
        icon.pack()

        title = ctk.CTkLabel(
            dialog_content,
            text="Confirm Rollback",
            font=(theme.fonts.family, theme.fonts.size_xl, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(pady=(12, 8))

        self.dialog_message = ctk.CTkLabel(
            dialog_content,
            text="",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
            wraplength=350,
            justify="center",
        )
        self.dialog_message.pack()

        warning = ctk.CTkLabel(
            dialog_content,
            text="This will overwrite the current repository state!",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.warning,
        )
        warning.pack(pady=(12, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(dialog_content, fg_color="transparent")
        btn_frame.pack(pady=(24, 0))

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            height=40,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("outline"),
            command=self._hide_dialog,
        )
        cancel_btn.pack(side="left", padx=(0, 12))

        self.confirm_btn = ctk.CTkButton(
            btn_frame,
            text="Rollback",
            width=100,
            height=40,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("danger"),
            command=self._confirm_rollback,
        )
        self.confirm_btn.pack(side="left")

    def load_history(self) -> None:
        """Load backup history."""
        # Clear existing items
        for widget in self.list_frame.winfo_children():
            if widget != self.empty_label:
                widget.destroy()

        # Get filter
        repo_filter = self.filter_entry.get().strip() or None

        # Load backups
        self._backups = BackupManager.list_backups(repo_filter)

        if not self._backups:
            self.empty_label.pack(pady=50)
            self.stats_label.configure(text="No backups")
            return

        self.empty_label.pack_forget()
        self.stats_label.configure(text=f"{len(self._backups)} backup(s)")

        # Create items
        for backup in self._backups:
            item = HistoryItem(
                self.list_frame,
                backup=backup,
                on_rollback=self._show_rollback_dialog,
            )
            item.pack(fill="x", pady=(0, 8))

    def _show_rollback_dialog(self, backup: BackupInfo) -> None:
        """Show the rollback confirmation dialog."""
        self._rollback_backup = backup
        self.dialog_message.configure(
            text=f"Rollback to backup from {backup.created_at.strftime('%Y-%m-%d %H:%M')}?"
        )
        self.dialog_overlay.place(x=0, y=0, relwidth=1, relheight=1)

    def _hide_dialog(self) -> None:
        """Hide the rollback dialog."""
        self.dialog_overlay.place_forget()

    def _confirm_rollback(self) -> None:
        """Execute the rollback."""
        if not hasattr(self, "_rollback_backup"):
            return

        backup = self._rollback_backup
        self._hide_dialog()

        try:
            from refactor_bot.backup import rollback
            rollback(backup.run_id)

            # Show success
            self.stats_label.configure(
                text=f"Rolled back to {backup.run_id}",
            )

        except Exception as e:
            self.stats_label.configure(
                text=f"Rollback failed: {e}",
            )
