# Kick-off Loop · SPARK Kick-off 14.10., 17:00

Session-Start: diese Datei, dann `uv run src/kickoff_loop.py sheet` (zeigt den Stand in ~10 s). Stellschrauben: `loop.toml`.
Regeln fürs Pack: `../CLAUDE.md`. **Vor Vorschlägen** `ENTSCHEIDUNGEN.md` (Befunde, Verworfenes, Archiv) und Skill `spark-motion`.

## Übergabe Video (6.10. abends) · **neue Session: das Video fertig machen**

**Zuerst `HANDOFF_ENDE.md` lesen** (6.10. nachmittags): Video-Ende O14–M4 verworfen, Vadims Stand, Aufräumen (Agent A), Neubau (Agent B). Schritt 1 unten ist überholt.

**Plakate sind abgenommen (Vadim 6.10.) und gedruckt** (`print` → `kickoff_loop/print/`, gitignored: `aushang_NN.pdf` mit
Rückseite, `foto_NN.pdf`, `NN.png`, A3 300 dpi mit Druckmarken). `[type]`, `[type.ink]`, `[type.halo]`, `[color]`,
`[styles]`, `[spark]` in `loop.toml` **nicht mehr ändern** (sonst stimmen Video und Druck nicht überein; Marken: Nummer +
Lage bleiben, nur `polish` greift nicht). Details zum Satz: Abschnitt „Stand 6.10.“ unten.
**Druck-PDFs** (`pdf` baut sie ohne Rendern neu aus `print/NN.png`): `aushaenge_duplex.pdf` (31 Aushänge, vorn/hinten
abwechselnd, Duplex lange Kante), `fotos_einseitig.pdf` (33), `rueckseite.pdf` („BITTE NICHT ABHÄNGEN / BIS 15.10.“),
Einzel-PDFs. A4 = dieselben Dateien mit „An Seite anpassen“ (kein eigener Export). `print_a4/` vom 2.10. ist veraltet.
**Druckrand** (`[print]`, `edge_fade`, nur Druck, nie im Video): kein eigener weißer Rand (den setzt der Drucker, Vadim),
ab der Kante Lichtabfall ins Weiß über 16 Zellen
(Bayer, ab 1/8 Dichte abgeschnitten: sonst gerade Punktlinie = Rahmen), Breite als **Welle** (A2: 3 Wellen, ±60 %, laufen
je 32er-Loop eine Wellenlänge um). Fotografiert und im Loop abgespielt läuft der Rand um; im Video selbst ist er noch
**nicht** drin (Vorschau mit simuliertem Druckerrand 5 Zellen: `previz/review/RAND/anim/A2.mp4`, `RAND/O13_rand/`).

Start: diese Datei, dann `uv run src/kickoff_loop.py preview kickoff_loop/previz/review/O13/O13.toml --draft` (neue
Plakate im Video; Foto-Segment ist kalt, weil sich der Satz geändert hat → erster Lauf länger).

In dieser Reihenfolge:
1. **Ende wählen.** O13 (`previz/review/O13/`, gerendert 3.10. mit den alten Plakaten) wartet auf Vadims Urteil, siehe
   Abschnitt „Finale O13“. Offen dort: Lesbarkeit der Begriffe auf dem großen Stern; Selbsttest am fertigen Bild, der
   Effekte hinter Titel/QR misst („zum vierten Mal“; die Plakate haben jetzt `fx_under_qr`, das Finale `fx_behind_qr`).
   O6/O7/O12a/O12b sind überholt → nach `archiv/review/alt/`, `INK/` und `S58b_S60d/` ebenso (entschieden).
2. **Sprung am Eintauchen prüfen (Risiko, ungeprüft):** `type_layers` überspringt im Digitalteil `[type.ink]` und
   `[type.halo]` (`if not lp["digital"]`, `halo = [] if lp["digital"]`). Beim Übergang Loop → Zoom kann der Satz springen:
   Glühen weg, Block-Farbe kippt zeilenweise zurück, Akzente (9 Karmin, 15 Himmelblau, 5 Dunkelblau) verschwinden. Am
   Eintauch-Bild mit dem Plakat davor vergleichen. Fix: Plakatnummer des Eintauch-Plakats in `dg` mitgeben und Farbe +
   Glühen dort weiterführen (oder bewusst überblenden), Vadim zeigen.
3. Gewähltes `[ending]` + `[endcard]` nach `loop.toml`, dann `preview` ohne `--draft`, zum Schluss `preview --master`
   (x264). Lieferung: `*.mp4` (Master), `*_share.mp4`, ProRes für Resolve (`resolve`).
4. **Musik schneidet Vadim selbst** in Resolve: `uv run src/kickoff_loop_resolve.py schnitt` (~3 min, Timeline „Schnitt“,
   IGOR, 9 Marker) nach dem finalen Render neu laufen lassen. Nur IGOR, kein Maker-Night-Material.
5. **Campus-Fotos: läuft** (Abschnitt „Campus-Fotos“ unten): 29/64 als Foto im Video, Rest folgt nach dem Aufhängen 7.10.

## Campus-Fotos (6.10., `src/kickoff_loop_photos.py`, `[photos]` in `loop.toml`) · **Vorschau F1, wartet auf Vadim**

Vadim 6.10.: alles in A4 + A3 gedruckt, aufgehängt, mit der R8 fotografiert; Fotos in Reihenfolge, für die Vorschau
skaliert, Farben wie digital, nichts (kaum) überbelichtet; fehlende Plakate bleiben Simulation.
- **Neue Fotos:** SD-Karte → `photos/raw/` (`rsync -a --include='IMG_*.JPG' --exclude='*' /Volumes/Canon/DCIM/<ordner>/
  kickoff_loop/photos/raw/`), dann `uv run src/kickoff_loop_photos.py` (~1 min, Erkennung je Foto gemerkt in
  `photos/detect.json`), dann `preview review/F1/F1.toml --draft`. Ausgabe `photos/aligned/NN.png` (fertig gegradet,
  `photo_plate` gradet echte Fotos nicht mehr nach), Bögen `photos/plates.png` (alle 64 wie im Video) und
  `photos/colors.png` (Plakat im Foto | digital), `photos/report.txt`. Foto je Plakat erzwingen: `[photos].pick`.
