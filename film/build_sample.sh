#!/bin/sh
# 开场 10 秒小样一键重建（Mac）：sh films/aistudio/build_sample.sh [preview]
#   preview：540×960、每 20 帧渲一张，叠上字幕拼成总览图（看构图用，十几秒出结果）
#   不带参数：1080×1920 全帧渲染 → 配乐 → 合成 mp4
set -e
HERE=$(cd "$(dirname "$0")" && pwd); LIB=$(cd "$HERE/../.." && pwd); cd "$LIB"
PY=${PY:-$( [ -x "$LIB/.venv/bin/python" ] && echo "$LIB/.venv/bin/python" || command -v python3 )}
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
OUT=${OUT:-$LIB/out/aistudio/sample}
# Playwright 浏览器版本不对时，用 PLAYWRIGHT_CHROME 指到本机任意一个 chrome-headless-shell
export PLAYWRIGHT_CHROME=${PLAYWRIGHT_CHROME:-$(ls -d ~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell | tail -1)}

"$PY" "$HERE/timeline.py"
rm -rf "$OUT/chat" "$OUT/overlay"
node "$HERE/shoot.mjs" chat "$OUT/chat" > /dev/null
node "$HERE/shoot.mjs" overlay "$OUT/overlay" > /dev/null
N=$("$PY" -c "import json;print(json.load(open('$HERE/timeline.json'))['SAMPLE_FRAMES'])")

if [ "$1" = preview ]; then
  rm -rf "$OUT/preview" "$OUT/preview_c"; mkdir -p "$OUT/preview_c"
  "$BLENDER" -b --factory-startup -P "$HERE/scene.py" -- "$OUT/chat" "$OUT/preview" 1 "$N" --preview --step 20 2>&1 | grep -E "Error|RENDERED"
  for f in "$OUT"/preview/*.png; do n=$(basename "$f")
    ffmpeg -v error -y -i "$f" -i "$OUT/overlay/$n" -filter_complex "[1]scale=540:960[o];[0][o]overlay" "$OUT/preview_c/$n"; done
  ffmpeg -v error -y -framerate 1 -pattern_type glob -i "$OUT/preview_c/*.png" -vf "scale=270:480,tile=8x2" -frames:v 1 "$OUT/preview_总览.jpg"
  echo "$OUT/preview_总览.jpg"; exit 0
fi

# 正式渲染：每 50 帧重开一次 Blender（屏幕贴图序列会一直占内存），已渲好的帧自动跳过
mkdir -p "$OUT/render"
i=1; while [ $i -le "$N" ]; do j=$((i + 49)); [ $j -gt "$N" ] && j=$N
  "$BLENDER" -b --factory-startup -P "$HERE/scene.py" -- "$OUT/chat" "$OUT/render" $i $j 2>&1 | grep -E "Error|RENDERED"
  i=$((j + 1)); done
"$PY" "$HERE/score.py" "$OUT/mix.wav"
# 合成：3D 画面 + 字幕层 + 配乐 → H.264 / yuv420p
ffmpeg -v error -y -framerate 30 -i "$OUT/render/%04d.png" -framerate 30 -i "$OUT/overlay/%04d.png" -i "$OUT/mix.wav" \
  -filter_complex "[0][1]overlay=format=auto,format=yuv420p[v]" -map "[v]" -map 2:a \
  -c:v libx264 -preset slow -crf 16 -c:a aac -b:a 256k -movflags +faststart -shortest "$OUT/一个人的AI团队_开场小样.mp4"
echo "$OUT/一个人的AI团队_开场小样.mp4"
