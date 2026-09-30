#!/usr/bin/env python3
"""
phone-to-mac agent — the "brain".

Turns a natural-language request ("mute everything and open Spotify") into one or
more actions from the FIXED allow-list, then runs each one through the same
command-locked dispatcher (dispatch.sh) that the phone Shortcut uses. It also just
talks: ask it a question and it answers, out loud if you want.

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
  python3 agent.py --speak "what's a good name for a dog"   # answer out loud
  python3 agent.py --talk                                    # voice conversation
  python3 agent.py --dry-run "shut down the office pc"      # show actions, run nothing
  python3 agent.py --yes "restart"                           # skip the confirm prompt
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time

try:
    import readline  # noqa: F401  (arrow keys and history at the talk prompt)
except ImportError:
    pass

try:
    import anthropic
except ImportError:
    sys.exit("Missing dependency. Run:  pip install anthropic")

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_ROUNDS = 6  # safety cap on tool rounds within one turn

# --- config ----------------------------------------------------------------
DEFAULT_CONFIG = {
    "model": "claude-opus-5-5",
    "default_target": "mac",
    "targets": {
        # local = run dispatch.sh on this machine; ssh = reach another machine.
        "mac": {"type": "local", "dispatch": "~/.phone-remote/dispatch.sh"},
    },
    # Optional, for spoken replies: a macOS voice name (see `say -v '?'`) and a
    # speaking rate in words per minute. None = the system default.
    "voice": None,
    "rate": None,
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
- If the user asks a QUESTION or is just chatting, do NOT use the tool — answer
  directly and conversationally (usually 1-3 sentences; it may be read aloud).
  You're a helpful voice assistant, not only a button panel.
- You can't look things up live (weather, news, prices, scores) and must not guess
  at them: use the search action to open the results for them, and say that's
  what you did.
- If they want something you truly can't do yet (it needs their email, calendar,
  files, or an action not in the list), say so briefly and what would enable it.
- Keep replies tight and speakable."""

VOICE_RULES = """You are talking out loud with the user, so:
- Speak in short, natural sentences, like a sharp, friendly assistant. No markdown,
  bullet points, headings, emoji or URLs: say things the way you would say them.
- Usually 1-3 sentences. Go longer only if they ask you to explain something, and
  then keep it easy to follow by ear.
- After doing an action, confirm in a few words ("Done, volume's at 25."). Don't
  narrate what you're about to do.
- If a request is ambiguous, ask ONE short question instead of guessing.
- The text comes from speech-to-text or typing, so expect small mishearings and
  infer the obvious intent."""


def build_system(voice):
    parts = [SYSTEM]
    if voice:
        parts.append(VOICE_RULES)
    # Fixed for the whole session, so it never changes mid-conversation.
    parts.append("Right now it is " + time.strftime("%A %d %B %Y, %H:%M")
                 + " (the user's local time).")
    return "\n\n".join(parts)


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


# --- speech ----------------------------------------------------------------
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")


def speakable(text):
    """Strip markdown, links and emoji so text-to-speech doesn't read them out."""
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)        # [label](url) -> label
    t = re.sub(r"https?://\S+", "a link", t)
    t = re.sub(r"^\s*(?:#{1,6}|>|[-*•]|\d+[.)])\s+", "", t, flags=re.M)
    t = t.replace("`", "").replace("*", "")
    t = _EMOJI.sub("", t)
    return re.sub(r"\s+", " ", t).strip()


