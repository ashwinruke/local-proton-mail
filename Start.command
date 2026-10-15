#!/bin/bash
# Double-click to start local-proton-mail on macOS. Opens http://127.0.0.1:7861 in your browser.
# Close this window to stop it. Agents can use "./pmail.sh start" / "./pmail.sh stop" instead.
"$(dirname "$0")/pmail.sh" serve
