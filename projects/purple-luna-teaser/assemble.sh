#!/usr/bin/env bash
# Assemble the Purple Luna teaser: slow push-in on each brand card, crossfades
# between them, bundled royalty-free bed underneath.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
CARDS="$DIR/cards"
WORK="$DIR/work"
MUSIC="${MUSIC:-$DIR/../mpt/resource/songs/output013.mp3}"
OUT="$DIR/purple-luna-teaser.mp4"
mkdir -p "$WORK"

FPS=30
T=0.7                       # crossfade length
DUR=(5.2 4.4 6.2 7.0 5.6)   # per-card screen time

# 1. Still -> moving clip. Render at 2x then zoompan down to 1080x1920 so the
#    slow push-in stays sharp instead of resampling a 1080p source.
for i in 1 2 3 4 5; do
  d="${DUR[$((i-1))]}"
  frames=$(python3 -c "print(int($d*$FPS))")
  ffmpeg -y -loglevel error -loop 1 -i "$CARDS/card$i.png" \
    -vf "scale=2160:3840,zoompan=z='min(zoom+0.00035,1.09)':d=$frames:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=$FPS,format=yuv420p" \
    -t "$d" -c:v libx264 -preset medium -crf 18 -r $FPS "$WORK/clip$i.mp4"
done

# 2. Chain the crossfades. Each offset is the running total minus the fades
#    already consumed, otherwise the tail drifts later with every transition.
python3 - "$WORK" "$T" "${DUR[@]}" <<'PY' > "$WORK/xfade.txt"
import sys
work, t, *durs = sys.argv[1], float(sys.argv[2]), *map(float, sys.argv[3:]),
parts, prev, elapsed = [], "0:v", 0.0
for i in range(1, len(durs)):
    elapsed += durs[i-1] - t
    label = f"x{i}"
    parts.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={t}:offset={elapsed:.3f}[{label}]")
    prev = label
print(";".join(parts) + f";[{prev}]format=yuv420p[v]")
PY
FILTER="$(cat "$WORK/xfade.txt")"

TOTAL=$(python3 -c "d=[${DUR[0]},${DUR[1]},${DUR[2]},${DUR[3]},${DUR[4]}];print(round(sum(d)-4*$T,2))")
echo "timeline: ${TOTAL}s"

# 3. Mux with the music bed: gentle fade in/out, held well under a voiceover
#    level so narration can be dropped on top later without re-grading.
ffmpeg -y -loglevel error \
  -i "$WORK/clip1.mp4" -i "$WORK/clip2.mp4" -i "$WORK/clip3.mp4" \
  -i "$WORK/clip4.mp4" -i "$WORK/clip5.mp4" -i "$MUSIC" \
  -filter_complex "$FILTER;[5:a]volume=0.22,afade=t=in:st=0:d=1.5,afade=t=out:st=$(python3 -c "print($TOTAL-2)"):d=2,atrim=0:$TOTAL[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart -t "$TOTAL" "$OUT"

echo "wrote $OUT"
