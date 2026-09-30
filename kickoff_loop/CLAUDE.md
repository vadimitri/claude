# Kick-off Loop · SPARK Kick-off 14.10., 17:00

Session-Start: diese Datei, dann `previz/index.html` (neueste Version oben) und `loop.toml`.
Regeln fürs ganze Pack (Ordner, Code, Git): `../CLAUDE.md`. Designsystem (Codes P/S/K, Dither, Taste): Skill `spark-motion`.

## Vision (Vadim, 30.9. abends, Stand v005)

- Die Plakate **sind** die Animation: 48 Frames = ein Loop. Jeder zweite Frame ist ein **Aushang** (hängt auf dem Campus),
  die anderen sind **Fotoframes** (nur fürs Video gedruckt und fotografiert, „fake it till we make it"). Kleine Sterne
  sind ok: die fernen Frames sind Fotoframes.
- **Bumerang**: der Stern fliegt einmal um den Betrachter: groß links rein, klein in die Tiefe, groß rechts raus. Der Stern
  ist **immer frontal** (keine Kippung, keine Achsdrehung, Vadim: „absolute Katastrophe"), er dreht sich nur in der Bildebene.
  Die Bahn soll Vadim in **Resolve per Keyframes** selbst setzen können; Python zieht sie heraus und rendert die Plakate.
- **Farbreise**: benachbarte Frames unterscheiden sich farblich nur wenig; über den Loop wandert die Farbe einmal im Kreis.
- **Titelblock steht**: SPARK + KICK-OFF + Datum in jedem Frame exakt gleich (kein Wachsen, nichts verrutscht).
- **QR als Caption-Box** (Spider-Verse): harte Karte, 1 Zelle Rand, Farbversatz-Schatten. Kein Hof, kein Glühen.
- **12 verschiedene Sternstile** im Zyklus (Stil wechselt alle 2 Frames), S36 „Schmelze" raus.
- **Video**: Song = **IGOR'S THEME im Original ab 22.435 s**, alles auf dessen Raster (81.61 BPM). Kamera zoomt vom ersten
  Frame an gleichmäßig, rollt leicht, stößt auf jedem Drum-Hit nach vorn. Takt 1 (nur Drone) Plakate auf Achteln, ab den
  Drums auf 16teln. ½ Beat vor dem Bass-Boom (Takt 5) **bricht der Stern aus dem Papier** (24 fps statt Stop-Motion),
  auf dem Boom ein **Impact-Frame** (Negativ), dann **Endkarte als Hypno-Loop** (XOR-Nest-Tunnel im Sternfenster, 24 fps).
  Video endet auf Taktstrich 7 (17.6 s).
- Inspiration: Spider-Man: Into the Spider-Verse (`ref/spiderverse/README.md`, Board `board.png`): Frame-Raten-Wechsel,
  Impact-Frame, Caption-Box, Farbversatz statt Blur.

## Begriffe (so reden wir miteinander)

| Begriff | Bedeutung |
|---|---|
| **Frame** | ein Bild des Loops = ein Plakatmotiv, Nummer 1–48 (nur intern, steht nicht auf dem Plakat) |
| **Aushang** | Frame mit ungerader Nummer (1, 3 … 47): wird gedruckt und hängt auf dem Campus. 24 Stück |
| **Fotoframe** (früher Zwischenframe) | gerade Nummer: einmal gedruckt, kurz aufgehängt, fotografiert, wieder ab. Nur fürs Video |
| **Loop** / **Umlauf** | Frame 1 → 48, auf 16teln bei 81.61 BPM = 3 Takte = 8.8 s |
| **Karussell** | wie der Loop im Video abläuft (`cadence`); endet immer auf dem letzten Frame |
| **Stern** („der Spark") | die sechszackige Form. Nicht verwechseln mit dem **Titel** („SPARK", das Wort) |
| **Titelblock** | SPARK + KICK-OFF + Datum |
| **Bahn** / **Bumerang** | der Weg des Sterns (`[spark]`, gerechnet oder aus Resolve) |
| **Stern-Editor** | Resolve-Projekt `SPARK_Kickoff_Loop`, Timeline `Stern-Bahn`: 1 Timeline-Frame = 1 Plakat-Frame |
| **Stil** (S-Code) | wie der Stern gezeichnet ist (S7 Nest, S2 Verlauf …); wechselt alle 2 Frames |
| **Farbreise**, **Station** | Farbwechsel über den Loop; Station = reine Colorway (P-Code), dazwischen Mischungen |
| **Caption-Box** | die harte Karte um JOIN US + QR (ersetzt den alten „Hof") |
| **Platte** | ein Foto (oder die Simulation), entzerrt, Plakat immer an derselben Stelle |
| **Zoom** | Kamerafahrt von „Plakat klein an der Wand" bis „Plakat füllt das Bild" |
| **Ausbruch** | Stern fliegt aus dem letzten Plakat auf die Kamera zu, bis er das Bild füllt (24 fps) |
| **Impact** | 2 Negativ-Frames genau auf dem Bass-Boom |
| **Endkarte** / **Hypno-Loop** | 9:16-Satz, XOR-Nest-Tunnel im Sternfenster, Titel/Datum/QR setzen auf 16teln ein |
| **Version** (v005) | ein Vorschau-Lauf in `previz/vNNN/` mit Video, Bogen, Report und Kopie der `loop.toml` |

## Pipeline und Stand

```
Bahn (orbit oder Resolve) ─▶ Frames ─▶ Druck A3 ─▶ Aufhängen + Fotos ─▶ Entzerren ─▶ Video ─▶ Resolve ─▶ Export
✓ gerechnet / Editor         ✓ v005     ✓ print    Vadim               offen        ✓ Sim.   Bausteine
```

| Befehl (aus dem Pack-Root) | Ergebnis |
|---|---|
| `uv run src/kickoff_loop.py preview` | neue Version `previz/vNNN/`: `preview.mp4` (Video + Song), `loop.mp4` (nur Frames), `music.wav`, `contact.png`, `report.txt` (Checks), Kopie der `loop.toml` |
| `uv run src/kickoff_loop.py frames` | nur Frames rendern + QR/Lesbarkeit ausgeben |
| `uv run src/kickoff_loop.py test` | Selbsttest am fertigen Bild: Verlauf pro Zeile, QR, QR-Box hart + Ruhezone, SPARK zentriert, Titel fix, Stationen, Lila-Test |
| `uv run src/kickoff_loop.py variants 1 9 27` | QR-Box-Varianten nebeneinander → `previz/variants/qr_box_sheet.png` |
| `uv run src/kickoff_loop.py print` | Druck-PDFs A3 300 dpi (img2pdf, verlustfrei) → `print/`: `aushang_NN.pdf` mit Rückseite „BITTE NICHT ABHÄNGEN", `foto_NN.pdf` einseitig; QR in Druckauflösung geprüft |
| `uv run src/kickoff_loop.py resolve` | Schnitt-Bausteine → `resolve/`: `plates/NN.png`, `digital.mov`, `camera.mov` (ProRes), `song.wav`, `timeline.json` (Schnittpunkte, Kamera, Marker) |
| `uv run src/kickoff_loop_resolve.py push / pull / check` | Stern-Editor in Resolve anlegen / Vadims Keyframes nach `star_path.json` ziehen / Rundreise prüfen. Danach `[spark].source = "resolve"` |
| `uv run src/kickoff_loop.py gallery` | `previz/index.html` neu bauen |

Abhängigkeiten im Skriptkopf (PEP 723). Fonts: Clash Display in `~/Library/Fonts`. Ein Lauf ~2 min (Frames gecacht in `_cache/`).

## Ordner

| Pfad | Inhalt | Git |
|---|---|---|
| `loop.toml` | **alle Stellschrauben**, kommentiert, Einheiten im Namen | ja |
| `star_path.json` | Bahn aus Resolve (`pull`), gilt bei `[spark].source = "resolve"` | ja |
| `ref/picks_2026-09-26/` | Vadims Picks aus dem Kick-off-Raster | ja |
| `ref/audio/igor_beats.json`, `igor_analysis.png` | Songraster (BPM, Taktstriche, Hits ab Einstieg) + Prüfbild | ja |
| `ref/audio/igors_theme.mp3`, `igor_from22.wav` | Song und Ausschnitt ab 22.435 s (48 kHz, unverändert) | nein |
| `ref/spiderverse/` | Spider-Verse-Techniken (README im Git, Board + Stills nicht) | teils |
| `previz/vNNN/` | jede Vorschau als Version; `report.txt` + `loop.toml` im Git, Medien nicht | teils |
| `previz/variants/` | Detailvergleiche zum Entscheiden | nein |
| `photos/raw/`, `photos/aligned/NN.png` | Fotos, entzerrt (ersetzen in der Vorschau automatisch die Simulation) | nein |
| `print/`, `_cache/` | Druckdateien, gerenderte Frames | nein |
| `resolve/` | `RECIPE.md` (Resolve-Scripting, geprüft/ungeprüft markiert) im Git, Bausteine nicht | teils |

Code: `src/kickoff_loop.py` (Konfiguration, Farbreise, Bahn, Satz, Caption-Box, Rendern, Druck, Selbsttest),
`src/kickoff_loop_video.py` (Zeitachse auf dem Songraster, Kamera, Platten + Grading, Ausbruch/Impact/Hypno-Endkarte,
Blitz-Check, Vorschau, Resolve-Export), `src/kickoff_loop_resolve.py` (Stern-Editor in Resolve). Neue Stile S44–S47,
S31g, S18d in `src/lab_spark.py`, der Tunnel im Nest (`nest_phase`) in `src/styles.py`.
Der Synth-Nachbau (v003, `kickoff_loop_audio.py`) ist gelöscht, steht in Commit e1bd6e1.

## Entscheidungen (mit Befund)

| Datum | Entscheidung | Warum |
|---|---|---|
| 30.9. | Farbreise P11 → P13 → P10 → P19 → P18 → P14 → P20 → P15 → zurück, OKLab pro Stufe | max. Schritt 0.020 (OKLab); andere Reihenfolgen wurden fliederfarben; `is_lilac` prüft jede Mischung in `load`. Vadim: „Farbübergang gut" |
| 30.9. | Papier-Colorways (P16 P21–P24) raus aus dem Loop | eine helle Station mitten in dunklen würde auf dem Weg grau |
| 30.9. | Stern ist **6-zackig**, Drehung pro Loop Vielfaches von 60° | Profil gemessen (60°-symmetrisch); 72°/Loop gab 12° Sprung am Neustart |
| 30.9. | **Stern immer frontal** (Kipp-Scheibe `styles.tilt` gebaut und wieder entfernt) | Vadim zu v004: „der Spark soll sich nicht in 3D bewegen … absolute Katastrophe", Bewegung selbst „cool" |
| 30.9. | Bahn: fern Radius 0.20 (vorher 0.54), `far_rush_frac` 0.7, `height` 0.33 | Vadim: „kleinere Sparks"; mit 0.22 lag Frame 3 mit Spitze im Datum (0.94), mit 0.33 alle 48 ≥ 0.96 |
| 30.9. | **48 Frames** (24 Aushänge + 24 Fotoframes) | Vadim: „mehr Frames"; 48 = 3 Takte in 16teln, 6 Frames pro Station |
| 30.9. | **Titel fix** (Titelwachstum + simulierter Foto-Versatz raus) | Vadim: „die Titel bewegen sich ganz komisch, verschieben sich"; Selbsttest vergleicht die Satzmasken von Frame 9 und 48 |
| 30.9. | **Caption-Box E2** (harte Karte, Rand 1 Zelle, Schatten [3, 3] in Stufe 3) statt Hof | Vadim zum Hof: „als hätte es ein Dreijähriger gemalt"; Schatten in Stufe 0 verschwand auf dunklem Grund (sichtbar 23/32 statt 32/32) |
| 30.9. | Stil-Zyklus: S31g S26 S45 S46 S23 S33 S7 S18d S19d S44 S47 S2 | 12 verschiedene, alle frontal silhouettentreu. Raus: S36 (Vadim), S13/S14/S24/S40/S31–S31f (Silhouette/Lesbarkeit, z. B. S31 0.84). S26 auf F3 (S45 0.93, S46 0.94 dort) |
| 30.9. | Letzter Frame voller Körper (S2) | er wird im Ausbruch bildfüllend; mit Ringen (S33) Blitz-Check 40 % der Fläche, mit S2 16 % (Grenze 25 %) |
| 30.9. | **Song im Original** ab 22.435 s statt Synth-Nachbau | Vadim: „IGOR-Song komplett übernehmen ab Sekunde 22, mit dem Beat". 22.0 s liegt zwischen zwei 16teln, 22.435 = Taktstrich (Start Drum-Loop). Raster 81.61 BPM, Fehler 19 ms RMS |
| 30.9. | Impact auf Taktstrich 5 (11.76 s), Karussell davor 1 Takt Achtel + 3 Takte 16tel | stärkste Eins im Fenster (Loop-Neustart, Bass-Boom, Beat-RMS +6.7 dB); Takt 1 ist nur Drone |
| 30.9. | Kamera: exponentieller Zoom + Rollen −4° → 0° + Stoß 5 % auf jedem Drum-Hit | Vadim: „zu wenig Bewegung"; Rollen endet waagerecht, damit der Wechsel ins Digitale pixelgenau bleibt |
| 30.9. | Digitalteil 24 fps: Ausbruch ½ Beat, 2 Negativ-Frames, Hypno-Endkarte | Vadim: „Framerate der digitalen Version ganz nice", dort keine Achsdrehung, „Hypno-Loop"; Tunnel im Sternfenster, sonst wuchs er über das Datum („14.1▯.") |
| 30.9. | Grading: Umgebung jeder Platte auf mittlere Helligkeit 0.22 | Blitz-Check v003 ohne: 45 % der Fläche, mit: 12 % |
| 30.9. | Resolve: Keyframes nur über Fusion (TimelineItem-API kennt keine), Bahn wird aus der Fusion-Comp gelesen | `resolve/RECIPE.md`; Stern-Editor statt Resolve-Rendering der Plakate, weil nur Python Pixelraster + Dither exakt hält |

## Checks (stehen in jedem `report.txt`)

- **QR**: jeder Frame wird dekodiert (OpenCV, mehrere Modulgrößen), beim Druck in Druckauflösung.
- **Lesbarkeit** Titel+Datum (`kickoff.legible`): alle Frames und die Endkarte Stufe A (≥ 0.95).
- **Blitz** (WCAG 2.3.1, vereinfacht): ≤ 3 Blitze/s auf ≤ 25 % der Fläche, über das ganze Video. Rot-Regel fehlt noch.
- **Lila**: keine Mischung der Farbreise im Flieder-Bereich (`load` bricht ab).
- **Selbsttest** (`test`): Verlauf pro Zeile, QR, Caption-Box zellgenau + Ruhezone, SPARK zentriert, Titel fix, Stationen.

## Druck und Aushang

- Alle Frames sind A3 hoch (Seitenverhältnis √2): dieselben Dateien drucken auch A4 hoch ohne Umbau.
- Plätze laut Vadim: 18 × A4 hoch, 56 × A3 hoch, 10 × A4 quer (quer gibt es noch nicht). Lieber mehrere Exemplare der
  Aushänge hängen als mehr Motive.
- `print`: Aushänge als 2-seitige PDFs (Duplex, Rückseite „BITTE NICHT ABHÄNGEN"), Fotoframes einseitig. Vollformat ohne
  Rand (296.7 × 419.6 mm bei 300 dpi): Drucker mit Rand skaliert leicht, der QR bleibt lesbar (in Druckauflösung geprüft).

## Fotos: Anleitung fürs Shooting

- **Hochformat**, Hauptkamera 1x (kein Weitwinkel), höchste Auflösung. Plakat **mittig**, ~1/3 der Fotohöhe, gerade von vorn.
- **Fotoframe am Ort seines Aushangs fotografieren** (kurz darüberhängen): Ort und Stil wechseln dann halb so oft wie
  Farbe und Stern. Ruhiger und weniger Blitz als 48 verschiedene Orte.
- Kein Blitz, keine Spiegelung. Belichtung darf schwanken, das Grading (`surround_luma`) gleicht die Umgebung an.
- Pro Frame 3–5 Fotos, Name `NN_…` (NN = Framenummer laut `report.txt`). Originale zusätzlich im Vault sichern.

## Offen, in dieser Reihenfolge

1. Vadim: Bahn im Stern-Editor prüfen/ändern → `pull` → `[spark].source = "resolve"` → `preview`. Ort
   (`kickoff.COPY["where"]`) für die Endkarte fehlt noch.
2. `print` laufen lassen, **Testdruck** von 2–3 Extremen (großer Stern angeschnitten, ferner Stern, S45 Ben-Day-Raster).
3. `align`: Fotos entzerren (Merkmalsabgleich gegen den Render, Homographie; Rückfall: 4 Ecken von Hand).
4. Resolve-Schnitt aus `resolve/` (Platten → echte Fotos, Relink über gleiche Dateinamen), Song-Pegel: Ausschnitt hat
   −9.2 LUFS, Vorschau normalisiert auf −14.
5. 9:16-Sicherheitszonen (Reels-UI deckt unten/rechts ab) für die Endkarte prüfen.
6. Instagram: Originalsong im Reel kann stumm geschaltet werden; notfalls den Song über Instagrams Musikauswahl anlegen.

## Bekannte Grenzen

- Die Wände in der Vorschau sind erfunden; echte Fotos in `photos/aligned/` ersetzen sie automatisch.
- Plakatwechsel liegen auf 16teln des Songs (4.41 Timeline-Frames); jeder Wechsel wird für sich auf ganze Frames gerundet.
