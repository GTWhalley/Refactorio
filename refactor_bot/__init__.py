"""
Refactorio - Automated whole-repo refactoring orchestrator using Claude Code CLI.

This tool enables safe, incremental, and verifiable refactoring across entire repositories
by leveraging Claude Code in headless mode with structured outputs.
"""

__version__ = "0.1.0"
__author__ = "Graydon Whalley"

from refactor_bot.config import Config, ClaudeConfig

__all__ = ["Config", "ClaudeConfig", "__version__"]
