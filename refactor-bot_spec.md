# Automated Whole-Repo Refactoring Orchestrator (Claude Code CLI) — Build Spec

**Audience:** This document is meant to be handed to an LLM coding agent (Claude Code / Codex) to build the program described below.

**High-level UX goal:**  
**Select directory → Refactor → Confirm**  
After confirmation, the tool runs fully unattended, performing safe, verifiable, incremental refactors across the repo, with automatic rollback on failure.

---

## 0) What changes because we’re using Claude Code CLI (not an API)

This design assumes **Claude Code is installed and you are already logged in** (via your email account in Claude Code). The orchestrator **must not** require API keys.

The orchestrator integrates by invoking the local `claude` binary in **print/headless mode** using:

- `claude -p "..."` (non-interactive)
- `--output-format json`
- `--json-schema '{...}'` for validated structured outputs
- `--system-prompt-file <file>` for deterministic, versioned prompting
- `--allowedTools "..."` for non-interactive tool approval
- `--max-turns N` to cap cost and prevent runaway loops

Claude Code stores auth and preferences locally; typical state is stored in `~/.claude.json`, and project-level settings can live in `.claude/settings.json`.

---

## 1) Problem statement

Build a program that can:

1. Take a target repo directory.
2. Create a *full revertable backup* (and a git safety branch/worktree).
3. Build an **index** of the codebase (symbols, dependencies, hotspots).
4. Generate an ordered refactor plan (small atomic batches).
5. For each batch:
   - Build a **small context packet** (no full-repo dumping into prompts).
   - Call Claude Code CLI to produce a patch as validated JSON.
   - Apply patch with strict constraints.
   - Run verifiers (tests/typecheck/lint/etc.).
   - Checkpoint commits and update durable “memory” artifacts.
6. Produce a final report and wait for **one user confirmation** to accept/merge, otherwise revert.

---

## 2) Operating principles (non-negotiable)

### 2.1 The LLM is **stateless**
Do **not** rely on long-lived conversations. Each batch is a fresh `claude -p` call, with a new session ID.

### 2.2 Tools verify; the LLM proposes
Acceptance is based on deterministic checks (tests, typecheck, lint, etc.). If verification fails, revert.

### 2.3 Small diffs, fast verifiers, frequent checkpoints
Refactoring proceeds in tiny, atomic batches. Large changes are explicitly blocked unless configured.

### 2.4 “NOOP is success”
If uncertain, the LLM must return `status: "noop"` rather than risk breaking changes.

---

## 3) Supported platforms

- macOS / Linux / WSL (primary)
- Windows (secondary; recommend WSL)

---

## 4) Claude Code prerequisites (assumed by this tool)

### 4.1 Installation & login
The orchestrator assumes `claude` is on PATH and you are already authenticated.

**If not authenticated:** the tool should fail early with a friendly message:
> “Claude Code is not logged in. Run `claude` interactively and use `/login`, then rerun.”

### 4.2 Headless (print) mode is required
All LLM interactions are executed via:
- `claude -p "<prompt>" ...`

### 4.3 Structured output is required
The orchestrator **must** request validated structured outputs by using:
- `--output-format json`
- `--json-schema '<json schema>'`

The orchestrator reads the JSON response from stdout and extracts the `structured_output` field (when schema is used).

### 4.4 Permissions / tool use
To avoid interactive prompts during automation, the orchestrator passes:
- `--allowedTools "Read,Edit,Bash,Grep,Glob"`

Additionally, it should restrict tool exposure when appropriate:
- Prefer `--tools "Bash,Edit,Read,Grep,Glob"` (deny other tools by default)

### 4.5 Prompt determinism
All prompts must be loaded from versioned files in the orchestrator repo:
- `./prompts/*.txt`
The orchestrator passes:
- `--system-prompt-file ./prompts/<role>.system.txt`

---

## 5) Program structure (recommended: Python)

