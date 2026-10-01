# Kick-off Loop · SPARK Kick-off 14.10., 17:00

Session-Start: diese Datei, dann `uv run src/kickoff_loop.py sheet` (zeigt den Stand in ~10 s). Stellschrauben: `loop.toml`.
Regeln fürs Pack: `../CLAUDE.md`. **Vor Vorschlägen** `ENTSCHEIDUNGEN.md` (Befunde, Verworfenes, Archiv) und Skill `spark-motion`.

## Stand 3.10. (Vadims Urteil zu N1/G1/S58/S60, Hintergrund-Inseln)

- **In `loop.toml`:** N1 übernommen (Welt 2 eigene Sternfolge). **S45 raus** („öde“), **S48c → S48e** (Poly-Glitch G1;
  G2/S48f geparkt), **S58 → S58b**, **S60 → S60d**. Die frei gewordenen S45-Plätze: W1 F20 S58b, W1 F24 S60d, W2 F20 S59
  (Vorschlag, Vadim kann tauschen). Bögen `previz/now/`.
- **S58b/S58c ohne Rand** (Vadim: „One-Pixel-Border an manchen Stellen“). Befund: die helle Kante `TUN_RIM` (1.5 Zellen,
  Stufe 4.6) zerfiel im Korn zu einzelnen hellen Pixeln, dazu kippte der Schein außen Randzellen. `TUN_RIM_CELLS` je Code,
  b/c = 0. S58 bleibt unverändert (Archiv bitgleich).
- **S60d** = S60 ohne Pfütze (Sprühwolke) und ohne Lücke (die dunkle, versetzte Outline las sich auf dunklem Grund als
  Grund, „wie ein Stencil“); das helle gesprühte Halo setzt direkt an der Füllung an. Lesbarkeit min 0.82 statt 0.71 (S60).
  Vergleich `previz/review/S58b_S60d/`. S60b/c: „beschissener“, nicht gewählt.
- **Hintergrund-Inseln I1–I4** (`previz/review/I*/`, je nur `[ground]`): `styles.ground_shape` ersetzt den linearen Verlauf
  in `styles.background` und `lab_spark.bg` (alle Labor-Sterne). Metaballs, wandern pro Umlauf einen Kreis (Loop nahtlos).
  I1 weich, I2 Terrassen (3 Höhenstufen), I3 organisch (wellige Küste, 2 Stufen), I4 Archipel (14 klein, steht still).
  Ohne `[ground]` bitgleich wie vorher (Cache-Schlüssel unverändert). Blanker Grund im Vergleich:
  `uv run src/kickoff_loop.py grounds kickoff_loop/previz/review/I{1,2,3,4}/I*.toml` → `previz/variants/grounds.png`.
  Befund: `gain` 2.5–3 hob den Grund 2 Stufen (P41 flächig Magenta, Split-Frames liefen in die zweite Colorway) → 1.6–2.0.
  Lesbarkeit unverändert (Mittel 0.806–0.808 gegen 0.807).
- **Lesbarkeit min 0.38** = Plakat 43 (W2 F11, S24), stand schon in N1 so (die 0.60 unten sind veraltet). Vadim 3.10.:
  „menschlich easy lesbar“ → kein Handlungsbedarf; das Gate 0.95 ist für die Sterne mit Effekten im Titel zu streng.
- **Approved 3.10.:** S48e, S58b, S60d, S59b (= S59 ohne Pinselschlaufe/Schein, Kleckse gleich: Zufall wird gezogen,
  nicht gemalt). Belegung der S45-Plätze bleibt (Vadim meldet sich, sonst gilt sie). Keine Rückfrage zu diesen mehr.
- **Hintergrund, Runde 2** (Vadim zu I1–I4: „Mix aus I1 und I3, harte Landmassen, aber mehr Stufen, eher ein Gradient, der
  flowy ist, 8-Bit, pixelated, toSquares“): `[ground].mode = "flow"` = schräger Verlauf, von `waves` Wellen quer verbogen
  (laufen `flow_per_loop` Perioden pro Umlauf, nahtlos), `terraces` harte Stufen, `blocks_cells` grobe Quadrate,
  `islands` > 0 mischt Inseln dazu. **I5** Fluss 6 Stufen · **I6** + 4er-Quadrate · **I7** 8 Stufen, 8er-Quadrate,
  4 Wellen (am meisten 8-Bit) · **I8** Fluss + 4 Inseln, 4er-Quadrate. Befund: `warp_frac` 0.18 gab fast parallele
  Streifen → 0.35. I5/I6 bleiben streifiger, I7/I8 fließen. Lesbarkeit unverändert.
- **Entschieden 3.10.: Grund bleibt linear** (Vadim: Inseln/Fluss haben den 8-Bit-Dither-Flair verloren, „subtil reicht“,
  I1 wäre okay). I1 → `archiv/review/geparkt/`, I2–I8 → `archiv/review/alt/`. Befund in `ENTSCHEIDUNGEN.md`.
