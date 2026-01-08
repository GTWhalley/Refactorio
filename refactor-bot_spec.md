# Refactorio — Technical Specification

An automated whole-repo refactoring orchestrator using Claude Code CLI.

**Core UX:**
**Select directory → Refactor → Confirm**

The tool runs unattended after confirmation, performing safe, verifiable, incremental refactors with automatic rollback on failure.

---

## 1) Claude Code CLI Integration

This design assumes Claude Code is installed and the user is authenticated. No API keys required—authentication is handled by the Claude Code CLI.

The orchestrator invokes the local `claude` binary in headless mode:

- `claude -p "..."` (non-interactive)
- `--output-format json`
- `--json-schema '{...}'` for validated structured outputs
- `--system-prompt-file <file>` for deterministic, versioned prompting
- `--allowedTools "..."` for non-interactive tool approval
- `--max-turns N` to cap cost and prevent runaway loops

Claude Code stores auth and preferences locally (typically `~/.claude.json`), with project-level settings in `.claude/settings.json`.

---

## 2) Core Functionality

The program:

1. Takes a target repo directory
2. Creates a full revertable backup (git safety branch/worktree)
3. Builds an index of the codebase (symbols, dependencies, hotspots)
4. Generates an ordered refactor plan (small atomic batches)
5. For each batch:
   - Builds a small context packet (avoids full-repo context)
   - Calls Claude Code CLI to produce a patch as validated JSON
   - Applies patch with strict constraints
   - Runs verifiers (tests/typecheck/lint)
   - Creates checkpoint commits and updates memory artifacts
6. Produces a final report; user confirms to accept/merge or revert

---

## 3) Operating Principles

### 3.1 Stateless Sessions
Each batch is a fresh `claude -p` call with a new session ID. No reliance on conversation memory.

### 3.2 Deterministic Verification
Acceptance is based on deterministic checks (tests, typecheck, lint). Verification failure triggers revert.

### 3.3 Small Diffs, Frequent Checkpoints
Refactoring proceeds in tiny, atomic batches. Large changes are blocked unless explicitly configured.

### 3.4 Safe Defaults
When uncertain, return `status: "noop"` rather than risk breaking changes.

---

## 4) Supported Platforms

- macOS / Linux / WSL (primary)
- Windows (secondary; WSL recommended)

---

## 5) Claude Code Prerequisites

### 5.1 Installation & Authentication
Assumes `claude` is on PATH and authenticated. If not authenticated, fail early with instructions to run `claude` interactively and use `/login`.

### 5.2 Headless Mode
All interactions via `claude -p "<prompt>" ...`

### 5.3 Structured Output
Uses `--output-format json` and `--json-schema '<schema>'`. Response JSON contains a `structured_output` field with validated data.

### 5.4 Tool Permissions
Passes `--allowedTools "Read,Edit,Bash,Grep,Glob"` to avoid interactive prompts.

### 5.5 Versioned Prompts
All prompts loaded from versioned files (`./prompts/*.txt`) via `--system-prompt-file`.

---

## 6) Implementation

### 6.1 Language
Python 3.11+ recommended for subprocess control, JSON schema validation, cross-platform CLI packaging, and git integration.

### 6.2 CLI Framework
`typer` or `click` for CLI; `rich` for TUI-style output.

### 6.3 Packaging
Package as `refactor-bot` CLI. Support `pipx install .` and `python -m refactor_bot ...`.

---

## 7) User Workflow

### 7.1 CLI Commands
- `refactor-bot run <repo_path>` — full refactor run
- `refactor-bot plan <repo_path>` — plan only, no changes
- `refactor-bot verify <repo_path>` — baseline verification only
- `refactor-bot rollback <run_id>` — restore from backup

### 7.2 UX Stages
1. Select directory (`run <repo>`)
2. Preflight + plan generation
3. User confirmation
4. Autonomous batch loop
5. Final report + accept/reject

---

## 8) Safety Model

### 8.1 Rollback Mechanisms

