// Plakat = JSON-Spec; Kampagne = Liste von Specs (localStorage + Export/Import)
import data from './data.json';

export type Star = { x: number; y: number; R: number; rot: number };  // x/W, y/H, R/kurze Seite, rot Grad
export type Spec = {
  id: string;
  template: string;
  fmt: string;
  pal: string;
  spark: string;
  K: string | null;       // Preset (K1..K8) oder null = frei (star)
  star: Star | null;
  rot: number;
  seed: number;
  copy: Record<string, string>;
  qr: string;
};

export const uid = () => Math.random().toString(36).slice(2, 10);
export const PCODE: Record<string, string> = Object.fromEntries(Object.entries(data.P).map(([c, v]) => [v, c]));
export const KS = Object.keys(data.K);

export function newSpec(template = 'kickoff', over: Partial<Spec> = {}): Spec {
  return {
    id: uid(), template, fmt: template === 'kickoff' ? 'a3' : template === 'slide' ? '16x9' : '9x16',
    pal: template === 'kickoff' ? 'signal' : 'lav', spark: 'S7', K: 'K4', star: null, rot: 14, seed: 0,
    copy: {}, qr: data.qr_url, ...over,
  };
}

export const codeOf = (s: Spec) => `${PCODE[s.pal] ?? s.pal}-${s.spark}-${s.star ? 'custom' : (data.own as string[]).includes(s.spark) ? 'K0' : s.K}`;
export const fileName = (s: Spec) => `${s.template}__${codeOf(s)}__${s.fmt}.png`;

const KEY = 'spark-editor-campaign-v1';
export function load(): Spec[] | null {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    return Array.isArray(v) && v.length ? v : null;
  } catch { return null; }
}
export function save(c: Spec[]) {
  try { localStorage.setItem(KEY, JSON.stringify(c)); } catch { /* voll / gesperrt */ }
}

// seeded RNG (mulberry32)
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 12 Geschwister: Streuung 0..1 = wie weit Palette/K/Stern/Rotation springen. */
export function variants(base: Spec, pals: string[], sparks: string[], spread: number, seed: number, n = 12): Spec[] {
  const r = rng(seed);
  const pick = <T,>(a: T[]) => a[Math.floor(r() * a.length)];
  return Array.from({ length: n }, () => {
    const s: Spec = clone(base);
    s.id = uid();
    s.seed = Math.floor(r() * 1000);
    if (r() < spread) s.pal = pick(pals);
    if (r() < spread * 0.6) s.spark = pick(sparks);
    s.rot = Math.round((base.rot + (r() - 0.5) * 120 * spread + 360) % 360);
    if (r() < spread * 0.5 || !base.star) { s.K = pick(KS); s.star = null; }
    if (base.star && s.star) {
      s.star = { x: base.star.x + (r() - 0.5) * 0.5 * spread, y: base.star.y + (r() - 0.5) * 0.5 * spread,
        R: Math.max(0.1, base.star.R * (1 + (r() - 0.5) * spread)), rot: s.rot };
    }
    return s;
  });
}
export function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)); }

export type Counts = { P: Record<string, number>; S: Record<string, number>; K: Record<string, number> };
export function counts(c: Spec[], pals: string[], sparks: string[]): Counts {
  const o: Counts = { P: Object.fromEntries(pals.map((p) => [p, 0])), S: Object.fromEntries(sparks.map((s) => [s, 0])), K: Object.fromEntries(KS.map((k) => [k, 0])) };
  for (const s of c) {
    if (s.pal in o.P) o.P[s.pal]++;
    if (s.spark in o.S) o.S[s.spark]++;
    if (!s.star && s.K && s.K in o.K) o.K[s.K]++;
  }
  return o;
}

/** kickoff.mix, ein Schritt: seltenste P, S, K, keine Kombi doppelt. */
export function fill(c: Spec[], base: Spec, pals: string[], sparks: string[]): Spec {
  const n = counts(c, pals, sparks);
  const used = new Set(c.map((s) => `${s.pal}|${s.spark}|${s.K}`));
  const r = rng(c.length * 7919 + 1);
  let best: [string, string, string] | null = null, bs = Infinity;
  for (const p of pals) for (const s of sparks) for (const k of KS) {
    if (used.has(`${p}|${s}|${k}`)) continue;
    const sc = n.P[p] + n.S[s] + n.K[k] + r() * 0.5;
    if (sc < bs) { bs = sc; best = [p, s, k]; }
  }
  const [pal, spark, K] = best ?? [pals[0], sparks[0], KS[0]];
  return { ...clone(base), id: uid(), pal, spark, K, star: null, rot: Math.round(r() * 60), seed: Math.floor(r() * 1000) };
}
