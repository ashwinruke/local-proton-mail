#!/bin/bash
# Double-click to start local-proton-mail on macOS. Opens http://127.0.0.1:7861 in your browser.
cd "$(dirname "$0")" || exit 1
if command -v uv >/dev/null 2>&1; then
  UV=(uv)
elif python3 -m uv --version >/dev/null 2>&1; then
  UV=(python3 -m uv)  # uv installed with "pip install uv" isn't always on PATH
else
  echo "uv isn't installed. Install it from https://docs.astral.sh/uv/ (or: pip3 install uv) and run this again."
  read -r -p "Press Enter to close."
  exit 1
fi
"${UV[@]}" sync --quiet && "${UV[@]}" run python -m pmail serve
