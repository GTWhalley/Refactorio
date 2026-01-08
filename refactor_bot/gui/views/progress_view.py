"""
Progress view for real-time refactoring visualization.
"""

import customtkinter as ctk
import threading
import time
from typing import Callable, Optional

from refactor_bot.gui.theme import theme
from refactor_bot.gui.state import AppView, app_state
from refactor_bot.gui.components.progress_bar import AnimatedProgressBar, BatchProgressIndicator
from refactor_bot.gui.components.log_viewer import LogViewer
from refactor_bot.gui.components.diff_viewer import DiffViewer
from refactor_bot.gui.components.debug_console import debug_log, debug_error
from refactor_bot.gui.components.activity_indicator import BatchActivityDisplay


class ProgressView(ctk.CTkFrame):
    """
    Progress view with real-time visualization of refactoring.
    """

    def __init__(self, master, on_navigate: Callable[[AppView], None], **kwargs):
        super().__init__(
            master,
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self._is_running = False
        self._is_paused = False
        self._should_stop = False
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
            text="Refactoring Progress",
            font=(theme.fonts.family, theme.fonts.size_title, "bold"),
            text_color=theme.colors.text_primary,
        )
        title.pack(side="left")

        # Control buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        self.pause_btn = ctk.CTkButton(
            btn_frame,
            text="Pause",
            width=80,
            height=36,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_button_style("outline"),
            command=self._toggle_pause,
        )
        self.pause_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="Stop",
            width=80,
            height=36,
            font=(theme.fonts.family, theme.fonts.size_sm),
            **theme.get_button_style("danger"),
            command=self._stop_refactoring,
        )
        self.stop_btn.pack(side="left")

        # Overall progress section
        progress_section = ctk.CTkFrame(
            container,
            fg_color=theme.colors.bg_medium,
            corner_radius=theme.dimensions.card_radius,
        )
        progress_section.pack(fill="x", pady=(0, 16))

        progress_content = ctk.CTkFrame(progress_section, fg_color="transparent")
        progress_content.pack(fill="x", padx=20, pady=20)

        # Progress bar
        self.overall_progress = AnimatedProgressBar(
            progress_content,
            label="Overall Progress",
            show_percentage=True,
            height=24,
        )
        self.overall_progress.pack(fill="x", pady=(0, 16))

        # Batch indicators
        self.batch_indicators = BatchProgressIndicator(
            progress_content,
            total=10,
            size=18,
        )
        self.batch_indicators.pack(anchor="w", pady=(0, 16))

        # Current batch info
        current_frame = ctk.CTkFrame(progress_content, fg_color="transparent")
        current_frame.pack(fill="x")

        self.current_batch_label = ctk.CTkLabel(
            current_frame,
            text="Ready to start",
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=theme.colors.text_primary,
        )
        self.current_batch_label.pack(anchor="w")

        self.current_goal_label = ctk.CTkLabel(
            current_frame,
            text="",
            font=(theme.fonts.family, theme.fonts.size_md),
            text_color=theme.colors.text_secondary,
        )
        self.current_goal_label.pack(anchor="w", pady=(4, 0))

        # Stats row
        stats_frame = ctk.CTkFrame(progress_content, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(16, 0))

        self.stat_completed = self._create_inline_stat(stats_frame, "0", "Completed")
        self.stat_completed.pack(side="left", padx=(0, 32))

        self.stat_failed = self._create_inline_stat(stats_frame, "0", "Failed", theme.colors.error)
        self.stat_failed.pack(side="left", padx=(0, 32))

        self.stat_remaining = self._create_inline_stat(stats_frame, "0", "Remaining")
        self.stat_remaining.pack(side="left", padx=(0, 32))

        self.stat_time = self._create_inline_stat(stats_frame, "0:00", "Elapsed")
        self.stat_time.pack(side="left")

        # Activity indicator (shows during Claude processing)
        self.activity_display = BatchActivityDisplay(container)
        # Initially hidden, will show during batch processing

        # Main content - two columns
        content = ctk.CTkFrame(container, fg_color="transparent")
        content.pack(fill="both", expand=True)

        # Left column - Diff preview
        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.diff_viewer = DiffViewer(left_col)
        self.diff_viewer.pack(fill="both", expand=True)

        # Right column - Log viewer
        right_col = ctk.CTkFrame(content, fg_color="transparent", width=400)
        right_col.pack(side="right", fill="both", padx=(8, 0))
        right_col.pack_propagate(False)

        self.log_viewer = LogViewer(right_col)
        self.log_viewer.pack(fill="both", expand=True)

        # Start button (shown before running)
        self.start_frame = ctk.CTkFrame(
            self,
            fg_color=theme.colors.bg_dark,
        )

        start_content = ctk.CTkFrame(self.start_frame, fg_color="transparent")
        start_content.place(relx=0.5, rely=0.5, anchor="center")

        start_icon = ctk.CTkLabel(
            start_content,
            text="▶",
            font=(theme.fonts.family, 48),
            text_color=theme.colors.accent_primary,
        )
        start_icon.pack()

        start_text = ctk.CTkLabel(
            start_content,
            text="Ready to start refactoring",
            font=(theme.fonts.family, theme.fonts.size_lg),
            text_color=theme.colors.text_primary,
        )
        start_text.pack(pady=(16, 0))

        self.start_btn = ctk.CTkButton(
            start_content,
            text="Start Refactoring",
            width=200,
            height=50,
            font=(theme.fonts.family, theme.fonts.size_lg),
            **theme.get_button_style("primary"),
            command=self.start_refactoring,
        )
        self.start_btn.pack(pady=(24, 0))

    def _create_inline_stat(
        self,
        parent,
        value: str,
        label: str,
        color: str = None,
    ) -> ctk.CTkFrame:
        """Create an inline stat widget."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        value_label = ctk.CTkLabel(
            frame,
            text=value,
            font=(theme.fonts.family, theme.fonts.size_lg, "bold"),
            text_color=color or theme.colors.text_primary,
        )
        value_label.pack(side="left")

        label_label = ctk.CTkLabel(
            frame,
            text=f" {label}",
            font=(theme.fonts.family, theme.fonts.size_sm),
            text_color=theme.colors.text_muted,
        )
        label_label.pack(side="left")

        frame.value_label = value_label
        return frame

    def show_start_screen(self) -> None:
        """Show the start screen."""
        plan = app_state.plan
        if plan and plan.batches:
            self.batch_indicators.set_total(min(len(plan.batches), 30))
            self.stat_remaining.value_label.configure(text=str(len(plan.batches)))

        self.start_frame.place(x=0, y=0, relwidth=1, relheight=1)

    def start_refactoring(self) -> None:
        """Start the refactoring process."""
        self.start_frame.place_forget()
        self._is_running = True
        self._is_paused = False
        self._should_stop = False
        self._start_time = time.time()

        # Start the timer update
        self._update_timer()

        # Start refactoring in background thread
        threading.Thread(target=self._run_refactoring, daemon=True).start()

    def _run_refactoring(self) -> None:
        """Run the refactoring process."""
        from refactor_bot.config import Config
        from refactor_bot.repo_manager import RepoManager
        from refactor_bot.backup import BackupManager
        from refactor_bot.verifier import Verifier, VerifierLevel
        from refactor_bot.indexer import SymbolExtractor, DependencyAnalyzer
        from refactor_bot.claude_driver import ClaudeDriver
        from refactor_bot.context_pack import ContextPackBuilder
        from refactor_bot.patch_apply import apply_patch
        from refactor_bot.ledger import TaskLedger
        from pathlib import Path

        repo = app_state.repo
        plan = app_state.plan

        if not repo.path or not plan:
            self.after(0, lambda: self.log_viewer.log_error("No repository or plan"))
            debug_log("Cannot start: No repository or plan", "error")
            return

        self.after(0, lambda: self.log_viewer.log_info("Starting refactoring..."))
        debug_log(f"Starting refactoring on {repo.path} with {len(plan.batches)} batches", "info")

        config = repo.config or Config.load_or_create(repo.path)
        debug_log(f"Config loaded. Claude binary: {config.claude.binary}", "debug")

        # Initialize
        repo_manager = RepoManager(repo.path)

        try:
            # Create backup
            self.after(0, lambda: self.log_viewer.log_info("Creating backup..."))
            backup_manager = BackupManager(repo.path, repo_manager.run_id)
            backup_info = backup_manager.create_backup()
            self.after(0, lambda: self.log_viewer.log_success(f"Backup created: {repo_manager.run_id}"))

            # Create worktree
            self.after(0, lambda: self.log_viewer.log_info("Creating worktree..."))
            worktree_path = repo_manager.create_worktree()
            self.after(0, lambda: self.log_viewer.log_success("Worktree created"))

            # Baseline verification
            self.after(0, lambda: self.log_viewer.log_info("Running baseline verification..."))
            verifier = Verifier(worktree_path, config)
            baseline = verifier.run_baseline()

            if not baseline.passed:
                self.after(0, lambda: self.log_viewer.log_error("Baseline verification failed!"))
                for cmd in baseline.failed_commands:
                    self.after(0, lambda c=cmd: self.log_viewer.log_error(f"  {c.command}"))
                return

            self.after(0, lambda: self.log_viewer.log_success("Baseline verification passed"))

            # Setup Claude driver
            # Path: views/progress_view.py -> gui -> refactor_bot -> project root
            project_root = Path(__file__).parent.parent.parent.parent
            prompts_dir = project_root / "prompts"
            schemas_dir = project_root / "schemas"
            debug_log(f"Prompts dir: {prompts_dir}", "debug")
            debug_log(f"Schemas dir: {schemas_dir}", "debug")

            claude_config = config.claude
            claude_config.binary = app_state.get_claude_binary()

            # Wire up debug logging and activity callback to Claude driver
            from refactor_bot.claude_driver import set_debug_logger, set_activity_callback
            set_debug_logger(debug_log)

            # Activity callback updates the UI during long Claude calls
            def on_activity(message: str, elapsed: float):
                self.after(0, lambda: self.activity_display.update_activity(message, elapsed))

            set_activity_callback(on_activity)

            claude_driver = ClaudeDriver(
                config=claude_config,
                prompts_dir=prompts_dir,
                schemas_dir=schemas_dir,
                working_dir=worktree_path,
            )
            debug_log(f"Claude driver initialized. Binary: {claude_config.binary}", "success")

            # Index
            self.after(0, lambda: self.log_viewer.log_info("Indexing codebase..."))
            symbols = SymbolExtractor(worktree_path, config.scope_excludes)
            symbols.index_files()
            deps = DependencyAnalyzer(worktree_path, config.scope_excludes)
            dep_graph = deps.analyze()

            # Setup ledger and context
            ledger_path = worktree_path / ".refactor-bot" / "TASK_LEDGER.jsonl"
            ledger = TaskLedger(ledger_path)

            context_builder = ContextPackBuilder(
                repo_path=worktree_path,
                config=config,
                symbols=symbols,
                deps=dep_graph,
                ledger=ledger,
            )

            # Process batches
            completed = 0
            failed = 0
            total = len(plan.batches)

            for i, batch in enumerate(plan.batches):
                if self._should_stop:
                    self.after(0, lambda: self.log_viewer.log_warning("Stopped by user"))
                    break

                while self._is_paused:
                    time.sleep(0.5)
                    if self._should_stop:
                        break

                # Update UI
                self.after(0, lambda i=i, b=batch: self._update_progress(i, total, b))
                self.after(0, lambda b=batch: self.log_viewer.log_info(f"Processing {b.id}: {b.goal}"))

                # Show activity display for this batch
                self.after(0, lambda b=batch: self.activity_display.start_batch(b.id, b.goal))

                batch_start = time.time()

                # Build context - Stage 0
                self.after(0, lambda: self.activity_display.set_stage(0))
                debug_log(f"Building context for batch {batch.id}...", "debug")
                context = context_builder.build_patcher_context(batch)
                debug_log(f"Context built: {len(context)} chars", "debug")

                # Call Claude - Stage 1
                self.after(0, lambda: self.activity_display.set_stage(1))
                self.after(0, lambda: self.log_viewer.log_info("Calling Claude Code CLI..."))
                claude_binary = app_state.get_claude_binary()
                debug_log(f"Invoking Claude: {claude_binary}", "info")
                debug_log(f"  Batch goal: {batch.goal}", "debug")
                debug_log(f"  Scope: {batch.scope_globs}", "debug")

                response = claude_driver.call_patcher(context)

                debug_log(f"Claude response received. Success: {response.success}", "info")
                if response.raw_output:
                    debug_log(f"Raw output length: {len(response.raw_output)} chars", "debug")

                if not response.success:
                    failed += 1
                    debug_log(f"Claude error: {response.error_message}", "error")
                    self.after(0, lambda e=response.error_message: self.log_viewer.log_error(f"Claude error: {e}"))
                    self.after(0, lambda i=i: self.batch_indicators.set_status(i, "failed"))
                    self.after(0, lambda: self.activity_display.stop_batch())
                    continue

                output = response.structured_output
                status = output.get("status", "blocked")

                if status == "noop":
                    self.after(0, lambda: self.log_viewer.log_info("No changes needed"))
                    self.after(0, lambda i=i: self.batch_indicators.set_status(i, "skipped"))
                    self.after(0, lambda: self.activity_display.stop_batch())
                    self.after(0, lambda i=i, b=batch: self._update_progress(i, total, b, completed=True))
                    completed += 1
                    continue

                if status == "blocked":
                    self.after(0, lambda r=output.get("rationale", ""): self.log_viewer.log_warning(f"Blocked: {r}"))
                    self.after(0, lambda i=i: self.batch_indicators.set_status(i, "skipped"))
                    self.after(0, lambda: self.activity_display.stop_batch())
                    self.after(0, lambda i=i, b=batch: self._update_progress(i, total, b, completed=True))
                    continue

                # Apply patch - Stage 2
                self.after(0, lambda: self.activity_display.set_stage(2))
                patch_diff = output.get("patch_unified_diff", "")
                if patch_diff:
                    self.after(0, lambda d=patch_diff: self.diff_viewer.set_diff(d))

                    result = apply_patch(
                        worktree_path,
                        patch_diff,
                        batch.scope_globs,
                        batch.diff_budget_loc,
                    )

                    if not result.success:
                        failed += 1
                        self.after(0, lambda e=result.error_message: self.log_viewer.log_error(f"Patch failed: {e}"))
                        self.after(0, lambda i=i: self.batch_indicators.set_status(i, "failed"))
                        self.after(0, lambda: self.activity_display.stop_batch())
                        continue

                    # Verify - Stage 3
                    self.after(0, lambda: self.activity_display.set_stage(3))
                    self.after(0, lambda: self.log_viewer.log_info("Running verification..."))
                    verification = verifier.run_fast()

                    if not verification.passed:
                        failed += 1
                        self.after(0, lambda: self.log_viewer.log_error("Verification failed"))
                        repo_manager.revert_to_baseline()
                        self.after(0, lambda i=i: self.batch_indicators.set_status(i, "failed"))
                        self.after(0, lambda: self.activity_display.stop_batch())
                        continue

                    # Checkpoint
                    repo_manager.checkpoint_commit(batch.id, batch.goal)
                    completed += 1
                    self.after(0, lambda: self.log_viewer.log_success("Batch completed"))
                    self.after(0, lambda i=i: self.batch_indicators.set_status(i, "completed"))
                    self.after(0, lambda: self.activity_display.stop_batch())
                    self.after(0, lambda i=i, b=batch: self._update_progress(i, total, b, completed=True))

                # Update stats
                self.after(0, lambda c=completed, f=failed, r=total-i-1: self._update_stats(c, f, r))

            # Done
            self._is_running = False
            self.after(0, lambda c=completed, f=failed: self._show_completion(c, f, total))

        except Exception as e:
            self._is_running = False
            debug_error(e, "Refactoring process failed")
            self.after(0, lambda e=str(e): self.log_viewer.log_error(f"Error: {e}"))
            self.after(0, lambda: self.current_batch_label.configure(text="Error - See Debug Console"))

    def _update_progress(self, current: int, total: int, batch, completed: bool = False) -> None:
        """Update progress display.

        Args:
            current: Current batch index (0-based)
            total: Total number of batches
            batch: Current batch object
            completed: If True, this batch just finished (show full progress)
        """
        if completed:
            # Batch finished - show progress including this batch
            progress = (current + 1) / total
        else:
            # Batch in progress - show progress up to but not including this batch
            progress = current / total
        self.overall_progress.set_progress(progress)
        self.batch_indicators.set_current(current)
        self.current_batch_label.configure(text=f"Batch {current + 1}/{total}: {batch.id}")
        self.current_goal_label.configure(text=batch.goal)

    def _update_stats(self, completed: int, failed: int, remaining: int) -> None:
        """Update statistics."""
        self.stat_completed.value_label.configure(text=str(completed))
        self.stat_failed.value_label.configure(text=str(failed))
        self.stat_remaining.value_label.configure(text=str(remaining))

    def _update_timer(self) -> None:
        """Update elapsed time display."""
        if self._is_running:
            elapsed = int(time.time() - self._start_time)
            mins = elapsed // 60
            secs = elapsed % 60
            self.stat_time.value_label.configure(text=f"{mins}:{secs:02d}")
            self.after(1000, self._update_timer)

    def _show_completion(self, completed: int, failed: int, total: int) -> None:
        """Show completion status."""
        if failed == 0:
            self.current_batch_label.configure(text="Refactoring Complete!")
            self.current_goal_label.configure(text=f"Successfully completed {completed}/{total} batches")
            self.log_viewer.log_success(f"Refactoring complete: {completed}/{total} batches")
        else:
            self.current_batch_label.configure(text="Refactoring Finished with Errors")
            self.current_goal_label.configure(text=f"Completed: {completed}, Failed: {failed}")
            self.log_viewer.log_warning(f"Finished with {failed} failures")

    def _toggle_pause(self) -> None:
        """Toggle pause state."""
        self._is_paused = not self._is_paused
        if self._is_paused:
            self.pause_btn.configure(text="Resume")
            self.log_viewer.log_info("Paused")
        else:
            self.pause_btn.configure(text="Pause")
            self.log_viewer.log_info("Resumed")

    def _stop_refactoring(self) -> None:
        """Stop the refactoring process."""
        self._should_stop = True
        self._is_paused = False
        self.log_viewer.log_warning("Stopping...")
