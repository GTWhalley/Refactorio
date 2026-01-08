"""
Risk badge component for visualizing risk levels.
"""

import customtkinter as ctk

from refactor_bot.gui.theme import theme


class RiskBadge(ctk.CTkFrame):
    """
    Visual badge showing risk level with color coding.
    """

    def __init__(self, master, risk_score: int = 0, **kwargs):
        super().__init__(
            master,
            corner_radius=12,
            height=24,
            **kwargs
        )
        self.pack_propagate(False)

        self._risk_score = risk_score
        self._create_widgets()
        self._update_appearance()

    def _create_widgets(self) -> None:
        """Create badge widgets."""
        self.label = ctk.CTkLabel(
            self,
            text="",
            font=(theme.fonts.family, theme.fonts.size_xs, "bold"),
            height=24,
        )
        self.label.pack(padx=10)

    def _update_appearance(self) -> None:
        """Update appearance based on risk score."""
        if self._risk_score <= 30:
            bg_color = theme.colors.success_bg
            text_color = theme.colors.success
            text = f"Low ({self._risk_score})"
        elif self._risk_score <= 60:
            bg_color = theme.colors.warning_bg
            text_color = theme.colors.warning
            text = f"Medium ({self._risk_score})"
        else:
            bg_color = theme.colors.error_bg
            text_color = theme.colors.error
            text = f"High ({self._risk_score})"

        self.configure(fg_color=bg_color)
        self.label.configure(text=text, text_color=text_color)

    def set_risk(self, score: int) -> None:
        """Set the risk score."""
        self._risk_score = max(0, min(100, score))
        self._update_appearance()


class RiskHeatmap(ctk.CTkFrame):
    """
    Visual heatmap showing risk distribution across batches.
    """

    def __init__(
        self,
        master,
        cell_size: int = 16,
        cells_per_row: int = 20,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=theme.dimensions.border_radius,
            **kwargs
        )

        self.cell_size = cell_size
        self.cells_per_row = cells_per_row
        self.cells: list[ctk.CTkFrame] = []

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create heatmap widgets."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 4))

        title = ctk.CTkLabel(
            header,
            text="Risk Heatmap",
            font=(theme.fonts.family, theme.fonts.size_sm, "bold"),
            text_color=theme.colors.text_secondary,
        )
        title.pack(side="left")

        # Legend
        legend = ctk.CTkFrame(header, fg_color="transparent")
        legend.pack(side="right")

        for label, color in [
            ("Low", theme.colors.success),
            ("Medium", theme.colors.warning),
            ("High", theme.colors.error),
        ]:
            dot = ctk.CTkLabel(
                legend,
                text="●",
                font=(theme.fonts.family, 10),
                text_color=color,
            )
            dot.pack(side="left", padx=(8, 2))

            lbl = ctk.CTkLabel(
                legend,
                text=label,
                font=(theme.fonts.family, theme.fonts.size_xs),
                text_color=theme.colors.text_muted,
            )
            lbl.pack(side="left")

        # Grid container
        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="x", padx=12, pady=(4, 12))

    def set_data(self, risk_scores: list[int]) -> None:
        """Set the risk scores to display."""
        # Clear existing
        for cell in self.cells:
            cell.destroy()
        self.cells.clear()

        # Create cells
        for i, score in enumerate(risk_scores):
            row = i // self.cells_per_row
            col = i % self.cells_per_row

            # Determine color
            if score <= 30:
                color = theme.colors.success
            elif score <= 60:
                color = theme.colors.warning
            else:
                color = theme.colors.error

            cell = ctk.CTkFrame(
                self.grid_frame,
                width=self.cell_size,
                height=self.cell_size,
                fg_color=color,
                corner_radius=2,
            )
            cell.grid(row=row, column=col, padx=1, pady=1)
            self.cells.append(cell)

    def clear(self) -> None:
        """Clear the heatmap."""
        for cell in self.cells:
            cell.destroy()
        self.cells.clear()