**Git safety branch + worktree:**
- For git repos: create branch `refactor-bot/<timestamp>`, temporary worktree in `~/.refactor-bot/worktrees/<run_id>/`, all edits in worktree only
- For non-git repos: initialize temporary git repo in worktree copy (never touch original)

**Full backup artifact:**
- Git repos: `git bundle create backup.bundle --all` + `tar.gz` snapshot
- Stored in `~/.refactor-bot/backups/<repo_name>/<run_id>/`

### 8.2 Checkpoints
After every passing batch: git commit (`checkpoint: batch-XYZ <goal>`), record hash in ledger.

### 8.3 Rollback Rules
On batch failure after `retry_per_batch` attempts:
- Reset to last passing checkpoint
- Mark batch as failed
- Stop run, produce report
- Offer rollback to baseline on reject

---

## 9) Verification System

### 9.1 Baseline Verification
Must pass before any changes. Configurable commands:
- Build (optional)
- Unit tests (required)
- Typecheck (recommended)
- Lint (recommended)
- Integration tests (optional)
- Benchmarks (optional)

Records: command strings, exit codes, elapsed time, stdout/stderr, environment info.

### 9.2 Per-Batch Verification
- **Fast verifier** after each patch: unit tests + lint
- **Full verifier** every N batches: full test suite + typecheck + integration tests

### 9.3 Contract Snapshots (Optional)
Snapshot and compare: public exports, routes/endpoints, schema formats, CLI flags. Fail batch if contracts change without explicit allowance.

---

## 10) Indexing & Project Memory

### 10.1 Purpose
Avoids putting entire repos into context. Builds local index, retrieves small slices per batch.

### 10.2 Index Artifacts
Stored in `.refactor-bot/`:
- `ARCHITECTURE_SNAPSHOT.md`
- `SYMBOL_REGISTRY.json`
- `DEPENDENCY_GRAPH.json`
- `CALL_GRAPH.json` (best-effort)
- `RISK_REGISTER.json`
- `TASK_LEDGER.jsonl`
- `CONTRACTS/public_api_snapshot.json`

### 10.3 Indexer Implementation
**Minimum:** file tree + hashes, ripgrep-based symbol extraction

**Better:** Tree-sitter for accurate cross-language symbols, import graph extraction

---

## 11) Planner

### 11.1 Batch Structure
Each atomic refactor batch includes:
- `id`, `goal`, `scope_globs`
- `allowed_operations`
- `diff_budget_loc`, `risk_score`
- `required_verifier` (fast/full)
- `notes`

### 11.2 Ordering Policy (Risk-Limiting)
1. Formatting-only pass (optional, first)
2. Import cleanup / dead-code removal
3. Renames / small extracts / module splits
4. Add/strengthen tests
5. Larger internal restructures
6. Big transforms last (async refactor, architecture shifts)

### 11.3 Plan Generation
Program generates naive plan via heuristics; Claude refines within constraints (cannot invent unbounded tasks).

---

## 12) Agent Roles

### 12.1 Role Types
- **Planner**: proposes/refines batch list (no code changes)
- **Patcher**: outputs a patch for exactly one batch
- **Critic** (optional): reviews patch before apply; can request shrink scope/diff or noop

### 12.2 Session Strategy
Each call passes:
- `--session-id <uuid>` (new per call)
- `--max-turns <N>` (e.g., 6–12 for patcher)

Avoid `--continue` in automated mode.

---

## 13) Context Pack Builder

### 13.1 Budgets
Enforce limits in lines and bytes:
- Max prompt body: ~40k chars
- Max file excerpts: ~600 lines
- Max ledger tail: 10 entries, 8 lines each

### 13.2 Retrieval Policy
For each batch scope, include:
- Recently touched in-scope files
- Highest fan-in symbols
- Import-referenced files
- Only signatures, docstrings, and small excerpts (not full files unless tiny)

### 13.3 Deterministic Summaries
Program generates: candidate file lists, symbol summaries (signature + location), recent batch summaries from ledger.

---

## 14) Claude Code Invocation

