# Jarvis — what needs you, across Claude

A private claude.ai page that sits on top of your Claude workspace. Open it and it shows
what's waiting on you across your Claude Code sessions, what's working or just finished, and
the routines running for you. Tap **Brief me** and it reads that out loud. Ask it a question
(typed or dictated) and it answers on screen and out loud.

**Live page:** https://claude.ai/artifact/Q2drES2Moj7B5PVUHtxCUV (private to you)

## What it can and can't do

| | |
|---|---|
| Routines | Read live (`list_triggers` on the **Claude Code Remote** connector, as you), re-read every 10 minutes while open. |
| Sessions | claude.ai doesn't let pages list sessions (`list_sessions` comes back `blocked_by_policy`). So the **Jarvis morning refresh** routine lists them every day at 07:54 London time and saves a short copy into the page's own storage, readable only by you. The page shows "Sessions as of 07:55", and the brief says how old the copy is when it's more than 15 minutes old. |
| Refresh sessions | The button (or typing/saying "refresh" in Ask) runs that routine now; the new copy appears by itself a minute or two later. If claude.ai won't let the page start a routine, the page says how to run it from a Claude chat instead. |
| Can't | Change anything. The one thing it can start is the refresh routine, which only reads your sessions and writes the copy. |
| Dates | The date and "N min ago" come from your own clock. |
| Brief me | Built on the page from the live data, so it's instant and free (no model call). |
| Ask | Sends your question plus a short text summary of what the page shows to Claude (the `sample` capability), using a small amount of *your* Claude usage per question. Your routines' instructions are never shown or sent, only their names and times. |
| Your voice | claude.ai blocks the microphone inside pages, so you speak through your keyboard's dictation (the 🎤 key on iPhone; on a Mac usually Fn pressed twice). |
| The voice | Your browser's built-in voices; the page picks the most natural one for your language and lets you change it. Novelty voices are hidden. |

The first time you open it, claude.ai may ask you to allow the page to use Claude Code Remote,
and the first question asks to allow it to use Claude. If you decline, the page says so and
Brief me still works.

**The refresh routine** (`trig_01C343Px5rSu7J1ESJY5mBuX`) is a normal routine in your claude.ai
routines list: pause, reschedule or delete it there. Each run is a short Claude Code session on
your usage. If it's renamed, the page's Refresh button can't find it and says so.

**Outcome (2 Oct 2026):** the claude.ai routines editor offers no connectors on this account,
so the refresh routine couldn't list sessions (4 runs, nothing saved). The routine was deleted.
On this account Jarvis can't show sessions: it shows routines (live) and does the brief. For
what's waiting on you, use the session list in the Claude app.

## Rules it uses

- **Waiting on you:** a session that's blocked on you, ready for your review, or whose last
  turn failed, in the last 14 days and not archived. A session's live status wins over its
  last summary, so one you've already answered moves to *Working* straight away.
- **Working & just finished:** running now, or finished in the last 3 days.
- **Projects:** artifacts linked to your recent sessions (claude.ai links only).
- The routine copies your newest 100 sessions (those updated in the last 14 days, plus any
  still working) and the page reads the first 100 active routines. If there are more, it
  says so on the page, in the brief and to Claude, rather than implying nothing else exists.

## Changing it

The page is `jarvis.html` (published as-is; the platform adds the `<head>`). To change it,
edit the file and republish it to the same URL from a Claude session with the Artifact tool,
keeping its capabilities:
`{"mcp": {"servers": [{"server": "Claude Code Remote", "tools": ["list_triggers", "fire_trigger"]}]}, "sample": {}, "db": {"rules": [{"path": "jarvis", "read": "owner", "write": "owner"}]}}`.
The sessions copy lives at `jarvis/sessions` as `{refreshed_at, has_more, sessions: [...]}`.

Test it first:

```bash
pip install playwright
python3 test_jarvis_ui.py      # 89 checks; set JARVIS_CHROME to a Chromium binary if needed
```

The test loads the real page in Chromium with a stand-in for claude.ai's runtime: made-up
routines, a made-up sessions copy in storage (including hostile titles and broken links), a
refresh routine that delivers a new copy, and a speech engine stand-in that queues, starts,
ends and cancels like a real one.

## Tested vs not

Tested: 89 checks in real Chromium (classification on real-shaped payloads, plain-text
rendering of hostile titles, link allow-listing, the brief, asking and follow-ups, the sessions
copy and its age, Refresh sessions and every way it can fail, losing and regaining access, a
dropped storage connection, the iPhone speech unlock, light/dark, phone and mid widths). Earlier
versions were reviewed twice by independent reviewers (29 issues found and fixed).

In the real claude.ai viewer: the page, routines, Brief me and Ask were checked before this
version. **Not yet seen in the real viewer:** the sessions copy and the Refresh button (whether
claude.ai lets a page start a routine), real voices, and a real iPhone.
