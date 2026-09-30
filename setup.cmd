@echo off
rem SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
rem SPDX-License-Identifier: CC-BY-NC-SA-4.0
rem Set up the repository: uv creates or updates .venv (Python from .python-version, packages from uv.lock), then
rem tools\setup_local.py fetches the mb-framepacing submodule and creates local.toml. Arguments are passed on, for example:
rem   setup.cmd --ffmpeg C:\ffmpeg\bin
setlocal
where uv >nul 2>nul
if errorlevel 1 (
  echo uv was not found. Install it: winget install --id astral-sh.uv ^(or see https://docs.astral.sh/uv/^), then run setup.cmd again. 1>&2
  exit /b 1
)
pushd "%~dp0"
uv run tools\setup_local.py %*
set result=%errorlevel%
popd
exit /b %result%
