#!/bin/bash
# Run this ON THE MAC. It installs the dispatcher and pins your phone's SSH key
# to it, so that key can ONLY ever run the allow-list in dispatch.sh.
set -euo pipefail

DIR="$HOME/.phone-remote"
AUTH="$HOME/.ssh/authorized_keys"
SRC="$(cd "$(dirname "$0")" && pwd)/dispatch.sh"

echo "==> Installing dispatcher into $DIR"
mkdir -p "$DIR"
cp "$SRC" "$DIR/dispatch.sh"
chmod 700 "$DIR/dispatch.sh"
touch "$DIR/activity.log"; chmod 600 "$DIR/activity.log"

echo
echo "==> Paste the PUBLIC key your iOS Shortcut shows (one line, starts with 'ssh-')."
echo "    Press Enter on an empty line to skip and add it by hand later."
read -r PUBKEY || PUBKEY=""

if [ -n "$PUBKEY" ]; then
  case "$PUBKEY" in
    ssh-ed25519\ *|ssh-rsa\ *|ecdsa-*\ *|sk-*\ *) : ;;
    *) echo "That does not look like an SSH public key. Nothing added."; exit 1 ;;
  esac
  mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
  touch "$AUTH"; chmod 600 "$AUTH"
  if grep -qF "$PUBKEY" "$AUTH" 2>/dev/null; then
    echo "That key is already in $AUTH; not adding a duplicate."
  else
    printf 'command="%s/dispatch.sh",restrict %s\n' "$DIR" "$PUBKEY" >> "$AUTH"
    echo "Added a restricted (command-locked) entry to $AUTH"
  fi
fi

echo
echo "==> Turn on Remote Login so the phone can reach this Mac:"
echo "      System Settings > General > Sharing > Remote Login = ON"
echo "      (set 'Allow access for' to your user only)"
echo "    or from Terminal:  sudo systemsetup -setremotelogin on"
echo
echo "Done. From the Shortcut, test with the command:  ping"
echo "To remove access later:  ./remove.sh"
