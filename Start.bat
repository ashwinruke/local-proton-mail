@echo off
rem Double-click to start local-proton-mail. Opens http://127.0.0.1:7861 in your browser.
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv isn't installed. Install it from https://docs.astral.sh/uv/ and run this again.
  pause
  exit /b 1
)
uv sync --quiet
uv run python -m pmail serve
pause
