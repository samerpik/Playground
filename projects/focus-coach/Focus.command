#!/bin/bash
# Double-click me in Finder (or run me in Terminal) to start the focus coach.
cd "$(dirname "$0")" || exit 1

# One-time, best-effort: get the free natural voice (edge-tts). Never blocks the launch —
# if it can't install (offline, no pip), the coach still runs with the built-in Mac voices.
ensure_voice() {
  local py="$1"
  "$py" -c "import edge_tts" 2>/dev/null && return 0
  echo "Setting up the natural voice (one-time)…"
  if command -v uv >/dev/null 2>&1 && uv pip install --python "$py" edge-tts >/dev/null 2>&1; then return 0; fi
  "$py" -m pip install edge-tts >/dev/null 2>&1 && return 0
  echo "  (Skipped — using the built-in Mac voices. To add the natural voice later, see the README.)"
}

# Use the Python that already has the `anthropic` package (the phone-to-mac one).
for PY in "${FOCUS_PYTHON:-}" "../phone-to-mac/.venv/bin/python" "$(command -v python3)"; do
  if [ -n "$PY" ] && [ -x "$PY" ] && "$PY" -c "import anthropic" 2>/dev/null; then
    ensure_voice "$PY"
    exec "$PY" server.py
  fi
done
echo "Couldn't find a Python that has the 'anthropic' package."
echo "Fix, in Terminal:  cd ~/Playground/projects/phone-to-mac && uv venv && uv pip install anthropic"
read -r -p "Press Enter to close. " _