- **Erkennen:** Marken (`marks.detect`) für 141/170; ohne Treffer QR + Vergleich mit allen 64 Renders + ECC (`identify`):
  +5 (u. a. 11 dunkelgold). Nicht zuordenbar: Litfaßsäule IMG_1024–1031 (gewölbt, keine Ebene; gelb mit blauem
  Stern, 19 oder 20), 7 Nicht-Plakat-Fotos. `marks.align` gelöscht (schrieb ungegradete Platten an dieselbe Stelle).
- **Farbe:** im Plakat linear `(foto^g) @ A + b` gegen den Render, robust gefittet am Inneren (ohne Druckrand-Welle):
  dE OK Median roh 0.04–0.34 → fertig 0.012–0.05. **Befund:** die volle Matrix auf die Wand hochgerechnet kippt sie
  (Holztür knallrot, Wand grün/magenta) → Wand bekommt nur die Grauachse der Matrix (Weißabgleich ≤ x1.25, Schwarzpunkt
  ≤ 0.02, sonst kippte 35 bei einem fast rein roten Plakat), Lichter mit Schulter ab 0.7, dann auf `surround_luma`
  abgedunkelt, aber nie unter x0.5 und nie heller. Übergang Plakat → Wand 12 Zellen (40 gab einen weißen Glühring).
  Fast alle Wände landen bei x0.5 (Fotos heller als die Simulation mit 0.22).
- **Offen:** Ausgefressen im Plakat 17 (6.5 %, Glas), 28 (4.3 %); Wand ausgefressen schon im JPG bei 47, 5, 57
  (Fenster), rettbar nur über die CR3 (liegen auf der SD-Karte, nicht kopiert). Auswahl je Plakat Vadim (`pick`).

Vadims Regeln aus der Plakat-Runde, gelten fürs Video weiter: nie flache Farben (immer Verlauf + Bayer), nie einzelne
Buchstaben umfärben, Effekte werden nie von QR/Titel blockiert, kein Drop-Shadow, im Loop keine Zeilen, die sich einzeln
ändern. Er entscheidet an beschrifteten Bögen/Videos (Codes), schnell zeigen (`sheet`, `--draft`), volles Video nur wenn
Musik/Ende betroffen. Hilfsskripte der Plakat-Runde (Kontrast-Messung je Zeile, Vergleichsbögen) lagen nur im Job-Ordner,
nicht im Repo; die Messidee steht unten unter „Stand 6.10.“.

## Stand 6.10. (Ort, Satzkante, Lesbarkeit je Plakat) · **abgenommen**

- **Ort** `kickoff.COPY["where"] = "D-SCHOOL"` (d-school, EG; ohne Kurzform), dritte Zeile unter dem Datum.
- **Satzkante** = linke Tinte des zentrierten SPARK (`title_left`): KICK-OFF/Datum/Ort, JOIN US, QR-Platte buendig am S
  (Vadim: seit Kerning P-A stand der Block daneben; lieber mehr Rand). Titel wird immer ab `m` zentriert (round() rundet
  .5 zur geraden Zahl, sonst sprang er 1 Zelle), linke Zeilen werden an der gemessenen Tinte auf `x0` geschoben.
- **`[type.ink]`** Plakatnummer -> Zeile/Wort -> Palettenstufe k (Verlauf endet auf k) oder `["#unten", "#oben"]`
  (Akzent mit eigener Ebenenpalette, gleicher Verlauf + Bayer). Vadim: **nie flach, nie einzelne Buchstaben**.
- **Gluehen auf allen Plakaten** (`halo_all`, Vadim 6.10. vorlaeufig: „im Loop sieht es scheisse aus, wenn sich einzelne
  Zeilen veraendern“): jeder Block hat eine Farbe. Plakate aus `[type.halo]` ganz in Tinte (abgenommen), die anderen
  kippen als ganzer Block nach Mehrheit (sonst stand z. B. 13 hell auf hellem Stern). Gluehen sehr subtil rundum:
  `halo_cells` 6, kein Kern, **kein Drop-Shadow** (`halo_shift_cells` [0, 0]), Innenraeume mit demselben Abfall wie aussen
  (gefuellt / frei / nur Kontur: alles verworfen). Volles Gluehen, schwach (`halo_weak`) nur ohne halo_all. Farbe = Seite mit
  mehr Helligkeitsabstand zur Schrift, `halo_step` 1 zur Mitte. Bayer direkt Untergrund <-> Gluehfarbe, Zweierpotenz-Baender.
  `[type.ink]`: Stufe k, `"hell"`/`"dunkel"` (Luminanz) oder `["#unten", "#oben"]`, immer ganzer Block. `halo_none`: Plakate
  ohne Gluehen (Vadim 6.10.: 22-27, 37, 49, 50, 54, 55, 58 brauchen keins), dort Satz wie vor der Gluehen-Runde.
- **QR blockiert keine Effekte mehr** (Vadim 6.10., 15/23 Fokuslinien): `fx_under_qr` auf allen Loop-Plakaten schaltet
  `lab_spark._qr_zone` ab, das QR-Gluehen bleibt. Selbsttest misst das Gluehen-Profil an einem Render ohne fx_under_qr.
- Gewaehlt: 5 Dunkelblau (Stufe 2), 9 Karmin-Akzent, 15 Himmelblau-Akzent, 61 Gluehen; Rest der Liste vom 6.10. per
  Messung (Kontrast des schlechtesten Buchstabens je Option auto/dunkel/hell/Gluehen, Wunschrichtung gewinnt bei >= 0.9x):
  meist Gluehen, dunkel bei 2 und 41. Runde 2 (Vadim): 3, 12, 33, 34, 39, 44, 48, 60 ganzer Block hell + Gluehen,
  29/64 hell, 16/29/52 durch die Block-Regel gleichmaessig. 6 und 35 am Bild auf Gluehen fuer den ganzen Block.
  Vergleich `previz/review/INK/vorher_nachher.png`, ganze Plakate `INK/*.png`.
