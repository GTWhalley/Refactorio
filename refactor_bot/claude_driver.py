"""
Claude Code CLI driver for Refactorio.

Handles all interactions with the Claude Code CLI, including:
- Binary discovery and authentication verification
- Executing prompts with structured outputs
- Parsing and validating responses
"""

from __future__ import annotations

import json
import subprocess
import shutil
import time
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable

from refactor_bot.config import ClaudeConfig
from refactor_bot.util import generate_session_id

# Optional debug logger - set by GUI if available
_debug_logger: Optional[Callable[[str, str], None]] = None

# Optional activity callback - called periodically during long operations
_activity_callback: Optional[Callable[[str, float], None]] = None


def set_debug_logger(logger: Callable[[str, str], None]) -> None:
    """Set the debug logger function."""
    global _debug_logger
    _debug_logger = logger


def set_activity_callback(callback: Callable[[str, float], None]) -> None:
    """Set the activity callback function.

    Callback receives (activity_message, elapsed_seconds).
    """
    global _activity_callback
    _activity_callback = callback


def _debug(message: str, level: str = "debug") -> None:
    """Log a debug message if logger is available."""
    if _debug_logger:
        _debug_logger(message, level)


def _notify_activity(message: str, elapsed: float) -> None:
    """Notify about ongoing activity."""
    if _activity_callback:
        _activity_callback(message, elapsed)


class ClaudeError(Exception):
    """Base exception for Claude-related errors."""

    pass


class ClaudeNotFoundError(ClaudeError):
    """Claude binary not found."""

    pass


class ClaudeAuthError(ClaudeError):
    """Claude not authenticated."""

    pass


class ClaudeResponseError(ClaudeError):
    """Invalid response from Claude."""

    pass


class AgentRole(str, Enum):
    """Agent roles for Claude calls."""

    PLANNER = "planner"
    PATCHER = "patcher"
    CRITIC = "critic"


@dataclass
class ClaudeResponse:
    """Response from a Claude call."""

    success: bool
    raw_output: str
    structured_output: Optional[dict] = None
    error_message: Optional[str] = None
    session_id: Optional[str] = None
    cost_usd: Optional[float] = None
    tokens_used: Optional[int] = None

    @classmethod
    def from_error(cls, error: str) -> "ClaudeResponse":
        return cls(
            success=False,
            raw_output="",
            error_message=error,
        )


