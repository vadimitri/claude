<script lang="ts">
  import { onMount } from 'svelte';
  import { Renderer } from '../render/renderer';
  import { buildSpec, loadFonts, type Built } from '../templates';
  import { st } from './store.svelte';
  import type { Spec } from '../spec';

  let { onready }: { onready?: (r: Renderer) => void } = $props();

  let view: HTMLDivElement;
  let canvas: HTMLCanvasElement;
  let renderer: Renderer | null = null;
  let fontsOk = $state(false);
  let built = $state<Built | null>(null);
  let vw = $state(800), vh = $state(600);
  let space = $state(false);
  let mode = $state<'' | 'pan' | 'move' | 'scale' | 'rot'>('');
  let hover = $state<'' | 'move' | 'scale' | 'rot'>('');
  let err = $state('');

  const W = $derived(built?.scene.W ?? 1000);
  const H = $derived(built?.scene.H ?? 1000);
  const short = $derived(Math.min(W, H));

  // Stern in Plakatpixeln
  const star = $derived.by(() => {
    const f = built?.star ?? [0.5, 0.5, 0.5, 0];
    return { x: f[0] * W, y: f[1] * H, r: f[2] * short, rot: f[3] };
  });
  const toS = (x: number, y: number) => [st.panX + x * st.zoom, st.panY + y * st.zoom];
  const toP = (sx: number, sy: number) => [(sx - st.panX) / st.zoom, (sy - st.panY) / st.zoom];

  let raf = 0;
  $effect(() => {
    const snap = $state.snapshot(st.spec) as Spec;   // tief verfolgen
    if (!fontsOk) return;
    try {
      built = buildSpec(snap);
      err = '';
    } catch (e) {
      err = String(e);
      return;
    }
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      if (!renderer || !built) return;
      try { renderer.render(built.scene); } catch (e) { err = String(e); }
    });
  });

  $effect(() => {                        // Einpassen bei Formatwechsel / auf Anfrage
    void st.fitReq; void W; void H; void vw; void vh;
    fit();
  });
  function fit() {
    const z = Math.min((vw - 96) / W, (vh - 96) / H);
    st.zoom = Math.max(0.02, z);
    st.panX = (vw - W * st.zoom) / 2;
    st.panY = (vh - H * st.zoom) / 2;
  }

  onMount(() => {
    try {
      renderer = new Renderer(canvas);
      onready?.(renderer);
    } catch (e) { err = String(e); }
    loadFonts().then(() => (fontsOk = true), (e) => (err = 'Fonts: ' + e));
    const ro = new ResizeObserver(() => { vw = view.clientWidth; vh = view.clientHeight; });
    ro.observe(view);
    const kd = (e: KeyboardEvent) => { if (e.code === 'Space' && !isInput(e.target)) { space = true; e.preventDefault(); } };
    const ku = (e: KeyboardEvent) => { if (e.code === 'Space') space = false; };
    addEventListener('keydown', kd);
    addEventListener('keyup', ku);
    return () => { ro.disconnect(); removeEventListener('keydown', kd); removeEventListener('keyup', ku); };
  });
  const isInput = (t: EventTarget | null) => t instanceof HTMLElement && /INPUT|TEXTAREA|SELECT/.test(t.tagName);

  // Treffer: Rotationsgriff ausserhalb der Ecken, Eckgriffe skalieren, innen verschieben
  function hit(sx: number, sy: number): '' | 'move' | 'scale' | 'rot' {
    const [cx, cy] = toS(star.x, star.y);
    const rs = star.r * st.zoom;
    const a = (-star.rot * Math.PI) / 180;
    const dx = sx - cx, dy = sy - cy;
    const lx = dx * Math.cos(a) - dy * Math.sin(a), ly = dx * Math.sin(a) + dy * Math.cos(a);
    const nearCorner = Math.abs(Math.abs(lx) - rs) < 7 && Math.abs(Math.abs(ly) - rs) < 7;
    if (nearCorner) return 'scale';
    const outX = Math.abs(lx) - rs, outY = Math.abs(ly) - rs;
    if (outX > 0 && outY > 0 && outX < 22 && outY < 22) return 'rot';
    if (Math.abs(lx) < rs && Math.abs(ly) < rs && Math.hypot(lx, ly) < rs * 0.9) return 'move';
    return '';
  }

  function materialize(s: Spec) {           // K-Preset -> freie Platzierung
    if (!s.star && built) {
      const f = built.star;
      s.star = { x: f[0], y: f[1], R: f[2], rot: f[3] };
      s.K = null;
    }
  }

  let drag = { sx: 0, sy: 0, px: 0, py: 0, x0: 0, y0: 0, R0: 0, rot0: 0, a0: 0 };
  function down(e: PointerEvent) {
    const r = view.getBoundingClientRect();
    const sx = e.clientX - r.left, sy = e.clientY - r.top;
    if (e.button === 1 || space) {
      mode = 'pan';
      drag = { ...drag, sx, sy, px: st.panX, py: st.panY };
    } else if (e.button === 0) {
      const h = hit(sx, sy);
      if (!h) { st.layer = 'star'; return; }
      st.layer = 'star';
      st.checkpoint();
      materialize(st.spec);
      const s = st.spec.star!;
      const [cx, cy] = toS(star.x, star.y);
      drag = { ...drag, sx, sy, x0: s.x, y0: s.y, R0: s.R, rot0: s.rot, a0: Math.atan2(sy - cy, sx - cx) };
      mode = h;
    } else return;
    view.setPointerCapture(e.pointerId);
    e.preventDefault();
  }
  function move(e: PointerEvent) {
    const r = view.getBoundingClientRect();
    const sx = e.clientX - r.left, sy = e.clientY - r.top;
    if (!mode) { hover = hit(sx, sy); return; }
    if (mode === 'pan') {
      st.panX = drag.px + sx - drag.sx;
      st.panY = drag.py + sy - drag.sy;
      return;
    }
    const s = st.spec.star!;
    if (mode === 'move') {
      s.x = drag.x0 + (sx - drag.sx) / st.zoom / W;
      s.y = drag.y0 + (sy - drag.sy) / st.zoom / H;
    } else if (mode === 'scale') {
      const [cx, cy] = toS(star.x, star.y);
      const d0 = Math.hypot(drag.sx - cx, drag.sy - cy), d1 = Math.hypot(sx - cx, sy - cy);
      s.R = Math.max(0.02, (drag.R0 * d1) / Math.max(1, d0));
    } else if (mode === 'rot') {
      const [cx, cy] = toS(star.x, star.y);
      let rot = drag.rot0 + ((Math.atan2(sy - cy, sx - cx) - drag.a0) * 180) / Math.PI;
      if (e.shiftKey) rot = Math.round(rot / 15) * 15;
      s.rot = Math.round(((rot % 360) + 360) % 360 * 10) / 10;
      st.spec.rot = s.rot;
    }
  }
  function up() { mode = ''; }

  function wheel(e: WheelEvent) {
    e.preventDefault();
    const r = view.getBoundingClientRect();
    const sx = e.clientX - r.left, sy = e.clientY - r.top;
    if (e.ctrlKey || e.metaKey) {
      const [px, py] = toP(sx, sy);
      st.zoom = Math.min(8, Math.max(0.02, st.zoom * Math.exp(-e.deltaY * 0.01)));
      st.panX = sx - px * st.zoom;
      st.panY = sy - py * st.zoom;
      return;
    }
    const mouseWheel = e.deltaMode === 1 || (e.deltaX === 0 && Math.abs(e.deltaY) >= 50 && Number.isInteger(e.deltaY));
    if (e.altKey || (mouseWheel && hit(sx, sy) === 'move')) {
      st.edit((s) => { materialize(s); s.star!.R = Math.max(0.02, s.star!.R * Math.exp(-e.deltaY * 0.002)); });
      return;
    }
    st.panX -= e.deltaX;
    st.panY -= e.deltaY;
  }

  // Auswahlrahmen einer Ebene (Zellen -> Bildschirm)
  const layerRect = $derived.by(() => {
    if (!built || st.layer === 'star' || st.layer === 'bg') return null;
    const b = built.boxes[st.layer];
    if (!b) return null;
    const px = built.scene.cellPx;
    const [x0, y0] = toS(b[0] * px, b[1] * px);
    return { x: x0, y: y0, w: (b[2] - b[0]) * px * st.zoom, h: (b[3] - b[1]) * px * st.zoom };
  });
  const cursor = $derived(mode === 'pan' || space ? (mode ? 'grabbing' : 'grab') : ({ move: 'move', scale: 'nwse-resize', rot: 'alias', '': 'default' } as const)[mode || hover]);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="view" bind:this={view} style:cursor onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up} onwheel={wheel}>
  <canvas bind:this={canvas} style:left="{st.panX}px" style:top="{st.panY}px" style:width="{W * st.zoom}px" style:height="{H * st.zoom}px"></canvas>
  <div class="label" style:left="{st.panX}px" style:top="{st.panY - 20}px">{st.spec.template} · {st.spec.fmt} · {W}×{H}</div>
  <svg width={vw} height={vh}>
    {#if layerRect}
      <rect x={layerRect.x} y={layerRect.y} width={layerRect.w} height={layerRect.h} class="sel" />
    {/if}
    {#if st.layer === 'star' && built}
      {@const c = toS(star.x, star.y)}
      {@const rs = star.r * st.zoom}
      <g transform="translate({c[0]} {c[1]}) rotate({star.rot})">
        <rect x={-rs} y={-rs} width={2 * rs} height={2 * rs} class="sel" />
        <circle r={rs} class="ring" />
        {#each [[-1, -1], [1, -1], [1, 1], [-1, 1]] as [a, b]}
          <rect x={a * rs - 4} y={b * rs - 4} width="8" height="8" class="h" />
        {/each}
        <line x1={0} y1={-6} x2={0} y2={6} class="cross" /><line x1={-6} y1={0} x2={6} y2={0} class="cross" />
      </g>
      <text x={c[0]} y={c[1] + rs + 22} class="dim" text-anchor="middle">
        {Math.round(star.x)}, {Math.round(star.y)} · R {built.star[2].toFixed(2)} · {Math.round(star.rot)}°
      </text>
    {/if}
  </svg>
  {#if err}<div class="err">{err}</div>{/if}
  {#if renderer?.errors.length}<div class="err">Shader: {renderer.errors.map((e) => e.code).join(', ')}</div>{/if}
</div>

<style>
  .view { position: relative; flex: 1; overflow: hidden; background: #1e1e1e; touch-action: none; user-select: none; }
  canvas { position: absolute; image-rendering: pixelated; box-shadow: 0 0 0 1px #0006, 0 4px 24px #0008; }
  svg { position: absolute; inset: 0; pointer-events: none; overflow: visible; }
  .sel { fill: none; stroke: #0d99ff; stroke-width: 1; }
  .ring { fill: none; stroke: #0d99ff; stroke-width: 1; stroke-dasharray: 3 3; opacity: 0.6; }
  .h { fill: #fff; stroke: #0d99ff; stroke-width: 1; }
  .cross { stroke: #0d99ff; }
  .dim { fill: #fff; font-size: 10px; paint-order: stroke; stroke: #0d99ff; stroke-width: 12px; stroke-linejoin: round; }
  .label { position: absolute; color: #999; font-size: 11px; white-space: nowrap; pointer-events: none; }
  .err { position: absolute; left: 8px; bottom: 8px; right: 8px; background: #5a1d1d; color: #fcc; padding: 6px 8px; font: 11px monospace; border-radius: 4px; }
</style>
