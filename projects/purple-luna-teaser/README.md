# Purple Luna — 25s vertical teaser

`purple-luna-teaser.mp4` — 1080×1920, H.264/AAC, 25.6s. Built for TikTok / Reels /
YouTube Shorts.

Every claim in it is lifted from the live site, not invented:

- headline promise → `Hero.tsx` (`"Luna answers your WhatsApp and books you out."`)
- the three stats → `HonestNumbers.tsx` (`24/7`, `Seconds`, `£0` commission), wording trimmed but not embellished
- positioning → `lib/site.ts` (`"A small studio in Brighton…"`)

Brand fidelity comes from the real assets rather than an approximation: `pl-logo.png`
straight from `purple-luna-site/public/`, the exact tokens from `globals.css`
(`--pl-ink #1a0e2e`, `--pl-purple #8b5cf6`, `--pl-peach #f4a261`, `--pl-cream #faf7f2`),
and the real Fraunces + Geist webfonts.

## How it was built

1. `build_cards.py` — writes five HTML cards and screenshots them at 1080×1920
   with headless Chromium. Using a browser (rather than ffmpeg `drawtext`) is what
   makes the real brand fonts, the italic Fraunces accent and the peach underline
   possible.
2. `assemble.sh` — slow push-in on each card via `zoompan`, 0.7s crossfades, and a
   royalty-free bed held at 0.22 gain so a voiceover can sit on top without
   re-grading.

```bash
python3 build_cards.py     # cards/card1..5.png
./assemble.sh              # purple-luna-teaser.mp4
```

## Adding the voiceover

The video is deliberately cut to work silent-with-captions (how most of the feed is
watched), but it's timed to take narration. Three takes of this script were generated
in Higgsfield and are sitting in that account's library:

| Voice | Job ID |
|---|---|
| Isla | `12c78853-70c7-4b7f-a45a-a8bae441e954` |
| Nadine | `e7c8b752-fd77-4e75-a399-09ecb214f6d1` |
| Celine | `2cdd5cc6-c6e5-465c-8747-01c6d4985b0f` |

Script as recorded:

> Your hands are full. The phone rings. And that booking just walked out the door.
> Luna answers your WhatsApp in seconds. Two in the afternoon, two in the morning,
> weekends and bank holidays included. She knows your prices, your hours, your
> services. And she books the customer while they're still interested. Every booking
> stays a hundred percent yours. Zero commission, ever. Purple Luna. A small studio
> in Brighton, building AI agents for service businesses.

Download the preferred take, then let MoneyPrinterTurbo do the assembly — it will
transcribe the narration with Whisper and generate word-timed subtitles, which is
the one thing this ffmpeg cut doesn't do:

```bash
python cli.py \
  --video-script "<the script above>" \
  --video-source local \
  --video-materials "cards/card1.png,cards/card2.png,cards/card3.png,cards/card4.png,cards/card5.png" \
  --custom-audio-file narration.wav \
  --video-aspect 9:16 --bgm-type random \
  --subtitle-enabled --font-name "BeVietnamPro-Bold.ttf" \
  --text-fore-color "#faf7f2" --stroke-color "#1a0e2e" --stroke-width 2
```

Set `subtitle_provider = "whisper"` in `config.toml` first — the Edge subtitle
provider needs a network path this build environment didn't have.

## Four AI scene images also exist

Generated for a photographic cut (busy salon with an unanswered phone; the shop dark
at 2am with the phone lit; a chat mid-reply; a full diary the next morning). They're in
the Higgsfield library under job IDs `a9e0b99c…`, `a0017d41…`, `d0a9ef6c…`, `d930ccd8…`.
They are **not** in this cut — see below.

## What blocked the photographic version

This session's egress policy denies `d8j0ntlcm91z4.cloudfront.net` and
`cdn.higgsfield.ai` (403 on CONNECT), so generated media could not be pulled into the
build container. Routing around an org policy denial isn't appropriate, so the cut was
rebuilt from assets that were legitimately available: the brand repo and the bundled
music. Downloading those four images locally and re-running `assemble.sh` against them
gives the photographic version.

## Before publishing

- **Swap the music.** The bed is one of MoneyPrinterTurbo's bundled tracks — fine for
  an internal review, but use a track with a licence you hold for a public post.
- **Check the WhatsApp CTA.** The end card carries the domain only. If the goal is
  chats rather than clicks, the live `wa.me` number from `lib/site.ts` should be on it.
- Total Higgsfield spend: **9.8 credits** (4 images at 2, three narration takes at 0.6).
