# Kick-off Loop · SPARK Kick-off 14.10., 17:00

Session-Start: diese Datei (zuerst **Übergabe**), dann `loop.toml`, dann `uv run src/kickoff_loop.py sheet` (zeigt den
Stand in ~10 s). Regeln fürs ganze Pack (Ordner, Code, Git): `../CLAUDE.md`. Designsystem und Verworfenes: Skill `spark-motion`.

## Übergabe 1.10. — hier weitermachen

**Stand:** QR glüht (R2 Licht) ✓ · 8 Sterne gewählt ✓ · 16 Frames pro Loop, 3–5 Durchgänge ✓ · Zeitachse folgt dem
Musik-Raster ✓ · schnelle Befehle `sheet`/`stars`/`variants` ✓. Letzte Videos: `previz/v006` (Musik A), `v007` (Musik B).

**Vadims Feedback zu v006/v007, in dieser Reihenfolge.** Erst die Animation, dann die Musik, die Endkarte ganz am Ende:

1. **Der Loop ist nicht clean.** Im Video ist der Stern im ersten Frame schon groß links da und im letzten noch groß rechts.
   Er ist nie ganz außerhalb des Plakats, der Neustart springt von rechts nach links. Ziel: ein vollständiger Bumerang. Der
   Stern kommt von außerhalb ins Plakat und verlässt es wieder ganz.
   - Befund: `[spark].sweep_deg = [-78, 73]` ist nur der sichtbare Bogen. Frame 1 und 16 liegen darin schon groß am Rand,
     den Weg „hinter dem Kopf" gibt es als Frame gar nicht.
   - Wege: den Bogen verlängern, bis Frame 1/16 fast leer sind (nur eine Spitze ragt herein), oder eigene Ein-/Austritts-Frames.
   - Beachten: Ein Aushang (ungerade Nummer) ohne Stern trägt allein nicht. Also die leeren Frames auf Fotoframes legen.
   - Frame 2 liegt heute bei Lesbarkeit 0.95: eine Sternspitze sticht durch „KICK-OFF / 14.". Das auch über die Bahn lösen,
     nicht über die Stile (Befund des Sterne-Agenten).
   - Arbeiten mit `sheet` (Kontaktbogen + Plakat-Loop) und erst dann `preview`.
2. **Mehr Farbe, „es soll sich interdimensional anfühlen".** Vadim findet alle Colorways cool und will jede drin haben. Er
   meint, mit mehr Frames könne man sich mehr Farben erlauben.
   - Heute sind 8 Stationen drin, alle dunkel: P11 P13 P10 P19 P18 P14 P20 P15.
   - Nicht drin, dunkel: P6 CGA, P9 RED LASER, P17 SIGNAL FLARE, P25 AFTERHOURS, P26 PALETTE ZERO.
   - Nicht drin, hell (Papier): P16 FLUO PINK, P21 MINT, P22 SAFETY ORANGE, P23 ABSOLUTE ZERO, P24 HAZARD.
   - Fallen:
     - Hell zwischen Dunkel gemischt wird grau (Entscheidung 30.9.).
     - Manche OKLab-Mischungen werden lila (`is_lilac` in `load`).
     - Wechselt die Palette in jedem Frame bei 8 fps, blitzt es (Skill-Gotcha: 60 % der Fläche, Grenze 25 %, `flash_check`).
     - CGA-Paletten P6/P26 haben nur 4 Stufen und werden gedoppelt.
   - **Vor dem Bauen Vadim fragen, welche Form er meint:**
     - (a) mehr Frames pro Loop (z. B. 32 Frames = 16 Stationen), oder
     - (b) jeder Durchgang ist eine andere „Dimension": gleiche Bahn, eigenes Farbset. Zwischen den Durchgängen wird hart
       gewechselt, nicht gemischt, damit geht auch Hell ↔ Dunkel ohne Grau. Das ergibt mehr Plakate (4 × 16). (b) passt
       zu Spider-Verse, dort hat jede Welt ihre eigene Grafik.
   - Im README steht außerdem die Idee des Sterne-Agenten, jeden Stil an eine Welt/Colorway zu koppeln.
