"""
CLI commands for Refactorio.

Provides the main command-line interface using Typer and Rich.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text
from rich import box

from refactor_bot import __version__
from refactor_bot.config import Config, ensure_directories
from refactor_bot.repo_manager import RepoManager
from refactor_bot.backup import BackupManager
from refactor_bot.verifier import Verifier, VerifierLevel
from refactor_bot.indexer import SymbolExtractor, DependencyAnalyzer
from refactor_bot.claude_driver import ClaudeDriver, check_claude_ready, AgentRole
from refactor_bot.planner import Planner, RefactorPlan
from refactor_bot.context_pack import ContextPackBuilder
from refactor_bot.patch_apply import apply_patch
from refactor_bot.ledger import TaskLedger, BatchStatus
from refactor_bot.report import ReportGenerator

app = typer.Typer(
    name="refactorio",
    help="Automated whole-repo refactoring orchestrator using Claude Code CLI",
    add_completion=False,
)

console = Console()


def print_header():
    """Print the application header."""
    header = Text()
    header.append("╭─────────────────────────────────────────────────────────────╮\n", style="cyan")
    header.append("│  ", style="cyan")
    header.append("REFACTORIO", style="bold cyan")
    header.append("                                      ", style="cyan")
    header.append(f"v{__version__}", style="dim cyan")
    header.append("  │\n", style="cyan")
    header.append("╰─────────────────────────────────────────────────────────────╯", style="cyan")
    console.print(header)
    console.print()


def print_error(message: str):
    """Print an error message."""
    console.print(f"[bold red]Error:[/] {message}")


def print_success(message: str):
    """Print a success message."""
    console.print(f"[bold green]✓[/] {message}")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[bold yellow]⚠[/] {message}")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[bold blue]ℹ[/] {message}")


def risk_badge(score: int) -> str:
    """Get a colored risk badge for a score."""
    if score <= 30:
        return f"[green]●[/] Low ({score})"
    elif score <= 60:
        return f"[yellow]●[/] Medium ({score})"
    else:
        return f"[red]●[/] High ({score})"


@app.command()
def run(
    repo_path: Path = typer.Argument(
        ...,
        help="Path to the repository to refactor",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file",
    ),
    skip_backup: bool = typer.Option(
        False,
        "--skip-backup",
        help="Skip creating backup (not recommended)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Generate plan but don't apply changes",
    ),
    max_batches: Optional[int] = typer.Option(
        None,
        "--max-batches",
        help="Override maximum number of batches",
    ),
):
    """
    Run automated refactoring on a repository.

    This command will:
    1. Create a backup and safety branch
    2. Run baseline verification
    3. Build an index of the codebase
    4. Generate a refactoring plan
    5. Execute batches with verification after each
    6. Present a final report for acceptance
    """
    print_header()
    started_at = datetime.now()

    # Ensure directories exist
    ensure_directories()

    # Load configuration
    if config_path and config_path.exists():
        config = Config.model_validate_json(config_path.read_text())
    else:
        config = Config.load_or_create(repo_path)
        config = config.detect_verifiers(repo_path)

    if max_batches:
        config.max_batches = max_batches

    console.print(f"Repository: [cyan]{repo_path}[/]")
    console.print()

    # Step 1: Check Claude Code
    console.print("[bold]Step 1/6:[/] Checking Claude Code...", end=" ")
    ready, message = check_claude_ready()
    if not ready:
        console.print("[red]FAILED[/]")
        print_error(message)
        raise typer.Exit(1)
    console.print("[green]OK[/]")

    # Step 2: Validate repository and create backup
    console.print("[bold]Step 2/6:[/] Setting up repository...")

    repo_manager = RepoManager(repo_path)
    is_valid, errors = repo_manager.validate()

    if errors:
        for error in errors:
            print_warning(error)

    if not is_valid:
        print_error("Repository validation failed. Cannot proceed.")
        raise typer.Exit(1)

    info = repo_manager.get_info()
    console.print(f"  Repository: [cyan]{info.name}[/]")
    console.print(f"  Files: {info.file_count}")
    if info.is_git:
        console.print(f"  Branch: {info.current_branch}")
        console.print(f"  Commit: {info.commit_hash}")

    # Create backup
    if not skip_backup:
        with console.status("Creating backup..."):
            backup_manager = BackupManager(repo_path, repo_manager.run_id)
            backup_info = backup_manager.create_backup()
        print_success(f"Backup created: {backup_info.backup_path}")
    else:
        backup_info = None
        print_warning("Backup skipped (--skip-backup)")

    # Create worktree
    with console.status("Creating worktree..."):
        worktree_path = repo_manager.create_worktree()
    print_success(f"Worktree: {worktree_path}")

    # Step 3: Run baseline verification
    console.print()
    console.print("[bold]Step 3/6:[/] Running baseline verification...")

    verifier = Verifier(worktree_path, config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running verifiers...", total=None)
        baseline = verifier.run_baseline()
        progress.remove_task(task)

    if baseline.passed:
        print_success("Baseline verification passed")
        for cmd in baseline.commands:
            console.print(f"  {cmd.summary()}")
    else:
        print_error("Baseline verification failed")
        for cmd in baseline.failed_commands:
            console.print(f"  [red]{cmd.summary()}[/]")
            if cmd.stderr:
                console.print(f"    [dim]{cmd.stderr[:200]}...[/]")
        print_error("Cannot proceed with failing baseline. Fix issues and retry.")
        repo_manager.cleanup_worktree()
        raise typer.Exit(1)

    # Step 4: Build index
    console.print()
    console.print("[bold]Step 4/6:[/] Building codebase index...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Index symbols
        task = progress.add_task("Extracting symbols...", total=None)
        symbol_extractor = SymbolExtractor(worktree_path, config.scope_excludes)
        symbol_extractor.index_files()
        progress.remove_task(task)

        # Analyze dependencies
        task = progress.add_task("Analyzing dependencies...", total=None)
        dep_analyzer = DependencyAnalyzer(worktree_path, config.scope_excludes)
        dep_graph = dep_analyzer.analyze()
        progress.remove_task(task)

    print_success(f"Indexed {len(symbol_extractor.files)} files, {len(symbol_extractor.symbols)} symbols")

    # Save index artifacts
    index_dir = worktree_path / ".refactor-bot"
    index_dir.mkdir(exist_ok=True)
    symbol_extractor.save_registry(index_dir)
    dep_graph.save(index_dir / "DEPENDENCY_GRAPH.json")

    # Step 5: Generate plan
    console.print()
    console.print("[bold]Step 5/6:[/] Generating refactoring plan...")

    planner = Planner(
        worktree_path,
        config,
        symbol_extractor=symbol_extractor,
        dependency_graph=dep_graph,
    )

    plan = planner.generate_naive_plan()
    print_success(f"Generated {len(plan.batches)} batches")

    # Display plan
    console.print()
    plan_table = Table(
        title="Refactoring Plan",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    plan_table.add_column("#", justify="right", style="dim", width=4)
    plan_table.add_column("Goal", style="white", min_width=40)
    plan_table.add_column("Risk", justify="center", width=15)
    plan_table.add_column("LOC", justify="right", width=6)
    plan_table.add_column("Verifier", justify="center", width=8)

    for i, batch in enumerate(plan.batches[:20], 1):
        plan_table.add_row(
            str(i),
            batch.goal[:50] + ("..." if len(batch.goal) > 50 else ""),
            risk_badge(batch.risk_score),
            str(batch.diff_budget_loc),
            batch.verifier_level.value,
        )

    if len(plan.batches) > 20:
        plan_table.add_row("...", f"... and {len(plan.batches) - 20} more batches", "", "", "")

    console.print(plan_table)
    console.print()
    console.print(f"Total estimated changes: ~{plan.total_estimated_loc} lines")
    console.print()

    if dry_run:
        print_info("Dry run - no changes will be applied")
        plan.save(worktree_path / ".refactor-bot" / "plan.json")
        print_success(f"Plan saved to {worktree_path / '.refactor-bot' / 'plan.json'}")
        repo_manager.cleanup_worktree()
        raise typer.Exit(0)

    # Confirm before proceeding
    if not Confirm.ask("Proceed with refactoring?", default=False):
        print_info("Aborted by user")
        repo_manager.cleanup_worktree()
        raise typer.Exit(0)

    # Step 6: Execute batches
    console.print()
    console.print("[bold]Step 6/6:[/] Executing refactoring batches...")
    console.print()

    # Initialize components
    prompts_dir = Path(__file__).parent.parent / "prompts"
    schemas_dir = Path(__file__).parent.parent / "schemas"

    claude_driver = ClaudeDriver(
        config=config.claude,
        prompts_dir=prompts_dir,
        schemas_dir=schemas_dir,
        working_dir=worktree_path,
    )

    ledger_path = worktree_path / ".refactor-bot" / "TASK_LEDGER.jsonl"
    ledger = TaskLedger(ledger_path)

    context_builder = ContextPackBuilder(
        repo_path=worktree_path,
        config=config,
        symbols=symbol_extractor,
        deps=dep_graph,
        ledger=ledger,
    )

    # Execute batches
    completed_batches = []
    failed_batches = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing batches...", total=len(plan.batches))

        for batch in plan.batches:
            progress.update(task, description=f"Batch {batch.id}: {batch.goal[:40]}...")

            batch_start = time.time()
            ledger.record_start(batch.id, batch.goal)

            # Build context
            context = context_builder.build_patcher_context(
                batch=batch,
                previous_batches=completed_batches[-3:],
            )

            # Call Claude
            response = claude_driver.call_patcher(context)

            if not response.success:
                ledger.record_failure(
                    batch.id,
                    batch.goal,
                    response.error_message or "Unknown error",
                    time.time() - batch_start,
                )
                failed_batches.append(batch)
                batch.status = "failed"
                progress.advance(task)
                continue

            output = response.structured_output
            status = output.get("status", "blocked")

            if status == "noop":
                ledger.record_noop(batch.id, batch.goal, output.get("rationale", ""))
                batch.status = "noop"
                progress.advance(task)
                continue

            if status == "blocked":
                ledger.record_skipped(batch.id, batch.goal, output.get("rationale", ""))
                batch.status = "skipped"
                progress.advance(task)
                continue

            # Apply patch
            patch_diff = output.get("patch_unified_diff", "")
            if not patch_diff:
                ledger.record_noop(batch.id, batch.goal, "Empty patch")
                batch.status = "noop"
                progress.advance(task)
                continue

            result = apply_patch(
                worktree_path,
                patch_diff,
                batch.scope_globs,
                batch.diff_budget_loc,
            )

            if not result.success:
                ledger.record_failure(
                    batch.id,
                    batch.goal,
                    result.error_message or "Patch application failed",
                    time.time() - batch_start,
                )
                failed_batches.append(batch)
                batch.status = "failed"
                progress.advance(task)
                continue

            # Run verification
            verify_level = VerifierLevel(batch.verifier_level.value)
            verification = verifier.run_level(verify_level)

            if not verification.passed:
                # Revert and record failure
                repo_manager.revert_to_baseline()
                ledger.record_failure(
                    batch.id,
                    batch.goal,
                    "Verification failed after patch",
                    time.time() - batch_start,
                )
                failed_batches.append(batch)
                batch.status = "failed"
                progress.advance(task)
                continue

            # Checkpoint
            checkpoint = repo_manager.checkpoint_commit(batch.id, batch.goal)

            ledger.record_success(
                batch.id,
                batch.goal,
                result.stats.files_touched if result.stats else [],
                result.stats.lines_added if result.stats else 0,
                result.stats.lines_removed if result.stats else 0,
                checkpoint,
                time.time() - batch_start,
            )

            completed_batches.append(batch)
            batch.status = "completed"
            progress.advance(task)

    # Generate report
    console.print()

    report_generator = ReportGenerator(
        run_id=repo_manager.run_id,
        repo_path=repo_path,
        ledger=ledger,
        plan=plan,
    )

    report = report_generator.generate(
        started_at=started_at,
        backup_path=backup_info.backup_path if backup_info else Path(),
        worktree_path=worktree_path,
        final_commit=ledger.get_last_checkpoint(),
    )

    console.print(report_generator.format_terminal_report(report))

    # Save report
    report_path = worktree_path / ".refactor-bot" / "report.json"
    report.save(report_path)

    # Final acceptance
    if report.success and completed_batches:
        console.print()
        if Confirm.ask("Accept changes and merge to main repository?", default=True):
            try:
                repo_manager.merge_to_main()
                print_success("Changes merged successfully!")
            except Exception as e:
                print_error(f"Failed to merge: {e}")
                print_info(f"Changes are still available in: {worktree_path}")
        else:
            print_info("Changes not merged.")
            print_info(f"Worktree preserved at: {worktree_path}")
            print_info(f"Backup available at: {backup_info.backup_path if backup_info else 'N/A'}")
    elif failed_batches:
        print_warning(f"{len(failed_batches)} batches failed")
        print_info(f"Review the report and ledger at: {worktree_path / '.refactor-bot'}")

    console.print()


@app.command()
def plan(
    repo_path: Path = typer.Argument(
        ...,
        help="Path to the repository to analyze",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Path to save the plan (JSON)",
    ),
):
    """
    Generate a refactoring plan without applying changes.

    Useful for previewing what refactor-bot would do.
    """
    print_header()

    console.print(f"Analyzing: [cyan]{repo_path}[/]")
    console.print()

    config = Config.load_or_create(repo_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing codebase...", total=None)
        symbol_extractor = SymbolExtractor(repo_path, config.scope_excludes)
        symbol_extractor.index_files()
        progress.update(task, description="Analyzing dependencies...")
        dep_analyzer = DependencyAnalyzer(repo_path, config.scope_excludes)
        dep_graph = dep_analyzer.analyze()
        progress.remove_task(task)

    print_success(f"Indexed {len(symbol_extractor.files)} files")

    planner = Planner(repo_path, config, symbol_extractor, dep_graph)
    plan = planner.generate_naive_plan()

    # Display plan
    plan_table = Table(
        title="Refactoring Plan",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    plan_table.add_column("#", justify="right", style="dim", width=4)
    plan_table.add_column("Goal", style="white", min_width=40)
    plan_table.add_column("Risk", justify="center", width=15)
    plan_table.add_column("LOC", justify="right", width=6)

    for i, batch in enumerate(plan.batches, 1):
        plan_table.add_row(
            str(i),
            batch.goal,
            risk_badge(batch.risk_score),
            str(batch.diff_budget_loc),
        )

    console.print()
    console.print(plan_table)
    console.print()
    console.print(f"Total batches: {len(plan.batches)}")
    console.print(f"Estimated changes: ~{plan.total_estimated_loc} lines")

    if output:
        plan.save(output)
        print_success(f"Plan saved to: {output}")


@app.command()
def verify(
    repo_path: Path = typer.Argument(
        ...,
        help="Path to the repository to verify",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Run full verification (not just fast)",
    ),
):
    """
    Run verification commands on a repository.

    Useful for testing that the baseline passes before refactoring.
    """
    print_header()

    console.print(f"Verifying: [cyan]{repo_path}[/]")
    console.print()

    config = Config.load_or_create(repo_path)
    config = config.detect_verifiers(repo_path)

    level = VerifierLevel.FULL if full else VerifierLevel.FAST
    console.print(f"Running [cyan]{level.value}[/] verification...")
    console.print()

    verifier = Verifier(repo_path, config)
    result = verifier.run_level(level)

    for cmd in result.commands:
        if cmd.passed:
            console.print(f"  [green]✓[/] {cmd.command} ({cmd.duration_seconds:.1f}s)")
        else:
            console.print(f"  [red]✗[/] {cmd.command} ({cmd.duration_seconds:.1f}s)")
            if cmd.stderr:
                console.print(f"    [dim]{cmd.stderr[:200]}[/]")

    console.print()
    if result.passed:
        print_success(f"All {len(result.commands)} checks passed")
    else:
        print_error(f"{len(result.failed_commands)} checks failed")
        raise typer.Exit(1)


@app.command()
def rollback(
    run_id: str = typer.Argument(
        ...,
        help="Run ID to rollback to",
    ),
    use_archive: bool = typer.Option(
        False,
        "--archive",
        help="Use tar.gz archive instead of git bundle",
    ),
):
    """
    Rollback a repository to a previous backup.

    Use 'refactor-bot list-backups' to see available backups.
    """
    print_header()

    from refactor_bot.backup import rollback as do_rollback

    console.print(f"Rolling back to: [cyan]{run_id}[/]")

    try:
        restored_path = do_rollback(run_id, use_bundle=not use_archive)
        print_success(f"Restored to: {restored_path}")
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Rollback failed: {e}")
        raise typer.Exit(1)


@app.command(name="list-backups")
def list_backups(
    repo_name: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Filter by repository name",
    ),
):
    """
    List available backups.
    """
    print_header()

    backups = BackupManager.list_backups(repo_name)

    if not backups:
        print_info("No backups found")
        return

    table = Table(
        title="Available Backups",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Run ID", style="cyan")
    table.add_column("Repository", style="white")
    table.add_column("Created", style="dim")
    table.add_column("Size", justify="right")

    from refactor_bot.util import format_size

    for backup in backups:
        table.add_row(
            backup.run_id,
            backup.repo_name,
            backup.created_at.strftime("%Y-%m-%d %H:%M"),
            format_size(backup.size_bytes),
        )

    console.print(table)


@app.command()
def version():
    """Show version information."""
    console.print(f"Refactorio version {__version__}")


@app.command()
def gui():
    """
    Launch the graphical user interface.

    Opens the Refactorio GUI with visual controls for:
    - Claude configuration and authentication
    - Repository selection and browsing
    - Refactoring configuration
    - Plan editing and visualization
    - Real-time progress monitoring
    - Diff viewing with syntax highlighting
    - History and rollback management
    """
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print_error("GUI dependencies not installed.")
        print_info("Install with: pip install customtkinter")
        raise typer.Exit(1)

    from refactor_bot.gui import RefactorBotApp

    print_info("Launching GUI...")
    app_gui = RefactorBotApp()
    app_gui.mainloop()


if __name__ == "__main__":
    app()
