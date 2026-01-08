"""
Log viewer component for real-time log output.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Optional

from refactor_bot.gui.theme import theme


class LogEntry:
    """Represents a single log entry."""

    def __init__(
        self,
        message: str,
        level: str = "info",
        timestamp: Optional[datetime] = None,
    ):
        self.message = message
        self.level = level
        self.timestamp = timestamp or datetime.now()

    def format(self) -> str:
        """Format the log entry for display."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{time_str}] {self.message}"


class LogViewer(ctk.CTkFrame):
    """
    Scrollable log viewer with colored output.
    """

    def __init__(
        self,
        master,
        max_lines: int = 500,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_darkest,
            corner_radius=theme.dimensions.border_radius,
            **kwargs
        )

        self.max_lines = max_lines
        self.entries: list[LogEntry] = []

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create log viewer widgets."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=32)
        header.pack(fill="x", padx=8, pady=(8, 4))
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header,
            text="Activity Log",
            font=(theme.fonts.family, theme.fonts.size_sm, "bold"),
            text_color=theme.colors.text_secondary,
        )
        title.pack(side="left")

        # Clear button
        clear_btn = ctk.CTkButton(
            header,
            text="Clear",
            width=60,
            height=24,
            font=(theme.fonts.family, theme.fonts.size_xs),
            fg_color="transparent",
            hover_color=theme.colors.bg_light,
            text_color=theme.colors.text_muted,
            command=self.clear,
        )
        clear_btn.pack(side="right")

        # Text area with scrollbar
        self.textbox = ctk.CTkTextbox(
            self,
            fg_color=theme.colors.bg_darkest,
            text_color=theme.colors.text_secondary,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            wrap="word",
            state="disabled",
        )
        self.textbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def add_log(
        self,
        message: str,
        level: str = "info",
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a log entry."""
        entry = LogEntry(message, level, timestamp)
        self.entries.append(entry)

        # Trim if over max
        if len(self.entries) > self.max_lines:
            self.entries = self.entries[-self.max_lines:]
            self._rebuild_display()
        else:
            self._append_entry(entry)

    def _append_entry(self, entry: LogEntry) -> None:
        """Append a single entry to the display."""
        self.textbox.configure(state="normal")

        # Get color based on level
        colors = {
            "info": theme.colors.text_secondary,
            "success": theme.colors.success,
            "warning": theme.colors.warning,
            "error": theme.colors.error,
            "debug": theme.colors.text_muted,
        }

        formatted = entry.format() + "\n"
        self.textbox.insert("end", formatted)

        # Auto-scroll to bottom
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def _rebuild_display(self) -> None:
        """Rebuild the entire display from entries."""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")

        for entry in self.entries:
            self.textbox.insert("end", entry.format() + "\n")

        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self) -> None:
        """Clear all log entries."""
        self.entries.clear()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

    def log_info(self, message: str) -> None:
        """Log an info message."""
        self.add_log(message, "info")

    def log_success(self, message: str) -> None:
        """Log a success message."""
        self.add_log(f"✓ {message}", "success")

    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        self.add_log(f"⚠ {message}", "warning")

    def log_error(self, message: str) -> None:
        """Log an error message."""
        self.add_log(f"✗ {message}", "error")
