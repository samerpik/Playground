#!/bin/bash
# Double-click me in Finder (or run me in Terminal) to start the focus coach.
cd "$(dirname "$0")" || exit 1
# Use the Python that already has the `anthropic` package (the phone-to-mac one).
for PY in "${FOCUS_PYTHON:-}" "../phone-to-mac/.venv/bin/python" "$(command -v python3)"; do
  if [ -n "$PY" ] && [ -x "$PY" ] && "$PY" -c "import anthropic" 2>/dev/null; then
    exec "$PY" server.py
  fi
done
echo "Couldn't find a Python that has the 'anthropic' package."
echo "Fix, in Terminal:  cd ~/Playground/projects/phone-to-mac && uv venv && uv pip install anthropic"
read -r -p "Press Enter to close. " _
