# Focus coach: talk your week through, with a memory

A small local page you talk to. It starts already knowing the areas you're juggling
(Purple Luna, the Purple Luna clients, the GTA videos, the cat Instagram, your ideas)
and the Purple Luna facts from your own repo, so you can have a back-and-forth about
what to do next, and any idea you mention gets saved instead of lost. For the areas it
doesn't know yet, it says so and asks — or you tap **Brief me** and tell it everything
in one go. It's built to be cheap: a small model, one short call per turn, no web
search, no thinking.

It is a different tool from `phone-to-mac` (which controls your Mac). This one has
**no power over your computer at all**: the only thing it can do is add lines to
your notes.

## Start it

Double-click **`Focus.command`** in Finder (Playground, projects, focus-coach), or in
Terminal:

```bash
~/Playground/projects/focus-coach/Focus.command
```

A page opens (Chrome if you have it, otherwise Safari). Click **Start**: it reads you
a free reminder of what's on your plate (built from your notes, no model call), then
you talk. Keep the Terminal window open while you use it; close it to stop.

It uses the Python and API key you already set up for `mac` (the `anthropic` package
in `phone-to-mac/.venv`, and the key in `~/.phone-remote/agent.env`).

## Talking to it

| You do | What happens |
|---|---|
| Hold **Space**, talk, let go | it hears you and answers out loud |
| Tap **Space**, talk, tap again | same, for longer stretches |
| **Space** while it's talking | cuts it off and listens |
| **Esc** | stops it talking, or cancels listening |
| Type in the box | works too (so does your own dictation tool) |
| Start a message with `idea:` | saved to Ideas **instantly, with no model call, free** |
| **Brief me** | a brain-dump mode: tell it everything on your plate and it just listens and saves, one line per thing, no coaching. Tap **Done** when finished |
| **New chat** | forgets the conversation (your notes stay) |

The hotkey works while that page is the front window. (A hotkey that works from any
app would need a small native helper; say if you want it.)

## Your notes are its memory

`~/.focus-coach/notes.md` is a plain markdown file, created from
`notes.example.md` the first time. Each `## Heading` is one area. You can edit it
in the page (**Notes**, then **Edit**) or in any editor. Each turn the coach reads it,
and it can only **add** dated lines under your headings (when you give it an idea, a
decision or a status update). It never edits or deletes anything, and it can't invent
new headings. Every save from the page keeps the previous version as `notes.md.bak`.

**Seeded from your repo, once.** On first run it fills in what's verifiable about
Purple Luna from `projects/purple-luna-teaser/README.md` (the studio, the product, the
teaser and its two "before publishing" to-dos) via `starter_notes.json`. It only adds
lines and swaps the placeholder intro; it never overwrites anything you wrote. The GTA
videos and cat Instagram are left blank on purpose — there's nothing about them in the
repo, so it asks you rather than inventing. To re-seed after editing `starter_notes.json`,
delete `~/.focus-coach/.starter-v1-applied`.

**Still-blank areas.** While an area has nothing saved, the coach nudges you to fill it
(one question at a time), and the opening reminder says which areas it knows nothing
about. Tap **Brief me** to fill several at once.

It coaches using your own working rules: attention is your scarcest resource, favour
finishing over starting, challenge ideas that don't move a current priority, rank
rather than list, and don't reopen settled decisions. Edit `PERSONA` in `server.py`
to change how it behaves.

## What it costs

Default model is `claude-haiku-4-5`, the cheapest current model, at
$1 per million input tokens and $5 per million output tokens (from the price table I
had, dated 2026-09-25; check the Anthropic pricing page).

My estimate: about 3,000 input tokens and 100 output tokens per turn, which is
roughly **a third of a cent per turn**, so about 50 turns a day is 15 to 20 cents, in
the region of $5 a month. That's an estimate from assumptions, not a measurement.
The page shows a running estimate for today (from the token counts the API reports),
and the Anthropic console has the real figure. It also stops calling the model past
`daily_cap_usd` (default $1.00) so a bug can never run up a bill.

