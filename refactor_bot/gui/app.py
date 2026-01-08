"""
Main application window for Refactorio GUI.
"""

import customtkinter as ctk
from typing import Optional

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, ConnectionStatus, app_state
from refactor_bot.gui.components.sidebar import Sidebar
from refactor_bot.gui.components.status_bar import StatusBar
from refactor_bot.gui.views.dashboard import DashboardView
from refactor_bot.gui.views.settings import SettingsView
from refactor_bot.gui.views.repo_select import RepoSelectView
from refactor_bot.gui.views.configuration import ConfigurationView
from refactor_bot.gui.views.plan_view import PlanView
from refactor_bot.gui.views.progress_view import ProgressView
from refactor_bot.gui.views.history_view import HistoryView


class RefactorBotApp(ctk.CTk):
    """
    Main application window for refactor-bot.
    """

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Refactorio")
        self.geometry("1400x900")
        self.minsize(1200, 700)

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Configure colors
        self.configure(fg_color=theme.colors.bg_dark)

        # Initialize views
        self._views: dict[AppView, ctk.CTkFrame] = {}
        self._current_view: Optional[ctk.CTkFrame] = None

        # Create layout
        self._create_layout()
        self._create_views()

        # Set initial view
        self._navigate(AppView.DASHBOARD)

        # Subscribe to state changes
        app_state.subscribe("connection_status", self._on_connection_status_change)
        app_state.subscribe("repo", self._on_repo_change)

    def _create_layout(self) -> None:
        """Create the main layout."""
        # Main container
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = Sidebar(
            self.main_container,
            on_navigate=self._navigate,
        )
        self.sidebar.pack(side="left", fill="y")

        # Content area
        self.content_area = ctk.CTkFrame(
            self.main_container,
            fg_color="transparent",
        )
        self.content_area.pack(side="left", fill="both", expand=True)

        # Status bar
        self.status_bar = StatusBar(self)
        self.status_bar.pack(side="bottom", fill="x")

    def _create_views(self) -> None:
        """Create all view instances."""
        # Dashboard
        self._views[AppView.DASHBOARD] = DashboardView(
            self.content_area,
            on_navigate=self._navigate,
        )

        # Settings
        self._views[AppView.SETTINGS] = SettingsView(
            self.content_area,
            on_navigate=self._navigate,
        )

        # Repository selection
        self._views[AppView.SELECT_REPO] = RepoSelectView(
            self.content_area,
            on_navigate=self._navigate,
        )

        # Configuration
        self._views[AppView.CONFIGURATION] = ConfigurationView(
            self.content_area,
            on_navigate=self._navigate,
        )

        # Plan
        self._views[AppView.PLAN] = PlanView(
            self.content_area,
            on_navigate=self._navigate,
        )

        # Progress
        self._views[AppView.PROGRESS] = ProgressView(
            self.content_area,
            on_navigate=self._navigate,
        )

        # History
        self._views[AppView.HISTORY] = HistoryView(
            self.content_area,
            on_navigate=self._navigate,
        )

    def _navigate(self, view: AppView) -> None:
        """Navigate to a view."""
        # Hide current view
        if self._current_view:
            self._current_view.pack_forget()

        # Show new view
        new_view = self._views.get(view)
        if new_view:
            new_view.pack(fill="both", expand=True)
            self._current_view = new_view

            # Update sidebar
            self.sidebar.set_active_view(view)

            # Update state
            app_state.current_view = view

            # View-specific initialization
            self._on_view_shown(view)

    def _on_view_shown(self, view: AppView) -> None:
        """Handle view-specific initialization when shown."""
        if view == AppView.CONFIGURATION:
            config_view = self._views[AppView.CONFIGURATION]
            config_view.load_config()

        elif view == AppView.PLAN:
            plan_view = self._views[AppView.PLAN]
            # Generate plan if we have a repo but no plan
            if app_state.repo.path and not app_state.plan:
                plan_view.generate_plan()

        elif view == AppView.PROGRESS:
            progress_view = self._views[AppView.PROGRESS]
            progress_view.show_start_screen()

        elif view == AppView.HISTORY:
            history_view = self._views[AppView.HISTORY]
            history_view.load_history()

    def _on_connection_status_change(self, status: ConnectionStatus) -> None:
        """Handle connection status changes."""
        self.sidebar.set_connection_status(status)

        # Update dashboard
        dashboard = self._views.get(AppView.DASHBOARD)
        if dashboard:
            dashboard.update_connection_status(status)

        # Update status bar
        status_messages = {
            ConnectionStatus.CONNECTED: ("Claude Code connected", "success"),
            ConnectionStatus.NOT_FOUND: ("Claude Code not found", "error"),
            ConnectionStatus.NOT_AUTHENTICATED: ("Claude Code not authenticated", "warning"),
            ConnectionStatus.CHECKING: ("Checking Claude Code...", "info"),
            ConnectionStatus.ERROR: ("Claude Code error", "error"),
        }

        msg, msg_type = status_messages.get(status, ("Unknown status", "info"))
        self.status_bar.set_status(msg, msg_type)

    def _on_repo_change(self, repo) -> None:
        """Handle repository changes."""
        if repo.path:
            self.status_bar.set_repo(repo.name)
        else:
            self.status_bar.set_repo(None)


def run_gui():
    """Run the GUI application."""
    app = RefactorBotApp()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
