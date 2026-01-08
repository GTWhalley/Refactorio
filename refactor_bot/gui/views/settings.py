"""
Settings view with Claude Code configuration and login.
"""

import customtkinter as ctk
import subprocess
import threading
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, ConnectionStatus, ClaudeSettings, app_state


class SettingsView(ctk.CTkFrame):
    """
    Settings view for configuring Claude Code path and authentication.
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
        self._load_current_settings()
        self._auto_detect_claude()

    def _create_widgets(self) -> None:
        """Create settings widgets."""
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
            text="Settings",
            font=(theme.fonts.family, theme.fonts.size_title, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Configure Claude Code CLI and application settings",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        # Claude Code section
        claude_section = ctk.CTkFrame(
            scroll,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )
        claude_section.pack(fill="x", pady=(0, 16))

        claude_content = ctk.CTkFrame(claude_section, fg_color="transparent")
        claude_content.pack(fill="x", padx=20, pady=20)

        # Section title
        section_title = ctk.CTkLabel(
            claude_content,
            text="Claude Code CLI",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        section_title.pack(anchor="w")

        section_desc = ctk.CTkLabel(
            claude_content,
            text="Configure the path to your Claude Code CLI installation",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        section_desc.pack(anchor="w", pady=(4, 16))

        # Status indicator
        status_frame = ctk.CTkFrame(claude_content, fg_color=theme.colors.bg_dark, corner_radius=8)
        status_frame.pack(fill="x", pady=(0, 16))

        status_inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_inner.pack(fill="x", padx=16, pady=12)

        self.status_dot = ctk.CTkLabel(
            status_inner,
            text="●",
            font=(theme.fonts.family, 16),
            text_color=theme.colors.text_muted,
        )
        self.status_dot.pack(side="left")

        self.status_label = ctk.CTkLabel(
            status_inner,
            text="Checking...",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
        )
        self.status_label.pack(side="left", padx=(8, 0))

        self.version_label = ctk.CTkLabel(
            status_inner,
            text="",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        self.version_label.pack(side="right")

        # Binary path input
        path_label = ctk.CTkLabel(
            claude_content,
            text="Claude Binary Path",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        path_label.pack(anchor="w", pady=(0, 4))

        path_frame = ctk.CTkFrame(claude_content, fg_color="transparent")
        path_frame.pack(fill="x", pady=(0, 8))

        self.path_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="Path to claude binary (leave empty for auto-detect)",
            height=40,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            **theme.get_input_style(),
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_btn = ctk.CTkButton(
            path_frame,
            text="Browse",
            width=80,
            height=40,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_button_style("outline"),
            command=self._browse_for_binary,
        )
        browse_btn.pack(side="right")

        # Auto-detected path info
        self.auto_detect_label = ctk.CTkLabel(
            claude_content,
            text="",
            font=(theme.fonts.family, theme.fonts.size_xs),
            text_color=theme.colors.text_muted,
            wraplength=600,
            justify="left",
        )
        self.auto_detect_label.pack(anchor="w", pady=(0, 16))

        # Action buttons
        btn_frame = ctk.CTkFrame(claude_content, fg_color="transparent")
        btn_frame.pack(fill="x")

        self.login_btn = ctk.CTkButton(
            btn_frame,
            text="Login to Claude",
            width=140,
            height=40,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("primary"),
            command=self._launch_claude_login,
        )
        self.login_btn.pack(side="left", padx=(0, 8))

        self.test_btn = ctk.CTkButton(
            btn_frame,
            text="Test Connection",
            width=140,
            height=40,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("secondary"),
            command=self._test_connection,
        )
        self.test_btn.pack(side="left", padx=(0, 8))

        self.save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            width=140,
            height=40,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("outline"),
            command=self._save_settings,
        )
        self.save_btn.pack(side="left")

        # Help section
        help_section = ctk.CTkFrame(
            scroll,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )
        help_section.pack(fill="x", pady=(0, 16))

        help_content = ctk.CTkFrame(help_section, fg_color="transparent")
        help_content.pack(fill="x", padx=20, pady=20)

        help_title = ctk.CTkLabel(
            help_content,
            text="Need Help?",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        help_title.pack(anchor="w")

        help_text = ctk.CTkLabel(
            help_content,
            text=(
                "Claude Code CLI is typically installed via npm:\n"
                "  npm install -g @anthropic-ai/claude-code\n\n"
                "Or it may be bundled with the Claude desktop app at:\n"
                "  ~/Library/Application Support/Claude/claude-code/<version>/claude\n\n"
                "After installation, run 'claude' in terminal and use /login to authenticate."
            ),
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            justify="left",
        )
        help_text.pack(anchor="w", pady=(8, 0))

        # Common paths section
        paths_section = ctk.CTkFrame(
            scroll,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )
        paths_section.pack(fill="x")

        paths_content = ctk.CTkFrame(paths_section, fg_color="transparent")
        paths_content.pack(fill="x", padx=20, pady=20)

        paths_title = ctk.CTkLabel(
            paths_content,
            text="Common Installation Paths",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        paths_title.pack(anchor="w")

        self.common_paths_frame = ctk.CTkFrame(paths_content, fg_color="transparent")
        self.common_paths_frame.pack(fill="x", pady=(12, 0))

    def _auto_detect_claude(self) -> None:
        """Auto-detect Claude installation."""
        def detect():
            common_paths = [
                # npm global
                Path.home() / ".npm-global" / "bin" / "claude",
                Path("/usr/local/bin/claude"),
                Path("/opt/homebrew/bin/claude"),
                # Claude desktop app bundled
            ]

            # Check for Claude desktop app bundled version
            claude_support = Path.home() / "Library" / "Application Support" / "Claude" / "claude-code"
            if claude_support.exists():
                for version_dir in sorted(claude_support.iterdir(), reverse=True):
                    if version_dir.is_dir():
                        claude_bin = version_dir / "claude"
                        if claude_bin.exists():
                            common_paths.insert(0, claude_bin)
                            break

            detected_path = None
            for path in common_paths:
                if path.exists():
                    detected_path = str(path)
                    break

            # Update UI on main thread
            self.after(0, lambda: self._update_auto_detect(detected_path, common_paths))

        threading.Thread(target=detect, daemon=True).start()

    def _update_auto_detect(self, detected: Optional[str], paths: list) -> None:
        """Update UI with auto-detect results."""
        if detected:
            app_state.claude_settings = ClaudeSettings(
                auto_detected_path=detected,
                binary_path=app_state.claude_settings.binary_path,
            )
            self.auto_detect_label.configure(
                text=f"Auto-detected: {detected}",
                text_color=theme.colors.success,
            )
        else:
            self.auto_detect_label.configure(
                text="Could not auto-detect Claude. Please specify the path manually.",
                text_color=theme.colors.warning,
            )

        # Show common paths as clickable options
        for widget in self.common_paths_frame.winfo_children():
            widget.destroy()

        for path in paths[:5]:
            exists = path.exists()
            btn = ctk.CTkButton(
                self.common_paths_frame,
                text=f"{'✓' if exists else '✗'} {path}",
                anchor="w",
                height=32,
                font=(theme.fonts.family_mono, theme.fonts.size_xs),
                fg_color="transparent",
                hover_color=theme.colors.bg_light if exists else "transparent",
                text_color=theme.colors.text_secondary if exists else theme.colors.text_muted,
                command=lambda p=str(path): self._use_path(p) if Path(p).exists() else None,
            )
            btn.pack(fill="x", pady=2)

        # Test connection with detected/saved path
        self._test_connection()

    def _use_path(self, path: str) -> None:
        """Use a specific path."""
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, path)
        self._test_connection()

    def _load_current_settings(self) -> None:
        """Load current settings into the form."""
        settings = app_state.claude_settings
        if settings.binary_path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, settings.binary_path)

    def _browse_for_binary(self) -> None:
        """Open file browser to select Claude binary."""
        filename = filedialog.askopenfilename(
            title="Select Claude Binary",
            initialdir=str(Path.home()),
            filetypes=[("All files", "*"), ("Executables", "*.exe")],
        )
        if filename:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, filename)
            self._test_connection()

    def _test_connection(self) -> None:
        """Test the Claude connection."""
        self.status_dot.configure(text_color=theme.colors.warning)
        self.status_label.configure(text="Testing connection...")
        self.version_label.configure(text="")
        self.test_btn.configure(state="disabled")

        def test():
            path = self.path_entry.get().strip()
            if not path:
                path = app_state.claude_settings.auto_detected_path
            if not path:
                path = "claude"

            status = ConnectionStatus.UNKNOWN
            version = ""

            try:
                # Check if binary exists
                if not Path(path).exists() and path != "claude":
                    status = ConnectionStatus.NOT_FOUND
                else:
                    # Try to get version
                    result = subprocess.run(
                        [path, "-v"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        version = result.stdout.strip()

                        # Try a simple prompt to check auth
                        result = subprocess.run(
                            [path, "-p", "Say OK", "--output-format", "json"],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.returncode == 0 and "OK" in result.stdout:
                            status = ConnectionStatus.CONNECTED
                        else:
                            status = ConnectionStatus.NOT_AUTHENTICATED
                    else:
                        status = ConnectionStatus.ERROR

            except FileNotFoundError:
                status = ConnectionStatus.NOT_FOUND
            except subprocess.TimeoutExpired:
                status = ConnectionStatus.ERROR
            except Exception as e:
                status = ConnectionStatus.ERROR
                print(f"Connection test error: {e}")

            # Update UI on main thread
            self.after(0, lambda: self._update_status(status, version, path))

        threading.Thread(target=test, daemon=True).start()

    def _update_status(self, status: ConnectionStatus, version: str, path: str) -> None:
        """Update status display."""
        self.test_btn.configure(state="normal")
        app_state.connection_status = status

        if status == ConnectionStatus.CONNECTED:
            self.status_dot.configure(text_color=theme.colors.success)
            self.status_label.configure(
                text="Connected",
                text_color=theme.colors.success,
            )
            self.version_label.configure(text=version)

            # Save working path
            settings = app_state.claude_settings
            settings.is_authenticated = True
            settings.version = version
            if path != "claude":
                settings.binary_path = path
            app_state.claude_settings = settings

        elif status == ConnectionStatus.NOT_FOUND:
            self.status_dot.configure(text_color=theme.colors.error)
            self.status_label.configure(
                text="Not Found",
                text_color=theme.colors.error,
            )
            self.version_label.configure(text="Binary not found at specified path")

        elif status == ConnectionStatus.NOT_AUTHENTICATED:
            self.status_dot.configure(text_color=theme.colors.warning)
            self.status_label.configure(
                text="Not Authenticated",
                text_color=theme.colors.warning,
            )
            self.version_label.configure(text=f"{version} - Please run 'claude' and /login")

        else:
            self.status_dot.configure(text_color=theme.colors.error)
            self.status_label.configure(
                text="Error",
                text_color=theme.colors.error,
            )
            self.version_label.configure(text="Could not connect to Claude")

    def _save_settings(self) -> None:
        """Save settings."""
        path = self.path_entry.get().strip()

        settings = app_state.claude_settings
        settings.binary_path = path
        app_state.claude_settings = settings

        # Show confirmation
        self.save_btn.configure(text="✓ Saved!")
        self.after(2000, lambda: self.save_btn.configure(text="Save Settings"))

    def _launch_claude_login(self) -> None:
        """Launch Claude in Terminal for interactive login."""
        import platform

        # Get the Claude binary path
        path = self.path_entry.get().strip()
        if not path:
            path = app_state.claude_settings.auto_detected_path
        if not path:
            # Show error
            self.status_label.configure(
                text="No Claude binary found - please specify path first",
                text_color=theme.colors.error,
            )
            return

        # Show launching message
        self.login_btn.configure(text="Launching...", state="disabled")

        try:
            if platform.system() == "Darwin":  # macOS
                # Open Terminal and run claude for interactive login
                # The user can then type /login in the Claude CLI
                apple_script = f'''
                tell application "Terminal"
                    activate
                    do script "echo 'Starting Claude Code CLI for login...'; echo 'Type /login once Claude starts, then follow the prompts.'; echo ''; \\"{path}\\""
                end tell
                '''
                subprocess.Popen(["osascript", "-e", apple_script])

            elif platform.system() == "Linux":
                # Try common terminal emulators
                terminals = ["gnome-terminal", "konsole", "xterm"]
                for term in terminals:
                    try:
                        if term == "gnome-terminal":
                            subprocess.Popen([term, "--", path])
                        else:
                            subprocess.Popen([term, "-e", path])
                        break
                    except FileNotFoundError:
                        continue

            elif platform.system() == "Windows":
                # Open in new cmd window
                subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", path])

            # Update button after launch
            self.after(1000, lambda: self.login_btn.configure(text="Login to Claude", state="normal"))

            # Show instructions
            self.status_label.configure(
                text="Terminal opened - type /login in Claude CLI",
                text_color=theme.colors.warning,
            )

        except Exception as e:
            self.login_btn.configure(text="Login to Claude", state="normal")
            self.status_label.configure(
                text=f"Failed to launch: {e}",
                text_color=theme.colors.error,
            )
