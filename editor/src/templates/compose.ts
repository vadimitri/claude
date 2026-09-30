// Gemeinsamer Satz: Layout (Displaypixel, wie styles.layout / kickoff.layout) -> Scene fuer den Renderer.
import type { Scene } from '../render/types';
import data from '../data.json';
import { labelGlyphs, lineMask, qrMatrix, type Grid } from './type';
import type { Spec } from '../spec';
import { sparkDefault } from '../render/renderer';

export const FMTS: Record<string, [number, number, number]> = {
  a3: [3504, 4956, 3], '9x16': [1080, 1920, 1], '16x9': [1920, 1080, 1], '1x1': [1080, 1080, 1], '4x5': [1080, 1350, 1],
};
export const R = 4;
const F_LO = data.f_lo, F_HI = data.f_hi;

export type Ctx = Grid & { W: number; H: number; short: number; port: boolean; snap: (v: number) => number; spec: Spec };

export type Block = {
  name: string;
  lines: string[];
  bases: number[];
  cap: number;
  x: number;
  font: 'clash' | 'departure';
  flip: 0 | 1 | 2;
  fill?: boolean;           // Glutverlauf (Titel/Datum), sonst fester Wert v
  v?: number;
  right?: boolean;
  box?: { centerOn: [number, number] }; // CTA: Etikett in lvl(0), mittig ueber [x, Breite] in Displaypixeln
  title?: boolean;
};

export type Layout = {
  blocks: Block[];
  qr: { left: number; bottom: number } | null;  // Displaypixel: linke Kante, Unterkante der Platte
  starY?: number;                               // Ersatz fuer K-Presets mit y = None (Displaypixel)
};

export type Built = { scene: Scene; star: [number, number, number, number]; boxes: Record<string, [number, number, number, number]>; L: Layout };


export function ctxOf(spec: Spec): Ctx {
  const [W0, H0, u] = FMTS[spec.fmt] ?? FMTS['9x16'];
  const px = R * u;
  const gw = Math.floor(W0 / px), gh = Math.floor(H0 / px);
  const W = gw * px, H = gh * px;
  return { W, H, px, gw, gh, short: Math.min(W, H), port: H > W, snap: (v) => Math.round(v / px) * px, spec };
}

/** Stern in Bruchteilen (x/W, y/H, R/kurze Seite, rot). Reihenfolge: freie Platzierung -> own_k -> sparkDefault -> K-Preset.
 *  own_k und sparkDefault nur fuer OWN-Sterne (wie kickoff.spark), sonst waeren die K-Presets tot. titleBox in m. */
export function starFrac(c: Ctx, L: Layout, titleBox: [number, number, number, number]): [number, number, number, number] {
  const s = c.spec;
  if (s.star) return [s.star.x, s.star.y, s.star.R, s.star.rot];
  const own = (data.own as string[]).includes(s.spark);
  const ok = (data.own_k as Record<string, number[]>)[s.spark];
  if (own && ok) return [ok[0], ok[1], ok[2], s.rot];
  const gd = own ? sparkDefault(s.spark, [c.W / c.short, c.H / c.short], titleBox) : null;
  if (gd) return [(gd[0] * c.short) / c.W, (gd[1] * c.short) / c.H, gd[2], gd[3]];
  const k = (data.komp as Record<string, { port: (number | null)[]; land: (number | null)[] }>)[(data.K as Record<string, string>)[s.K ?? 'K1'] ?? 'riese'];
  const [fx, fy, fr] = k[c.port ? 'port' : 'land'];
  return [fx as number, fy == null ? (L.starY ?? 0.4 * c.H) / c.H : fy, fr as number, s.rot];
}

