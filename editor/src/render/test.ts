// Paritaets-Harness: test.html?spark=S7&pal=lav&fmt=16x9|9x16|a3&x=&y=&R=&rot=&seed=&glow=0&tb=x0,y0,x1,y1
// Rendert einen Spark ohne Schrift/QR im richtigen Raster, Stern per Default wie KOMP riese.
import { Renderer, sparkDefault, sparkCodes } from './renderer';
import type { Scene } from './types';
import data from '../data.json';

const q = new URLSearchParams(location.search);
const fmt = (q.get('fmt') ?? '16x9') as keyof typeof data.sizes;
const [W, H, u] = data.sizes[fmt];
const cellPx = 4 * u;
const gw = Math.floor(W / cellPx), gh = Math.floor(H / cellPx), m = Math.min(W, H);
const pals = data.pals as Record<string, string[]>;
const palName = q.get('pal') ?? 'lav';
const altName = (data.alt2 as Record<string, string>)[palName];
const port = H > W;

const canvas = document.getElementById('c') as HTMLCanvasElement;
const errEl = document.getElementById('err')!;
let r: Renderer;
try { r = new Renderer(canvas); } catch (e) { errEl.textContent = String(e); throw e; }
const code = q.get('spark') ?? r.sparkCodes()[0] ?? 'S2';

// Titel-Bbox (m) fuer Tx/Ty-Defaults: &tb=x0,y0,x1,y1, sonst leer (Titelmitte = Seitenmitte)
const tb = q.get('tb')?.split(',').map(Number);
const titleBox = tb?.length === 4 ? (tb as [number, number, number, number]) : undefined;
// Platzierung: URL > own_k / Datei-Default (nur OWN) > KOMP riese
const riese = data.komp.riese[port ? 'port' : 'land'] as [number, number | null, number];
let star: [number, number, number, number] = [riese[0] * W / m, (riese[1] ?? 0.4) * H / m, riese[2], 14];
if ((data.own as string[]).includes(code)) {
  const ok = (data.own_k as Record<string, number[]>)[code];
  const d = sparkDefault(code, [W / m, H / m], titleBox);
  if (ok) star = [ok[0] * W / m, ok[1] * H / m, ok[2], d?.[3] ?? 14];
  else if (d) star = d;
}
(['x', 'y', 'R', 'rot'] as const).forEach((k, i) => { if (q.has(k)) star[i] = +q.get(k)!; });

const n = gw * gh;
const scene: Scene = {
  gw, gh, W, H, cellPx, pal: pals[palName], alt: altName ? pals[altName] : undefined, spark: code, star,
  seed: +(q.get('seed') ?? 0), titleMask: new Uint8Array(n), textMask: new Uint8Array(n), titleBox: titleBox ?? [0, 0, 0, 0],
  typeV: new Float32Array(n).fill(NaN), typeFlip: new Uint8Array(n), glyphId: new Uint16Array(n), qr: null,
  glow: q.get('glow') !== '0',
};

r.render(scene);
// Frame-Zeit: 20 Frames, Sync ueber 1-Pixel-readPixels
const px = new Uint8Array(4), gl = r.gl;
const t0 = performance.now();
for (let i = 0; i < 20; i++) { r.render(scene); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); }
const ms = (performance.now() - t0) / 20;
(window as any).__frameMs = ms;
(window as any).__renderer = r;
(window as any).__scene = scene;

const have = r.sparkCodes();
document.getElementById('info')!.textContent =
  `${code}${have.includes(code) ? '' : ' (FEHLT -> Fallback S2)'} · ${palName} · ${fmt} ${gw}x${gh} · star ${star.map((v) => +v.toFixed(3)).join(' ')} · ${ms.toFixed(2)} ms/frame`;
const base = (s: string) => { const p = new URLSearchParams(q); p.set('spark', s); ['x', 'y', 'R', 'rot'].forEach((k) => p.delete(k)); return `?${p}`; };
document.getElementById('links')!.innerHTML =
  sparkCodes().map((c) => `<a href="${base(c)}" style="${have.includes(c) ? '' : 'color:#f66'}">${c}</a>`).join(' ') +
  '<br><br>' + ['16x9', '9x16', 'a3'].map((f) => { const p = new URLSearchParams(q); p.set('fmt', f); return `<a href="?${p}">${f}</a>`; }).join(' ') +
  '<br>' + Object.keys(pals).map((p) => { const s = new URLSearchParams(q); s.set('pal', p); return `<a href="?${s}">${p}</a>`; }).join(' ');
errEl.textContent = r.errors.map((e) => `== ${e.code}\n${e.log}`).join('\n');
