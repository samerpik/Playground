#!/bin/bash
# Run this ON THE MAC to check the phone-to-mac setup. Non-destructive:
# it only reads state, pings, and does a volume change it restores.
set -u

DIR="$HOME/.phone-remote"
DISPATCH="$DIR/dispatch.sh"
AUTH="$HOME/.ssh/authorized_keys"

pass=0; fail=0
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$1"; pass=$((pass+1)); }
no()   { printf '  \033[31mFAIL\033[0m %s\n' "$1"; fail=$((fail+1)); }

echo "phone-to-mac doctor"
echo "-------------------"

# 1. Is SSH (Remote Login) listening?
if nc -z -G2 localhost 22 >/dev/null 2>&1 || nc -z localhost 22 >/dev/null 2>&1; then
  ok "Remote Login is listening on port 22"
else
  no "nothing on port 22 - turn on System Settings > General > Sharing > Remote Login"
fi

# 2. Is the dispatcher installed?
if [ -x "$DISPATCH" ]; then
  ok "dispatcher installed at $DISPATCH"
else
  no "dispatcher missing/not executable at $DISPATCH - run ./install.sh"
fi

# 3. Is a command-locked key pinned?
if [ -f "$AUTH" ] && grep -qF "$DISPATCH" "$AUTH"; then
  ok "a command-locked key is present in authorized_keys"
else
  no "no command-locked key in $AUTH - run ./install.sh and paste the phone's public key"
fi

# 4. Ping through the dispatcher.
if [ -x "$DISPATCH" ]; then
  out="$(SSH_ORIGINAL_COMMAND=ping bash "$DISPATCH" 2>&1)"
  case "$out" in
    OK*) ok "dispatcher ping -> $out" ;;
    *)   no "dispatcher ping failed -> $out" ;;
  esac
fi

# 5. Volume round-trip (reversible, no permission prompt).
if [ -x "$DISPATCH" ]; then
  cur="$(osascript -e 'output volume of (get volume settings)' 2>/dev/null)"
  if [ -n "$cur" ]; then
    SSH_ORIGINAL_COMMAND="volume 30" bash "$DISPATCH" >/dev/null 2>&1
    now="$(osascript -e 'output volume of (get volume settings)' 2>/dev/null)"
    SSH_ORIGINAL_COMMAND="volume $cur" bash "$DISPATCH" >/dev/null 2>&1   # restore
    if [ "$now" = "30" ]; then
      ok "volume set works (restored to $cur)"
    else
      no "volume set did not take (read back '$now')"
    fi
  else
    no "could not read volume via osascript"
  fi
fi

echo
echo "Result: $pass passed, $fail failed."
echo
echo "Manual checks (each may pop a ONE-TIME macOS permission prompt - approve it):"
echo "  SSH_ORIGINAL_COMMAND='app-open TextEdit'  bash \"$DISPATCH\"   # Automation prompt"
echo "  SSH_ORIGINAL_COMMAND='app-close TextEdit' bash \"$DISPATCH\""
echo "  SSH_ORIGINAL_COMMAND='screenshot' bash \"$DISPATCH\" | head -c 40   # Screen Recording prompt"
echo "  SSH_ORIGINAL_COMMAND='lock' bash \"$DISPATCH\"                 # locks the screen"
echo
echo "Then the real paths:"
echo "  phone Shortcut, command:  ping"
echo "  agent:  python3 agent.py --dry-run 'lock the mac'   then without --dry-run"