- **Verlauf V1–V3** (Vadim 3.10.: „linear, aber mit Rain/Melt zwischen den Stufen, subtil; Gradient so ausrichten, dass er
  mit dem Loop Sinn ergibt, dunkler um den Stern bei F17 hinten“). `[ground]`: `melt_cells/_pow/_width_cells` (jede
  Zellspalte nach unten verschoben, Bayer-Matrix fest → die Dither-Konturen tropfen), `mode = "depth"` (Verlauf radial vom
  Fluchtpunkt `center = "vanish"` bzw. vom Stern `"star"`, je ferner desto radialer), `gain` (Spannweite).
  **V1** linear + Melt · **V2** Fluchtpunkt + Melt, gain 1.8 · **V3** Stern-Tiefe + Melt, gain 1.8.
  **Vadim: „wir nehmen V3“ → `[ground]` in `loop.toml`**, V1–V3 archiviert. Gilt damit auch für alle Varianten-TOMLs.
  Befunde: Melt muss auf den ganzen Grund (der Nebel in `styles.ground` macht die sichtbaren Konturen), Tropfen ~1
  Konturabstand lang (~36 Zellen) und 2 Zellen breit (1 verschwindet im Bayer). Bei gain 1 (heute: halbe Stufe) änderte
  der gedrehte Verlauf ≤ 4 % der Pixel, mit 1.8 10–14 %. Auf Papier-Frames ist Stufe 0 das Papier: dort wird es um den
  Fluchtpunkt heller (wie alles in den Negativ-Welten). Lesbarkeit/QR unverändert.
- **Enden:** Z4/Z5 → `archiv/review/alt/` (bewertet, daher die neuen), W1/W2 → `archiv/review/geparkt/` (Vadim: „Idee
  cool, erstmal parken“).
- **Agenten (3.10.):** `pipeline` (Render-Tempo: Machbarkeit + Prototyp, eigener Branch, kein Merge) und `enden`
  (neue digitale Enden laut Übergabe unten: v1 nach hinten + Zoom, Schleuder-Varianten; eigener Branch, kein Merge).

## Bahn-Enden O4, O5 (Agent `enden`, 3.10.; Vadim: nicht clean genug → Übergabe unten)

`[endcard].end_mode = "orbit"` (`kickoff_loop_end.py`, Schlüssel `orbit_*` in `[ending]`): nach dem Karussell (4 Takte T16)
läuft der Loop auf dem Bass-Boom (11.76 s) **genau einen Umlauf digital** weiter (`orbit_loops` 1, 1.96 s, 24 fps,
`KL.orbit` mit gebrochener Phase, Farbe/Stern je ganzer Phase im T16-Raster, an ganzen Phasen bitgleich zum Plakat), dann
wechselt der Stern auf `orbit_frame` die Bahn (13.72 s). `end_frame` und der Zeitpunkt folgen daraus (load setzt/prüft).
Endkarte auf den Beats danach (SPARK, KICK-OFF, Datum, QR, ~6 s stehen). Vergleich `previz/review/Vergleich_O4_O5.mp4`.
- Vadim 3.10. zu O1–O4 (je 1.1–2.6 digitale Umläufe): „ab dem Moment, wo es digital ist, nur noch EINEN Loop und dann
  zack, sonst zu teasing“. Musik-Sync zweitrangig (Padding/Sprünge macht er am Ende). **O1–O3 verworfen** (O1 Bremsen in
  F17 + Zoom aus dem Stand, O2 Schleuder seitlich, O3 zur Kamera), Code für O1 gelöscht.
- **O4** Schleuder in die Tiefe (`orbit_path = "throw"`): lässt in F14 los, Tangente rechts in die Tiefe, schrumpft rechts
  von SPARK zum Punkt (weg 14.81 s), x5/Beat, `orbit_throw_boost` 2, Drehung x5. Befund: rein exponentiell schrumpft er
  in die Tiefe mit festem Verhältnis pro Bild (wirkt gleichmäßig), daher `boost` (der Tempo-Faktor wächst selbst).
- **O5** Wurf auf die Kamera + Infinite Zoom (`"dive"`, Vadim 3.10.: „wo der Spark riesig und frontal ist, weiter in die
  eine Richtung, aber zu einem hin, mit Infinite Zoom, das Momentum da auch“): im riesigen F1 (S33) fährt die Mitte in
  ihrer Richtung weiter (läuft in `orbit_dive_drift_beats` aus), der Matrjoschka-Zoom (`zoom_spark`) startet mit dem
  Sehtempo des Loops (`orbit_dive_match` 1.25; 1.0 brach auf x0.88 ein) und wird x1.5/Beat schneller (x2 = 16 Puppen/s,
  flackert). Farbe rastet beim Wurf ein (mit Farbwechsel bildfüllend = Hypno-Ringe).
- Selbsttest `uv run src/kickoff_loop_end.py test kickoff_loop/previz/review/O5/O5.toml`: Bahn-Nachbau = `KL.orbit`, Loop
  bitgleich, Stetigkeit am Bild (Sternfläche S2 mit/ohne Stern, Radius auf ≤ 1/4 Bildbreite skaliert, sonst war der
  bildfüllende O5-Stern unmessbar), Beschleunigung monoton, kein Tempo-Einbruch beim Wechsel (Sehtempo und Drehung ≥ x0.9;
  Gegenprobe Zoom aus dem Stand x0.03), ≤ 1 digitaler Umlauf (Gegenprobe 2.5). Report: Zeile „Bahn-Check“.
