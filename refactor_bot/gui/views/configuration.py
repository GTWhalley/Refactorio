"""
Configuration view for refactoring settings.
"""

import customtkinter as ctk
from pathlib import Path
from typing import Callable, Optional

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, app_state
from refactor_bot.config import Config


class ConfigurationView(ctk.CTkFrame):
    """
    Configuration view for setting up refactoring parameters.
    """

    def __init__(self, master, on_navigate: Callable[[AppView], None], **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self._config: Optional[Config] = None
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create view widgets."""
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
            text="Configuration",
            font=(theme.fonts.family, theme.fonts.size_title, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(anchor="w")

        self.repo_label = ctk.CTkLabel(
            header,
            text="No repository selected",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
        )
        self.repo_label.pack(anchor="w", pady=(4, 0))

        # Verification Commands Section
        verify_section = self._create_section(scroll, "Verification Commands")

        verify_desc = ctk.CTkLabel(
            verify_section,
            text="Commands to run to verify the code still works after refactoring",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        verify_desc.pack(anchor="w", pady=(0, 12))

        # Fast verifier
        fast_label = ctk.CTkLabel(
            verify_section,
            text="Fast Verifier (runs after each batch)",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        fast_label.pack(anchor="w", pady=(0, 4))

        self.fast_verifier_entry = ctk.CTkEntry(
            verify_section,
            placeholder_text="e.g., npm test, pytest",
            height=40,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            **theme.get_input_style(),
        )
        self.fast_verifier_entry.pack(fill="x", pady=(0, 12))

        # Full verifier
        full_label = ctk.CTkLabel(
            verify_section,
            text="Full Verifier (runs periodically)",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        full_label.pack(anchor="w", pady=(0, 4))

        self.full_verifier_entry = ctk.CTkEntry(
            verify_section,
            placeholder_text="e.g., npm test && npm run lint && npm run typecheck",
            height=40,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            **theme.get_input_style(),
        )
        self.full_verifier_entry.pack(fill="x")

        # Auto-detect button
        detect_btn = ctk.CTkButton(
            verify_section,
            text="Auto-Detect",
            width=120,
            height=32,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_button_style("outline"),
            command=self._auto_detect_verifiers,
        )
        detect_btn.pack(anchor="w", pady=(8, 0))

        # Limits Section
        limits_section = self._create_section(scroll, "Limits & Budgets")

        limits_grid = ctk.CTkFrame(limits_section, fg_color="transparent")
        limits_grid.pack(fill="x")

        # Diff budget
        diff_frame = ctk.CTkFrame(limits_grid, fg_color="transparent")
        diff_frame.grid(row=0, column=0, sticky="ew", padx=(0, 16))

        diff_label = ctk.CTkLabel(
            diff_frame,
            text="Diff Budget (LOC per batch)",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        diff_label.pack(anchor="w", pady=(0, 4))

        self.diff_budget_entry = ctk.CTkEntry(
            diff_frame,
            placeholder_text="300",
            width=120,
            height=40,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            **theme.get_input_style(),
        )
        self.diff_budget_entry.pack(anchor="w")

        # Max batches
        batch_frame = ctk.CTkFrame(limits_grid, fg_color="transparent")
        batch_frame.grid(row=0, column=1, sticky="ew", padx=(0, 16))

        batch_label = ctk.CTkLabel(
            batch_frame,
            text="Max Batches",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        batch_label.pack(anchor="w", pady=(0, 4))

        self.max_batches_entry = ctk.CTkEntry(
            batch_frame,
            placeholder_text="200",
            width=120,
            height=40,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            **theme.get_input_style(),
        )
        self.max_batches_entry.pack(anchor="w")

        # Retries
        retry_frame = ctk.CTkFrame(limits_grid, fg_color="transparent")
        retry_frame.grid(row=0, column=2, sticky="ew")

        retry_label = ctk.CTkLabel(
            retry_frame,
            text="Retries per Batch",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        retry_label.pack(anchor="w", pady=(0, 4))

        self.retry_entry = ctk.CTkEntry(
            retry_frame,
            placeholder_text="2",
            width=120,
            height=40,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            **theme.get_input_style(),
        )
        self.retry_entry.pack(anchor="w")

        limits_grid.columnconfigure(0, weight=1)
        limits_grid.columnconfigure(1, weight=1)
        limits_grid.columnconfigure(2, weight=1)

        # Scope Section
        scope_section = self._create_section(scroll, "Scope")

        exclude_label = ctk.CTkLabel(
            scope_section,
            text="Exclude Patterns (one per line)",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
        )
        exclude_label.pack(anchor="w", pady=(0, 4))

        self.exclude_text = ctk.CTkTextbox(
            scope_section,
            height=100,
            font=(theme.fonts.family_mono, theme.fonts.size_sm),
            fg_color=theme.colors.bg_dark,
            text_color=theme.colors.text_primary,
        )
        self.exclude_text.pack(fill="x")

        # Safety Options Section
        safety_section = self._create_section(scroll, "Safety Options")

        self.allow_api_changes = ctk.CTkCheckBox(
            safety_section,
            text="Allow public API changes",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            fg_color=theme.colors.accent_primary,
            hover_color=theme.colors.accent_primary_hover,
        )
        self.allow_api_changes.pack(anchor="w", pady=(0, 8))

        self.allow_lockfile = ctk.CTkCheckBox(
            safety_section,
            text="Allow lockfile changes",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            fg_color=theme.colors.accent_primary,
            hover_color=theme.colors.accent_primary_hover,
        )
        self.allow_lockfile.pack(anchor="w", pady=(0, 8))

        self.allow_format_only = ctk.CTkCheckBox(
            safety_section,
            text="Allow formatting-only batches",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            fg_color=theme.colors.accent_primary,
            hover_color=theme.colors.accent_primary_hover,
        )
        self.allow_format_only.select()
        self.allow_format_only.pack(anchor="w")

        # Action buttons
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(24, 0))

        self.save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Configuration",
            width=160,
            height=44,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("outline"),
            command=self._save_config,
        )
        self.save_btn.pack(side="left", padx=(0, 12))

        self.generate_plan_btn = ctk.CTkButton(
            btn_frame,
            text="Generate Plan →",
            width=160,
            height=44,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("primary"),
            command=self._generate_plan,
        )
        self.generate_plan_btn.pack(side="left")

    def _create_section(self, parent, title: str) -> ctk.CTkFrame:
        """Create a configuration section."""
        section = ctk.CTkFrame(
            parent,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )
        section.pack(fill="x", pady=(0, 16))

        content = ctk.CTkFrame(section, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=20)

        title_label = ctk.CTkLabel(
            content,
            text=title,
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        title_label.pack(anchor="w", pady=(0, 12))

        return content

    def load_config(self) -> None:
        """Load configuration for the selected repository."""
        repo = app_state.repo
        if not repo.path:
            return

        self.repo_label.configure(text=f"Repository: {repo.name}")

        # Load or create config
        self._config = Config.load_or_create(repo.path)
        self._config = self._config.detect_verifiers(repo.path)

        # Populate fields
        self.fast_verifier_entry.delete(0, "end")
        self.fast_verifier_entry.insert(0, ", ".join(self._config.fast_verifier))

        self.full_verifier_entry.delete(0, "end")
        self.full_verifier_entry.insert(0, ", ".join(self._config.full_verifier))

        self.diff_budget_entry.delete(0, "end")
        self.diff_budget_entry.insert(0, str(self._config.diff_budget_loc))

        self.max_batches_entry.delete(0, "end")
        self.max_batches_entry.insert(0, str(self._config.max_batches))

        self.retry_entry.delete(0, "end")
        self.retry_entry.insert(0, str(self._config.retry_per_batch))

        self.exclude_text.delete("1.0", "end")
        self.exclude_text.insert("1.0", "\n".join(self._config.scope_excludes))

        if self._config.allow_public_api_changes:
            self.allow_api_changes.select()
        else:
            self.allow_api_changes.deselect()

        if self._config.allow_lockfile_changes:
            self.allow_lockfile.select()
        else:
            self.allow_lockfile.deselect()

        if self._config.allow_formatting_only:
            self.allow_format_only.select()
        else:
            self.allow_format_only.deselect()

        # Store in app state
        app_state.repo.config = self._config

    def _auto_detect_verifiers(self) -> None:
        """Auto-detect verification commands."""
        repo = app_state.repo
        if not repo.path:
            return

        from refactor_bot.verifier import Verifier

        detected = Verifier.detect_commands(repo.path)

        self.fast_verifier_entry.delete(0, "end")
        self.fast_verifier_entry.insert(0, ", ".join(detected.get("fast", [])))

        self.full_verifier_entry.delete(0, "end")
        self.full_verifier_entry.insert(0, ", ".join(detected.get("full", [])))

    def _save_config(self) -> None:
        """Save the current configuration."""
        if not self._config:
            return

        # Update config from form
        fast = [cmd.strip() for cmd in self.fast_verifier_entry.get().split(",") if cmd.strip()]
        full = [cmd.strip() for cmd in self.full_verifier_entry.get().split(",") if cmd.strip()]

        self._config.fast_verifier = fast
        self._config.full_verifier = full

        try:
            self._config.diff_budget_loc = int(self.diff_budget_entry.get())
        except ValueError:
            pass

        try:
            self._config.max_batches = int(self.max_batches_entry.get())
        except ValueError:
            pass

        try:
            self._config.retry_per_batch = int(self.retry_entry.get())
        except ValueError:
            pass

        excludes = self.exclude_text.get("1.0", "end").strip().split("\n")
        self._config.scope_excludes = [e.strip() for e in excludes if e.strip()]

        self._config.allow_public_api_changes = self.allow_api_changes.get() == 1
        self._config.allow_lockfile_changes = self.allow_lockfile.get() == 1
        self._config.allow_formatting_only = self.allow_format_only.get() == 1

        # Save to disk
        repo = app_state.repo
        if repo.path:
            self._config.save(repo.path)
            app_state.repo.config = self._config

        # Visual feedback
        self.save_btn.configure(text="✓ Saved!")
        self.after(2000, lambda: self.save_btn.configure(text="Save Configuration"))

    def _generate_plan(self) -> None:
        """Save config and navigate to plan view."""
        self._save_config()
        self.on_navigate(AppView.PLAN)
