#!/usr/bin/env bash
# Build the tracked FastVC README/landing walkthrough from validated frames.
set -euo pipefail
cd "$(dirname "$0")/.."

FRAMES_DIR="docs/demo/frames"
MANIFEST="$FRAMES_DIR/manifest.txt"
OUT="${OUT:-docs/demo/fastvc-walkthrough.gif}"
LANDING="static/product-demo.gif"
DELAY="${DELAY:-170}"
WIDTH="${WIDTH:-1100}"

if [[ ! -s "$MANIFEST" ]]; then
  echo "No validated frame manifest. Run scripts/capture_demo.py first." >&2
  exit 1
fi

mapfile -t names < <(sed '/^[[:space:]]*$/d' "$MANIFEST")
frames=()
for name in "${names[@]}"; do
  frame="$FRAMES_DIR/$name"
  if [[ ! -f "$frame" ]]; then
    echo "Validated frame is missing: $frame" >&2
    exit 1
  fi
  frames+=("$frame")
done

if (( ${#frames[@]} < 10 )); then
  echo "Refusing to build a product tour from fewer than 10 clean frames." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")" "$(dirname "$LANDING")"

if command -v convert >/dev/null 2>&1; then
  convert -loop 0 -delay "$DELAY" -resize "${WIDTH}x" \
    "${frames[@]}" -layers Optimize "$OUT"
elif command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -y -framerate "$(awk "BEGIN{print 100/$DELAY}")" \
    -f concat -safe 0 \
    -i <(for frame in "${frames[@]}"; do printf "file '%s/%s'\n" "$PWD" "$frame"; done) \
    -vf "scale=${WIDTH}:-1:flags=lanczos" "$OUT"
else
  echo "ImageMagick or ffmpeg is required." >&2
  exit 1
fi

cp "$OUT" "$LANDING"
echo "Wrote $OUT ($(du -h "$OUT" | cut -f1), ${#frames[@]} frames)"
echo "Wrote $LANDING (landing-page copy)"