### 5.1 Language
Implement in **Python 3.11+** for:
- strong subprocess control (`subprocess.run`)
- JSON schema validation
- cross-platform CLI packaging
- easier filesystem + git integration

### 5.2 CLI framework
Use `typer` or `click`. Use `rich` for TUI-style output.

### 5.3 Packaging
- Package as `refactor-bot` CLI.
- Support `pipx install .` and `python -m refactor_bot ...`.

---

## 6) User-facing workflow

### 6.1 CLI commands (minimum)
- `refactor-bot run <repo_path>`
- `refactor-bot plan <repo_path>` (plan only; no changes)
- `refactor-bot verify <repo_path>` (baseline verification only)
- `refactor-bot rollback <run_id>` (restore from backup)

### 6.2 UX stages
1. **Select directory**: `run <repo>`
2. **Refactor** (dry-run preflight + plan generation)
3. **Confirm** (single checkpoint)
4. Autonomous batch loop
5. Final report + accept/reject

---

## 7) Safety model (backup + rollback)

### 7.1 Two rollback mechanisms (required)
1) **Git safety branch + worktree**
- If repo is git:
  - create branch `refactor-bot/<timestamp>`
  - create temporary worktree in `~/.refactor-bot/worktrees/<run_id>/`
  - perform all edits in the worktree only
- If repo is not git:
  - initialize a temporary git repo **in the worktree copy** (never touch original)

2) **Full backup artifact**
- Always create a backup archive:
  - If git repo: also create `git bundle create backup.bundle --all`
  - And/or `tar.gz` snapshot
- Store under:
  - `~/.refactor-bot/backups/<repo_name>/<run_id>/`

### 7.2 Checkpoints
After every passing batch:
- create a git commit (`checkpoint: batch-XYZ <goal>`)
- record commit hash in the ledger

### 7.3 Rollback rules
If a batch fails verification and cannot be fixed in `retry_per_batch` attempts:
- reset to last passing checkpoint commit
- mark batch as failed
- stop the run and produce a report
- offer rollback to baseline (restore backup) on reject

---

## 8) Verification system (what “nothing broke” means)

### 8.1 Baseline verification (must pass before any change)
The tool must detect or be configured with:
- build command (optional)
- unit tests command (required)
- typecheck command (recommended)
- lint command (recommended)
- integration tests (optional)
- benchmark command (optional)

The tool runs baseline verification in the worktree and records:
- command strings
- exit code
- elapsed time
- stdout/stderr paths
- environment (language version, lockfile hashes)

### 8.2 Per-batch verification
After applying a patch:
- run **fast verifier** (default: unit tests + lint)
Every N batches:
- run **full verifier** (default: full test suite + typecheck + integration tests)

### 8.3 Contract snapshots (optional but recommended)
Block accidental breaking changes by snapshotting:
- public exports
- routes/endpoints
- schema formats (OpenAPI/JSON schemas)
- CLI flags

Compare baseline vs current snapshot; if changed and not allowed → fail batch.

---

## 9) Indexing & durable “project memory”

### 9.1 Why
The orchestrator must not put entire repos into LLM context. Instead it:
- builds a local index
- retrieves small slices per batch

### 9.2 Required index artifacts (in worktree)
Store under `.refactor-bot/`:

- `.refactor-bot/ARCHITECTURE_SNAPSHOT.md`
- `.refactor-bot/SYMBOL_REGISTRY.json`
- `.refactor-bot/DEPENDENCY_GRAPH.json`
- `.refactor-bot/CALL_GRAPH.json` (best-effort)
- `.refactor-bot/RISK_REGISTER.json`
- `.refactor-bot/TASK_LEDGER.jsonl`
- `.refactor-bot/CONTRACTS/public_api_snapshot.json`

### 9.3 Indexer implementation
Minimum viable:
- file tree + hashes
- ripgrep-based symbol extraction (function/class defs)
Better:
- Tree-sitter for accurate symbols across languages
- import graph extraction per language

