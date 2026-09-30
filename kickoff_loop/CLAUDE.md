# Kick-off Loop · SPARK Kick-off 14.10., 17:00

Session-Start: diese Datei (zuerst **Übergabe**), dann `loop.toml`, dann `uv run src/kickoff_loop.py sheet` (zeigt den
Stand in ~10 s). Regeln fürs ganze Pack (Ordner, Code, Git): `../CLAUDE.md`. Designsystem und Verworfenes: Skill `spark-motion`.

## Übergabe 1.10. abends — hier weitermachen

**Große Entscheidung:** Die echten Plakate sind **komplett vom Video getrennt**. Für den Video-Loop gelten die
Druck-Regeln nicht mehr: kein Wechsel Aushang/Fotoframe, kein Frame muss allein tragen, leere Frames sind ok, nichts wird
pro Frame fotografiert. Die Campus-Plakate werden separat gemacht (Konzept offen, siehe Offen).

**Gewählt (Vadim):**
- **Farbe C1**: 32 Frames pro Loop, eine gemischte Farbreise über alle dunklen Colorways außer P6.
  Vorlage: `previz/review/C1.toml`. Vadim will das aber „verrückter, wir sind zu zahm". Der Farb-Agent hat dazu
  C1b/C1c/C1d gebaut (Branch `worktree-agent-a32df95e98bda0733`, Bögen in `previz/review/`), Urteil offen.
- **Tempo T16**: 16.32 Plakate/s = 32tel-Triolen auf IGOR (81.6 BPM). Ein Loop (32 Frames) = 1⅓ Takte, also
  3 Loops = 4 Takte. Der Neustart liegt nur jeden 3. Loop auf der Eins. Vergleich: `previz/review/tempo_T*.mp4`
  (alle Bahnen nebeneinander, IGOR ab 22.435 s darunter).
- **Bahn: Ellipse um den Betrachter**, Stern an den Seiten riesig, in der Mitte klein. Hinter dem Kopf ist er
  weg, und zwar so lange, wie es sich echt anfühlt. `orbit()` mit `width`/`ahead`/`kepler_frac`, siehe `[spark]`.
  **Welche Variante, ist offen**: B15–B20 (`previz/review/C1_B*.toml`, Bögen + `tempo_T16.mp4`). B18 = B15 mit
  angehobener Bahn, dort bleiben die Riesen seitlich im Bild statt unten herauszufallen.
- **Sterne**: S50 kommt rein. S51 → S51b. S48 (→ S48b/c, chromatische Aberration) und S54 (→ S54b, Handskizze) sind
  überarbeitet. Bögen `previz/review/S_rework_1.png`, `S_rework_2*.png`, Branch `worktree-agent-ad5a3c216a0aab393`.
  Urteil zur Überarbeitung offen.

**Als Nächstes, in dieser Reihenfolge:**
1. Beide Agent-Branches mergen (`git merge worktree-agent-…`). Der Welten-Code des Farb-Agenten ist schon drin
   (Commit 7e65046). In `lab_spark.py/c_lampe` hat der Hauptzweig eine Zeile geändert (leerer Saum).
2. Vadim wählt B (B15–B20) und die Farbvariante (C1/C1b–d) und die Sterne. Dann in `loop.toml` übernehmen:
   `[loop].frames = 32`, `[color]` aus der Farbvariante, `[spark]` aus B, `[styles].hold_frames = 4`.
3. **Leere Frames im Code nachziehen**, bevor `preview` läuft:
   - `kickoff_loop_video.digital_style` nimmt `star_at(n - 1)`. Ist der letzte Frame leer (Radius 0), teilt
     `1 / r0` durch null. Der Ausbruch muss vom **letzten Frame mit Stern** starten, das Karussell dort enden.
   - Stile nur auf Frames mit Stern verteilen: Heute bekommen leere Frames einen Stil, der dann fehlt.
   - Leere Frames rendern heute einen winzigen S2-Stern außerhalb (`OFF_STAR`), weil Labor-Stile am Stern messen.
4. Lesbarkeit der Riesenframes: B17–B20 liegen bei 0.90–0.93, der Riesenstern liegt über SPARK/KICK-OFF. Über Bahn
   oder Satz lösen, Gate bleibt 0.95.
5. Zeitachse auf T16: Das Musik-Raster kennt nur 16tel-Teiler (`load`: `16 % per`). 32tel-Triolen = 24 Wechsel pro
   Takt, `carousel_bars` und die Prüfung müssen das können. Blitz-Check bei 16 Plakaten/s neu messen (C1 wechselt
   die Farbe jedes Frame).
6. Musik nur IGOR (alte Übergabe 3) und Endkarte neu (alte Übergabe 4) sind unverändert offen.

**Arbeitsweise heute (hat getragen):** Varianten als vollständige TOML-Kopie in `previz/review/`, gerendert mit
`sheet <datei>.toml` (~10 s, öffnet Bogen + Loop). Vadim schaut im Finder und antwortet mit Codes. Veraltetes kommt
nach `previz/review/alt/`, nicht löschen. Agenten in eigenen Worktrees, Stände per Patch/Merge herüberholen.
Befund zuerst rechnen, dann rendern: Die Bahn-Suche lief als Skript über die Parameter (sichtbarer Anteil,
Radius pro Frame, leere Frames). Das ging schneller als Bögen raten.

**Stern-Editor in Resolve** (Details `resolve/EDITOR.md`): Projekt `SPARK_Kickoff_Loop`, Timeline `Stern-Bahn`, 1 Timeline-Frame
= 1 Plakat-Frame. `push`/`pull`/`check` laufen, sind aber am Bild noch nicht bestätigt. **Die Frame-Zahl ist jetzt 16:** vor der
Nutzung `push --force` (überschreibt Keys). Resolve ist Editor und Schnitt, Python bleibt Renderer (nur Python hält Pixelraster,
Bayer und Palette exakt).

