"""
Dashboard view - main landing page with quick actions.
"""

import customtkinter as ctk
from typing import Callable, Optional

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, ConnectionStatus, app_state


class QuickActionCard(ctk.CTkFrame):
    """A card for quick actions on the dashboard."""

    def __init__(
        self,
        master,
        title: str,
        description: str,
        icon: str,
        action: Optional[Callable] = None,
        enabled: bool = True,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
            **kwargs
        )

        self.action = action
        self._enabled = enabled

        self._create_widgets(title, description, icon)
        self._bind_events()

    def _create_widgets(self, title: str, description: str, icon: str) -> None:
        """Create card widgets."""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        # Icon
        icon_label = ctk.CTkLabel(
            content,
            text=icon,
            font=(theme.fonts.family, 32),
        )
        icon_label.pack(anchor="w")

        # Title
        title_label = ctk.CTkLabel(
            content,
            text=title,
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        title_label.pack(anchor="w", pady=(12, 4))

        # Description
        desc_label = ctk.CTkLabel(
            content,
            text=description,
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            wraplength=200,
            justify="left",
        )
        desc_label.pack(anchor="w")

    def _bind_events(self) -> None:
        """Bind mouse events."""
        if self._enabled:
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
            self.bind("<Button-1>", self._on_click)

            for child in self.winfo_children():
                child.bind("<Button-1>", self._on_click)

    def _on_enter(self, event) -> None:
        self.configure(fg_color=theme.colors.bg_light)

    def _on_leave(self, event) -> None:
        self.configure(fg_color=theme.colors.bg_medium)

    def _on_click(self, event) -> None:
        if self.action and self._enabled:
            self.action()


class DashboardView(ctk.CTkFrame):
    """
    Dashboard view with quick actions and status overview.
    """

    def __init__(self, master, on_navigate: Callable[[AppView], None], **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create dashboard widgets."""
        # Scrollable container
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=24)

        # Header
        header = ctk.CTkFrame(scroll, fg_color="transparent")
        header.pack(fill="x", pady=(0, 24))

        title = ctk.CTkLabel(
            header,
            text="Dashboard",
            font=(theme.fonts.family, theme.fonts.size_title, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Welcome to Refactorio. Select a repository to get started.",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        # Connection status banner
        self.status_banner = ctk.CTkFrame(
            scroll,
            fg_color=theme.colors.warning_bg,
            corner_radius=theme.dimensions.card_radius,
        )
        self.status_banner.pack(fill="x", pady=(0, 24))

        banner_content = ctk.CTkFrame(self.status_banner, fg_color="transparent")
        banner_content.pack(fill="x", padx=16, pady=12)

        self.status_icon = ctk.CTkLabel(
            banner_content,
            text="⚠️",
            font=(theme.fonts.family, theme.fonts.size_lg),
        )
        self.status_icon.pack(side="left")

        self.status_text = ctk.CTkLabel(
            banner_content,
            text="Claude Code not configured. Click Settings to set up.",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.warning,
        )
        self.status_text.pack(side="left", padx=(8, 0))

        settings_btn = ctk.CTkButton(
            banner_content,
            text="Settings",
            width=80,
            height=28,
            font=(theme.fonts.family, theme.fonts.size_sm),
            fg_color=theme.colors.warning,
            hover_color="#b8860b",
            text_color=theme.colors.bg_darkest,
            command=lambda: self.on_navigate(AppView.SETTINGS),
        )
        settings_btn.pack(side="right")

        # Quick actions section
        actions_label = ctk.CTkLabel(
            scroll,
            text="Quick Actions",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        actions_label.pack(anchor="w", pady=(0, 12))

        actions_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 24))

        # Action cards
        cards_data = [
            ("Select Repository", "Choose a codebase to refactor", "📁", AppView.SELECT_REPO),
            ("View Plan", "Review the refactoring plan", "📋", AppView.PLAN),
            ("Run Refactor", "Start automated refactoring", "▶️", AppView.PROGRESS),
            ("History", "View past refactoring runs", "📜", AppView.HISTORY),
        ]

        for i, (title, desc, icon, view) in enumerate(cards_data):
            card = QuickActionCard(
                actions_frame,
                title=title,
                description=desc,
                icon=icon,
                action=lambda v=view: self.on_navigate(v),
            )
            card.grid(row=0, column=i, padx=(0, 16) if i < 3 else 0, sticky="nsew")

        for i in range(4):
            actions_frame.columnconfigure(i, weight=1)

    def update_connection_status(self, status: ConnectionStatus) -> None:
        """Update the connection status banner."""
        if status == ConnectionStatus.CONNECTED:
            self.status_banner.configure(fg_color=theme.colors.success_bg)
            self.status_icon.configure(text="✓")
            self.status_text.configure(
                text="Claude Code connected and ready",
                text_color=theme.colors.success,
            )
        elif status == ConnectionStatus.NOT_FOUND:
            self.status_banner.configure(fg_color=theme.colors.error_bg)
            self.status_icon.configure(text="✗")
            self.status_text.configure(
                text="Claude Code not found. Configure the path in Settings.",
                text_color=theme.colors.error,
            )
        elif status == ConnectionStatus.NOT_AUTHENTICATED:
            self.status_banner.configure(fg_color=theme.colors.warning_bg)
            self.status_icon.configure(text="⚠️")
            self.status_text.configure(
                text="Claude Code not authenticated. Please log in.",
                text_color=theme.colors.warning,
            )
        else:
            self.status_banner.configure(fg_color=theme.colors.warning_bg)
            self.status_icon.configure(text="⚠️")
            self.status_text.configure(
                text="Claude Code status unknown. Check Settings.",
                text_color=theme.colors.warning,
            )