class ClaudeDriver:
    """
    Driver for interacting with Claude Code CLI.

    Each call is stateless - new session ID per call.
    """

    def __init__(
        self,
        config: ClaudeConfig,
        prompts_dir: Path,
        schemas_dir: Path,
        working_dir: Optional[Path] = None,
    ):
        self.config = config
        self.prompts_dir = prompts_dir
        self.schemas_dir = schemas_dir
        self.working_dir = working_dir
        self._binary_path: Optional[str] = None

    @property
    def binary_path(self) -> str:
        """Get the path to the Claude binary."""
        if self._binary_path is None:
            self._binary_path = self._find_binary()
        return self._binary_path

    def _find_binary(self) -> str:
        """Find the Claude binary."""
        # Check configured path first
        if self.config.binary != "claude":
            if Path(self.config.binary).exists():
                return self.config.binary

        # Check PATH
        binary = shutil.which("claude")
        if binary:
            return binary

        raise ClaudeNotFoundError(
            "Claude Code binary not found. Please install Claude Code or set the "
            "correct path in configuration."
        )

    def check_installation(self) -> tuple[bool, str]:
        """
        Check if Claude Code is installed and get version.

        Returns:
            (is_installed, version_or_error)
        """
        try:
            binary = self.binary_path
            result = subprocess.run(
                [binary, "-v"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, result.stderr.strip()
        except ClaudeNotFoundError as e:
            return False, str(e)
        except subprocess.TimeoutExpired:
            return False, "Timeout checking Claude version"
        except Exception as e:
            return False, str(e)

    def check_authentication(self) -> tuple[bool, str]:
        """
        Check if Claude Code is authenticated.

        Returns:
            (is_authenticated, message)
        """
        try:
            result = self.call_raw(
                prompt='Respond with exactly "OK" and nothing else.',
                max_turns=1,
            )
            if result.success and "OK" in result.raw_output:
                return True, "Authenticated"
            return False, result.error_message or "Authentication check failed"
        except ClaudeNotFoundError as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)

    def call_raw(
        self,
        prompt: str,
        max_turns: int = 1,
        session_id: Optional[str] = None,
    ) -> ClaudeResponse:
        """
        Make a raw call to Claude without schema validation.

        Used for simple prompts like authentication checks.
        """
        session_id = session_id or generate_session_id()

        cmd = [
            self.binary_path,
            "-p", prompt,
            "--output-format", "json",
            "--max-turns", str(max_turns),
            "--session-id", session_id,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=self.working_dir,
            )

            if result.returncode != 0:
                return ClaudeResponse.from_error(
                    f"Claude exited with code {result.returncode}: {result.stderr}"
                )

            # Parse JSON output
            try:
                output = json.loads(result.stdout)
                return ClaudeResponse(
                    success=True,
                    raw_output=result.stdout,
                    structured_output=output,
                    session_id=session_id,
                )
            except json.JSONDecodeError:
                # Non-JSON output
                return ClaudeResponse(
                    success=True,
                    raw_output=result.stdout,
                    session_id=session_id,
                )

        except subprocess.TimeoutExpired:
            return ClaudeResponse.from_error("Claude call timed out")
        except Exception as e:
            return ClaudeResponse.from_error(str(e))

    def call_with_schema(
        self,
        prompt: str,
        role: AgentRole,
        max_turns: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> ClaudeResponse:
        """
        Call Claude with a system prompt and JSON schema validation.

        Args:
            prompt: The user prompt
            role: The agent role (determines system prompt and schema)
            max_turns: Maximum turns (defaults based on role)
            session_id: Optional session ID (generates new if not provided)

        Returns:
            ClaudeResponse with structured_output containing validated JSON
        """
        session_id = session_id or generate_session_id()

        # Determine max turns based on role
        if max_turns is None:
            if role == AgentRole.PATCHER:
                max_turns = self.config.max_turns_patcher
            elif role == AgentRole.PLANNER:
                max_turns = self.config.max_turns_planner
            else:
                max_turns = 6

        # Get system prompt file
        system_prompt_file = self.prompts_dir / f"{role.value}.system.txt"
        if not system_prompt_file.exists():
            return ClaudeResponse.from_error(
                f"System prompt file not found: {system_prompt_file}"
            )

        # Get schema file
        schema_file = self.schemas_dir / f"{role.value}.schema.json"
        if not schema_file.exists():
            return ClaudeResponse.from_error(
                f"Schema file not found: {schema_file}"
            )

        # Load schema
        try:
            with open(schema_file) as f:
                schema = json.load(f)
        except json.JSONDecodeError as e:
            return ClaudeResponse.from_error(f"Invalid schema JSON: {e}")

        # Build command
        cmd = [
            self.binary_path,
            "-p", prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(schema),
            "--system-prompt-file", str(system_prompt_file),
            "--allowedTools", self.config.allowed_tools,
            "--tools", self.config.tools,
            "--max-turns", str(max_turns),
            "--session-id", session_id,
        ]

        # Log the command (without the full prompt for brevity)
        cmd_display = [
            self.binary_path, "-p", f"<{len(prompt)} chars>",
            "--output-format", "json", "--json-schema", "<schema>",
            "--system-prompt-file", str(system_prompt_file),
            "--allowedTools", self.config.allowed_tools,
            "--tools", self.config.tools,
            "--max-turns", str(max_turns),
            "--session-id", session_id,
        ]
        _debug(f"Executing: {' '.join(cmd_display)}", "info")
        _debug(f"Working directory: {self.working_dir}", "debug")

        try:
            _debug("Starting Claude process...", "info")
            start_time = time.time()

            # Use Popen for streaming output and activity monitoring
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.working_dir,
            )

            # Activity monitor thread
            stop_monitor = threading.Event()
            stdout_chunks = []
            stderr_chunks = []

            def monitor_activity():
                """Thread to update elapsed time during Claude execution."""
                while not stop_monitor.is_set():
                    elapsed = time.time() - start_time
                    _notify_activity("Waiting for Claude response...", elapsed)
                    stop_monitor.wait(1.0)  # Update every second

            monitor_thread = threading.Thread(target=monitor_activity, daemon=True)
            monitor_thread.start()

            # Read output with timeout (10 minutes for large batches)
            try:
                stdout, stderr = process.communicate(timeout=600)
                stdout_chunks.append(stdout)
                stderr_chunks.append(stderr)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                stop_monitor.set()
                return ClaudeResponse.from_error("Claude call timed out after 10 minutes")
            finally:
                stop_monitor.set()
                monitor_thread.join(timeout=1.0)

            elapsed = time.time() - start_time
            _debug(f"Claude process completed in {elapsed:.1f}s with return code: {process.returncode}", "info")
            _notify_activity("Claude finished", elapsed)

            result_stdout = "".join(stdout_chunks)
            result_stderr = "".join(stderr_chunks)

            if process.returncode != 0:
                _debug(f"Claude stderr: {result_stderr[:500]}", "error")
                return ClaudeResponse.from_error(
                    f"Claude exited with code {process.returncode}: {result_stderr}"
                )

            # Parse JSON output
            try:
                output = json.loads(result_stdout)
            except json.JSONDecodeError:
                return ClaudeResponse.from_error(
                    f"Failed to parse Claude output as JSON: {result_stdout[:500]}"
                )

            # Extract structured output
            structured_output = output.get("structured_output")
            if structured_output is None:
                # Try to find it in the result
                if isinstance(output, dict):
                    structured_output = output
                else:
                    return ClaudeResponse.from_error(
                        "No structured_output in Claude response"
                    )

            # Validate against schema (defense in depth)
            validation_error = self._validate_schema(structured_output, schema)
            if validation_error:
                return ClaudeResponse.from_error(
                    f"Schema validation failed: {validation_error}"
                )

            return ClaudeResponse(
                success=True,
                raw_output=result_stdout,
                structured_output=structured_output,
                session_id=session_id,
            )

        except subprocess.TimeoutExpired:
            return ClaudeResponse.from_error("Claude call timed out after 10 minutes")
        except Exception as e:
            return ClaudeResponse.from_error(str(e))

    def _validate_schema(self, data: Any, schema: dict) -> Optional[str]:
        """Validate data against a JSON schema. Returns error message or None."""
        try:
            import jsonschema

            jsonschema.validate(data, schema)
            return None
        except jsonschema.ValidationError as e:
            return str(e.message)
        except Exception as e:
            return f"Schema validation error: {e}"

    def call_planner(self, context: str) -> ClaudeResponse:
        """Call the planner agent to generate/refine a refactoring plan."""
        return self.call_with_schema(
            prompt=context,
            role=AgentRole.PLANNER,
        )

    def call_patcher(self, context: str) -> ClaudeResponse:
        """Call the patcher agent to generate a patch for a batch."""
        return self.call_with_schema(
            prompt=context,
            role=AgentRole.PATCHER,
        )

    def call_critic(self, context: str) -> ClaudeResponse:
        """Call the critic agent to review a patch."""
        return self.call_with_schema(
            prompt=context,
            role=AgentRole.CRITIC,
        )


def check_claude_ready() -> tuple[bool, str]:
    """
    Check if Claude Code is installed and authenticated.

    Returns:
        (is_ready, message)
    """
    driver = ClaudeDriver(
        config=ClaudeConfig(),
        prompts_dir=Path("."),
        schemas_dir=Path("."),
    )

    # Check installation
    installed, version = driver.check_installation()
    if not installed:
        return False, (
            f"Claude Code is not installed or not found in PATH.\n"
            f"Error: {version}\n\n"
            f"Please install Claude Code and ensure 'claude' is available."
        )

    # Check authentication
    authed, message = driver.check_authentication()
    if not authed:
        return False, (
            f"Claude Code is not authenticated.\n"
            f"Error: {message}\n\n"
            f"Please run 'claude' interactively and use '/login' to authenticate."
        )

    return True, f"Claude Code {version} is ready"
