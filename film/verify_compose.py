"""正式渲染验收 + 合成：先逐帧核对（序号连续、能完整解码、尺寸对、不是粉屏），全部通过才合成视频。
用法：python verify_compose.py <渲染目录> <字幕层目录> <配乐 wav> <起始帧> <结束帧> <输出 mp4>"""
import os, sys, subprocess
import numpy as np
from PIL import Image

R, OV, WAV, F0, F1, OUT = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
miss, bad, pink, ovmiss = [], [], [], []
for f in range(F0, F1 + 1):
    p = f'{R}/{f:04d}.png'
    if not os.path.exists(p): miss.append(f); continue
    try:
        im = Image.open(p); im.load()                      # 完整解码，截断的 PNG 会在这里报错
        if im.size != (1920, 1080): bad.append((f, im.size)); continue
        a = np.asarray(im.convert('RGB').resize((192, 108))).astype(int)
        if ((a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 120)).mean() > .02: pink.append(f)
    except Exception as e:
        bad.append((f, str(e)[:60]))
    if not os.path.exists(f'{OV}/{f:04d}.png'): ovmiss.append(f)

def ranges(xs):
    out, s = [], None
    for i, x in enumerate(xs):
        if s is None: s = x
        if i == len(xs) - 1 or xs[i + 1] != x + 1: out.append(f'{s}-{x}' if s != x else f'{s}'); s = None
    return out
n = F1 - F0 + 1
print(f'应有 {n} 帧（{F0}-{F1}）')
print('缺帧', len(miss), ranges(miss)); print('损坏/尺寸不对', len(bad), bad[:10])
print('粉屏', len(pink), ranges(pink)); print('字幕层缺', len(ovmiss), ranges(ovmiss))
if miss or bad or pink or ovmiss:
    print('不合成：先补齐上面的帧'); sys.exit(1)

# 合成：3D 帧 + 字幕层 + 配乐（从起始帧对应的秒数截）
t0 = (F0 - 1) / 30
cmd = ['ffmpeg', '-v', 'error', '-y', '-framerate', '30', '-start_number', str(F0), '-i', f'{R}/%04d.png',
       '-framerate', '30', '-start_number', str(F0), '-i', f'{OV}/%04d.png', '-ss', f'{t0:.4f}', '-i', WAV,
       '-filter_complex', '[0][1]overlay=format=auto,format=yuv420p[v]', '-map', '[v]', '-map', '2:a',
       '-frames:v', str(n), '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-c:a', 'aac', '-b:a', '256k',
       '-movflags', '+faststart', '-shortest', OUT]
subprocess.run(cmd, check=True)
probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                        'stream=nb_read_frames,width,height', '-of', 'csv=p=0', OUT], capture_output=True, text=True).stdout.strip()
print('合成完成', OUT, '（宽,高,帧数）', probe)
