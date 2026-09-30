# Focus coach: talk your week through, with a memory

A small local page you talk to. It already knows what you're juggling (Purple Luna,
the Purple Luna clients, the GTA videos, the cat Instagram, your ideas), so you can
have a back-and-forth about what to do next, and any idea you mention gets saved
instead of lost. It's built to be cheap: a small model, one short call per turn, no
web search, no thinking.

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

The first time your notes are empty, it interviews you, one question at a time, about
each area and saves your answers.

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
mode; replies capped at 300 tokens (they're spoken anyway); only the last 12
exchanges are sent; `idea:` capture costs nothing; speech recognition and the voice
are your browser's, which are free. If the coaching feels shallow, set
`"model": "claude-sonnet-5-5"` (about twice the price).

## Where your data goes

- Your **speech** goes to your browser's speech service: Google for Chrome, Apple for
  Safari. (Your own dictation tool has the same trade-off.)
- Your **notes and the recent conversation** go to Anthropic with each message.
- Nothing else leaves your Mac. The server only listens on this computer, only
  answers requests carrying a per-run secret from its own page, and refuses other
  sites and forged hostnames, so a web page you visit can't read your notes or spend
  your budget.

## Config

Optional `~/.focus-coach/config.json`, for example:

```json
{ "model": "claude-haiku-4-5", "daily_cap_usd": 1.0, "keep_turns": 12,
  "max_tokens": 300, "lang": "en-GB", "port": 8765 }
```

`lang` sets the speech-recognition language (default: your browser's, e.g. `tr-TR`
for Turkish). `prices` overrides the built-in price table for the meter.

## If something's off

- **"Microphone is blocked"**: allow it for the page (address bar), and check System
  Settings, Privacy & Security, Microphone.
- **Safari says speech is switched off**: it needs Dictation turned on in System
  Settings, Keyboard. Chrome works without.
- **No voice**: check the "speak replies" box and your Mac's volume. The voice list
  in the page is your Mac's (better ones can be downloaded in System Settings,
  Accessibility, Spoken Content).
- **A "credit balance" message**: top up in the Anthropic console.

## Limits, honestly

- Replies are spoken once complete, not word by word.
- Memory is the notes file plus the last few exchanges. It doesn't remember old
  conversations unless something was saved.
- It only knows what's in your notes, so the more you tell it, the better it coaches.
- No reminders or scheduled nudges yet.

## Tested vs not

Tested here: 60 checks on the server (notes handling, cost meter, the conversation
loop against a fake API using the real Anthropic library, and the local-only security
checks) and 34 checks driving the real page in Chromium with a stand-in microphone
and speaker (tap and hold to talk, interrupting, Esc, saving ideas, the notes panel,
errors, a browser with no speech recognition, light and dark mode). **Not tested:**
real microphone and speech recognition, real voices, a live call to the Anthropic
API, and Safari.