- **`[loop].video_only = [1]`**: Aushang nur fuers Video (Druck als Fotoframe, Bogen „V“). Video-only laut Vadim auch 4,
  14, 46, 48 (sind ohnehin Fotoframes).
- Abgenommen 6.10., gedruckt (`print`).

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

## Finale O13 (3.10., Vadims Urteil zu O12: „12er-Reihe veraltet, neue Version“) · **gerendert, wartet auf Vadims Urteil**

Start: `previz/review/O12a/O12a.toml` → `O13/O13.toml`. Vadim wörtlich zusammengefasst:
1. **Weißraum um den QR blockiert die Effekte** → weg. Ebenso **blockiert der Titel dahinter die Sparks** → weg.
   „Das Problem hatten wir schon dreimal, fix das endlich“: Selbsttest am fertigen Bild, der Effekte hinter QR/Titel misst.
2. **QR verschwindet nicht verzögert** nach dem großen Spark, sondern **mit dem Momentum** des Sparks, der groß wird.
3. **Begriffe früher** („wir warten da so blöd“).
4. **Keine kleinen Sterne in der Mitte**: der große Spark fliegt rein, **bleibt groß** und **wechselt je Begriff** in einen
   anderen Spark (kontinuierlich).
5. **Rand um SPARK/KICK-OFF-Schriftzug weg**; das Halo (Glühen) bleibt.

Umsetzung (`previz/review/O13/O13.toml`, je Punkt ein Schalter):
1. `orbit_fx_free`: ab dem Eintauchen `fx_behind_title` + neues `fx_behind_qr` (`lab_spark._qr_zone` leer, `KL.qr_glow`
   ohne hellen Hof). Die Ruhezone der QR-Platte selbst bleibt, bis der QR zerfällt.
2. `orbit_dissolve_at_beats` 1.66 = gemessener Eintauch-Beat (`orbit_switch`), 1 Beat lang, Splitter x6 auf die Kamera.
3. `orbit_words_at_beats` 3 (O12 5); Abschluss 24, Video 8.5 Takte.
4. `orbit_stop_r_frac` 0 = keine kleinen Sterne; der große Stern übernimmt je Begriff `orbit_sparks[k]` + Colorway
   idx+1+k. `orbit_wall_r_frac` 2 statt 4 (Befund: R 0.5 → 1.9 → 3.6 x Bildbreite bei Beat 1.5/2/3, bei 4 nur Tapete;
   1.5 sättigte zu früh: Zoomrate am Wechsel x0.61, Bahn-Check FEHLER; 2: x0.70 ok).
5. `orbit_glow_clear_cells` 0 (vorher `GLOW_CLEAR_CELLS` frei um die Schrift).
Render `previz/review/O13/` (`preview.mp4`, `orbit.png`, `contact.png`, Report): QR 64/64, Bahn-Check ok, Schlussbild
SPARK + KICK-OFF/Datum 0.97 A auf #000; über den Zoom Mittel 0.86, min 0.49 (8.58 s), 34/51 ≥ B. Am Bogen: Effekte laufen
hinter SPARK, Stern wechselt je Begriff. Schwach: Begriffe auf unruhigen Sternen (ELECTRONICS, LASER CUTTING, HACKATHONS).
**Noch offen:** Lesbarkeit der Begriffe auf dem großen Stern; Selbsttest, der Effekte hinter Titel/QR am fertigen Bild misst (Punkt 1 „zum vierten Mal“).

## Finale O12 (2.10. abends, Vadims Urteil zu O11) · **Vadim: „sieht scheiße aus“ → neue Session**

**Stand der Übergabe:** O12 nur als Stills gesehen (Bogen: blaues Schraffur-Wallpaper, kleine Sterne + Begriff in der
Mitte, Schluss auf Schwarz), Vadim verwirft die Richtung schon daran. Vorschau-Render abgebrochen: `O12a/digital.ts`
(Digitalteil fertig kodiert) + `music.wav` liegen noch, O12b ist leer, kein `preview.mp4`, kein Report. Code-Stand O12
ist committet (Wallpaper-Sättigung, `stop_sparks`, Matrjoschka gelöscht). Zuletzt gut bewertete Teile, die bleiben sollten:
Übergang Loop → Eintauchen ohne Schnitt (O11), Drehung ohne Ruck, Glühen unter dem Satz + Helligkeit über Paletten,
Begriffe mittig mit Ein-/Auspixeln, Gag-Folge, Schluss auf Schwarz. In der neuen Session zuerst klären, was an O12
„scheiße“ ist (Wallpaper? kleine Sterne? Takt?), bevor gebaut wird. O11 ist per Git wiederherstellbar (Commit 27530e4).


Vadim zu O11: Vortex „zu stark, sieht weird aus“ → subtiler/smoother; **Zoom-Idee parken**: am Ende des Vortex wird der
Stern riesig und bildet einen neuen Hintergrund, in der Mitte dann ein kleiner Stern, ein Stil je Begriff (Stop-Motion
wie der Loop, Spider-Verse-Look), wächst etwas, aber kein Zoom; dazu je Stern ein Begriff. Rückfragen geklärt:
Hintergrund steht; Takt „3/4 oder 1 Beat überall, 1/2 zu schnell“; Wachsen stufig auf Zweiern; Begriffe „beides“.
`previz/review/O12a/` (1 Beat je Stern + Begriff, Begriff hart mit dem Stern, 9 Takte) und `O12b/` (¾ Beat, Begriff pixelt
ein/aus, 7.5 Takte). O11a/b → `archiv/review/alt/` (laden nicht mehr: Matrjoschka-Schlüssel gelöscht).
- **Hintergrund-Stern** (`orbit_wall_r_frac` 4): der Zoom in den Eintauch-Stern sättigt weich, ln R → ln(4 x Bildbreite)
  (Tempo am Anfang wie vorher, kommt ohne Ruck zur Ruhe, steht ab Beat ~4). **Befund:** ohne Sättigung war der Stern bei
  Beat 2.5 schon 13 904 px groß und der Schraffur-Stern S54c renderte ein Bild > 3 min (die Matrjoschka malte Puppen
  außerhalb des Bildes nie). Bahn-Check zählt dort „langsamer“ nicht (das Ausrollen ist gewollt), nur den Übergang:
  Knick 3.3°, Tempo x0.93, Rate x0.78.
