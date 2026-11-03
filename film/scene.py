"""《一个人的 AI 团队》3D 场景：全部由代码搭、由时间函数驱动，不手调关键帧（脚本每帧算一次位置写进去）。
用法（Blender 后台）：
  Blender -b --factory-startup -P scene.py -- <贴图根目录> <输出目录> <起始帧> <结束帧> [选项]
  贴图根目录下每块屏幕一个子目录（chat/、mac/、queue/…），文件名 = 全片帧号。
  --preview：540×960、低采样，看构图用。  --step N：每 N 帧渲一张。  --frames a,b,c：只渲这几帧。
  --save <x.blend>：只存工程不渲染。
坐标：桌面 z=0，相机在 -Y 往 +Y 看；平板竖放，聊天界面顶部朝 +Y。"""
import bpy, json, math, os, sys, random
from mathutils import Vector, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:]
TEX, OUT, F0, F1 = argv[0], argv[1], int(argv[2]), int(argv[3])
CHAT = os.path.join(TEX, 'chat')
FRAMES = [int(x) for x in argv[argv.index('--frames') + 1].split(',')] if '--frames' in argv else None
if FRAMES: F0, F1 = min(FRAMES), max(FRAMES)
PREVIEW = '--preview' in argv
TL = json.load(open(os.path.join(HERE, 'timeline.json'), encoding='utf-8'))
O, FPS = TL['OPEN'], TL['FPS']
C1, ACT = TL['CH1'], TL['ACT']
NF = int(round(TL['DUR'] * FPS))      # 全片帧数（屏幕贴图序列按全片帧号取图）

# ---------- 小工具 ----------
clamp = lambda x, a=0., b=1.: max(a, min(b, x))
lerp = lambda a, b, u: a + (b - a) * u
smooth = lambda u: (lambda v: v * v * v * (v * (6 * v - 15) + 10))(clamp(u))      # smootherstep
out3 = lambda u: 1 - (1 - clamp(u)) ** 3
def back(u, s=1.9):            # 带过冲的缓出（揭起、站起来用）
    u = clamp(u) - 1; return 1 + (s + 1) * u ** 3 + s * u ** 2
def pop01(u):                  # 0→1 带过冲的弹出
    u = clamp(u); return 0 if u <= 0 else 1 - (1 - u) ** 3 * math.cos(u * 7.5)
def spring(u, k=9., w=11.):    # 落地后的弹性回弹：1 → 0 的衰减振荡
    return math.exp(-k * u) * math.cos(w * u) if u >= 0 else 1.

def mat(name, rgb, rough=.45, metal=0., emit=None, es=0.):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = es
    return m

def box(name, size, loc, m, parent, rot=(0, 0, 0), bevel=.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(m)
    if bevel:
        md = o.modifiers.new('bv', 'BEVEL'); md.width = bevel; md.segments = 3
    o.parent = parent
    return o

# ---------- 场景 ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, TL['SAMPLE_FRAMES']

w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (.010, .010, .018, 1)

# 桌面：深色、带一点反光，屏幕和角色能在桌面上看到倒影
bpy.ops.mesh.primitive_plane_add(size=1, location=(15, 0, 0)); bpy.context.object.scale = (80, 40, 1)   # 长桌：开场平板 + 第一章五个工位
bpy.context.object.data.materials.append(mat('desk', (.025, .024, .03), rough=.28))

# 平板：圆角机身 + 屏幕（聊天界面序列帧做自发光贴图）
SW, SH, SZ = TL['SW'], TL['SH'], TL['SZ']          # 横放：2.6 × 1.625（界面 1600×1000）
body = box('tablet', (SW + .14, SH + .14, .06), (0, 0, .03), mat('alu', (.05, .05, .058), rough=.32, metal=.6), None, bevel=.05)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, SZ)); scr = bpy.context.object; scr.scale = (SW, SH, 1)
ms = mat('screen', (0, 0, 0), rough=.12); nt = ms.node_tree
img = bpy.data.images.load(os.path.join(CHAT, '0001.png')); img.source = 'SEQUENCE'
tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img
tx.image_user.frame_duration = NF; tx.image_user.frame_start = 1; tx.image_user.use_auto_refresh = True
bsdf = nt.nodes['Principled BSDF']
nt.links.new(tx.outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 1.15
scr.data.materials.append(ms)

px2w = lambda px, py: ((px / TL['PX'][0] - .5) * SW, (.5 - py / TL['PX'][1]) * SH)   # 聊天界面像素 → 屏幕上的 3D 坐标

# 灯：主光偏暖 + 粉、青两道轮廓光（角色身上的糖果色只做点缀）
def area(name, loc, tgt, power, rgb, size=1.5):
    bpy.ops.object.light_add(type='AREA', location=loc); L = bpy.context.object; L.name = name
    L.data.energy = power; L.data.color = rgb; L.data.size = size
    L.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return L
area('key', (-2.6, -3.2, 3.6), (0, -.8, 0), 520, (1, .93, .85), 2.5)
area('rimP', (2.2, .2, 1.7), (0, -1.6, .2), 140, (1, .3, .62))
area('rimC', (-2.2, 0, 1.6), (0, -1.6, .2), 190, (.25, .8, 1))
area('fill', (0, -6, 2.2), (0, -1, .3), 70, (1, 1, 1), 3)
CH1_LIGHTS = []                         # 第一章每个工位一套灯；开场期间能量为 0，开场画面不受影响
for cx in (3.8, 7.6, 11.4, 15.2, 20.0, 24.8, 32.0, 35.8, 39.6, 43.4, 48.5):
    k_ = 760 if cx == 20.0 else 520
    for L in (area(f'key{cx}', (cx - 2.6, -3.2, 3.6), (cx, -.6, 0), k_, (1, .93, .85), 2.5),
              area(f'rimP{cx}', (cx + 2.2, .6, 2.4), (cx, -.4, .2), 70, (1, .3, .62)),
              area(f'rimC{cx}', (cx - 2.2, .4, 2.3), (cx, -.4, .2), 100, (.25, .8, 1)),
              area(f'fill{cx}', (cx, -6, 2.2), (cx, -.8, .3), 70, (1, 1, 1), 3)):
        CH1_LIGHTS.append((L, L.data.energy))

# 远处的彩色光斑（景深虚掉）
random.seed(7)
PAL = [(1, .35, .6), (.3, .85, 1), (1, .62, .3), (.65, .45, 1), (1, .9, .5)]
for i in range(18):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(.04, .09),
        location=(random.uniform(-4.5, 4.5), random.uniform(3.5, 9), random.uniform(.3, 3.2)))
    c = PAL[i % len(PAL)]; bpy.context.object.data.materials.append(mat(f'bk{i}', c, emit=c, es=random.uniform(4, 9)))
