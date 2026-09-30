// Generisch: freie Titelzeilen, Datum, Ort, CTA ueber dem QR, jede Palette
import data from '../data.json';
import type { Spec } from '../spec';
import { codename, compose, ctxOf, ink, qrSize, type Built, type Layout } from './compose';
import { widthPerCap } from './type';

export const name = 'Event';
export const pals = Object.keys(data.pals);
export const copy = { title: 'SOLDER\nSESSION', date: '05.11. / 18:00', place: 'HPI · MAKERSPACE', cta: 'JOIN US', org: 'SPARK' };

export function build(spec: Spec): Built {
  const c = ctxOf(spec);
  const { W, H, px, short, snap, port } = c;
  const t = { ...copy, ...spec.copy };
  const m = snap(0.07 * short), sc = 0.026 * short, meta = m + snap(sc);
  const title = t.title.split('\n').filter(Boolean);
  const measure = port ? W - 2 * m : 0.6 * W;
  const cap = Math.min(0.3 * H, Math.floor(measure / px / Math.max(0.1, ...title.map(widthPerCap))) * px);
  const tb = title.map((_, i) => meta + snap(0.4 * cap) + cap + i * snap(1.14 * cap));
  const capd = snap(Math.max(0.34 * cap, 0.05 * short));
  const sub = [t.date, t.place].filter(Boolean);
  const sb = sub.map((_, i) => tb[tb.length - 1] + snap(0.42 * cap) + capd + i * snap(1.3 * capd));
  const qs = (qrSize(spec.qr) + 6) * 2 * px, qbot = H - m;
  const capj = snap(0.62 * capd), jb = qbot - qs - snap(0.45 * capj);
  const L: Layout = {
    blocks: [
      { name: 'title', title: true, lines: title, bases: tb, cap: Math.floor(cap / px) * px, x: m, font: 'clash', flip: 1, fill: true },
      { name: 'date', lines: sub, bases: sb, cap: capd, x: m, font: 'clash', flip: 2, fill: true },
      ...(t.cta && spec.qr ? [{ name: 'cta', lines: [t.cta], bases: [jb], cap: capj, x: m, font: 'clash' as const, flip: 0 as const, fill: true, box: { centerOn: [m, qs] as [number, number] } }] : []),
      { name: 'meta', lines: [t.org], bases: [meta], cap: sc, x: m, font: 'departure', flip: 2, v: ink(c) },
      { name: 'meta', lines: [codename(spec.pal)], bases: [meta], cap: sc, x: W - m, font: 'departure', flip: 2, v: ink(c), right: true },
    ],
    qr: { left: m, bottom: qbot },
    starY: (tb[0] + tb[tb.length - 1]) / 2 - cap / 2,
  };
  return compose(c, L);
}