- **Kleine Sterne** (`stop_sparks`): je Begriffs-Slot `orbit_sparks[k]` in der Bildmitte, Colorway Plakat + 1 + k aus der
  Farbreise (Palette je Zelle wie O11), gerade, Radius `orbit_stop_r_frac` 0.22 x Bildbreite, wächst über den Slot um
  `orbit_stop_grow_frac` 15 %, nur alle 2 Bilder ein Schritt (`STOP_ON`). Matrjoschka-Kette, `orbit_sparks_ratio`,
  `_spin_deg` und der Sterne-pro-Bild-Check gelöscht.
- **Vortex** 120° statt 360°, Ankunft-Ease 1.5 (länger, weicher).
- **Begriffe**: `orbit_words_in_frac`/`_out_frac` = 0 heißt hart mit dem Stern (O12a); Selbsttest prüft dort ganz ab dem
  ersten bis zum letzten Bild + mittig.

## Finale O11 (2.10. abends, Urteil umgesetzt in O12 oben, archiviert)

Vadim zu O10: „wenn, dann O10a“; kein Abdunkeln je Puppe; Colorways dürfen loopen; Glühen lesbar und ohne harten
Farbwechsel; Disconnect Loop → Zoom bei ~7 s „geht absolut gar nicht“; Rotation hört plötzlich auf; Zoom erst zu schnell,
dann zu langsam; Spark sitzt nach dem Schleudern auf einmal fest in der Mitte („kleine Vortex-Runde“); Text zu wenig, zu
langsam, Pixel-out fehlt; NEW SEMESTER weg. Rückfragen geklärt: Puppen farbig, nur der Abschluss auf Schwarz; Schluss =
Plakatsatz; Gag-Folge DESIGN, THINKING, DESIGN THINKING, JAZZ, HACKATHONS; Takt „beides probieren“.
`archiv/review/alt/O11a/` (erst 3 Begriffe je Beat, dann 18 je ½ Beat) und `O11b/` (21 je ½ Beat), Video 7 Takte.
O10, O10b, O10c → `archiv/review/alt/`. `preview` rendert bei Ende-Varianten kein `loop.mp4` mehr (hängt nicht vom Ende ab).
- **Disconnect** (Befund am Video 6.4–7.6 s: die Kamera tauchte schon 7 Bahnframes vor F1 in den Loop-Stern ein, dessen
  Plakate weiterwechselten, ein Bild ganz ohne Stern, dann harter Schnitt auf S33 in anderer Colorway): die Matrjoschka
  beginnt jetzt beim Eintauchen mit genau diesem Stern und dieser Colorway (Puppe 0 = `first`), Farbe/Stern stehen ab dort.
- **Farbe**: Puppe j läuft in der Farbreise weiter (Plakat + j, zyklisch über alle 64), `orbit_sparks_colors`/`_dim`/`BW`
  gelöscht. Schrift + Glühen bleiben in der Colorway des Eintauch-Plakats (kein harter Wechsel). Abschluss kippt auf echtes
  #000 (`c.layer_pal`), die Schrift wird dort zur hellsten Stufe (die feste Colorway kann Papier sein: dunkle Tinte).
- **Lesbarkeit**: das Glühen malt jetzt UNTER dem Satz (`glow_layer`), SPARK/KICK-OFF/Datum kippen dagegen, 2 Zellen Rand
  frei. Dazu rechnen Kippen/Difference/Glühen die Puppen über ihre echte Helligkeit in die Stufen der festen Colorway um
  (`KD.luma_to_base`; vorher galt eine dunkle Puppe als hell: dunkelblaue Schrift auf dunkelblauer Puppe). Gemessen
  (Beat 3/5.2/6.5/8.2/12.2): vorher 0.64/0.55/0.49/0.50/0.89, jetzt 0.75/0.80/0.65/0.44/0.66. Rest: eine Zeile über
  unruhigem Stern (gelb-blaues Karo) kippt als Ganzes und bleibt halb schwach. Report: Zeile „Finale über den Zoom“.
- **Drehung** läuft mit Tempo (1 − u)² aus (vorher linear: am Ende volle Bremsung), 3 Beats. Selbsttest misst den Ruck am
  Ende; Gegenprobe linearer Auslauf schlägt an.
- **Zoom** gleichmäßiger: Deckel x1.2/Bild, Gipfel Beat 2.5, danach x0.88/Beat (Rate fällt bis Beat 17 auf 1/6, O10 auf
  1/260), ~18 Puppen. Bahn-Check clean.
- **Vortex** (`orbit_dive_vortex_deg` 360): der Weg in die Mitte dreht eine Runde um die Bildmitte, Drehsinn der Bahn,
  Winkel smootherstep (mit 3u² − 2u³ sprang das Tempo am Wechsel auf x2.2), Ankunft-Ease 2. Tempo am Wechsel x1.12.
- **Begriffe**: nur noch sparkle (ripple/zoom gelöscht). `orbit_words_slots` = [[Anzahl, Beats]], je Slot Anteile
  `in`/`fade`/`out` (0.35/0.2/0.3), jeder pixelt am Ende in neuer Zufallsfolge aus (leuchtet kurz auf, weg). 21 Begriffe
  (Vadims Liste + LASER CUTTING, CNC MILLING, PROTOTYPING, WORKSHOPS als Vorschlag). Selbsttest: ein/aus monoton, ganz/leer,
  mittig; Gegenprobe neuer Zufall je Bild.

## Finale O10 (2.10. abends, Urteil umgesetzt in O11 oben, archiviert)

