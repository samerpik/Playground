#!/usr/bin/env python3
"""
Focus coach: a keystroke-to-talk conversation that knows what you're juggling.

Run it and a page opens in your browser. Hold or tap SPACE and talk; it answers out
loud (your browser's speech), remembers your week from a notes file, and saves new
ideas to that file. It is deliberately small and cheap: one short call to a small
model per turn, no web access, no thinking, and the only thing it can do to your
computer is append lines to your notes.

Where things go:
  - Your speech is turned into text by your browser's speech service (Google for
    Chrome, Apple for Safari).
  - Your notes and the recent conversation are sent to Anthropic with each message.
  - Nothing else leaves your Mac. The server listens on this computer only.

Files live in ~/.focus-coach/ (notes.md, usage.json, optional config.json).
"""

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import anthropic
except ImportError:
    sys.exit("Missing dependency. Run:  pip install anthropic")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.expanduser(os.environ.get("FOCUS_HOME", "~/.focus-coach"))
NOTES_PATH = os.path.join(DATA, "notes.md")
USAGE_PATH = os.path.join(DATA, "usage.json")
CONFIG_PATH = os.path.join(DATA, "config.json")

DEFAULTS = {
    "model": "claude-haiku-4-5",  # small and cheap; use "claude-sonnet-5-5" for deeper coaching
    "max_tokens": 300,            # replies are spoken, so short
    "keep_turns": 12,             # earlier exchanges sent along with each new message; older ones are dropped (notes stay)
    "daily_cap_usd": 1.00,        # stop calling the model past this estimated daily spend
    "port": 8765,
    "lang": None,                 # speech recognition language, e.g. "en-GB"; None = the browser's
    "prices": {},                 # {"model": [input, output]} in $ per million tokens; overrides PRICES
}

# $ per million tokens (input, output). From the price table I had (dated 2026-09-25);
# estimates only, so check the Anthropic console for what you were actually billed.
PRICES = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
MAX_NOTES_CHARS = 24000  # beyond this only the most recent notes are sent (and the page says so)

PERSONA = """You are the user's personal focus coach, talking with them out loud. Their attention is the most expensive resource they have; your job is to help them choose what deserves it and to keep them moving.

What you know about their week is in the notes below. Treat the notes as the source of truth. Don't invent details that aren't there; when something is missing, ask.

How to coach:
- Be direct. Don't soften feedback. If an idea is weak, or doesn't move a current priority, say so and why, in a sentence.
- Favour finishing over starting. When a new idea would pull time from something more important, say so and suggest parking it.
- Don't reopen decisions that are already made unless there is new information. Call out over-polishing and perfectionism.
- Rank, don't list: when several things compete, say which matters most, which can wait, and which to drop.
- Ask one question at a time. Aim for the single highest-leverage next step.
- Small problems that don't affect clients, revenue or the main goal go on the backlog.

Speaking: your reply is read aloud, so use 1-3 short sentences. No markdown, lists, headings, emoji or URLs. The text comes from speech recognition, so expect small mishearings and infer the obvious meaning.

Saving: when the user gives you a new idea, makes a decision, or gives a status update (for example a client deadline), call save_note with a short line in their own words. Never save your own advice. Say your spoken reply in the same message as the save. You can only save notes: you cannot browse the web, set reminders or control the computer, so don't offer to."""

ONBOARDING = """Their notes are still empty. Start by asking, one question at a time, about each area in the notes: what the goal is, what the next step is and any deadline. Save each answer with save_note as you go."""

QUICK = re.compile(r"^\s*(idea|note)\s*[:,\-]\s*(.+)$", re.IGNORECASE | re.DOTALL)
HEADING = re.compile(r"^##\s+(.+?)\s*$")
NOTE_LINE = re.compile(r"^\s*-\s+(?:\((\d{4}-\d{2}-\d{2})\)\s*)?(.+)$")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

NOTES_LOCK = threading.Lock()


# --- config, key, files ------------------------------------------------------
def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        sys.exit(f"Could not read {CONFIG_PATH}: {e}")
    return cfg


