#!/usr/bin/env python3
"""
phone-to-mac agent — the "brain".

Turns a natural-language request ("mute everything and open Spotify") into one or
more actions from the FIXED allow-list, then runs each one through the same
command-locked dispatcher (dispatch.sh) that the phone Shortcut uses.

Safety design:
  - Claude can ONLY choose from the enum of allow-list actions (strict tool schema).
    It cannot invent an action or emit shell.
  - Every chosen action is re-checked here against ALLOWED, and every argument is
    re-validated inside dispatch.sh (URL scheme, volume range, app-name charset).
  - restart / shutdown require an interactive confirmation before they run.
  - v1 does NOT feed screen contents or web pages back to the model, so the only
    thing that can steer it is the request you type. (That keeps prompt-injection
    out of the loop.)

The model can, at worst, pick a different harmless allow-list action. It cannot
read files, run commands, or exfiltrate anything — the dispatcher won't accept it.

Usage:
  export ANTHROPIC_API_KEY=sk-ant-...
  python3 agent.py "set the volume to 20 and open youtube lofi beats"
  python3 agent.py --dry-run "shut down the office pc"     # show actions, run nothing
  python3 agent.py --yes "restart"                          # skip the confirm prompt
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time

try:
    import anthropic
except ImportError:
    sys.exit("Missing dependency. Run:  pip install anthropic")

HERE = os.path.dirname(os.path.abspath(__file__))

# --- config ----------------------------------------------------------------
DEFAULT_CONFIG = {
    "model": "claude-opus-5-5",
    "default_target": "mac",
    "targets": {
        # local = run dispatch.sh on this machine; ssh = reach another machine.
        "mac": {"type": "local", "dispatch": "~/.phone-remote/dispatch.sh"},
    },
}


def load_config():
    path = os.path.join(HERE, "config.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            sys.exit(f"Could not read config.json: {e}")
    return DEFAULT_CONFIG


# --- the allow-list (must stay in sync with dispatch.sh) --------------------
ALLOWED = [
    "ping", "openurl", "search", "youtube", "app-open", "app-close",
    "volume", "mute", "unmute", "playpause", "lock", "sleep",
    "restart", "shutdown", "screenshot",
]
NEEDS_CONFIRM = {"restart", "shutdown"}

COMPUTER_TOOL = {
    "name": "computer",
    "description": (
        "Perform ONE action on a paired computer. Call it more than once "
        "(the calls run in order) for multi-step requests."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ALLOWED},
            "value": {
                "type": "string",
                "description": (
                    "The argument. URL for openurl; query for search/youtube; "
                    "app name for app-open/app-close; a number 0-100 for volume; "
                    "empty string for actions that take no argument."
                ),
            },
            "target": {
                "type": "string",
                "description": "Computer name if the user named one, else empty for the default.",
            },
        },
        "required": ["action", "value", "target"],
        "additionalProperties": False,
    },
}

SYSTEM = """You are the control layer for the user's own computer(s). Convert the \
request into actions by calling the `computer` tool. Call it more than once for \
multi-step requests (e.g. 'mute and open Spotify' = two calls).