### 14.1 Command Pattern
Each role has a system prompt file (`prompts/planner.system.txt`, `prompts/patcher.system.txt`, etc.).

Invocation:
```
claude -p "<PROMPT>" --output-format json --json-schema '<schema>' \
  --system-prompt-file <file> --allowedTools "..." --session-id <uuid> --max-turns <n>
```

### 14.2 Response Parsing
Parse stdout as JSON, read `structured_output` field, validate locally (defense-in-depth).

---

## 15) JSON Schemas

### 15.1 PlannerResponse
```json
{
  "type": "object",
  "properties": {
    "batches": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "goal": { "type": "string" },
          "scope_globs": { "type": "array", "items": { "type": "string" } },
          "allowed_operations": { "type": "array", "items": { "type": "string" } },
          "diff_budget_loc": { "type": "integer" },
          "risk_score": { "type": "integer", "minimum": 0, "maximum": 100 },
          "verifier_level": { "type": "string", "enum": ["fast", "full"] },
          "notes": { "type": "string" }
        },
        "required": ["id", "goal", "scope_globs", "allowed_operations", "diff_budget_loc", "risk_score", "verifier_level"]
      }
    }
  },
  "required": ["batches"]
}
```

### 15.2 PatchResponse
```json
{
  "type": "object",
  "properties": {
    "status": { "type": "string", "enum": ["ok", "noop", "blocked"] },
    "rationale": { "type": "string" },
    "risk_notes": { "type": "array", "items": { "type": "string" } },
    "patch_unified_diff": { "type": "string" },
    "touched_files": { "type": "array", "items": { "type": "string" } },
    "expected_verifier": { "type": "array", "items": { "type": "string" } },
    "followups": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["status", "rationale", "risk_notes", "patch_unified_diff", "touched_files", "expected_verifier"]
}
```

### 15.3 CriticResponse (Optional)
```json
{
  "type": "object",
  "properties": {
    "decision": { "type": "string", "enum": ["accept", "reject", "shrink_scope", "shrink_diff", "noop"] },
    "reasons": { "type": "array", "items": { "type": "string" } },
    "suggested_constraints": { "type": "object" }
  },
  "required": ["decision", "reasons"]
}
```

---

## 16) System Prompts

### 16.1 Patcher Prompt Requirements
- Output schema-validated JSON only
- Patch as unified diff
- Never touch files outside scope
- Preserve behavior and public contracts
- Stay within diff budget
- Return `noop` when uncertain
- Don't modify lockfiles unless allowed
- Don't reformat entire repo unless instructed

### 16.2 Planner Prompt Requirements
- Propose small batches with clear scope/goal
- Order by risk-limiting policy
- Cap total batches (default 200)
- Avoid large structural changes unless safety net is strong

### 16.3 Project Context
Optionally use `CLAUDE.md` or `.refactor-bot/CLAUDE_CONTEXT.md` for repo-specific conventions (test commands, style, dangerous areas). Don't rely on it for automation correctness—explicit prompts and schemas take precedence.

---

## 17) Patch Application

### 17.1 Validation
Before applying:
- `touched_files` must be subset of scope allowlist
- Diff must apply cleanly (`git apply --check`)
- LOC touched must respect `diff_budget_loc`
- Reject binary changes unless allowed

### 17.2 Application
Use `git apply` (preferred), fallback to patch library if needed.

### 17.3 Formatting-Only Mode
For format-only batches: verify only formatting configs/files are touched, use formatter command (not manual edits).

---

## 18) Execution Loop

