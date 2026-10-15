#!/bin/bash
# Double-click to start local-proton-mail on macOS. Opens http://127.0.0.1:7861 in your browser.
cd "$(dirname "$0")" || exit 1
# Finder starts this with a short PATH, so also look where uv's installers put it.
UV=$(command -v uv)
for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
  [ -z "$UV" ] && [ -x "$candidate" ] && UV="$candidate"
done
if [ -z "$UV" ]; then
  echo "uv isn't installed. Install it from https://docs.astral.sh/uv/ and run this again."
  read -r -p "Press Enter to close."
  exit 1
fi
"$UV" sync --quiet && "$UV" run python -m pmail serve
