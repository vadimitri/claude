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
- **Agenten (3.10.):** `pipeline` und `enden` sind gemergt; die Enden stehen jetzt als O6/O7 unten.

## Bahn-Enden O6, O7 (1.10. abends, aus der Übergabe; Runde 2 gebaut, wartet auf Vadims Urteil)

`[endcard].end_mode = "orbit"` (`kickoff_loop_end.py`, Schlüssel `orbit_*` in `[ending]`): nach dem Karussell (4 Takte T16)
genau **ein** digitaler Umlauf ab dem Bass-Boom (11.76 s, Vadim 3.10.: „sonst zu teasing“), dann die neue Bahn. Beide
Fortsetzungen starten am Zustand der Bahn **im Bild** (`orbit_kin`: Lage, Tempo, Größenrate) und werden nur schneller.
Draft-Vorschauen: `previz/review/O6/`, `O7/` (`preview_draft.mp4`, `report_draft.txt`). O4/O5 → `archiv/review/alt/`.
- **O6** Wurf in die Tiefe (`orbit_path = "throw"`, F14): gerade Linie zum Fluchtpunkt rechts von SPARK. Gesteuert wird 1/Z
  (für eine Gerade sind Radius und Abstand zum Fluchtpunkt beide ∝ 1/Z): R = R0 + R0'·F, Mitte = c0 + v0·F,
  F = ∫ k^(t/b), `orbit_throw_speedup` 5. Bildtempo 50 → 86 px/Bild, weg nach 0.34 s (14.06 s). Befund O4: die Gerade
  mit exponentiellem *Raum*tempo wurde im Bild langsamer (46 → 3 px/Bild) = „stoppt kurz“; `boost`/`orbit_3d` gelöscht.
- **O7** Wurf auf die Kamera + Infinite Zoom (`"dive"`): S33 liegt nur auf F1–F4 (am/nach dem Nahpunkt, Wachstum 0, Mitte
  seitlich 110 px/Bild). Deshalb taucht die Kamera **im Anflug** ein (`orbit_dive_lead_beats` 1/3 = ab F29): Zoomrate
  g = g0·k^(t/b) ab der Rate der Bahn (`orbit_throw_speedup` 4), die Mitte fährt in ihrer Richtung weiter und läuft mit dem
  Zoom aus (Tempo ∝ (R0/R)^`orbit_dive_drift_pow` 0.5, Ruhe bei ~(520, 1221), keine Umkehr, kein Ziel). Auf F1 der
  S33-Schnitt wie im Loop, dann `KD.zoom_spark`: **Puppen bis zum Punkt** (`orbit_dive_core_shrink` 20; mit 1 schrumpfte
  der Kern gegen den Zoom = wirkte rückwärts), Rauschen der Luft wächst mit (`_flow_noise`, 2 Oktaven, selbstähnlich),
  **Dreiecksblende** (`orbit_dive_shutter_frac` 0.5: Ringe verschwinden genau ab 1 Puppe/Bild; der Kasten kehrte den
  Kontrast um). Der alte Tempo-Deckel x1.5/Beat ist weg. Raster (Vorlauf × k × Potenz): 0.25 Beat trieb die Mitte aus dem
  Bild, 0.42 knickte 24°, Potenz 1 bremste die Mitte schneller, als der Zoom anzog.
- Selbsttest `uv run src/kickoff_loop_end.py test kickoff_loop/previz/review/O7/O7.toml` (bzw. O6): Loop bitgleich,
  Stetigkeit am Bild (S2), **Bahn clean** (`orbit_measure`/`orbit_clean`: Knick ≤ 10° inkl. Eigenkrümmung der Bahn (O7
  8.9°), Tempo/Rate am Wechsel x0.67–1.5, danach nie langsamer (O6 |v| und |g|; O7 g und Sehfluss |v| + g·rms-Radius),
  keine Umkehr, Mitte im Bild oder weg; Gegenproben alter O4 (Tempo x0.5) und alter O5 (ohne Vorlauf aus F1) schlagen an),
  **Stroboskop am Bild** (O7: Ringkontrast mit/ohne Unschärfe ab 1 Puppe/Bild 0.18 ≤ 0.3, unter ½ Puppe 0.62 ≥ 0.5),
  ≤ 1 digitaler Umlauf. Report: Zeile „Bahn-Check“.
