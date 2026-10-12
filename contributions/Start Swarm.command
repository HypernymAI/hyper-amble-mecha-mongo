#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
SWARM_PYTHON="$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3 || true)"
if [ -z "$SWARM_PYTHON" ]; then
  echo "Install Python 3.9 or newer, then reopen Start Swarm.command."
  read -r
  exit 1
fi
"$SWARM_PYTHON" scripts/swarm_run.py --bootstrap
swarm_status=$?
if [ "$swarm_status" -ne 0 ]; then read -r -p "Press Return to close."; fi
exit "$swarm_status"
