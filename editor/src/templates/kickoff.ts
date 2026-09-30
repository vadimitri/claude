// kickoff.layout / kickoff.type_layers: Meta "NN/18 HEX" + Codename, riesiges SPARK, KICK-OFF + Datum, JOIN US ueber dem QR
import data from '../data.json';
import type { Spec } from '../spec';
import { codename, compose, ctxOf, ink, qrSize, type Built, type Layout } from './compose';
import { widthPerCap } from './type';

export const name = 'Kick-off';
export const pals = data.kick_pals;
export const copy = { title: 'SPARK', what: 'KICK-OFF', when: '14.10. / 17:00', where: '', cta: 'JOIN US' };

export function build(spec: Spec): Built {
  const c = ctxOf(spec);
  const { W, H, px, short, snap, port } = c;
  const t = { ...copy, ...spec.copy };
  const m = snap(0.07 * short), sc = 0.026 * short, meta = m + snap(sc);
  const measure = port ? W - 2 * m : 0.55 * W;              // quer: Titel nur links, rechts Platz fuer den Stern
  const cap = Math.floor(measure / px / Math.max(0.1, widthPerCap(t.title))) * px;
  const tb = [meta + snap(0.36 * cap) + cap];
  const capd = snap(0.3 * cap);
  const sub = [t.what, t.when, t.where].filter(Boolean);
  const sb = sub.map((_, i) => tb[0] + snap(0.2 * cap) + capd + i * snap(1.3 * capd));
  const qs = (qrSize(spec.qr) + 6) * 2 * px, qbot = H - m;
  const capj = snap(0.62 * capd), jb = qbot - qs - snap(0.45 * capj);
  const i = pals.indexOf(spec.pal);
  const frag = (data.frag as Record<string, string>)[spec.pal] ?? '';
  const L: Layout = {
    blocks: [
      { name: 'title', title: true, lines: [t.title], bases: tb, cap, x: m, font: 'clash', flip: 1, fill: true },
      { name: 'date', lines: sub, bases: sb, cap: capd, x: m, font: 'clash', flip: 2, fill: true },
      ...(t.cta && spec.qr ? [{ name: 'cta', lines: [t.cta], bases: [jb], cap: capj, x: m, font: 'clash' as const, flip: 0 as const, fill: true, box: { centerOn: [m, qs] as [number, number] } }] : []),
      { name: 'meta', lines: [`${String(i + 1).padStart(2, '0')}/${pals.length} ${frag}`], bases: [meta], cap: sc, x: m, font: 'departure', flip: 2, v: ink(c) },
      { name: 'meta', lines: [codename(spec.pal)], bases: [meta], cap: sc, x: W - m, font: 'departure', flip: 2, v: ink(c), right: true },
    ],
    qr: { left: m, bottom: qbot },
    starY: 0.4 * H,
  };
  return compose(c, L);
}
