"""
Security scan view for vulnerability analysis.
"""

import customtkinter as ctk
import threading
from typing import Callable, Optional
from pathlib import Path

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, ConnectionStatus, app_state
from refactor_bot.gui.components.debug_console import debug_log, debug_error


class FindingCard(ctk.CTkFrame):
    """Card displaying a single security finding."""

    SEVERITY_COLORS = {
        "high": "#dc3545",
        "medium": "#ffc107",
        "low": "#6c757d",
        "info": "#17a2b8",
    }

    def __init__(self, master, finding: dict, **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
            **kwargs
        )

        self._create_widgets(finding)

    def _create_widgets(self, finding: dict) -> None:
        """Create card widgets."""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=12)

        # Header row
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")

        severity = finding.get("severity", "info")
        color = self.SEVERITY_COLORS.get(severity, "#6c757d")

        severity_badge = ctk.CTkLabel(
            header,
            text=severity.upper(),
            font=(theme.fonts.family, theme.fonts.size_xs, "bold"),
            fg_color=color,
            corner_radius=4,
            width=60,
            height=20,
            text_color="white" if severity != "medium" else "black",
        )
        severity_badge.pack(side="left")

        title = ctk.CTkLabel(
            header,
            text=finding.get("title", "Unknown"),
            font=(theme.fonts.family, theme.fonts.size_md, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(side="left", padx=(12, 0))

        # File location
        file_info = f"{finding.get('file', 'Unknown')}:{finding.get('line', 0)}"
        file_label = ctk.CTkLabel(
            content,
            text=file_info,
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.accent,
        )
        file_label.pack(anchor="w", pady=(8, 0))

        # Description
        desc = ctk.CTkLabel(
            content,
            text=finding.get("description", ""),
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            wraplength=600,
            justify="left",
        )
        desc.pack(anchor="w", pady=(4, 0))

        # Recommendation
        rec_label = ctk.CTkLabel(
            content,
            text="Recommendation:",
            font=(theme.fonts.family, theme.fonts.size_sm, "bold"),
            text_color=theme.colors.text_primary,
        )
        rec_label.pack(anchor="w", pady=(8, 0))

        rec = ctk.CTkLabel(
            content,
            text=finding.get("recommendation", ""),
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            wraplength=600,
            justify="left",
        )
        rec.pack(anchor="w")

        # CWE if available
        cwe = finding.get("cwe")
        if cwe:
            cwe_label = ctk.CTkLabel(
                content,
                text=cwe,
                font=(theme.fonts.family, theme.fonts.size_xs),
                text_color=theme.colors.text_secondary,
            )
            cwe_label.pack(anchor="w", pady=(4, 0))


class SecurityView(ctk.CTkFrame):
    """
    Security scan view with vulnerability analysis.
    """

    def __init__(self, master, on_navigate: Callable[[AppView], None], **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self._is_scanning = False
        self._result = None
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create view widgets."""
        # Scrollable container
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self.scroll.pack(fill="both", expand=True, padx=24, pady=24)

        # Header
        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))

        title = ctk.CTkLabel(
            header,
            text="Security Scan",
            font=(theme.fonts.family, theme.fonts.size_title, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(side="left")

        # Scan button
        self.scan_btn = ctk.CTkButton(
            header,
            text="Run Security Scan",
            width=160,
            height=36,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_button_style("primary"),
            command=self._start_scan,
        )
        self.scan_btn.pack(side="right")

        # Status section
        self.status_frame = ctk.CTkFrame(
            self.scroll,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )
        self.status_frame.pack(fill="x", pady=(0, 16))

        status_content = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        status_content.pack(fill="x", padx=20, pady=16)

        self.status_label = ctk.CTkLabel(
            status_content,
            text="Select a repository and run a security scan to check for vulnerabilities.",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
        )
        self.status_label.pack(anchor="w")

        # Summary section (hidden until scan completes)
        self.summary_frame = ctk.CTkFrame(
            self.scroll,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )

        # Findings container
        self.findings_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")

    def _start_scan(self) -> None:
        """Start the security scan."""
        if self._is_scanning:
            return

        repo = app_state.repo
        if not repo.path:
            self.status_label.configure(
                text="No repository selected. Please select a repository first.",
                text_color=theme.colors.error,
            )
            return

        if app_state.connection_status != ConnectionStatus.CONNECTED:
            self.status_label.configure(
                text="Claude Code not connected. Please check settings.",
                text_color=theme.colors.error,
            )
            return

        self._is_scanning = True
        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.status_label.configure(
            text="Running security analysis... This may take a minute.",
            text_color=theme.colors.text_primary,
        )

        # Clear previous results
        self.summary_frame.pack_forget()
        for widget in self.findings_frame.winfo_children():
            widget.destroy()
        self.findings_frame.pack_forget()

        # Run scan in background
        thread = threading.Thread(target=self._run_scan, daemon=True)
        thread.start()

    def _run_scan(self) -> None:
        """Run the security scan in background."""
        try:
            from refactor_bot.security import SecurityReviewer
            from refactor_bot.claude_driver import ClaudeDriver
            from refactor_bot.config import Config, ClaudeConfig
            from refactor_bot.indexer import SymbolExtractor

            repo = app_state.repo
            repo_path = repo.path

            debug_log(f"Starting security scan on {repo_path}", "info")

            # Get config
            config = repo.config or Config.load_or_create(repo_path)

            # Get files to scan
            extractor = SymbolExtractor(repo_path, config.scope_excludes)
            extractor.index_files()
            scan_files = [str(f.relative_to(repo_path)) for f in extractor.files]

            if not scan_files:
                self.after(0, lambda: self._show_error("No files found to scan"))
                return

            debug_log(f"Scanning {len(scan_files)} files", "info")

            # Initialize Claude driver
            prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts"
            schemas_dir = Path(__file__).parent.parent.parent.parent / "schemas"

            claude_binary = app_state.get_claude_binary()
            claude_config = ClaudeConfig(binary=claude_binary)

            claude_driver = ClaudeDriver(
                config=claude_config,
                prompts_dir=prompts_dir,
                schemas_dir=schemas_dir,
                working_dir=repo_path,
            )

            # Run security scan
            reviewer = SecurityReviewer(claude_driver, repo_path)
            result = reviewer.review_changes(scan_files)

            debug_log(f"Security scan complete. Found {result.summary.total} issues", "info")

            self._result = result
            self.after(0, self._display_results)

        except Exception as e:
            debug_error(e, "Security scan failed")
            self.after(0, lambda: self._show_error(str(e)))
        finally:
            self._is_scanning = False
            self.after(0, lambda: self.scan_btn.configure(state="normal", text="Run Security Scan"))

    def _show_error(self, error: str) -> None:
        """Show error message."""
        self.status_label.configure(
            text=f"Error: {error}",
            text_color=theme.colors.error,
        )

    def _display_results(self) -> None:
        """Display scan results."""
        if not self._result:
            return

        result = self._result

        if not result.success:
            self._show_error(result.error_message or "Unknown error")
            return

        # Update status
        if result.summary.total == 0:
            self.status_label.configure(
                text="No security vulnerabilities found!",
                text_color=theme.colors.success,
            )
        else:
            self.status_label.configure(
                text=f"Found {result.summary.total} potential security issues.",
                text_color=theme.colors.warning if result.summary.high == 0 else theme.colors.error,
            )

        # Show summary
        self._create_summary()

        # Show findings
        if result.findings:
            self._create_findings()

    def _create_summary(self) -> None:
        """Create summary section."""
        # Clear existing
        for widget in self.summary_frame.winfo_children():
            widget.destroy()

        result = self._result
        content = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=16)

        title = ctk.CTkLabel(
            content,
            text="Summary",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(anchor="w", pady=(0, 12))

        # Stats row
        stats = ctk.CTkFrame(content, fg_color="transparent")
        stats.pack(fill="x")

        # High
        high_frame = ctk.CTkFrame(stats, fg_color="#dc354520", corner_radius=8)
        high_frame.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            high_frame, text=str(result.summary.high),
            font=(theme.fonts.family, 24, "bold"),
            text_color="#dc3545",
        ).pack(padx=16, pady=(8, 0))
        ctk.CTkLabel(
            high_frame, text="High",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        ).pack(padx=16, pady=(0, 8))

        # Medium
        med_frame = ctk.CTkFrame(stats, fg_color="#ffc10720", corner_radius=8)
        med_frame.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            med_frame, text=str(result.summary.medium),
            font=(theme.fonts.family, 24, "bold"),
            text_color="#ffc107",
        ).pack(padx=16, pady=(8, 0))
        ctk.CTkLabel(
            med_frame, text="Medium",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        ).pack(padx=16, pady=(0, 8))

        # Low
        low_frame = ctk.CTkFrame(stats, fg_color="#6c757d20", corner_radius=8)
        low_frame.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            low_frame, text=str(result.summary.low),
            font=(theme.fonts.family, 24, "bold"),
            text_color="#6c757d",
        ).pack(padx=16, pady=(8, 0))
        ctk.CTkLabel(
            low_frame, text="Low",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        ).pack(padx=16, pady=(0, 8))

        # Overall risk
        risk_label = ctk.CTkLabel(
            content,
            text=f"Overall Risk: {result.overall_risk.value.upper()}",
            font=(theme.fonts.family, theme.fonts.size_md, "bold"),
            text_color=theme.colors.text_primary,
        )
        risk_label.pack(anchor="w", pady=(16, 0))

        if result.notes:
            notes = ctk.CTkLabel(
                content,
                text=result.notes,
                font=(theme.fonts.family, theme.fonts.size_sm),
                text_color=theme.colors.text_secondary,
                wraplength=600,
                justify="left",
            )
            notes.pack(anchor="w", pady=(8, 0))

        self.summary_frame.pack(fill="x", pady=(0, 16))

    def _create_findings(self) -> None:
        """Create findings list."""
        result = self._result

        # Title
        title = ctk.CTkLabel(
            self.findings_frame,
            text="Findings",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(anchor="w", pady=(0, 12))

        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
        sorted_findings = sorted(
            result.findings,
            key=lambda f: severity_order.get(f.severity.value, 4)
        )

        for finding in sorted_findings:
            card = FindingCard(
                self.findings_frame,
                finding.to_dict(),
            )
            card.pack(fill="x", pady=(0, 8))

        self.findings_frame.pack(fill="x")
