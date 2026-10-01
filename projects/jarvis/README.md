# Jarvis — what needs you, across Claude

A private claude.ai page that sits on top of your Claude workspace. Open it and it shows,
live, what's waiting on you across your Claude Code sessions, what's working or just
finished, and the routines running for you. Tap **Brief me** and it reads that out loud. Ask
it a question (typed or dictated) and it answers on screen and out loud.

**Live page:** https://claude.ai/artifact/Q2drES2Moj7B5PVUHtxCUV (private to you)

## What it can and can't do

| | |
|---|---|
| Reads | Your Claude Code sessions (`list_sessions`) and routines (`list_triggers`) through the **Claude Code Remote** connector, as you, with your sign-in. Nothing else. |
| Can't | Act on anything. It never sends, starts, archives or changes a session or routine. |
| Freshness | Reads live when you open it and refreshes itself every couple of minutes while open (routines every 10). The date and "updated N min ago" come from your own clock. |
| Brief me | Built on the page from the live data, so it's instant and free (no model call). |
| Ask | Sends your question plus a short text summary of what the page shows to Claude (the `sample` capability), using a small amount of *your* Claude usage per question. Your routines' instructions are never shown or sent, only their names and times. |
| Your voice | claude.ai blocks the microphone inside pages, so you speak through your keyboard's dictation (the 🎤 key on iPhone; on a Mac usually Fn pressed twice). |
| The voice | Your browser's built-in voices; the page picks the most natural one for your language and lets you change it. Novelty voices are hidden. |

The first time you open it, claude.ai asks you to allow the page to read Claude Code Remote,
and the first question asks to allow it to use Claude. If you decline, the page says so and
Brief me still works.

## Rules it uses

- **Waiting on you:** a session that's blocked on you, ready for your review, or whose last
  turn failed, in the last 14 days and not archived. A session's live status wins over its
  last summary, so one you've already answered moves to *Working* straight away.
- **Working & just finished:** running now, or finished in the last 3 days.
- **Projects:** artifacts linked to your recent sessions (claude.ai links only).
- It reads your newest 100 sessions and first 100 active routines. If there are more, it
  says so on the page, in the brief and to Claude, rather than implying nothing else exists.

## Changing it

The page is `jarvis.html` (published as-is; the platform adds the `<head>`). To change it,
edit the file and republish it to the same URL from a Claude session with the Artifact tool,
keeping its capabilities:
`{"mcp": {"servers": [{"server": "Claude Code Remote", "tools": ["list_sessions", "list_triggers"]}]}, "sample": {}}`.

Test it first:

```bash
pip install playwright
python3 test_jarvis_ui.py      # 67 checks; set JARVIS_CHROME to a Chromium binary if needed
```

The test loads the real page in Chromium with a stand-in for claude.ai's runtime serving
made-up sessions (including hostile titles and broken links), and a speech engine stand-in
that queues, starts, ends and cancels like a real one.

## Tested vs not

Tested: 67 checks in real Chromium (live data, classification on real-shaped payloads,
plain-text rendering of hostile titles, link allow-listing, the brief, asking and follow-ups,
every error state, losing and regaining access, the iPhone speech unlock, light/dark,
phone width). Reviewed twice by independent reviewers (29 issues found and fixed).

**Not tested:** inside the real claude.ai viewer (its consent prompts, the connector's exact
answer from inside a page), real voices, and a real iPhone. If a section ever says your
data "came back in a format Jarvis doesn't recognise", the connector's answer differs from
what the page expects; that's a quick fix.
