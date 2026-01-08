"""
Application state management for refactor-bot GUI.

Provides a centralized state store with observer pattern for UI updates.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from refactor_bot.config import Config, REFACTOR_BOT_HOME


class AppView(str, Enum):
    """Available application views."""

    DASHBOARD = "dashboard"
    SETTINGS = "settings"
    SELECT_REPO = "select_repo"
    CONFIGURATION = "configuration"
    PLAN = "plan"
    PROGRESS = "progress"
    HISTORY = "history"


class ConnectionStatus(str, Enum):
    """Claude connection status."""

    UNKNOWN = "unknown"
    CHECKING = "checking"
    CONNECTED = "connected"
    NOT_FOUND = "not_found"
    NOT_AUTHENTICATED = "not_authenticated"
    ERROR = "error"


@dataclass
class ClaudeSettings:
    """Claude Code CLI settings."""

    binary_path: str = ""
    auto_detected_path: str = ""
    is_authenticated: bool = False
    version: str = ""


@dataclass
class RepoState:
    """State for currently selected repository."""

    path: Optional[Path] = None
    name: str = ""
    is_git: bool = False
    branch: str = ""
    file_count: int = 0
    config: Optional[Config] = None


@dataclass
class RefactorState:
    """State for an active refactoring run."""

    run_id: str = ""
    is_running: bool = False
    current_batch: int = 0
    total_batches: int = 0
    current_goal: str = ""
    completed_batches: list = field(default_factory=list)
    failed_batches: list = field(default_factory=list)
    logs: list = field(default_factory=list)


class AppState:
    """
    Centralized application state with observer pattern.

    Usage:
        state = AppState()
        state.subscribe("current_view", callback)
        state.current_view = AppView.SETTINGS  # triggers callback
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._observers: dict[str, list[Callable]] = {}

        # View state
        self._current_view: AppView = AppView.DASHBOARD

        # Connection state
        self._connection_status: ConnectionStatus = ConnectionStatus.UNKNOWN
        self._claude_settings: ClaudeSettings = ClaudeSettings()

        # Repository state
        self._repo: RepoState = RepoState()

        # Refactoring state
        self._refactor: RefactorState = RefactorState()

        # Plan state
        self._plan: Optional[Any] = None  # RefactorPlan

        # Load saved settings
        self._load_settings()

    def _notify(self, key: str, value: Any) -> None:
        """Notify observers of a state change."""
        if key in self._observers:
            for callback in self._observers[key]:
                try:
                    callback(value)
                except Exception as e:
                    print(f"Observer error for {key}: {e}")

    def subscribe(self, key: str, callback: Callable) -> Callable:
        """
        Subscribe to state changes.

        Returns an unsubscribe function.
        """
        with self._lock:
            if key not in self._observers:
                self._observers[key] = []
            self._observers[key].append(callback)

        def unsubscribe():
            with self._lock:
                if key in self._observers and callback in self._observers[key]:
                    self._observers[key].remove(callback)

        return unsubscribe

    # Current view
    @property
    def current_view(self) -> AppView:
        return self._current_view

    @current_view.setter
    def current_view(self, value: AppView) -> None:
        self._current_view = value
        self._notify("current_view", value)

    # Connection status
    @property
    def connection_status(self) -> ConnectionStatus:
        return self._connection_status

    @connection_status.setter
    def connection_status(self, value: ConnectionStatus) -> None:
        self._connection_status = value
        self._notify("connection_status", value)

    # Claude settings
    @property
    def claude_settings(self) -> ClaudeSettings:
        return self._claude_settings

    @claude_settings.setter
    def claude_settings(self, value: ClaudeSettings) -> None:
        self._claude_settings = value
        self._save_settings()
        self._notify("claude_settings", value)

    # Repository state
    @property
    def repo(self) -> RepoState:
        return self._repo

    @repo.setter
    def repo(self, value: RepoState) -> None:
        self._repo = value
        self._notify("repo", value)

    # Refactor state
    @property
    def refactor(self) -> RefactorState:
        return self._refactor

    @refactor.setter
    def refactor(self, value: RefactorState) -> None:
        self._refactor = value
        self._notify("refactor", value)

    def update_refactor(self, **kwargs) -> None:
        """Update specific fields of refactor state."""
        for key, value in kwargs.items():
            if hasattr(self._refactor, key):
                setattr(self._refactor, key, value)
        self._notify("refactor", self._refactor)

    # Plan
    @property
    def plan(self) -> Optional[Any]:
        return self._plan

    @plan.setter
    def plan(self, value: Any) -> None:
        self._plan = value
        self._notify("plan", value)

    # Settings persistence
    def _settings_path(self) -> Path:
        return REFACTOR_BOT_HOME / "gui_settings.json"

    def _load_settings(self) -> None:
        """Load settings from disk."""
        path = self._settings_path()
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)

                self._claude_settings = ClaudeSettings(
                    binary_path=data.get("claude_binary_path", ""),
                    auto_detected_path=data.get("claude_auto_detected_path", ""),
                )
            except Exception:
                pass

    def _save_settings(self) -> None:
        """Save settings to disk."""
        path = self._settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w") as f:
                json.dump({
                    "claude_binary_path": self._claude_settings.binary_path,
                    "claude_auto_detected_path": self._claude_settings.auto_detected_path,
                }, f, indent=2)
        except Exception:
            pass

    def get_claude_binary(self) -> str:
        """Get the Claude binary path to use."""
        if self._claude_settings.binary_path:
            return self._claude_settings.binary_path
        if self._claude_settings.auto_detected_path:
            return self._claude_settings.auto_detected_path
        return "claude"


# Singleton instance
app_state = AppState()
