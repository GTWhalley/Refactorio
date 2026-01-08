"""
Batch list component for displaying and editing refactoring batches.
"""

import customtkinter as ctk
from typing import Callable, Optional, Any

from refactor_bot.gui.theme import theme
from refactor_bot.gui.components.risk_badge import RiskBadge


class BatchItem(ctk.CTkFrame):
    """A single batch item in the list."""

    def __init__(
        self,
        master,
        batch: Any,  # Batch object
        index: int,
        on_select: Optional[Callable] = None,
        on_toggle: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.border_radius,
            **kwargs
        )

        self.batch = batch
        self.index = index
        self.on_select = on_select
        self.on_toggle = on_toggle
        self._is_selected = False
        self._is_enabled = True

        self._create_widgets()
        self._bind_events()

    def _create_widgets(self) -> None:
        """Create batch item widgets."""
        # Main content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=12, pady=10)

        # Left section
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        # Checkbox for enabling/disabling
        self.checkbox = ctk.CTkCheckBox(
            left,
            text="",
            width=24,
            checkbox_width=18,
            checkbox_height=18,
            fg_color=theme.colors.accent_primary,
            hover_color=theme.colors.accent_primary_hover,
            border_color=theme.colors.border,
            command=self._on_checkbox_toggle,
        )
        self.checkbox.select()
        self.checkbox.pack(side="left", padx=(0, 8))

        # Batch info
        info_frame = ctk.CTkFrame(left, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        # Header row with ID and goal
        header = ctk.CTkFrame(info_frame, fg_color="transparent")
        header.pack(fill="x")

        self.id_label = ctk.CTkLabel(
            header,
            text=self.batch.id,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        self.id_label.pack(side="left")

        self.goal_label = ctk.CTkLabel(
            header,
            text=self.batch.goal,
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_primary,
            anchor="w",
        )
        self.goal_label.pack(side="left", padx=(12, 0), fill="x", expand=True)

        # Details row
        details = ctk.CTkFrame(info_frame, fg_color="transparent")
        details.pack(fill="x", pady=(4, 0))

        # Scope
        scope_text = ", ".join(self.batch.scope_globs[:2])
        if len(self.batch.scope_globs) > 2:
            scope_text += f" +{len(self.batch.scope_globs) - 2} more"

        self.scope_label = ctk.CTkLabel(
            details,
            text=f"📁 {scope_text}",
            font=(theme.fonts.family, theme.fonts.size_xs),
            text_color=theme.colors.text_muted,
        )
        self.scope_label.pack(side="left")

        # LOC budget
        self.loc_label = ctk.CTkLabel(
            details,
            text=f"📝 {self.batch.diff_budget_loc} LOC",
            font=(theme.fonts.family, theme.fonts.size_xs),
            text_color=theme.colors.text_muted,
        )
        self.loc_label.pack(side="left", padx=(16, 0))

        # Right section - risk and status
        right = ctk.CTkFrame(content, fg_color="transparent")
        right.pack(side="right")

        # Risk badge
        self.risk_badge = RiskBadge(right, self.batch.risk_score)
        self.risk_badge.pack(side="right")

        # Status indicator (for completed/failed batches)
        self.status_label = ctk.CTkLabel(
            right,
            text="",
            font=(theme.fonts.family, theme.fonts.size_sm),
            width=80,
        )
        self.status_label.pack(side="right", padx=(0, 12))
        self._update_status()

    def _bind_events(self) -> None:
        """Bind mouse events."""
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, event) -> None:
        """Handle mouse enter."""
        if not self._is_selected:
            self.configure(fg_color=theme.colors.bg_light)

    def _on_leave(self, event) -> None:
        """Handle mouse leave."""
        if not self._is_selected:
            self.configure(fg_color=theme.colors.bg_medium)

    def _on_click(self, event) -> None:
        """Handle click."""
        if self.on_select:
            self.on_select(self)

    def _on_checkbox_toggle(self) -> None:
        """Handle checkbox toggle."""
        self._is_enabled = self.checkbox.get() == 1
        if self.on_toggle:
            self.on_toggle(self, self._is_enabled)

    def _update_status(self) -> None:
        """Update status indicator."""
        status = getattr(self.batch, "status", "pending")
        status_config = {
            "pending": ("", theme.colors.text_muted),
            "in_progress": ("Running...", theme.colors.accent_secondary),
            "completed": ("✓ Done", theme.colors.success),
            "failed": ("✗ Failed", theme.colors.error),
            "skipped": ("○ Skipped", theme.colors.warning),
            "noop": ("○ No-op", theme.colors.text_muted),
        }
        text, color = status_config.get(status, ("", theme.colors.text_muted))
        self.status_label.configure(text=text, text_color=color)

    def set_selected(self, selected: bool) -> None:
        """Set selection state."""
        self._is_selected = selected
        if selected:
            self.configure(fg_color=theme.colors.accent_secondary)
        else:
            self.configure(fg_color=theme.colors.bg_medium)

    def set_enabled(self, enabled: bool) -> None:
        """Set enabled state."""
        self._is_enabled = enabled
        if enabled:
            self.checkbox.select()
        else:
            self.checkbox.deselect()

    def update_batch(self, batch: Any) -> None:
        """Update with new batch data."""
        self.batch = batch
        self.goal_label.configure(text=batch.goal)
        self.risk_badge.set_risk(batch.risk_score)
        self._update_status()


class BatchList(ctk.CTkScrollableFrame):
    """
    Scrollable list of refactoring batches.
    """

    def __init__(
        self,
        master,
        on_select: Optional[Callable[[Any], None]] = None,
        on_reorder: Optional[Callable[[list], None]] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=theme.dimensions.border_radius,
            **kwargs
        )

        self.on_select = on_select
        self.on_reorder = on_reorder
        self.items: list[BatchItem] = []
        self._selected_item: Optional[BatchItem] = None
        self._batches: list = []

    def set_batches(self, batches: list) -> None:
        """Set the list of batches to display."""
        self._batches = batches
        self.clear()

        for i, batch in enumerate(batches):
            item = BatchItem(
                self,
                batch=batch,
                index=i,
                on_select=self._on_item_select,
                on_toggle=self._on_item_toggle,
            )
            item.pack(fill="x", pady=(0, 8))
            self.items.append(item)

    def _on_item_select(self, item: BatchItem) -> None:
        """Handle item selection."""
        # Deselect previous
        if self._selected_item:
            self._selected_item.set_selected(False)

        # Select new
        item.set_selected(True)
        self._selected_item = item

        if self.on_select:
            self.on_select(item.batch)

    def _on_item_toggle(self, item: BatchItem, enabled: bool) -> None:
        """Handle item enable/disable."""
        # Could notify parent of change
        pass

    def get_enabled_batches(self) -> list:
        """Get list of enabled batches."""
        return [
            item.batch for item in self.items
            if item._is_enabled
        ]

    def update_batch(self, batch_id: str, **kwargs) -> None:
        """Update a specific batch."""
        for item in self.items:
            if item.batch.id == batch_id:
                for key, value in kwargs.items():
                    if hasattr(item.batch, key):
                        setattr(item.batch, key, value)
                item.update_batch(item.batch)
                break

    def clear(self) -> None:
        """Clear all items."""
        for item in self.items:
            item.destroy()
        self.items.clear()
        self._selected_item = None