---

## 10) Planner (batch backlog generation)

### 10.1 Output
Planner generates a list of **atomic refactor batches** with:
- `id`
- `goal`
- `scope_globs`
- `allowed_operations`
- `diff_budget_loc`
- `risk_score`
- `required_verifier` (fast/full)
- `notes`

### 10.2 Ordering policy (risk-limiting)
1. Formatting-only pass (optional; if enabled do first)
2. Import cleanup / dead-code removal (only if safe)
3. Renames / small extracts / small module splits
4. Add/strengthen tests (seams) when needed
5. Larger internal restructures
6. “big transforms” last (async refactor, architecture shifts)

### 10.3 Planner agent vs program planner
Preferred:
- program generates a naive plan via heuristics
- LLM refines within constraints (never invents unbounded tasks)

---

## 11) The LLM protocol (schema-locked, batch-stateless)

### 11.1 Roles (recommended)
- **PlannerAgent**: proposes/refines batch list (no code changes)
- **PatcherAgent**: outputs a patch for exactly one batch
- **CriticAgent** (optional): reviews patch *before* apply; can request shrink scope/diff or noop

### 11.2 Stateless session strategy
For each LLM call, the orchestrator must pass:
- `--session-id <uuid>` (new per call)
- `--max-turns <small number>` (e.g., 6–12 for patcher)
Never use `--continue` in automated mode unless explicitly configured.

---

## 12) Context Pack Builder (the anti-overflow subsystem)

### 12.1 Hard budgets
Define budgets in **lines** and **bytes** (enforce both), e.g.:
- max prompt body: 40k chars
- max file excerpts: 600 lines total
- max ledger tail: 10 entries, 8 lines each

### 12.2 Retrieval policy (top-K)
Given a batch scope:
- include the most relevant files:
  - in-scope files touched recently
  - highest fan-in symbols
  - files referenced by imports from in-scope modules
- include only:
  - signatures + docstrings
  - small excerpts around hotspots
  - not full files unless tiny

### 12.3 Deterministic summaries (program-generated)
The program generates:
- list of candidate files
- symbol summaries (signature + location)
- recent batch summaries (from ledger)
Do not depend on the LLM to summarize the repo history.

---

## 13) How the orchestrator calls Claude Code (exact pattern)

### 13.1 Use `--system-prompt-file` and `--json-schema`
Each role has a system prompt file:
- `prompts/planner.system.txt`
- `prompts/patcher.system.txt`
- `prompts/critic.system.txt` (optional)

Each call uses:
- `claude -p "<USER_PROMPT>" --output-format json --json-schema '<schema>' --system-prompt-file <file> --allowedTools "..." --tools "..." --session-id <uuid> --max-turns <n>`

### 13.2 Parsing rule
When `--json-schema` is provided, Claude Code returns JSON with a `structured_output` field containing schema-validated output.
The orchestrator should:
- parse stdout as JSON
- read `structured_output`
- validate it again locally (defense-in-depth)

---

## 14) Required schemas

### 14.1 PlannerResponse schema (JSON Schema)
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

### 14.2 PatchResponse schema (JSON Schema)
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

### 14.3 CriticResponse schema (optional)
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

## 15) System prompts (must be versioned files)

### 15.1 `prompts/patcher.system.txt` (requirements)
The patcher system prompt must enforce:
- output only schema-validated JSON (no markdown)
- patch must be a unified diff
- never touch files outside scope
- preserve behavior and public contracts
- keep within diff budget
- if uncertain: `noop`
- do not modify lockfiles unless explicitly allowed
- do not reformat entire repo unless instructed

### 15.2 `prompts/planner.system.txt` (requirements)
Planner must:
- propose small batches, each with clear scope and goal
- order by risk-limiting policy
- cap total batches (default 200)
- avoid huge structural changes unless safety net is strong