`archiv/review/alt/O10/` (sparkle = Version a), `O10b/` (ripple = b), `O10c/` (Begriff zoomt mit), je `preview.mp4`,
`orbit.png`, Report. Tempo-Vergleich: `O10/tempo.mp4` (Bildmitte, a/b x schnell/mittel/langsam/ohne Fade, mit Musik; Einmal-Skript, nicht im Repo).
O9 → `archiv/review/alt/O9/` (lädt nicht mehr: neue Pflichtschlüssel). Selbsttest `kl end` grün für alle drei.
1. **Begriffe mittig** (`finale_words`, `word_layer`): Block waagerecht und senkrecht auf der Bildmitte, Größe wie
   KICK-OFF/Datum. Befund: aus der Fontbreite gesetzt lag ROBOTICS 5 Zellen rechts (Tinte 1 Zelle versetzt, Schriftgrad
   gerundet) → Zeile wird einmal gesetzt, an der Tinte nachgemessen, neu gesetzt: ≤ ½ Zelle (Selbsttest).
2. **Colorway je Puppe** (`orbit_sparks_colors`, `KD.zoom_sparks`, Palette je Zelle in `styles.render` nur für die
   Sternebene): Puppe j ≥ 1 in Station j, die letzte gilt für alle tieferen. Schrift/Glühen/Abdimmen stehen in der Colorway
   der Puppe, die gerade das Bild deckt. Liste = dunklere Stationen der Farbreise ab der Endfarbe `~P23/P13`, absteigend
   nach Grundhelligkeit, dann `BW` (neue Pseudo-Station Schwarz-Weiß). **Befund:** dunkle Colorways allein machten das
   Bild nicht dunkler (Sterne malen in den hohen Stufen; Beat 8–13 hellgrau) → zusätzlich `orbit_sparks_dim` (Puppe j malt
   mit dim^j, 0.85; Puppe 0 bitgleich). Die 10 Colorways sind bei O10 bis Beat ~7.5 durch, danach Graustufen ins Schwarze.
3. **Endbild blankes Schwarz**: BW-Palette, Abschluss kippt in Stufe 0 = #000. Report misst den Anteil #000 außerhalb der
   Schrift (`finale_check`).
4. **Pixel-Effekt statt Kristall** (`orbit_words_effect`; Kristall + `crystal_order` gelöscht): **sparkle** (a) jede Zelle
   setzt zu einem festen Zufallszeitpunkt ein und leuchtet `flash_frac` lang in der hellsten Stufe; **ripple** (b) Ring +
   3 Nachläufer laufen von der Wortmitte nach außen (Front ~ t^0.8 wie `motionpack._ripple`), zünden Funken, außen
   verlöschen sie, im Wort bleibt, was die Front überstrichen hat. Selbsttest: monoton, am Ende ganzer Begriff, keine Funken
   mehr; Gegenproben (neuer Zufall je Bild bzw. die Funken außen) schlagen an.
5. **Tempo** des Einsetzens: `tempo.mp4`, T1 1/6+1/8 Beat, T2 1/3+1/4 (= O10), T3 1/2+3/8, T4 ohne Fade
   (`orbit_words_fade_beats = 0`: Pixel landen direkt in der Tinte, keine Difference-Phase). Vadim wählt.
6. **Kerning (a)**: `styles.KERN = {"PA": -0.15}` (alle Plakate, Druck). **Befund Lesbarkeit (6 + 7 zusammen):** Mittel
   0.814 → 0.803, 0/64 in Stufe A (O9 3/64), min unverändert 0.38 (Plakat 43). Getrennt an Plakat 29/61 (0.95 → 0.86/0.87):
   Kerning allein −0.03/−0.04, Kippen je Zeile allein −0.08 (einzelne Buchstaben auf Hellem kippen nicht mehr mit).
7. **Kippen je Zeile überall**: `KL.flip_glyphs` gelöscht, Plakate kippen KICK-OFF/Datum je Zeile (`flip_word`), in
   `kickoff.py` Datum und beide Kopfzeilen je Zeile (`flip_lines`).
8. **Tempo Ende**: `orbit_loop_speedup` 1.6 → 1.3, `orbit_zoom_max_per_frame` 1.5 → 1.3, Gipfel Beat 4 → 2.5, danach
   x0.7/Beat (O9 0.75): ~12 statt ~31 Puppen bis zum Abschluss (in S33-Einheiten 33 statt 89). Bahn-Check clean.
   Befund: der Check zählte jedes Bremsen im 2-Beat-Fenster als „langsamer“, also auch den gewollten Abfall nach einem
   früheren Gipfel → Messfenster endet am Gipfel (geprüft wird der Übergang).
9. **Weg zur Bildmitte** (`target_path`, `orbit_dive_target_ease` = 3): Tempo v0 (1 − u^p)², startet mit dem Bahntempo
   ohne Ruck und kommt mit Tempo **und** Bremsung 0 an (Hermite: Tempo fiel linear auf 0, am Ziel voller Ruck), Dauer
   1.56 statt 2 x Abstand/Tempo. Querausgleich u(1−u)³(1+3u) (erst u(1−u)³ bremste sofort: Tempo am Wechsel x0.60,
   jetzt x0.83, O9 x0.70; Knick 3.6° statt 8.4°).
10. **Spin**: Puppe j ist um j x `orbit_sparks_spin_deg` (8°) gedreht.
11. **O10c Begriff zoomt mit**: jeder Begriff hängt an der Puppe, die bei seinem Einsatz `zoom_from_px` (40) Radius
    hat, Versalhöhe 0.2 x Puppenradius, Oberkante 0.35 x Puppenradius unter der Mitte → wächst nur nach unten, nie in
    SPARK. Befund: mit dem ruhigen Zoom von O10 (x0.7/Beat) blieb ROBOTICS bis zum Schluss stehen → O10c zoomt nach dem
    Gipfel mit x0.9/Beat (~24 Puppen, dim 0.92), jeder Begriff ist ~1 Beat im Bild. Der letzte wächst aus der Mitte
    (Ease-out) und bleibt; fliegende Begriffe wachsen nach dem Abschluss weiter, bis sie raus sind.

