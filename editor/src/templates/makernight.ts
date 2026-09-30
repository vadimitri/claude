// styles.layout / styles.type_layers: MAKER / NIGHT (hoch zweizeilig, quer einzeilig), Datum, SPARK + Codename, QR
import data from '../data.json';
import type { Spec } from '../spec';
import { codename, compose, ctxOf, ink, type Built, type Layout } from './compose';
import { widthPerCap } from './type';

export const name = 'Maker Night';
export const pals = Object.keys(data.pals);
export const copy = { title: 'MAKER\nNIGHT', date: '20–21 NOV', org: 'SPARK' };

export function build(spec: Spec): Built {
  const c = ctxOf(spec);
  const { W, H, px, short, snap, port } = c;
  const t = { ...copy, ...spec.copy };
  const m = snap(0.07 * short), sc = 0.026 * short, meta = m + snap(sc);
  const lines = t.title.split('\n').filter(Boolean);
  const title = port ? lines : [lines.join(' ')];
  const measure = port ? W - 2 * m : 0.6 * W;
  const cap = Math.floor(measure / px / Math.max(0.1, ...title.map(widthPerCap))) * px;
  const tb = title.map((_, i) => meta + snap(0.4 * cap) + cap + i * snap(1.14 * cap));
  const capd = snap((port ? 0.46 : 0.5) * cap);
  const db = tb[tb.length - 1] + snap(0.42 * cap) + capd;
  const L: Layout = {
    blocks: [
      { name: 'title', title: true, lines: title, bases: tb, cap, x: m, font: 'clash', flip: 1, fill: true },
      { name: 'date', lines: [t.date], bases: [db], cap: capd, x: m, font: 'clash', flip: 1, fill: true },
      { name: 'meta', lines: [t.org], bases: [meta], cap: sc, x: m, font: 'departure', flip: 1, v: ink(c) },
      { name: 'meta', lines: [codename(spec.pal)], bases: [meta], cap: sc, x: W - m, font: 'departure', flip: 1, v: ink(c), right: true },
    ],
    qr: { left: m, bottom: H - m },
    starY: (tb[0] + tb[tb.length - 1]) / 2 - cap / 2,
  };
  return compose(c, L);
}
