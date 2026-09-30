<script lang="ts">
  import data from '../data.json';
  import { TEMPLATES, FMTS, buildSpec } from '../templates';
  import { KS, PCODE, codeOf, type Spec } from '../spec';
  import { st } from './store.svelte';
  import Section from './Section.svelte';
  import Num from './Num.svelte';

  const s = $derived(st.spec);
  const tpl = $derived(TEMPLATES[s.template] ?? TEMPLATES.kickoff);
  const pals = data.pals as Record<string, string[]>;
  const kname = data.K as Record<string, string>;
  const built = $derived.by(() => { try { return buildSpec($state.snapshot(s) as Spec); } catch { return null; } });
  const sf = $derived(built?.star ?? [0.5, 0.5, 0.5, 0]);

  function setStar(k: 'x' | 'y' | 'R' | 'rot', v: number) {
    if (!s.star) { s.star = { x: sf[0], y: sf[1], R: sf[2], rot: sf[3] }; s.K = null; }
    s.star[k] = v;
    if (k === 'rot') s.rot = v;
  }
  function setTemplate(t: string) {
    st.edit((x) => {
      x.template = t;
      x.copy = {};
      if (!TEMPLATES[t].pals.includes(x.pal)) x.pal = TEMPLATES[t].pals[0];
    });
    st.fitReq++;
  }
  const own = $derived((data.own as string[]).includes(s.spark));
</script>

<aside>
  <div class="tabs"><span class="on">Design</span><span class="code">{codeOf(s)}</span></div>

  <Section title="Template">
    <select value={s.template} onchange={(e) => setTemplate(e.currentTarget.value)}>
      {#each Object.entries(TEMPLATES) as [k, t]}<option value={k}>{t.name}</option>{/each}
    </select>
  </Section>

  <Section title="Format">
    <div class="seg">
      {#each Object.keys(FMTS) as f}
        <button class:on={s.fmt === f} onclick={() => { st.edit((x) => (x.fmt = f)); st.fitReq++; }}>{f}</button>
      {/each}
    </div>
  </Section>

  <Section title="Farbe">
    <div class="pals">
      {#each tpl.pals as p}
        <button class="pal" class:on={s.pal === p} title="{PCODE[p]} · {p}" onclick={() => st.edit((x) => (x.pal = p))}>
          <span class="ramp">{#each pals[p] as c}<i style:background={c}></i>{/each}</span>
          <span class="pn"><b>{PCODE[p]}</b> {(data.codename as Record<string, string>)[p]}</span>
        </button>
      {/each}
    </div>
  </Section>

  <Section title="Stern">
    <div class="sparks">
      {#each st.sparks as c}
        <button class:on={s.spark === c} onclick={() => st.edit((x) => (x.spark = c))}>{c}{#if (data.own as string[]).includes(c)}<sup>own</sup>{/if}</button>
      {/each}
    </div>
    <div class="grid2">
      <Num label="X" value={sf[0]} step={0.002} set={(v) => setStar('x', v)} />
      <Num label="Y" value={sf[1]} step={0.002} set={(v) => setStar('y', v)} />
      <Num label="R" value={sf[2]} step={0.004} min={0.02} set={(v) => setStar('R', v)} />
      <Num label="↻" value={sf[3]} step={0.5} digits={1} set={(v) => setStar('rot', v)} />
    </div>
    <div class="ks">
      {#each KS as k}
        <button class:on={!s.star && s.K === k} title={kname[k]} onclick={() => st.edit((x) => { x.K = k; x.star = null; })}>{k}<small>{kname[k]}</small></button>
      {/each}
    </div>
    <p class="hint">{s.star ? 'frei platziert' : own ? 'OWN: Platzierung vom Stern' : `Preset ${s.K} ${kname[s.K ?? '']}`}</p>
  </Section>

  <Section title="Text">
    {#each Object.entries(tpl.copy) as [k, dflt]}
      <label class="field"><span>{k}</span>
        {#if dflt.includes('\n') || k === 'title'}
          <textarea rows={Math.max(1, (s.copy[k] ?? dflt).split('\n').length)} value={s.copy[k] ?? dflt}
            onfocus={() => st.checkpoint()} onkeydown={(e) => e.stopPropagation()}
            oninput={(e) => (s.copy[k] = e.currentTarget.value)}></textarea>
        {:else}
          <input value={s.copy[k] ?? dflt} onfocus={() => st.checkpoint()} onkeydown={(e) => e.stopPropagation()}
            oninput={(e) => (s.copy[k] = e.currentTarget.value)} />
        {/if}
      </label>
    {/each}
  </Section>

  <Section title="QR">
    <label class="field"><span>URL</span>
      <input value={s.qr} placeholder="leer = kein QR" onfocus={() => st.checkpoint()} onkeydown={(e) => e.stopPropagation()}
        oninput={(e) => (s.qr = e.currentTarget.value)} /></label>
  </Section>

  <Section title="Seed">
    <div class="grid2">
      <Num label="#" value={s.seed} step={1} digits={0} min={0} set={(v) => (s.seed = v)} />
      <button class="btn" onclick={() => st.edit((x) => (x.seed = Math.floor(Math.random() * 1000)))}>Zufall</button>
    </div>
  </Section>
</aside>

<style>
  aside { width: 260px; flex: none; background: #2c2c2c; border-left: 1px solid #444; overflow-y: auto; }
  .tabs { display: flex; justify-content: space-between; align-items: center; height: 40px; padding: 0 12px; border-bottom: 1px solid #444; }
  .tabs .on { font-weight: 600; color: #fff; }
  .code { color: #999; font-family: ui-monospace, monospace; font-size: 10px; }
  select, input, textarea { width: 100%; background: #383838; border: 1px solid transparent; color: #eee; font: inherit; border-radius: 2px; padding: 4px 6px; outline: none; box-sizing: border-box; }
  select:focus, input:focus, textarea:focus { border-color: #0d99ff; }
  textarea { resize: vertical; font-family: inherit; }
  .seg { display: flex; flex-wrap: wrap; gap: 2px; background: #383838; border-radius: 3px; padding: 2px; }
  .seg button { flex: 1; background: none; border: 0; color: #bbb; font: inherit; padding: 4px 0; border-radius: 2px; cursor: pointer; }
  .seg button.on { background: #1e1e1e; color: #fff; }
  .pals { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
  .pal { background: none; border: 1px solid transparent; border-radius: 3px; padding: 3px; cursor: pointer; text-align: left; color: #bbb; font: inherit; }
  .pal:hover { border-color: #555; }
  .pal.on { border-color: #0d99ff; color: #fff; }
  .ramp { display: flex; height: 14px; border-radius: 2px; overflow: hidden; }
  .ramp i { flex: 1; }
  .pn { display: block; font-size: 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }
  .pn b { color: #eee; }
  .sparks { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; margin-bottom: 8px; }
  .sparks button, .ks button, .btn { background: #383838; border: 1px solid transparent; color: #ddd; font: inherit; border-radius: 2px; padding: 4px 2px; cursor: pointer; }
  .sparks button:hover, .ks button:hover, .btn:hover { border-color: #555; }
  .sparks button.on, .ks button.on { border-color: #0d99ff; color: #fff; background: #0d99ff22; }
  sup { font-size: 7px; color: #999; margin-left: 1px; }
  .ks { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; margin-top: 6px; }
  .ks small { display: block; font-size: 8px; color: #999; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 8px; }
  .field { display: block; margin-bottom: 6px; }
  .field span { display: block; color: #999; margin-bottom: 2px; }
  .hint { color: #888; font-size: 10px; margin: 6px 0 0; }
</style>
