"""《一个人的 AI 团队》唯一时间表。所有时间都按"第几小节第几拍"写，导出 timeline.json 给
网页界面（ui/*.html）、Blender 场景（scene.py）、配乐（score.py）共用。改节奏只改这里。
运行：python films/aistudio/timeline.py"""
import json, os

BPM, FPS = 116, 30         # 116 比 128 稍慢：Grok 转圈那段才看得清
BEAT = 60 / BPM            # 0.517 s
BAR = BEAT * 4             # 2.069 s
at = lambda bar, beat=0.0: round(bar * BAR + beat * BEAT, 4)

# 全片结构（48 小节 ≈ 99 秒）。章节边界给进度条和配乐用；开场之后的细节等小样确认后再填。
SECTIONS = [
    ('开场', 0, 5),
    ('第一章 · 这个工作室怎么转', 5, 27),
    ('第二章 · 这条片子怎么做的', 27, 40),
    ('收尾 · 统计卡 + 领提示词', 40, 48),
]

# 开场（小样范围）事件。角色：claude（原版 Clawd 体素化）、codex、grok（后两个是我们自己设计的形象）。
OPEN = {
    # 第 0 帧 Claude 的回复已经在（钩子不能等），Codex、Grok 的回复按八分音符补上
    'reply': {'claude': -0.3, 'codex': at(0, .5), 'grok': at(0, 1)},
    # Claude：揭起 → 立成纸片 → 转一圈变立体 → 下蹲 → 跳出屏幕 → 落地
    'claude': {'peel': at(0, 2), 'stand': at(0, 3), 'spin_end': at(1, 1), 'jump': at(1, 1.5),
               'land': at(1, 3), 'settle': at(1, 3.5)},
    # Codex、Grok 节奏更快（半圈），Grok 落地正好砸在第 4 小节重拍 = 标题出现
    'codex': {'peel': at(2, 0), 'stand': at(2, .75), 'spin_end': at(2, 1.5), 'jump': at(2, 1.5),
              'land': at(2, 2.5), 'settle': at(2, 3)},
    'grok': {'peel': at(2, 1.5), 'stand': at(2, 2.25), 'spin_end': at(2, 3), 'jump': at(2, 3),
             'land': at(3, 0), 'settle': at(3, .5)},
    'title': at(3, 0),           # 「一个人的 AI 团队」
    'roles': at(3, 2),           # 三个角色各管什么
    'hops': [at(3, 2), at(3, 3), at(4, 0), at(4, 1)],   # 三个角色原地按拍子蹦
    'bigjump': at(4, 2),         # 一起跳起
    'chapter': at(5, 0),         # 「第一章」卡
    'end': at(5, 4 / 3),          # 开场收尾 = 第一章卡后 1⅓ 拍（原写死 10.0 秒，116 BPM 后早于第一章卡，镜头会跳、灯提前亮）
}

# ---------------- 画幅与几何（横版 1920×1080）----------------
W, H = 1920, 1080
SZ = .0612                          # 屏幕表面高度
PZ = .04                            # 全息平台台面高度
SW, SH = 2.6, 1.625                 # 所有平板都横放：2.6 × 1.625（界面 1600×1000 像素）
PX = (1600, 1000)
CLAUDE_RGB = (.533, .115, .045)     # Claude 橙，深一点（#C15F3C 再深一点）
CLAUDE_HEX = '#c15f3c'

# 开场平板（群聊）：三个"贴纸"的像素中心
STICK_PX = {'claude': (145, 375), 'codex': (145, 555), 'grok': (145, 735)}
LAND = {'claude': (0, -1.3, 0), 'codex': (-.42, -1.2, 0), 'grok': (.42, -1.2, 0)}   # 开场跳出屏幕后落在平板前的桌面上

