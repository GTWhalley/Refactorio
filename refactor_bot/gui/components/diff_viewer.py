"""
Diff viewer component with syntax highlighting.
"""

import customtkinter as ctk
from typing import Optional, Tuple

from refactor_bot.gui.theme import theme


class DiffViewer(ctk.CTkFrame):
    """
    Diff viewer with syntax highlighting for unified diffs.

    Shows additions in green, deletions in red, and context in gray.
    """

    def __init__(
        self,
        master,
        show_line_numbers: bool = True,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_darkest,
            corner_radius=theme.dimensions.border_radius,
            **kwargs
        )

        self.show_line_numbers = show_line_numbers
        self._diff_content = ""

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create diff viewer widgets."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=36)
        header.pack(fill="x", padx=12, pady=(8, 4))
        header.pack_propagate(False)

        self.title_label = ctk.CTkLabel(
            header,
            text="Diff Preview",
            font=(theme.fonts.family, theme.fonts.size_sm, "bold"),
            text_color=theme.colors.text_secondary,
        )
        self.title_label.pack(side="left")

        # Stats
        self.stats_label = ctk.CTkLabel(
            header,
            text="",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        self.stats_label.pack(side="right")

        # File tabs (for multi-file diffs)
        self.file_tabs_frame = ctk.CTkFrame(self, fg_color="transparent", height=32)
        self.file_tabs_frame.pack(fill="x", padx=8, pady=(0, 4))
        self.file_tabs_frame.pack_propagate(False)

        # Main content area
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Line numbers (optional)
        if self.show_line_numbers:
            self.line_numbers = ctk.CTkTextbox(
                content_frame,
                width=50,
                fg_color=theme.colors.bg_dark,
                text_color=theme.colors.text_muted,
                font=(theme.fonts.family_mono, theme.fonts.size_sm),
                state="disabled",
            )
            self.line_numbers.pack(side="left", fill="y")

        # Diff content
        self.diff_text = ctk.CTkTextbox(
            content_frame,
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            wrap="none",
        )
        self.diff_text.pack(side="left", fill="both", expand=True)

        # Synchronize scrolling between line numbers and diff content
        if self.show_line_numbers:
            self._sync_scrolling()

    def _sync_scrolling(self) -> None:
        """Synchronize scrolling between line numbers and diff content."""
        # Get the underlying tkinter text widgets
        diff_textbox = self.diff_text._textbox
        line_textbox = self.line_numbers._textbox

        # Flag to prevent infinite scroll loops
        self._syncing = False

        def on_diff_scroll(*args):
            if self._syncing:
                return
            self._syncing = True
            # Sync line numbers to match diff position
            line_textbox.yview_moveto(args[0])
            self._syncing = False

        def on_line_scroll(*args):
            if self._syncing:
                return
            self._syncing = True
            # Sync diff to match line numbers position
            diff_textbox.yview_moveto(args[0])
            self._syncing = False

        # Configure scroll commands
        diff_textbox.configure(yscrollcommand=on_diff_scroll)
        line_textbox.configure(yscrollcommand=on_line_scroll)

        # Also sync mousewheel events
        def on_diff_mousewheel(event):
            if self._syncing:
                return
            self._syncing = True
            # Scroll line numbers by the same amount
            line_textbox.yview_scroll(int(-1 * (event.delta / 120)), "units")
            self._syncing = False

        def on_line_mousewheel(event):
            if self._syncing:
                return
            self._syncing = True
            # Scroll diff by the same amount
            diff_textbox.yview_scroll(int(-1 * (event.delta / 120)), "units")
            self._syncing = False

        diff_textbox.bind("<MouseWheel>", on_diff_mousewheel)
        line_textbox.bind("<MouseWheel>", on_line_mousewheel)
        # Linux uses different events
        diff_textbox.bind("<Button-4>", lambda e: on_diff_mousewheel(type('Event', (), {'delta': 120})))
        diff_textbox.bind("<Button-5>", lambda e: on_diff_mousewheel(type('Event', (), {'delta': -120})))
        line_textbox.bind("<Button-4>", lambda e: on_line_mousewheel(type('Event', (), {'delta': 120})))
        line_textbox.bind("<Button-5>", lambda e: on_line_mousewheel(type('Event', (), {'delta': -120})))

    def set_diff(self, diff: str, filename: Optional[str] = None) -> None:
        """Set the diff content to display."""
        self._diff_content = diff

        # Parse and display
        self.diff_text.configure(state="normal")
        self.diff_text.delete("1.0", "end")

        if self.show_line_numbers:
            self.line_numbers.configure(state="normal")
            self.line_numbers.delete("1.0", "end")

        lines = diff.split("\n")
        line_num = 1
        additions = 0
        deletions = 0
        current_file = filename or ""

        for line in lines:
            # Track file changes
            if line.startswith("+++ b/"):
                current_file = line[6:]
            elif line.startswith("--- a/"):
                pass

            # Insert the line
            self.diff_text.insert("end", line + "\n")

            # Line numbers
            if self.show_line_numbers:
                self.line_numbers.insert("end", f"{line_num:4}\n")

            line_num += 1

            # Count stats
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1

        self.diff_text.configure(state="disabled")
        if self.show_line_numbers:
            self.line_numbers.configure(state="disabled")

        # Update stats
        self.stats_label.configure(
            text=f"+{additions} -{deletions}"
        )

        # Update title
        if current_file:
            self.title_label.configure(text=f"Diff: {current_file}")

    def set_title(self, title: str) -> None:
        """Set the viewer title."""
        self.title_label.configure(text=title)

    def clear(self) -> None:
        """Clear the diff display."""
        self._diff_content = ""
        self.diff_text.configure(state="normal")
        self.diff_text.delete("1.0", "end")
        self.diff_text.configure(state="disabled")

        if self.show_line_numbers:
            self.line_numbers.configure(state="normal")
            self.line_numbers.delete("1.0", "end")
            self.line_numbers.configure(state="disabled")

        self.stats_label.configure(text="")
        self.title_label.configure(text="Diff Preview")


class SideBySideDiffViewer(ctk.CTkFrame):
    """
    Side-by-side diff viewer showing old and new versions.
    """

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_darkest,
            corner_radius=theme.dimensions.border_radius,
            **kwargs
        )

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create side-by-side viewer widgets."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=36)
        header.pack(fill="x", padx=12, pady=(8, 4))

        self.title_label = ctk.CTkLabel(
            header,
            text="Side-by-Side Comparison",
            font=(theme.fonts.family, theme.fonts.size_sm, "bold"),
            text_color=theme.colors.text_secondary,
        )
        self.title_label.pack(side="left")

        # Content area with two panes
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Left pane (old)
        left_frame = ctk.CTkFrame(content, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        left_header = ctk.CTkLabel(
            left_frame,
            text="Original",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.error,
        )
        left_header.pack(anchor="w", pady=(0, 4))

        self.left_text = ctk.CTkTextbox(
            left_frame,
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            wrap="none",
        )
        self.left_text.pack(fill="both", expand=True)

        # Right pane (new)
        right_frame = ctk.CTkFrame(content, fg_color="transparent")
        right_frame.pack(side="right", fill="both", expand=True, padx=(4, 0))

        right_header = ctk.CTkLabel(
            right_frame,
            text="Modified",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.success,
        )
        right_header.pack(anchor="w", pady=(0, 4))

        self.right_text = ctk.CTkTextbox(
            right_frame,
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_primary,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            wrap="none",
        )
        self.right_text.pack(fill="both", expand=True)

    def set_content(self, old_content: str, new_content: str) -> None:
        """Set the old and new content."""
        self.left_text.configure(state="normal")
        self.left_text.delete("1.0", "end")
        self.left_text.insert("1.0", old_content)
        self.left_text.configure(state="disabled")

        self.right_text.configure(state="normal")
        self.right_text.delete("1.0", "end")
        self.right_text.insert("1.0", new_content)
        self.right_text.configure(state="disabled")