**Offen / Fragen an Vadim:** a, b oder c? Tempo T1–T4? Glühen jetzt auf dunklem Grund ansehen (Befund: es überstrahlt
KICK-OFF/Datum zwischen Beat 4 und dem Abschluss). Colorways schneller durch als gedacht (bis Beat ~7.5) – Liste
kürzen/strecken? O7/test.toml lädt nicht mehr (`orbit_dive_target_ease` fehlt).

## Übergabe O10 (2.10. abends, Vadims Urteil zu O9, umgesetzt in Finale O10 oben)

Start: `previz/review/O9/O9.toml` → `O10/O10.toml`. Mehrere Versionen gewünscht, wo unten „Versionen“ steht.
1. **Begriffe mittig und zentral** im Bild (waagerecht und senkrecht), nicht mehr an der QR-Stelle.
2. **Colorway je Zoom-Puppe**: jede neue Puppe eine andere Colorway (alle aus der Farbreise), Tendenz immer dunkler,
   bis die Schrift ganz hell ist und alles bei **Schwarz** landet. Vadim: das Glühen ist in den Farben nicht gut,
   „vielleicht ändert sich das mit dem Untergang ins Dunkle“ → danach neu ansehen.
3. **Endbild: blankes Schwarz**, kein Stern, kein Korn, nur helle Schrift (Farbe komplett weg).
4. **Pixel-Effekt statt Kristall**: Referenz `pack/gif/color_red*` (die Ripples, Farbe egal). Vadim findet beide Deutungen
   gut → **Versionen**: (a) zufällige Pixel im Wort leuchten einzeln nacheinander auf, (b) Funken im Feld um das Wort,
   außen verlöschen sie, im Wort bleiben sie (Ripple wie in der Referenz).
5. **Tempo des Einblendens**: **Versionen** (schneller / langsamer / ohne Fade), Vadim wählt.
6. **Kerning (a)**: `styles.KERN = {"PA": -0.15}`, Wortbreite mittig (wirkt auf alle Plakate + Druck, Cache kalt,
   Lesbarkeit neu messen).
7. **Kippen je Zeile überall**, wo heute pro Buchstabe gekippt wird (`flip_glyphs` → je Zeile `flip_word`, auch auf den
   64 Plakaten und in `kickoff.py`). Pixelgenaues Kippen (SPARK, `title_value`) bleibt.
8. **Tempo**: letzter Loop beschleunigt zu stark (`orbit_loop_speedup` 1.6 runter), Zoom zu schnell und zu lange schnell →
   Deckel tiefer und früher abbremsen (`orbit_zoom_peak_beats` vor 4). Bahn-Check muss clean bleiben.
9. **Mitte rechts → Bildmitte** ist zu sichtbar und hat kein Ease-out („sieht komisch aus“): Hermite fällt linear auf 0;
   weicher auslaufen und/oder kürzer.
10. **Ein bisschen Spin**: jede neue Puppe leicht gedreht (Versatz je Puppe), damit die Drehung nicht abrupt aufhört.
11. **Weitere Version „Begriff zoomt mit“**: kein Pixel-Effekt, jeder Begriff kommt aus der Tiefe, sitzt in seiner Puppe und
    wächst mit ihr, fliegt nach **unten** aus dem Bild (nicht in die Wortmarke SPARK), der nächste folgt.

## Finale O9 (2.10. abends, Urteil umgesetzt in O10 oben, archiviert)

`archiv/review/alt/O9/` (`preview.mp4`, `orbit.png`, Report), `O9.toml` = O8 + Vadims Urteil zu O8. O8 → `archiv/review/alt/O8/`
(lädt mit dem neuen Code nicht mehr: `orbit_new_*` sind durch `orbit_words*` ersetzt). Video 6 Takte = 17.6 s.
1. **JOIN US geht mit dem QR** (`orbit_dissolve = ["qr", "cta"]`).
2. **Begriffe pro Beat** an der QR-Stelle, je Beat einer ersetzt den vorigen (harter Wechsel auf dem Beat), der letzte bleibt:
   ROBOTICS, DRONES, AUTONOMOUS / ROBOTS, ROBOT FIGHTS, SENSORS, ELECTRONICS, 3D PRINTING, SOLDERING, dann
   NEW SEMESTER, / NEW PROJECTS (ab Beat 13). Takt: 6 Takte reichen für 8 Begriffe ab Beat 5 (QR fertig 4.5); 11 hätten erst
   bei Beat 14.5 geendet (Video endet 16). PCB DESIGN, FIRMWARE stehen nur im Kommentar. `orbit_words` = Liste von
   Zeilen-Listen, `orbit_words_at_beats`/`_beats`/`_grow_beats`/`_fade_beats`.
3. **Kristallisieren** (`crystal_order`): je Buchstabe ein Keim, Wachstum über kürzeste Wege durch den Buchstaben mit
   zufälligen Zellkosten (skimage `MCP_Geometric`), Buchstaben versetzt. 1/3 Beat als Difference (`KL.title_value`),
   dann 1/4 Beat Fade in die Tinte (`flip_word`). Selbsttest: monoton, höchstens so viele Inseln wie Buchstaben (12/12),
   am Ende ganze Maske; Gegenprobe Bayer-Einblenden 1144 Inseln.