Actions and their `value`:
- ping (value ""): check a computer is online
- openurl (value: a full https:// URL): open a web page
- search (value: the query): Google search
- youtube (value: the query): YouTube search
- app-open (value: app name): open an app
- app-close (value: app name): quit an app
- volume (value: 0-100): set output volume
- mute / unmute (value "")
- playpause (value ""): toggle the current player
- lock (value ""): lock the screen
- sleep (value ""): sleep the computer
- restart / shutdown (value ""): the system asks the user to confirm these
- screenshot (value "")

Rules:
- Set `target` only if the user names a computer; otherwise leave it "".
- To open a website use openurl with the full https URL; for an app use app-open.
- volume must be 0-100: 'half'->50, 'max'->100. To silence, use the mute action.
- If the request can't be done with these actions, do NOT call the tool — reply in
  one short sentence saying you can't.
- Keep any text reply to one short line; it may be read aloud."""


# --- target resolution + dispatch ------------------------------------------
def resolve_target(config, name):
    targets = config["targets"]
    if name:
        for k, v in targets.items():
            if k.lower() == name.strip().lower():
                return k, v
    default = config.get("default_target")
    if default in targets:
        return default, targets[default]
    k = next(iter(targets))
    return k, targets[k]


def dispatch(action, value, tcfg):
    """Send one action to a target's dispatcher. Returns (ok, output)."""
    command = action if not value else f"{action} {value}"
    try:
        if tcfg["type"] == "local":
            path = os.path.expanduser(tcfg["dispatch"])
            env = dict(os.environ, SSH_ORIGINAL_COMMAND=command)
            p = subprocess.run(["bash", path], env=env,
                               capture_output=True, text=True, timeout=30)
        elif tcfg["type"] == "ssh":
            args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
            if tcfg.get("key"):
                args += ["-i", os.path.expanduser(tcfg["key"])]
            if tcfg.get("port"):
                args += ["-p", str(tcfg["port"])]
            args += [f'{tcfg["user"]}@{tcfg["host"]}', command]
            p = subprocess.run(args, capture_output=True, text=True, timeout=30)
        else:
            return False, f"unknown target type: {tcfg.get('type')}"
    except subprocess.TimeoutExpired:
        return False, "target did not respond (offline?)"
    except FileNotFoundError as e:
        return False, f"could not run dispatcher: {e}"

    out = (p.stdout or "").strip() or (p.stderr or "").strip()
    return p.returncode == 0, out


def confirm(action, target_name):
    try:
        ans = input(f"⚠  Confirm {action} on '{target_name}'? [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def execute(config, action, value, target, auto_yes, dry_run):
    tname, tcfg = resolve_target(config, target)

    if dry_run:
        return f"[dry-run] would run: {action} {value}".strip() + f"  on '{tname}'"

    if action in NEEDS_CONFIRM and not auto_yes:
        if not confirm(action, tname):
            return f"cancelled {action} on '{tname}' (declined)"

    ok, out = dispatch(action, value, tcfg)

    # Screenshot returns base64 PNG on stdout; save it rather than feed it back.
    if action == "screenshot" and ok and out:
        dest = os.path.expanduser(f"~/phone-remote-screenshot-{int(time.time())}.png")
        try:
            with open(dest, "wb") as f:
                f.write(base64.b64decode(out))
            return f"OK screenshot saved to {dest}"
        except (OSError, ValueError) as e:
            return f"ERR screenshot decode failed: {e}"

    return out or ("OK" if ok else "ERR (no output)")


# --- agent loop ------------------------------------------------------------
def run(config, request, auto_yes, dry_run):
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": request}]

    for _ in range(6):  # safety cap on tool rounds
        try:
            resp = client.messages.create(
                model=config["model"],
                max_tokens=4096,
                system=SYSTEM,
                tools=[{**COMPUTER_TOOL}],
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
                messages=messages,
            )
        except anthropic.AuthenticationError:
            sys.exit("Auth failed. Set a valid ANTHROPIC_API_KEY (or run `ant auth login`).")
        except anthropic.APIError as e:
            sys.exit(f"Claude API error: {e}")

        if resp.stop_reason == "refusal":
            detail = getattr(resp, "stop_details", None)
            why = f" ({detail.category})" if detail and getattr(detail, "category", None) else ""
            print(f"Claude declined this request{why}.")
            return

        for b in resp.content:
            if b.type == "text" and b.text.strip():
                print(b.text.strip())

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not tool_uses:
            return

        messages.append({"role": "assistant", "content": resp.content})

        results = []
        for tu in tool_uses:
            inp = tu.input or {}
            action = str(inp.get("action", ""))
            value = str(inp.get("value", ""))
            target = str(inp.get("target", ""))
            if action not in ALLOWED:
                res = f"ERR action '{action}' is not in the allow-list"
            else:
                res = execute(config, action, value, target, auto_yes, dry_run)
                shown_target = target or config.get("default_target", "")
                print(f"  → {action} {value} [{shown_target}]: {res}")
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": res})

        messages.append({"role": "user", "content": results})

    print("(stopped: too many steps)")


def main():
    ap = argparse.ArgumentParser(description="Drive your computers from natural language, safely.")
    ap.add_argument("request", nargs="+", help="what you want done, in plain words")
    ap.add_argument("-y", "--yes", action="store_true", help="skip the confirm prompt for power actions")
    ap.add_argument("-n", "--dry-run", action="store_true", help="show the actions, run nothing")
    args = ap.parse_args()

    config = load_config()
    run(config, " ".join(args.request), args.yes, args.dry_run)


if __name__ == "__main__":
    main()