- Verworfen: Maßstab am Bild per log-polarer Korrelation (Puppen selbstähnlich: ab ½ Puppe/Bild nur modulo einer Puppe
  messbar, O7 startet bei 0.37). `cv2.warpPolar` liefert im Log-Modus `nan` → eigene Abtastung per `cv2.remap`.
- **Endfarbe offen, Vadim mochte Blau.** O7 Navy/Türkis (Plakat 1), O6 Dunkelrot (Plakat 62).
- **Runde 2 (Vadim 1.10. spät, gebaut):** „letzten Loop schneller, Wegschleudern zu langsam“ → `orbit_loop_speedup` 1.6
  (Tempo des digitalen Umlaufs x1.6 pro Beat ab T16, Wurf bei 7.15 s statt 13.72 s) und O6 `orbit_throw_speedup` 8 (weg
  nach 0.19 s, 108 → 154 px/Bild). „Zoom nicht mittig, nervig“ → `orbit_dive_target` [0.55, 0.5]: die Mitte fährt auf
  einer Hermite-Kurve (Lage + Tempo der Bahn → Ziel mit Tempo 0, Dauer 2 x Abstand / Tempo = lineares Abbremsen) dorthin,
  Vorlauf jetzt in Bahnframes (`orbit_dive_lead_frames` 7 = ab F26, Raster: weniger bremst in 3 Bildern hart), Zoom x8,
  Drehung x1.5 (x2 lief über 30°/Bild = Wagenrad rückwärts). „Text verschwindet nicht und kommt neu“ → `orbit_type_morph`:
  jedes Plakat-Element zerfällt in derselben Bayer-Reihenfolge, in der sein Kartenteil eindithert (`MORPH`), „Gradients
  bewegen sich darunter, lively, posterisiert“ → `orbit_flow_*` (Zeilenverlauf als Dreieckswelle nach oben, auf
  Palettenstufen gerundet; 3 Stufen halbierten die kleine Schrift, Lesbarkeit 0.85 → 2 Stufen, 0.95/0.97). „Nichts poppt
  von links/rechts ein“ → `card_moves` alle dx = dy = 0, Maßstab 1, nur Eindithern. „Video zu lang“ → `carousel_bars` 2,
  `length_bars` 5 (14.7 s statt 22.8 s). JOIN US kippt nur noch als ganzes Wort (`KL.flip_word`, Regel fürs ganze System).
  Messung angepasst: Knick = Drehung am Wechsel minus Drehung davor (bei x1.6 dreht die Bahn selbst 20°/Bild), Sprung =
  erster ganzer Schritt danach / letzter davor (der Schritt über den Wechsel verdeckte den Stand-Zoom), Zoomrate muss
  echt steigen; Gegenprobe Versatz = 2 Videobilder Bahnweg.
- `previz/review/O7/new.toml` = Vadims eigener Tweak (Zoom x6, Potenz 0.2, Drehung x3), auf den neuen Stand gezogen; Bahn-
  Check dort FEHLER, weil Drehung x3 über 30°/Bild läuft (6 Zacken: wirkt rückwärts).
- **Offen für Vadim:** O6 vs O7; dann das gewählte `[ending]` + `[endcard]` nach `loop.toml`, `preview` ohne `--draft`.

## Übergabe O9 (2.10. spät, Vadims Urteil zu O8, in neuer Session bauen)

