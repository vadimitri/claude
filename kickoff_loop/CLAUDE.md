# Kick-off Loop · SPARK Kick-off 14.10., 17:00

Session-Start: diese Datei, dann `previz/index.html` (neueste Version oben) und `loop.toml`.
Regeln fürs ganze Pack (Ordner, Code, Git): `../CLAUDE.md`. Designsystem (Codes P/S/K, Dither, Taste): Skill `spark-motion`.

## Vision (Vadim, 30.9., Stand v003)

- Die Plakate **sind** die Animation: 32 Frames = ein Loop. Jeder zweite Frame ist ein **Aushang** (hängt auf dem Campus),
  die anderen sind **Zwischenframes** (nur fürs Video gedruckt und fotografiert). Jeder Frame muss allein gut aussehen.
- **Bumerang**: der Stern kreist einmal um den Betrachter. Er kommt hinten links (am linken Ohr vorbei) ins Bild, fliegt
  in die Tiefe, kehrt um, kommt auf einen zu und verlässt das Bild rechts. Der Sprung von rechts nach links zwischen
  Frame 32 und 1 ist der Flug hinter dem Kopf = der sichtbare Neustart des Karussells. Nie viel Leerraum.
- **Farbreise**: benachbarte Frames unterscheiden sich farblich nur wenig; über den Loop wandert die Farbe einmal im Kreis.
- **Titel wächst**: SPARK (mit KICK-OFF + Datum) beginnt auf Frame 1 etwas kleiner und wächst bis Frame 32 auf den
  Standardsatz; SPARK steht waagerecht zentriert. Keine Kopfzeile, keine Nummern, keine Farbnamen.
- **QR eingebettet**: JOIN US + QR stehen, wie sie sind; nur ihr heller Grund läuft weich, rund, in eigenem Dither aus.
- **Video**: Kamera zoomt vom ersten Frame an gleichmäßig, bis das Plakat das Bild füllt; das Karussell bremst nur leicht
  und endet immer auf Frame 32. Dann **Wechsel ins Digitale**: das Plakat klappt ins 9:16-Bild auf (Titel hoch, QR runter),
  der Stern kehrt zurück, fliegt auf einen zu und wird riesig. Synth-Hit auf dem Wechsel.
- **Musik**: der Intro-Synth aus IGOR'S THEME (Tyler, The Creator), nachgebaut aus Messwerten, kein Sample.
- Schnitt in DaVinci Resolve; Claude liefert Bausteine, Exporte, Vorschauen. Jede Version wird gemessen (Checks).

## Begriffe (so reden wir miteinander)

| Begriff | Bedeutung |
|---|---|
| **Frame** | ein Bild des Loops = ein Plakatmotiv, Nummer 1–32 (nur intern, steht nicht auf dem Plakat) |
| **Aushang** | Frame mit ungerader Nummer (1, 3 … 31): wird gedruckt und hängt auf dem Campus. 16 Stück |
| **Zwischenframe** | gerade Nummer: einmal gedruckt, kurz aufgehängt, fotografiert, wieder ab. Nur fürs Video |
| **Loop** / **Umlauf** | Frame 1 → 32, bei 8 fps genau 4 s = 2 Takte |
| **Karussell** | wie der Loop im Video abläuft (`cadence`); endet immer auf Frame 32 |
| **Stern** ("der Spark") | die sechszackige Form. Nicht verwechseln mit dem **Titel** ("SPARK", das Wort) |
| **Titelblock** | SPARK + KICK-OFF + Datum |
| **Bahn** / **Bumerang** | der Weg des Sterns um den Betrachter (`[spark]`) |
| **Stil** (S-Code) | wie der Stern gezeichnet ist (S7 Nest, S2 Verlauf …); wechselt alle 2 Frames |
| **Farbreise**, **Station** | Farbwechsel über den Loop; Station = reine Colorway (P-Code), dazwischen Mischungen |
| **Hof** | der weich auslaufende helle Grund um JOIN US + QR |
| **Platte** | ein Foto (oder die Simulation), entzerrt, Plakat immer an derselben Stelle |
| **Zoom** | Kamerafahrt von „Plakat klein an der Wand" bis „Plakat füllt das Bild" |
| **Wechsel ins Digitale**, **Digitalteil** | ab Zoom-Ende rendert der Rechner weiter (24 fps, hängt nirgends) |
| **Endkarte** | der stehende Schluss des Digitalteils |
| **Version** (v003) | ein Vorschau-Lauf in `previz/vNNN/` mit Video, Bogen, Report und Kopie der `loop.toml` |

## Pipeline und Stand

```
loop.toml ─▶ Frames ─▶ Druck A3 ─▶ Aufhängen + Fotos ─▶ Entzerren ─▶ Video ─▶ Resolve ─▶ Export
             ✓ v003     offen      Vadim               offen        ✓ Sim.   offen
```

