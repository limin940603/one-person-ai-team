"""《一个人的 AI 团队》配乐 + 音效：BPM 读 timeline（现 116），F 大调（F–Dm–B♭–C），全部 numpy 合成，时间全读 timeline.json。
乐器分工：鼓 = 节拍骨架；贝斯 = 落地的重量；铃铛 = 聊天消息弹出、角色蹦跳；木琴 = 角色转身变立体时的上行音阶。
角色的每个动作都在拍子上，每个动作配一个音。
运行：python films/aistudio/score.py <输出 wav>"""
import os, sys, json
import numpy as np
import soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); LIB = os.path.abspath(os.path.join(HERE, '../..'))
sys.path.insert(0, LIB)
from core.audio.sfx import SR, t_, noise, lp, bp, hp, env_exp, norm, whoosh, thump, pop, crash, add, compress, limit, click

TL = json.load(open(os.path.join(HERE, 'timeline.json'), encoding='utf-8'))
O, BEAT, BAR = TL['OPEN'], TL['BEAT'], TL['BAR']
END = float(sys.argv[2]) if len(sys.argv) > 2 else O['end']   # 第二个参数 = 混到第几秒（默认只到小样结尾）
C1, ACT = TL['CH1'], TL['ACT']
N = int((END + 1.5) * SR)
mus, fx = np.zeros((N, 2)), np.zeros((N, 2))
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
at = lambda bar, beat=0.: bar * BAR + beat * BEAT

# ---------- 音色 ----------
def kick(v=1.):
    d = .4; tt = t_(d); f = 46 + 130 * np.exp(-tt / .028); ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * env_exp(d, .14) + hp(noise(d), 4000) * env_exp(d, .002) * .3) * v
def clap(v=1.):
    d = .25; x = np.zeros(int(d * SR))
    for k, o in enumerate((0, .008, .017)):
        s = int(o * SR); m = len(x) - s; x[s:] += noise(d)[:m] * np.exp(-np.arange(m) / (SR * (.01 if k < 2 else .06)))
    return bp(x, 1000, 7000) * .7 * v
def hat(v=1., op=False):
    d = .28 if op else .05; return hp(noise(d), 8500) * env_exp(d, .08 if op else .012) * .4 * v
def saw(f, d):
    ph = f * t_(d); return 2 * (ph - np.floor(ph + .5))
def bass(m, d, v=1.):
    tt = t_(d); x = saw(hz(m), d) * .5 + np.sin(2 * np.pi * hz(m) * tt)
    return lp(x, 420) * np.clip(tt / .004, 0, 1) * np.clip((d - tt) / .02, 0, 1) * .55 * v
def bell(m, v=1., d=1.2):      # 铃铛：FM，金属感
    tt = t_(d); f = hz(m); mod = np.sin(2 * np.pi * f * 3.5 * tt) * 3 * np.exp(-tt / .15)
    return np.sin(2 * np.pi * f * tt + mod) * np.exp(-tt / .45) * .35 * v
def marimba(m, v=1., d=.9):
    tt = t_(d); f = hz(m); tau = .45 * (440 / f) ** .5
    mod = np.sin(2 * np.pi * f * 4 * tt) * 2 * np.exp(-tt / .02)
    return (np.sin(2 * np.pi * f * tt + mod) * np.exp(-tt / tau) + bp(noise(d), f * 2, min(f * 8, 16000)) * np.exp(-tt / .004) * .5) * .5 * v
def pad(ms, d, v=1.):
    x = sum(saw(hz(m) * (1 + dt), d) for m in ms for dt in (-.004, .004)) / (2 * len(ms))
    tt = t_(d); return lp(x, 1500) * np.clip(tt / .4, 0, 1) * np.clip((d - tt) / .6, 0, 1) * .28 * v
def riser(d, v=1.):
    tt = t_(d); x = noise(d); y = np.zeros_like(x)
    for i in range(10):
        a, b = int(i / 10 * len(x)), int((i + 1) / 10 * len(x)); f = 300 * 2 ** (i * .55)
        y[a:b] = bp(x, f, min(f * 2.5, 18000))[a:b]
    return y * (tt / d) ** 2.2 * .35 * v
def peel(v=1.):                # 揭贴纸：细碎的撕扯声
    d = .4; tt = t_(d); x = bp(noise(d), 2500, 9000) * (np.abs(np.sin(2 * np.pi * 38 * tt)) ** 3)
    return x * np.clip(tt / .05, 0, 1) * env_exp(d, .18) * .8 * v
