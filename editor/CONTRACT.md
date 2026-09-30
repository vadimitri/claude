# SPARK Poster-Editor · Vertrag zwischen den Teilen

Ziel: Plakat-Editor im Browser, **alles live auf der GPU (WebGL2)**, Look identisch zum Python-System in `../src/`
(styles.py, kickoff.py, lab_spark.py = Referenz). Nur lokal fuer Vadim. Stack: Vite + TypeScript + Svelte 5, WebGL2 roh.
Dev-Server: `cd editor && npm run dev` auf **Port 5199** (`--strictPort`). Nur der CORE-Agent startet ihn.

## Dateien und Besitz (niemand editiert fremde Dateien)
| Pfad | Besitzer |
|---|---|
| `package.json`, `vite.config.ts`, `index.html`, `test.html`, `src/render/**` | CORE |
| `src/templates/**`, `src/ui/**`, `src/App.svelte`, `src/main.ts`, `src/spec.ts` | UI |
| `src/sparks/<Code>.glsl` | je Spark-Agent nur seine Codes |
| `src/sparks/_common.glsl`, `src/data.json`, `CONTRACT.md` | Orchestrator (nur lesen) |

`src/data.json`: `prof` (Sternprofil), `pals` (Paletten dunkel->hell), `codename`, `komp` (K -> port/land (x,y,R)),
`P`/`K` (Code -> Name), `alt2` (Zweitpalette), `kick_pals` (Kick-off: ohne Lila), `roster`, `own`, `own_k`, `frag`,
`secret`, `f_lo`/`f_hi`, `sizes`, `qr_url`, `copy_mn`, `copy_kick`. Fonts: `public/fonts/` (ClashDisplay-Variable Bold, DepartureMono).

## Spark-Shader
Datei `src/sparks/S7.glsl` definiert genau `vec4 spark_S7(vec2 p)`. Der Renderer sammelt alle Dateien per
`import.meta.glob('../sparks/*.glsl', {query: '?raw', eager: true})`, haengt `_common.glsl` davor und baut einen Switch
ueber `uniform int uSpark`. Hilfsfunktionen im eigenen File mit Code-Praefix (`S31_rays`), sonst Namenskollision.
- `p` = Zellmitte in m-Einheiten (m = kurze Seite), y nach unten. Alles aus `_common.glsl` ist verfuegbar
  (`uStar` = x0, y0, R, rot; `star_r`, `sd`, `star`, `starMain`, `bg`, `fbm`, `titleMask`, `textMask`, `uTitleBox`, `uCell`, `tall()`).
- Rueckgabe `vec4(v, lit, v2, a2)`:
  - `v` Wert 0..1 (0 = Grund, 1 = hellste Tinte). `v < 0` = transparent, Seitenhintergrund (styles.background) scheint durch
    (so arbeiten S2/S7/S33: nur im Stern deckend). Labor-Sterne liefern meist das ganze Feld inkl. `bg(p)`.
  - `lit` 1 = leuchtender Stern (Schrift kippt dort ins Negativ, XOR-Regel = `c.star_m` / `g.lit`).
  - `v2, a2`: Zweitlicht (S31c): wo `a2 > 0.5`, gilt `v2` in der Zweitpalette `alt2[P]` (ausserhalb der Schrift).
- Platzierung immer aus `uStar` (entspricht `g.pos(...)`/`g.ro(...)` im Python; Python-Default nur, wenn Code zu OWN gehoert
  und der Editor keine Position gesetzt hat -> dann setzt der Editor uStar auf `own_k` bzw. den Python-Default, den der
  Spark-Agent als Kommentar `// default: x0 y0 R rot` in die erste Zeile seiner Datei schreibt).
  Formatabhaengig: `// default:` gilt hochkant, optional folgt `// default-wide: x0 y0 R rot` fuer quer (fehlt sie, gilt
  `default` fuer beide). x0/y0 duerfen seitenrelativ sein: `0.5A` = 0.5 * uPage.x, `0.63B` = 0.63 * uPage.y; reine Zahlen
  = m-Einheiten. `Tx`/`Ty` = Mitte von titleBox (m), jedes Token mit optionalem Offset in m (`Tx Ty+0.016 0.2177 14`).
  Aufloesung per `sparkDefault(code, [A, B], titleBox)` aus `src/render/renderer.ts` (Harness und Editor nutzen sie;
  ohne titleBox gilt die Seitenmitte als Titelmitte; Harness: `&tb=x0,y0,x1,y1`).
- Noise ist nicht bitgleich zu numpy: gleicher Charakter reicht. Formen, Proportionen, Stufen muessen stimmen.
- Kein Multi-Pass: alles in einem Fragment. Schwere Sachen (Reaktionsdiffusion, Attraktor) als Approximation im Fragment.

## Szene (UI -> CORE)
```ts
// src/render/types.ts (CORE legt an, UI importiert)
export type Scene = {
  gw: number; gh: number;              // Zellraster
  W: number; H: number;                // Seite in Displaypixeln bei Export (A3 3504x4956, 9x16 1080x1920, 16x9 1920x1080, ...)
  cellPx: number;                      // Displaypixel pro Zelle beim Export (= R*u: 4 bei 1080p, 12 bei A3)
  pal: string[];                       // Palette dunkel->hell (data.pals[name])
  alt?: string[];                      // Zweitpalette fuer a2
  spark: string;                       // "S7"
  star: [number, number, number, number]; // x0, y0, R in m-Einheiten, rot Grad
  seed: number;
  titleMask: Uint8Array; textMask: Uint8Array;  // gw*gh, 0/1, Zeile fuer Zeile von oben
  titleBox: [number, number, number, number];   // m-Einheiten
  typeV: Float32Array;                 // gw*gh, Schriftwert 0..1 oder NaN = keine Schrift (inkl. CTA-Kasten in lvl(0))
  typeFlip: Uint8Array;                // 0 = nie kippen (CTA), 1 = pro Zelle kippen wo lit (Titel), 2 = pro Glyphe (Mehrheit, Kleintext)
  glyphId: Uint16Array;                // fuer typeFlip 2: Glyphen-Nummer (0 = keine)
  qr: { x: number; y: number; n: number; modules: Uint8Array } | null; // Platte in Zellen (links oben, Kantenlaenge n inkl. 3 Module Rand, Modul = 2 Zellen)
  glow: boolean;                       // Sternglow im Seitenhintergrund (styles.background)
};
```
Komposition (CORE, Reihenfolge wie Python): Seitenhintergrund (Verlauf + Nebel + Glow um uStar) -> Spark v (wenn >= 0) ->
Zweitlicht -> QR (Halo exp(-dist/2.6) Richtung hellste Stufe bis 10 Module, Platte diagonaler Verlauf zwischen hellster
und Nachbarstufe (amt 0.55, bei dunkler Nachbarstufe 0), Module in dunkelster Stufe; siehe kickoff.qr) -> Schrift
(Flip: lvl(0)) -> Bayer 4x4 (styles.dither, exakt) -> Palette -> nearest-Upscale. `lvl(k) = k/N`.
