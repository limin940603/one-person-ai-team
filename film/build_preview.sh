#!/bin/sh
# 0 秒到第一章结尾的低清动态预览（横版 960×540、低采样、开运动模糊），看流畅度和转场用：
#   sh films/aistudio/build_preview.sh
# 已经渲好的帧会跳过；改了某一段，删掉那段的 render/*.png 再跑即可。
set -e
HERE=$(cd "$(dirname "$0")" && pwd); LIB=$(cd "$HERE/../.." && pwd); cd "$LIB"
PY=${PY:-$( [ -x "$LIB/.venv/bin/python" ] && echo "$LIB/.venv/bin/python" || command -v python3 )}
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
OUT=${OUT:-$LIB/out/aistudio/preview}
export PLAYWRIGHT_CHROME=${PLAYWRIGHT_CHROME:-$(ls -d ~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell | tail -1)}

"$PY" "$HERE/timeline.py"
N=$("$PY" -c "import json;print(json.load(open('$HERE/timeline.json'))['CH1_FRAMES'][1])")
END=$("$PY" -c "print($N / 30)")
echo "预览：1-$N 帧（$END 秒）"

# 1) 所有界面页逐帧截图（并行）
mkdir -p "$OUT/tex"
for p in chat overlay mac kb code sub0 sub1 sub2 review chat2 queue gen; do
  [ "$(ls "$OUT/tex/$p" 2>/dev/null | wc -l)" -ge "$N" ] && [ -z "$RESHOOT" ] && continue   # 已截齐就跳过；改了界面要重截：RESHOOT=1
  node "$HERE/shoot.mjs" $p "$OUT/tex/$p" "1-$N" > "$OUT/tex/$p.log" 2>&1 &
done
node "$HERE/shoot.mjs" kbcard "$OUT/tex/kbcard" 1 > /dev/null
wait
echo "界面截图完成"

# 2) 3D：每 100 帧重开一次 Blender
mkdir -p "$OUT/render"
i=1; while [ $i -le "$N" ]; do j=$((i + 99)); [ $j -gt "$N" ] && j=$N
  "$BLENDER" -b --factory-startup -P "$HERE/scene.py" -- "$OUT/tex" "$OUT/render" $i $j --preview 2>&1 | grep -E "Error|Traceback|RENDERED"
  i=$((j + 1)); done

# 3) 配乐 + 合成
"$PY" "$HERE/score.py" "$OUT/mix.wav" "$END"
ffmpeg -v error -y -framerate 30 -i "$OUT/render/%04d.png" -framerate 30 -i "$OUT/tex/overlay/%04d.png" -i "$OUT/mix.wav" \
  -filter_complex "[1]scale=960:540[o];[0][o]overlay=format=auto,format=yuv420p[v]" -map "[v]" -map 2:a \
  -c:v libx264 -preset medium -crf 18 -c:a aac -b:a 192k -movflags +faststart -shortest "$OUT/一个人的AI团队_横版_预览_v4慢版.mp4"
echo "$OUT/一个人的AI团队_横版_预览_v4慢版.mp4"
