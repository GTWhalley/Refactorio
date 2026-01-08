#!/bin/bash
# Refactorio GUI Launcher
# Double-click this file to launch the GUI

cd "$(dirname "$0")"
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m refactor_bot.cli gui
