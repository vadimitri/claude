<script lang="ts">
  import { onMount } from 'svelte';
  import type { Renderer } from './render/renderer';
  import { TEMPLATES, FMTS, buildSpec } from './templates';
  import { fileName, newSpec, variants, type Spec } from './spec';
  import { st } from './ui/store.svelte';
  import { thumb } from './ui/thumbs.svelte';
  import Canvas from './ui/Canvas.svelte';
  import Left from './ui/Left.svelte';
  import Inspector from './ui/Inspector.svelte';

  let renderer: Renderer | null = null;
  let spread = $state(0.5);
  let vseed = $state(1);
  let busy = $state('');
  const tpl = $derived(TEMPLATES[st.spec.template] ?? TEMPLATES.kickoff);
  const sibs = $derived(st.variantsOpen ? variants($state.snapshot(st.spec) as Spec, tpl.pals, st.sparks, spread, vseed) : []);

  $effect(() => {                             // speichern (entprellt)
    void $state.snapshot(st.campaign);
    const t = setTimeout(() => st.persist(), 300);
    return () => clearTimeout(t);
  });

  function onready(r: Renderer) {
    renderer = r;
    st.sparks = r.sparkCodes();
    if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__ed = { st, r, buildSpec };
  }

  const snap = () => $state.snapshot(st.spec) as Spec;
  function download(blob: Blob, name: string) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  async function exportOne() {
    if (!renderer) return;
    busy = 'Export …';
    try { download(await renderer.exportPNG(buildSpec(snap()).scene), fileName(snap())); } finally { busy = ''; renderer.render(buildSpec(snap()).scene); }
  }
  async function exportAll() {
    if (!renderer) return;
    const picker = (window as unknown as { showDirectoryPicker?: (o?: object) => Promise<FileSystemDirectoryHandle> }).showDirectoryPicker;
    if (!picker) { alert('Braucht Chrome (File System Access API).'); return; }
    const dir = await picker({ mode: 'readwrite' });
    const all = $state.snapshot(st.campaign) as Spec[];
    const seen = new Map<string, number>();
    for (const [i, s] of all.entries()) {
      busy = `Export ${i + 1}/${all.length}`;
      let name = fileName(s);
      const k = seen.get(name) ?? 0;
      seen.set(name, k + 1);
      if (k) name = name.replace('.png', `_${k + 1}.png`);
      const blob = await renderer.exportPNG(buildSpec(s).scene);
      const w = await (await dir.getFileHandle(name, { create: true })).createWritable();
      await w.write(blob);
      await w.close();
    }
    const w = await (await dir.getFileHandle('campaign.json', { create: true })).createWritable();
    await w.write(JSON.stringify(all, null, 1));
    await w.close();
    busy = '';
    renderer.render(buildSpec(snap()).scene);
  }
  function exportJSON() {
    download(new Blob([JSON.stringify($state.snapshot(st.campaign), null, 1)], { type: 'application/json' }), 'campaign.json');
  }
  function importJSON() {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = '.json,application/json';
    inp.onchange = async () => {
      try {
        const v = JSON.parse(await inp.files![0].text());
        const list = (Array.isArray(v) ? v : [v]).map((s: Partial<Spec>) => ({ ...newSpec(s.template ?? 'kickoff'), ...s }));
        st.checkpoint();
        st.campaign = list;
        st.cur = 0;
      } catch (e) { alert('Import fehlgeschlagen: ' + e); }
    };
    inp.click();
  }

  function key(e: KeyboardEvent) {
    const t = e.target as HTMLElement;
    if (/INPUT|TEXTAREA|SELECT/.test(t.tagName)) return;
    const mod = e.metaKey || e.ctrlKey;
    const k = e.key.toLowerCase();
    if (mod && k === 'z') { e.preventDefault(); e.shiftKey ? st.doRedo() : st.doUndo(); return; }
    if (mod && k === 'y') { e.preventDefault(); st.doRedo(); return; }
    if (mod && k === 'd') { e.preventDefault(); st.duplicate(); return; }
    if (mod && k === '0') { e.preventDefault(); st.zoom = 1; return; }
    if (e.shiftKey && e.code === 'Digit1') { st.fitReq++; return; }
    if (k === 'delete' || k === 'backspace') { e.preventDefault(); st.remove(); return; }
    if (mod) return;
    const arrows: Record<string, [number, number]> = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, -1], arrowdown: [0, 1] };
    if (k in arrows || k === 'r') {
      e.preventDefault();
      const b = buildSpec(snap());
      const f = b.star;
      st.edit((s) => {
        if (!s.star) { s.star = { x: f[0], y: f[1], R: f[2], rot: f[3] }; s.K = null; }
        if (k === 'r') { s.star.rot = (s.star.rot + (e.shiftKey ? -15 : 15) + 360) % 360; s.rot = s.star.rot; return; }
        const [dx, dy] = arrows[k], step = b.scene.cellPx * (e.shiftKey ? 10 : 1);
        s.star.x += (dx * step) / b.scene.W;
        s.star.y += (dy * step) / b.scene.H;
      });
      return;
    }
    if (k === 'escape') st.variantsOpen = false;
  }

  onMount(() => {
    addEventListener('keydown', key);
    return () => removeEventListener('keydown', key);
  });