random.seed(11)                        # 第一章长桌后面也撒一些（不动开场那 18 个，小样画面不变）
for i in range(70):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(.04, .09),
        location=(random.uniform(4.5, 35), random.uniform(3.5, 9), random.uniform(.3, 3.2)))
    c = PAL[i % len(PAL)]; bpy.context.object.data.materials.append(mat(f'bk2_{i}', c, emit=c, es=random.uniform(2, 4.5)))
random.seed(13)                        # 第二章和收尾那段
for i in range(45):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(.04, .09),
        location=(random.uniform(35, 56), random.uniform(3.5, 9), random.uniform(.3, 3.2)))
    c = PAL[i % len(PAL)]; bpy.context.object.data.materials.append(mat(f'bk3_{i}', c, emit=c, es=random.uniform(2, 4.5)))

# ---------- 第一章：工位（平躺的发光屏）、全息平台和 9 台机器、道具 ----------
def seq_mat(name, page, still=False, es=None):
    m = mat(name, (0, 0, 0), rough=.32); n = m.node_tree   # 屏幕略哑光：灯的反光不要盖住界面上的字
    first = sorted(f for f in os.listdir(os.path.join(TEX, page)) if f.endswith('.png') and not f.startswith('.'))[0]   # 跳过 macOS 打包带进来的 ._ 隐藏文件（11-02 在 3060Ti 上整屏粉色就是它）   # 序列：任取一张，Blender 按帧号找其它
    im = bpy.data.images.load(os.path.join(TEX, page, first))
    if not still: im.source = 'SEQUENCE'
    t_ = n.nodes.new('ShaderNodeTexImage'); t_.image = im
    if not still:
        t_.image_user.frame_duration = NF; t_.image_user.frame_start = 1; t_.image_user.use_auto_refresh = True
    b = n.nodes['Principled BSDF']; n.links.new(t_.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = es if es is not None else (.5 if page.startswith('kb') else 1.1)   # 知识书房是浅色界面，同样亮度会发白
    return m
def emat(name, rgb, es):
    return mat(name, (0, 0, 0), emit=rgb, es=es)
def standing_plane(name, w_, h_, m, parent):   # 竖起来的面片，原点在底边中点，正面朝 -Y
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, h_ / 2), rotation=(math.pi / 2, 0, 0)); o = bpy.context.object
    o.name = name; o.scale = (w_, h_, 1); o.data.materials.append(m); o.parent = parent; return o
def empty(name):
    e = bpy.data.objects.new(name, None); sc.collection.objects.link(e); return e