| Befehl (aus dem Pack-Root) | Ergebnis |
|---|---|
| `uv run src/kickoff_loop.py preview` | neue Version `previz/vNNN/`: `preview.mp4` (Video + Musik), `loop.mp4` (nur Frames), `music.wav`, `contact.png`, `report.txt` (Checks), Kopie der `loop.toml` |
| `uv run src/kickoff_loop.py variants 9` | Hof-Varianten von Frame 9 nebeneinander → `previz/variants/frame09.png` |
| `uv run src/kickoff_loop.py frames` | nur Frames rendern + QR/Lesbarkeit ausgeben |
| `uv run src/kickoff_loop.py test` | Selbsttest am fertigen Bild: Verlauf pro Zeile, QR, SPARK zentriert, Titelwachstum, Stationen, Lila-Test |
| `uv run src/kickoff_loop.py gallery` | `previz/index.html` neu bauen |

Abhängigkeiten im Skriptkopf (PEP 723). Fonts: Clash Display in `~/Library/Fonts`. Ein Lauf ~80 s (Frames gecacht in `_cache/`).

## Ordner

| Pfad | Inhalt | Git |
|---|---|---|
| `loop.toml` | **alle Stellschrauben**, kommentiert, Einheiten im Namen | ja |
| `ref/picks_2026-09-26/` | Vadims Picks aus dem Kick-off-Raster | ja |
| `ref/audio/igors_theme.mp3` | Referenz-Song (Kopie aus Downloads), nur zum Vermessen | nein |
| `previz/vNNN/` | jede Vorschau als Version; `report.txt` + `loop.toml` im Git, Medien nicht | teils |
| `previz/variants/` | Detailvergleiche zum Entscheiden | nein |
| `photos/raw/`, `photos/aligned/NN.png` | Fotos, entzerrt (ersetzen in der Vorschau automatisch die Simulation) | nein |
| `print/`, `resolve/`, `_cache/` | Druckdateien, Resolve-Übergabe, gerenderte Frames | nein |

Code: `src/kickoff_loop.py` (Konfiguration, Farbreise, Bahn, Satz, QR-Hof, Rendern, Selbsttest),
`src/kickoff_loop_video.py` (Zeitachse, Kamera, Platten + Grading, Digitalteil, Blitz-Check, Vorschau),
`src/kickoff_loop_audio.py` (Synth-Nachbau, Klicks, Swoosh, Hit). Nutzt `src/kickoff.py` (Layout, QR-Check, Lesbarkeit;
einzige Änderung: optionaler `title_scale`) und `src/styles.py` unverändert.

## Entscheidungen (mit Befund)