# ---------------- 第一章 · 这个工作室怎么转（第 5–26 小节，10.3–55.9 s）----------------
# 照原片：一镜到底；每个工具前面一个图标格子，工具之间一排踏板格子；角色按拍子一格一格跳，跳上图标 = 打开这个工具；
# 屏幕里的东西也都是格子（任务卡、文件标签、审查项、机器），落在哪格哪格弹起、点亮、出声。
ST = {   # 工位：中心；page = 贴图页面名
    'mac':    dict(c=(3.8, 0),  page='mac'),
    'kb':     dict(c=(7.6, 0),  page='kb'),
    'code':   dict(c=(11.4, 0), page='code'),
    'review': dict(c=(15.2, 0), page='review'),
    'chat2':  dict(c=(24.8, 0), page='chat2'),
    # 第二章：这条片子怎么做的（4 个工位，Claude 从群聊扎进去，从时间表屏幕里冒出来）
    'tl':     dict(c=(32.0, 0), page='tl'),
    'shot':   dict(c=(35.8, 0), page='shot'),
    'render': dict(c=(39.6, 0), page='render'),
    'score':  dict(c=(43.4, 0), page='score'),
}
SUBT = {f'sub{i}': dict(c=(10.6 + .8 * i, 1.4), s=(.7, .46), page=f'sub{i}', px=(600, 400)) for i in range(3)}   # Claude 分身用的三块小屏
ROW_Y = -1.3                        # 图标和踏板格子那一排
MAP = dict(c=(20.0, .35), r=1.9)
DEV = {   # 9 台机器：相对平台中心的位置、尺寸、样式、标签
    'mac':    dict(o=(0, -.65),    s=(.42, .42, .2),  kind='macstudio', label='Mac 主控'),
    'k9700':  dict(o=(0, .75),     s=(.3, .55, .6),   kind='tower',     label='9700K 调度台'),
    'x3d':    dict(o=(-1.25, .45), s=(.32, .58, .64), kind='rgbtower',  label='X3D · RTX 5080'),
    'gpu':    dict(o=(-1.15, 1.25), s=(.28, .5, .55), kind='tower',     label='3060Ti'),
    'mini0':  dict(o=(.95, 1.2),   s=(.26, .26, .07), kind='mini',      label='迷你主机 ×3'),
    'mini1':  dict(o=(1.35, .9),   s=(.26, .26, .07), kind='mini',      label=''),
    'mini2':  dict(o=(1.6, .5),    s=(.26, .26, .07), kind='mini',      label=''),
    'laptop': dict(o=(1.25, -.35), s=(.42, .28, .02), kind='laptop',    label='笔记本'),
    'nas':    dict(o=(-1.05, -.75), s=(.42, .32, .36), kind='nas',      label='NAS 存档'),
}
for d in DEV.values(): d['p'] = (MAP['c'][0] + d['o'][0], MAP['c'][1] + d['o'][1])