Start: diese Liste, dann `previz/review/O8/O8.toml` nach `O9/O9.toml` kopieren und dort ändern. Code: `finale`,
`finale_layers`, `_fly`, `spin_stop` (`kickoff_loop_end.py`), Dimmer in `KD.zoom_type`. Vorschau `preview … --draft`.

1. **JOIN US geht mit dem QR**: `orbit_dissolve = ["qr", "cta"]` (eine Zeile, Code kann das schon).
2. **Begriffe pro Beat** nach dem QR-Zerfall, an der freien QR-Stelle, je Beat einer ersetzt den vorigen (Vorschlag:
   am Ende bleibt NEW SEMESTER, NEW PROJECTS stehen; Vadim bestätigen lassen). Liste (Vadim: „Robotics, Drones, Autonomous
   Robots, Robotfights, Sensorik, Elektronik und so weiter“), Englisch wie JOIN US/NEW SEMESTER:
   `ROBOTICS, DRONES, AUTONOMOUS ROBOTS, ROBOT FIGHTS, SENSORS, ELECTRONICS`; **Vorschlag dazu** (Spark macht Zumo-
   Challenges, Workshops, Maker Night): `3D PRINTING, PCB DESIGN, FIRMWARE, SOLDERING`. Altes W1 hatte deutsch
   `HARDWARE, ROBOTER, LÖTEN, 3D-DRUCK, CODE, WORKSHOPS, PROJEKTE` (archiv/geparkt/W1) – Mechanik dort: `words_*`.
   Takt: Beat = 0.7352 s, Karussell-Ende 5.88 s = Beat 0, Video endet Beat 12. Starke Drum-Schläge (igor_beats.json
   `hits_s`) bei Beat 4.0 / 5.5 / 7.5 / 11.2. Zwischen QR-Zerfall (fertig Beat 4.5) und Abschluss (Beat 9) passen nur
   **5 Begriffe**; für 8–10: `length_bars` 6 (17.6 s), Abschluss nach hinten. Vadim fragen oder 6 nehmen und sagen.
3. **Kristallisieren statt Fade** (Vadim: „Pixel für Pixel, natürlich, nicht wie Fade-In, relativ kurz, weil pro Beat“):
   Zellen setzen in Wachstumsreihenfolge ein (Abstand zu wenigen Keimzellen im Buchstaben + Rauschen, wie Kristalle),
   in ~1/3 Beat (6 Bilder bei 24 fps), **zuerst als Difference** (Negativ des Untergrunds wie SPARK, `KL.title_value`
   bzw. früher `card_diff`), danach ein **kurzer Fade** (~1/4 Beat, das will er hier ausdrücklich) in die normale
   Tintenstufe. Bausteine: `reveal` (bayer/noise/blocks), `bayer`, `KL.title_value`, `KL.flip_word`. Selbsttest am Bild:
   Anteil gesetzter Zellen wächst monoton und zusammenhängend (Zahl der Inseln sinkt), am Ende = Maske; Gegenprobe Bayer.
4. **Zoom „scheiße“**: „Spark kommt schnell, Zoom langsamer, dann direkt unscharf“. Befund O8: am Wechsel Bildtempo
   **x0.70** (Gate erlaubt 0.67), ab Beat ~2.5 mehr als 1 Puppe pro Bild → Ringe werden radialer Verlauf (= „unscharf“).
   Wunsch: **weiter zwischen den Sparks wechseln**, nicht nur S33: alle Sparks werden immer größer, Momentum bleibt.
   Vorschlag: Matrjoschka aus allen Sparks (jede Puppe ein anderer Stil aus `[styles].cycle`, Kamera fliegt durch),
   Zoomrate gedeckelt unter ~0.5 Puppe/Bild (dann keine Unschärfe nötig), Tempo am Wechsel ≥ x1.0. „Langsamer werden
   können wir auch, wenn die Sparks wechseln.“ Heute stoppt der Wechsel bei `orbit_cycle_beats` 1.73.
