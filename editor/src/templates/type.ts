// Schrift auf dem Zellraster: Canvas2D rastert die Fonts aus public/fonts, Schwelle 127 wie styles.line_mask.
import QRCode from 'qrcode';

export type Grid = { gw: number; gh: number; px: number };
export type Font = 'clash' | 'departure';

let ready: Promise<void> | null = null;
export let fontsLoaded = false;   // vorher nichts cachen (Fallback-Font wuerde haengen bleiben)
export function loadFonts(): Promise<void> {
  ready ??= (async () => {
    const faces = [
      new FontFace('SparkClash', 'url(/fonts/ClashDisplay-Variable.ttf)', { weight: '200 700' }),
      new FontFace('SparkDeparture', 'url(/fonts/DepartureMono-Regular.otf)'),
    ];
    for (const f of faces) document.fonts.add(await f.load());
    fontsLoaded = true;
  })();
  return ready;
}

const cv = document.createElement('canvas');
const cx = cv.getContext('2d', { willReadFrequently: true })!;
const fontCss = (T: Font, size: number) => (T === 'clash' ? `700 ${size}px SparkClash` : `${size}px SparkDeparture`);

let capH100 = 0;
function clashCap100(): number {  // Versalhoehe von "H" bei 100 px
  if (capH100) return capH100;
  cx.font = fontCss('clash', 100);
  const h = cx.measureText('H').actualBoundingBoxAscent;
  if (fontsLoaded) capH100 = h;
  return h;
}

const prep = (s: string, T: Font) => (T === 'clash' ? s.replace(/ /g, '  ') : s);  // Clash-Wortabstand wie Python

/** styles.width_per_cap: Zeilenbreite in Versalhoehen. */
export function widthPerCap(s: string): number {
  cx.font = fontCss('clash', 200);
  const m = cx.measureText(prep(s, 'clash'));
  return (m.actualBoundingBoxRight + m.actualBoundingBoxLeft) / (2 * clashCap100());
}

type Raster = { w: number; h: number; base: number; left: number; a: Uint8Array };
const cache = new Map<string, Raster>();

/** Zeile rastern: Bool-Maske in Font-Pixeln, base = Zeile der Grundlinie, left = erste Tintenspalte. */
function raster(s: string, T: Font, size: number): Raster {
  const key = `${T}|${size}|${s}`;
  const hit = cache.get(key);
  if (hit) return hit;
  cx.font = fontCss(T, size);
  const m = cx.measureText(s);
  const pad = 4;
  const w = Math.ceil(m.actualBoundingBoxLeft + m.actualBoundingBoxRight) + 2 * pad;
  const asc = Math.ceil(Math.max(m.actualBoundingBoxAscent, size)) + pad;
  const h = asc + Math.ceil(Math.max(m.actualBoundingBoxDescent, 0.4 * size)) + pad;
  cv.width = Math.max(1, w);
  cv.height = Math.max(1, h);
  cx.clearRect(0, 0, cv.width, cv.height);
  cx.font = fontCss(T, size);
  cx.textBaseline = 'alphabetic';
  cx.fillStyle = '#fff';
  cx.fillText(s, pad + Math.round(m.actualBoundingBoxLeft), asc);
  const d = cx.getImageData(0, 0, cv.width, cv.height).data;
  const a = new Uint8Array(cv.width * cv.height);
  let left = cv.width;
  for (let i = 0; i < a.length; i++) {
    if (d[i * 4 + 3] > 127) {
      a[i] = 1;
      left = Math.min(left, i % cv.width);
    }
  }
  let right = -1;
  for (let i = 0; i < a.length; i++) if (a[i]) right = Math.max(right, i % cv.width);
  const r: Raster = { w: cv.width, h: cv.height, base: asc, left: right < 0 ? 0 : left, a };
  (r as Raster & { right: number }).right = right;
  if (fontsLoaded) cache.set(key, r);
  if (cache.size > 400) cache.delete(cache.keys().next().value!);
  return r;
}

/** styles.line_mask: Tinte beginnt bei x (right: endet bei x), Grundlinie bei base, alles in Displaypixeln. */
export function lineMask(out: Uint8Array, g: Grid, s: string, T: Font, capPx: number, base: number, x: number, right = false) {
  if (!s) return;
  const cap = capPx / g.px;
  let k = 1, size: number;
  if (T === 'departure') {
    k = Math.max(1, Math.round(cap / 8));
    size = 11;
  } else size = Math.max(6, Math.round((100 * cap) / clashCap100()));
  const r = raster(prep(s, T), T, size) as Raster & { right: number };
  if (r.right < 0) return;
  const inkW = (r.right - r.left + 1) * k;
  const X = Math.round(x / g.px), B = Math.round(base / g.px);
  const x0 = right ? X - inkW : X;
  for (let yy = 0; yy < r.h; yy++)
    for (let xx = r.left; xx <= r.right; xx++) {
      if (!r.a[yy * r.w + xx]) continue;
      for (let dy = 0; dy < k; dy++) {
        const Y = B + (yy - r.base) * k + dy;
        if (Y < 0 || Y >= g.gh) continue;
        for (let dx = 0; dx < k; dx++) {
          const C = x0 + (xx - r.left) * k + dx;
          if (C >= 0 && C < g.gw) out[Y * g.gw + C] = 1;
        }
      }
    }
}

/** 4er-Nachbarschaft wie scipy.ndimage.label; schreibt Glyphen-Nummern ab start in ids, gibt naechste Nummer zurueck. */
export function labelGlyphs(mask: Uint8Array, g: Grid, ids: Uint16Array, start: number): number {
  let n = start;
  const stack: number[] = [];
  for (let i = 0; i < mask.length; i++) {
    if (!mask[i] || ids[i]) continue;
    ids[i] = n;
    stack.push(i);
    while (stack.length) {
      const j = stack.pop()!;
      const x = j % g.gw;
      for (const q of [j - g.gw, j + g.gw, x > 0 ? j - 1 : -1, x < g.gw - 1 ? j + 1 : -1])
        if (q >= 0 && q < mask.length && mask[q] && !ids[q]) {
          ids[q] = n;
          stack.push(q);
        }
    }
    n = Math.min(n + 1, 65535);
  }
  return n;
}

/** styles.qr_matrix: Byte-Modus, Fehlerkorrektur M, ohne Rand. */
export function qrMatrix(url: string): { size: number; modules: Uint8Array } {
  const q = QRCode.create([{ data: new TextEncoder().encode(url || ' '), mode: 'byte' }], { errorCorrectionLevel: 'M' });
  return { size: q.modules.size, modules: Uint8Array.from(q.modules.data as ArrayLike<number>) };
}
