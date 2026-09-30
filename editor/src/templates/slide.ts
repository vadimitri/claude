// 16:9-Titelfolie: Meta oben, grosser Titel unten links, Untertitel, optional QR unten rechts
import data from '../data.json';
import type { Spec } from '../spec';
import { codename, compose, ctxOf, ink, qrSize, type Built, type Layout } from './compose';
import { widthPerCap } from './type';

export const name = 'Folie';
export const pals = Object.keys(data.pals);
export const copy = { title: 'MAKER NIGHT', sub: '20–21 NOV · HPI', org: 'SPARK' };

export function build(spec: Spec): Built {
  const c = ctxOf(spec);
  const { W, H, px, short, snap, port } = c;
  const t = { ...copy, ...spec.copy };
  const m = snap(0.07 * short), sc = 0.026 * short, meta = m + snap(sc);
  const title = t.title.split('\n').filter(Boolean);
  const qs = spec.qr && !port ? (qrSize(spec.qr) + 6) * 2 * px : 0;   // QR nur quer (hoch kollidiert er mit dem Titel)
  const measure = port ? W - 2 * m : Math.min(0.62 * W, W - 3 * m - qs);
  const cap = Math.min(0.24 * H, Math.floor(measure / px / Math.max(0.1, ...title.map(widthPerCap))) * px);
  const capd = snap(0.32 * cap);
  const bottom = H - m - (t.sub ? snap(0.5 * cap) + capd : 0);
  const tb = title.map((_, i) => bottom - (title.length - 1 - i) * snap(1.14 * cap));
  const L: Layout = {
    blocks: [
      { name: 'title', title: true, lines: title, bases: tb, cap: Math.floor(cap / px) * px, x: m, font: 'clash', flip: 1, fill: true },
      { name: 'date', lines: [t.sub], bases: [H - m], cap: capd, x: m, font: 'clash', flip: 2, fill: true },
      { name: 'meta', lines: [t.org], bases: [meta], cap: sc, x: m, font: 'departure', flip: 2, v: ink(c) },
      { name: 'meta', lines: [codename(spec.pal)], bases: [meta], cap: sc, x: W - m, font: 'departure', flip: 2, v: ink(c), right: true },
    ],
    qr: qs ? { left: W - m - qs, bottom: H - m } : null,
    starY: (tb[0] + tb[tb.length - 1]) / 2 - cap / 2,
  };
  return compose(c, L);
}