## Vision (Stand 1.10. abends)

- **Video-Loop und Plakate sind getrennt.** Der Loop ist reines Video (32 Frames, T16), die Campus-Plakate kommen eigens.
- **Bumerang als Ellipse**: Der Stern kommt links riesig herein (von hinten am Ohr vorbei), fliegt in die Tiefe (klein),
  kommt rechts riesig zurück und ist hinter dem Kopf weg. Die Zeit dort ist echt. Er ist **immer frontal** (keine Kippung,
  „absolute Katastrophe") und dreht sich nur in der Bildebene.
- **Farbe**: interdimensional, möglichst alle Colorways (C1: eine Reise über 32 Frames), gern verrückter.
- **Titelblock steht**: SPARK + KICK-OFF + Datum in jedem Frame exakt gleich.
- **QR glüht ein**: helle Platte mit 1 Modul Ruhezone, Lichtabfall ins Plakat. JOIN US frei, kippt pro Buchstabe hell/dunkel.
- **8 Sternstile** im Zyklus (+ S50, S51b …), letzter Frame mit Stern voller Körper (S2) für den Ausbruch.
- **Video**: Das Karussell läuft mehrmals durch, die Kamera zoomt, rollt leicht und stößt auf den Hits nach vorn. Am Ende
  **bricht der Stern aus dem Papier** (24 fps), auf dem Drop kommt der **Impact** (Negativ), dann die Endkarte (neu).
  Musik: nur IGOR, Custom-Mashup.
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
| `uv run src/kickoff_loop.py sheet kickoff_loop/previz/review/X.toml` | dasselbe für eine Variante (volle Kopie der `loop.toml`) → `previz/review/X_contact.png`, `X_loop.mp4` | ~10 s |
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
| `previz/review/` | **aktuelle Varianten** für Vadim: `<Code>.toml` (im Git) + Bogen/Loop, `tempo_T*.mp4`, `S_rework_*`; Veraltetes in `alt/` | toml ja |
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
| 1.10. | **Plakate und Video getrennt** | Vadim: „wir trennen echte Plakate vom Video komplett, also lösen sich da einige constraints". Leere Frames ok („drucke ja sowieso einige Plakate nur für das Video") |
| 1.10. | **Bahn: Ellipse** (`width`, `ahead`, `kepler_frac`), Stern größer als sein Vorbeiflug-Abstand | Befund (Skript, 32 Frames): perspektivisch korrekt (Kepler, B4–B10) ist der Stern nur 1 Frame pro Seite groß, eine gleichmäßige Kreisbahn läuft 6–8 von 16 Frames leer. Vadim: „an den Seiten riesig … elliptisch" und „man fühlt, wenn der Spark nicht genug Zeit hatte" → Comic-Größe, echte Zeit |
| 1.10. | ~~B9/B10~~ (größer über Brennweite) verworfen | Vadim: „sieht praktisch flach aus". Tiefe = Größenverhältnis nah/fern, dort nur ×2.5 statt ×4 und mehr |
| 1.10. | ~~Bahn diagonal/senkrecht (B11–B13), Tiefenbumerang (B14)~~ | Vadim: „wir bleiben beim normalen Loop". `plane_roll_deg` bleibt als Regler (0) |
| 1.10. | **Farbe C1** (32 Frames, eine Reise), nicht C2 (Welt pro Durchgang) / C3 (4 Welten im Loop) | Vadim: „C1 am besten, gerne verrückter". P6 fliegt raus: sein Magenta dithert mit Schwarz zu Lila (Farb-Agent, `load` prüft jetzt jedes Plakat) |
| 1.10. | **Tempo T16** = 16.32 Plakate/s (32tel-Triolen auf IGOR) | aus T8/T12/T16/T24 mit IGOR darunter (`previz/review/tempo_T*.mp4`) |
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

0. **Übergabe oben**, Schritte 1–6.
1. **Campus-Plakate** als eigenes Konzept. Denkbar: die stärksten Loop-Frames als Aushänge, ohne Parität und ohne Fotoframes.
   Plätze laut Vadim: 18 × A4 hoch, 56 × A3 hoch, 10 × A4 quer.
2. Ort (`kickoff.COPY["where"]`) fehlt noch (für Endkarte und Plakate).
3. `print` + Testdruck der Extreme, sobald die Plakate stehen.
4. Resolve-Schnitt aus `resolve/`. Der Stern-Editor (`kickoff_loop_resolve.py`) nutzt `orbit()`, leere Frames (Radius 0)
   dort noch nicht geprüft.
5. 9:16-Sicherheitszonen (die Reels-UI deckt unten/rechts ab) für die Endkarte prüfen.
6. `align` (Fotos entzerren) nur noch, falls das Video doch echte Fotos zeigt.

## Bekannte Grenzen

- Die Wände in der Vorschau sind erfunden. Echte Fotos in `photos/aligned/` ersetzen sie automatisch.
- Plakatwechsel liegen auf 16teln der Musik (120 BPM: 3 Timeline-Frames, 81.6 BPM: 4.41). Jeder Wechsel wird für sich gerundet.
- `SV_LABEL_CELLS` in `lab_spark.py` (`_qr_zone`: Aussparung um JOIN US + QR für die neuen Sterne, z. B. S50) spiegelt
  `[qr]` (Versalhöhe 9 + Abstand 4). Ändert sich JOIN US, dort nachziehen.
