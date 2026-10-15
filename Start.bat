@echo off
rem Double-click to start local-proton-mail. Opens http://127.0.0.1:7861 in your browser.
cd /d "%~dp0"
set "UV=uv"
where uv >nul 2>nul
if errorlevel 1 (
  rem uv installed with "pip install uv" isn't always on PATH; use it through Python.
  python -m uv --version >nul 2>nul
  if errorlevel 1 (
    echo uv isn't installed. Install it from https://docs.astral.sh/uv/ ^(or: pip install uv^) and run this again.
    pause
    exit /b 1
  )
  set "UV=python -m uv"
)
%UV% sync --quiet
%UV% run python -m pmail serve
pause
