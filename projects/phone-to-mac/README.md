# phone-to-mac — let your phone run a fixed set of actions on your Mac

A deliberately small, safe way to make your Mac do things from your phone
(via Siri / a Shortcut): open a URL or a search, open/close an app, change
volume, lock, sleep, screenshot, and — with confirmation — restart or shut
down.

It is the **safe alternative** to a bespoke remote-control agent. There is no
custom daemon, no persistence tricks, no antivirus exclusions, no self-update,
and no arbitrary-command channel. It uses only macOS's built-in SSH plus one
small allow-list script.

> Status: written and syntax-checked on Linux; **not yet run on macOS**. The
> shell is bash 3.2-safe (the version macOS ships). You need to test it on your
> Mac — see [Testing checklist](#testing-checklist). A few items carry honest
> caveats, flagged inline.

## How it works (three moving parts, all native)

```
iPhone Shortcut ──SSH──▶ macOS Remote Login (sshd) ──forced command──▶ dispatch.sh
   "volume 30"              (built into macOS)         (fixed allow-list)
```

1. **Remote Login (SSH)** — macOS's built-in server. Nothing to install.
2. **A pinned key** — your phone's SSH public key is added to
   `~/.ssh/authorized_keys` with a `command="…/dispatch.sh",restrict` prefix.
   That prefix is the whole security model: **whatever command the phone sends,
   sshd throws it away and runs `dispatch.sh` instead.** The requested string is
   handed to the script in `$SSH_ORIGINAL_COMMAND`.
3. **`dispatch.sh`** — parses that string as `<action> <argument>`, checks the
   action against a fixed `case` allow-list, validates the argument, and runs a
   native command with the argument as a single quoted value.

## Why this is safe

- **Command-locked key.** Even if the phone's private key leaked, the thief can
  only invoke `dispatch.sh`. They cannot get a shell, run `scp`, forward ports,
  or run any command outside the allow-list. `restrict` disables pty, agent/port/
  X11 forwarding.
- **No shell, no eval.** The argument is never passed to a shell. Tested:
  sending `rm -rf /` is simply rejected as `unknown action: rm`; sending
  `openurl "; rm -rf ~"` is passed to `open` as one literal string.
- **Per-action validation.** URLs must be `http(s)://`; volume must be 0–100;
  app names are charset-restricted; power actions require a literal `confirm`.
- **No file operations, no `type text`, no keystroke injection** (see
  [What I left out](#what-i-left-out-and-why)).
- **Instant, local removal.** Delete one line from `authorized_keys` (or run
  `remove.sh`), or turn Remote Login off — access is gone immediately. It does
  not depend on the phone or any server cooperating.
- **Audit log.** Every call is appended to `~/.phone-remote/activity.log`
  (timestamp, action, argument, result), so you can see exactly what ran.

## Threat model — what this does NOT protect against

Be clear-eyed:

- **Your phone is now a key to your Mac.** Anyone who can run your Shortcut
  (unlocked phone, "Hey Siri" if you allow it on the lock screen) can run these
  actions. Lock your phone; consider disabling Siri-on-lock-screen.
- **Whoever controls the network path can reach sshd.** Keep the Mac's SSH on
  your LAN/VPN, not exposed to the public internet. Do not port-forward 22.
- **`open -a` can launch any installed app**, and `openurl` can open any web
  page. That is the intended power; it is not arbitrary code execution, but it
  is not nothing.
- **`screenshot` can see your screen.** It is in the allow-list; drop it if you
  don't want that capability to exist at all.

## The allow-list

| Command sent from phone | Does |
|---|---|
| `ping` | returns the Mac's name (health/online check) |
| `openurl https://…` | opens the URL (http/https only) |
| `search <terms>` | opens a Google search |
| `youtube <terms>` | opens YouTube search results |
| `app-open <name>` | opens an app by name |
| `app-close <name>` | quits it (graceful, then force) |
| `volume <0-100>` | sets output volume |
| `mute` / `unmute` | mutes / unmutes |
| `playpause` | play/pause **Music or Spotify** (see caveat) |
| `lock` | locks the screen |
| `sleep` | sleeps the Mac |
| `restart confirm` | restarts (needs the word `confirm`) |
| `shutdown confirm` | shuts down (needs the word `confirm`) |
| `screenshot` | returns a base64 PNG (needs permission, see caveat) |

Anything else → `ERR unknown action`.

## Install (on the Mac)

```bash
cd projects/phone-to-mac
./install.sh          # copies dispatch.sh into ~/.phone-remote and asks for the phone's public key
```

Then enable **System Settings → General → Sharing → Remote Login = ON**, and set
*Allow access for* to your user only.

## Check it works (runbook)

Run the checker on the Mac after installing:

```bash
cd projects/phone-to-mac
./doctor.sh
```

It verifies Remote Login, the dispatcher, the pinned key, a `ping`, and a
reversible volume change, then lists the manual checks. Paste its output if
anything fails.

**First-run permission prompts are normal.** The first time an action drives
another app, macOS shows a one-time prompt — approve it once and it sticks:

- `app-open` / `app-close`, `playpause`, `restart` / `shutdown` → **Automation**
- `screenshot` → **Screen Recording**
- `volume`, `openurl`, `lock`, `sleep`, `ping` → no prompt

Approve these while sitting at the Mac (run the command in Terminal or via the
agent), because the prompt appears on the Mac's screen, not on the phone.

Order to reach "working end to end":

1. `./install.sh` (and turn on Remote Login)
2. `./doctor.sh` → passes at the top
3. `python3 agent.py --dry-run "lock the mac"` → shows the action, runs nothing
4. `python3 agent.py "lock the mac"` → screen locks ← **agent path proven**
5. iOS Shortcut sending `ping` → `OK <mac name>` ← **phone path proven**

## Set up the phone (iOS Shortcut)

> UI wording moves between iOS versions; adapt as needed. I'm describing the
> "Run Script Over SSH" action — verify it exists on your iOS.

1. New Shortcut → add **Run Script Over SSH**.
2. Host = your Mac's LAN IP, Port 22, User = your macOS username.
3. Authentication = **SSH Key**. Let it generate a key, then copy the **public
   key** it displays.
4. Run `./install.sh` on the Mac and paste that public key when asked (or add it
   by hand — see below).
5. Set the **Script** field to a command, e.g. `ping`. Run it; you should get
   `OK <your Mac's name>`.
6. Name the Shortcut (e.g. "Lock the Mac" with script `lock`) so you can say
   *"Hey Siri, Lock the Mac."* For search, add a **Dictate Text** / **Ask for
   Input** step and set the script to `search ` + that text.

Adding the key by hand instead of via `install.sh`:

```
command="/Users/YOU/.phone-remote/dispatch.sh",restrict ssh-ed25519 AAAA...yourphone
```

(one line in `~/.ssh/authorized_keys`; replace `YOU` and the key).

## Driving it with an AI agent (Claude API)

The Shortcut runs *fixed* commands. If you'd rather talk naturally ("mute
everything and open lofi on YouTube") and have a model choose the actions,
`agent.py` puts Claude in front of the **same dispatcher** — nothing else touches
the machine.

```
you: "set volume to 20 and open youtube lofi beats"
        │
        ▼
   agent.py → Claude picks actions, ONLY from the allow-list enum
        │        {volume 20}  {youtube lofi beats}
        ▼
   the same dispatch.sh (local, or SSH to another machine)
```

Why it stays safe with a model in the loop:

- Claude can only pick from the fixed action enum (a strict tool schema) — it
  can't invent an action or produce shell.
- Every action is re-checked here and every argument is re-validated in
  `dispatch.sh`. Worst case, a confused (or prompt-injected) model picks a
  different *harmless* action; it can't read files or run commands.
- `restart` / `shutdown` require an interactive confirmation.
- Screen contents are never fed back to the model. Web pages are only read in the
  spoken modes (talk / speak) when web search is on; typed `mac ...` and the phone
  path never see web content. See [Talk mode](#talk-mode-a-spoken-conversation)
  for what changes when it is on.

Setup:

```bash
cd projects/phone-to-mac
pip install -r requirements.txt          # just the `anthropic` SDK
export ANTHROPIC_API_KEY=sk-ant-...       # your key; never commit it
cp config.example.json config.json        # edit targets; delete the 'office' example until you add a PC

python3 agent.py --dry-run "lock the mac"          # shows the action, runs nothing
python3 agent.py "set volume to 20 and open youtube lofi beats"
python3 agent.py --yes "restart"                    # -y skips the confirm prompt
```

**Cost / model:** it defaults to `claude-opus-5-5`. `claude-sonnet-5-5` is the
cheaper option that works with the current settings (about half the per-token
price in the price table I had; check Anthropic's pricing page for today's
numbers). Switch with the `"model"` field in `config.json`, or try one run with
`--model claude-sonnet-5-5`. **Not Haiku:** `claude-haiku-4-5` rejects the
adaptive-thinking and effort settings this agent sends, so it needs code changes
first.

**Wiring to voice later:** the phone Shortcut can `ssh` into the Mac and run
`python3 .../agent.py "<dictated text>"`, so Siri dictation becomes the input.
Get the CLI behaving first.

Status: `agent.py` is syntax-checked and its allow-list is verified to match
`dispatch.sh`. It's **not yet run against the live API** (needs your key + Mac).

### Make it a one-word command

Typing the venv path every time is tedious, and a key set with `export` only
lasts one terminal session. Fix both once — store the key in a private file and
add a `mac` shell function:

```bash
mkdir -p ~/.phone-remote
printf 'ANTHROPIC_API_KEY=%s\n' "$ANTHROPIC_API_KEY" > ~/.phone-remote/agent.env  # grabs the key from your current shell
chmod 600 ~/.phone-remote/agent.env

cat >> ~/.zshrc <<'EOF'

# phone-to-mac — type: mac lock the screen
mac() {
  ( set -a; source ~/.phone-remote/agent.env; set +a
    ~/Playground/projects/phone-to-mac/.venv/bin/python ~/Playground/projects/phone-to-mac/agent.py "$@" )
}
EOF
source ~/.zshrc
```

Adjust the two paths if your clone lives elsewhere. Then just:

```bash
mac set the volume to 20
mac --dry-run lock the screen
```

The key file is owner-only (`chmod 600`) and never leaves your Mac; rotate it
anytime in the Anthropic console.

## Talk mode (a spoken conversation)

`--talk` turns the agent into a back-and-forth conversation: it remembers what
you said earlier in the session and **speaks every reply** (macOS `say`). Actions
still work mid-conversation ("mute it", "open Spotify"), through the same
allow-list.

```bash
# one-time: give it a short name (any name you like)
echo "alias jarvis='mac --talk'" >> ~/.zshrc && source ~/.zshrc

jarvis                                   # start talking
jarvis --model claude-sonnet-5-5         # same, on a different model
```

Speak into your dictation tool (or type) and press Enter. It answers aloud and
prints the reply and how long it took.

| You do | What happens |
|---|---|
| say/type `goodbye` | ends the session |
| say/type `reset` | forgets the conversation, starts fresh |
| press Enter on a blank line | cuts off whatever it is saying |
| Ctrl+C (at the prompt) | quits |

Notes:

- **No memory between sessions.** Each `jarvis` starts blank.
- **Live web answers are OFF by default** (they made replies slow and cost extra).
  Turn them on with `"web_search": true` in `config.json`. Then live questions
  (fixtures, weather, news) get a spoken answer and it prints the search it ran.
  Web search costs about $10 per 1,000 searches on top of normal usage (figure
  from the API docs I had; check current pricing), capped at 3 per question, and
  needs web search switched on for your Anthropic account (Console settings).
- **Web pages are untrusted input** (when web search is on). Once it has read the web, opening any link
  needs your y/N first, and `--yes` doesn't skip that. Reason: a booby-trapped page
  can try to steer a reply, and opening a URL is the one action that leads
  somewhere you don't control. Everything else in the allow-list is unchanged.
- **Silent Mac = silent assistant.** It warns you at start-up if the sound is
  muted or at zero.
- **Better voice:** System Settings, Accessibility, Spoken Content, System Voice,
  Manage Voices (menu names vary by macOS version) has higher-quality voices.
  `say -v '?'` lists installed voices with their languages. Put the name in
  `config.json` as `"voice"`, and an optional speed as `"rate"` (words/minute).
  Other talk-mode keys: `"web_search"` (true/false), `"web_search_max_uses"`
  (default 3) and `"location"` (optional, e.g. `{"city": "Brighton", "country":
  "GB", "timezone": "Europe/London"}` for local results).
- **Limits of this version:** it starts speaking when the whole reply is ready
  (not word by word), you can't interrupt by talking over it, and speech input is
  whatever dictation tool you already use. Fully hands-free listening needs a
  local speech-to-text model plus microphone permission, and headphones so it
  doesn't hear itself.

## Removing a device instantly

```bash
./remove.sh                              # strips the key line (keeps a backup)
# or, to cut ALL ssh access right now:
sudo systemsetup -setremotelogin off
```

## What I left out, and why

- **`type text` (arbitrary keystroke injection).** This was the most dangerous
  item in the original request. Free-form typing into the focused app can drive
  anything — password fields, terminals, banking pages. It is deliberately not
  here. If you truly need it, we should scope it to a few *fixed* strings, never
  free text.
- **Antivirus/Defender exclusions, hidden persistence, self-update, self-delete.**
  Those belong to the malware playbook, not to a tool you run on your own machine
  in the open. Not included, by design.

## Honest caveats / things to verify on macOS

- **`playpause` is app-specific.** macOS has no clean CLI for the system-wide
  media key, so this controls Music or Spotify only. A true media key needs a
  small helper binary — out of scope for v1.
- **`screenshot` needs Screen Recording permission** granted to whatever runs
  sshd. Until then it may fail or return black. macOS may also need Automation/
  Accessibility permission the first time `osascript` drives an app
  (volume/app-close/power) — you'll get a system prompt; approve it once.
- **`lock`** uses the long-standing `CGSession -suspend` path. I believe it's
  still valid on current macOS but couldn't verify from here — confirm on your
  machine.
- **`restart`/`shutdown`** use System Events (no admin needed) and are graceful;
  an app with unsaved work can block them with a dialog.
- Wake-on-LAN and RGB from the original request are **not** Mac-agent concerns —
  they belong to the hub layer if you decide to build one later.

## Testing checklist

Run on the Mac after install:

- [ ] `ping` returns your Mac's name
- [ ] `openurl https://example.com` opens Safari
- [ ] `volume 20` then `volume 60` changes volume (approve the osascript prompt)
- [ ] `lock` locks the screen
- [ ] `app-open Calculator` / `app-close Calculator`
- [ ] `search test` / `youtube test`
- [ ] `sleep`
- [ ] `screenshot` (after granting Screen Recording)
- [ ] confirm `shutdown` **without** `confirm` is refused, `shutdown confirm` works
- [ ] `remove.sh` then a phone command fails with a permission error