- Grund V3 (Tasche um den Stern): ist der Stern weg, bleibt `c.L["star"]` dort, wo er wäre (`ghost`), sonst sprang die
  Tasche in die Ecke und der ganze Grund wurde hell. `qr_scan`: OpenCV-Abbruch auf Zoom-Bildern gilt als nicht lesbar,
  gleiche Bilder nur einmal (zwei Threads schrieben dieselbe Merk-Datei).
- **Endfarbe offen, Vadim mochte Blau.** Sie folgt heute aus der Phase beim Stopp des Farbwechsels
  (`orbit_cycle_beats`): O5 Navy (Plakat 1, ~P23/P13), O4 Dunkelrot (Plakat 62, P9). Kein eigener Schalter.

## Übergabe → nächste Session: Ende absolut clean und flüssig (Stand 3.10., abends)

**Auftrag (Vadim 3.10. zu O4/O5):** „Beide Versionen ergeben logisch und physisch nicht wirklich Sinn und haben zu wenig
Schwung. Sie fühlen sich disconnected zum Loop an. **O4** stoppt irgendwie kurz, bewegt sich und dann nach hinten weiter, das
ist keine flüssige Linie. **O5** kommt zu einem, schießt dann ein bisschen über, korrigiert und zoomt dann rein. Das muss
**absolut clean und flüssig** sein.“ Neue Session nur dafür. Ausgang: `previz/review/O4/`, `O5/` (+ `Vergleich_O4_O5.mp4`),
Code `src/kickoff_loop_end.py` (`end_mode = "orbit"`, `orbit_*`, Abschnitt „Bahn-Enden O4, O5“ oben). O1–O3 verworfen.

**Feste Vorgaben** (Vadim 3.10.): ab dem Wechsel ins Digitale **genau ein Umlauf**, dann die neue Bahn und weg („sonst zu
teasing“). Musik-Sync zweitrangig (Padding/Sprünge macht Vadim am Ende). Richtung O4 (in die Tiefe) bzw. O5 (auf die Kamera
im riesigen frontalen F1, dann Infinite Zoom mit dem Momentum) ist gewollt, nur die Ausführung nicht. Endfarbe offen, Vadim
mochte Blau. Vorschauen mit Hardware-Encoder, Tempo vor Qualität.

**Hypothesen zur Ursache** (aus Code/TOML, noch nicht am Bild gemessen):
- O5: `orbit_dive_drift_beats` 0.1 → die Mitte läuft in ~70 ms aus (bremst nach 2–3 Bildern hart), der Zoom (`zoom_spark`)
  übernimmt um eine eigene Mitte: liest sich als Überschießen + Korrigieren. Dazu verweilt B20c vorn (`front_dwell_frac`
  0.6): am Wurfpunkt F1 ist die Bahn fast still, „weiterfliegen“ hat kaum Schwung zum Übernehmen.
- O4: Loslassen auf F14, wo B20c hinter dem Titel kriecht (Befund 2.10.: 0.08/Frame gegen 0.26 an den Seiten), danach x5/Beat
  + `boost`: Stopp → Anfahren. Die Tangente ist im Raum gerade, im Bild biegt sie perspektivisch ab (keine gerade Linie).
- **O5-Zoom (Vadim 3.10., nachgeschoben): „der Zoom bei O5 ist kein richtiger Zoom und hat nicht das Momentum!!!“**
  Vermutung: `zoom_spark` + `orbit_dive_core_shrink` lässt innen neue Puppen aufgehen (Ringe wandern nach außen, eher
  Palette-Cycling/Hypno als Kamerafahrt), das Tempo ist auf x1.5/Beat gedeckelt, weil schnellere Ringe flackerten (x2 = 16
  Puppen/s). Gefordert: **echter Kamera-Zoom** – das Bild selbst (Stern samt Korn/Effekten, Satz fällt weg) skaliert um die
  weiterfliegende Sternmitte, Maßstab wächst exponentiell und **beschleunigt** (d ln s/dt steigt), Startrate = Größenrate
  des Sterns im Wurf. Gegen Flackern nicht bremsen, sondern das Detail anpassen (Selbstähnlichkeit der Matrjoschka als
  Endlos-Zoom: nach einer Puppe Faktor 1/0.64 nahtlos zurücksetzen, so bleibt die Zoomrate frei wählbar) bzw. Bewegungs-
  unschärfe/Smear im Korn auf den schnellsten Bildern. Messung: Maßstab pro Bild aus dem Bild selbst (z. B. Phasenkorrelation
  log-polar), muss monoton beschleunigen; Gegenprobe heutiger O5 schlägt an.
- Der bisherige Selbsttest misst nur Größensprung und Tempo-Verhältnis am Wechsel, **nicht Richtungsumkehr und Bremsen
  danach** – deshalb grün trotz Überschießen.

**Maßstab „clean“** (zuerst als Messung bauen, die an O4/O5 heute **anschlägt**, dann erst neu bauen): pro Bild im Bild-
raum Geschwindigkeitsvektor der Sternmitte, d(ln Radius)/dt und Drehrate, über den ganzen Digitalteil.
- stetig am Wechsel: Betrag und Richtung (Winkel < ~10°) wie der Schritt davor, kein Knick;
- danach **nie langsamer** (jede Größe monoton steigend bis zum Verschwinden/Zudecken), **keine Umkehr** der Richtung
  (Skalarprodukt aufeinanderfolgender Schritte > 0), Krümmung glatt (zweite Ableitung ohne Vorzeichensprung);
