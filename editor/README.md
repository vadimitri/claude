# SPARK Poster-Editor

`cd editor && npm install && npm run dev -- --port 5199 --strictPort` → http://localhost:5199 (nur lokal).
Figma-artig: links Plakate/Ebenen/Balance, Mitte Leinwand (Stern ziehen, Ecken = Groesse, Griff = Drehung, Space+Drag = Pan,
Cmd+Rad = Zoom), rechts Design-Inspector. Pfeile = Stern verschieben (Shift x10), R = drehen, Cmd+D/Z, Varianten, Auffuellen,
Export PNG in voller Aufloesung, "Alle exportieren" in einen Ordner. Vertrag zwischen Renderer, UI und Sternen: `CONTRACT.md`.
Python in `../src/` bleibt die Referenz fuer Look und QR-Check.


## Renderer

Starten: `cd editor && npm install && npm run dev -- --port 5199 --strictPort` → Editor `http://localhost:5199/`,
Paritaets-Harness `http://localhost:5199/test.html?spark=S7&pal=lav&fmt=16x9` (optional `x y R rot` in m-Einheiten,
`seed`, `glow=0`). Der Harness rendert einen Spark ohne Schrift/QR, Stern per Default wie KOMP `riese`
(OWN-Codes: `own_k` bzw. `// default:`-Zeile), zeigt ms/Frame, Compile-Fehler (`<pre id=err>`, Console) und Links zu allen Sparks/Paletten.

Aufbau (`src/render/`):
- `types.ts` – `Scene` (Vertrag, siehe CONTRACT.md). `qr.modules` = qn x qn, Zeilen von oben, qn = (n - 12) / 2.
- `renderer.ts` – `new Renderer(canvas)`, `render(scene)` (Canvas = Zellraster gw x gh, Anzeige per CSS
  `image-rendering: pixelated`), `exportPNG(scene)` (W x H, nearest-Upscale um cellPx), `sparkCodes()`, `sparkDefault(code)`, `errors`.
- Shader: `_common.glsl` + alle `src/sparks/*.glsl` (import.meta.glob) + generierter `if (uSpark == i)`-Verteiler.
  Jeder Spark wird erst einzeln testkompiliert; kaputte fliegen raus (`renderer.errors`), Rueckfall = S2-Verlauf.
  Identifier mit `__` sind in GLSL reserviert.
- Pass 1 (RGBA32F-FBO): styles.background (Verlauf, fbm-Nebel, Glow) → Spark v (wenn >= 0) → kickoff.qr (Halo, Platte, Module)
  → Ausgabe (V, lit, v2, a2). Bei Kleintext (typeFlip 2) wird das FBO zurueckgelesen und pro Glyphe die Mehrheit
  (lit oder V > 0.5) in JS bestimmt.
- Pass 2: Schrift (Flip → lvl(0)), sonst Zweitlicht (a2 > 0.5, eigene Palette), sonst V → Bayer 4x4 exakt wie styles.dither → Palette.
