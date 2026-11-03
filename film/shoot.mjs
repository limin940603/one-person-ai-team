// 把界面网页逐帧截成 PNG 序列（文件名 = 全片帧号，t = (帧号-1)/30）：
//   node films/aistudio/shoot.mjs <页面> <输出目录> [帧]
//   页面：chat / overlay / 第一章屏幕（mac、pane_claude、queue、kb、term、chat2、ex0…，见 ui/screens.html）
//   帧：  "1-300"（默认 = 小样 300 帧）或 "282,350,421"（只截关键帧）
// chat 和屏幕页 → 不透明（贴到 3D 屏幕）；overlay → 透明 1080×1920（最后叠在画面上）。
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { EXE, ARGS } from '../../core/render/browser.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const [name, outDir, spec] = process.argv.slice(2);
const TL = JSON.parse(fs.readFileSync(path.join(HERE, 'timeline.json'), 'utf8'));
const frames = !spec ? [...Array(TL.SAMPLE_FRAMES).keys()].map(i => i + 1)
  : spec.includes('-') ? (([a, b]) => [...Array(b - a + 1).keys()].map(i => i + a))(spec.split('-').map(Number))
  : spec.split(',').map(Number);
const solo = { chat: [1600, 1000], overlay: [TL.W, TL.H] };   // 横版
const st = Object.values(TL.ST).find(s => s.page === name) ? { px: TL.PX } : Object.values(TL.SUBT).find(s => s.page === name);
const PROPS = { kbcard: [900, 1200], gen: [900, 1200], queue: [1200, 1640] };   // 不是工位、但要贴图的道具
const [w, h] = solo[name] || (st ? st.px : PROPS[name]) || [];
if (!w) throw new Error('未知页面：' + name);
const url = 'file://' + path.join(HERE, 'ui', solo[name] ? name + '.html' : 'screens.html') + (solo[name] ? '' : '?s=' + name);
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ executablePath: EXE, args: ARGS });
const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
await page.goto(url);
// 代码屏要显示真实源文件：截图时把它们读进页面
const skipHead = (f, txt) => {   // 跳过文件开头的说明（Python 的文档字符串、HTML 的头两行注释），从真正的代码开始显示
  if (f.endsWith('.py')) { const m = txt.match(/^[\s\S]*?"""[\s\S]*?"""\s*\n/); return m ? txt.slice(m[0].length) : txt; }
  return txt.split('\n').slice(4).join('\n');
};
const SRC = Object.fromEntries(['timeline.py', 'scene.py', 'score.py', 'ui/screens.html'].map(f => [path.basename(f), skipHead(f, fs.readFileSync(path.join(HERE, f), 'utf8'))]));
await page.evaluate(([tl, src]) => { window.TL = tl; window.SRC = src; }, [TL, SRC]);
await page.evaluate(() => document.fonts.ready);
await page.evaluate(() => Promise.all([...document.images].map(i => i.complete || new Promise(r => { i.onload = i.onerror = r; }))));
for (const f of frames) {
  await page.evaluate(t => window.renderAt(t), (f - 1) / TL.FPS);
  await page.evaluate(() => Promise.all([...document.images].map(i => i.complete || new Promise(r => { i.onload = i.onerror = r; }))));
  await page.screenshot({ path: path.join(outDir, `${String(f).padStart(4, '0')}.png`), omitBackground: name === 'overlay' });
}
await browser.close();
console.log(name, 'done', frames.length);