def boing(v=1.):               # 起跳：往上滑的弹簧音
    d = .32; tt = t_(d); f = 180 * 2 ** (tt / d * 1.6) * (1 + .06 * np.sin(2 * np.pi * 22 * tt))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(d, .12) * .7 * v
def ripple(v=1.):              # 屏幕波纹：玻璃般的下行琶音
    x = np.zeros(int(1.2 * SR))
    for i, m in enumerate((96, 91, 88, 84)):
        b = bell(m, .5, 1.0); s = int(i * .06 * SR); x[s:s + len(b)] += b[:len(x) - s]
    return x * v
def impact(v=1.):              # 低频一锤 + 镲片，长度不同，补零后相加
    a, b = thump(1, 52) * .9, crash(.6) * .5
    x = np.zeros(max(len(a), len(b))); x[:len(a)] += a; x[:len(b)] += b
    return x * v

# ---------- 编排 ----------
F, Dm, Bb, C = (41, [65, 69, 72]), (38, [62, 65, 69]), (34, [62, 65, 70]), (36, [64, 67, 72])
PROG = [F, Dm, Bb, C, F, Dm]
# 第 0–1 小节：只有铺底和铃铛，留给聊天和揭贴纸
for b in range(2):
    add(mus, pad(PROG[b][1], BAR + .3, .8), at(b))
    for s in range(8): add(mus, hat(.35 if s % 2 else .2), at(b, s / 2), pan=.2)
# Claude 落地（第 1 小节第 4 拍）先砸一下，第 2 小节起整套鼓进
add(mus, kick(1.1), O['claude']['land'])
for b in range(2, 6):
    root, ch = PROG[b]
    add(mus, pad(ch, BAR + .3, .7), at(b))
    for beat in range(4):
        add(mus, kick(1. if beat % 2 == 0 else .85), at(b, beat))
        if beat % 2: add(mus, clap(.8), at(b, beat), pan=-.05)
        for s in (0, .5): add(mus, hat(.5 if s else .3, op=(s == .5 and beat == 3)), at(b, beat + s), pan=.25)
    for s in range(8):          # 贝斯八分音符，第 4 小节砸标题那一下用长音
        if b == 3 and s == 0: add(mus, bass(root, BEAT * 2, 1.1), at(b)); continue
        if b == 3 and s < 4: continue
        add(mus, bass(root + (12 if s in (3, 6) else 0), BEAT / 2 * .9), at(b, s / 2))
