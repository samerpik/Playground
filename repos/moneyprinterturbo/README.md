# MoneyPrinterTurbo — review notes

Upstream: https://github.com/harry0703/MoneyPrinterTurbo
Reviewed at commit `1f9f19c` (v1.3.4), 16 Aug 2026. Author: harry0703. Licence: MIT.

## Verdict

**Nothing dodgy found.** It is what it says it is: an open-source short-video
generator. It is genuinely well-built — 545 passing tests, a documented security
policy, and several places where the author has deliberately chosen the safe
default. Safe to run. See [Caveats](#caveats) for the things that are worth
knowing but are not security problems.

## What it actually does

You give it a topic (e.g. "5 facts about deep sea fish"). It then, in one pipeline:

1. **Writes a script** — sends your topic to an LLM of your choosing.
2. **Picks search keywords** from that script — again via the LLM.
3. **Downloads stock footage** matching those keywords from Pexels / Pixabay /
   Coverr. You can also point it at your own local images and clips instead.
4. **Narrates it** — text-to-speech. The default (Microsoft Edge TTS) is free and
   needs no key.
5. **Generates subtitles** — transcribes the narration locally with
   faster-whisper, so word timings line up with the voice.
6. **Adds background music** from the 30 royalty-free tracks bundled in `resource/songs/`.
7. **Renders** with ffmpeg to a 1080x1920 vertical (or 16:9, or 1:1) MP4.

The output is aimed at TikTok / Reels / YouTube Shorts. Hence the name — the
premise is churning out faceless short-form content at volume. There is an
optional feature to auto-post the results to those platforms via a third-party
service (`upload-post.com`), **off by default**.

Four ways to drive it: a Streamlit **WebUI** (the main one), a **CLI**, a
**REST API**, and an **AI agent skill**.

## Why it's Chinese-first

The author is Chinese and the primary README is Simplified Chinese, but this is
not a China-only tool. The UI ships in 9 languages including English. The
Dockerfile defaults to Aliyun/Tsinghua package mirrors purely because they're
faster from mainland China — pass `--build-arg DOCKER_BUILD_MIRROR=default` to
use standard Debian/PyPI mirrors instead. Code comments are largely in Chinese;
the code itself is normal, readable Python.

## Security review

Checked specifically for the things that make a repo dodgy:

| Check | Result |
|---|---|
| Obfuscated code (`eval`/`exec` on remote data, base64 payloads) | **None.** Every `base64` use decodes audio returned by a TTS API. The only `exec` calls are in the test suite, loading the local WebUI module. |
| Telemetry / phoning home with your data | **None.** No analytics, no Sentry, no device fingerprinting. |
| Hardcoded credentials or backdoor endpoints | **None.** `config.example.toml` ships with every key field empty. |
| Suspicious outbound domains | **None.** Every domain is a documented, expected service: OpenAI, DeepSeek, Moonshot, Gemini, Groq, Azure, ElevenLabs, Pexels, Pixabay, Coverr, etc. |
| Shell injection | Clean. All `subprocess` calls pass argument lists, never `shell=True`. |
| Path traversal | Actively defended — `app/utils/file_security.py` resolves user-supplied paths with `realpath` + `commonpath`, which correctly handles symlinks and `../`. |
| Dependencies | 21 pinned, mainstream packages (moviepy, streamlit, fastapi, openai, litellm...). No typosquats. Locked via `uv.lock`. |
| CI/CD workflows | Standard test/lint. No secret exfiltration, no `pull_request_target` misuse. |

**Signs of a careful author, not a careless one:**

- `tls_verify = true` by default, with a comment saying only disable it temporarily.
- Streamlit usage stats explicitly disabled.
- Docker publishes to `127.0.0.1:8501` — bound to localhost, not exposed to the network.
- `config.toml` is written `0600` (owner read/write only) since it holds your API keys.
- A real `SECURITY.md` with a private disclosure process.

**The only outbound call it makes unprompted** is a once-per-12-hours check
against `api.github.com` for a newer release. It sends no data about you — just
a plain GET for the latest version tag.

## Caveats

These are worth knowing, but none are security issues:

- **Affiliate links.** The README and the Kimi config URL carry the author's
  referral tracking codes, and the README carries paid sponsor placements. Normal
  for a project of this size, but it does mean sponsor recommendations are not
  neutral advice.
- **It costs money to run properly.** You need an LLM API key (steps 1–2) and a
  Pexels/Pixabay key (step 3). Both have free tiers. The TTS default is free.
- **Content quality is what you'd expect.** LLM script over generic stock footage.
  Useful as a pipeline; it won't produce anything distinctive on its own.
- **Platform terms of service.** TikTok/YouTube have rules about bulk, low-effort,
  automated uploads. Auto-posting at volume risks your accounts, not your machine.
- **Stock footage licences.** Pexels/Pixabay are permissive, but attribution and
  commercial-use terms are still yours to honour.

## Verified working

Installed and run on this machine:

- `uv sync --frozen` — clean install, Python 3.11.
- Full test suite: **545 passed, 11 skipped, 4155 subtests passed** in 46s.
- WebUI boots and serves healthy on `127.0.0.1:8501`.
- **End-to-end render succeeded** — produced a valid 8s 1080x1920 H.264/AAC MP4
  from local images plus an audio track, no API keys used.

One environment-specific failure, not a repo bug: **Edge TTS times out here**,
because it opens a WebSocket to Microsoft and this sandbox's proxy only permits
HTTPS. On a normal machine it works. Workarounds: use a different TTS provider,
or supply your own audio with `--custom-audio-file`.

## Running it yourself

```bash
git clone https://github.com/harry0703/MoneyPrinterTurbo.git
cd MoneyPrinterTurbo
uv sync --frozen                 # or: pip install -r requirements.txt
cp config.example.toml config.toml
# edit config.toml: set an LLM api key and pexels_api_keys
./webui.sh                       # webui.bat on Windows
```

ffmpeg must be on your PATH. Then open http://127.0.0.1:8501.

Docker is the lower-effort route:

```bash
docker compose up
```

CLI, no keys needed, using your own footage and audio:

```bash
python cli.py \
  --video-script "your script here" \
  --video-source local --video-materials "clip1.mp4,photo.png" \
  --custom-audio-file narration.wav \
  --video-aspect 9:16 --bgm-type random
```

## Recommendation

Worth using. Get a free Pexels key and an LLM key, start with the WebUI, and keep
auto-posting switched off until you've seen what the output looks like.