5. **Glühen bleibt** (Vadim: „soll nicht weggehen, hört auf, wird langsamer“): heute hängt es an der Zoomrate und
   klingt nach dem Gipfel ab. Neu: einmal erreicht, steht es bis zum Abschluss.
6. **Kein Kippen pro Buchstabe** bei KICK-OFF/Datum (heute `flip_glyphs`, im Zoom wechseln sie hell/dunkel). Im Ende
   `flip_word` je Zeile. Offen: auch auf allen 64 Plakaten? Vadim sagte 1.10. „niemals unterschiedliche
   Buchstabenfarben“ (bisher nur JOIN US). Vorschlag: systemweit, Lesbarkeits-Gate prüfen, Vadim fragen.
7. **Kerning P–A in SPARK** (Vadim: „zwischen P und A mehr Platz, das A soll richtig zentriert sein, P näher ran“).
   Befund (Clash, Versalhöhe 200 px, kleinster/mittlerer waagerechter Abstand zeilenweise): S–P 13/32, **P–A 44/85**,
   A–R 6/49, R–K 9/28. P–A ist 3–7x so weit wie die anderen (A schiebt sich unter den offenen Bauch des P).
   Vorschlag: Kern-Paar P–A ≈ −0.15 Versalhöhe (engster Abstand ~13 wie S–P) in `S.line_mask`/Clash-Satz, dann
   zentrieren: Varianten (a) Kasten mittig, (b) Achse des A auf Bildmitte. Beide im Bogen zeigen. Wirkt auf alle Plakate
   und Druck (Cache kalt, Lesbarkeit neu messen).
8. Version: `O9` mit allem oben, `preview --draft`, dann voll. Danach O8 → `archiv/review/alt/`.

Parallel offen: **Druckmarken fertig, nicht gemergt**: Branch `worktree-agent-a242633ca97527a0e` (Commit 21b027b,
gepusht), `src/kickoff_loop_marks.py` + `[marks]` in loop.toml + Abschnitt „Druckmarken“ in seiner CLAUDE.md. Verfahren:
2x2-Zellquadrate leicht +/− (je Gruppe ausgeglichen), halb festes Lagemuster, halb Code aus der Frame-Nummer; QR und
Glühen frei; nur `print`, Video bitgleich. Gegengeprüft 2.10.: `kickoff_loop.py test` grün, `kickoff_loop_marks.py test`
ok (64/64 Nummern, Eckfehler max 0.26 % < 0.5 %, Sichtbarkeit bei 1 m max ΔE 0.012 < JND 0.02, QR 64/64,
Gegenproben schlagen an). Annahme Druckermodell (3 % Schwarz, Punktzuwachs) → **ein Testdruck + Handyfoto + `align`**
vor dem Großdruck. Merge: `git merge worktree-agent-a242633ca97527a0e` (berührt CLAUDE.md, loop.toml, kickoff_loop.py:
Konflikt nur in CLAUDE.md erwartet). **Steganografie/Schnitzeljagd**: in der Session 2.10. nicht
gebaut, ein Sicherheitsfilter hat den Auftrag blockiert. Vadim entscheidet, wie es weitergeht.

## Finale O8 (2.10., Urteil siehe Übergabe O9 oben)

Vadim zum Ende: „Matrjoschka soll sich nicht drehen, langsamer werden, gerade bleiben; kein neuer Titel, QR brauchen wir
nicht; Titel glüht, damit man sieht, wie stark wir reinzoomen; Gradient funktioniert nicht (nur Linien nach oben); nur der
QR löst sich nach vorn in Pixel auf, dann NEW SEMESTER, NEW PROJECTS; das Abdimmen schließt das Video ab.“
`previz/review/O8/O8.toml` = Vadims `O7/test.toml` (Ziel mittig, Blende 0.1) + Finale (`finale`/`finale_layers` in
`kickoff_loop_end.py`, Dimmer in `KD.zoom_type`). `card_on = false`, Morph und Verlauf aus.
- **Zoom** zieht bis `orbit_zoom_peak_beats` 3.5 an (x8/Beat, Bahn-Check misst bis 3.45: clean), danach Rate x0.25/Beat:
  die Ringe werden wieder sichtbar und laufen langsam. Ohne Gipfel lief R über `float` (Überlauf nach ~7 Beats).