4. **Zoom**: Befund O8 je Bild: die Rate stieg bis 40 S33-Puppen pro Bild (= „direkt unscharf“), die Seitenbewegung fiel
   am Wechsel 86 → 39 px/Bild. Neu `orbit_zoom_max_per_frame` 1.5 (Deckel), Gipfel Beat 4, danach x0.75/Beat. Der Deckel
   muss über dem Tempo der Bahn am Wechsel liegen (dort schon x1.26/Bild); x1.25 ließ den Bildfluss 231 → 142 fallen,
   x1.5 hält ihn über dem Wert am Wechsel (242 → 306, Landen der Mitte 258). Bahn-Check: mit Deckel gilt „Fluss nie unter
   dem am Wechsel“ statt streng monoton, am Deckel halten zählt nicht als Bremsen.
   **Matrjoschka aus allen Sternen** (`orbit_sparks`, `KD.zoom_sparks`): Puppe j = Stern j mit Radius R x
   `orbit_sparks_ratio`^j (0.26 = Kern der S33, dort setzt Puppe 1 auf F1 ein), Puppe 0 = S33, von außen nach innen gemalt,
   jede auf ihre Silhouette beschnitten; neue Puppen wachsen ab 2 Zellen aus dem Punkt. 19 Sterne (alle aus dem Zyklus,
   je einmal). Keine Bewegungsunschärfe (Verschluss 0). Gate „Sterne pro Bild ≤ 0.5“: 0.30, Gegenprobe ohne Deckel 38.
   Zweitlicht der Labor-Sterne fällt im Zoom weg. S31e brach bildfüllend ab (`lab_spark.shafts` maß einen leeren Rand):
   misst dann über alles, Plakate bitgleich (Tabelle O8 = O9).
5. **Glühen bleibt**: hält den bis zum Gipfel erreichten Wert bis zum Abschluss (`rate_hold`), `orbit_glow_frames` 2.
6. **Kein Kippen pro Buchstabe** im Ende: KICK-OFF und Datum kippen je Zeile als Ganzes (`KL.type_layers`, nur mit
   `zoom`, Plakate unverändert). Befund am Bild: auf unruhigem Grund (Zoom-Puppen, Abdimmen) wird eine Zeile dadurch
   zeitweise schwach; Schlussbild 0.97 A.
7. **Kerning P–A**: `styles.KERN` (Kernpaare Clash in Versalhöhen, `line_mask` + `width_per_cap`), **leer = heute**.
   Befund (Versalhöhe 200 px, engster Abstand): P–A −0.15 → 14 px (S–P 13). Titel wird dadurch 42 → 43 Zellen hoch.
   Bogen `previz/variants/kern.png`: heute / (a) Kasten mittig / (b) Achse des A mittig. (b) bräuchte noch Code in
   `KL.line_masks` (heute nur im Bogen). Wirkt auf alle Plakate und den Druck → Vadim wählt.

**Fragen an Vadim:** Begriffe und Reihenfolge, 8 statt 10 ok? Kerning a / b / so lassen? Kippen je Zeile auch auf den
64 Plakaten (heute pro Buchstabe)? Matrjoschka-Tempo (Deckel, Gipfel, Abklingen) und Puppenabstand 0.26?

Parallel offen: **Druckmarken fertig, nicht gemergt**: Branch `worktree-agent-a242633ca97527a0e` (Commit 21b027b,
gepusht), `src/kickoff_loop_marks.py` + `[marks]` in loop.toml + Abschnitt „Druckmarken“ in seiner CLAUDE.md. Verfahren:
2x2-Zellquadrate leicht +/− (je Gruppe ausgeglichen), halb festes Lagemuster, halb Code aus der Frame-Nummer; QR und
Glühen frei; nur `print`, Video bitgleich. Gegengeprüft 2.10.: `kickoff_loop.py test` grün, `kickoff_loop_marks.py test`
ok (64/64 Nummern, Eckfehler max 0.26 % < 0.5 %, Sichtbarkeit bei 1 m max ΔE 0.012 < JND 0.02, QR 64/64,
Gegenproben schlagen an). Annahme Druckermodell (3 % Schwarz, Punktzuwachs) → **ein Testdruck + Handyfoto + `align`**
vor dem Großdruck. Merge: `git merge worktree-agent-a242633ca97527a0e` (Probe-Merge 2.10. per `git merge-tree`: konfliktfrei).
**Steganografie/Schnitzeljagd**: in der Session 2.10. nicht
gebaut, ein Sicherheitsfilter hat den Auftrag blockiert. Vadim entscheidet, wie es weitergeht.

## Finale O8 (2.10., Urteil umgesetzt in O9 oben, archiviert)

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
| `orbit_words`, `_at_beats` | Finale: Begriffe mittig, ab diesem Beat (Takt: `orbit_words_slots`) | O11: 21 Begriffe, 5 |
| `orbit_zoom_max_per_frame` | Deckel der Zoomrate (Maßstab pro Bild) | O9: 1.5 |
| `orbit_sparks` | O12: Stile der kleinen Sterne je Begriff (zyklisch) | 19 Sterne |
| `orbit_close_at_beats`, `_beats` | Finale: Abschluss (Zoom kippt in den Grund) | 9, 1 |
| `orbit_dive_target_ease`, `orbit_dive_vortex_deg` | Weg der Mitte ins Ziel: Tempo v0 (1 − u^p)², größer = kürzer; Vortex-Runde in Grad um das Ziel | O11: 2, 360 |
| `orbit_wall_r_frac` | O12: Zoom sättigt weich, Eintauch-Stern endet bei so viel x Bildbreite (Hintergrund) | 4 |
| `orbit_stop_r_frac`, `_grow_frac` | O12: kleiner Stern je Begriff in der Mitte, Radius x Bildbreite, Wachstum über den Slot (auf Zweiern) | 0.22, 0.15 |
| `orbit_words_slots` | [[Anzahl, Beats je Begriff], ...], Anzahlen = Begriffe | O11a [[3, 1], [18, 0.5]], O11b [[21, 0.5]] |
| `orbit_words_in_frac`, `_fade_frac`, `_out_frac`, `_flash_frac` | Anteile des Slots: einpixeln, Difference → Tinte (0 = direkt Tinte), auspixeln; Aufleuchten je Pixel | 0.35, 0.2, 0.3, 0.25 |


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
| `uv run src/kickoff_loop.py frames` / `variants` / `boil` / `print` / `resolve` | Frames rendern / QR-Varianten / Boil-Test / Druck-PDFs (mit Druckmarken) / Resolve-Bausteine | |
| `uv run src/kickoff_loop_photos.py` / `test` | Campus-Fotos `photos/raw/` → `photos/aligned/NN.png` + Bögen + Report / Selbsttest Farbausgleich | ~1 min (neue Fotos ~4 s je Stück) / ~3 s |
| `uv run src/kickoff_loop_marks.py test` | Selbsttest Druckmarken → `previz/marks/` | ~160 s |
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

