"""第一章关键帧：每个镜头挑一个最能说明问题的时刻，渲出来拼成一张图给导演确认分镜。
  python ch1_keys.py frames            → 打印帧号（逗号分隔），给 shoot.mjs / scene.py --frames 用
  python ch1_keys.py sheet <渲染目录> <字幕层目录> <输出.jpg>   → 叠字幕、标镜头号、拼图"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, 'timeline.json'), encoding='utf-8'))
FPS = TL['FPS']

KEYS = [  # (时刻, 镜头号, 一句话)
    (0.0, '1', '第 0 帧：钩子'), (1.6, '1', '贴纸揭起、转身'), (2.75, '2', '跳出屏幕，波纹'), (6.2, '4', '标题 + 三个角色'),
    (9.6, '5', '第一章卡'),
    (10.75, '6', '一格一格跳向 Mac'), (11.4, '7', '跳上图标，Mac 打开'), (12.6, '7', '打字'), (15.5, '8', '踩一格弹一件事'),
    (17.15, '9', '挂负责人，各自踩上自己的格子'), (18.55, '9', '跟拍 Grok 跳踏板'), (19.35, '10', 'Grok 跳上图标，知识书房打开'),
    (21.9, '11', '资料龙卷风'), (23.4, '11', '判断卡塔 + 7,253 张'), (25.8, '12', '跟拍判断卡飞给 Claude'),
    (27.2, '13', 'Claude 踩文件标签，打开真实源码'), (28.6, '13', '踩到最后一个标签'), (30.0, '14', '分身跳上三块小屏'),
    (32.2, '15', '一脚踢出文件'), (34.9, '16', 'Codex 一格一格审'), (37.6, '17', '盖章「通过」'), (39.0, '18', '封面显影'),
    (42.6, '19', '升镜：全息平台'), (44.0, '20', 'Claude 踩机器，连线亮'), (45.4, '20', 'Grok 踩迷你主机'),
    (47.9, '21', 'Codex 跳上 NAS，灯变绿'), (49.6, '22', '回到群聊'), (50.3, '22', '扎进屏幕'),
]
frames = [int(round(t * FPS)) + 1 for t, _, _ in KEYS]

if sys.argv[1] == 'frames':
    print(','.join(map(str, frames)))
elif sys.argv[1] == 'sheet':
    from PIL import Image, ImageDraw, ImageFont
    rd, od, out = sys.argv[2:5]
    font = ImageFont.truetype(os.path.join(HERE, '..', 'opus60', 'fonts', 'NotoSansSC.ttf'), 20)
    W, H, COLS = 480, 270, 4
    rows = (len(KEYS) + COLS - 1) // COLS
    sheet = Image.new('RGB', (COLS * W, rows * (H + 56)), (18, 18, 22))
    for i, ((t, shot, note), f) in enumerate(zip(KEYS, frames)):
        im = Image.open(os.path.join(rd, f'{f:04d}.png')).convert('RGBA').resize((TL['W'], TL['H']))
        ov = Image.open(os.path.join(od, f'{f:04d}.png')).convert('RGBA')
        im = Image.alpha_composite(im, ov).convert('RGB').resize((W, H), Image.LANCZOS)
        x, y = (i % COLS) * W, (i // COLS) * (H + 56)
        sheet.paste(im, (x, y))
        d = ImageDraw.Draw(sheet)
        d.text((x + 10, y + H + 4), f'镜头 {shot} · {t:.1f}s', font=font, fill=(255, 138, 101))
        d.text((x + 10, y + H + 28), note, font=font, fill=(220, 220, 228))
    sheet.save(out, quality=88)
    print(out)
