#!/usr/bin/env python3
"""Schreibt index.html: alle GIFs nach Typ gruppiert, Stil/Farbe umschaltbar. Nur stdlib."""
import json
import os

from motionpack import TRANSITIONS, ACCENTS, LOOPS

ROOT = os.path.dirname(os.path.abspath(__file__))
sets = sorted(d for d in os.listdir(f"{ROOT}/gif") if os.path.isdir(f"{ROOT}/gif/{d}"))
groups = {"Transitions · Frame 10 = voll bedeckt": list(TRANSITIONS),
          "Akzente · Beat-Hits": list(ACCENTS), "Loops · Hintergründe, nahtlos": list(LOOPS)}

html = """<!doctype html><html lang="de"><head><meta charset="utf-8"><title>SPARK Motion Pack</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0b0b0b;--fg:#f2efe6;--mut:#8a877f;--line:#262626;--acc:#1A3A6E}
@media (prefers-color-scheme:light){:root{--bg:#f2efe6;--fg:#141414;--mut:#6b675e;--line:#d8d3c6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 ui-monospace,Menlo,monospace;padding:24px 16px}
h1{font-size:28px;margin:0 0 4px;letter-spacing:-.02em}p{color:var(--mut);margin:0 0 20px;max-width:70ch}
nav{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:24px;position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:1}
button{font:inherit;background:none;color:var(--fg);border:1px solid var(--line);padding:6px 12px;cursor:pointer}
button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
h2{font-size:15px;font-weight:600;margin:32px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px}
figure{margin:0}img{width:100%;aspect-ratio:1;display:block;background:#000;image-rendering:pixelated}
figcaption{margin-top:6px;font-size:12px;color:var(--mut);word-break:break-all}
</style></head><body>
<h1>SPARK Motion Pack</h1>
<p>Prozedurale Transitions, Beat-Akzente und Loops. Diese GIFs sind nur die Vorschau. Die ProRes-4444-Dateien mit Alpha liegen in <code>mov_alpha/</code>,
die fertig eingefärbten Loops in <code>mp4/</code>. Mehr steht in README.md.</p>
<nav id="nav"></nav><main id="main"></main>
<script>
const SETS=__SETS__, GROUPS=__GROUPS__;
let cur=SETS.includes("dots")?"dots":SETS[0];
try{cur=localStorage.getItem("set")||cur}catch(e){}
function draw(){
  document.getElementById("nav").innerHTML=SETS.map(s=>`<button aria-pressed="${s===cur}" data-s="${s}">${s.replace("color_","")}</button>`).join("");
  document.getElementById("main").innerHTML=Object.entries(GROUPS).map(([g,names])=>
    `<h2>${g}</h2><div class="grid">`+names.map(n=>`<figure><img loading="lazy" src="gif/${cur}/${n}.gif" alt="${n}" onerror="this.parentNode.remove()"><figcaption>${n}</figcaption></figure>`).join("")+`</div>`).join("");
}
document.getElementById("nav").onclick=e=>{const s=e.target.dataset.s;if(!s)return;cur=s;try{localStorage.setItem("set",s)}catch(e){};draw()};
if(!SETS.includes(cur))cur=SETS[0];draw();
</script></body></html>"""
html = html.replace("__SETS__", json.dumps(sets)).replace("__GROUPS__", json.dumps(groups, ensure_ascii=False))
open(f"{ROOT}/index.html", "w", encoding="utf-8").write(html)
print(f"{ROOT}/index.html", sets)