def ensure_api_key():
    """Use ANTHROPIC_API_KEY if set, else the one saved for the `mac` command."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    try:
        with open(os.path.expanduser("~/.phone-remote/agent.env"), encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*(?:export\s+)?ANTHROPIC_API_KEY\s*=\s*(.+?)\s*$", line)
                if m:
                    os.environ["ANTHROPIC_API_KEY"] = m.group(1).strip("'\"")
                    return True
    except OSError:
        pass
    return False


def ensure_notes():
    os.makedirs(DATA, mode=0o700, exist_ok=True)
    if not os.path.exists(NOTES_PATH):
        shutil.copyfile(os.path.join(HERE, "notes.example.md"), NOTES_PATH)
        os.chmod(NOTES_PATH, 0o600)


def read_notes():
    with open(NOTES_PATH, encoding="utf-8") as f:
        return f.read()


def write_notes(text):
    """Replace the notes, keeping the previous version as notes.md.bak."""
    if os.path.exists(NOTES_PATH):
        shutil.copyfile(NOTES_PATH, NOTES_PATH + ".bak")
    tmp = NOTES_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, NOTES_PATH)


# --- notes -------------------------------------------------------------------
def strip_comments(text):
    return COMMENT.sub("", text)


def sections(text):
    names = [m.group(1) for line in text.splitlines() if (m := HEADING.match(line))]
    return names or ["Ideas"]


def has_notes(text):
    return any(NOTE_LINE.match(line) for line in strip_comments(text).splitlines())


def append_note(section, note, today=None):
    """Append one dated line under a section. Never edits or removes anything else.

    An unknown section falls back to "Ideas", so the model cannot invent headings.
    Returns (ok, section it went to).
    """
    note = " ".join(str(note).split())[:400]
    if not note:
        return False, ""
    line = f"- ({(today or date.today()).isoformat()}) {note}"
    want = " ".join(str(section).split()).lower()
    with NOTES_LOCK:
        lines = read_notes().splitlines()
        heads = {m.group(1).lower(): (i, m.group(1)) for i, l in enumerate(lines) if (m := HEADING.match(l))}
        if want not in heads:
            want = "ideas"
        if want not in heads:
            lines += ["", "## Ideas", line]
            target = "Ideas"
        else:
            idx, target = heads[want]
            end = idx + 1
            while end < len(lines) and not HEADING.match(lines[end]) and not lines[end].startswith("# "):
                end += 1
            while end > idx + 1 and not lines[end - 1].strip():
                end -= 1  # keep the blank line before the next heading
            lines.insert(end, line)
        write_notes("\n".join(lines) + "\n")
    return True, target


def _join(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def brief(text):
    """A free, spoken reminder built from the notes (no model call)."""
    counts, recent, cur = {}, [], None
    for line in strip_comments(text).splitlines():
        if m := HEADING.match(line):
            cur = m.group(1)
            counts.setdefault(cur, 0)
        elif cur and (n := NOTE_LINE.match(line)):
            counts[cur] += 1
            recent.append((n.group(1) or "", cur, n.group(2)))
    if not counts:
        return "Your notes have no sections yet. Add some in the notes panel, then tell me what you're juggling."
    parts = [f"You're juggling {len(counts)} thing{'s' if len(counts) != 1 else ''}: {_join(list(counts))}."]
    total = sum(counts.values())
    if total == 0:
        parts.append("Nothing is saved yet. Tell me about each one and I'll keep track.")
    else:
        recent.sort(key=lambda r: r[0], reverse=True)  # newest first; stable for equal dates
        latest = "; ".join(f"{sec}: {note[:90]}" for _, sec, note in recent[:2])
        parts.append(f"{total} note{'s' if total != 1 else ''} saved. Latest, {latest}.")
    parts.append("Tap or hold space and tell me where you want to start.")
    return " ".join(parts)


def trim(history, keep_turns):
    """Drop old exchanges, always cutting at a plain user message so tool pairs stay whole."""
    starts = [i for i, m in enumerate(history) if m["role"] == "user" and isinstance(m["content"], str)]
    if len(starts) > keep_turns:
        del history[: starts[-keep_turns]]


def save_tool(names):
    return {
        "name": "save_note",
        "description": ("Append one short line to the user's notes under a section. Use it for new ideas, "
                        "decisions and status updates. It only adds; it never changes or deletes anything."),
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {"type": "string", "enum": names},
                "note": {"type": "string", "description": "One short line, in the user's own words."},
            },
            "required": ["section", "note"],
        },
    }


# --- cost meter --------------------------------------------------------------
class Usage:
    """Estimated spend per day, from the token counts the API reports."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()

    def _load(self):
        try:
            with open(USAGE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def today(self):
        blank = {"in": 0, "out": 0, "usd": 0.0, "turns": 0}
        return {**blank, **self._load().get(date.today().isoformat(), {})}

    def price(self, model):
        p = self.cfg.get("prices", {}).get(model) or PRICES.get(model) or max(PRICES.values())
        return p  # an unknown model is priced like the dearest one, to err on the safe side

    def add(self, model, usage):
        tin, tout = getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0
        p_in, p_out = self.price(model)
        with self.lock:
            data = self._load()
            key = date.today().isoformat()
            day = {"in": 0, "out": 0, "usd": 0.0, "turns": 0, **data.get(key, {})}
            day["in"] += tin
            day["out"] += tout
            day["usd"] += tin * p_in / 1e6 + tout * p_out / 1e6
            day["turns"] += 1
            data[key] = day
            for old in sorted(data)[:-60]:
                del data[old]
            tmp = USAGE_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.chmod(tmp, 0o600)
            os.replace(tmp, USAGE_PATH)


# --- the coach ---------------------------------------------------------------
def _texts(content):
    return "".join(b.text for b in content if b.type == "text").strip()


class Coach:
    def __init__(self, cfg, client=None):
        self.cfg = cfg
        self.client = client or anthropic.Anthropic()
        self.history = []
        self.lock = threading.Lock()
        self.usage = Usage(cfg)

    def system(self):
        text = strip_comments(read_notes()).strip()
        if len(text) > MAX_NOTES_CHARS:
            text = "[older notes omitted]\n" + text[-MAX_NOTES_CHARS:]
        parts = [PERSONA, "Today is " + date.today().strftime("%A %d %B %Y") + ".",
                 "<notes>\n" + text + "\n</notes>"]
        if not has_notes(text):
            parts.append(ONBOARDING)
        return "\n\n".join(parts)

    def reset(self):
        with self.lock:
            self.history.clear()

    def chat(self, text):
        """One spoken turn. Returns {"reply", "saved": [...], ...}. SDK errors propagate."""
        text = text.strip()
        if not text:
            return {"reply": "", "saved": []}

        quick = QUICK.match(text)
        if quick:  # "idea: ..." is saved straight away, with no model call at all
            ok, where = append_note("Ideas", quick.group(2))
            note = " ".join(quick.group(2).split())[:400]
            return {"reply": f"Saved to {where}." if ok else "That was empty, so I saved nothing.",
                    "saved": [{"section": where, "note": note}] if ok else [], "free": True}

        with self.lock:
            cap = float(self.cfg["daily_cap_usd"])
            if self.usage.today()["usd"] >= cap:
                return {"reply": f"I've reached today's spending cap of ${cap:.2f}. You can raise it in config.json.",
                        "saved": [], "capped": True}
            trim(self.history, int(self.cfg["keep_turns"]))
            mark = len(self.history)
            self.history.append({"role": "user", "content": text})
            saved, reply = [], ""
            try:
                system = self.system()
                tool = save_tool(sections(read_notes()))
                for _ in range(3):
                    resp = self.client.messages.create(
                        model=self.cfg["model"], max_tokens=int(self.cfg["max_tokens"]),
                        system=system, tools=[tool], messages=self.history)
                    self.usage.add(self.cfg["model"], resp.usage)
                    tool_uses = [b for b in resp.content if b.type == "tool_use"]
                    if resp.stop_reason == "refusal" or (tool_uses and resp.stop_reason != "tool_use"):
                        del self.history[mark:]  # nothing usable, and a cut-off tool call can't be replayed
                        return {"reply": "Sorry, I couldn't answer that one. Try saying it again.", "saved": saved}
                    self.history.append({"role": "assistant",
                                         "content": resp.content or [{"type": "text", "text": "(no reply)"}]})
                    say = _texts(resp.content)
                    if say:
                        reply = say
                    if not tool_uses:
                        break
                    results = []
                    for tu in tool_uses:
                        inp = tu.input or {}
                        if tu.name == "save_note":
                            ok, where = append_note(inp.get("section", ""), inp.get("note", ""))
                            if ok:
                                saved.append({"section": where, "note": " ".join(str(inp.get("note", "")).split())[:400]})
                            out = f"Saved to {where}." if ok else "Nothing to save."
                        else:
                            out = "Unknown tool."
                        results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
                    self.history.append({"role": "user", "content": results})
                else:  # still asking for tools after 3 rounds: end on an assistant turn
                    self.history.append({"role": "assistant", "content": [{"type": "text", "text": "(stopped)"}]})
            except BaseException:
                del self.history[mark:]
                raise
        if not reply:
            reply = "Saved." if saved else "(no reply)"
        return {"reply": reply, "saved": saved}


# --- HTTP --------------------------------------------------------------------
def api_error_text(e):
    """The API's own sentence ("Your credit balance is too low...") instead of the raw error dump."""
    body = getattr(e, "body", None)
    inner = body.get("error") if isinstance(body, dict) else None
    if isinstance(inner, dict) and inner.get("message"):
        return str(inner["message"])
    return str(getattr(e, "message", e))


def state_payload(coach):
    text = read_notes()
    today = coach.usage.today()
    return {
        "notes": text, "sections": sections(text), "brief": brief(text), "model": coach.cfg["model"],
        "cost": {"usd": round(today["usd"], 5), "turns": today["turns"], "cap": coach.cfg["daily_cap_usd"]},
        "notes_chars": len(text), "notes_truncated": len(strip_comments(text).strip()) > MAX_NOTES_CHARS,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "FocusCoach"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    def _send(self, status, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype != "application/json" else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _allowed(self, need_token):
        """Only this computer's own page may talk to us (blocks other sites in your browser)."""
        srv = self.server
        if self.headers.get("Host", "") not in srv.allowed_hosts:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in srv.allowed_origins:
            return False
        if need_token and not secrets.compare_digest(self.headers.get("X-Focus-Token", ""), srv.token):
            return False
        return True

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            if not self._allowed(False):
                return self._send(403, {"error": "forbidden"})
            nonce = secrets.token_urlsafe(12)
            conf = json.dumps({"lang": self.server.coach.cfg.get("lang")}).replace("</", "<\\/")
            page = (self.server.page.replace("__TOKEN__", self.server.token)
                    .replace("__NONCE__", nonce).replace("__CONF__", conf)).encode("utf-8")
            csp = ("default-src 'none'; script-src 'nonce-%s'; style-src 'nonce-%s'; connect-src 'self'; "
                   "base-uri 'none'; form-action 'none'; frame-ancestors 'none'" % (nonce, nonce))
            return self._send(200, page, "text/html", {"Content-Security-Policy": csp, "X-Frame-Options": "DENY"})
        if path == "/api/state":
            if not self._allowed(True):
                return self._send(403, {"error": "forbidden"})
            return self._send(200, state_payload(self.server.coach))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        if not self._allowed(True):
            return self._send(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 300_000:
                return self._send(413, {"error": "too large"})
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {"error": "bad request"})
        coach = self.server.coach

        if path == "/api/chat":
            text = body.get("text")
            if not isinstance(text, str) or len(text) > 4000:
                return self._send(400, {"error": "bad request"})
            try:
                result = coach.chat(text)
            except anthropic.AuthenticationError:
                return self._send(502, {"error": "Your Anthropic API key was rejected. Check the key saved for the mac command."})
            except anthropic.APIError as e:
                return self._send(502, {"error": f"Claude API error: {api_error_text(e)}"})
            result["state"] = state_payload(coach)
            return self._send(200, result)
        if path == "/api/reset":
            coach.reset()
            return self._send(200, {"ok": True})
        if path == "/api/notes":
            text = body.get("notes")
            if not isinstance(text, str) or len(text) > 200_000:
                return self._send(400, {"error": "bad request"})
            with NOTES_LOCK:
                write_notes(text if text.endswith("\n") else text + "\n")
            return self._send(200, {"state": state_payload(coach)})
        self._send(404, {"error": "not found"})


def make_server(coach, port):
    """Bind to this computer only. `port` 0 picks any free port (used by tests)."""
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        page = f.read()
    last = None
    for p in ([port] if port == 0 else range(port, port + 20)):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError as e:
            last = e
    else:
        sys.exit(f"Couldn't open a port near {port}: {last}")
    bound = httpd.server_address[1]
    httpd.coach, httpd.page, httpd.token = coach, page, secrets.token_urlsafe(24)
    httpd.allowed_hosts = {f"127.0.0.1:{bound}", f"localhost:{bound}"}
    httpd.allowed_origins = {f"http://127.0.0.1:{bound}", f"http://localhost:{bound}"}
    return httpd


def open_browser(url):
    """Chrome first (its speech recognition works out of the box), then Safari, then the default."""
    if sys.platform == "darwin":
        choice = os.environ.get("FOCUS_BROWSER")
        for app in ([choice] if choice else ["Google Chrome", "Safari"]):
            if subprocess.run(["open", "-a", app, url], capture_output=True).returncode == 0:
                return
    webbrowser.open(url)


def main():
    cfg = load_config()
    ensure_notes()
    if not ensure_api_key():
        print("!  No Anthropic API key found (environment, or ~/.phone-remote/agent.env). "
              "Chat will fail until one is set.")
    httpd = make_server(Coach(cfg), int(cfg["port"]))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"Focus coach is running: {url}")
    print(f"  model: {cfg['model']} · notes: {NOTES_PATH}")
    print("  Press Ctrl+C here (or close this window) to stop it.")
    threading.Timer(0.6, open_browser, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