- Zoom-Mitte = weitergerechnete Sternmitte (keine zweite Mitte, auf die zugesteuert wird).

**Wie bauen** (Vorschlag): Release-Zustand aus `KL.orbit` per Differenzen nehmen (Lage, Geschwindigkeit, ln-Radius-Rate,
Drehrate im Bildraum) und **eine** analytische Fortsetzung rechnen, die nur beschleunigt (konstanter bzw. wachsender Ruck
entlang der bestehenden Richtung, kein Ausklingen, kein Blend auf ein Ziel). Wurfpunkt dort wählen, wo die Bahn **schnell**
ist (Bahngeschwindigkeit je Frame aus `orbit` tabellieren), oder die Bahn im letzten Umlauf in den Wurf hinein beschleunigen
lassen statt danach. O5: Zoom-Rate stetig aus der Größenrate des Sterns übernehmen, Mitte driftet mit dem Tempo weiter und
wird nicht zurückgeholt. Erst Kurven plotten (Bahn + Tempo-Graph je Bild, wie `orbit.png`), selbst prüfen, dann `--draft`,
dann Bildstreifen ansehen, dann Vadim.

**Sonst Stand:** Hauptversion `previz/v022/` (Zyklus 3.10., S59b, Grund V3, altes Ende). Render-Pipeline: Agent `pipeline`
(Hardware-Encoder für alle Vorschauen, Foto-Phase als Video-Segment im Cache, Digitalteil streamen, QR-Prüfung früh
abbrechen; bitgleich) – Merge-Stand siehe Git-Log. **Platte:** keine Rohvideos schreiben, `df -h` prüfen.

## Stand 2.10. (Abend)

- **Offen zum Ansehen** in `previz/review/<Code>/` (je Ordner: TOML, `preview.mp4`, `loop.mp4`, Bögen, `report.txt`);
  Übersicht: `previz/index.html`. Alles Alte/Entschiedene: `previz/archiv/` (v001–v020, `review/alt|geparkt/<Code>/`).
  - **Ausstiege** (`src/kickoff_loop_end.py`, `[ending]`), alle auf IGOR **ungeschnitten** ab 22.435 s (Vadim: M3-Schnitt
    „nicht smooth“, die Musik schneidet er später selbst). IGOR-Ereignisse ab Videoanfang: Takt 5 = 11.76 s Bass-Boom,
    19.85 s Stopp (1 Beat Stille), 20.59 s stärkster Hit, 23.53 s B-Teil.
    - **Z4** Auslauf + Zoom: 2 Takte T16, 1 Umlauf bremst ab wie ein Glücksrad (kubisch, Anfangstempo = T16), landet auf
      F1 auf dem Boom, Kamera bremst mit; Zoom aus dem Stand (ease_in), Schwarz auf IGORs Stopp.
    - **Z5** Zoom + Endkarte: Zoom bremst ab, dimmt ab Takt 7 im Korn; SPARK fällt, KICK-OFF/Datum gleiten ein, Stille,
      QR springt auf dem Hit aus der Mitte auf (Ease-out-back), QR groß (4 Zellen/Modul) mittig, steht bis Takt 10.
    - **W1** Begriffe: Loop endet auf F17 (ganz hinten), Stern fährt in den Fluchtpunkt, Begriffswände (HARDWARE × 17
      untereinander) fliegen je Beat heran (Sigmoid im log. Maßstab), alte stürzt vorbei, XOR, je Begriff nächste Colorway.
      Begriffe sind **Vorschlag** (`words`), Vadim ersetzt.
    - **W2** = W1 + Endkarte fliegt als letzte Wand heran, QR auf dem Hit.
    - Vadim zu Z4/Z5: „das Ende muss das Momentum vom Loop matchen“, Text „mit Dither-Effekt mit Difference-Layer, kein
      langer Fade, auf den Beat war cool“ → **Z6–Z9 (verworfen, gelöscht)** (`zoom_dolls_per_beat` = Anfangstempo 3 Puppen/Beat, Drehung übernimmt
      den Karussell-Spin; `zoom_step_per_bar` 48 = rastet im T16-Raster; `card_reveal` bayer|blocks|noise, `card_diff`):
      Z6 linear fließend + Bayer, Z7 linear T16 + Blöcke, Z8 bremst fließend + Rauschen, Z9 bremst T16 + Bayer.
      Befund: QR überall lesbar (letzte 5.5–5.8 s), Karten-Lesbarkeit mit Difference 0.66–0.71 (C) statt 0.98 mit
      Abdimmen (Z5); Zoom-Check bei schnellem Zoom blind (Gegenprobe < x3), Sprünge keine (max x1.1–1.6 des Medians).
    - Z4 v1 war kaputt (Landung fiel auf den Zoom-Start, F1 nie als Plakat, Sprung x5.8); v2 hält F1 2 Beats.
  - **N1**: Welt 2 eigene Sternfolge mit den neuen Spider-Verse-Sternen **S56** Neonblasen, **S57/S57b** Collage, **S58**
    Tunnel, **S59** Impact-Spritzer, **S60** Graffiti (Bögen + Referenzvergleich `review/S56/`). Welt 1 unverändert.
  - **G1/G2** Poly-Glitch statt S48c (F21, F29): S48e Dreiecks-Scherben (Nachfolger), S48f Glasbruch/Facetten.
    `G1/bahn_S48c_e_f_gross.png` = Vergleich groß.
