# Spark in Resolve · eine Seite

**Prinzip:** Alles im Projekt ist **grau** (0 = Grund, 1 = Tinte). Die **Spark Lens** rastert und färbt es:
4-px-Zellen, Bayer 4×4, 6 Stufen einer Colorway. Gleiche Mathe wie die Figma-Lens und `styles.py`.
Colorway wechseln = ein Klick, nichts neu rendern. Text+ wird durch die Lens automatisch Pixel-Schrift.

## Start

1. Projekt **SPARK_Template** öffnen. Neues Stück: Projektmanager > Rechtsklick > *Duplicate*. Template nie direkt bearbeiten.
2. Timeline nach Kanal wählen: **Story 9x16** (1080×1920), **Post 4x5** (1080×1350), **Wide 16x9** (1920×1080). 24 fps.
   Marker = Takte bei 120 BPM (lila = jeder 4.). Schnitte auf Marker legen.
3. Spuren: V1 Grund · V2 Spark · V3 Titel · V4 Zumo · **V5 Lens** · A1 Musik · A2 SFX.

## Lens

- **Ganze Timeline (Standard):** auf V5 *Lens* liegt ein **Adjustment Clip** über die ganze Länge, darauf die Lens als
  LUT: Color page > Node > Rechtsklick > LUT > Spark > Colorways > *P-Code*. Colorway wechseln = andere LUT wählen.
  Lens aus = Adjustment Clip deaktivieren (D). Neue Länge: Adjustment Clip mitziehen.
- **Mit Reglern:** statt LUT Effects > OpenFX > ResolveFX Color > **DCTL** auf den Adjustment Clip, DCTL-Liste >
  *Spark Lens*. Regler: Colorway, Cell size (4 = Standard, 8 = gröber), Transparent ground (Grund wird durchsichtig →
  Element über Foto, nur pro Clip sinnvoll), Photo fade (Dither löst sich ins Original auf: *dither up to* < 1,
  *angle* 0 = unten).
- Geprüft 10.10.: Render aus Resolve = Python-Referenz (`kit.lens`) bei 99,999 % der Pixel, 100 % auf der Palette.
- **Fotos/Footage** ohne Pixel: Timeline-Lens aus, Lens nur auf die Grafik-Clips (Transparent ground an).
- **Stufen steuern:** Vor der Lens ist alles nur Helligkeit. Lift/Gain/Kurve am Clip verschiebt, welche Farbstufen vorkommen.
  Exakte Grauwerte k/5 (0, 51, 102, 153, 204, 255) werden flach, alles dazwischen wird Dither.
- Lila (P1 P5 P8 P12) gehört der Maker Night, bunt (P11 P17 …) dem Kick-off.

## Effekte aus dem Kick-off (alle mit Keyframes animierbar)

| Effekt | Wo | Wie |
|---|---|---|
| **Glow / Halo** (Lichtschweif von F16–F19) | ResolveFX **DCTL > Spark Glow** auf Titel, Spark oder einen Compound aus beiden, *unter* der Lens | *Centre* = Lichtquelle (z. B. Spark-Mitte), *Length* = Schweiflänge: von 0 hochkeyframen = Halo wächst (nur wachsen lassen, nie atmen), *Peak* = Helligkeit |
| **Licht in eigener Farbe** (F16: glimmend rot → weiß) | Glow-Clip **über** der Lens-Spur, darauf zusätzlich *Spark Lens* mit *Transparent ground* + eigener Colorway (z. B. P18 MOLTEN) | Szene in P1, Licht in P18: zwei Welten in einem Bild |
| **Colorway-Reise** (Spider-Verse, jedes Bild eine Welt) | *Spark Lens* (ResolveFX) auf dem Adjustment Clip, **Journey** = Bilder je Colorway (1–4), *Journey set* = alle / Maker Night / Kick-off | Achtung Flackern: groß und schnell = Blitzgefahr, kurz halten oder Journey ≥ 3 |
| **Boil** (Korn kocht wie im MN-Teaser) | *Spark Lens*, **Boil** = alle n Bilder (2 = 12 fps) | ruhige Flächen leben, ohne sich zu bewegen |
| **Glühender QR** | Bin 01 Spark: `qr_telegram.png` (dunkle Colorways), `qr_telegram_paper.png` (Papier: P8 P16 P21–P24) | nicht skalieren außer 200 %; liest in allen 22 Colorways (geprüft); neue URL: `kit.py qr <url>` |
| **Wortwand im Stern** (F19-Ende) | `wall_<wort>_<fmt>.png` über `spark_cover_<fmt>`, Composite Mode **Multiply** | neue Wörter: `kit.py wall MAKER NIGHT` |
| **Spark-Blende / dunkler Spark** | `spark_cover_<fmt>` (rückwärts = aufdecken); dunkel: Clip-Gain 0 bzw. Invert | Schnitt auf das letzte Bild der Blende = Taktmarker |
| **Nest-Tunnel** | `nest_tunnel_<fmt>` als Grund | 4-s-Loop |

