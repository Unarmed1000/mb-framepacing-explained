@echo off
rem SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
rem SPDX-License-Identifier: CC-BY-NC-SA-4.0
rem Create or update the .venv and local.toml (see tools\setup_venv.py). Arguments are passed on, for example:
rem   setup.cmd --ffmpeg C:\ffmpeg\bin
setlocal
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0tools\setup_venv.py" %*
) else (
  py -3.14 "%~dp0tools\setup_venv.py" %*
)
exit /b %errorlevel%