What keeps it cheap: a small model; no tools other than saving a note; no thinking
mode; replies capped at 250 tokens (they're spoken anyway); only the last 12
exchanges are sent; `idea:` capture and the **Brief me** reminder cost nothing extra;
speech recognition is your browser's and the natural voice (below) is free. If the
coaching feels shallow, set `"model": "claude-sonnet-5-5"` (about twice the price).

## The voice

Out of the box the reply is spoken by your browser's built-in voices. On macOS the
default ones sound robotic, so the launcher tries to install **`edge-tts`** (Microsoft's
free online neural voices) into the same Python — one time, quietly, and it never
blocks the launch if it can't. When it's installed you get a much more natural voice,
picked in the dropdown next to "speak replies" (Emma, Ava, Sonia, Ryan, Andrew). If a
neural voice ever fails (you're offline, or the service is down), it falls back to the
browser voice automatically, so speech always happens.

To add or remove it yourself:

```bash
../phone-to-mac/.venv/bin/python -m pip install edge-tts   # or: uv pip install --python <that python> edge-tts
```

Honesty caveat: `edge-tts` sends the reply text to a Microsoft endpoint to synthesise
the audio (so with the natural voice on, your replies' text goes there as well as to
Anthropic — turn it off by uninstalling `edge-tts` if that matters to you). And I
could **not verify the five voice IDs** against Microsoft's live voice list from the
build environment (the network was blocked), so if one is wrong you'll get a fallback
to the browser voice rather than that voice; the current list of real voices is
`edge-tts --list-voices`.

## Where your data goes

- Your **speech** goes to your browser's speech service: Google for Chrome, Apple for
  Safari. (Your own dictation tool has the same trade-off.)
- Your **notes and the recent conversation** go to Anthropic with each message.
- If the natural voice (`edge-tts`) is on, each **reply's text** also goes to Microsoft
  to be turned into audio. Uninstall `edge-tts` to keep everything on the browser's
  built-in voices.
- Nothing else leaves your Mac. The server only listens on this computer, only
  answers requests carrying a per-run secret from its own page, and refuses other
  sites and forged hostnames, so a web page you visit can't read your notes or spend
  your budget.

## Config

Optional `~/.focus-coach/config.json`, for example:

```json
{ "model": "claude-haiku-4-5", "daily_cap_usd": 1.0, "keep_turns": 12,
  "max_tokens": 250, "lang": "en-GB", "port": 8765,
  "edge_voice": "en-US-EmmaMultilingualNeural" }
```

`lang` sets the speech-recognition language (default: your browser's, e.g. `tr-TR`
for Turkish). `edge_voice` is the default natural voice (the dropdown overrides it per
device). `prices` overrides the built-in price table for the meter.

## If something's off

- **"Microphone is blocked"**: allow it for the page (address bar), and check System
  Settings, Privacy & Security, Microphone.
- **Safari says speech is switched off**: it needs Dictation turned on in System
  Settings, Keyboard. Chrome works without.
- **No voice**: check the "speak replies" box and your Mac's volume. With `edge-tts`
  installed the dropdown lists the natural voices; without it, the list is your Mac's
  built-in voices (better ones can be downloaded in System Settings, Accessibility,
  Spoken Content).
- **Robotic voice**: install `edge-tts` (see "The voice" above); the launcher normally
  does this for you on first run.
- **A "credit balance" message**: top up in the Anthropic console.

## Limits, honestly

- Replies are spoken once complete, not word by word.
- Memory is the notes file plus the last few exchanges. It doesn't remember old
  conversations unless something was saved.
- It only knows what's in your notes, so the more you tell it, the better it coaches.
- No reminders or scheduled nudges yet.

## Tested vs not

Tested here: 81 checks on the server (notes handling, the starter-notes seeding, the
gaps nudge, briefing mode, the free reminder, cost meter, the conversation loop
against a fake API using the real Anthropic library, the `/api/tts` voice endpoint,
and the local-only security checks) and 45 checks driving the real page in Chromium
with a stand-in microphone and speaker (tap and hold to talk, interrupting, Esc,
saving ideas, Brief me, the notes panel, errors, a browser with no speech
recognition, light and dark mode, and the natural-voice path with its fallback).
**Not tested:** real microphone and speech recognition, the actual sound of the
neural voices (the voice IDs are unverified — see "The voice"), a live call to the
Anthropic API, and Safari.