- **Drehung** läuft linear aus (`spin_stop`, Tempo am Wurf stetig x1.02) und steht ab Beat ~3.5 gerade (Vielfaches von
  60°). Bahn-Check zählt beim Finale die Drehung nicht mehr als „langsamer“ (gewollt).
- **Zoom-Glühen**: SPARK + KICK-OFF/Datum 16-mal um die Zoom-Mitte vergrößert, in der hellsten Stufe, Länge = Zoom in
  `orbit_glow_frames` Bildern (Deckel `orbit_glow_max_scale` 1.6), klingt mit dem Zoom und dem Abschluss ab.
- **QR** zerfällt ab Beat 3 in 1.5 Beats: je Modul ein Splitter mit eigener Tiefe/Verzögerung, wächst bis x6 um die
  Zoom-Mitte und kippt im Korn weg (`_fly`). `orbit_dissolve = ["qr", "cta"]` nähme JOIN US mit.
- **NEW SEMESTER, / NEW PROJECTS** an der QR-Stelle (Größe/Zeilenabstand wie KICK-OFF/Datum, letzte Grundlinie auf der
  QR-Unterkante), Beat 4–5, kippt als ganzes Wort (`flip_word`; pro Buchstabe gab gemischte Farben).
- **Abschluss** Beat 9–10: alles außer Schrift kippt im Korn in Grundstufe 0, dann 2 Beats Satz allein.
  Befund: `flip_glyphs` hielt den abgedimmten Stern noch für hell und ließ Buchstaben verschwinden → `c.star_m` wird mit
  abgedimmt.
- Report „Finale“: QR im Schlussbild weg, Lesbarkeit SPARK + Datum + neue Zeilen **0.97 A**. Selbsttest „Drehung läuft
  aus“ (Gegenprobe alte Drehung schlägt an). **Stroboskop-Gate FEHLER 0.83 > 0.3** kommt aus Vadims Blende 0.1 (O7/test
  genauso, O7 mit 0.5: 0.23 ok), nicht vom Finale. Vadim entscheidet.
- KICK-OFF/Datum kippen weiter pro Buchstabe (Systemregel aus dem Loop); im Zoom wechseln sie dadurch hell/dunkel.

**Stellschrauben Ende** (alle in `[ending]` der Varianten-TOML; Report-Zeile „Bahn-Check“ sagt, ob es noch clean ist):