alu = bpy.data.materials['alu']
HAS_CH1 = True                  # 永远搭完整场景（原来按渲染范围判断，分段渲染时开场和第一章接缝处场景会突然变，11-02 修）
SZ1, PZ = TL['SZ'], TL['PZ']
if HAS_CH1:
    SCREENS = {}
    for k, st in list(TL['ST'].items()) + list(TL['SUBT'].items()):
        (cx, cy), (w_, d_) = st['c'], st.get('s', (SW, SH))
        box('slab_' + k, (w_ + .1, d_ + .1, .06), (cx, cy, .03), alu, None, bevel=.04)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, cy, SZ1)); o = bpy.context.object
        o.scale = (w_, d_, 1); m_ = seq_mat('scr_' + k, st['page']); o.data.materials.append(m_); SCREENS[k] = m_
    # 图标格子：每个工具前一个，跳上去 = 打开这个工具
    FONT = bpy.data.fonts.load(os.path.join(HERE, '..', 'opus60', 'fonts', 'NotoSansSC.ttf'))
    def label3d(name, text, loc, size, rgb=(1, 1, 1), es=3, rot=(0, 0, 0)):
        cu = bpy.data.curves.new(name, 'FONT'); cu.body = text; cu.font = FONT; cu.size = size; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
        o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o); o.data.materials.append(emat(name + 'm', rgb, es))
        o.location = loc; o.rotation_euler = rot; return o
    ICON_STYLE = {'mac': ('主控', (.3, .55, 1)), 'kb': ('书房', (.25, .8, .5)), 'code': ('代码', tuple(TL['CLAUDE_RGB'])), 'review': ('审查', (.85, .85, .92))}
    CELL_OBJ = {}                                  # 格子 id → (根物体, 发光材质, 基础亮度)
    for k in TL['ICONS']:
        x, y, z = TL['CELLS']['i_' + k]; txt, col = ICON_STYLE[k]
        root = empty('icon_' + k); root.location = (x, y, 0)
        box('iconb_' + k, (.5, .5, .05), (0, 0, .025), mat('iconbm_' + k, (.04, .04, .05), rough=.3, metal=.4), root, bevel=.03)
        em = emat('icont_' + k, col, 2.5); box('icont_' + k, (.44, .44, .004), (0, 0, .051), em, root, bevel=0)
        lb = label3d('iconl_' + k, txt, (0, 0, .056), .15, (1, 1, 1), 4); lb.parent = root; lb.location = (0, 0, .056)
        CELL_OBJ['i_' + k] = (root, em, 2.5)
    for cid, (x, y, z) in TL['CELLS'].items():     # 踏板格子：一排发光边框的小方块
        if not cid.startswith('p'): continue
        root = empty('tile_' + cid); root.location = (x, y, 0)
        box('tileb_' + cid, (.3, .3, .03), (0, 0, .015), mat('tilebm', (.035, .035, .045), rough=.3, metal=.4) if 'tilebm' not in bpy.data.materials else bpy.data.materials['tilebm'], root, bevel=.01)
        em = emat('tilee_' + cid, (.35, .7, 1), .8); box('tilee_' + cid, (.26, .26, .003), (0, 0, .0305), em, root, bevel=0)
        CELL_OBJ[cid] = (root, em, .8)

    STAT_OBJ = []                                  # 收尾统计台：角色落上去，数字弹出来
    for i, (num, lab) in enumerate(TL['STATS']):
        x, y, z = TL['CELLS'][f's{i}']; col = ((.3, .55, 1), (.25, .8, .5), tuple(TL['CLAUDE_RGB']), (.85, .85, .92))[i]
        root = empty(f'stat{i}'); root.location = (x, y, 0)
        box(f'statb{i}', (.8, .5, .08), (0, 0, .04), mat(f'statbm{i}', (.04, .04, .05), rough=.3, metal=.4), root, bevel=.03)
        em = emat(f'state{i}', col, 2.0); box(f'state{i}', (.74, .44, .004), (0, 0, .081), em, root, bevel=0)
        CELL_OBJ[f's{i}'] = (root, em, 2.0)
        sign = empty(f'stats{i}'); sign.location = (x, y + .32, .1)
        n_ = label3d(f'statn{i}', num, (0, 0, .62), .6 if len(num) < 6 else .44, (1, 1, 1), 8, rot=(math.radians(78), 0, 0)); n_.parent = sign; n_.location = (0, 0, .62)
        l_ = label3d(f'statl{i}', lab, (0, 0, .25), .19, (1, 1, 1), 6, rot=(math.radians(78), 0, 0)); l_.parent = sign; l_.location = (0, 0, .25)
        STAT_OBJ.append(sign)

    # 全息平台：深色圆台 + 发光同心圆 + 放射线（慢慢转）
    (mx, my), MR = TL['MAP']['c'], TL['MAP']['r']
    bpy.ops.mesh.primitive_cylinder_add(radius=MR, depth=PZ, location=(mx, my, PZ / 2), vertices=96)
    bpy.context.object.data.materials.append(mat('plat', (.02, .022, .03), rough=.25, metal=.4))
    holo = empty('holo'); holo.location = (mx, my, PZ + .002)
    for i, (rr, c) in enumerate(((MR - .04, (.3, .7, 1)), (MR * .7, (.35, .9, 1)), (MR * .38, (.6, .5, 1)))):
        bpy.ops.mesh.primitive_torus_add(major_radius=rr, minor_radius=.006, location=(0, 0, 0)); o = bpy.context.object
        o.data.materials.append(emat(f'ring{i}', c, 4)); o.parent = holo
    for i in range(16):
        a_ = i * math.pi / 8
        box(f'ray{i}', (MR * .62, .004, .002), (math.cos(a_) * MR * .62 / 2 + math.cos(a_) * MR * .38, math.sin(a_) * MR * .62 / 2 + math.sin(a_) * MR * .38, 0),
            emat(f'raym{i}', (.3, .6, 1), 1.5), holo, rot=(0, 0, a_), bevel=0)

    # 9 台机器（体素风格的简化模型，真实设备清单）
    DEVS, STRIPS = {}, {}
    dark = mat('devdark', (.03, .03, .035), rough=.35, metal=.4)
    silver = mat('devsilver', (.62, .63, .66), rough=.25, metal=.85)
    for name, d in TL['DEV'].items():
        (x, y), (w_, d_, h_) = d['p'], d['s']
        root = empty('dev_' + name); root.location = (x, y, PZ); DEVS[name] = root
        kind = d['kind']
        if kind == 'macstudio':
            box(name + 'b', (w_, d_, h_), (0, 0, h_ / 2), silver, root, bevel=.04)
            sm = emat(name + 's', (1, 1, 1), 3); box(name + 'l', (.02, .006, .02), (w_ * .3, -d_ / 2 - .004, h_ * .3), sm, root, bevel=0)
            CELL_OBJ['d_' + name] = (root, sm, 3)
        elif kind in ('tower', 'rgbtower', 'nas', 'mini'):
            box(name + 'b', (w_, d_, h_), (0, 0, h_ / 2), dark if kind != 'mini' else mat(name + 'm', (.12, .12, .14), rough=.3, metal=.5), root, bevel=.02)
            sm = emat(name + 's', (.25, .55, 1) if kind != 'nas' else (.2, .5, 1), 3)
            if kind in ('tower', 'rgbtower'):
                box(name + 'l', (.012, .006, h_ * .75), (w_ * .3, -d_ / 2 - .004, h_ * .5), sm, root, bevel=0)
            elif kind == 'mini':
                box(name + 'l', (.03, .006, .012), (0, -d_ / 2 - .004, h_ * .5), sm, root, bevel=0)
            else:   # NAS：四个硬盘位，每个一颗灯
                LEDS = []
                for i, dx in enumerate((-.15, -.05, .05, .15)):
                    box(f'bay{i}', (.08, .012, h_ * .62), (dx, -d_ / 2 - .004, h_ * .42), mat(f'bay{i}', (.07, .07, .08), rough=.5), root, bevel=.006)
                    lm = emat(f'led{i}', (.2, .5, 1), 2); box(f'led{i}', (.025, .012, .025), (dx, -d_ / 2 - .012, h_ * .82), lm, root, bevel=0); LEDS.append(lm)
            STRIPS[name] = sm
            CELL_OBJ['d_' + name] = (root, sm, 3)
        elif kind == 'laptop':
            box(name + 'b', (w_, d_, .02), (0, 0, .01), silver, root, bevel=.008)
            lid = empty(name + 'lid'); lid.parent = root; lid.location = (0, d_ / 2, .02); lid.rotation_euler = (math.radians(-15), 0, 0)
            box(name + 'lb', (w_, .012, d_), (0, 0, d_ / 2), silver, lid, bevel=.006)
            STRIPS[name] = emat(name + 's', (.25, .55, 1), 2)
            box(name + 'sc', (w_ * .9, .004, d_ * .85), (0, -.008, d_ / 2), STRIPS[name], lid, bevel=0)
            CELL_OBJ['d_' + name] = (root, STRIPS[name], 2)
        if d['label']:   # 悬浮标签（中文，正对镜头略后仰）
            cu = bpy.data.curves.new('lab_' + name, 'FONT'); cu.body = d['label']; cu.font = FONT; cu.size = .13; cu.align_x = 'CENTER'
            to = bpy.data.objects.new('lab_' + name, cu); sc.collection.objects.link(to); to.data.materials.append(emat('labm' + name, (1, 1, 1), 3))
            to.location = (x, y - d_ / 2, PZ + h_ + .12); to.rotation_euler = (math.radians(70), 0, 0)
    # 调度台上方的全息面板：Prefect 运行列表（真实流程名）
    hp = empty('holopanel'); hp.location = (TL['MAP']['c'][0] + 1.0, TL['MAP']['c'][1] + 1.75, PZ + .55); hp.rotation_euler = (math.radians(-12), 0, math.radians(-12))
    standing_plane('holopanel_s', .78, 1.07, seq_mat('queue', 'queue', es=1.4), hp)

    # 连线（抬高的弧线）+ 线上流动的光点
    def arc_pts(a, b, n=24, h=.45):
        return [a.lerp(b, i / (n - 1)) + Vector((0, 0, h * 4 * (i / (n - 1)) * (1 - i / (n - 1)))) for i in range(n)]
    ECOL = {'blue': (.3, .65, 1), 'green': (.3, 1, .45)}
    EDGE_OBJ = []
    for ei, (a, b, t_on, t_off, col) in enumerate(TL['EDGES']):
        pa = Vector((*TL['DEV'][a]['p'], PZ + TL['DEV'][a]['s'][2] * .7)); pb = Vector((*TL['DEV'][b]['p'], PZ + TL['DEV'][b]['s'][2] * .7))
        pts = arc_pts(pa, pb)
        cu = bpy.data.curves.new(f'edge{ei}', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = .006
        sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
        for i, q in enumerate(pts): sp.points[i].co = (*q, 1)
        eo = bpy.data.objects.new(f'edge{ei}', cu); sc.collection.objects.link(eo)
        em = emat(f'edgem{ei}', ECOL[col], 0); eo.data.materials.append(em)
        pulses = [box(f'pulse{ei}_{j}', (.035, .035, .035), (0, 0, 0), emat(f'pm{ei}_{j}', ECOL[col], 12), None, bevel=0) for j in range(3)]
        EDGE_OBJ.append((pts, em, pulses, t_on, t_off))

    # 资料龙卷风：90 张资料卡卷进 Grok；判断卡一张张吐出来叠成塔
    random.seed(23)
    DOCS = [box(f'doc{i}', (.09, .004, .12), (0, 0, 0), mat(f'docm{i % 3}', ((.95, .95, .97), (.85, .9, 1), (1, .95, .85))[i % 3], rough=.5) if i < 3 else bpy.data.materials[f'docm{i % 3}'], None, bevel=0) for i in range(90)]
    kbx, kby = TL['ST']['kb']['c']
    DOC0 = [(Vector((random.uniform(kbx - 1.15, kbx + 1.15), random.uniform(kby - .7, kby + .7), SZ1 + .005)), random.uniform(0, 2 * math.pi)) for _ in DOCS]
    jm = mat('jcm', (.98, .97, .95), rough=.45); js = emat('jcs', (1, .54, .4), 3)
    JC = []
    for j in range(24):
        r_ = empty(f'jc{j}'); box(f'jcb{j}', (.16, .22, .008), (0, 0, 0), jm, r_, bevel=0); box(f'jcs{j}', (.16, .04, .009), (0, .08, .001), js, r_, bevel=0); JC.append(r_)
    # 递给 Claude 的那张判断卡（真实内容）、Claude 踢给 Codex 的文件
    JCARD = empty('jcard'); standing_plane('jcard_s', .45, .6, seq_mat('kbcard', 'kbcard', still=True, es=.9), JCARD)
    DOCK = empty('dockick'); box('dockb', (.2, .012, .27), (0, 0, .135), mat('dockm', (.95, .95, .97), rough=.4), DOCK, bevel=.005)
    box('docks', (.2, .014, .05), (0, -.001, .22), emat('docks', (.4, .7, 1), 3), DOCK, bevel=0)
    # Codex：封面图显影框
    GEN = empty('genframe'); box('genbk', (.76, .02, 1.0), (0, .012, .5), mat('genbkm', (.05, .05, .06), rough=.3, metal=.5), GEN, bevel=.01)
    standing_plane('gen_s', .7, .93, seq_mat('gen', 'gen', es=1.0), GEN).location.z += .035
    # 转场：Claude 扎进去的地方荡开的光环
    RINGS = []
    for i in range(2):
        bpy.ops.mesh.primitive_torus_add(major_radius=.2, minor_radius=.012); o = bpy.context.object
        o.data.materials.append(emat(f'portal{i}', (.6, .85, 1), 10)); RINGS.append(o)

# ---------- 角色 ----------
# 统一骨架：身体 + 两只手 + 四条腿，原点在脚底中心，正面朝 -Y。尺寸 = 贴纸大小（约 0.28）。
BW, BD, BH, LH = .22, .17, .19, .06
HC = LH + BH / 2            # 身体中心高度（空翻绕这里转）
def critter(key, body_rgb, rough=.42, metal=0.):
    root = bpy.data.objects.new(key, None); sc.collection.objects.link(root)
    mb = mat(key + '_b', body_rgb, rough, metal)
    box(key + '_body', (BW, BD, BH), (0, 0, LH + BH / 2), mb, root)
    for s in (-1, 1):
        box(key + '_arm', (.045, .07, .06), (s * (BW / 2 + .02), 0, LH + BH * .45), mb, root, bevel=.006)
    for x in (-.075, -.028, .028, .075):
        box(key + '_leg', (.032, .05, LH + .01), (x, 0, LH / 2), mb, root, bevel=.004)
    return root

black = mat('eye', (.005, .005, .005), rough=.3)
glow = mat('glow', (1, 1, 1), emit=(1, 1, 1), es=3.5)
FY = -BD / 2 - .004        # 正面贴脸的 y

claude = critter('claude', tuple(TL['CLAUDE_RGB']))                       # Claude Code 的 Clawd，体素化
for s in (-1, 1): box('c_eye', (.026, .012, .05), (s * .055, FY, LH + BH * .62), black, claude, bevel=0)

codex = critter('codex', (.82, .82, .84), rough=.38)                # 白色外壳，黑色眼睛：脸是终端提示符 >_
for (x, z, r) in ((-.062, LH + BH * .66, 40), (-.062, LH + BH * .48, -40)):
    box('x_gt', (.05, .012, .016), (x, FY, z), black, codex, rot=(0, math.radians(r), 0), bevel=0)
box('x_us', (.06, .012, .016), (.035, FY, LH + BH * .4), black, codex, bevel=0)

grok = critter('grok', (.006, .006, .007), rough=.18, metal=.2)     # 自设计：亮黑机身，白眼 + 一道斜杠
for s in (-1, 1): box('g_eye', (.03, .012, .03), (s * .055, FY, LH + BH * .66), glow, grok, bevel=0)
box('g_sl', (.012, .012, .1), (0, FY, LH + BH * .32), glow, grok, rot=(0, math.radians(-35), 0), bevel=0)

MINIS = []
if HAS_CH1:                   # Claude 的 3 个分身（子代理）：小一号的 Clawd
    for i in range(3):
        m_ = critter(f'mini{i}', tuple(TL['CLAUDE_RGB']))
        for s_ in (-1, 1): box('m_eye', (.026, .012, .05), (s_ * .055, FY, LH + BH * .62), black, m_, bevel=0)
        MINIS.append(m_)
STICK = {k: px2w(*v) for k, v in TL['STICK_PX'].items()}
LAND = {k: tuple(v) for k, v in TL['LAND'].items()}
FLIP = {'claude': ('x', -1), 'codex': ('z', 1), 'grok': ('y', 1)}    # 跳出屏幕时各自的花样：前空翻 / 转体 / 侧手翻
JUMPH = {'claude': 1.0, 'codex': .8, 'grok': .9}

def pose(k, t):
    """返回 (位置, 欧拉角, 缩放)。一段一段按时间算：贴纸 → 揭起 → 转身变立体 → 下蹲 → 跳出 → 落地 → 蹦。"""
    e = O[k]; cx, cy = STICK[k]
    start = Vector((cx, cy - (LH + BH) / 2, SZ + .006))
    rx = ry = rz = 0.; sx = sy = sz = 1.; flat = 1.; loc = start.copy()
    p = clamp((t - O['reply'][k]) / .3)
    pop_ = 0 if p <= 0 else 1 - (1 - p) ** 3 * math.cos(p * 7.5)        # 跟聊天气泡一起弹出
    if t < e['jump']:
        u = (t - e['peel']) / (e['stand'] - e['peel'])
        rx = math.radians(-90) * (1 - back(u)) if t > e['peel'] else math.radians(-90)
        v = (t - e['stand']) / (e['spin_end'] - e['stand'])
        rz = 2 * math.pi * smooth(v) * (1 if k == 'claude' else .5) * 2   # Claude 转两圈，另两个转一圈
        flat = lerp(.05, 1, smooth(v))
        c = clamp((t - (e['jump'] - .18)) / .18)                          # 起跳前下蹲
        sz, sx = 1 - .25 * math.sin(c * math.pi / 2), 1 + .12 * math.sin(c * math.pi / 2)
        sx, sy, sz = sx * pop_, flat * pop_ * sx, sz * pop_
        return loc, Euler((rx, 0, rz)), (sx, sy, sz)
    L = Vector(LAND[k])
    if t < e['land']:
        u = (t - e['jump']) / (e['land'] - e['jump'])
        c = start.lerp(L, u) + Vector((0, 0, HC + 4 * JUMPH[k] * u * (1 - u)))   # 身体中心走抛物线
        ax, sgn = FLIP[k]; a = 2 * math.pi * smooth(u) * sgn
        R = Euler((a if ax == 'x' else 0, a if ax == 'y' else 0, a if ax == 'z' else 0))
        loc = c - R.to_matrix() @ Vector((0, 0, HC))
        st = 1 + .18 * (1 - clamp(u * 3)) - .08 * clamp(u * 3 - 2)       # 起跳拉长，快落地时缩
        return loc, R, (1 / st ** .5, 1 / st ** .5, st)
    # 落地以后：回弹 → 按拍子原地蹦 → 一起跳起
    loc = L.copy(); sq = .3 * spring(t - e['land'])
    sx, sz = 1 + sq * .6, 1 - sq
    for h in O['hops']:
        u = (t - h) / .3
        if 0 < u < 1: loc.z += .12 * 4 * u * (1 - u)
    u = (t - O['bigjump']) / (O['chapter'] - O['bigjump'])
    if 0 < u < 1:
        loc.z += .75 * 4 * u * (1 - u); rz = 2 * math.pi * smooth(u) * (1 if k != 'codex' else -1)
    if t >= O['chapter']:
        sq = .3 * spring(t - O['chapter']); sx, sz = 1 + sq * .6, 1 - sq
    return loc, Euler((0, 0, rz)), (sx, sx, sz)

# ---------- 第一章动作引擎 ----------
# 每个角色一串动作（timeline.py 的 ACT）。没在做动作时站在上一个落点，落地后有弹性回弹；起跳前下蹲。
def arc(p0, p1, u, h, ax=None, sgn=0, turns=1):
    c = p0.lerp(p1, u) + Vector((0, 0, HC + 4 * h * u * (1 - u)))
    a = 2 * math.pi * turns * smooth(u) * sgn if ax else 0
    R = Euler((a if ax == 'x' else 0, a if ax == 'y' else 0, a if ax == 'z' else 0))
    st = 1 + .18 * (1 - clamp(u * 3)) - .08 * clamp(u * 3 - 2)
    return c - R.to_matrix() @ Vector((0, 0, HC)), R, (1 / st ** .5, 1 / st ** .5, st)

def act_pose(k, t):
    p = Vector(LAND[k]); land_t, amp = -9, .3; hop = 0.; hidden = False
    evs = ACT[k]
    for i, e in enumerate(evs):
        kind, t0 = e[0], e[1]
        if kind == 'hop':
            u = (t - t0) / .3
            if 0 < u < 1: hop = .12 * 4 * u * (1 - u)
            continue
        t1 = e[2]
        if t < t0:
            break
        if kind == 'jump':
            if t < t1: return arc(p, Vector(e[3]), (t - t0) / (t1 - t0), e[4], e[5], e[6])
            p, land_t, amp = Vector(e[3]), t1, .3
        elif kind == 'slam':                        # 一屁股砸下去：跳高、后仰、重重落下
            if t < t1:
                u = (t - t0) / (t1 - t0); z = .38 * math.sin(math.pi * min(u / .55, 1) / 2) if u < .55 else .38 * (1 - ((u - .55) / .45) ** 2)
                return p + Vector((0, 0, z)), Euler((math.radians(-28) * math.sin(math.pi * u), 0, 0)), (1, 1, 1 + .12 * math.sin(math.pi * u))
            land_t, amp = t1, .5
        elif kind == 'surf':                         # 踩着进度条滑过去：沿途经点匀速，身体前倾
            pts = [p] + [Vector(q) for q in e[3]]
            if t < t1:
                u = smooth((t - t0) / (t1 - t0)); L = [(b - a).length for a, b in zip(pts, pts[1:])]; d = u * sum(L)
                for a, b, l in zip(pts, pts[1:], L):
                    if d <= l or b is pts[-1]:
                        q = a.lerp(b, clamp(d / l)); dirv = (b - a).normalized()
                        return q + Vector((0, 0, .05)), Euler((-.25 * dirv.y, .25 * dirv.x, 0)), (1.05, 1.05, .95)
                    d -= l
            p, land_t, amp = pts[-1], t1, .2
        elif kind == 'spin':                         # 原地转圈（资料往身上卷），转 4 圈（5 圈太快看不清）
            if t < t1:
                u = (t - t0) / (t1 - t0)
                return p + Vector((0, 0, .04 * math.sin(math.pi * u))), Euler((0, 0, 2 * math.pi * 4 * smooth(u))), (1.06, 1.06, .95)
            land_t, amp = t1, .25
        elif kind == 'dive':                         # 扎进屏幕：蹦起、头朝下钻进去
            if t < t1:
                u = (t - t0) / (t1 - t0)
                c = p + Vector((0, 0, HC + .35 * math.sin(math.pi * min(u * 1.6, 1)) - (.9 * clamp((u - .45) / .55) ** 1.5)))
                R = Euler((math.pi * smooth(u * 1.4), 0, 0))
                return c - R.to_matrix() @ Vector((0, 0, HC)), R, (1, 1, 1)
            hidden = True; continue                                        # 已经钻进去了：藏起来，等第二章冒出来
        elif kind == 'warp':                         # 从第二章屏幕中间的洞里蹦出来，空翻落到格子上
            src = Vector(TL['PORTAL2']) - Vector((0, 0, .25))
            if t < t1:
                u = (t - t0) / (t1 - t0); q, R, s_ = arc(src, Vector(e[3]), u, e[4], e[5], e[6]); k_ = clamp(u * 4)
                return q, R, tuple(v * k_ for v in s_)
            p, land_t, amp, hidden = Vector(e[3]), t1, .35, False
    if hidden: return p - Vector((0, 0, 2)), Euler((0, 0, 0)), (0, 0, 0)
    # 站着：落地回弹 + 下一个动作前的下蹲 + 原地蹦
    sq = amp * spring(t - land_t); sx, sz = 1 + sq * .6, 1 - sq
    nxt = next((e for e in evs if e[0] in ('jump', 'slam', 'dive') and e[1] > t), None)
    if nxt:
        c = clamp((t - (nxt[1] - .16)) / .16); sz *= 1 - .22 * math.sin(c * math.pi / 2); sx *= 1 + .1 * math.sin(c * math.pi / 2)
    return p + Vector((0, 0, hop)), Euler((0, 0, 0)), (sx, sx, sz)

FIRST = {k: ACT[k][0][1] for k in ACT}
def pose_all(k, t):
    return pose(k, t) if t < FIRST[k] else act_pose(k, t)

# ---------- 相机 ----------
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
tgt = bpy.data.objects.new('tgt', None); sc.collection.objects.link(tgt)
tc = cam.constraints.new('TRACK_TO'); tc.target = tgt; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
cam.data.lens = 30                                   # 横版
cam.data.dof.use_dof = True; cam.data.dof.focus_object = tgt; cam.data.dof.aperture_fstop = 2.4
cx0, cy0 = STICK['claude']
CAMK = [  # (时间, 机位, 看向)
    (0.0, (.15, -2.0, 1.75), (.05, .0, 0)),                        # 第 0 帧：整块群聊（提问 + 三条回复）都在画面里
    (O['claude']['stand'], (cx0 + .3, cy0 - 1.0, .62), (cx0 + .05, cy0 - .05, .14)),
    (O['claude']['jump'], (cx0 + .5, cy0 - 1.15, .55), (cx0, cy0, .2)),
    (O['claude']['land'] + .15, (0, -2.75, .85), (0, -1.05, .3)),
    (O['title'], (.12, -2.9, .9), (0, -1.0, .3)),
    (O['bigjump'], (-.06, -2.85, .85), (0, -1.05, .3)),
    (O['chapter'], (.1, -2.7, 1.45), (.2, -1.05, .4)),
    (O['end'], (.25, -2.65, 1.5), (.35, -1.05, .4)),
] + [tuple(k) for k in TL['CAM1']]
CAM2 = [tuple(k) for k in TL['CAM2']]
NOPEN = 8                     # CAMK 前 8 个是开场（到小样结尾），之后是第一章
def _hermite(keys, t, idx):
    """非均匀 Catmull-Rom：穿过每个关键点、速度连续，不会在关键点停顿"""
    ts = [k[0] for k in keys]; P = [Vector(k[idx]) for k in keys]
    i = max(0, min(len(ts) - 2, next((j for j in range(len(ts) - 1) if t <= ts[j + 1]), len(ts) - 2)))
    t0, t1 = ts[i], ts[i + 1]; dt = t1 - t0; u = clamp((t - t0) / dt)
    def m(j):
        a, b = max(0, j - 1), min(len(ts) - 1, j + 1)
        return (P[b] - P[a]) / (ts[b] - ts[a])
    h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
    return h00 * P[i] + h10 * dt * m(i) + h01 * P[i + 1] + h11 * dt * m(i + 1)
def campose(t):
    loc = None
    if t <= O['end']:
        for (t0, l0, g0), (t1, l1, g1) in zip(CAMK[:NOPEN], CAMK[1:NOPEN]):
            if t <= t1:
                u = smooth((t - t0) / (t1 - t0))
                loc, g = Vector(l0).lerp(Vector(l1), u), Vector(g0).lerp(Vector(g1), u); break
    if loc is None:
        ks = CAMK[NOPEN - 1:] if t < TL['CH2']['start'] else CAM2
        loc, g = _hermite(ks, t, 1), _hermite(ks, t, 2)
    # 跟拍对开场段也生效（11-02：原来只在开场结束后才叠加，第一章第一跳在 11 秒处镜头猛甩）
    for (t0, t1, who, off) in TL['FOLLOW']:              # 跟拍：飞行途中镜头跟着走
        w = smooth((t - t0) / .25) * smooth((t1 + .15 - t) / .3)
        if w > 0 and HAS_CH1:
            q = follow_pos(who, t)
            loc, g = loc.lerp(q + Vector(off), w), g.lerp(q, w)
    k = clamp((t - O['end']) / .5)                       # 手持感：很轻的漂移（开场不加）
    loc = loc + k * Vector((.012 * math.sin(1.3 * t), .008 * math.sin(.9 * t + 1), .01 * math.sin(1.1 * t + 2)))
    return loc, g

# ---------- 逐帧写入（代码算的，不是手 K 的）----------
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'   # 每帧都有值，帧间线性即可（运动模糊用）
CH = {'claude': claude, 'codex': codex, 'grok': grok}
def key(ob, f, *props):
    for p in props: ob.keyframe_insert(p, frame=f)
C1 = TL['CH1']; CELLS = {k: Vector(v) for k, v in TL['CELLS'].items()} if HAS_CH1 else {}; G = CELLS.get('kb:search', Vector())
def hump(a, b, u, h):         # 两点间的抛物线
    return a.lerp(b, u) + Vector((0, 0, 4 * h * u * (1 - u)))
STACK = Vector(TL['STACK'])
def jcard_pose(t):            # 判断卡：从塔顶升起立直 → 飞向 Claude → 被吸收
    a0, a1 = C1['kb_card'], C1['jcard'][0]; b1 = C1['jcard'][1]
    top = STACK + Vector((0, 0, .02 + 24 * .012))
    claude_at = CELLS['i_code'] + Vector((0, 0, .38))
    if t < a0: return top, Euler((math.radians(-90), 0, 0)), 0
    if t < a1:
        u = (t - a0) / (a1 - a0); return top + Vector((0, 0, .45 * smooth(u))), Euler((math.radians(-90) * (1 - back(u)), 0, 0)), 1
    if t < b1:
        u = smooth((t - a1) / (b1 - a1)); return hump(top + Vector((0, 0, .45)), claude_at, u, .5), Euler((0, 0, .6 * math.sin(math.pi * u))), 1 - clamp((u - .8) / .2)
    return claude_at, Euler((0, 0, 0)), 0
def doc_pose(t):              # 文件：Claude 一脚踢出 → 翻着跟头飞到 Codex 的屏幕上 → 落下被屏幕吸收
    a, b = C1['doc']; p0 = CELLS[TL['DOC_FROM']] + Vector((0, 0, .25)); p1 = Vector(TL['DOC_TO']) + Vector((0, 0, .01))
    if t < a: return p0, Euler((0, 0, 0)), 0
    if t < b:
        u = smooth((t - a) / (b - a)); return hump(p0, p1, u, .8), Euler((math.radians(-90) * u + 2 * math.pi * u, 0, .5 * math.sin(math.pi * u)), 'XYZ'), 1
    u = clamp((t - b) / .25); return p1, Euler((math.radians(-90), 0, 0)), 1 - u
def follow_pos(who, t):
    if who in ('claude', 'codex', 'grok'): return pose_all(who, t)[0] + Vector((0, 0, HC))
    return (jcard_pose if who == 'jcard' else doc_pose)(t)[0] + Vector((0, 0, .2))
def mini_pose(i, t):          # 分身：从 Claude 身上蹦出来 → 跳到各自的小屏 → 按拍子干活 → 跳回来合体
    home = CELLS[TL['DOC_FROM']]; dst = CELLS[f'sub{i}']
    s0 = C1['split'] + i * .12; s1 = C1['subs'][0]; m0, m1 = C1['merge']
    if t < s0: return home, Euler((0, 0, 0)), 0
    if t < s1:
        u = (t - s0) / (s1 - s0); p_, R, _ = arc(home, dst, u, .55, 'x', -1); k = .55 * clamp(u * 4); return p_, R, k
    if t < m0 + i * .08:
        hp_ = 0
        for b in range(8):
            tb = s1 + .2 + b * TL['BEAT'] / 2 + i * .07; u = (t - tb) / .2
            if 0 < u < 1: hp_ = .08 * 4 * u * (1 - u)
        return dst + Vector((0, 0, hp_)), Euler((0, 0, 0)), .55
    u = clamp((t - m0 - i * .08) / (m1 - m0)); p_, R, _ = arc(dst, home, u, .5, 'x', 1)
    return p_, R, .55 * (1 - clamp((u - .75) / .25))

if HAS_CH1:
    mx_, my_ = TL['MAP']['c']
for f in range(max(1, F0 - 2), F1 + 3):
    t = (f - 1) / FPS
    for k, ob in CH.items():
        ob.location, ob.rotation_euler, ob.scale = pose_all(k, t)
        key(ob, f, 'location', 'rotation_euler', 'scale')
    cam.location, tgt.location = campose(t)
    key(cam, f, 'location'); key(tgt, f, 'location')
    if not HAS_CH1: continue
    # 第一章的灯：开场期间关着，第 10 秒起 0.6 秒内亮起
    for L, e0 in CH1_LIGHTS:
        L.data.energy = e0 * smooth((t - O['end']) / .6); L.data.keyframe_insert('energy', frame=f)
    # 资料龙卷风
    a0, a1 = C1['torrent']
    for i, (ob, (p0, th)) in enumerate(zip(DOCS, DOC0)):
        t0 = a0 + (a1 - a0 - 1.4) * i / len(DOCS); u = (t - t0) / 1.4
        if 0 <= u <= 1:
            if u < .2:
                v = u / .2; ob.location = p0 + Vector((0, 0, .25 * smooth(v))); ob.rotation_euler = (math.radians(-90) * (1 - v), 0, th); sc_ = smooth(v * 2)
            else:
                v = (u - .2) / .8; ang = th + 2 * math.pi * v; rad = .9 * (1 - v) ** 1.3 + .04
                ob.location = G + Vector((math.cos(ang) * rad, math.sin(ang) * rad, .25 + .55 * math.sin(math.pi * v) * (1 - v) + .15 * v))
                ob.rotation_euler = (0, .4, ang + math.pi / 2); sc_ = 1 - clamp((v - .8) / .2)
            ob.scale = (sc_, sc_, sc_)
        else:
            ob.location = p0; ob.scale = (0, 0, 0)
        key(ob, f, 'location', 'rotation_euler', 'scale')
    for j, ob in enumerate(JC):   # 判断卡从 Grok 身上吐出来，飞到旁边叠成塔
        tj = a0 + .5 + (a1 - a0 - .5) * j / len(JC); u = (t - tj) / .45
        dst = STACK + Vector((0, 0, j * .012))
        if u < 0: ob.location = G + Vector((0, 0, .15)); ob.scale = (0, 0, 0)
        else:
            v = smooth(clamp(u)); ob.location = hump(G + Vector((0, 0, .2)), dst, v, .35); ob.scale = (1, 1, 1)
            ob.rotation_euler = (0, 0, (1 - v) * 3 + j * .07)
        if t >= C1['kb_card'] and j == len(JC) - 1: ob.scale = (0, 0, 0)    # 最上面那张变成递给 Claude 的判断卡
        key(ob, f, 'location', 'rotation_euler', 'scale')
    JCARD.location, JCARD.rotation_euler, k_ = jcard_pose(t); JCARD.scale = (k_, k_, k_); key(JCARD, f, 'location', 'rotation_euler', 'scale')
    DOCK.location, DOCK.rotation_euler, k_ = doc_pose(t); DOCK.scale = (k_, k_, k_); key(DOCK, f, 'location', 'rotation_euler', 'scale')
    for i, m_ in enumerate(MINIS):
        m_.location, m_.rotation_euler, k_ = mini_pose(i, t); m_.scale = (k_, k_, k_); key(m_, f, 'location', 'rotation_euler', 'scale')
    # Codex：扫描线从上扫到下；封面图显影框从屏幕上立起来
    g0 = C1['gen'][0]; u = (t - g0) / .5
    GEN.location = (*TL['GEN_AT'], SZ1); GEN.rotation_euler = (math.radians(-90) * (1 - back(u)), 0, 0) if u > 0 else (math.radians(-90), 0, 0)
    k_ = clamp(u * 3) * clamp((C1['steps'][4][0] + .5 - t) / .3); GEN.scale = (k_, k_, k_); key(GEN, f, 'location', 'rotation_euler', 'scale')
    # 全息平台：圆环慢慢转；连线按时间亮起，光点沿线流动
    holo.rotation_euler = (0, 0, .25 * t); key(holo, f, 'rotation_euler')
    for pts, em, pulses, t_on, t_off in EDGE_OBJ:
        on = smooth((t - t_on) / .3) * clamp((t_off - t) / .3)
        b = em.node_tree.nodes['Principled BSDF']; b.inputs['Emission Strength'].default_value = 3 * on
        b.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)
        for j, pu in enumerate(pulses):
            if on > .05:
                v = ((t - t_on) / .7 + j / 3) % 1; x_ = v * (len(pts) - 1); i0 = min(int(x_), len(pts) - 2)
                pu.location = pts[i0].lerp(pts[i0 + 1], x_ - i0); pu.scale = (on, on, on)
            else: pu.location = pts[0]; pu.scale = (0, 0, 0)
            key(pu, f, 'location', 'scale')
    # 设备灯：被派到活时变亮闪动；X3D 的灯带彩虹循环；NAS 收文件时琥珀快闪，核对完变绿
    import colorsys
    for name, sm in STRIPS.items():
        b = sm.node_tree.nodes['Principled BSDF']
        busy = any(e[1] == name and t >= e[2] for e in TL['EDGES'])
        es = 3 + (5 + 3 * math.sin(t * 9 + sum(map(ord, name)) % 7)) * busy
        if name == 'x3d': col = colorsys.hsv_to_rgb((t * .35) % 1, .8, 1)
        else: col = (.25, .55, 1)
        b.inputs['Emission Color'].default_value = (*col, 1); b.inputs['Emission Strength'].default_value = es
        b.inputs['Emission Color'].keyframe_insert('default_value', frame=f); b.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)
    nas_in = min(e[2] for e in TL['EDGES'] if e[1] == 'nas')
    for i, lm in enumerate(LEDS):
        b = lm.node_tree.nodes['Principled BSDF']
        if t < nas_in: col, es = (.2, .5, 1), 2
        elif t < C1['archived']: col, es = (1, .6, .1), 7 * (math.floor(t * 12 + i * 1.7) % 2)
        else: col, es = (.2, 1, .35), 9
        b.inputs['Emission Color'].default_value = (*col, 1); b.inputs['Emission Strength'].default_value = es
        b.inputs['Emission Color'].keyframe_insert('default_value', frame=f); b.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)
    for cid, (root, em, base) in CELL_OBJ.items():
        v = 0
        for tl, c, _ in TL['LANDS']:
            if c == cid and 0 <= t - tl < .5: v = max(v, 1 - (t - tl) / .5)
        sq = math.sin(v * math.pi)
        root.scale = (1 + .12 * sq, 1 + .12 * sq, 1 - .3 * sq * (v > .7) + .5 * sq * (v <= .7)); key(root, f, 'scale')
        b = em.node_tree.nodes['Principled BSDF']; b.inputs['Emission Strength'].default_value = base * (1 + 3 * v)
        b.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)
    for k, m_ in SCREENS.items():
        on = smooth((t - TL['OPEN_AT'][k]) / .35) if k in TL['OPEN_AT'] else 1
        b = m_.node_tree.nodes['Principled BSDF']; b.inputs['Emission Strength'].default_value = (.5 if k == 'kb' else 1.1) * (.08 + .92 * on)
        b.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)
    # 传送门光环：Claude 扎进去的地方荡开两圈
    d0, d1 = C1['dive']; c_ = CELLS['chat2:dive'] + Vector((0, 0, .006))
    if t >= TL['CH2']['start']: d0, c_ = TL['CH2']['start'] - .1, Vector(TL['PORTAL2']) + Vector((0, 0, .006))   # 第二章：从这个洞里冒出来
    for i, rg in enumerate(RINGS):
        u = (t - d0 - .12 - i * .12) / .7
        rg.location = c_; k_ = (.3 + 3.5 * smooth(clamp(u))) if 0 < u < 1.2 else 0; rg.scale = (k_, k_, k_ * .3)
        key(rg, f, 'location', 'scale')
        b_ = rg.data.materials[0].node_tree.nodes['Principled BSDF']            # 消失前 0.5 秒淡出，不再一帧就没
        b_.inputs['Emission Strength'].default_value = 10 * (1 - smooth((u - .7) / .5)); b_.inputs['Emission Strength'].keyframe_insert('default_value', frame=f)

    for i, sg in enumerate(STAT_OBJ):
        k_ = pop01((t - TL['CH2']['stats'][i]) / .45); sg.scale = (k_, k_, k_); key(sg, f, 'scale')

