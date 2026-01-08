"""
Activity indicator component for long-running operations.
"""

import customtkinter as ctk
import threading
import time
from typing import Optional

from refactor_bot.gui.theme import theme


class ActivityIndicator(ctk.CTkFrame):
    """
    Animated activity indicator showing that Claude is working.

    Features:
    - Spinning animation
    - Current activity message
    - Elapsed time display
    - Pulsing effect
    """

    def __init__(
        self,
        master,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
            **kwargs
        )

        self._is_active = False
        self._spinner_index = 0
        self._spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._activity_message = ""
        self._elapsed_seconds = 0.0

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create indicator widgets."""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=12)

        # Left side - spinner and message
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        # Spinner
        self.spinner_label = ctk.CTkLabel(
            left,
            text=self._spinner_chars[0],
            font=(theme.fonts.family, 20, "bold"),
            text_color=theme.colors.accent_primary,
            width=30,
        )
        self.spinner_label.pack(side="left")

        # Activity message
        self.message_label = ctk.CTkLabel(
            left,
            text="Waiting...",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_primary,
        )
        self.message_label.pack(side="left", padx=(8, 0))

        # Right side - elapsed time
        self.time_label = ctk.CTkLabel(
            content,
            text="0:00",
            font=(theme.fonts.family, theme.fonts.size_md, "bold"),
            text_color=theme.colors.text_secondary,
        )
        self.time_label.pack(side="right")

        time_prefix = ctk.CTkLabel(
            content,
            text="Elapsed: ",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        time_prefix.pack(side="right")

        # Initially hidden
        self.pack_forget()

    def start(self) -> None:
        """Start the activity indicator."""
        self._is_active = True
        self._elapsed_seconds = 0
        self.pack(fill="x", pady=(0, 12))
        self._animate()

    def stop(self) -> None:
        """Stop the activity indicator."""
        self._is_active = False
        self.pack_forget()

    def update_activity(self, message: str, elapsed: float) -> None:
        """Update the activity display.

        Args:
            message: Current activity message
            elapsed: Elapsed seconds
        """
        self._activity_message = message
        self._elapsed_seconds = elapsed

        # Schedule UI update on main thread
        self.after(0, self._update_display)

    def _update_display(self) -> None:
        """Update UI elements (must be called from main thread)."""
        if not self._is_active:
            return

        self.message_label.configure(text=self._activity_message)

        # Format elapsed time
        mins = int(self._elapsed_seconds // 60)
        secs = int(self._elapsed_seconds % 60)
        self.time_label.configure(text=f"{mins}:{secs:02d}")

    def _animate(self) -> None:
        """Animate the spinner."""
        if not self._is_active:
            return

        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_chars)
        self.spinner_label.configure(text=self._spinner_chars[self._spinner_index])

        # Continue animation
        self.after(100, self._animate)


class BatchActivityDisplay(ctk.CTkFrame):
    """
    Detailed activity display for batch processing.

    Shows:
    - Current batch info
    - Activity spinner with message
    - Batch-specific elapsed time
    - Operation stage indicator
    """

    STAGES = [
        ("context", "Building context"),
        ("claude", "Waiting for Claude"),
        ("patch", "Applying patch"),
        ("verify", "Verifying"),
    ]

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
            **kwargs
        )

        self._is_active = False
        self._current_stage = 0
        self._batch_start_time = 0.0
        self._stage_start_time = 0.0

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create display widgets."""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=12)

        # Batch header
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        self.batch_label = ctk.CTkLabel(
            header,
            text="Processing Batch",
            font=(theme.fonts.family, theme.fonts.size_md, "bold"),
            text_color=theme.colors.text_primary,
        )
        self.batch_label.pack(side="left")

        self.batch_time_label = ctk.CTkLabel(
            header,
            text="0:00",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.accent_primary,
        )
        self.batch_time_label.pack(side="right")

        # Stage indicators
        self.stage_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.stage_frame.pack(fill="x", pady=(4, 8))

        self.stage_labels = []
        for i, (stage_id, stage_name) in enumerate(self.STAGES):
            stage_container = ctk.CTkFrame(self.stage_frame, fg_color="transparent")
            stage_container.pack(side="left", padx=(0, 16))

            indicator = ctk.CTkLabel(
                stage_container,
                text="○",
                font=(theme.fonts.family, 14),
                text_color=theme.colors.text_muted,
            )
            indicator.pack(side="left")

            label = ctk.CTkLabel(
                stage_container,
                text=stage_name,
                font=(theme.fonts.family, theme.fonts.size_sm),
                text_color=theme.colors.text_muted,
            )
            label.pack(side="left", padx=(4, 0))

            self.stage_labels.append((indicator, label))

        # Current activity
        activity_frame = ctk.CTkFrame(content, fg_color="transparent")
        activity_frame.pack(fill="x")

        self.spinner_label = ctk.CTkLabel(
            activity_frame,
            text="⠋",
            font=(theme.fonts.family, 16, "bold"),
            text_color=theme.colors.accent_secondary,
        )
        self.spinner_label.pack(side="left")

        self.activity_label = ctk.CTkLabel(
            activity_frame,
            text="Initializing...",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        self.activity_label.pack(side="left", padx=(8, 0))

        self.stage_time_label = ctk.CTkLabel(
            activity_frame,
            text="",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        self.stage_time_label.pack(side="right")

        # Initially hidden
        self.pack_forget()

        self._spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_index = 0

    def start_batch(self, batch_id: str, batch_goal: str) -> None:
        """Start tracking a batch."""
        self._is_active = True
        self._current_stage = 0
        self._batch_start_time = time.time()
        self._stage_start_time = time.time()

        self.batch_label.configure(text=f"{batch_id}: {batch_goal[:40]}...")
        self._reset_stages()
        self._set_stage(0)

        self.pack(fill="x", pady=(0, 12))
        self._animate()
        self._update_times()

    def stop_batch(self) -> None:
        """Stop tracking the batch."""
        self._is_active = False
        self.pack_forget()

    def set_stage(self, stage_index: int) -> None:
        """Set the current stage (0-3)."""
        if 0 <= stage_index < len(self.STAGES):
            # Mark previous stages as complete
            for i in range(stage_index):
                indicator, label = self.stage_labels[i]
                indicator.configure(text="●", text_color=theme.colors.success)
                label.configure(text_color=theme.colors.text_secondary)

            self._current_stage = stage_index
            self._stage_start_time = time.time()
            self._set_stage(stage_index)

    def _set_stage(self, index: int) -> None:
        """Set a stage as active."""
        indicator, label = self.stage_labels[index]
        indicator.configure(text="◐", text_color=theme.colors.accent_primary)
        label.configure(text_color=theme.colors.text_primary)

        self.activity_label.configure(text=self.STAGES[index][1])

    def _reset_stages(self) -> None:
        """Reset all stage indicators."""
        for indicator, label in self.stage_labels:
            indicator.configure(text="○", text_color=theme.colors.text_muted)
            label.configure(text_color=theme.colors.text_muted)

    def update_activity(self, message: str, elapsed: float) -> None:
        """Update the activity message."""
        self.after(0, lambda: self.activity_label.configure(text=message))

    def _animate(self) -> None:
        """Animate the spinner."""
        if not self._is_active:
            return

        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_chars)
        self.spinner_label.configure(text=self._spinner_chars[self._spinner_index])

        self.after(100, self._animate)

    def _update_times(self) -> None:
        """Update time displays."""
        if not self._is_active:
            return

        # Batch elapsed time
        batch_elapsed = time.time() - self._batch_start_time
        mins = int(batch_elapsed // 60)
        secs = int(batch_elapsed % 60)
        self.batch_time_label.configure(text=f"{mins}:{secs:02d}")

        # Stage elapsed time
        stage_elapsed = time.time() - self._stage_start_time
        stage_mins = int(stage_elapsed // 60)
        stage_secs = int(stage_elapsed % 60)
        self.stage_time_label.configure(text=f"({stage_mins}:{stage_secs:02d})")

        self.after(1000, self._update_times)