| Schlüssel | macht | O6 / O7 |
|---|---|---|
| `carousel_bars`, `length_bars` | Länge Kamerafahrt+Karussell bzw. ganzes Video (Takte à 2.94 s) | 2 / 5 |
| `orbit_loop_speedup` | digitaler Umlauf wird pro Beat so viel schneller (1 = T16) | 1.6 |
| `orbit_frame` | Bahnframe des Wurfs (throw: einer, auf dem er schrumpft F2–F16; dive: F1 = S33) | 14 / 1 |
| `orbit_throw_speedup` | throw: Bildtempo x pro Beat; dive: Zoomrate x pro Beat | 8 / 8 |
| `orbit_spin_speedup` | Drehung legt pro Beat (x − 1) zu; über 30°/Bild wirkt sie rückwärts | 5 / 1.5 |
| `orbit_dive_lead_frames` | Kamera taucht so viele Bahnframes vor F1 ein (mehr = weicher aufs Ziel) | – / 7 |
| `orbit_dive_target` | Ruhepunkt der Zoom-Mitte [x, y] als Bruchteil des Bildes, `[]` = läuft frei aus | – / [0.55, 0.5] |
| `orbit_dive_shutter_frac` | Bewegungsunschärfe (0 = scharf, flackert ab ½ Puppe/Bild; 0.5 = Ringe weg ab 1) | – / 0.5 |
| `orbit_dive_core_shrink` | 20 = Puppen bis zum Punkt; 1 = Kern schrumpft sichtbar (wirkt rückwärts) | – / 20 |
| `orbit_cycle_beats` | bis hier wechseln Farbe/Stern, dann steht die Colorway (Endfarbe) | 1.73 |
| `orbit_flow_at_beats`, `_in_beats`, `_steps`, `_per_beat` | laufender Verlauf in der Schrift: Start, Einblendung, Spannweite (Stufen), Tempo (Zeilen/Beat) | 1, 1, 2, 1 |
| `orbit_type_morph` | true = Satz morpht in die Karte, false = alter Zerfall (`orbit_type_out_*`) | true |
| `card_moves` | [Teil, Einsatz-Beat, dx, dy, Startmaßstab] je Kartenteil; Reihenfolge/Takt des Morphs | 2.75–3.75 |
| `card_in_beats` | Dauer des Eindithern (Hälfte davon) | 1 |
| `card_reveal` | bayer / blocks / noise | bayer |
| `card_dim_frac` | Grund unter der Karte abdimmen (1 = Zoom geht ganz in den Grund) | 0 / 1 |
| `card_*_frac`, `card_qr_*` | Layout der Karte (Titelbreite, Abstände, QR-Größe/-Lage) | |
| `orbit_zoom_peak_beats`, `_decay` | Finale: Zoom zieht bis hier an, danach Rate x decay pro Beat | O8: 3.5, 0.25 |
| `orbit_spin_stop_beats`, `_rest_deg` | Finale: Drehung läuft in ~so vielen Beats aus, steht auf rest + n·60° | 2, 0 |
| `orbit_glow_frames`, `_max_scale` | Finale: Länge des Zoom-Glühens (Zoom in so vielen Bildern), Deckel | 0.25, 1.6 |
| `orbit_dissolve`, `_at_beats`, `_beats`, `_scale` | Finale: welche Satzteile nach vorn zerfallen, wann, wie lange, bis zu welchem Maßstab | ["qr"], 3, 1.5, 6 |
| `orbit_new_lines`, `_at_beats`, `_in_beats` | Finale: neue Zeilen an der QR-Stelle | NEW SEMESTER, / NEW PROJECTS, 4, 1 |
| `orbit_close_at_beats`, `_beats` | Finale: Abschluss (Zoom kippt in den Grund) | 9, 1 |


## Stand vor O6/O7 (Übergabe O4/O5 erledigt 1.10. abends, Details oben)

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

Aus jedem Ordner (Vadims Shell, `~/.zshrc`): `kl <befehl> [x.toml] [--draft]` = `uv run src/kickoff_loop.py <befehl> <x.toml>`
mit Pfad relativ zum aktuellen Ordner, Pack-Root wird über der TOML gesucht; `kl end x.toml` = Selbsttest Ende; ohne TOML
bei sheet/preview/end die einzige im Ordner.