# ---------- 渲染设置 ----------
r = sc.render; r.engine = 'CYCLES'
pr = bpy.context.preferences.addons['cycles'].preferences   # Mac 用 Metal；Windows 的 N 卡用 OptiX（3060Ti 实测可用）
for dt in (('METAL',) if sys.platform == 'darwin' else ('OPTIX', 'CUDA')):
    pr.compute_device_type = dt; pr.refresh_devices()
    if any(d.type == dt for d in pr.devices): break
for d in pr.devices: d.use = d.type != 'CPU'
sc.cycles.device = 'GPU'
sc.cycles.samples = 16 if PREVIEW else 64; sc.cycles.adaptive_threshold = .03
sc.cycles.use_denoising = True; sc.cycles.max_bounces = 6
r.resolution_x, r.resolution_y = (TL['W'] // 2, TL['H'] // 2) if PREVIEW else (TL['W'], TL['H'])   # 横版 1920×1080
r.use_motion_blur = True; r.motion_blur_shutter = .5   # 预览也开：看流畅度要看运动模糊
r.use_persistent_data = True
sc.view_settings.view_transform = 'AgX'            # 深色场景用 AgX（亮场景再换 Standard）
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass
ng = bpy.data.node_groups.new('comp', 'CompositorNodeTree')           # 后期：泛光（Blender 5 的合成节点组）
ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
rl = ng.nodes.new('CompositorNodeRLayers'); gl = ng.nodes.new('CompositorNodeGlare'); go = ng.nodes.new('NodeGroupOutput')
gl.inputs['Type'].default_value = 'Bloom'; gl.inputs['Threshold'].default_value = 2.0   # 白色的 Codex 不能被泛光吃掉，只让真正发光的东西起光晕
gl.inputs['Strength'].default_value = .45; gl.inputs['Size'].default_value = .55
ng.links.new(rl.outputs['Image'], gl.inputs['Image']); ng.links.new(gl.outputs['Image'], go.inputs[0])
sc.compositing_node_group = ng
r.image_settings.file_format = 'PNG'; r.filepath = os.path.join(OUT, '####')
r.use_overwrite = False; r.use_placeholder = True     # 分段、断点续渲：已有的帧跳过
sc.frame_start, sc.frame_end = F0, F1
if '--cam' in argv:            # 出封面用：固定机位 + 自定分辨率，关掉运动模糊。--cam x,y,z,tx,ty,tz --res W,H [--lens mm]
    v = [float(x) for x in argv[argv.index('--cam') + 1].split(',')]
    cam.animation_data_clear(); tgt.animation_data_clear(); cam.location = v[:3]; tgt.location = v[3:]
    r.resolution_x, r.resolution_y = [int(x) for x in argv[argv.index('--res') + 1].split(',')]
    if '--lens' in argv: cam.data.lens = float(argv[argv.index('--lens') + 1])
    r.use_motion_blur = False; sc.cycles.samples = 256; cam.data.dof.aperture_fstop = 2.0
if '--step' in argv: sc.frame_step = int(argv[argv.index('--step') + 1])
if '--save' in argv:          # 只导出渲染工程（.blend），不渲染
    bpy.ops.wm.save_as_mainfile(filepath=argv[argv.index('--save') + 1]); sys.exit(0)
if FRAMES:                    # 只渲关键帧
    for f in FRAMES:
        sc.frame_set(f); r.filepath = os.path.join(OUT, f'{f:04d}.png'); bpy.ops.render.render(write_still=True)
    print('RENDERED', FRAMES); sys.exit(0)
bpy.ops.render.render(animation=True)
print('RENDERED', F0, F1)
