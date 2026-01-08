"""
Plan view for displaying and editing the refactoring plan.
"""

import customtkinter as ctk
import threading
import traceback
from typing import Callable, Optional

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, app_state
from refactor_bot.gui.components.batch_list import BatchList
from refactor_bot.gui.components.risk_badge import RiskHeatmap
from refactor_bot.gui.components.diff_viewer import DiffViewer
from refactor_bot.gui.components.debug_console import debug_log, debug_error


class PlanView(ctk.CTkFrame):
    """
    Plan view showing refactoring batches with editing capabilities.
    """

    def __init__(self, master, on_navigate: Callable[[AppView], None], **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self._plan = None
        self._selected_batch = None
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create view widgets."""
        # Main container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=24)

        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))

        title = ctk.CTkLabel(
            header,
            text="Refactoring Plan",
            font=(theme.fonts.family, theme.fonts.size_title, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(side="left")

        # Action buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        self.regenerate_btn = ctk.CTkButton(
            btn_frame,
            text="Regenerate",
            width=100,
            height=36,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_button_style("outline"),
            command=self._regenerate_plan,
        )
        self.regenerate_btn.pack(side="left", padx=(0, 8))

        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="Start Refactoring →",
            width=160,
            height=36,
            font=(theme.fonts.family, theme.fonts.size_md),
            **theme.get_button_style("primary"),
            command=self._start_refactoring,
        )
        self.start_btn.pack(side="left")

        # Stats bar
        stats_bar = ctk.CTkFrame(
            container,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.border_radius,
            height=60,
        )
        stats_bar.pack(fill="x", pady=(0, 16))
        stats_bar.pack_propagate(False)

        stats_content = ctk.CTkFrame(stats_bar, fg_color="transparent")
        stats_content.pack(fill="both", expand=True, padx=16, pady=12)

        # Stat items
        self.stat_batches = self._create_stat(stats_content, "0", "Batches")
        self.stat_batches.pack(side="left", padx=(0, 32))

        self.stat_loc = self._create_stat(stats_content, "0", "Est. LOC")
        self.stat_loc.pack(side="left", padx=(0, 32))

        self.stat_low = self._create_stat(stats_content, "0", "Low Risk", theme.colors.success)
        self.stat_low.pack(side="left", padx=(0, 32))

        self.stat_med = self._create_stat(stats_content, "0", "Med Risk", theme.colors.warning)
        self.stat_med.pack(side="left", padx=(0, 32))

        self.stat_high = self._create_stat(stats_content, "0", "High Risk", theme.colors.error)
        self.stat_high.pack(side="left")

        # Main content - two columns
        content = ctk.CTkFrame(container, fg_color="transparent")
        content.pack(fill="both", expand=True)

        # Left column - Batch list
        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 12))

        # Risk heatmap
        self.heatmap = RiskHeatmap(left_col)
        self.heatmap.pack(fill="x", pady=(0, 12))

        # Batch list
        self.batch_list = BatchList(
            left_col,
            on_select=self._on_batch_select,
        )
        self.batch_list.pack(fill="both", expand=True)

        # Right column - Batch details
        right_col = ctk.CTkFrame(
            content,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
            width=400,
        )
        right_col.pack(side="right", fill="both", padx=(12, 0))
        right_col.pack_propagate(False)

        details_content = ctk.CTkFrame(right_col, fg_color="transparent")
        details_content.pack(fill="both", expand=True, padx=16, pady=16)

        self.details_title = ctk.CTkLabel(
            details_content,
            text="Select a batch to view details",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        self.details_title.pack(anchor="w")

        self.details_goal = ctk.CTkLabel(
            details_content,
            text="",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
            wraplength=360,
            justify="left",
        )
        self.details_goal.pack(anchor="w", pady=(8, 0))

        # Detail sections
        self.details_frame = ctk.CTkFrame(details_content, fg_color="transparent")
        self.details_frame.pack(fill="x", pady=(16, 0))

        # Scope
        scope_label = ctk.CTkLabel(
            self.details_frame,
            text="Scope",
            font=(theme.fonts.family, theme.fonts.size_sm, "bold"),
            text_color=theme.colors.text_muted,
        )
        scope_label.pack(anchor="w")

        self.scope_text = ctk.CTkLabel(
            self.details_frame,
            text="-",
            font=(theme.fonts.family_mono, theme.fonts.size_xs),
            text_color=theme.colors.text_secondary,
            wraplength=360,
            justify="left",
        )
        self.scope_text.pack(anchor="w", pady=(4, 12))

        # Operations
        ops_label = ctk.CTkLabel(
            self.details_frame,
            text="Allowed Operations",
            font=(theme.fonts.family, theme.fonts.size_sm, "bold"),
            text_color=theme.colors.text_muted,
        )
        ops_label.pack(anchor="w")

        self.ops_text = ctk.CTkLabel(
            self.details_frame,
            text="-",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            wraplength=360,
            justify="left",
        )
        self.ops_text.pack(anchor="w", pady=(4, 12))

        # Notes
        notes_label = ctk.CTkLabel(
            self.details_frame,
            text="Notes",
            font=(theme.fonts.family, theme.fonts.size_sm, "bold"),
            text_color=theme.colors.text_muted,
        )
        notes_label.pack(anchor="w")

        self.notes_text = ctk.CTkLabel(
            self.details_frame,
            text="-",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_secondary,
            wraplength=360,
            justify="left",
        )
        self.notes_text.pack(anchor="w", pady=(4, 0))

        # Loading overlay
        self.loading_frame = ctk.CTkFrame(
            self,
            fg_color=theme.colors.bg_dark,
        )

        loading_content = ctk.CTkFrame(self.loading_frame, fg_color="transparent")
        loading_content.place(relx=0.5, rely=0.5, anchor="center")

        self.loading_label = ctk.CTkLabel(
            loading_content,
            text="Generating plan...",
            font=(theme.fonts.family, theme.fonts.size_lg),
            text_color=theme.colors.text_primary,
        )
        self.loading_label.pack()

        self.loading_progress = ctk.CTkProgressBar(
            loading_content,
            width=300,
            height=8,
            fg_color=theme.colors.progress_bg,
            progress_color=theme.colors.accent_secondary,
            mode="indeterminate",
        )
        self.loading_progress.pack(pady=(16, 0))

    def _create_stat(
        self,
        parent,
        value: str,
        label: str,
        color: str = None,
    ) -> ctk.CTkFrame:
        """Create a stat display widget."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        value_label = ctk.CTkLabel(
            frame,
            text=value,
            font=(theme.fonts.family, theme.fonts.size_xl, "bold"),
            text_color=color or theme.colors.text_primary,
        )
        value_label.pack(anchor="w")

        label_label = ctk.CTkLabel(
            frame,
            text=label,
            font=(theme.fonts.family, theme.fonts.size_xs),
            text_color=theme.colors.text_muted,
        )
        label_label.pack(anchor="w")

        frame.value_label = value_label
        return frame

    def generate_plan(self) -> None:
        """Generate a refactoring plan for the current repository.

        Uses config.use_llm_planner to determine whether to refine with Claude.
        """
        repo = app_state.repo
        if not repo.path:
            debug_log("No repository selected", "warning")
            return

        debug_log(f"Starting plan generation for: {repo.path}", "info")

        # Show loading
        self.loading_frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.loading_progress.start()

        def generate():
            try:
                from refactor_bot.config import Config
                from refactor_bot.indexer import SymbolExtractor, DependencyAnalyzer
                from refactor_bot.planner import Planner
                from refactor_bot.claude_driver import ClaudeDriver, set_debug_logger
                from pathlib import Path

                debug_log("Loading configuration...", "debug")
                # Always get fresh config from app_state to pick up settings changes
                config = app_state.repo.config or Config.load_or_create(repo.path)
                debug_log(f"Config loaded. Excludes: {config.scope_excludes}", "debug")

                # Check config for LLM planner setting (must be inside thread to get fresh value)
                use_claude = config.use_llm_planner
                debug_log(f"Using Claude for planning: {use_claude}", "info")

                # Index
                self.after(0, lambda: self.loading_label.configure(text="Indexing codebase..."))
                debug_log("Indexing codebase - extracting symbols...", "info")
                symbols = SymbolExtractor(repo.path, config.scope_excludes)
                symbols.index_files()
                debug_log(f"Indexed {len(symbols.files)} files, {len(symbols.symbols)} symbols", "success")

                self.after(0, lambda: self.loading_label.configure(text="Analyzing dependencies..."))
                debug_log("Analyzing dependencies...", "info")
                deps = DependencyAnalyzer(repo.path, config.scope_excludes)
                dep_graph = deps.analyze()
                debug_log(f"Dependency analysis complete. {len(dep_graph.nodes)} nodes", "success")

                # Generate naive plan first
                self.after(0, lambda: self.loading_label.configure(text="Generating initial plan..."))
                debug_log("Generating naive refactoring plan...", "info")
                planner = Planner(repo.path, config, symbols, dep_graph)
                plan = planner.generate_naive_plan()
                debug_log(f"Naive plan: {len(plan.batches)} batches, ~{plan.total_estimated_loc} LOC", "success")

                # Optionally refine with Claude
                if use_claude and len(symbols.files) > 0:
                    self.after(0, lambda: self.loading_label.configure(text="Asking Claude to refine plan..."))
                    debug_log("Refining plan with Claude PlannerAgent...", "info")

                    # Setup Claude driver
                    # Path: views/plan_view.py -> gui -> refactor_bot -> project root
                    project_root = Path(__file__).parent.parent.parent.parent
                    prompts_dir = project_root / "prompts"
                    schemas_dir = project_root / "schemas"
                    debug_log(f"Prompts dir: {prompts_dir}", "debug")

                    claude_config = config.claude
                    claude_config.binary = app_state.get_claude_binary()

                    # Wire up debug logging
                    set_debug_logger(debug_log)

                    claude_driver = ClaudeDriver(
                        config=claude_config,
                        prompts_dir=prompts_dir,
                        schemas_dir=schemas_dir,
                        working_dir=repo.path,
                    )
                    debug_log(f"Claude driver initialized. Binary: {claude_config.binary}", "debug")

                    # Build architecture snapshot for context
                    architecture_snapshot = self._build_architecture_snapshot(symbols, dep_graph)

                    # Refine plan with Claude
                    refined_plan = planner.refine_with_llm(plan, claude_driver, architecture_snapshot)

                    if refined_plan and len(refined_plan.batches) > 0:
                        debug_log(f"Claude refined plan: {len(refined_plan.batches)} batches", "success")
                        plan = refined_plan
                    else:
                        debug_log("Claude returned no changes, using naive plan", "warning")
                elif use_claude and len(symbols.files) == 0:
                    debug_log("No files indexed - cannot use Claude for planning (nothing to analyze)", "warning")

                debug_log(f"Final plan: {len(plan.batches)} batches, ~{plan.total_estimated_loc} LOC", "success")

                # Update UI
                self.after(0, lambda: self._display_plan(plan))

            except Exception as e:
                debug_error(e, "Plan generation failed")
                self.after(0, lambda: self._on_plan_error(str(e)))

        threading.Thread(target=generate, daemon=True).start()

    def _build_architecture_snapshot(self, symbols, dep_graph) -> str:
        """Build a concise architecture snapshot for Claude context."""
        lines = ["# Codebase Architecture Snapshot\n"]

        # File summary
        lines.append(f"## Files: {len(symbols.files)}")
        lines.append(f"## Symbols: {len(symbols.symbols)}\n")

        # Languages
        langs = {}
        for f in symbols.files.values():
            lang = f.language or "unknown"
            langs[lang] = langs.get(lang, 0) + 1
        if langs:
            lines.append("## Languages:")
            for lang, count in sorted(langs.items(), key=lambda x: -x[1]):
                lines.append(f"  - {lang}: {count} files")
            lines.append("")

        # Key files (high fan-in)
        if dep_graph and dep_graph.nodes:
            hotspots = dep_graph.get_hotspots(min_fan_in=2)[:10]
            if hotspots:
                lines.append("## High-Impact Files (most dependents):")
                for node in hotspots:
                    lines.append(f"  - {node.path} (fan-in: {node.fan_in})")
                lines.append("")

        # Symbol types
        symbol_types = {}
        for s in symbols.symbols:
            st = s.symbol_type.value
            symbol_types[st] = symbol_types.get(st, 0) + 1
        if symbol_types:
            lines.append("## Symbol Types:")
            for st, count in sorted(symbol_types.items(), key=lambda x: -x[1]):
                lines.append(f"  - {st}: {count}")

        return "\n".join(lines)

    def _on_plan_error(self, error_msg: str) -> None:
        """Handle plan generation error."""
        self.loading_progress.stop()
        self.loading_frame.place_forget()
        self.loading_label.configure(text=f"Error: {error_msg}")

    def _display_plan(self, plan) -> None:
        """Display the generated plan."""
        self._plan = plan
        app_state.plan = plan

        # Hide loading
        self.loading_progress.stop()
        self.loading_frame.place_forget()

        # Update stats
        batches = plan.batches
        self.stat_batches.value_label.configure(text=str(len(batches)))
        self.stat_loc.value_label.configure(text=str(plan.total_estimated_loc))

        low = sum(1 for b in batches if b.risk_score <= 30)
        med = sum(1 for b in batches if 30 < b.risk_score <= 60)
        high = sum(1 for b in batches if b.risk_score > 60)

        self.stat_low.value_label.configure(text=str(low))
        self.stat_med.value_label.configure(text=str(med))
        self.stat_high.value_label.configure(text=str(high))

        # Update heatmap
        self.heatmap.set_data([b.risk_score for b in batches])

        # Update batch list
        self.batch_list.set_batches(batches)

    def _on_batch_select(self, batch) -> None:
        """Handle batch selection."""
        self._selected_batch = batch

        self.details_title.configure(text=batch.id)
        self.details_goal.configure(text=batch.goal)
        self.scope_text.configure(text="\n".join(batch.scope_globs))
        self.ops_text.configure(text=", ".join(batch.allowed_operations))
        self.notes_text.configure(text=batch.notes or "-")

    def _regenerate_plan(self) -> None:
        """Regenerate the plan."""
        self.generate_plan()

    def _start_refactoring(self) -> None:
        """Start the refactoring process."""
        if not self._plan or not self._plan.batches:
            return

        self.on_navigate(AppView.PROGRESS)
