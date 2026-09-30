# Playground

A place to try out GitHub repositories — install them, audit them, run them, and
write down what they actually do and whether they're worth keeping.

Each repo gets a folder under `repos/` with review notes. The upstream code is
never committed here; the notes are.

## What each review covers

- **Verdict** — is there anything dodgy in it, and is it safe to run
- **What it actually does** — in plain terms, not the marketing version
- **Security review** — obfuscated code, telemetry, hardcoded credentials,
  outbound domains, shell injection, path traversal, dependency health, CI
- **Caveats** — the honest downsides that aren't security problems
- **Verified working** — what was actually installed, tested, and run
- **Running it yourself** — the shortest path to a working setup

## Reviews

| Repo | What it is | Verdict |
|---|---|---|
| [MoneyPrinterTurbo](repos/moneyprinterturbo/README.md) | AI short-video generator (TikTok/Reels/Shorts) | Clean — safe to run, worth using |

## Things built with them

| Project | Built with | Output |
|---|---|---|
| [Purple Luna teaser](projects/purple-luna-teaser/README.md) | Headless Chromium + ffmpeg, brand assets from `purple-luna-site` | 25.6s 1080×1920 vertical teaser |
| [phone-to-mac](projects/phone-to-mac/README.md) | Native macOS SSH + a command-locked allow-list script, optional Claude API agent (typed or spoken) | Run a fixed set of safe actions on your Mac from your phone or a natural-language agent |
| [Focus coach](projects/focus-coach/README.md) | A local page with push-to-talk, a small cheap model and a notes file | Talk your week through with something that remembers it, and never lose an idea |
