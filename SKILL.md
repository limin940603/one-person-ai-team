# SKILL：把《一个人的 AI 团队》在你的电脑上渲出来

> 给 coding agent 读的执行说明。目标：装好环境 → 出 10 秒开场小样 → 渲全片 → 逐帧核对后合成。人也能照着做。
> 预计：小样 Apple 芯片 Mac 约 10 分钟；全片 2,979 帧单机约 6–10 小时，多台机器领活按比例缩短。

## 0. 前提
- macOS（Apple 芯片）或 Windows（NVIDIA 显卡）。下面以 macOS 写，Windows 把路径换掉即可。
- 已装：git、Python ≥ 3.11、Node ≥ 20、ffmpeg、[Blender 5.2](https://www.blender.org/download/)（默认路径 `/Applications/Blender.app`，否则设环境变量 `BLENDER`）。
- 磁盘留 15 GB（截图序列和渲染帧）。

## 1. 取代码
```sh
git clone https://github.com/lemomo-ai/lemo-opuscar.git
git clone https://github.com/limin940603/one-person-ai-team.git
cp -R one-person-ai-team/film lemo-opuscar/films/aistudio
cd lemo-opuscar
git apply ../one-person-ai-team/patches/lemo-opuscar-render-quality.patch   # 可选：画质补丁，失败就跳过
```
本片必须放在 `lemo-opuscar/films/aistudio/`：`shoot.mjs` 和 `score.py` 从 `../../core` 取浏览器和音效底层。

## 2. 装依赖
```sh
python3 -m venv .venv && .venv/bin/pip install numpy soundfile pillow
npm install                      # 装 playwright-core
npx playwright install chromium  # 或设 PLAYWRIGHT_CHROME 指到本机已有的 chrome-headless-shell
```
验收：`.venv/bin/python -c "import numpy, soundfile, PIL"` 无报错；`node -e "import('playwright-core')"` 无报错；`"$BLENDER" -b --version` 打出 5.2。

## 3. 出时间表和 10 秒小样
```sh
.venv/bin/python films/aistudio/timeline.py      # 生成 timeline.json
sh films/aistudio/build_sample.sh preview        # 十几秒：构图总览图 out/aistudio/sample/preview_总览.jpg
sh films/aistudio/build_sample.sh                # 约 10 分钟：out/aistudio/sample/一个人的AI团队_开场小样.mp4
```
验收：总览图 16 格都有画面、没有粉色方块（粉色 = 贴图没找到）；小样能播放、有声音、角色在拍子上落地。

## 4. 渲全片
```sh
N=$(.venv/bin/python -c "import json;print(round(json.load(open('films/aistudio/timeline.json'))['DUR']*30))")
OUT=out/aistudio/full
# 4.1 所有屏幕的贴图序列（约 47,000 张 PNG）
for p in chat overlay mac kb code review chat2 tl shot render score sub0 sub1 sub2 kbcard gen queue; do node films/aistudio/shoot.mjs $p $OUT/tex/$p "1-$N"; done
# 4.2 渲染：单机
MACHINES=local bash films/aistudio/farm.sh 1 $N $OUT/tex $OUT
#     多机：MACHINES="local win1" WIN1="win1=C:/tools/lemo-opuscar|C:/tools/blender/blender.exe"（win1 是 ssh 别名，远端先放好同一份 films/aistudio 和贴图）
# 4.3 配乐
.venv/bin/python films/aistudio/score.py $OUT/mix.wav
# 4.4 逐帧核对 + 合成（有一帧不过就不合成，按打印的帧号重渲那一段）
.venv/bin/python films/aistudio/verify_compose.py $OUT/render $OUT/tex/overlay $OUT/mix.wav 1 $N $OUT/一个人的AI团队.mp4
```
`shoot.mjs` 的页面名以 `films/aistudio/ui/screens.html` 里定义的为准；缺哪个页面，渲染时对应屏幕会是粉色，补截那一个即可。

## 5. 常见坑
- **粉屏**：贴图目录名和帧号对不上，或从 Mac 拷到 Windows 时带了 `._` 隐藏文件（打包加 `COPYFILE_DISABLE=1`）。
- **Blender 内存涨**：`farm.sh` 每段重开一次 Blender，CHUNK 默认 30 帧，可调小。
- **改了节奏画面跳**：所有时间都要用 `at(小节, 拍)` 写，不要写死秒数。
- **代码屏显示注释**：`shoot.mjs` 截代码屏时会跳过文件头的说明，别把内部备注写进正文代码。

## 6. 做自己的片子
读 `prompts/一个人的AI团队-提示词.md`，9 条提示词按顺序发给 Claude Code，每条做完看过结果再发下一条。
