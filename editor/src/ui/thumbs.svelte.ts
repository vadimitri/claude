// Vorschaubilder: eigener Renderer auf verstecktem Canvas, eins pro Frame, Cache per Spec-JSON
import { Renderer } from '../render/renderer';
import { buildSpec, loadFonts } from '../templates';
import type { Spec } from '../spec';

const urls = $state<Record<string, string>>({});
let r: Renderer | null = null;
const queue = new Map<string, Spec>();
let busy = false;

const keyOf = (s: Spec) => JSON.stringify({ ...s, id: 0 });

export function thumb(s: Spec, w = 120): string | undefined {
  const k = keyOf(s) + w;
  const u = urls[k];
  if (u === undefined && !queue.has(k)) {
    queue.set(k, JSON.parse(JSON.stringify(s)));
    pump(w);
  }
  return u;
}

function pump(w: number) {
  if (busy) return;
  busy = true;
  loadFonts().then(() => requestAnimationFrame(() => {
    busy = false;
    const it = queue.entries().next();
    if (it.done) return;
    const [k, s] = it.value;
    queue.delete(k);
    try {
      r ??= new Renderer(document.createElement('canvas'));
      const b = buildSpec(s);
      r.render(b.scene);
      const c = document.createElement('canvas');
      c.width = w;
      c.height = Math.round((w * b.scene.H) / b.scene.W);
      const x = c.getContext('2d')!;
      x.imageSmoothingEnabled = true;
      x.drawImage(r.canvas, 0, 0, c.width, c.height);
      urls[k] = c.toDataURL();
    } catch (e) {
      console.warn('thumb', e);
      urls[k] = '';
    }
    if (queue.size) pump(w);
  }));
}