</script>

<div class="app">
  <header class="bar">
    <span class="logo">✦ SPARK</span>
    <select value={st.spec.template} onchange={(e) => { const v = e.currentTarget.value; st.edit((s) => { s.template = v; s.copy = {}; if (!TEMPLATES[v].pals.includes(s.pal)) s.pal = TEMPLATES[v].pals[0]; }); st.fitReq++; }}>
      {#each Object.entries(TEMPLATES) as [k, t]}<option value={k}>{t.name}</option>{/each}
    </select>
    <select value={st.spec.fmt} onchange={(e) => { const v = e.currentTarget.value; st.edit((s) => (s.fmt = v)); st.fitReq++; }}>
      {#each Object.keys(FMTS) as f}<option value={f}>{f}</option>{/each}
    </select>
    <button class="tb" onclick={() => (st.variantsOpen = true)}>Varianten</button>
    <span class="grow"></span>
    {#if busy}<span class="busy">{busy}</span>{/if}
    <button class="tb" onclick={importJSON}>Import</button>
    <button class="tb" onclick={exportJSON}>JSON</button>
    <button class="tb" onclick={exportAll}>Alle exportieren</button>
    <button class="zoom" onclick={() => st.fitReq++} title="Einpassen (⇧1)">{Math.round(st.zoom * 100)}%</button>
    <button class="primary" onclick={exportOne}>Export PNG</button>
  </header>
  <main>
    <Left />
    <Canvas {onready} />
    <Inspector />
  </main>

  {#if st.variantsOpen}
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="modal" onclick={() => (st.variantsOpen = false)}>
      <div class="dlg" onclick={(e) => e.stopPropagation()}>
        <div class="dh">
          <b>Varianten</b>
          <label>Streuung <input type="range" min="0" max="1" step="0.05" bind:value={spread} /> {Math.round(spread * 100)}%</label>
          <button class="tb" onclick={() => vseed++}>Neu würfeln</button>
          <span class="grow"></span>
          <button class="tb" onclick={() => (st.variantsOpen = false)}>Schließen</button>
        </div>
        <div class="vgrid">
          {#each sibs as v (v.id)}
            <button class="vt" onclick={() => st.add(v, false)} title="zur Kampagne hinzufügen">
              {#if thumb(v, 200)}<img src={thumb(v, 200)} alt="" />{:else}<span class="ph"></span>{/if}
              <small>{v.pal} · {v.spark} · {v.star ? 'frei' : v.K}</small>
            </button>
          {/each}
        </div>
        <p class="hint">Klick = zur Kampagne hinzufügen (hinter dem aktuellen Plakat).</p>
      </div>
    </div>
  {/if}
</div>

<style>
  :global(html, body) { margin: 0; height: 100%; background: #1e1e1e; color: #eee; font: 11px Inter, system-ui, -apple-system, sans-serif; overflow: hidden; }
  :global(#app) { height: 100%; }
  :global(button) { font: inherit; }
  .app { display: flex; flex-direction: column; height: 100%; }
  .bar { display: flex; align-items: center; gap: 6px; height: 40px; padding: 0 8px; background: #2c2c2c; border-bottom: 1px solid #444; flex: none; }
  .logo { font-weight: 700; padding: 0 8px; letter-spacing: 0.05em; }
  .bar select { background: #383838; color: #eee; border: 1px solid transparent; border-radius: 2px; height: 26px; font: inherit; }
  .tb, .zoom { background: none; color: #ddd; border: 1px solid transparent; border-radius: 2px; height: 26px; padding: 0 8px; cursor: pointer; }
  .tb:hover, .zoom:hover { background: #383838; }
  .primary { background: #0d99ff; color: #fff; border: 0; border-radius: 4px; height: 26px; padding: 0 12px; cursor: pointer; font-weight: 600; }
  .grow { flex: 1; }
  .busy { color: #0d99ff; }
  main { flex: 1; display: flex; min-height: 0; }
  .modal { position: fixed; inset: 0; background: #0008; display: grid; place-items: center; z-index: 10; }
  .dlg { background: #2c2c2c; border: 1px solid #444; border-radius: 6px; width: min(1100px, 92vw); max-height: 88vh; overflow: auto; box-shadow: 0 10px 40px #000a; }
  .dh { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid #444; position: sticky; top: 0; background: #2c2c2c; }
  .dh label { display: flex; align-items: center; gap: 6px; color: #bbb; }
  .vgrid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; padding: 12px; }
  .vt { background: #1e1e1e; border: 1px solid transparent; border-radius: 3px; padding: 4px; cursor: pointer; color: #bbb; }
  .vt:hover { border-color: #0d99ff; }
  .vt img, .vt .ph { display: block; width: 100%; aspect-ratio: auto; min-height: 60px; }
  .vt small { display: block; margin-top: 4px; font-size: 9px; }
  .hint { color: #888; padding: 0 12px 12px; margin: 0; }
</style>
