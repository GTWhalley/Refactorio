"""
Sidebar navigation component.
"""

import customtkinter as ctk
from typing import Callable, Optional

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, ConnectionStatus


class SidebarButton(ctk.CTkButton):
    """A navigation button for the sidebar."""

    def __init__(
        self,
        master,
        text: str,
        icon: str = "",
        view: Optional[AppView] = None,
        command: Optional[Callable] = None,
        **kwargs
    ):
        self.view = view
        self._is_active = False

        display_text = f"  {icon}  {text}" if icon else f"  {text}"

        super().__init__(
            master,
            text=display_text,
            anchor="w",
            height=40,
            corner_radius=theme.dimensions.border_radius,
            fg_color="transparent",
            hover_color=theme.colors.bg_light,
            text_color=theme.colors.text_secondary,
            font=(theme.fonts.family, theme.fonts.size_md),
            command=command,
            **kwargs
        )

    def set_active(self, active: bool) -> None:
        """Set the active state of the button."""
        self._is_active = active
        if active:
            self.configure(
                fg_color=theme.colors.bg_light,
                text_color=theme.colors.text_primary,
            )
        else:
            self.configure(
                fg_color="transparent",
                text_color=theme.colors.text_secondary,
            )


class StatusIndicator(ctk.CTkFrame):
    """Connection status indicator."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.status_dot = ctk.CTkLabel(
            self,
            text="●",
            font=(theme.fonts.family, 12),
            text_color=theme.colors.text_muted,
            width=20,
        )
        self.status_dot.pack(side="left")

        self.status_label = ctk.CTkLabel(
            self,
            text="Not Connected",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        self.status_label.pack(side="left", padx=(4, 0))

    def set_status(self, status: ConnectionStatus) -> None:
        """Update the status indicator."""
        status_config = {
            ConnectionStatus.UNKNOWN: ("●", theme.colors.text_muted, "Unknown"),
            ConnectionStatus.CHECKING: ("●", theme.colors.warning, "Checking..."),
            ConnectionStatus.CONNECTED: ("●", theme.colors.success, "Connected"),
            ConnectionStatus.NOT_FOUND: ("●", theme.colors.error, "Not Found"),
            ConnectionStatus.NOT_AUTHENTICATED: ("●", theme.colors.warning, "Not Logged In"),
            ConnectionStatus.ERROR: ("●", theme.colors.error, "Error"),
        }

        icon, color, text = status_config.get(
            status,
            ("●", theme.colors.text_muted, "Unknown")
        )

        self.status_dot.configure(text=icon, text_color=color)
        self.status_label.configure(text=text, text_color=color)


class Sidebar(ctk.CTkFrame):
    """
    Main sidebar navigation component.
    """

    def __init__(self, master, on_navigate: Callable[[AppView], None], **kwargs):
        super().__init__(
            master,
            width=theme.dimensions.sidebar_width,
            fg_color=theme.colors.bg_darkest,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self.buttons: dict[AppView, SidebarButton] = {}

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create sidebar widgets."""
        # Logo / Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=16, pady=(20, 8))

        title = ctk.CTkLabel(
            title_frame,
            text="REFACTORIO",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(anchor="w")

        version = ctk.CTkLabel(
            title_frame,
            text="v0.1.0",
            font=(theme.fonts.family, theme.fonts.size_xs),
            text_color=theme.colors.text_muted,
        )
        version.pack(anchor="w")

        # Separator
        sep = ctk.CTkFrame(self, height=1, fg_color=theme.colors.border)
        sep.pack(fill="x", padx=16, pady=16)

        # Navigation buttons
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=8)

        nav_items = [
            ("Dashboard", "🏠", AppView.DASHBOARD),
            ("Select Repo", "📁", AppView.SELECT_REPO),
            ("Configuration", "⚙️", AppView.CONFIGURATION),
            ("Plan", "📋", AppView.PLAN),
            ("Progress", "▶️", AppView.PROGRESS),
            ("History", "📜", AppView.HISTORY),
        ]

        for text, icon, view in nav_items:
            btn = SidebarButton(
                nav_frame,
                text=text,
                icon=icon,
                view=view,
                command=lambda v=view: self._on_button_click(v),
            )
            btn.pack(fill="x", pady=2)
            self.buttons[view] = btn

        # Spacer
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Bottom section
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=8, pady=(0, 8))

        # Settings button
        settings_btn = SidebarButton(
            bottom_frame,
            text="Settings",
            icon="⚡",
            view=AppView.SETTINGS,
            command=lambda: self._on_button_click(AppView.SETTINGS),
        )
        settings_btn.pack(fill="x", pady=2)
        self.buttons[AppView.SETTINGS] = settings_btn

        # Status indicator
        self.status_indicator = StatusIndicator(bottom_frame)
        self.status_indicator.pack(fill="x", padx=8, pady=(16, 8))

    def _on_button_click(self, view: AppView) -> None:
        """Handle navigation button click."""
        self.set_active_view(view)
        self.on_navigate(view)

    def set_active_view(self, view: AppView) -> None:
        """Set the active navigation item."""
        for btn_view, button in self.buttons.items():
            button.set_active(btn_view == view)

    def set_connection_status(self, status: ConnectionStatus) -> None:
        """Update the connection status indicator."""
        self.status_indicator.set_status(status)