# 收在第 5 小节重拍（第一章卡），之后只留余音（只混小样时）；混第一章时律动接着走
add(mus, kick(1.2), O['chapter']); add(mus, bass(41, 1.4, 1.1), O['chapter']); add(mus, pad(F[1] + [77], 1.6, .9), O['chapter'])
if END > O['end']:
    LOOP = [F, Dm, Bb, C]
    C2 = TL['CH2']; LAST = int(round(TL['DUR'] / BAR)) - 1          # 最后一小节单独收
    for b in range(5, LAST):
        root, ch = LOOP[(b - 5) % 4]
        step = (b - 6) // 4 if b < 27 else (3 if b >= 37 else 1 if b < 28 else 0) # 第一章第几步；第二章前段稀、配乐那步和收尾满
        if b >= 40: step = 4
        if b == 27: add(mus, kick(1.2), at(b)); add(mus, bass(41, 1.4, 1.1), at(b)); add(mus, pad(F[1] + [77], BAR + .3, .9), at(b)); continue   # 白闪那一小节：只留一锤和长音
        add(mus, pad(ch, BAR + .3, .6), at(b))
        for beat in range(4):
            if not (b == 5 and beat == 0): add(mus, kick(1. if beat % 2 == 0 else .85), at(b, beat))
            if beat % 2: add(mus, clap(.8), at(b, beat), pan=-.05)
            subdiv = 4 if step in (1, 4) else 2                       # Grok 读资料、9 台机器那两步用十六分音符踩镲
            for k in range(subdiv):
                add(mus, hat(.45 if k % 2 else .3, op=(k == subdiv - 1 and beat == 3)), at(b, beat + k / subdiv), pan=.25)
        for k in range(8):
            add(mus, bass(root + (12 if k in (3, 6) else 0), BEAT / 2 * .9), at(b, k / 2))
        if step >= 3:                                                  # 第 4、5 步：木琴琶音
            for k in range(8): add(mus, marimba([ch[0], ch[1], ch[2], ch[1] + 12][k % 4], .35), at(b, k / 2), pan=.3 * (-1) ** k)
    for t0, _ in C1['steps'] + C2['steps']: add(fx, crash(.5), t0)    # 每一步开头一个镲
    # 最后一小节：三个一起跳，落地一锤收住，长音拖尾
    add(mus, kick(1.2), at(LAST)); add(mus, pad(F[1] + [77], BAR * 1.2, .8), at(LAST)); add(mus, bass(41, BAR, 1.0), at(LAST))
    add(fx, riser(BEAT * 2, .6), at(LAST)); add(fx, impact(1.3), at(LAST, 2)); add(mus, pad(F[1] + [77, 84], BAR * .9, .9), at(LAST, 2))
    add(fx, riser(BAR, .7), at(39))
    for m in (77, 81, 84, 89): add(fx, bell(m, .4, 1.6), C2['endcard'] + (m - 77) * .02)   # 片尾卡出现：一串铃
    for i, ts in enumerate(C2['shots']): add(fx, click(1.6, .5), ts, pan=-.3)        # 截一帧：咔嚓
    add(mus, riser(BAR, .8), at(26)); add(fx, impact(1.2), at(27))     # 转第二章：上行 + 一锤
    PENT = [72, 74, 77, 79, 81, 84]
    def typing(a, b, n):                                               # 打字：一个字一声轻敲
        for i in range(n): add(fx, click(1 + .15 * (i % 3), .25), a + (b - a) * i / n, pan=.1)
    typing(*C1['typing'], 18); typing(*C1['kb_typing'], 12)
    for tt in C1['tabs']: typing(tt, tt + .42, 8)                  # 每踩开一个文件，代码刷一下
    add(fx, pop(.5), C1['send'])
    for i, t in enumerate(C1['items']): add(fx, bell(PENT[i], .6), t)
    for i, t in enumerate(C1['owners']): add(mus, marimba(PENT[i] - 12, .6), t)
    # 角色动作：大跳 = 弹簧音 + 嗖 + 落地一锤；一拍一格的小跳 = 按落的格子出声（踏板铃铛逐级升高、图标"啵"+和弦、界面格子木琴、机器高音铃）
    PANK = {'claude': 0, 'codex': -.3, 'grok': .3}
    tile_n = 0
    for k, evs in ACT.items():
        pan = PANK[k]
        for i, e in enumerate(evs):
            if e[0] == 'warp':                                         # 从洞里冒出来：吸出来的反向扫频 + 落地
                add(fx, ripple(.6), e[1], pan=pan); add(fx, boing(.6), e[1] + .1, pan=pan); add(fx, thump(.6, 80), e[2], pan=pan)
            if e[0] == 'jump' and e[1] >= O['end'] - .1:
                cell = e[7]
                if e[4] >= 1.0 and not (cell.startswith('score:n') or cell in ('s0', 's1', 's2', 's3')):
                    add(fx, boing(.6), e[1], pan=pan); add(fx, whoosh(.45, .5), e[1] + .08, pan=pan); add(fx, thump(.75, 70), e[2], pan=pan)
                elif cell.startswith('p'):
                    add(fx, bell(PENT[int(cell[-1]) + 1] + 12, .45, .6), e[2], pan=pan); add(fx, thump(.35, 110), e[2], pan=pan)
                elif cell.startswith('i_'):
                    add(fx, pop(.6), e[2], pan=pan); add(fx, thump(.6, 80), e[2], pan=pan)
                    for m in (72, 76, 79): add(mus, marimba(m, .45), e[2], pan=pan)
                elif cell.startswith('score:n'):                      # 配乐那一步：落哪个音符格子就响哪个音（F 大调上行）
                    add(mus, marimba([65, 67, 69, 72, 74, 77, 79, 81][int(cell[-1])], .9), e[2], pan=pan); add(mus, bell([65, 67, 69, 72, 74, 77, 79, 81][int(cell[-1])] + 12, .35), e[2], pan=pan)
                elif cell in ('s0', 's1', 's2', 's3'):                # 统计台：数字弹出一个和弦
                    add(fx, pop(.6), e[2], pan=pan); add(fx, thump(.7, 75), e[2], pan=pan)
                    for m in (72, 76, 79, 84): add(mus, bell(m, .35), e[2], pan=pan)
                elif cell.startswith('d_'):
                    add(fx, bell(88 + (i % 4) * 2, .45, .6), e[2], pan=pan); add(fx, thump(.4, 95), e[2], pan=pan)
                else:
                    add(mus, marimba(PENT[i % 6], .6), e[2], pan=pan); add(fx, thump(.3, 120), e[2], pan=pan)
            elif e[0] == 'hop' and e[1] > O['end']: add(fx, bell(PENT[i % 6] + 12, .25, .45), e[1], pan=pan)
            elif e[0] == 'slam': add(fx, impact(.8), e[2], pan=pan)
    a, b = C1['torrent']; add(fx, riser(b - a, .7), a); add(fx, whoosh(.8, .6), a + .2)
    for j in range(24): add(fx, pop(.18), a + .5 + (b - a - .5) * j / 24 + .45, pan=.3)   # 判断卡一张张落到塔上
    for a_, b_ in (C1['jcard'], C1['doc']): add(fx, whoosh(b_ - a_, .7), a_)
    add(fx, ripple(.7), C1['split'])
    for i in range(3): add(fx, bell(84 + 3 * i, .5), C1['subs'][1] - .25 + .12 * i)    # 三个分身各自完成
    for i, tc in enumerate(C1['checks']):                             # 审查：踩到有问题的格子是低音，没问题是高音
        add(fx, bell(70 if i in (1, 4) else 88, .4, .5), tc, pan=-.3)
    add(fx, impact(1.), C1['stamp'])
    a, b = C1['gen']; add(fx, riser(b - a, .6), a); add(fx, bell(88, .7), b)
    a, b = C1['reveal']; add(fx, whoosh(b - a, .9), a); add(fx, crash(.7), b)
    for e in TL['EDGES']: add(fx, bell(96, .12, .3), e[2], pan=.4)      # 连线亮起：细碎的提示音
    for m in (77, 81, 84): add(fx, bell(m, .45), C1['archived'])        # 核对完：一个和弦
    a, b = C1['dive']; add(fx, whoosh(b - a + .3, .9), a); add(fx, ripple(.8), a + .15)