# ---- 格子：id → 世界坐标（角色落点）。界面里的格子用像素定义，这里换算成 3D，网页也用同一份像素画格子 ----
UI_CELLS = {   # 页面: {格子名: (中心 x, 中心 y, 宽, 高)}（像素）
    'mac':    {**{f'item{i}': (205 + 300 * i, 600, 270, 260) for i in range(5)}, 'input': (800, 925, 1520, 110),
               'spotL': (230, 300, 200, 160), 'spotR': (1400, 300, 200, 160)},
    'kb':     {'search': (1430, 400, 190, 100), 'res0': (420, 690, 720, 440), 'res1': (1170, 690, 720, 440)},
    'code':   {**{f'tab{i}': (190 + 260 * i, 150, 240, 70) for i in range(4)}, **{f'task{i}': (1330, 390 + 170 * i, 440, 140) for i in range(3)}},
    'review': {f'c{i}': (205 + 300 * i, 560, 270, 320) for i in range(5)},
    'chat2':  {'dive': (800, 620, 200, 200)},
    'tl':     {**{f'L{i}': (800, 310 + 140 * i, 1440, 110) for i in range(4)}, 'portal': (800, 500, 200, 200),
               'spotL': (150, 900, 200, 140), 'spotR': (1450, 900, 200, 140)},
    'shot':   {**{f'f{i}': (205 + 297 * i, 790, 270, 200) for i in range(5)}, 'spotL': (150, 380, 200, 160), 'spotR': (1450, 380, 200, 160)},
    'render': {**{f'g{i}': (330 + 470 * (i % 3), 290 + 290 * (i // 3), 440, 260) for i in range(6)},
               'spotL': (150, 890, 200, 130), 'spotR': (1450, 890, 200, 130)},
    'score':  {f'n{i}': (170 + 180 * i, 720, 160, 220) for i in range(8)},
}
CELLS = {}
def _px2w(c, px, py, z=SZ):
    return (round(c[0] + (px / PX[0] - .5) * SW, 4), round(c[1] + (.5 - py / PX[1]) * SH, 4), z)
for st, cells in UI_CELLS.items():
    for k, (px, py, *_) in cells.items(): CELLS[f'{st}:{k}'] = _px2w(ST[st]['c'], px, py)
ICONS = ['mac', 'kb', 'code', 'review']                     # 每个工具前面的图标格子
for k in ICONS: CELLS['i_' + k] = (ST[k]['c'][0], ROW_Y, .05)
_xs = [0] + [ST[k]['c'][0] for k in ICONS]                   # 踏板：相邻两站之间 3 格
for j in range(4):
    for i in range(1, 4): CELLS[f'p{j}_{i}'] = (round(_xs[j] + (_xs[j + 1] - _xs[j]) * i / 4, 4), ROW_Y, .03)
_xs2 = [ST[k]['c'][0] for k in ('tl', 'shot', 'render', 'score')]   # 第二章工位之间也铺踏板（p4、p5、p6）
for j in range(3):
    for i in range(1, 4): CELLS[f'p{j + 4}_{i}'] = (round(_xs2[j] + (_xs2[j + 1] - _xs2[j]) * i / 4, 4), ROW_Y, .03)
STAT_X = 48.5                                                # 收尾：统计台，4 块数据格子
for i in range(4): CELLS[f's{i}'] = (round(STAT_X + (i - 1.5) * .95, 4), -.55, .08)
for k, d in DEV.items(): CELLS['d_' + k] = (d['p'][0], d['p'][1], PZ + d['s'][2])
CELLS['map:spotG'] = (MAP['c'][0] + .55, MAP['c'][1] - .75, PZ)
CELLS['map:spotX'] = (MAP['c'][0] - .45, MAP['c'][1] - 1.15, PZ)
for i in range(3): CELLS[f'sub{i}'] = (*SUBT[f'sub{i}']['c'], SZ)

STEPS = [  # (开始时刻, 步骤名) — 每步 4 小节；步骤名先大字 2 拍，再缩到左上角当进度条
    (at(6), '我只说一句话'), (at(10), 'Grok 先读资料'), (at(14), 'Claude 写代码、分身'),
    (at(18), 'Codex 挑错、出图'), (at(22), '9 台机器一起转'),
]
CH1 = dict(
    start=at(5), end=at(27), steps=STEPS,
    typing=(at(6, .3), at(6, 3.3)), send=at(7, 0),
    items=[at(7, 3), at(8, 0), at(8, 1), at(8, 2), at(8, 3)],          # 5 件事逐个弹出（Claude 正好踩上去）
    owners=[at(9, 0), at(9, .5), at(9, 1), at(9, 1.5), at(9, 2)],      # 挂负责人（负责的角色正好踩上去）
    kb_typing=(at(10, 1.3), at(10, 2.8)), kb_search=at(11, 0), kb_card=at(13, 0),
    torrent=(at(11, 1), at(12, 3)), jcard=(at(13, 2), at(14, 0)),
    tabs=[at(14, 1), at(14, 2), at(14, 3), at(15, 0)],                  # Claude 踩过 4 个文件标签，每踩一个打开一个真实源文件
    split=at(15, 2), subs=(at(15, 3), at(16, 3)), merge=(at(17, 0), at(17, 1)),
    doc=(at(17, 2), at(18, 0)),
    checks=[at(18, 2), at(18, 3), at(19, 0), at(19, 1), at(19, 2)],     # Codex 一格一格审
    stamp=at(20, 0), gen=(at(20, 1), at(21, 1)),
    reveal=(at(21, 2), at(22, 2)), archived=at(25, 2),
    ask=(at(26, 0), at(26, 1.5)), dive=(at(26, 2), at(26, 3)),
)
STACK = (9.3, .45, .006)            # 判断卡叠成的塔（知识书房右边的桌面上）
GEN_AT = (16.15, .35)               # 封面图显影框立在 Codex 屏幕右后方
DOC_FROM, DOC_TO = 'code:task1', (15.2, 0, SZ)

# 角色动作：J(起, 落, 格子, 跳高, 花样轴, 方向)；('hop', t)；('slam', 起, 落)；('spin', 起, 止)；('dive', 起, 落)
def J(t0, t1, cell, h=.35, ax=None, sgn=0):
    return ('jump', t0, t1, CELLS[cell], h, ax, sgn, cell)
ACT = {
    'claude': [
        J(at(5, .5), at(5, 1), 'p0_1', .3), J(at(5, 1), at(5, 2), 'p0_2'), J(at(5, 2), at(5, 3), 'p0_3'),
        J(at(5, 3), at(6, 0), 'i_mac', .55, 'z', 1),                          # 跳上图标 = 打开 Mac 主控
        ('hop', at(6, 1)), ('hop', at(6, 2)), ('hop', at(6, 3)), ('hop', CH1['send']),
        J(at(7, 2), at(7, 3), 'mac:item0', .55, 'x', -1),
        *[J(CH1['items'][i - 1], CH1['items'][i], f'mac:item{i}', .3) for i in range(1, 5)],
        J(at(8, 3.5), CH1['owners'][1], 'mac:item1', .5), J(CH1['owners'][1], CH1['owners'][2], 'mac:item2', .3),
        J(at(11, 0), at(11, 2), 'i_code', 2.6, 'x', -1),                      # 镜头在 Grok 那边时从高处飞过去
        J(at(14, .5), CH1['tabs'][0], 'code:tab0', .5, 'z', 1),
        *[J(CH1['tabs'][i - 1], CH1['tabs'][i], f'code:tab{i}', .3) for i in range(1, 4)],
        J(CH1['tabs'][3], at(15, 1), 'code:task1', .45),
        ('hop', at(15, 3)), ('hop', at(16, 0)), ('hop', at(16, 1)), ('hop', at(16, 2)),
        ('slam', at(17, 1), CH1['doc'][0]),                                    # 一脚把文件踢给 Codex
        J(at(21, 2), at(22, 1), 'd_mac', 2.6, 'x', -1),
        J(at(22, 3), at(23, 0), 'd_k9700', .6), J(at(23, 0), at(23, 1), 'd_x3d', .6), J(at(23, 1), at(23, 2), 'd_gpu', .45),
        J(at(23, 3), at(24, 1), 'd_mac', .8, 'z', 1),
        ('hop', at(24, 3)), ('hop', at(25, 2)),
        J(at(26, 0), at(26, 2), 'chat2:dive', 1.8, 'x', -1),
        ('dive', *CH1['dive']),
    ],
    'codex': [
        J(at(5, 1), at(5, 2), 'p0_1', .4), J(at(5, 2), at(5, 3), 'p0_2'), J(at(5, 3), at(6, 0), 'p0_3'),
        J(at(6, 0), at(6, 1), 'mac:spotR', .55, 'z', -1),
        J(at(9, 1), CH1['owners'][3], 'mac:item3', .45), J(CH1['owners'][3], CH1['owners'][4], 'mac:item4', .3),
        J(at(11, 1), at(11, 3), 'i_review', 2.8, 'z', 1),
        J(at(18, 1), CH1['checks'][0], 'review:c0', .55, 'z', 1),
        *[J(CH1['checks'][i - 1], CH1['checks'][i], f'review:c{i}', .3) for i in range(1, 5)],
        J(CH1['checks'][4], at(19, 3), 'review:c2', .5),
        ('slam', at(19, 3), CH1['stamp']),
        ('hop', at(20, 2)), ('hop', at(20, 3)), ('hop', at(21, 0)),
        J(at(21, 3), at(22, 2), 'map:spotX', 2.6, 'z', 1),
        ('hop', at(23, 0)), ('hop', at(24, 0)),
        J(at(25, 1), CH1['archived'], 'd_nas', .6),                            # 定稿核对完，Codex 跳上 NAS
    ],
    'grok': [
        J(at(5, 2), at(5, 3), 'p0_1', .4), J(at(5, 3), at(6, 0), 'p0_2'), J(at(6, 0), at(6, 1), 'p0_3'),
        J(at(6, 1), at(6, 2), 'mac:spotL', .55, 'y', 1),
        J(at(8, 3.5), CH1['owners'][0], 'mac:item0', .5),
        J(at(9, 1), at(9, 2), 'p1_1', .7), J(at(9, 2), at(9, 3), 'p1_2'), J(at(9, 3), at(10, 0), 'p1_3'),
        J(at(10, 0), at(10, 1), 'i_kb', .5, 'y', 1),                           # 跳上图标 = 打开知识书房
        J(at(10, 2), at(10, 3), 'kb:search', .55),
        ('slam', at(10, 3.4), CH1['kb_search']),
        ('spin', *CH1['torrent']),
        ('hop', at(13, 0)), ('hop', at(13, 1)),
        J(at(21, 2.5), at(22, 1.5), 'map:spotG', 2.6, 'y', 1),
        J(at(23, 2), at(23, 3), 'd_mini0', .7), J(at(23, 3), at(24, 0), 'd_mini1', .35),
        J(at(24, 0), at(24, 1), 'd_mini2', .35), J(at(24, 1), at(24, 2), 'd_laptop', .5),
    ],
}
# ---------------- 第二章 · 这条片子怎么做的（第 27–39 小节）+ 收尾（第 40–47 小节）----------------
STEPS2 = [(at(28), '一份时间表管全片'), (at(31), '网页画界面，逐帧截图'), (at(34), 'Blender 用代码渲染'), (at(37), '配乐也是代码写的')]
CH2 = dict(start=at(27), end=at(40), steps=STEPS2, lines=[at(28), at(28, 2), at(29), at(29, 2)],
           shots=[at(31, 2), at(32), at(32, 2), at(33), at(33, 2)], stats=[at(40), at(41), at(42), at(43)],
           endcard=at(44), sign=at(45, 2))
PORTAL2 = (ST['tl']['c'][0], ST['tl']['c'][1], SZ)
def WARP(t0, t1, cell):            # 从第二章第一块屏幕的"洞"里冒出来，落到格子上
    return ('warp', t0, t1, CELLS[cell], .6, 'x', -1, cell)
HOPS_END = [at(44), at(44, 2), at(45), at(45, 2), at(46), at(46, 2)]
ACT['claude'] += [
    WARP(at(27, .5), at(28), 'tl:L0'),
    *[J(CH2['lines'][i - 1], CH2['lines'][i], f'tl:L{i}', .3) for i in range(1, 4)],     # 一行一行踩：节拍、步骤、动作、镜头
    ('slam', at(30), at(30, 1)),
    J(at(30, 2), at(31, 1), 'shot:spotR', 2.0, 'x', -1),
    J(at(33, 3), at(34, 2), 'render:spotR', 2.0, 'x', -1),
    J(at(36, 1), at(37), 'score:n0', 2.0, 'x', -1), J(at(37), at(37, 3), 'score:n3', .5), J(at(37, 3), at(38, 2), 'score:n6', .5),
    J(at(39), at(40), 's0', 1.8, 'x', -1), J(at(42, 2), at(43), 's3', .9, 'z', 1),
    *[('hop', h) for h in HOPS_END], J(at(47), at(47, 2), 's3', 1.0, 'x', -1),
]
ACT['codex'] += [
    WARP(at(27, 1.5), at(28, .5), 'tl:spotL'), ('hop', at(28, 2)), ('hop', at(29, 2)),
    J(at(30, 1), at(30, 2), 'p4_1', .4), J(at(30, 2), at(30, 3), 'p4_2'), J(at(30, 3), at(31), 'p4_3'),
    J(at(31), CH2['shots'][0], 'shot:f0', .55, 'z', 1),
    *[J(CH2['shots'][i - 1], CH2['shots'][i], f'shot:f{i}', .3) for i in range(1, 5)],   # 落一格 = 截下一帧
    J(at(34), at(34, 3), 'render:spotL', 2.0, 'z', 1),
    J(at(36, 2), at(37, 1), 'score:n1', 2.0, 'z', 1), J(at(37, 1), at(38), 'score:n4', .5), J(at(38), at(38, 3), 'score:n7', .5),
    J(at(40), at(41), 's1', 1.8, 'z', 1),
    *[('hop', h) for h in HOPS_END], J(at(47), at(47, 2), 's1', 1.0, 'z', 1),
]
ACT['grok'] += [
    WARP(at(27, 2.5), at(28, 1), 'tl:spotR'), ('hop', at(28, 3)), ('hop', at(29, 3)),
    J(at(30, 3), at(31, 3), 'shot:spotL', 2.0, 'y', 1),
    J(at(33, 1), at(33, 2), 'p5_1', .5), J(at(33, 2), at(33, 3), 'p5_2'), J(at(33, 3), at(34), 'p5_3'),
    J(at(34), at(34, 2), 'render:g0', .55, 'y', 1), J(at(34, 2), at(35), 'render:g1', .3),
    J(at(35), at(35, 2), 'render:g2', .3), J(at(35, 2), at(36), 'render:g5', .3),
    J(at(36, 3), at(37, 2), 'score:n2', 2.0, 'y', 1), J(at(37, 2), at(38, 1), 'score:n5', .5),
    J(at(41), at(42), 's2', 1.8, 'y', 1),
    *[('hop', h) for h in HOPS_END], J(at(47), at(47, 2), 's2', 1.0, 'y', 1),
]

LANDS = sorted((e[2], e[7], k) for k, evs in ACT.items() for e in evs if e[0] in ('jump', 'warp'))   # (时刻, 格子, 谁)：格子弹起、出声都用它
OPEN_AT = {k: min(t for t, c, _ in LANDS if c == 'i_' + k) for k in ICONS}                  # 第一次有人跳上图标 = 这个工具打开

EDGES = [  # 连线：(起, 止, 亮起, 熄灭, 颜色)。亮起时刻 = 角色落在那台机器上的那一拍
    ('mac', 'k9700', at(23, 0), at(26), 'blue'),
    ('k9700', 'x3d', at(23, 1), at(26), 'blue'), ('k9700', 'gpu', at(23, 2), at(26), 'blue'),
    ('k9700', 'mini0', at(23, 3), at(26), 'blue'), ('k9700', 'mini1', at(24, 0), at(26), 'blue'),
    ('k9700', 'mini2', at(24, 1), at(26), 'blue'), ('k9700', 'laptop', at(24, 2), at(26), 'blue'),
    ('mac', 'nas', at(24, 3), at(26), 'green'), ('x3d', 'nas', at(24, 3.25), at(26), 'green'),
    ('gpu', 'nas', at(24, 3.5), at(26), 'green'), ('k9700', 'nas', at(25, 0), at(26), 'green'),
]

# 镜头：(时刻, 机位, 看向)，连续样条穿过这些点；FOLLOW = 这段时间跟拍
CAM1 = [
    (at(6), (3.8, -2.05, 1.95), (3.8, -.15, 0)),                     # 第 1 步：Mac 主控全屏
    (at(6, 3), (3.8, -1.65, 1.5), (3.8, -.5, 0)),                    # 推近输入框
    (at(7, 2.5), (3.8, -1.7, 1.55), (3.8, -.1, .05)),                # 五个任务格子
    (at(8, 3), (3.95, -1.6, 1.45), (3.9, -.1, .05)),
    (at(9, 1), (3.6, -1.8, 1.5), (3.7, -.3, .05)),
    (at(10, 2), (7.6, -1.85, 1.85), (7.6, -.05, 0)),                 # 第 2 步：知识书房全屏
    (at(11, 0), (7.95, -1.6, 1.55), (8.1, .1, .05)),
    (at(11, 2), (7.7, -1.9, .78), (8.5, .2, .5)),                    # 低机位：资料龙卷风
    (at(12, 3), (9.4, -1.5, .95), (8.65, .2, .5)),                   # 绕着转
    (at(13, 1), (9.2, -1.6, 1.0), (8.9, .3, .55)),
    (at(14, 1), (11.3, -1.5, 1.9), (11.3, .25, 0)),                  # 第 3 步：代码屏（往上看一点，文件标签和 Claude 都在画面里）
    (at(15, 1), (11.65, -1.6, 1.6), (11.7, .05, 0)),
    (at(15, 3), (11.4, -2.2, 2.2), (11.4, .5, 0)),                   # 拉开：带上后排三块小屏
    (at(16, 3), (11.45, -1.15, 1.5), (11.4, 1.1, .1)),               # 贴近小屏
    (at(17, 1), (12.0, -1.8, 1.25), (12.2, -.2, .1)),                # 正对 Claude 踢文件
    (at(18, 1), (15.2, -1.85, 1.85), (15.2, -.1, 0)),                # 第 4 步：审查屏全屏
    (at(19, 2), (15.25, -1.7, 1.6), (15.3, -.1, .05)),
    (at(20, 0), (15.2, -1.45, .9), (15.2, -.25, .2)),                # 贴近盖章
    (at(20, 2), (15.6, -1.6, .95), (16.1, .4, .5)),                  # 封面图显影
    (at(21, 2), (16.5, -1.8, 1.1), (16.2, .3, .5)),
    (at(22, 2), (20.0, -3.3, 2.5), (20.0, .35, .2)),                 # 第 5 步：升起，看到整个工作室
    (at(23, 2), (21.0, -2.6, 1.8), (20.1, .45, .3)),                 # 绕平台
    (at(24, 2), (19.1, -2.6, 1.7), (20.0, .35, .25)),
    (at(25, 2), (18.7, -1.75, 1.0), (19.0, -.4, .3)),                # 贴近 NAS
    (at(26, 1), (24.8, -2.0, 1.85), (24.8, -.1, 0)),                 # 回到群聊
    (at(27), (24.8, -.28, .32), (24.8, -.2, 0)),                     # 钻进屏幕
]
FOLLOW = [  # (起, 止, 跟谁, 机位相对偏移)
    (at(5, .5), at(6, 0), 'claude', (-.5, -1.9, 1.0)),
    (at(9, 1), at(10, 1), 'grok', (-.6, -1.9, 1.0)),
    (CH1['jcard'][0], CH1['jcard'][1], 'jcard', (-.5, -1.6, .7)),
    (CH1['doc'][0], CH1['doc'][1], 'doc', (-.6, -1.7, .8)),
]

FOLLOW += [(at(30, 1), at(31), 'codex', (-.6, -1.9, 1.0)), (at(33, 1), at(34), 'grok', (-.6, -1.9, 1.0))]
CAM2 = [   # 第二章从这里硬切（白闪）：镜头从时间表屏幕上方开始
    (at(27), (32.0, -1.2, 2.9), (32.0, -.05, 0)),
    (at(28), (32.0, -2.05, 1.95), (32.0, -.15, 0)),
    (at(29, 2), (32.3, -1.75, 1.6), (32.2, 0, .05)),
    (at(30, 1), (32.6, -1.9, 1.7), (32.8, -.5, 0)),
    (at(31, 1), (35.8, -2.05, 1.95), (35.8, -.15, 0)),
    (at(33), (36.1, -1.8, 1.7), (36.0, 0, .05)),
    (at(34), (39.6, -2.1, 2.0), (39.6, -.15, 0)),
    (at(35, 2), (39.4, -1.75, 1.45), (39.6, .05, .1)),
    (at(36, 3), (41.5, -2.5, 2.2), (42.0, 0, 0)),
    (at(37, 1), (43.4, -2.05, 1.95), (43.4, -.15, 0)),
    (at(38, 3), (43.6, -1.7, 1.45), (43.6, -.25, .05)),
    (at(39, 3), (47.0, -3.6, 2.0), (47.6, -.2, .4)),
    (at(40), (48.5, -4.0, 1.75), (48.5, -.2, .5)),
    (at(43, 2), (48.5, -3.8, 1.65), (48.5, -.2, .5)),
    (at(44, 2), (48.5, -4.4, 2.3), (48.5, 0, .45)),
    (at(48), (48.5, -4.8, 2.6), (48.5, 0, .45)),
]

CAPS = [
    (at(7, 1.5), at(9), '我说需求，Claude 拆活'),
    (at(9), at(10), '谁擅长什么，就派给谁'),
    (at(11, 1), at(13, 2), 'Grok：几万篇资料，先读一遍'),
    (at(14, 1), at(15, 2), 'Claude：写方案、写代码'),
    (at(15, 2), at(17, 2), '还能分身，几路一起干'),
    (at(18, 2), at(20, 1), 'Codex：交叉审查，挑错'),
    (at(20, 1), at(21, 2), '再把封面图画出来'),
    (at(22, 2), at(24, 2), '慢活交给调度台，到点自动跑'),
    (at(24, 2), at(26), '定稿进 NAS，逐个文件核对'),
    (at(28, 1), at(30), '节拍、步骤、动作、镜头，全写在一个文件里'),
    (at(30), at(31), '画面、配乐、字幕都读它'),
    (at(31, 1), at(33, 2), '界面是网页，一帧一帧截成图，贴到 3D 屏幕上'),
    (at(34, 1), at(35, 2), 'Blender 在后台渲染，动作和镜头都是公式算的'),
    (at(35, 2), at(37), '没有一个关键帧是手调的'),
    (at(37, 1), at(39, 2), '每跳一下就是一个音：配乐也是代码合成的'),
    (at(40), at(44), '一个人 + 三个 AI，这条片子用了：'),
]
CARDS = [
    (at(12, 0), at(13, 2), '7,253 张', 'Grok 写的判断卡\n同题盲评 Grok 4.42 · Sonnet 3.76（10 篇，样本小）'),
    (at(23, 0), at(24, 2), '9 台机器', 'Mac 指挥 · 9700K 调度 · NAS 存档\n近 7 天调度台自动跑了 162 次'),
]

# 收尾统计卡：构建时现数（不写死），改了代码重跑 timeline.py 就会变
PAGES = ['chat', 'overlay', 'mac', 'kb', 'code', 'sub0', 'sub1', 'sub2', 'review', 'chat2', 'queue', 'gen', 'tl', 'shot', 'render', 'score']
def _count_lines():
    here = os.path.dirname(os.path.abspath(__file__)); n = 0
    for root, _, fs in os.walk(here):
        for f in fs:
            if f.endswith(('.py', '.mjs', '.sh', '.html')):
                n += sum(1 for ln in open(os.path.join(root, f), encoding='utf-8') if ln.strip())
    return n
_NF = int(round(48 * BAR * FPS))
STATS = [(f'{_count_lines():,}', '行代码'), (f'{_NF:,}', '帧画面'), (f'{len(PAGES) * _NF + 1:,}', '张界面截图'), ('0', '个手调关键帧')]

TL = dict(BPM=BPM, FPS=FPS, BEAT=BEAT, BAR=BAR, DUR=48 * BAR, SECTIONS=SECTIONS, OPEN=OPEN,
          SAMPLE_FRAMES=int(round(OPEN['end'] * FPS)), W=W, H=H,
          SZ=SZ, PZ=PZ, SW=SW, SH=SH, PX=PX, CLAUDE_RGB=CLAUDE_RGB, CLAUDE_HEX=CLAUDE_HEX, STICK_PX=STICK_PX, LAND=LAND,
          ST=ST, SUBT=SUBT, ROW_Y=ROW_Y, MAP=MAP, DEV=DEV, UI_CELLS=UI_CELLS, CELLS=CELLS, ICONS=ICONS,
          STEPS=STEPS, CH1=CH1, STACK=STACK, GEN_AT=GEN_AT, DOC_FROM=DOC_FROM, DOC_TO=DOC_TO,
          ACT=ACT, LANDS=LANDS, CH2=CH2, STEPS2=STEPS2, PORTAL2=PORTAL2, CAM2=CAM2, STATS=STATS, PAGES=PAGES, STAT_X=STAT_X, OPEN_AT=OPEN_AT, EDGES=EDGES, CAM1=CAM1, FOLLOW=FOLLOW, CAPS=CAPS, CARDS=CARDS,
          CH1_FRAMES=(int(round(at(5) * FPS)) + 1, int(round(at(27) * FPS))), ALL_FRAMES=_NF)

if __name__ == '__main__':
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timeline.json')
    json.dump(TL, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('timeline.json', TL['SAMPLE_FRAMES'], 'frames sample,', TL['DUR'], 's full')