### 15.3 Use `CLAUDE.md` for repo-specific conventions (recommended)
The orchestrator should optionally generate/update `.refactor-bot/CLAUDE_CONTEXT.md` and/or project `CLAUDE.md` to help Claude Code understand:
- test commands
- style conventions
- dangerous areas
But **do not** rely on it for automation correctness. The orchestrator still passes explicit prompts and schemas.

---

## 16) Patch application constraints

### 16.1 Patch validation
Before applying a patch:
- ensure `touched_files` ⊆ scope allowlist
- ensure diff applies cleanly (`git apply --check`)
- compute LOC touched; enforce `diff_budget_loc`
- reject binary changes unless allowed

### 16.2 Apply
Apply with:
- `git apply` (preferred)
- fallback to patch library if needed

### 16.3 Formatting-only mode
If a batch is “format only”, verify it:
- touches only formatting configs and files
- uses a formatter command, not manual edits

---

## 17) Execution loop (pseudocode)

```text
run(repo_path):
  preflight(repo_path)
  worktree = create_worktree_and_backup(repo_path)

  baseline = run_baseline_verifier(worktree)
  if baseline.fail: stop

  index = build_index(worktree)
  plan = build_plan(index)  # program + optional PlannerAgent

  show_confirm_screen(plan, baseline, backup_path)
  if user_cancel: cleanup and exit

  for batch in plan.batches:
    context = build_context_packet(index, ledger, batch)
    patch_resp = call_claude_patcher(context, batch)

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

## 18) Stop conditions (must be strict)

Stop immediately if:
- baseline verifier fails
- Claude Code not installed or not logged in
- patch violates scope/diff budget and cannot be regenerated cleanly
- verifier fails repeatedly
- contract snapshot shows breaking changes while disallowed
- exceeded max runtime (optional)

---

## 19) Configuration file

Create `.refactor-bot.config.json` in the repo root of the **worktree**:

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

## 20) Claude Code integration details the orchestrator must implement

### 20.1 Binary discovery
- Check `claude -v` works.
- If not found, show message: install/repair Claude Code.

### 20.2 Authentication check
Run a trivial headless query:
- `claude -p "Respond with OK" --output-format json`
If auth fails, exit with instructions to run interactive login.

### 20.3 Always use schema outputs
For every role call, use `--json-schema`.
If schema validation fails, retry once with stronger instructions; if still fails, stop.

### 20.4 Session isolation
- Always pass a random UUID via `--session-id`.
- Never use `--continue` by default.

---

## 21) Suggested repository layout for the orchestrator

```text
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

## 22) Milestones (build order)

### Milestone 1 — MVP
- Worktree + backup + rollback
- Baseline verifier
- Simple indexer (file tree + ripgrep symbols)
- PatcherAgent only (single batch, single scope)
- Ledger + report

### Milestone 2 — Planner + batching
- PlannerAgent schema + plan generation
- Context pack builder
- Batch loop with checkpoints

### Milestone 3 — Contract snapshots + stronger safety
- Public API snapshot for common ecosystems
- Benchmark gates (optional)
- CriticAgent (optional)

---

## 23) Deliverables checklist

The finished program must:
- [ ] Run with `refactor-bot run <repo>`
- [ ] Create backup + git safety worktree
- [ ] Refuse to run if baseline verification fails
- [ ] Use `claude -p` with `--json-schema` for every agent call
- [ ] Enforce scope + diff budgets
- [ ] Verify after every batch, rollback on failure
- [ ] Produce a final report and wait for user accept/reject

---

## 24) Notes for the builder (LLM) implementing this

- Do not assume Claude Code “conversation memory” exists. Treat each `claude -p` call as new.
- Depend on structured outputs (`--json-schema`) so parsing is reliable.
- Prefer deterministic, mechanical transformations; avoid logic rewrites unless explicitly requested.
- Keep code modular. Each subsystem should be independently testable.
