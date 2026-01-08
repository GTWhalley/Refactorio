#!/bin/bash
# Refactorio GUI Launcher
# Double-click this file to launch the GUI

cd "$(dirname "$0")"
python -m refactor_bot.cli gui