## Druckmarken (2.10., `src/kickoff_loop_marks.py`, `[marks]` in `loop.toml`)

Vadim: „unsichtbare Marken auf Plakaten und Frames, damit du sie später leichter anordnen kannst, fürs Auge nicht groß
sichtbar". Nur im Druck (`print` → `_print_job` → `marks.print_image`), nie im Video: Vorschau-Renders und Cache
bleiben bitgleich (65 Renders alt/neu verglichen), Video-Code unberührt.

- **Verfahren:** Chips à 2 × 2 Zellen, je ±, in 2×2-Blöcken ausgeglichen. Jede Palettenfarbe wird im Chip + / − um einen
  Hub verschoben, symmetrisch im linearen Licht (aus Abstand mischt das Auge die Basis zurück). Hub je Farbe: Richtung
  mit dem meisten Kamerasignal (Blau minus Gelb), begrenzt auf `amp_ok` nach dem Augenfilter (S-CIELAB, 1 m), auf dem
  Ausdruck UND am Bildschirm. Am Gamut-Rand (Fast-Schwarz, B = 255) schiebt die Basis bis `tone_ok` nach innen.
  Halb Sync (alle Frames gleich → Lage), halb Code (Seed = Frame-Nummer → Nummer). QR + Ruhezone + Glühen bleiben frei.
- **Erkennen:** QR lesen → affin aus 3 Ecken → ECC an der QR-Platte (Perspektive) → Marke vom Plakat trennen (Zelle minus
  gleichfarbige Nachbarn) → Sync in 35 Feldern → Homographie (RANSAC, 2×) → Nummer (z gegen 64 Codes). Bei < 30 Feldern
  zusätzlich ECC am Render der erkannten Nummer (`polish`, nur übernommen, wenn es passt).
- **Befund Selbsttest** (64 Frames, simuliert: ±20° Perspektive, Plakat 0.28–0.40 der Höhe in 12 MP, Unschärfe σ bis
  2.5 px + Verwacklung bis 4 px, Rauschen, WB ±15 %, Farbrausch-Filter, JPEG q80, Ausdruck mit Schwarz 3 %/Papier 88 %):
  Nummer 64/64 (z min 19, Gate 8, Zufall max 4.3) · Eckfehler max 0.26 %, Mittel 0.09 % der Plakatbreite (Gate 0.5 %;
  nur Marken max 0.80 % bei Frame 40, deshalb `polish`) · Sichtbarkeit aus 1 m max 0.0105 (Ausdruck) / 0.0120
  (Bildschirm) ΔE OK, Mittel 0.003, JND 0.02 · aus 30 cm max 0.015 · QR 64/64 · align-Korrelation min 0.95 ·
  Gegenproben: ohne Marken 8/8 abgelehnt, falsche Nummer 8/8 erkannt. Bericht `previz/marks/report.txt`,
  Vergleich `previz/marks/compare.png` (Frame 1/21/45: ohne | mit | 400 % ohne | mit | Differenz ×10).
- **Befunde unterwegs:** Fixe Blau-Gelb-Achse trägt nichts auf Farben mit B = 255 (Frame 57) → Richtung je Farbe.
  Gegenläufige Richtungen löschen sich im Dither aus → eine Kamera-Achse. Gauß-Hochpass: z 17–48, bilateral
  (gleichfarbige Nachbarn): 64–90. Marken im QR-Glühen → `check_qr` fiel bei Frame 1/6 durch. Fast-Schwarz trägt im
  Druck praktisch nichts (0.1 DN im Foto) → dunkle Frames leben von Titel/Stern. QR-Hochrechnung affin 6–28 % daneben,
  mit ECC 0.2–3 %. Vadim 2.10.: „Fotos nicht pixelgenau ohne Blur" → Unschärfe σ 2.5 + Verwacklung in die Simulation.
- **Befehle:** `uv run src/kickoff_loop.py print` (Druck-PDFs mit Marken) · Fotos: `uv run src/kickoff_loop_photos.py` ·
  `uv run src/kickoff_loop_marks.py test [N..]` (~160 s für alle).
- **Offen (Vadim):** Druck nur mit den Dateien aus `print` (nicht neu exportieren/skalieren lassen, A4 = dieselbe Datei
  verkleinert ist ok). `loop.toml` nach dem Druck ändern → Nummer + Lage bleiben (Marken), nur `polish` greift nicht.
  Druckermodell (Schwarz 3 %, Tonwertzunahme) ist angenommen: ein Probedruck + Handyfoto + `align` bestätigt es.

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
- Ort steht seit 6.10.: `kickoff.COPY["where"] = "D-SCHOOL"` (Vadim: d-school, Erdgeschoss; ohne Kurzform nur
  „d-school“), dritte Zeile unter dem Datum auf allen 64. Endkarte (`card_info`) ungenutzt, solange das Ende `orbit` ist.
- Sterne-Agent: das alte Korn mischt mit der Stufe darunter, auf der Split-Naht (Stufe 3) entsteht so Flieder/Oliv
  (Rot+Blau, Gelb+Blau). S56–S60 halten das Korn in einer Colorway; alte Sterne ungeprüft.
- Auf F1–4/F29–32 liegt die ganze Seite im Stern: Effekte außerhalb sind dort unsichtbar (nur S58 trägt auf F1).

- **Campus-Plakate** als eigenes Konzept (z. B. die stärksten Loop-Frames). Plätze: 18 × A4 hoch, 56 × A3 hoch, 10 × A4 quer.
- Campus-Fotos: ja, das Video zeigt echte Fotos (6.10., Abschnitt „Campus-Fotos“).
- Resolve-Stern-Editor kennt 32 Frames und leere Frames noch nicht.
- 9:16-Sicherheitszonen der Endkarte (Reels-UI unten/rechts).
- `SV_LABEL_CELLS` in `lab_spark.py` spiegelt `[qr]` (Versalhöhe 9 + Abstand 4). Ändert sich JOIN US, dort nachziehen.
