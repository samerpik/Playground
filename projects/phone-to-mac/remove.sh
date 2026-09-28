#!/bin/bash
# Run this ON THE MAC to instantly revoke the phone's access.
set -euo pipefail

DIR="$HOME/.phone-remote"
AUTH="$HOME/.ssh/authorized_keys"

echo "==> Revoking phone-to-mac access."
if [ -f "$AUTH" ] && grep -qF "$DIR/dispatch.sh" "$AUTH"; then
  cp "$AUTH" "$AUTH.bak.$(date +%s)"
  grep -vF "$DIR/dispatch.sh" "$AUTH" > "$AUTH.tmp"
  mv "$AUTH.tmp" "$AUTH"
  chmod 600 "$AUTH"
  echo "Removed the command-locked key line(s) from $AUTH (backup kept alongside)."
else
  echo "No phone-to-mac entry found in $AUTH."
fi

printf 'Also delete the dispatcher folder %s ? [y/N] ' "$DIR"
read -r a || a=""
case "$a" in
  y|Y) rm -rf "$DIR"; echo "Deleted $DIR." ;;
  *)   echo "Kept $DIR (holds activity.log)." ;;
esac

echo
echo "To cut ALL SSH into this Mac immediately:"
echo "  sudo systemsetup -setremotelogin off"