3. **Musik: nur IGOR, Custom-Mashup.** Der Maker-Night-Beat bleibt exklusiv für die Maker Night und fliegt aus dem Kick-off.
   Stattdessen ein eigenes Mashup aus IGOR'S THEME: Wo die Drums kommen, machen wir etwas Eigenes. **Erst, wenn die
   Animation fertig ist.**
   - Code: `src/kickoff_loop_music.py`. Es baut heute A/B mit Maker-Night-Drop; dieser Teil und `[mashup]` für die Maker
     Night fliegen raus.
   - Das Raster-Format bleibt: Die Timeline liest `sixteenth_s`, `carousel_bars`, `hits_s`, `burst_s`, `impact_s` und
     `end_s` aus dem JSON (`GRID_KEYS` in `kickoff_loop.py`).
4. **Endkarte ganz am Ende neu, in einer eigenen Session.** Vadim: keine Hypno-Endkarte. Die Varianten H1–H5 (Taktsog,
   Palettenringe, Gegenlauf) fand er „schrecklich", sie sind gebaut und wieder gelöscht. Die jetzige Endkarte (Nest-Tunnel)
   ist Platzhalter.

**Liegt offen, noch ohne Urteil von Vadim:**
- **Neue Sterne S48–S55** (Sterne-Agent, Recherche Spider-Verse ITSV/ATSV + Manga/Comic): Bogen `previz/variants/stars_neu.png`,
  je Code Idee/Quelle/Lesbarkeit in `ref/spiderverse/README.md`, Abschnitt „Neue Sterne (1.10., Agent)". Alle folgen der Bahn,
  QR 16/16. Agent-Sichtung: S50 Fokuslinien, S55 Halbton, S53 Spot am stärksten. Vadim wählen lassen, dann `[styles].cycle`.
- **Boil** (Test): `uv run src/kickoff_loop.py boil` → `previz/now/boil.mp4`, Digitalteil ohne | mit. Der Stern springt auf
  Zweiern 1 Zelle, das Bayer-Korn wandert mit (`[endcard].boil_*`, `styles.dither(shift=…)`). Das hängt an der neuen Endkarte,
  also ohne Vadims Ja nicht weiterbauen.

