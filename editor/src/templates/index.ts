import type { Spec } from '../spec';
import { ctxOf, starFrac, type Built } from './compose';
import * as kickoff from './kickoff';
import * as makernight from './makernight';
import * as event from './event';
import * as slide from './slide';

export type Template = { name: string; pals: string[]; copy: Record<string, string>; build: (s: Spec) => Built };
export const TEMPLATES: Record<string, Template> = { kickoff, makernight, event, slide };
export { FMTS } from './compose';
export { loadFonts } from './type';
import { fontsLoaded } from './type';
export type { Built } from './compose';

// Satz nur neu bauen, wenn sich Schrift/Format/Palette aendern; Stern, Spark, Seed werden nur gepatcht (Drag = billig)
const cache = new Map<string, Built>();
export function buildSpec(s: Spec): Built {
  const key = JSON.stringify([s.template, s.fmt, s.pal, s.copy, s.qr]);
  let b = cache.get(key);
  if (!b) {
    b = (TEMPLATES[s.template] ?? TEMPLATES.kickoff).build(s);
    if (fontsLoaded) cache.set(key, b);
    if (cache.size > 64) cache.delete(cache.keys().next().value!);
  }
  const c = ctxOf(s);
  const sf = starFrac(c, b.L, b.scene.titleBox);
  const scene = { ...b.scene, spark: s.spark, seed: s.seed, star: [(sf[0] * c.W) / c.short, (sf[1] * c.H) / c.short, sf[2], sf[3]] as [number, number, number, number] };
  return { ...b, scene, star: sf };
}
