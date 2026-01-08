# Refactorio

Automated whole-repo refactoring orchestrator using Claude Code CLI.

Refactorio analyzes your codebase, generates a safe refactoring plan, and executes changes in isolated batches with automatic verification and rollback support.

## Features

- **Intelligent Planning**: Analyzes codebase structure, dependencies, and symbol usage to generate optimal refactoring batches
- **Claude-Powered**: Uses Claude Code CLI for both planning refinement and code generation
- **Safe Execution**: Git worktree isolation ensures your main repo is never modified until changes are verified
- **Automatic Backups**: Creates git bundles and tar.gz archives before any changes
- **Batch Processing**: Breaks large refactors into safe, verifiable chunks with risk scoring
- **Real-time Progress**: GUI shows live progress with stage indicators and elapsed time
- **Rollback Support**: One-click rollback to any previous state

## Supported Languages

- Python, JavaScript, TypeScript
- Rust, Go, Java, C/C++, C#
- GDScript (Godot), including .tscn and .tres files
- Ruby, PHP, Lua, Swift, Kotlin
- Shell/Bash scripts

## Installation

```bash
# Clone the repository
git clone https://github.com/GTWhalley/Refactorio.git
cd Refactorio

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

### Requirements

- Python 3.10+
- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- Git

## Usage

### GUI (Recommended)

```bash
# Launch the GUI
python -m refactor_bot.cli gui

# Or on macOS, double-click Refactorio.command
```

### CLI

```bash
# Generate a refactoring plan
refactorio plan /path/to/repo

# Run refactoring with the plan
refactorio run /path/to/repo

# Verify changes without applying
refactorio verify /path/to/repo

# Rollback to a previous state
refactorio rollback /path/to/repo --backup-id <id>

# List available backups
refactorio list-backups /path/to/repo
```

## How It Works

1. **Index**: Scans your codebase to extract symbols (classes, functions, variables) and analyze dependencies
2. **Plan**: Generates a naive refactoring plan using heuristics, optionally refined by Claude
3. **Isolate**: Creates a git worktree for safe, isolated changes
4. **Execute**: Processes batches one at a time, calling Claude to generate patches
5. **Verify**: Runs your test suite and linters after each batch
6. **Commit**: Creates checkpoint commits for successful batches
7. **Merge**: Once complete, changes can be merged back to your main branch

## Configuration

Create a `.refactor-bot.yaml` in your repo root:

```yaml
# Scope excludes (glob patterns)
scope_excludes:
  - "**/dist/**"
  - "**/build/**"
  - "**/.venv/**"
  - "**/node_modules/**"

# Verification commands
verifier_fast:
  - "npm test"
verifier_full:
  - "npm run lint"
  - "npm test"

# Batch limits
max_batches: 20
diff_budget_loc: 300

# Claude settings
claude:
  binary: "claude"  # or full path
  max_turns_patcher: 10
  max_turns_planner: 6
```

## GUI Overview

- **Dashboard**: Quick status overview and actions
- **Repository**: Select and configure target repository
- **Configuration**: Set verifier commands and batch limits
- **Plan**: View and edit the generated refactoring plan
- **Progress**: Real-time visualization during refactoring
- **History**: Browse past runs and rollback if needed
- **Settings**: Configure Claude Code CLI path and connection

## Architecture

```
refactor_bot/
├── cli.py              # CLI entry point
├── config.py           # Configuration management
├── claude_driver.py    # Claude Code CLI integration
├── planner.py          # Refactoring plan generation
├── context_pack.py     # Context building for Claude
├── patch_apply.py      # Unified diff application
├── verifier.py         # Test/lint verification
├── backup.py           # Backup management
├── repo_manager.py     # Git worktree management
├── ledger.py           # Task tracking
├── indexer/
│   ├── symbols.py      # Symbol extraction
│   └── deps.py         # Dependency analysis
└── gui/
    ├── app.py          # Main GUI application
    ├── theme.py        # Dark theme configuration
    ├── state.py        # Application state management
    ├── views/          # GUI screens
    └── components/     # Reusable UI components
```

## Development

This project was developed with assistance from [Claude Code](https://claude.ai/code), Anthropic's AI coding assistant. The architecture, implementation, and iterative debugging were done collaboratively between the author and Claude Code over multiple sessions.

## License

MIT