| Befehl | Ergebnis | Dauer |
|---|---|---|
| `uv run src/kickoff_loop.py sheet [review/X/X.toml]` | Kontaktbogen + Loop-Video → `previz/now/` bzw. `previz/review/X/` (+ Report). Öffnet nichts (Vadim schaut selbst) | warm ~4 s, kalt ~15 s |
| `uv run src/kickoff_loop.py stars [S..]` | Sterne-Bogen an 3 Bahnstellen → `previz/variants/stars.png` | ~25 s |
| `uv run src/kickoff_loop.py grounds [review/I1/I1.toml ..]` | blanker Grund (ohne Stern/Satz) je Variante, erste Zeile loop.toml → `previz/variants/grounds.png` | ~3 s |
| `uv run src/kickoff_loop.py test [N..]` | Selbsttest am fertigen Bild (+ Bahn, Blitz) | ~5 s |
| `uv run --with numpy --with pillow --with scipy --with qrcode --with scikit-image --with opencv-python-headless python src/lab_spark.py test` | Selbsttest Sterne (Hand-Schraffur) | ~20 s |
| `uv run src/kickoff_loop_resolve.py schnitt` | Resolve-Projekt `SPARK_Kickoff_Schnitt`: Timeline „Schnitt" = Loop (9:16, Wechsel auf IGORs Raster, F1 auf 22.435 s) + IGOR-Song, verknüpft, 9 Marker; „Referenz" = `resolve/schnitt/ref/*`. Erneut aufrufen = neue Medien, Timeline bleibt (Resolve verlinkt neu) | ~3 min |
| `uv run src/kickoff_loop.py preview [review/X/X.toml]` | ohne Argument neue Version `previz/vNNN/`, mit Variante in ihren Ordner (Video, Bögen, Report, Config-Kopie). `--master`: x264 statt Hardware-Encoder (Endabnahme) | nichts/nur Ende geändert ~9 / ~11 s, Stern geändert ~21 s, kalt ~30 s |
| `uv run src/kickoff_loop.py preview review/X/X.toml --draft` | Entwurf: Digitalteil auf Zweiern, kein Zoom-Check → `*_draft.mp4/.png`, `report_draft.txt` (Kopfzeile DRAFT); teilt das Foto-Segment mit der Endversion | Ende geändert ~9 s |
| `uv run src/kickoff_loop_end.py test review/Z4/Z4.toml` | Selbsttest Ausstiege (Auslauf bremst/landet, Kamera stetig, warp), Gegenprobe linear | ~5 s |
| `uv run src/kickoff_loop.py frames` / `variants` / `boil` / `print` / `resolve` | Frames rendern / QR-Varianten / Boil-Test / Druck-PDFs / Resolve-Bausteine | |
| `uv run src/kickoff_loop_music.py` | Musik + Raster → `ref/audio/mashup_*.wav/.json` | ~5 s |

Frames sind nach Inhalt gecacht (`_cache/`): Schlüssel = ganzes Stil-Dict + Hash nur der Quelltexte, die das Bild
bestimmen (`kickoff_loop.POSTER_SOURCES`/`DIGITAL_SOURCES` samt Importen; `test` prüft per Trace, dass nichts fehlt).
Änderungen an `kickoff_loop_video.py`, Musik, Resolve lassen den Cache stehen. QR/Lesbarkeit stehen gemerkt in
`_cache/checks/`. Ein Pool pro Lauf (`kickoff_loop.pool()`), Foto-Phase parallel je Plakat.
**Foto-Segment** (`_cache/video/photo_<key>.ts`, `kickoff_loop_video.PhotoSegment`): die Foto-Phase liegt fertig kodiert im
Cache, der Digitalteil wird als zweites Segment ohne Neukodieren angehängt (dekodiert bitgleich). Schlüssel `photo_key` =
Kamera-Werte je Frame + Plakat-Schlüssel + `[simulation]`/`[video]` + Encoder + Quelltext; `test` prüft per Trace. Ändert
sich nur das Ende (oder `--draft`), fallen Platten, Kamera und Encoder der Foto-Phase weg. Die 4 zuletzt benutzten Segmente
bleiben (~70 MB je Stück). **Encoder**: alle Vorschauen VideoToolbox q65 (`PREVIEW_ENCODER`, Vadim 3.10.: Tempo vor
Qualität), `--master` = x264 `fast` crf 16 (`MASTER_ENCODER`). Digitalteil kommt in Zeitfolge aus dem Pool
(`DigitalFrames`), der Encoder wartet nicht mehr auf den ganzen Teil. QR-Prüfung bricht ab, sobald das Ergebnis steht.

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