class Speaker:
    """Speaks with macOS `say` without blocking; new speech cuts off the old."""

    def __init__(self, voice=None, rate=None):
        self.voice, self.rate, self.proc = voice, rate, None
        self.enabled = shutil.which("say") is not None
        if not self.enabled:
            print("(No `say` command found: spoken replies only work on a Mac.)")

    def say(self, text):
        text = speakable(text)
        if not text or not self.enabled:
            return
        self.stop()
        cmd = ["say"]
        if self.voice:
            cmd += ["-v", str(self.voice)]
        if self.rate:
            cmd += ["-r", str(int(self.rate))]
        try:
            # The text goes in on stdin, so nothing in it can be read as an option.
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            self.proc.stdin.write(text.encode("utf-8"))
            self.proc.stdin.close()
        except OSError:
            self.proc = None

    def stop(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                p.kill()

    def wait(self):
        try:
            if self.proc:
                self.proc.wait(timeout=120)
        except (KeyboardInterrupt, subprocess.TimeoutExpired):
            self.stop()


def audio_state():
    """Return (output volume 0-100 or None, muted True/False or None) from macOS."""
    try:
        out = subprocess.run(["osascript", "-e", "get volume settings"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return None, None
    vol = re.search(r"output volume:(\d+)", out)
    muted = re.search(r"output muted:(true|false)", out)
    return (int(vol.group(1)) if vol else None,
            (muted.group(1) == "true") if muted else None)


def warn_if_silent():
    vol, muted = audio_state()
    if muted or vol == 0:
        print("!  Your Mac's sound is muted or at zero, so you won't hear me.\n"
              "   Type 'unmute' (or 'set the volume to 40') and I'll sort it.")


EXIT_WORDS = {"exit", "quit", "bye", "bye bye", "goodbye", "good bye", "thats all", "that's all"}
RESET_WORDS = {"reset", "new conversation", "start over", "start again"}


def _plain(text):
    return re.sub(r"[^\w\s']", "", text.replace("’", "'").lower()).strip()


def is_exit(text):
    return _plain(text) in EXIT_WORDS


def is_reset(text):
    return _plain(text) in RESET_WORDS


# --- agent loop ------------------------------------------------------------
def turn(client, config, system, messages, text, auto_yes, dry_run, quiet=False):
    """Run one user turn (several model rounds when tools are used).

    `messages` is the conversation so far. It is only ever appended to, so the model
    keeps its memory across turns. If a turn fails part-way, everything it added is
    removed again, so the history is always a run of complete exchanges.
    Returns (reply text, last tool result or None). SDK errors propagate.
    """
    mark = len(messages)
    messages.append({"role": "user", "content": text})
    printed = False
    last_res = None
    reply = ""
    try:
        for _ in range(MAX_ROUNDS):
            resp = client.messages.create(
                model=config["model"],
                max_tokens=4096,
                system=system,
                tools=[COMPUTER_TOOL],
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
                messages=messages,
            )
            tool_uses = [b for b in resp.content if b.type == "tool_use"]

            if resp.stop_reason == "refusal":
                del messages[mark:]
                detail = getattr(resp, "stop_details", None)
                why = f" ({detail.category})" if detail and getattr(detail, "category", None) else ""
                msg = f"Sorry, I can't help with that{why}."
                print(msg)
                return msg, last_res
            if tool_uses and resp.stop_reason != "tool_use":
                # Cut off mid tool call: it can't be replayed, so drop the turn.
                del messages[mark:]
                msg = "Sorry, that reply got cut off. Could you say it again?"
                print(msg)
                return msg, last_res

            texts = [b.text.strip() for b in resp.content if b.type == "text" and b.text.strip()]
            for t in texts:
                print(t)
                printed = True
            if texts:
                reply = " ".join(texts)

            # An empty reply still needs a well-formed assistant turn in the history.
            content = resp.content or [{"type": "text", "text": "(no reply)"}]
            messages.append({"role": "assistant", "content": content})

            if not tool_uses:
                if quiet and not printed and last_res:
                    print(last_res)
                return reply, last_res

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
                    if not quiet:
                        print(f"  → {action} {value} [{shown_target}]: {res}")
                last_res = res
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": res})
            messages.append({"role": "user", "content": results})

        # Out of rounds. End on an assistant message so the history stays well-formed.
        note = "(I stopped after too many steps.)"
        messages.append({"role": "assistant", "content": [{"type": "text", "text": note}]})
        if quiet and not printed and last_res:
            print(last_res)
        elif not quiet:
            print(note)
        return reply, last_res
    except BaseException:
        del messages[mark:]
        raise


def run(config, request, auto_yes, dry_run, quiet=False, voice=False):
    """One request, no memory: the `mac ...` and `ask ...` commands."""
    client = anthropic.Anthropic()
    try:
        reply, _ = turn(client, config, build_system(voice), [], request,
                        auto_yes, dry_run, quiet)
    except anthropic.AuthenticationError:
        sys.exit("Auth failed. Set a valid ANTHROPIC_API_KEY (or run `ant auth login`).")
    except anthropic.APIError as e:
        sys.exit(f"Claude API error: {e}")
    return reply


def talk(config, first, auto_yes, dry_run):
    """A back-and-forth conversation: you speak (dictate) or type, it answers aloud."""
    client = anthropic.Anthropic()
    speaker = Speaker(config.get("voice"), config.get("rate"))
    system = build_system(voice=True)
    messages = []

    print("Talk mode: speak (dictate) or type, then press Enter.")
    print("  'goodbye' ends it · 'reset' starts a fresh conversation · "
          "Enter on a blank line cuts me off")
    warn_if_silent()
    speaker.say("I'm listening.")

    try:
        while True:
            print()
            if first:
                text, first = first, None
                print(f"you> {text}")
            else:
                try:
                    text = input("you> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
            speaker.stop()  # anything you send cuts off the previous reply
            if not text:
                continue
            if is_exit(text):
                speaker.say("Goodbye.")
                speaker.wait()
                break
            if is_reset(text):
                messages.clear()
                print("(fresh conversation)")
                speaker.say("Okay, fresh start.")
                continue

            started = time.time()
            try:
                reply, last_res = turn(client, config, system, messages, text,
                                       auto_yes, dry_run)
            except KeyboardInterrupt:
                print("\n(cancelled)")
                continue
            except anthropic.AuthenticationError:
                print("Auth failed. Set a valid ANTHROPIC_API_KEY (or run `ant auth login`).")
                break
            except anthropic.APIError as e:
                print(f"(Claude API error: {e})")
                speaker.say("Sorry, I hit an error talking to Claude.")
                continue

            if not reply and last_res:
                reply = "Done." if last_res.startswith("OK") else "That didn't work."
            speaker.say(reply)
            print(f"   ({time.time() - started:.1f}s)")
    finally:
        speaker.stop()


def main():
    ap = argparse.ArgumentParser(description="Drive your computers from natural language, safely.")
    ap.add_argument("request", nargs="*", help="what you want done, in plain words")
    ap.add_argument("-y", "--yes", action="store_true", help="skip the confirm prompt for power actions")
    ap.add_argument("-n", "--dry-run", action="store_true", help="show the actions, run nothing")
    ap.add_argument("-q", "--quiet", action="store_true", help="print only the final result (for voice/SSH)")
    ap.add_argument("-s", "--speak", action="store_true", help="speak the reply aloud (macOS 'say')")
    ap.add_argument("-t", "--talk", action="store_true", help="voice conversation (keeps memory until you say goodbye)")
    ap.add_argument("--model", help="use this model instead of the one in config.json")
    args = ap.parse_args()

    config = dict(load_config())
    if args.model:
        config["model"] = args.model

    if args.talk:
        talk(config, " ".join(args.request) or None, args.yes, args.dry_run)
        return
    if not args.request:
        ap.error("give a request, or use --talk for a conversation")

    reply = run(config, " ".join(args.request), args.yes, args.dry_run,
                args.quiet, voice=args.speak)
    if args.speak and reply and reply.strip():
        speaker = Speaker(config.get("voice"), config.get("rate"))
        speaker.say(reply)
        speaker.wait()


if __name__ == "__main__":
    main()
