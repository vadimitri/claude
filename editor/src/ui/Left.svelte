<script lang="ts">
  import data from '../data.json';
  import { TEMPLATES } from '../templates';
  import { KS, PCODE, codeOf, counts, fill } from '../spec';
  import { st } from './store.svelte';
  import { thumb } from './thumbs.svelte';
  import Section from './Section.svelte';

  const LAYERS = [['star', '✦', 'Stern'], ['title', 'T', 'Titel'], ['date', 'T', 'Datum'], ['cta', '▭', 'CTA'], ['meta', 'T', 'Meta'], ['qr', '▦', 'QR'], ['bg', '▨', 'Hintergrund']];
  const tpl = $derived(TEMPLATES[st.spec.template] ?? TEMPLATES.kickoff);
  // Balance ueber die Plakate mit demselben Template (Paletten-Pool haengt am Template)
  const same = $derived(st.campaign.filter((s) => s.template === st.spec.template));
  const n = $derived(counts(same, tpl.pals, st.sparks));
  const maxOf = (o: Record<string, number>) => Math.max(1, ...Object.values(o));
  const kname = data.K as Record<string, string>;

  function auffuellen() {
    st.add(fill($state.snapshot(same) as never, $state.snapshot(st.spec) as never, tpl.pals, st.sparks));
  }
</script>

<aside>
  <Section title="Plakate · {st.campaign.length}">
    {#snippet extra()}<button class="ic" title="Duplizieren (⌘D)" onclick={() => st.duplicate()}>+</button>{/snippet}
    <div class="pages">
      {#each st.campaign as s, i (s.id)}
        <button class="page" class:on={i === st.cur} onclick={() => (st.cur = i)}>
          {#if thumb(s)}<img src={thumb(s)} alt="" />{:else}<span class="ph"></span>{/if}
          <span class="pt"><b>{String(i + 1).padStart(2, '0')}</b> {codeOf(s)}<br /><small>{s.template} · {s.fmt}</small></span>
          <span class="x" role="button" tabindex="-1" title="Löschen" onclick={(e) => { e.stopPropagation(); st.remove(i); }} onkeydown={() => {}}>×</span>
        </button>
      {/each}
    </div>
  </Section>

  <Section title="Ebenen">
    {#each LAYERS as [k, ic, name]}
      <button class="layer" class:on={st.layer === k} onclick={() => (st.layer = k)}><span class="li">{ic}</span>{name}</button>
    {/each}
  </Section>

  <Section title="Balance · {tpl.name}">
    {#snippet extra()}<button class="btn" onclick={auffuellen} title="neues Plakat aus den seltensten P, S, K">Auffüllen</button>{/snippet}
    <div class="bal">
      <h4>Palette</h4>
      {#each Object.entries(n.P) as [k, v]}
        <div class="bar" title={k}><span class="bk">{PCODE[k]}</span><span class="bt"><i style:width="{(v / maxOf(n.P)) * 100}%" style:background={(data.pals as Record<string, string[]>)[k].at(-1)}></i></span><span class="bv">{v}</span></div>
      {/each}
      <h4>Stern</h4>
      {#each Object.entries(n.S) as [k, v]}
        <div class="bar"><span class="bk">{k}</span><span class="bt"><i style:width="{(v / maxOf(n.S)) * 100}%"></i></span><span class="bv">{v}</span></div>
      {/each}
      <h4>K</h4>
      {#each KS as k}
        <div class="bar" title={kname[k]}><span class="bk">{k}</span><span class="bt"><i style:width="{(n.K[k] / maxOf(n.K)) * 100}%"></i></span><span class="bv">{n.K[k]}</span></div>
      {/each}
    </div>
  </Section>
</aside>

<style>
  aside { width: 240px; flex: none; background: #2c2c2c; border-right: 1px solid #444; overflow-y: auto; }
  .pages { display: flex; flex-direction: column; gap: 1px; max-height: 42vh; overflow-y: auto; margin: 0 -12px 0 -16px; }
  .page { position: relative; display: flex; gap: 8px; align-items: center; background: none; border: 0; color: #ccc; font: inherit; padding: 4px 12px 4px 16px; text-align: left; cursor: pointer; }
  .page:hover { background: #383838; }
  .page.on { background: #0d99ff33; color: #fff; }
  .page img, .ph { width: 40px; height: 52px; object-fit: contain; background: #1e1e1e; flex: none; image-rendering: auto; }
  .pt { font-family: ui-monospace, monospace; font-size: 10px; line-height: 1.4; }
  .pt small { color: #888; font-family: Inter, system-ui, sans-serif; }
  .x { position: absolute; right: 8px; color: #888; opacity: 0; padding: 2px 4px; }
  .page:hover .x { opacity: 1; }
  .x:hover { color: #fff; }
  .layer { display: flex; align-items: center; gap: 8px; width: calc(100% + 28px); margin: 0 -12px 0 -16px; height: 28px; padding: 0 16px; background: none; border: 0; color: #ccc; font: inherit; cursor: pointer; }
  .layer:hover { background: #383838; }
  .layer.on { background: #0d99ff33; color: #fff; }
  .li { width: 14px; color: #999; text-align: center; }
  .ic, .btn { background: #383838; border: 1px solid transparent; color: #ddd; font: inherit; border-radius: 2px; padding: 2px 8px; cursor: pointer; }
  .ic:hover, .btn:hover { border-color: #555; }
  .bal h4 { margin: 8px 0 2px; font-size: 10px; color: #999; font-weight: 500; }
  .bar { display: flex; align-items: center; gap: 6px; height: 14px; font-size: 9px; }
  .bk { width: 34px; color: #bbb; font-family: ui-monospace, monospace; }
  .bt { flex: 1; height: 5px; background: #383838; border-radius: 2px; overflow: hidden; }
  .bt i { display: block; height: 100%; background: #0d99ff; }
  .bv { width: 14px; text-align: right; color: #888; }
</style>