- **In `loop.toml` seit 2.10. abends:** S54c auf F12/F16/F25 („Vundzwanzig“ als 25 gelesen), S50 auf F15 (S13, S2 damit
  nicht mehr im Loop); **Farbwelt 2** mit den reinen Plakat-Colorways (Tokyo = Afterhours P25, Molten P18, Red Laser P9,
  Absolute Zero P23, Mode 04H P6 **mit** Magenta: `lilac_ok`, Vadim: „fällt nicht unter die Lila-Regel“) → 64 Plakate;
  **SPARK zeigt die Effekte dahinter** invertiert (`title_value`, lokaler Grund), außer F13 (`title_plain_frames`).
  Endet noch mit dem alten Ende (Mashup A); wenn Vadim einen Ausstieg wählt: dessen `[ending]` + `[endcard]` nach `loop.toml`.

Der **Video-Loop ist von den Campus-Plakaten getrennt**, soll aber so aussehen, dass man die Frames als Plakate nutzen
könnte (Vadim 2.10.).

In `loop.toml` steht, was Vadim gewählt hat:
- **Bahn B20c**: Die Ellipse liegt ganz vor dem Betrachter (`ahead` 1.3 > 1), es gibt keine leeren Frames.
  - F1 zentral und riesig, dann links, kleiner und hoch hinter SPARK, rechts zurück.
  - `front_dwell_frac` 0.6: Der Stern verweilt vorn. `size` 0.85.
  - Vadim: „ehrlich echt nicht schlecht", weiter damit.
- **Tempo T16**: 16.32 Plakate/s = 32tel-Triolen auf IGOR (81.6 BPM) = **48** Wechsel pro Takt (`[loop].changes_per_bar`).
  Steht im Code. Jedes Vorschau-Video hat Ton.
