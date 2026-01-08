"""
GUI views for refactor-bot.
"""

from refactor_bot.gui.views.dashboard import DashboardView
from refactor_bot.gui.views.settings import SettingsView
from refactor_bot.gui.views.repo_select import RepoSelectView
from refactor_bot.gui.views.configuration import ConfigurationView
from refactor_bot.gui.views.plan_view import PlanView
from refactor_bot.gui.views.progress_view import ProgressView
from refactor_bot.gui.views.history_view import HistoryView

__all__ = [
    "DashboardView",
    "SettingsView",
    "RepoSelectView",
    "ConfigurationView",
    "PlanView",
    "ProgressView",
    "HistoryView",
]