**Arbeitsweise, die funktioniert hat** (Vadim will sofort Feedback, „schnelle Iteration"):
- Standbilder vor Video. `sheet` braucht ~10 s, `variants`/`stars` ~15–25 s. `preview` (~1 min) erst nach Abnahme.
- Ergebnis immer mit `open` zeigen, Varianten mit Code beschriften (G1…, R2…). Vadim antwortet mit Codes („R2 Licht").
- Unabhängiges parallel an Subagenten geben, mit klaren Dateigrenzen: Musik → `kickoff_loop_music.py`, Stile → `lab_spark.py`.
- Vor Vorschlägen die Verworfen-Liste im Skill `spark-motion` lesen: S15–S28 waren schon raus und wurden trotzdem vorgeschlagen.
- Ein Selbsttest muss am alten Fehler nachweislich anschlagen. Dazu den Fehler kurz einbauen und den Test laufen lassen. Beim
  Glühen war der erste Test blind dafür.

**Stern-Editor in Resolve** (Details `resolve/EDITOR.md`): Projekt `SPARK_Kickoff_Loop`, Timeline `Stern-Bahn`, 1 Timeline-Frame
= 1 Plakat-Frame. `push`/`pull`/`check` laufen, sind aber am Bild noch nicht bestätigt. **Die Frame-Zahl ist jetzt 16:** vor der
Nutzung `push --force` (überschreibt Keys). Resolve ist Editor und Schnitt, Python bleibt Renderer (nur Python hält Pixelraster,
Bayer und Palette exakt).

## Vision (Stand 1.10.)

- Die Plakate **sind** die Animation: 16 Frames = ein Loop = 1 Takt in 16teln. Ungerade Nummern sind **Aushänge** (hängen auf dem
  Campus, 8 Stück), gerade sind **Fotoframes** (nur fürs Video gedruckt und fotografiert, „fake it till we make it").
- **Bumerang**: Der Stern fliegt einmal um den Betrachter, groß links rein, klein in die Tiefe, groß rechts raus. Er ist **immer
  frontal** (keine Kippung, keine Achsdrehung, „absolute Katastrophe") und dreht sich nur in der Bildebene. Offen: Er soll
  vollständig raus und rein (Übergabe 1).
- **Farbe**: interdimensional, möglichst alle Colorways (Übergabe 2). Benachbarte Frames bleiben nah beieinander.
- **Titelblock steht**: SPARK + KICK-OFF + Datum in jedem Frame exakt gleich.
- **QR glüht ein**: helle Platte mit 1 Modul Ruhezone, Lichtabfall ins Plakat. JOIN US frei, kippt pro Buchstabe hell/dunkel.
- **8 Sternstile** im Zyklus (Stil wechselt alle 2 Frames, Aushang + Fotoframe teilen ihn), letzter Frame voller Körper (S2).
- **Video**: Das Karussell läuft 3–5-mal durch. Die Kamera zoomt vom ersten Frame an, rollt leicht und stößt auf den Hits nach
  vorn. Am Ende des letzten Durchgangs **bricht der Stern aus dem Papier** (24 fps statt Stop-Motion), auf dem Drop kommt der
  **Impact** (Negativ), dann die Endkarte (neu, Übergabe 4). Musik: nur IGOR, Custom-Mashup (Übergabe 3).
- Inspiration: Spider-Man ITSV/ATSV (`ref/spiderverse/README.md`): Wechsel der Bildrate, Impact-Frame, Farbversatz statt Blur,
  jede Welt ihre eigene Grafik.

## Begriffe (so reden wir miteinander)

| Begriff | Bedeutung |
|---|---|
| **Frame** | ein Bild des Loops = ein Plakatmotiv, Nummer 1–16 (nur intern, steht nicht auf dem Plakat) |
| **Aushang** | Frame mit ungerader Nummer (1, 3 … 15): wird gedruckt und hängt auf dem Campus |
| **Fotoframe** | gerade Nummer: einmal gedruckt, kurz aufgehängt, fotografiert, wieder ab. Nur fürs Video |
| **Loop** / **Umlauf** / **Durchgang** | Frame 1 → 16 = 1 Takt in 16teln (120 BPM: 2 s, 81.6 BPM: 2.9 s) |
| **Karussell** | wie der Loop im Video abläuft (`carousel_bars` im Musik-Raster), endet immer auf dem letzten Frame |
| **Stern** („der Spark") | die sechszackige Form. Nicht verwechseln mit dem **Titel** („SPARK", das Wort) |
| **Titelblock** | SPARK + KICK-OFF + Datum |
| **Bahn** / **Bumerang** | der Weg des Sterns (`[spark]`, gerechnet oder aus Resolve) |
| **Stil** (S-Code) | wie der Stern gezeichnet ist (S7 Nest, S2 Verlauf …), wechselt alle 2 Frames |
| **Farbreise**, **Station** | Farbwechsel über den Loop. Station = reine Colorway (P-Code), dazwischen Mischungen in OKLab |
| **Glühen** | helle QR-Platte + Lichtabfall ins Plakat (`qr_glow`), ersetzt Caption-Box (v005) und Hof (v003) |
| **Platte** | ein Foto (oder die Simulation), entzerrt, Plakat immer an derselben Stelle |
| **Ausbruch** / **Impact** | Stern fliegt aus dem letzten Plakat auf die Kamera zu (½ Beat, 24 fps) / Negativ-Frames auf dem Drop |
| **Endkarte** | 9:16-Satz nach dem Impact. Heute Platzhalter (Nest-Tunnel), wird neu gemacht |
| **Boil** | Test: Stern und Korn zittern auf Zweiern um ganze Zellen (Zeichentrick im Pixelraster) |
| **Version** (v007) | ein Vorschau-Lauf in `previz/vNNN/` mit Video, Bogen, Report und Kopie der `loop.toml` |

## Befehle (aus dem Pack-Root)

| Befehl | Ergebnis | Dauer |
|---|---|---|
| `uv run src/kickoff_loop.py sheet` | **schnelle Runde**: Kontaktbogen + Plakat-Loop → `previz/now/`, öffnet beides | ~10 s |
| `uv run src/kickoff_loop.py stars [S..]` | Sterne-Bogen: jeder Stil an 3 Bahnstellen, Lesbarkeit → `previz/variants/stars.png` | ~25 s |
| `uv run src/kickoff_loop.py variants 1 9` | QR-Varianten (`VARIANTS` im Code) → `previz/variants/qr_sheet.png` + `frameNN.png` | ~15 s |
| `uv run src/kickoff_loop.py test [N..]` | Selbsttest am fertigen Bild (Standard Frames 3, 7, 9) | ~5 s |
| `uv run src/kickoff_loop.py frames` | nur Frames rendern + QR/Lesbarkeit ausgeben | ~10 s |
| `uv run src/kickoff_loop.py preview [A\|B]` | neue Version `previz/vNNN/`: `preview.mp4`, `loop.mp4`, `contact.png`, `report.txt`, `loop.toml`. A/B = Musikvariante statt `[music]` | ~1 min |
| `uv run src/kickoff_loop.py boil` | Test: Digitalteil ohne \| mit Boil → `previz/now/boil.mp4` | ~1 min |
| `uv run src/kickoff_loop.py print` | Druck-PDFs A3 300 dpi → `print/` (Aushänge mit Rückseite „BITTE NICHT ABHÄNGEN") | |
| `uv run src/kickoff_loop.py resolve` | Schnitt-Bausteine → `resolve/` (Platten, `digital.mov`, `camera.mov`, `song.wav`, `timeline.json`) | |
| `uv run src/kickoff_loop_music.py` | Musik + Raster → `ref/audio/mashup_{A,B}.wav/.json`, Hörversionen `previz/music/` | ~5 s |
| `uv run src/kickoff_loop_resolve.py push/pull/check` | Stern-Editor in Resolve (siehe Übergabe) | |

Frames sind nach Inhalt gecacht (`_cache/`, Schlüssel inkl. Hash aller `src/*.py`: jede Code-Änderung rendert neu, ~10 s).

## Ordner

| Pfad | Inhalt | Git |
|---|---|---|
| `loop.toml` | **alle Stellschrauben**, kommentiert, Einheiten im Namen | ja |
| `star_path.json` | Bahn aus Resolve (`pull`), gilt bei `[spark].source = "resolve"` (heute: `orbit`) | ja |
| `ref/picks_2026-09-26/` | Vadims Picks aus dem Kick-off-Raster | ja |
| `ref/audio/igor_beats.json`, `igor_analysis.png` | IGOR-Raster (81.61 BPM, Taktstriche, Hits ab 22.435 s) + Prüfbild | ja |
| `ref/audio/mashup_{A,B}.json` | Zeitraster der Musik (liest die Timeline) | ja |
| `ref/audio/igors_theme.mp3`, `mashup_*.wav` | Song, gebaute Musik | nein |
| `ref/spiderverse/` | README (Techniken, Recherche, neue Sterne) im Git; `board.png`, `img/` nicht | teils |
| `previz/vNNN/` | Vorschau-Versionen; `report.txt` + `loop.toml` im Git, Medien nicht | teils |
| `previz/now/` | Kratzfläche der schnellen Befehle (`sheet`, `boil`), wird überschrieben | nein |
| `previz/variants/` | Bögen zum Entscheiden (`qr_sheet`, `stars`, `stars_neu`) | nein |
| `previz/music/` | Hörversionen (m4a) + `report.txt` (Befunde Musik) | report ja |
| `photos/raw/`, `photos/aligned/NN.png` | Fotos, entzerrt (ersetzen in der Vorschau automatisch die Simulation) | nein |
| `print/`, `_cache/` | Druckdateien, gerenderte Frames | nein |
| `resolve/` | `RECIPE.md`, `EDITOR.md` im Git, Bausteine nicht | teils |

Code: `src/kickoff_loop.py` (Config, Farbreise, Bahn, Satz, QR-Glühen, Rendern, Bögen, Druck, Selbsttest),
`src/kickoff_loop_video.py` (Timeline aus dem Musik-Raster, Kamera, Platten + Grading, Ausbruch/Impact/Endkarte, Boil,
Blitz-Check, sheet/preview/export), `src/kickoff_loop_music.py` (Mashup + Raster), `src/kickoff_loop_resolve.py` (Stern-Editor).
Sterne: S2/S7/S33 in `src/styles.py`, Labor-Stile (S18d S19d S23 S31g S44–S55 …) in `src/lab_spark.py`, Register `kickoff.LAB`.

## Entscheidungen (mit Befund)

| Datum | Entscheidung | Warum |
|---|---|---|
| 1.10. | **QR glüht, R2 Licht**: Ruhezone 1 Modul (`quiet_cells` 2), Lichtabfall exponentiell über 12 Zellen, rund, JOIN US frei 4 Zellen darüber, kippt pro Buchstabe | Vadim wählte aus G1–G6 und dann R2–R6 („nicht so viel Padding"). Befund: Die Gauß-Kuppe liest sich als Box mit Saum, der Lichtabfall als Glühen. QR 16/16 lesbar auch mit 1 Modul, weil das Glühen hell ist |
| 1.10. | Selbsttest Glühen: pro Abstandsring nach außen nie heller (über 4 Ringe gemittelt, Bayer-Periode) **und alle Seiten gleich hell** | Der Ringtest allein ließ den verbeulten v003-Hof durch. Der Seitenvergleich schlägt an: 1.0–1.6 Stufen gegen eine Grenze von 0.6 |
| 1.10. | **16 Frames** pro Loop (8 Aushänge + 8 Fotoframes), Drehung 240° pro Loop (15°/Frame) | Vadim: „mehrere Durchgänge statt mehr Frames". Unter 30°/Frame, sonst liest das Auge die Drehung rückwärts |
| 1.10. | **8 Sterne**: S31g S23 S33 S18d S19d S45 S47 S2 (Reihenfolge von Vadim), geparkt S26 S46 S7 S44 | Sterne-Bogen. Alle 16 Frames ≥ 0.95 (Frame 2 = 0.95 knapp) |
| 1.10. | Labor-Stile S15–S20, S25, S28 nicht im Loop | Sie ignorieren die Bahn (feste Lage oder seitenfüllend), S25 braucht eine Zweitpalette je Colorway. Laut Skill ohnehin verworfen |
| 1.10. | Zeitachse aus dem Musik-Raster (JSON) statt `[video].cadence` / `[music].switch_bar` | Das Karussell folgt der Musik darunter. `load` prüft, dass `burst_beats` zur Luft vor dem Drop passt |
| 1.10. | Lautheit als feste Verstärkung auf −14 LUFS statt `loudnorm` | Der dynamische Regler drückte Aufbau → Drop platt (Musik B: Drop +6 dB) |
| 1.10. | ~~Maker-Night-Drop im Kick-off~~ **verworfen** | Vadim: Der Beat gehört exklusiv der Maker Night. Nur IGOR, Custom-Mashup (Übergabe 3) |
| 1.10. | ~~Hypno-Endkarte~~ **verworfen** | Vadim: „keine Hypno-Endkarte", Endkarte neu am Ende |
| 30.9. | Farbreise P11 → P13 → P10 → P19 → P18 → P14 → P20 → P15 → zurück, OKLab pro Stufe | andere Reihenfolgen wurden fliederfarben, `is_lilac` prüft jede Mischung in `load`. Vadim: „Farbübergang gut". Wird mit Übergabe 2 erweitert |
| 30.9. | Papier-Colorways (P16 P21–P24) raus aus dem Loop | Eine helle Station zwischen dunklen wird auf dem Weg grau. Vadim will sie jetzt doch (Übergabe 2): nur mit hartem Wechsel, nicht gemischt |
| 30.9. | Stern ist **6-zackig**, Drehung pro Loop ein Vielfaches von 60° | Profil gemessen (60°-symmetrisch). 72°/Loop gab 12° Sprung am Neustart |
| 30.9. | **Stern immer frontal** (Kipp-Scheibe gebaut und wieder entfernt) | Vadim zu v004: „absolute Katastrophe", die Bewegung selbst „cool" |
| 30.9. | Bahn: fern Radius 0.20, `far_rush_frac` 0.7, `height` 0.33 | Vadim: „kleinere Sparks". Mit 0.22 lag eine Spitze im Datum |
| 30.9. | **Titel fix** (kein Titelwachstum, kein simulierter Foto-Versatz) | Vadim: „die Titel bewegen sich ganz komisch". Der Selbsttest vergleicht die Satzmasken zweier Frames |
| 30.9. | ~~Caption-Box~~ (v005) und ~~verbeulter Hof~~ (v003) **verworfen** | Vadim: „keinen harten QR-Code" bzw. „als hätte es ein Dreijähriger gemalt". Nachfolger: Glühen R2 Licht |
| 30.9. | Letzter Frame voller Körper (S2) | Er wird im Ausbruch bildfüllend. Mit Ringen (S33) ergab der Blitz-Check 40 % der Fläche, mit S2 16 % (Grenze 25 %) |
| 30.9. | Kamera: exponentieller Zoom + Rollen −4° → 0° + Stoß 5 % auf jedem Hit | Vadim: „zu wenig Bewegung". Das Rollen endet waagerecht, damit der Wechsel ins Digitale pixelgenau bleibt |
| 30.9. | Digitalteil 24 fps: Ausbruch ½ Beat, 2 Negativ-Frames | Vadim: „Framerate der digitalen Version ganz nice". Dort keine Achsdrehung |
| 30.9. | Grading: Umgebung jeder Platte auf mittlere Helligkeit 0.22 | Blitz-Check v003 ohne: 45 % der Fläche, mit: 12 % |
| 30.9. | Resolve: Keyframes nur über Fusion, Stern-Editor statt Resolve-Rendering der Plakate | `resolve/RECIPE.md`. Nur Python hält Pixelraster + Dither exakt |

## Checks (stehen in jedem `report.txt`, `sheet` zeigt QR/Lesbarkeit)

- **QR**: Jeder Frame wird dekodiert (OpenCV, mehrere Modulgrößen), beim Druck in Druckauflösung.
- **Lesbarkeit** von Titel+Datum (`kickoff.legible`): alle Frames und die Endkarte in Stufe A (≥ 0.95).
- **Blitz** (WCAG 2.3.1, vereinfacht): ≤ 3 Blitze/s auf ≤ 25 % der Fläche, über das ganze Video. Die Rot-Regel fehlt noch.
- **Lila**: keine Mischung der Farbreise im Flieder-Bereich (`load` bricht ab).
- **Selbsttest** (`test`): Verlauf pro Zeile, QR, Ruhezone, Glühen geometrisch (Ringe + Seitenvergleich), SPARK zentriert,
  Titel fix, Stationen exakt, Lila-Test.

## Druck und Aushang

- Alle Frames sind A3 hoch (Seitenverhältnis √2), dieselben Dateien drucken auch A4 hoch.
- Plätze laut Vadim: 18 × A4 hoch, 56 × A3 hoch, 10 × A4 quer (quer gibt es noch nicht). Lieber mehrere Exemplare der Aushänge
  hängen als mehr Motive (heute 8 Aushänge).
- `print`: Aushänge als 2-seitige PDFs (Duplex, Rückseite „BITTE NICHT ABHÄNGEN"), Fotoframes einseitig, Vollformat ohne Rand.

## Fotos: Anleitung fürs Shooting

- **Hochformat**, Hauptkamera 1x, höchste Auflösung. Plakat **mittig**, ~1/3 der Fotohöhe, gerade von vorn.
- **Fotoframe am Ort seines Aushangs fotografieren** (kurz darüberhängen): Ort und Stil wechseln halb so oft wie Farbe und Stern.
- Kein Blitz, keine Spiegelung. Die Belichtung darf schwanken, das Grading (`surround_luma`) gleicht aus.
- Pro Frame 3–5 Fotos, Name `NN_…` (NN = Framenummer laut `report.txt`). Originale zusätzlich im Vault sichern.

## Offen, in dieser Reihenfolge

0. **Übergabe 1–4** oben: Loop clean (Bahn), Farbe interdimensional (erst Form klären), Musik nur IGOR, Endkarte neu.
1. Neue Sterne S48–S55 von Vadim bewerten lassen, `URTEIL` in `lab_spark.py` nachziehen.
2. Ort (`kickoff.COPY["where"]`) fehlt noch (für die Endkarte).
3. `print` + **Testdruck** von 2–3 Extremen (großer Stern angeschnitten, ferner Stern, S45 Ben-Day-Raster).
4. `align`: Fotos entzerren (Merkmalsabgleich gegen den Render, Homographie; Rückfall: 4 Ecken von Hand).
5. Resolve-Schnitt aus `resolve/` (Platten → echte Fotos, Relink über gleiche Dateinamen).
6. 9:16-Sicherheitszonen (die Reels-UI deckt unten/rechts ab) für die Endkarte prüfen.

## Bekannte Grenzen

- Die Wände in der Vorschau sind erfunden. Echte Fotos in `photos/aligned/` ersetzen sie automatisch.
- Plakatwechsel liegen auf 16teln der Musik (120 BPM: 3 Timeline-Frames, 81.6 BPM: 4.41). Jeder Wechsel wird für sich gerundet.
- `SV_LABEL_CELLS` in `lab_spark.py` (`_qr_zone`: Aussparung um JOIN US + QR für die neuen Sterne, z. B. S50) spiegelt
  `[qr]` (Versalhöhe 9 + Abstand 4). Ändert sich JOIN US, dort nachziehen.
