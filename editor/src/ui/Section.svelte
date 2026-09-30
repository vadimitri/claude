<script lang="ts">
  import type { Snippet } from 'svelte';
  let { title, open = true, children, extra }: { title: string; open?: boolean; children: Snippet; extra?: Snippet } = $props();
  let o = $state(open);
</script>

<section>
  <header>
    <button class="t" onclick={() => (o = !o)}><span class="car" class:o>▸</span>{title}</button>
    {@render extra?.()}
  </header>
  {#if o}<div class="body">{@render children()}</div>{/if}
</section>

<style>
  section { border-bottom: 1px solid #444; padding: 4px 0 8px; }
  header { display: flex; align-items: center; height: 32px; padding: 0 8px 0 4px; }
  .t { flex: 1; text-align: left; background: none; border: 0; color: #eee; font: 600 11px Inter, system-ui, sans-serif; cursor: pointer; display: flex; gap: 4px; align-items: center; }
  .car { display: inline-block; width: 12px; color: #999; transition: transform .1s; }
  .car.o { transform: rotate(90deg); }
  .body { padding: 0 12px 0 16px; }
</style>