```
run(repo_path):
  preflight(repo_path)
  worktree = create_worktree_and_backup(repo_path)

  baseline = run_baseline_verifier(worktree)
  if baseline.fail: stop

  index = build_index(worktree)
  plan = build_plan(index)

  show_confirm_screen(plan, baseline, backup_path)
  if user_cancel: cleanup and exit

  for batch in plan.batches:
    context = build_context_packet(index, ledger, batch)
    patch_resp = call_patcher(context, batch)

    if patch_resp.status != "ok":
      record_ledger(batch, status=patch_resp.status)
      continue or stop depending on status

    if !validate_patch_constraints(patch_resp, batch):
      record failure; stop

    apply_patch(patch_resp)
    fast = run_fast_verifier()
    if fast.fail:
      revert_to_checkpoint()
      retry (up to retry_per_batch)
      if still fail: stop

    checkpoint_commit()
    update_index_if_needed()
    append_ledger()

    if batch_index % N == 0:
      full = run_full_verifier()
      if full.fail: stop

  final_full = run_full_verifier()
  generate_final_report()
  wait_for_user_accept_or_reject()
```

---

## 19) Stop Conditions

Stop immediately if:
- Baseline verifier fails
- Claude Code not installed or not authenticated
- Patch violates scope/diff budget and cannot be regenerated
- Verifier fails repeatedly
- Contract snapshot shows disallowed breaking changes
- Max runtime exceeded (optional)

---

## 20) Configuration

`.refactor-bot.config.json` in worktree root:

```json
{
  "diff_budget_loc": 300,
  "max_batches": 200,
  "retry_per_batch": 2,
  "run_full_verifier_every": 5,
  "fast_verifier": ["npm test"],
  "full_verifier": ["npm test", "npm run typecheck"],
  "scope_excludes": ["**/dist/**", "**/build/**", "**/.venv/**", "**/node_modules/**"],
  "allow_public_api_changes": false,
  "claude": {
    "binary": "claude",
    "allowed_tools": "Read,Edit,Bash,Grep,Glob",
    "tools": "Read,Edit,Bash,Grep,Glob",
    "max_turns_patcher": 10,
    "max_turns_planner": 6
  }
}
```

---

## 21) Claude Code Integration Details

### 21.1 Binary Discovery
Check `claude -v` works. If not found, prompt to install/repair.

### 21.2 Authentication Check
Run trivial headless query: `claude -p "Respond with OK" --output-format json`
On auth failure, exit with instructions to run interactive login.

### 21.3 Schema Outputs
Always use `--json-schema`. On validation failure, retry once; if still fails, stop.

### 21.4 Session Isolation
Always pass random UUID via `--session-id`. Never use `--continue` by default.

---

## 22) Repository Layout

```
refactor-bot/
  refactor_bot/
    __init__.py
    cli.py
    config.py
    repo_manager.py
    backup.py
    verifier.py
    indexer/
      __init__.py
      symbols.py
      deps.py
      callgraph.py
    planner.py
    context_pack.py
    claude_driver.py
    patch_apply.py
    contracts.py
    report.py
    ledger.py
    util.py
  prompts/
    planner.system.txt
    patcher.system.txt
    critic.system.txt
  schemas/
    planner.schema.json
    patcher.schema.json
    critic.schema.json
  pyproject.toml
  README.md
```

---

## 23) Implementation Milestones

### Milestone 1 — MVP
- Worktree + backup + rollback
- Baseline verifier
- Simple indexer (file tree + ripgrep symbols)
- Single-batch patching
- Ledger + report

### Milestone 2 — Planning & Batching
- Plan generation with schema
- Context pack builder
- Batch loop with checkpoints

### Milestone 3 — Advanced Safety
- Public API snapshots
- Benchmark gates (optional)
- Critic review (optional)

---

## 24) Deliverables Checklist

- [ ] Run with `refactor-bot run <repo>`
- [ ] Create backup + git safety worktree
- [ ] Refuse to run if baseline verification fails
- [ ] Use `claude -p` with `--json-schema` for all agent calls
- [ ] Enforce scope + diff budgets
- [ ] Verify after every batch, rollback on failure
- [ ] Produce final report and wait for user accept/reject

---

## 25) Design Notes

- Treat each `claude -p` call as stateless (no conversation memory)
- Depend on structured outputs (`--json-schema`) for reliable parsing
- Prefer deterministic, mechanical transformations over logic rewrites
- Keep code modular; each subsystem should be independently testable