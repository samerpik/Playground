#!/bin/bash
# phone-to-mac dispatcher
# ---------------------------------------------------------------------------
# This script is meant to run ONLY as an SSH forced command (see install.sh /
# README). It executes a FIXED allow-list of harmless actions. There is no
# shell, no eval, no arbitrary command execution, and no file deletion.
#
# The phone sends a command string over SSH; because the key is pinned to this
# script with command="..." in authorized_keys, sshd ignores whatever the
# client asks to run and runs THIS instead, putting the requested string in
# $SSH_ORIGINAL_COMMAND. We parse that as:  <action> <argument>
#
# Every argument is validated. Variables are always quoted, so even a command
# like  openurl "; rm -rf ~"  is passed to `open` as one literal string and
# never interpreted by a shell.
# ---------------------------------------------------------------------------
set -u

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$SELF_DIR/activity.log"

# --- parse action + argument -----------------------------------------------
raw="${SSH_ORIGINAL_COMMAND:-}"
action="${raw%% *}"                 # first word
arg=""
case "$raw" in
  *" "*) arg="${raw#* }" ;;         # everything after the first space
esac

log() {
  printf '%s\t%s\t%s\t%s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$action" "${arg:-}" "$1" >> "$LOG" 2>/dev/null || true
}
ok()  { printf 'OK %s\n'  "$1"; log "OK $1";  exit 0; }
die() { printf 'ERR %s\n' "$1"; log "ERR $1"; exit 1; }

require_arg() { [ -n "$arg" ] || die "missing argument for '$action'"; }

urlencode() {
  # byte-accurate percent-encoding; LC_ALL=C so UTF-8 (e.g. Turkish) encodes
  # correctly one byte at a time.
  local LC_ALL=C s="$1" out="" c i
  for (( i=0; i<${#s}; i++ )); do
    c="${s:i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out="$out$c" ;;
      *) out="$out$(printf '%%%02X' "'$c")" ;;
    esac
  done
  printf '%s' "$out"
}

# --- the allow-list --------------------------------------------------------
case "$action" in

  ping)
    ok "$(scutil --get ComputerName 2>/dev/null || hostname)"
    ;;

  openurl)
    require_arg
    case "$arg" in
      http://*|https://*) : ;;
      *) die "only http/https URLs are allowed" ;;
    esac
    open "$arg" && ok "opened url"
    die "open failed"
    ;;

  search)
    require_arg
    open "https://www.google.com/search?q=$(urlencode "$arg")" && ok "searched"
    die "open failed"
    ;;

  youtube)
    require_arg
    open "https://www.youtube.com/results?search_query=$(urlencode "$arg")" && ok "youtube"
    die "open failed"
    ;;

  app-open)
    require_arg
    case "$arg" in
      *[!A-Za-z0-9\ ._-]*) die "invalid app name" ;;
    esac
    open -a "$arg" && ok "opened $arg"
    die "app not found: $arg"
    ;;

  app-close)
    require_arg
    case "$arg" in
      *[!A-Za-z0-9\ ._-]*) die "invalid app name" ;;
    esac
    osascript -e "tell application \"$arg\" to quit" >/dev/null 2>&1   # graceful
    sleep 2
    if pgrep -x "$arg" >/dev/null 2>&1; then                          # then force
      killall "$arg" >/dev/null 2>&1 || true
    fi
    ok "closed $arg"
    ;;

  volume)
    require_arg
    case "$arg" in ''|*[!0-9]*) die "volume must be 0-100" ;; esac
    [ "$arg" -le 100 ] || die "volume must be 0-100"
    osascript -e "set volume output volume $arg" && ok "volume $arg"
    die "volume failed"
    ;;

  mute)   osascript -e "set volume output muted true"  && ok "muted";   die "failed" ;;
  unmute) osascript -e "set volume output muted false" && ok "unmuted"; die "failed" ;;

  playpause)
    # macOS has no built-in system-wide media key from the CLI. We control
    # whichever common player is running (documented limitation).
    if pgrep -x "Spotify" >/dev/null 2>&1; then
      osascript -e 'tell application "Spotify" to playpause' && ok "spotify"
    elif pgrep -x "Music" >/dev/null 2>&1; then
      osascript -e 'tell application "Music" to playpause' && ok "music"
    else
      die "no supported player running (Music/Spotify)"
    fi
    die "failed"
    ;;

  lock)
    CG="/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession"
    if [ -x "$CG" ]; then
      "$CG" -suspend >/dev/null 2>&1 && ok "locked"
    fi
    # fallback: sleep the display (locks if "require password immediately" is set)
    pmset displaysleepnow >/dev/null 2>&1 && ok "locked (display sleep)"
    die "lock failed"
    ;;

  sleep)
    # pmset needs no Automation permission; System Events is the fallback.
    pmset sleepnow >/dev/null 2>&1 && ok "sleeping"
    osascript -e 'tell application "System Events" to sleep' && ok "sleeping"
    die "failed"
    ;;

  restart)
    [ "$arg" = "confirm" ] || die "restart needs confirmation: send 'restart confirm'"
    printf 'OK restarting\n'; log "OK restarting"     # result sent before acting
    osascript -e 'tell application "System Events" to restart'
    exit 0
    ;;

  shutdown)
    [ "$arg" = "confirm" ] || die "shutdown needs confirmation: send 'shutdown confirm'"
    printf 'OK shutting down\n'; log "OK shutting down"   # result sent before acting
    osascript -e 'tell application "System Events" to shut down'
    exit 0
    ;;

  screenshot)
    # Needs Screen Recording permission for the process running sshd. Until
    # granted, the image is black or capture fails. Output is base64 PNG.
    tmp="$(mktemp -t phoneremote 2>/dev/null || echo "/tmp/phoneremote.$$")"
    if screencapture -x -t png "$tmp" >/dev/null 2>&1 && [ -s "$tmp" ]; then
      base64 < "$tmp"; rm -f "$tmp"; log "OK screenshot"; exit 0
    fi
    rm -f "$tmp"
    die "screenshot failed (grant Screen Recording permission)"
    ;;

  ""|help)
    printf 'actions: ping openurl search youtube app-open app-close volume mute unmute playpause lock sleep restart(confirm) shutdown(confirm) screenshot\n'
    exit 0
    ;;

  *)
    die "unknown action: $action"
    ;;
esac