| Datum | Entscheidung | Warum |
|---|---|---|
| 30.9. | 32 Frames = 16 Aushänge + 16 Zwischenframes, 16tel bei 120 BPM = 2 Takte pro Loop | weniger Aushänge als Plätze (56 × A3 hoch, 18 × A4 hoch, Konkurrenz); flüssiger als 16 Frames |
| 30.9. | Farbreise P11 → P13 → P10 → P19 → P18 → P14 → P20 → P15 → zurück, OKLab pro Stufe | Stationen fallen auf Aushänge 1, 5 … 29; max. Schritt 0.020 (OKLab). Andere Reihenfolgen wurden fliederfarben (z. B. P17 → P20: `#A877A6`, P18 → P17: Lila); `is_lilac` (240–320°, s > 0.2) prüft jede Mischung in `load` |
| 30.9. | Hue-Bogen um Lila herum verworfen | ergibt Regenbogen-Sprünge innerhalb von 4 Frames (Cyan → Grün → Orange → Pink), widerspricht „kleine Farbschritte" |
| 30.9. | Papier-Colorways (P16 P21–P24) raus aus dem Loop | eine helle Station mitten in dunklen würde auf dem Weg grau |
| 30.9. | Bumerang: Kreisbahn im Raum, Zentralprojektion, Bogen −68° … +58°, Radius 0.54 (fern) bis 1.10 (nah) | Silhouetten-Test: mit kleinerem Stern 4–10 % Bühnenabdeckung (Leerraum); asymmetrischer Bogen, damit Frame 32 (Heldenbild vor dem Digitalteil) den Stern groß zeigt |
| 30.9. | Stern ist **6-zackig**, Drehung pro Loop Vielfaches von 60° | Profil gemessen (60°-symmetrisch, Abweichung 0.008); v002 drehte 72°/Loop = 12° Sprung am Neustart |
| 30.9. | Stile S7 S2 S19d S33 S36 S23 S26 im Zyklus, je 2 Frames | S13 streut Kindsterne über den Titel (Lesbarkeit 0.85, unter A); S2 fällt auf Frame 31/32 (voller Körper) |
| 30.9. | QR-Hof: abgerundetes Feld, Gauss-Auslauf 12 Zellen, leicht verbogen, Blue Noise | weichgezeichnete Platte las sich als helle Kachel mit Glührand („viereckig"); hell-auf-dunkel-JOIN-US zerfiel auf dem Stern |
| 30.9. | SPARK waagerecht zentriert, keine Kopfzeile | Vadim 30.9. |
| 30.9. | Zoom exponentiell ab 0 s ohne Kurve, Karussell 3 Takte 16tel + 1 Takt Achtel | Vadim: „kontinuierlich, nicht schneller werden"; Bremsen bis Halbe war zu langsam |
| 30.9. | **Grading**: Umgebung jeder Platte auf mittlere Helligkeit 0.22 | Blitz-Check v003 ohne: 45 % der Fläche (Grenze 25 %), Ursache: jeder Frame an einem anderen Ort. Mit: 12 % |
| 30.9. | Digitalteil: Satz gleitet vom Plakat in den 9:16-Satz, Stern landet mit einem Tal nach oben | mit Spitze nach oben stand sie im Datum („17:0 0"); Endkarte jetzt Lesbarkeit 0.97 A |
| 30.9. | Musik: IGOR-Intro additiv aus Messwerten nachgebaut (Obertöne 2:3:5 von 37.85 Hz, 3 Stimmen −5/0/+11 Cent, Rauschplateau) | Spektrumvergleich Original/Nachbau: gleiche Schwebungsblöcke im Bass; −14.1 LUFS |

## Checks (stehen in jedem `report.txt`)

- **QR**: jeder Frame wird dekodiert (OpenCV, mehrere Modulgrößen).
- **Lesbarkeit** Titel+Datum (`kickoff.legible`): alle Frames und die Endkarte Stufe A (≥ 0.95).
- **Blitz** (WCAG 2.3.1, vereinfacht): ≤ 3 Blitze/s auf ≤ 25 % der Fläche, über das ganze Video. Rot-Regel fehlt noch.
- **Lila**: keine Mischung der Farbreise im Flieder-Bereich (`load` bricht ab).
- **Selbsttest** (`test`): Verlauf pro Zeile, QR, SPARK zentriert, Titel wächst monoton, Stationen = Original-Paletten.

## Druck und Aushang

- Alle Frames sind A3 hoch (Seitenverhältnis √2): dieselben Dateien drucken auch A4 hoch ohne Umbau.
- Plätze laut Vadim: 18 × A4 hoch, 56 × A3 hoch, 10 × A4 quer (quer gibt es noch nicht). Konkurrenz um die Plätze:
  lieber mehr Exemplare der 16 Aushänge hängen (z. B. 2–3 je Motiv) als mehr Motive.
- Rückseite jedes Aushangs: „BITTE NICHT ABHÄNGEN" (Vadim). Kommt mit dem Druck-Schritt.
- Zwischenframes: je 1 Druck, nur fürs Foto.

## Fotos: Anleitung fürs Shooting

- **Hochformat**, Hauptkamera 1x (kein Weitwinkel), höchste Auflösung. Plakat **mittig**, ~1/3 der Fotohöhe, gerade von vorn.
- **Zwischenframe am Ort seines Aushangs fotografieren** (kurz darüberhängen): Ort und Stil wechseln dann mit 4 fps,
  Farbe und Stern mit 8 fps. Ruhiger und weniger Blitz als 32 verschiedene Orte.
- Kein Blitz, keine Spiegelung. Belichtung darf schwanken, das Grading (`surround_luma`) gleicht die Umgebung an.
- Pro Frame 3–5 Fotos, Name `NN_…` (NN = Framenummer laut `report.txt`). Originale zusätzlich im Vault sichern.

## Offen, in dieser Reihenfolge

1. Vadim entscheidet über v003: Bahn, Farbreise, Stil-Zyklus, Titel-Startgröße (`title_scale_start`), Hof, Digitalteil,
   Musik. Ort (`kickoff.COPY["where"]`) für die Endkarte fehlt noch.
2. `print`: Druckdateien A3 300 dpi mit QR-Check, Rückseite „BITTE NICHT ABHÄNGEN", **Testdruck** von 2–3 Extremen.
3. `align`: Fotos entzerren (Merkmalsabgleich gegen den Render, Homographie; Rückfall: 4 Ecken von Hand).
4. Musik v2: nach Vadims Hör-Eindruck (Tiefpass-Fahrt, Hit, Pegel Klicks/Swoosh), evtl. Drums nach dem Hit.
5. Resolve-Übergabe: Platten, Digitalteil (ProRes 4444), Musik, Timeline mit den Schnittpunkten aus `Timeline`.
6. 9:16-Sicherheitszonen (Reels-UI deckt unten/rechts ab) für die Endkarte prüfen.

## Bekannte Grenzen

- Die Wände in der Vorschau sind erfunden; echte Fotos in `photos/aligned/` ersetzen sie automatisch.
- Rauschplateau im Synth ist etwas körniger als im Original (dort dichte, verstimmte Obertöne statt Rauschen).
