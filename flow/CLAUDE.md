# Spark Flow

**Vision:** ein ruhiger, lebendiger Verlauf als Hintergrund für alles (Deck, Screens, Videos). Er fließt langsam, und die
Spark Lens dithert ihn (Bayer 4x4, Zellraster, 6 Colorway-Stufen). Vadim 7.10.: „lively, aber calm und cool“.

## Wo
- **Figma:** Shader-Fill `Spark Flow` (Account-Library, id `b039441a-b758-44ef-9171-59f70e1e9029`, v `b10f234`).
  Liefert nur Grau, Farbe kommt von der Lens darüber.
  - Komponente `Gradient/Flow` (Varianten Drift, Tide): in `Spark_Design` auf der Seite Components, mit Beispielen in der Lens.
  - Im `Spark Deck` liegt sie auf einer übersprungenen Template-Slide „Flow“.
  - Jede Deck-Slide hat ganz unten einen gesperrten `Background · lens` mit Range high 0.4.
- **Video:** `src/flow.py` + `flow/flow.toml`, Ausgabe `flow/out/<name>.mp4` (+ ProRes `.mov`), Vorschau flach in `Vorschau/flow_*`.

## Entscheidungen (mit Befund)
- **Gewählt:** F1 Drift + F4 Tide (Vadim 7.10.). F2 Glow wirkte wie eine Lavalampe, F3 Dusk wurde nicht gewählt.
- **Mathe:** eine Formel, zweimal geschrieben (WGSL im Shader, numpy hier). Gegen echte WebGPU geprüft (Deno): Abweichung
  ≤ 0,002 (< ½ Graustufe). Alle Zeitterme sind ganzzahlige Vielfache von 2π·t/loop, daher ist die Naht exakt (roh:
  Schritt 719→0 = 0,340, wie jeder andere Schritt).
- **Ruhe:** pro Bild wechseln 0,4–1,5 % der Zellen die Stufe (24-s-Loop).
- **Video kommt von hier:** Figmas Server-Export (`export_video`) rendert eigene Shader nicht (7.10.: mit Lens schwarz,
  ohne Lens weiß, ein Kontroll-Rechteck bewegt sich). Ein Keyframe auf `phase` hilft nicht.
- **Farbraum:** Der Shader kodiert Grau wie die Lens (sRGB; bei srgb-/float-Zielen linearisiert), sonst lägen die Werte
  neben `value/k`.
- **Paletten in Figma:** Pro Collection sind nur 10 Modi erlaubt. Deshalb wählt `Colorway` die Familie
  (Night/Dark/Paper/Retro/Custom), `Colorway · <Familie>` die Palette, alle 22 + Custom-Slots.

## Offen
- Live-Animation im Präsentiermodus von Figma Slides selbst ansehen (per MCP nicht prüfbar).
- H.264-Loop: der Sprung letztes → erstes Bild ist im mp4 1,13 (normal ≤ 0,83). Grund: Encoder (I-Frame), nicht das Feld.
  ProRes 0,63. Bei Bedarf `-g`/closed GOP.
