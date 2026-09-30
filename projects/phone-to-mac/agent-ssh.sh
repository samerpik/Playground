#!/bin/bash
# SSH forced-command wrapper for the phone.
#
# Pinned in ~/.ssh/authorized_keys as the phone key's forced command, so the
# phone can ONLY run this. It takes whatever the phone sent (dictated or typed
# text, in $SSH_ORIGINAL_COMMAND) and runs the natural-language agent on it in
# --quiet mode. The agent can still ONLY emit allow-list actions, which
# dispatch.sh re-validates — so putting Claude on the phone changes nothing
# about what can actually run.
set -u

DIR="$(cd "$(dirname "$0")" && pwd)"

# Load the API key from the owner-only file, if present.
if [ -f "$HOME/.phone-remote/agent.env" ]; then
  set -a; . "$HOME/.phone-remote/agent.env"; set +a
fi

req="${SSH_ORIGINAL_COMMAND:-}"
[ -n "$req" ] || { echo "(say a command)"; exit 0; }

exec "$DIR/.venv/bin/python" "$DIR/agent.py" --quiet "$req"
