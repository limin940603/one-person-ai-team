#!/bin/bash
# 正式渲染「领活」：多台电脑从同一个队列领帧段，每次领 CHUNK 帧，渲完拉回本机，再领下一段。
#   bash films/aistudio/farm.sh <起始帧> <结束帧> <贴图目录(本机)> <输出目录(本机)>
# 机器用 ssh 别名配置（~/.ssh/config），每台一行环境变量，格式：别名=远端仓库根目录|远端 Blender 路径
#   MACHINES="local win1"  WIN1="win1=C:/tools/lemo-opuscar|C:/tools/blender/blender.exe"
# 远端要先放好同一份 films/aistudio 和贴图（COPYFILE_DISABLE=1 tar，别带 ._ 隐藏文件）。
# 注意：macOS 自带 bash 3.2，没有关联数组，所以用环境变量按机器名大写来取配置。
F0=$1; F1=$2; TEX=$3; OUT=$4; CHUNK=${CHUNK:-30}
HERE=$(cd "$(dirname "$0")" && pwd)
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
mkdir -p "$OUT/render" "$OUT/farm"; Q="$OUT/farm/next"; [ -f "$Q" ] || echo "$F0" > "$Q"
take() {   # 原子地领一段：用 mkdir 当锁
  until mkdir "$OUT/farm/lock" 2>/dev/null; do sleep .2; done
  local a=$(cat "$Q"); local b=$((a + CHUNK - 1)); [ $b -gt $F1 ] && b=$F1
  [ $a -le $F1 ] && echo $((b + 1)) > "$Q"; rmdir "$OUT/farm/lock"
  [ $a -le $F1 ] && echo "$a $b"
}
worker() {
  local m=$1
  while r=$(take); [ -n "$r" ]; do set -- $r; local a=$1 b=$2 t0=$(date +%s)
    if [ "$m" = local ]; then
      "$BLENDER" -b --factory-startup -P "$HERE/scene.py" -- "$TEX" "$OUT/render" $a $b > "$OUT/farm/local.last.log" 2>&1
    else
      # 远端 Windows：配置形如 别名=根目录|Blender 路径；用 PowerShell 跑，渲完打包拉回
      local cfg; cfg=$(eval echo "\$$(echo "$m" | tr '[:lower:]' '[:upper:]')"); local root=${cfg#*=}; root=${root%%|*}; local bl=${cfg##*|}
      ssh "$m" "& '$bl' -b --factory-startup -P '$root/films/aistudio/scene.py' -- '$root/out/tex' '$root/out/render' $a $b *> '$root/out/last.log'; cd '$root/out'; tar -cf c.tar -C render .; Remove-Item -Recurse -Force render" > /dev/null 2>&1
      scp -q "$m:$root/out/c.tar" "$OUT/farm/$m.tar" && tar -xf "$OUT/farm/$m.tar" -C "$OUT/render" && rm "$OUT/farm/$m.tar"
    fi
    local n=0; for i in $(seq $a $b); do [ -s "$OUT/render/$(printf %04d $i).png" ] && n=$((n + 1)); done
    echo "$(date +%H:%M:%S) $m $a-$b 完成 $n/$((b - a + 1)) 帧 用时 $(( $(date +%s) - t0 ))s"
  done
  echo "$(date +%H:%M:%S) $m 队列空了"
}
for m in ${MACHINES:-local}; do worker $m & done
wait; echo "全部完成。下一步：python films/aistudio/verify_compose.py 逐帧核对再合成"
