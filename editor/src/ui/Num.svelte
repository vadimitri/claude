<script lang="ts">
  // Figma-Zahlenfeld: Label ziehen = scrubben, Shift = 10x
  import { st } from './store.svelte';
  let { label, value, step = 0.01, digits = 3, min = -Infinity, max = Infinity, set }:
    { label: string; value: number; step?: number; digits?: number; min?: number; max?: number; set: (v: number) => void } = $props();
  let x0 = 0, v0 = 0, on = false;
  const clamp = (v: number) => Math.min(max, Math.max(min, v));
  function down(e: PointerEvent) {
    on = true; x0 = e.clientX; v0 = value;
    st.checkpoint();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }
  function move(e: PointerEvent) {
    if (!on) return;
    set(clamp(+(v0 + (e.clientX - x0) * step * (e.shiftKey ? 10 : 1)).toFixed(digits)));
  }
</script>

<label class="num">
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <span class="lab" onpointerdown={down} onpointermove={move} onpointerup={() => (on = false)}>{label}</span>
  <input type="number" step={step} value={+value.toFixed(digits)} onfocus={() => st.checkpoint()}
    oninput={(e) => { const v = parseFloat(e.currentTarget.value); if (!Number.isNaN(v)) set(clamp(v)); }}
    onkeydown={(e) => e.stopPropagation()} />
</label>

<style>
  .num { display: flex; align-items: center; height: 28px; border: 1px solid transparent; border-radius: 2px; }
  .num:hover { border-color: #444; }
  .num:focus-within { border-color: #0d99ff; }
  .lab { width: 24px; text-align: center; color: #999; cursor: ew-resize; flex: none; }
  input { width: 100%; min-width: 0; background: none; border: 0; color: #eee; font: inherit; outline: none; -moz-appearance: textfield; }
  input::-webkit-inner-spin-button { display: none; }
</style>
