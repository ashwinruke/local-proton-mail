#!/bin/bash
# Double-click to start local-proton-mail on macOS. Opens http://127.0.0.1:7861 in your browser.
cd "$(dirname "$0")" || exit 1
if ! command -v uv >/dev/null 2>&1; then
  echo "uv isn't installed. Install it from https://docs.astral.sh/uv/ and run this again."
  read -r -p "Press Enter to close."
  exit 1
fi
uv sync --quiet && uv run python -m pmail serve