export function compose(c: Ctx, L: Layout): Built {
  const { gw, gh, px, W, H, short } = c;
  const N = gw * gh;
  const pal = (data.pals as Record<string, string[]>)[c.spec.pal] ?? data.pals.lav;
  const altName = (data.alt2 as Record<string, string>)[c.spec.pal];
  const titleMask = new Uint8Array(N), textMask = new Uint8Array(N);
  const typeV = new Float32Array(N).fill(NaN), typeFlip = new Uint8Array(N), glyphId = new Uint16Array(N);
  const boxes: Record<string, [number, number, number, number]> = {};
  let gid = 1;
  const bbox = (mk: Uint8Array) => {
    let x0 = gw, y0 = gh, x1 = -1, y1 = -1;
    for (let i = 0; i < N; i++) if (mk[i]) {
      const x = i % gw, y = (i / gw) | 0;
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
    return x1 < 0 ? null : ([x0, y0, x1 + 1, y1 + 1] as [number, number, number, number]);
  };

  for (const b of L.blocks) {
    let mk = new Uint8Array(N);
    b.lines.forEach((s, i) => lineMask(mk, c, s, b.font, b.cap, b.bases[i], b.x, b.right));
    let bb = bbox(mk);
    if (!bb) continue;
    if (b.box) {                                        // kickoff CTA: mittig ueber der QR-Platte, harter Streifen
      const [bx, bw] = b.box.centerOn;
      const shift = Math.round(bx / px) + Math.floor((bw / px - (bb[2] - bb[0])) / 2) - bb[0];
      const m2 = new Uint8Array(N);
      for (let i = 0; i < N; i++) if (mk[i]) { const x = (i % gw) + shift; if (x >= 0 && x < gw) m2[i - (i % gw) + x] = 1; }
      mk = m2;
      bb = bbox(mk)!;
      const pad = Math.max(2, Math.round((0.25 * b.cap) / px));
      for (let y = Math.max(0, bb[1] - pad); y < Math.min(gh, bb[3] + pad); y++)
        for (let x = Math.max(0, bb[0] - pad); x < Math.min(gw, bb[2] + pad); x++) {
          const i = y * gw + x;
          typeV[i] = 0; typeFlip[i] = 0; glyphId[i] = 0; textMask[i] = 1;
        }
    }
    boxes[b.name] = boxes[b.name] ? union(boxes[b.name], bb) : bb;
    const fillRow = new Float32Array(gh).fill(NaN);
    if (b.fill) for (let y = 0; y < gh; y++) {
      const cy = (y + 0.5) * px;
      for (const base of b.bases) if (cy <= base + 0.1 * b.cap && cy > base - 1.4 * b.cap)
        fillRow[y] = Math.min(1, Math.max(0, (cy - (base - b.cap)) / b.cap));
    }
    if (b.flip === 2) gid = labelGlyphs(mk, c, glyphId, gid);
    for (let i = 0; i < N; i++) {
      if (!mk[i]) continue;
      const rel = fillRow[(i / gw) | 0];
      typeV[i] = b.fill ? F_LO + (F_HI - F_LO) * (1 - (Number.isNaN(rel) ? 0 : rel)) : (b.v ?? 1);
      typeFlip[i] = b.flip;
      if (b.flip !== 2) glyphId[i] = 0;
      textMask[i] = 1;
      if (b.title) titleMask[i] = 1;
    }
  }

  let qr: Scene['qr'] = null;
  if (L.qr && c.spec.qr) {
    const q = qrMatrix(c.spec.qr);
    const n = (q.size + 6) * 2;
    const top = Math.round((L.qr.bottom - n * px) / px), left = Math.round(L.qr.left / px);
    qr = { x: left, y: top, n, modules: q.modules };
    boxes.qr = [left, top, left + n, top + n];
  }

  const tb = boxes.title ?? [0, 0, 1, 1];
  const toM = (v: number) => (v * px) / short;
  const titleBox: [number, number, number, number] = [toM(tb[0]), toM(tb[1]), toM(tb[2]), toM(tb[3])];
  const sf = starFrac(c, L, titleBox);
  const scene: Scene = {
    gw, gh, W, H, cellPx: px, pal, alt: altName ? (data.pals as Record<string, string[]>)[altName] : undefined,
    spark: c.spec.spark, star: [(sf[0] * W) / short, (sf[1] * H) / short, sf[2], sf[3]], seed: c.spec.seed,
    titleMask, textMask, titleBox,
    typeV, typeFlip, glyphId, qr, glow: true,
  };
  return { scene, star: sf, boxes, L };
}

function union(a: [number, number, number, number], b: [number, number, number, number]): [number, number, number, number] {
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
}

/** Stufe fuer kleine Schrift: zweithellste, bei 1-/2-Bit die hellste (Ctx.ink). */
export function ink(c: Ctx): number {
  const n = ((data.pals as Record<string, string[]>)[c.spec.pal] ?? data.pals.lav).length - 1;
  return (n > 2 ? n - 1 : n) / n;
}
export const codename = (p: string) => (data.codename as Record<string, string>)[p] ?? p.toUpperCase();
export const qrSize = (url: string) => (url ? qrMatrix(url).size : 0);