## Bausteine (Media Pool)

| Bin | Was | Tipp |
|---|---|---|
| 01 Spark | `spark_spin_S2` (Verlaufsstern, 2,5-s-Loop), `spark_nest_S7` (Nest), `spark_cover_<fmt>` (Stern wächst bis bildfüllend, 0,5 s), Wortmarke, Logo | Blende endet auf dem Schnitt; rückwärts (Rechtsklick > Change Clip Speed > Reverse) = Aufdecken |
| 02 Gruende | `flow_drift`/`flow_tide` (24-s-Loop), `nest_tunnel` (4-s-Loop) je Format | Loops nahtlos: einfach hintereinander legen |
| 03 Zumo | Challenge-Szenen (Wert-Palette, Alpha), Emoji-GIFs | 12 fps Pixel-Art: nie skalieren außer ganzzahlig (200 %, 300 %) |
| 04 Sound | `hit_*`, `riser_2bar` (endet auf der Eins), `whoosh_lr`, `reverse_cymbal`, `glass_ping`, `key_click`, Drums, `chip_*` (8-Bit), `MN_loop_*` | MN-Loop + Arp nur für Maker Night |
| 05 Brand | Colorway-Bogen, Lens-Testbild | |
| 06 Footage | leer, eigene Fotos/Videos | |

## Titel

Effects > Titles > **Text+** auf V3. Font **Clash Display**, Style **Bold**, Farbe Weiß. Wortabstand doppelt (T2).
**Composite Mode: Difference** → Schrift kippt über hellem Stern in Grundfarbe (XOR-Regel, bleibt lesbar).
Kleintext: **Departure Mono** in Größe 44 oder 88 (Vielfache von 11). Kein Schatten, keine Kontur: die Lens macht den Look.

## Ton

Riser endet auf Takt-Marker, Hit genau darauf. Musik −14 LUFS: Fairlight > Loudness-Meter, Clip-Gain statisch anpassen
(kein Normalisieren über den ganzen Clip: drückt den Drop platt).

## Export

Deliver > H.264, Qualität *Best* oder 40 Mbit/s für Social (Dither frisst Bitrate). Story 9:16, Post 4:5. Dateiname
`SPARK_<Anlass>_<Format>_v01`. Endergebnis nach `~/Nextcloud/Sporga/assets/motion/out/`.

## Neue Bausteine

Claude fragen („neuer Baustein: …“), Code `src/kit.py`, Werte `kit/kit.toml`. Danach `uv run src/kit.py all && uv run
src/kit.py publish`, dann `src/kit_resolve.py` erneut (per MCP oder Workspace > Scripts): legt nur Fehlendes an,
bestehende Timelines bleiben unangetastet, setzt die Lens-LUT auf alle Clips der Spur *Lens*. Andere Colorway für alle:
`build(resolve, "P11")`.
