"""
Animated progress bar component.
"""

import customtkinter as ctk
from typing import Optional

from refactor_bot.gui.theme import theme


class AnimatedProgressBar(ctk.CTkFrame):
    """
    Animated progress bar with percentage and label.
    """

    def __init__(
        self,
        master,
        label: str = "",
        show_percentage: bool = True,
        height: int = 20,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self._progress = 0.0
        self._show_percentage = show_percentage
        self._bar_height = height

        self._create_widgets(label)

    def _create_widgets(self, label: str) -> None:
        """Create progress bar widgets."""
        # Header with label and percentage
        if label or self._show_percentage:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", pady=(0, 4))

            if label:
                self.label = ctk.CTkLabel(
                    header,
                    text=label,
                    font=(theme.fonts.family, theme.fonts.size_sm),
                    text_color=theme.colors.text_secondary,
                )
                self.label.pack(side="left")

            if self._show_percentage:
                self.percentage_label = ctk.CTkLabel(
                    header,
                    text="0%",
                    font=(theme.fonts.family, theme.fonts.size_sm),
                    text_color=theme.colors.text_primary,
                )
                self.percentage_label.pack(side="right")

        # Progress bar container
        self.bar_container = ctk.CTkFrame(
            self,
            height=self._bar_height,
            fg_color=theme.colors.progress_bg,
            corner_radius=self._bar_height // 2,
        )
        self.bar_container.pack(fill="x")
        self.bar_container.pack_propagate(False)

        # Progress fill
        self.bar_fill = ctk.CTkFrame(
            self.bar_container,
            height=self._bar_height,
            fg_color=theme.colors.progress_fill,
            corner_radius=self._bar_height // 2,
        )
        self.bar_fill.place(x=0, y=0, relwidth=0)

    def set_progress(self, value: float) -> None:
        """
        Set progress value (0.0 to 1.0).
        """
        self._progress = max(0.0, min(1.0, value))

        # Update fill width
        self.bar_fill.place(x=0, y=0, relwidth=self._progress)

        # Update percentage label
        if self._show_percentage:
            self.percentage_label.configure(text=f"{int(self._progress * 100)}%")

    def set_color(self, color: str) -> None:
        """Set the progress bar color."""
        self.bar_fill.configure(fg_color=color)

    def get_progress(self) -> float:
        """Get current progress value."""
        return self._progress


class BatchProgressIndicator(ctk.CTkFrame):
    """
    Visual indicator showing batch progress as a series of dots/squares.
    """

    def __init__(
        self,
        master,
        total: int = 10,
        size: int = 16,
        spacing: int = 4,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.total = total
        self.size = size
        self.spacing = spacing
        self.indicators: list[ctk.CTkLabel] = []
        self._current = 0

        self._create_indicators()

    def _create_indicators(self) -> None:
        """Create batch indicators."""
        for i in range(self.total):
            indicator = ctk.CTkLabel(
                self,
                text="○",
                font=(theme.fonts.family, self.size),
                text_color=theme.colors.text_muted,
                width=self.size + self.spacing,
            )
            indicator.pack(side="left")
            self.indicators.append(indicator)

    def set_total(self, total: int) -> None:
        """Update the total number of batches."""
        # Clear existing
        for indicator in self.indicators:
            indicator.destroy()
        self.indicators.clear()

        self.total = total
        self._create_indicators()

    def set_current(self, current: int) -> None:
        """Set the current batch (0-indexed)."""
        self._current = current

        for i, indicator in enumerate(self.indicators):
            if i < current:
                # Completed
                indicator.configure(text="●", text_color=theme.colors.success)
            elif i == current:
                # Current
                indicator.configure(text="◉", text_color=theme.colors.accent_secondary)
            else:
                # Pending
                indicator.configure(text="○", text_color=theme.colors.text_muted)

    def set_status(self, index: int, status: str) -> None:
        """Set status for a specific batch."""
        if 0 <= index < len(self.indicators):
            indicator = self.indicators[index]
            if status == "completed":
                indicator.configure(text="●", text_color=theme.colors.success)
            elif status == "failed":
                indicator.configure(text="●", text_color=theme.colors.error)
            elif status == "skipped":
                indicator.configure(text="○", text_color=theme.colors.warning)
            elif status == "current":
                indicator.configure(text="◉", text_color=theme.colors.accent_secondary)
            else:
                indicator.configure(text="○", text_color=theme.colors.text_muted)
