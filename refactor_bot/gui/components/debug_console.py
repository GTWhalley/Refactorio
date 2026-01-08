"""
Debug console component for viewing logs and errors.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Optional
import sys
import io
import traceback

from refactor_bot.gui.theme import theme


class DebugConsole(ctk.CTkFrame):
    """
    Debug console showing logs, errors, and debug information.
    Collapsible panel at the bottom of the screen.
    """

    _instance: Optional["DebugConsole"] = None

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_darkest,
            corner_radius=0,
            **kwargs
        )

        DebugConsole._instance = self

        self._expanded = True
        self._max_lines = 500

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create console widgets."""
        # Header bar (always visible)
        self.header = ctk.CTkFrame(
            self,
            fg_color=theme.colors.bg_medium,
            height=32,
            corner_radius=0,
        )
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        # Toggle button
        self.toggle_btn = ctk.CTkButton(
            self.header,
            text="▼ Debug Console",
            width=140,
            height=24,
            font=(theme.fonts.family, theme.fonts.size_sm),
            fg_color="transparent",
            hover_color=theme.colors.bg_light,
            text_color=theme.colors.text_secondary,
            anchor="w",
            command=self._toggle,
        )
        self.toggle_btn.pack(side="left", padx=8, pady=4)

        # Clear button
        clear_btn = ctk.CTkButton(
            self.header,
            text="Clear",
            width=60,
            height=24,
            font=(theme.fonts.family, theme.fonts.size_xs),
            fg_color="transparent",
            hover_color=theme.colors.bg_light,
            text_color=theme.colors.text_muted,
            command=self.clear,
        )
        clear_btn.pack(side="right", padx=8, pady=4)

        # Copy button
        copy_btn = ctk.CTkButton(
            self.header,
            text="Copy All",
            width=70,
            height=24,
            font=(theme.fonts.family, theme.fonts.size_xs),
            fg_color="transparent",
            hover_color=theme.colors.bg_light,
            text_color=theme.colors.text_muted,
            command=self._copy_all,
        )
        copy_btn.pack(side="right", padx=(0, 4), pady=4)

        # Content area
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        # Text widget
        self.text = ctk.CTkTextbox(
            self.content,
            font=(theme.fonts.family_mono, 11),
            fg_color=theme.colors.bg_darkest,
            text_color=theme.colors.text_secondary,
            height=150,
            wrap="word",
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

        # Log initial message
        self.log("Debug console initialized", "info")

    def _toggle(self) -> None:
        """Toggle console visibility."""
        self._expanded = not self._expanded

        if self._expanded:
            self.content.pack(fill="both", expand=True)
            self.toggle_btn.configure(text="▼ Debug Console")
        else:
            self.content.pack_forget()
            self.toggle_btn.configure(text="▶ Debug Console")

    def _copy_all(self) -> None:
        """Copy all console text to clipboard."""
        self.text.configure(state="normal")
        text = self.text.get("1.0", "end-1c")
        self.text.configure(state="disabled")

        self.clipboard_clear()
        self.clipboard_append(text)

        # Show feedback
        old_text = self.toggle_btn.cget("text")
        self.toggle_btn.configure(text="✓ Copied!")
        self.after(1500, lambda: self.toggle_btn.configure(text=old_text))

    def log(self, message: str, level: str = "info") -> None:
        """Log a message to the console."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        level_colors = {
            "info": theme.colors.text_secondary,
            "success": theme.colors.success,
            "warning": theme.colors.warning,
            "error": theme.colors.error,
            "debug": theme.colors.text_muted,
        }

        level_prefix = {
            "info": "INFO",
            "success": "OK",
            "warning": "WARN",
            "error": "ERROR",
            "debug": "DEBUG",
        }

        prefix = level_prefix.get(level, "INFO")
        formatted = f"[{timestamp}] [{prefix}] {message}\n"

        self.text.configure(state="normal")
        self.text.insert("end", formatted)

        # Limit lines
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > self._max_lines:
            self.text.delete("1.0", f"{lines - self._max_lines}.0")

        self.text.see("end")
        self.text.configure(state="disabled")

    def log_exception(self, e: Exception, context: str = "") -> None:
        """Log an exception with traceback."""
        tb = traceback.format_exc()
        if context:
            self.log(f"{context}: {type(e).__name__}: {e}", "error")
        else:
            self.log(f"{type(e).__name__}: {e}", "error")
        self.log(f"Traceback:\n{tb}", "debug")

    def clear(self) -> None:
        """Clear the console."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.log("Console cleared", "info")

    @classmethod
    def get_instance(cls) -> Optional["DebugConsole"]:
        """Get the singleton instance."""
        return cls._instance


# Global logging function
def debug_log(message: str, level: str = "info") -> None:
    """Log to the debug console if available."""
    console = DebugConsole.get_instance()
    if console:
        console.after(0, lambda: console.log(message, level))


def debug_error(e: Exception, context: str = "") -> None:
    """Log an exception to the debug console if available."""
    console = DebugConsole.get_instance()
    if console:
        console.after(0, lambda: console.log_exception(e, context))