# ---------- 动作音效（全部从时间表取时间点）----------
SC = [72, 76, 79, 84]                                  # 铃铛音高：消息弹出依次升高
add(fx, bell(84, .6), 0.02)                            # 第 0 帧：Claude 的消息已在，轻提示一声
add(fx, bell(SC[1], .7), O['reply']['codex'], pan=-.2); add(fx, bell(SC[2], .7), O['reply']['grok'], pan=.2)
for k, pan in (('claude', -.2), ('codex', -.35), ('grok', .35)):
    e = O[k]
    add(fx, peel(), e['peel'], pan=pan)
    add(fx, pop(.35), e['stand'], pan=pan)
    n = 8 if k == 'claude' else 5                       # 转身变立体：木琴上行
    for i in range(n):
        tt = e['stand'] + (e['spin_end'] - e['stand']) * i / n
        add(mus, marimba([65, 69, 72, 77, 81, 84, 89, 93][i], .55), tt, pan=pan)
    add(fx, whoosh(.35, .5), e['spin_end'] - .2, pan=pan)
    add(fx, boing(.8), e['jump'], pan=pan); add(fx, ripple(.6), e['jump'], pan=pan)
    add(fx, whoosh(.45, .6), e['jump'] + .1, pan=pan)
    add(fx, thump(.9, 70), e['land'], pan=pan * .5)
add(fx, impact(1.), O['title'])                        # Grok 落地 = 标题砸下
for i, h in enumerate(O['hops']): add(fx, bell([79, 81, 84, 88][i], .5), h, pan=(-.3, .3, -.15, .15)[i])
add(fx, riser(O['chapter'] - O['hops'][-1], .9), O['hops'][-1])
add(fx, whoosh(.5, .8), O['bigjump'])
add(fx, impact(1.2), O['chapter'])

# ---------- 混音 ----------
mix = mus * .8 + fx * .9
for c in range(2): mix[:, c] = compress(mix[:, c], thr=.35, ratio=2.5)
mix = mix[:int(END * SR)]
fade = int(.35 * SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix = mix / np.abs(mix).max() * .5
# 简单响度校正到约 −14 LUFS（RMS 近似），再限幅到 −1 dBFS
rms = np.sqrt((mix ** 2).mean()); mix *= 10 ** (-15.5 / 20) / max(rms, 1e-9)
for c in range(2): mix[:, c] = limit(mix[:, c], ceil=10 ** (-1.8 / 20))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'out', 'mix.wav')
os.makedirs(os.path.dirname(out), exist_ok=True)
sf.write(out, mix.astype(np.float32), SR, subtype='PCM_24')
print('mix', out, f'{len(mix) / SR:.2f}s')