- Die **Kamera-Stöße auf den Beats sind aus** (`[video].punch_frac` 0, Vadim: „diese kleinen Beat-Crop-ins weg").
- Der **Blitz-Check ist aus** (`[checks].flash_gate` false, Vadim: „Farben dürfen crazy gehen").
- **Farbe**: noch C1 als Platzhalter. Vadim mag die extrem bunten C4/C5, siehe unten.

Offen (Varianten liegen in `review/alt/` bzw. `geparkt/`, `review/` selbst ist leer bis auf `S_rework_3.png`):
- **Farbe auf B20c**, jeweils `<Code>_B20c.toml` + `_preview.mp4` (volles Video, vNNN):
  - C1, C1b–d (Vadim: „keinen Unterschied"), C4, C5, C6.
  - **C4b/C4c, C5b/C5c** (2.10.): dieselben Stationen wie C4/C5, umsortiert in Hell-Dunkel-Blöcke (b à 16, c à 8),
    innerhalb nach Farbton.
    - Vadim zu C4/C5: „zu viele Invertierungen, zu hoher Kontrast zwischen zwei Frames, bunter Grund neben schwarzem".
    - Befund am fertigen Bild (mittlere OKLab-Helligkeit je Frame, Sprung > 0.25 pro Loop): C4 29, C5 27 → C4b 3,
      C5b 3, C4c 5. Der Grund ist zweigeteilt (L 0.10–0.31 oder 0.92–1.00). Auf B20c macht der Riesenstern F1–4/F29–32
      hell, auch bei dunklem Grund. Messskript noch nicht im Report (Kandidat für `sheet_report`).
    - Weicher ginge es nur mit Grund-Stufen in der Mitte (dunkle Gründe anheben bzw. helle absenken), noch nicht gebaut.
- `geparkt/`: B19 (Ellipse um den Kopf) und B20d–g mit `screen_frac` (gleicher sichtbarer Weg pro Frame) bzw.
  `ends_dwell_frac` (Posen halten).
  - B20g sieht aus wie die Plakate: nah unten groß, Titel frei.
  - Vergleichsvideo `Vergleich_B20c_B20d_B20e_B20f_B20g.mp4`.
  - Befund zum Timing von B20c: Hinter dem Titel kriecht der Stern 0.08/Frame, an den Seiten 0.26, F1–4 sind nur Farbfläche.
- **Musik schneidet Vadim selbst** (2.10.: „das mit der Musik klappt nicht, gib mir ne DaVinci-Timeline"): `schnitt`, siehe Befehle.
  Video und Song starten bei Songzeit 0; gemeinsam auf Taktstrichen geschnitten bleibt der Loop synchron. M3a/M3b (16/20 s) liegen als Referenz bei.
- Musik-Verlauf: M1a/M1b (eigene Techno-Drums) verworfen: „zu ernst, zu trocken, nicht menschlich".
  - M2 läuft beim Musik-Agenten: IGORs eigene Drums, Spaß (Swing, Claps, Hook, Raum).
  - Drop = Sprung auf ~48 s im Song, wo Tyler singt (Vadim 2.10.).
- **Drop/Digital**: Vadim: „der Beatdrop muss sich lohnen, da muss nochmal was kommen".
  - Drop-Agent baut E1-Konzepte: Wand, Umstülpen, Pixel-Explosion, Dimensionssprung.
  - D1a–d (Umstülpen, `src/kickoff_loop_digital.py`) sind gemergt.
- `S_rework_3.png`: die gewählten neuen Sterne. `tempo_T16.mp4`: Tempo-Referenz.

## Nächste Schritte, in dieser Reihenfolge

1. **Sterne in den Zyklus.** S50, S48c, S48d und S54c sind gewählt, `[styles].cycle` hat aber noch die alten 8. Mit Vadim
   klären, welche raus (32 Frames = 8 Stile × `hold_frames` 4). Alles muss im Bayer-Korn liegen („unter dem Dither-Layer").
   S50 hat noch flache Flächen, das ist laut Sterne-Agent eine Zeile.
2. **Leere Frames im Code**, sonst bricht `preview`:
   - `kickoff_loop_video.digital_style` nimmt `star_at(n - 1)`. F32 ist leer (Radius 0), `1 / r0` teilt durch null.
     Ausbruch und Karussell-Ende gehören auf den **letzten Frame mit Stern**.
   - Stile nur auf Frames mit Stern verteilen; S2 (voller Körper) auf den letzten.
   - Leere Frames rendern einen winzigen S2 außerhalb (`OFF_STAR`), weil Labor-Stile am Stern messen.
   - `test` ohne Argumente bricht bei 32 Frames ab (QR-Glühen: Standardframes 3/7/9 haben den Stern am QR). `SELFTEST_FRAMES` auf freie Frames der neuen Bahn setzen.
3. **Lesbarkeit** der Riesenframes: min 0.91 (Gate 0.95), der Riesenstern liegt über SPARK/KICK-OFF. Über Bahn oder Satz lösen.
4. ~~Zeitachse T16~~ erledigt 2.10. (48 Wechsel pro Takt, Ton unter jedem Video, Blitz-Check aus).
   `test` ist wieder grün (2.10.). Der Test selbst hatte einen Fehler: `m &= level != 0` hat die Satzmasken an Ort
   und Stelle verändert, deshalb schlug „Titel steht nicht fest" auf jedem Frame mit gekippter Schrift an.
   Offen: Für Papier-Frames (C5b F17–28) gibt es noch keine Glüh-/Verlaufsregel. `test` nimmt deshalb nur Frames
   mit dunklem Grund.
5. Farbe: Urteil C4b/c, C5b/c, dann nach `loop.toml`.
6. **Musik** nur IGOR, Custom-Mashup: Wo IGORs Drums kommen, etwas Eigenes. Maker Night fliegt raus
   (`kickoff_loop_music.py`, `[mashup]`). Das Raster-Format bleibt (`GRID_KEYS`).
7. **Endkarte neu**, keine Hypno. Heute Platzhalter (Nest-Tunnel). Boil (`boil`) nur mit Vadims Ja.

**So arbeiten** (2.10. nachgeschärft, für schnelles Iterieren):
- **Gewähltes steht nur in `loop.toml`.** `previz/review/` enthält nur, was gerade offen ist, **ein Ordner pro Variante**
  (Vadim 2.10.: „MP4s und Contact-Sheets jeder Version in einem Ordner“). Nach jeder Wahl sofort aufräumen:
  Entschiedenes nach `archiv/review/alt/<Code>/`, Alternativen nach `archiv/review/geparkt/<Code>/`.
- **Nichts Freigegebenes rauswerfen.** Ein schlechter Messwert kommt in den Report, die Entscheidung trifft Vadim.
- **Varianten klein halten:** In eine Review-TOML nur den geänderten Abschnitt schreiben, `load` ergänzt den Rest aus
  `loop.toml`. So wirkt jede spätere Entscheidung automatisch auf alle offenen Varianten, und niemand muss Varianten
  neu abmischen. Name `<Code>.toml`, oben 1 Zeile, was die Variante macht und warum.
- **Vadim entscheidet an Bewegung mit Ton:**
  - `sheet <toml>` (~25 s, Bogen + Loop mit Ton) für Bahn, Farbe und Stile.
  - `preview <toml>` (ganzes Video) nur, wenn Musik oder Ende betroffen sind. Für schnelle Runden am Ende:
    `preview <toml> --draft` (Digitalteil auf Zweiern, Hardware-Encoder, Dateien `*_draft`, Report sagt DRAFT).
  - Mehrere Varianten gleichzeitig: ein `hstack`-Video. ffmpeg hat hier kein `drawtext`, deshalb steht die
    Reihenfolge im Dateinamen.
- **Befund am fertigen Bild, nicht an der Palette:** Bei B20c deckt der Riesenstern F1–4 ab, der Grund lügt dort.
  - Messen: Helligkeitssprung pro Frame (Bild-L, OKLab) und sichtbarer Weg der Sternspitzen pro Frame.
  - Die Skripte dafür liefen 2.10. noch als Wegwerfcode. Offen: als Befehl `measure` in den Report.
- **Agenten** in eigenen Worktrees mit klaren Dateigrenzen (Farbe, Bahn, Musik, Ende).
  - Auftrag beginnt mit `git reset --hard claude/kickoff-loop`, denn neue Worktrees können auf altem Stand liegen.
  - Audio ist gitignored: aus `kickoff-loop/kickoff_loop/ref/audio/` verlinken.
  - Nach dem Merge den Worktree entfernen (`git worktree remove`).
  - Vadims Zwischenrufe sofort an den zuständigen Agenten (SendMessage), nicht sammeln.
- Befund zuerst rechnen, dann rendern. Die Bahn-Suche lief als Skript über die Parameter, schneller als Bögen raten.

## Vision

- **Bumerang als Ellipse**, der Stern immer **frontal** (dreht nur in der Bildebene), Tiefe spürbar (riesig ↔ klein).
- **Farbe interdimensional**: möglichst alle Colorways, gern verrückter. Nie Lila (gehört der Maker Night).
- **Titelblock steht** (SPARK + KICK-OFF + Datum, jeder Frame gleich). **QR glüht ein**, JOIN US frei darüber.
- **Video**: Das Karussell läuft mehrmals, die Kamera zoomt, rollt und stößt auf den Hits. Am Ende **bricht der Stern
  aus** (24 fps), auf dem Drop **Impact** (Negativ), dann die Endkarte. Spider-Verse-Techniken: `ref/spiderverse/README.md`.

## Begriffe

| Begriff | Bedeutung |
|---|---|
| **Frame** | ein Bild des Loops, Nummer 1–32 |
| **Loop** / **Durchgang** | Frame 1 → 32. **Karussell** = wie der Loop im Video mehrmals abläuft (Musik-Raster) |
| **Stern** („der Spark") | die sechszackige Form. **Titel** = das Wort SPARK. **Titelblock** = SPARK + KICK-OFF + Datum |
| **Bahn** | der Weg des Sterns (`[spark]`); **leerer Frame** = Stern hinter dem Kopf |
| **Stil** (S-Code) / **Colorway** (P-Code) | wie der Stern gezeichnet ist / Palette. **Farbreise** = Colorways über den Loop, dazwischen OKLab-Mischungen |
| **Glühen** | helle QR-Platte + Lichtabfall (`qr_glow`) |
| **Ausbruch** / **Impact** / **Endkarte** | Stern fliegt auf die Kamera zu / Negativ-Frames auf dem Drop / 9:16-Satz danach |
| **B/C/T/S-Codes** | Varianten von Bahn / Farbe / Tempo / Stern in `previz/review/` |
| **Version** (v007) | ein `preview`-Lauf in `previz/vNNN/` |

## Befehle (aus dem Pack-Root)

| Befehl | Ergebnis | Dauer |
|---|---|---|
| `uv run src/kickoff_loop.py sheet [review/X/X.toml]` | Kontaktbogen + Loop-Video → `previz/now/` bzw. `previz/review/X/` (+ Report). Öffnet nichts (Vadim schaut selbst) | warm ~4 s, kalt ~15 s |
| `uv run src/kickoff_loop.py stars [S..]` | Sterne-Bogen an 3 Bahnstellen → `previz/variants/stars.png` | ~25 s |
| `uv run src/kickoff_loop.py grounds [review/I1/I1.toml ..]` | blanker Grund (ohne Stern/Satz) je Variante, erste Zeile loop.toml → `previz/variants/grounds.png` | ~3 s |
| `uv run src/kickoff_loop.py test [N..]` | Selbsttest am fertigen Bild (+ Bahn, Blitz) | ~5 s |
| `uv run --with numpy --with pillow --with scipy --with qrcode --with scikit-image --with opencv-python-headless python src/lab_spark.py test` | Selbsttest Sterne (Hand-Schraffur) | ~20 s |
| `uv run src/kickoff_loop_resolve.py schnitt` | Resolve-Projekt `SPARK_Kickoff_Schnitt`: Timeline „Schnitt" = Loop (9:16, Wechsel auf IGORs Raster, F1 auf 22.435 s) + IGOR-Song, verknüpft, 9 Marker; „Referenz" = `resolve/schnitt/ref/*`. Erneut aufrufen = neue Medien, Timeline bleibt (Resolve verlinkt neu) | ~3 min |
| `uv run src/kickoff_loop.py preview [review/X/X.toml]` | ohne Argument neue Version `previz/vNNN/`, mit Variante in ihren Ordner (Video, Bögen, Report, Config-Kopie) | warm ~30 s, kalt ~1 min |
| `uv run src/kickoff_loop.py preview review/X/X.toml --draft` | Entwurf: Digitalteil auf Zweiern, VideoToolbox-Encoder, kein Zoom-Check → `*_draft.mp4/.png`, `report_draft.txt` (Kopfzeile DRAFT) | ~20 s |
| `uv run src/kickoff_loop_end.py test review/Z4/Z4.toml` | Selbsttest Ausstiege (Auslauf bremst/landet, Kamera stetig, warp), Gegenprobe linear | ~5 s |
| `uv run src/kickoff_loop.py frames` / `variants` / `boil` / `print` / `resolve` | Frames rendern / QR-Varianten / Boil-Test / Druck-PDFs / Resolve-Bausteine | |
| `uv run src/kickoff_loop_music.py` | Musik + Raster → `ref/audio/mashup_*.wav/.json` | ~5 s |

Frames sind nach Inhalt gecacht (`_cache/`): Schlüssel = ganzes Stil-Dict + Hash nur der Quelltexte, die das Bild
bestimmen (`kickoff_loop.POSTER_SOURCES`/`DIGITAL_SOURCES` samt Importen; `test` prüft per Trace, dass nichts fehlt).
Änderungen an `kickoff_loop_video.py`, Musik, Resolve lassen den Cache stehen. QR/Lesbarkeit stehen gemerkt in
`_cache/checks/`. Ein Pool pro Lauf (`kickoff_loop.pool()`), Foto-Phase parallel je Plakat, x264 `fast` (`X264_PRESET`).

## Ordner und Code

| Pfad | Inhalt | Git |
|---|---|---|
| `loop.toml` | alle Stellschrauben, kommentiert, Einheit im Namen | ja |
| `previz/review/<Code>/` | offene Varianten: `<Code>.toml` + alles, was daraus gerendert ist | toml, report ja |
| `previz/vNNN/`, `previz/now/`, `previz/variants/` | Versionen von loop.toml / Kratzfläche / Sterne-Bögen | Reports ja |
| `previz/archiv/` | `versionen/v001…`, `review/alt|geparkt/<Code>/`, alte Musik-Hörversionen | toml, report ja |
| `ref/audio/` | `igors_theme.mp3` (nicht im Git), `igor_beats.json` (IGOR-Raster, Drums ab 22.435 s), `mashup_*.json` | teils |
| `ref/spiderverse/` | Recherche + Notizen zu allen Labor-Sternen | README ja |
| `resolve/` | `RECIPE.md`, `EDITOR.md` (Stern-Editor, Stand 16 Frames) | md ja |

`src/kickoff_loop.py`: Config, Farbreise (Welten, Split, Regenbogen), Bahn (`orbit`), Satz, QR-Glühen, Rendern, Selbsttest.
`src/kickoff_loop_video.py`: Timeline, Kamera, Ausbruch/Impact/Endkarte, Blitz-Check (inkl. Rot), sheet/preview.
`src/kickoff_loop_end.py`: Ausstiege (IGOR-Zeitachse, Auslauf, Begriffe, Endkarte, Selbsttest).
`src/kickoff_loop_music.py`: Mashup + Raster. Sterne: S2/S7/S33 in `src/styles.py`, Labor in `src/lab_spark.py` (`URTEIL`).

## Checks (stehen in jedem Report)

QR je Frame dekodiert · Titel-Lesbarkeit ≥ 0.95 (`kickoff.legible`) · Blitz ≤ 3/s auf ≤ 25 % der Fläche + Rot-Regel ·
kein Lila (auch im Korn, `load` bricht ab) · Selbsttests schlagen nachweislich am alten Fehler an.

## Offen (nach den nächsten Schritten)

- **Wahl Ausstieg** Z4/Z5/W1/W2 (Ausstiege kombinierbar: z. B. Auslauf vor W2 = `runout_bars` setzen) und **Begriffe**.
- **Wahl Glitch** G1/G2 (ersetzt S48c, Vadim: „wenn gut, löst die alte ab“).
- **F16 → F17** (dunkel → Papier) ist harsch; Vadim: „vielleicht lassen wir das so“. Lösung, falls doch: Welt 1 um einen
  Frame verschieben, damit der Wechsel auf den kleinsten Stern fällt, oder 1–2 Mittel-Helligkeits-Stationen als Brücke.
- Lesbarkeit sinkt durch die Effekte im Titel (min 0.69 → 0.60 inkl. Welt 2, Plakat 33 Tokyo/S33 schlechtestes).
- Ort fehlt weiter: Endkarte zeigt Platzhalter „ORT FOLGT“ (`card_info`).
- Sterne-Agent: das alte Korn mischt mit der Stufe darunter, auf der Split-Naht (Stufe 3) entsteht so Flieder/Oliv
  (Rot+Blau, Gelb+Blau). S56–S60 halten das Korn in einer Colorway; alte Sterne ungeprüft.
- Auf F1–4/F29–32 liegt die ganze Seite im Stern: Effekte außerhalb sind dort unsichtbar (nur S58 trägt auf F1).

- **Campus-Plakate** als eigenes Konzept (z. B. die stärksten Loop-Frames). Plätze: 18 × A4 hoch, 56 × A3 hoch, 10 × A4 quer.
- Ort (`kickoff.COPY["where"]`) fehlt, für Endkarte und Plakate.
- Zeigt das Video Campus-Fotos oder nur Simulation? Davon hängen `align` und das Shooting ab (Archiv in `ENTSCHEIDUNGEN.md`).
- Resolve-Stern-Editor kennt 32 Frames und leere Frames noch nicht.
- 9:16-Sicherheitszonen der Endkarte (Reels-UI unten/rechts).
- `SV_LABEL_CELLS` in `lab_spark.py` spiegelt `[qr]` (Versalhöhe 9 + Abstand 4). Ändert sich JOIN US, dort nachziehen.
