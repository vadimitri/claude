# Kick-off Loop · SPARK Kick-off 14.10., 17:00

Session-Start: diese Datei, dann `previz/index.html` (neueste Version oben) und `loop.toml`.
Regeln fürs ganze Pack (Ordner, Code, Git): `../CLAUDE.md`. Designsystem (Codes P/S/K, Dither, Taste): Skill `spark-motion`.

## Vision (Vadim, 30.9.)

- Die Plakate **sind** die Animation: 16 Plakate = 16 Frames eines Loops. Die Silhouette des Sterns ist auf allen gleich
  (er wächst und dreht sich von Frame zu Frame), Stil (S) und Colorway (P) wechseln: jede Karte eine Dimension (Spider-Verse).
  Titel, KICK-OFF, Datum und QR stehen auf allen Plakaten exakt gleich.
- Aufhängen auf dem ganzen Campus, jedes Plakat fotografieren, Fotos so entzerren, dass das Plakat immer an derselben Stelle
  liegt (Match Cut). Daraus ein Stop-Motion-Loop mit Musik und SFX; man soll sehen, dass er von vorn beginnt (Karussell).
- Die Kamera zoomt langsam hinein, bis das Plakat das Bild füllt, dann Wechsel in eine **digitale Endanimation** im selben
  Stil (hängt nicht, nur im Video) mit mehr Info (Ort, Zeit …) und einem Synth-Hit.
- Das Hex-Rätsel fliegt raus. Kopfzeile links jetzt `FRAME 07/16`.
- Schnitt in DaVinci Resolve (Timeline zum Anpassen); Claude liefert alle Bausteine, Exporte und Vorschauen.
- Anspruch: keine Fehler. Jede Version wird gemessen, nicht nur angeschaut (siehe Checks).

## Pipeline und Stand

```
loop.toml ─▶ Plakat-Frames ─▶ Druck A3 ─▶ Aufhängen + Fotos ─▶ Entzerren ─▶ Video ─▶ Resolve ─▶ Export
             ✓ Vorschau       offen        Vadim               offen        ✓ Simulation  offen
```

| Befehl (aus dem Pack-Root) | Ergebnis |
|---|---|
| `uv run src/kickoff_loop.py preview` | neue Version `previz/vNNN/`: `preview.mp4` (Video + Temp-Klick), `loop.mp4` (nur Plakate), `contact.png`, `report.txt` (Checks), Kopie der `loop.toml` |
| `uv run src/kickoff_loop.py variants 9` | Detailvarianten von Plakat 9 nebeneinander → `previz/variants/frame09.png` |
| `uv run src/kickoff_loop.py frames` | nur Plakate rendern + QR/Lesbarkeit ausgeben |
| `uv run src/kickoff_loop.py test` | Selbsttest am fertigen Bild: Verlauf pro Zeile + QR |
| `uv run src/kickoff_loop.py gallery` | `previz/index.html` neu bauen (z. B. nach dem Löschen einer Version) |

Abhängigkeiten stehen im Skriptkopf (PEP 723), `uv run` holt sie selbst. Fonts: Clash Display, DepartureMono in `~/Library/Fonts`.
Ein Lauf dauert ~35 s; Plakate sind nach Inhalt gecacht (`_cache/`), nur geänderte werden neu gerendert.

## Ordner

| Pfad | Inhalt | Git |
|---|---|---|
| `loop.toml` | **alle Stellschrauben**, kommentiert, Einheiten im Namen | ja |
| `ref/picks_2026-09-26/` | Vadims Picks aus dem Kick-off-Raster (vorher lose in Downloads/Desktop) | ja |
| `previz/vNNN/` | jede Vorschau als Version; `report.txt` + `loop.toml` im Git, Medien nicht | teils |
| `previz/variants/` | Detailvergleiche zum Entscheiden | nein |
| `photos/raw/` | Vadims Fotos, Name `NN_irgendwas.jpg` (NN = Plakatnummer) | nein |
| `photos/aligned/NN.png` | entzerrt, Plakat an fester Stelle; ersetzt in der Vorschau automatisch die Simulation | nein |
| `print/` | Druckdateien A3 300 dpi (kommt nach Freigabe) | nein |
| `resolve/` | Übergabe an Resolve: Platten, Endkarte (ProRes 4444), Musik, Timeline | nein |
| `_cache/` | gerenderte Plakate, jederzeit löschbar | nein |

Code: `src/kickoff_loop.py` (Konfiguration, Sterngeometrie, Plakatsatz, Rendern, Varianten, Selbsttest),
`src/kickoff_loop_video.py` (Zeitachse, Kamera, Simulation, Endkarte, Blitz-Check, Temp-Ton, Vorschau).
Nutzt `src/kickoff.py` (Layout, QR-Check, Lesbarkeit) und `src/styles.py` (Paletten, Dither, Raster) unverändert.

## Entscheidungen (mit Befund)

| Datum | Entscheidung | Warum |
|---|---|---|
| 30.9. | 16 Plakate, Wechsel in 16teln bei 120 BPM = 1 Takt pro Loop | Loop sitzt auf dem Musikraster; 8 fps = sichtbar Stop-Motion |
| 30.9. | **Karussell bremst**: `cadence` 2 Takte 16tel → 8tel → Viertel → Halbe, dann Endkarte | Blitz-Check: bildfüllend bei 8 fps blitzen 60 % der Fläche (Grenze 25 %), beste Reihenfolge immer noch 46 %, erst 4 fps = 8 %. Bremsen baut außerdem Spannung auf |
| 30.9. | Stern: Mitte 0.58/0.76, Radius 0.30 → 0.90, 72° pro Loop, `ease_out` | Lesbarkeit Titel+Datum auf allen 16 Stufe A (≥ 0.95); mit 0.60/0.66 → 0.98 fielen 7 Plakate auf B |
| 30.9. | Nur Stile mit stabiler Silhouette: S2 S7 S33 S19d S23 S26 S36 (S13, S31e/f bedingt) | Test gleiche Lage, alle Stile: S14 S24 S40 zeigen keinen Stern, S31–S31d fluten das ganze Plakat mit Licht |
| 30.9. | Papier-Colorways (P16 P22 P23) als Block am Loop-Ende | nur zwei Hell/Dunkel-Sprünge pro Loop |
| 30.9. | Verlauf pro Zeile, von Grundlinie bis Versalhöhe, 1 Palettenstufe | alter Bug: das Verlaufsband der Datumszeile reichte 1.4 Versalhöhen hoch, KICK-OFF fing unten wieder hell an (gemessen: unterste Reihen 100 % hellste Stufe); `test` fängt ihn |
| 30.9. | Zoom-Ende = 4 px pro Zelle | exakt das R3-Raster des Systems → Wechsel Foto → digital pixelgenau; 44 px Anschnitt je Seite liegen im 7-%-Rand |

**Vorschläge, warten auf Vadim** (Vergleich: `previz/variants/frame09.png`):
QR als **Karte** (JOIN US + QR auf einer hellen Fläche, harte Kante, kein Halo) oder **Band** (dunkles Band in Plattenbreite);
Verlauf **1.0** oder **1.4** Stufen; Kopfzeile `FRAME 07/16`.

## Checks (stehen in jedem `report.txt`)

- **QR**: jedes Plakat wird dekodiert (OpenCV, mehrere Modulgrößen), Vorschau und später Druck.
- **Lesbarkeit** Titel+Datum (`kickoff.legible`, 0..1): alle Plakate Stufe A (≥ 0.95), sie hängen sichtbar.
- **Blitz** (WCAG 2.3.1, vereinfacht, auf 1/16-Auflösung): ≤ 3 Blitze/s auf ≤ 25 % der Fläche. Die Rot-Regel fehlt noch.
- **Selbsttest** (`test`): Verlauf pro Zeile an beiden Enden flächig, nach unten nie heller; schlägt am alten Plakat an.

## Fotos: Anleitung fürs Shooting

Die Vorschau zeigt, was die Kamera am Anfang braucht: das Plakat ist 38 % der Bildhöhe, drumherum ~2 Plakatbreiten Umgebung.
- **Hochformat**, Hauptkamera 1x (kein Weitwinkel, der verzerrt), höchste Auflösung (48 MP).
- Plakat **mittig**, ungefähr **1/3 der Fotohöhe**, gerade von vorn, Kamera auf Plakatmitte. Lieber zu viel Umgebung als zu wenig.
- Kein Blitz, keine Spiegelung/Glanz auf dem Plakat; Licht darf von Ort zu Ort anders sein (das sind die Dimensionen).
- Pro Plakat 3–5 Fotos, Name `NN_…` (NN = Plakatnummer oben links). Originale zusätzlich im Vault sichern.

## Offen, in dieser Reihenfolge

1. Vadim entscheidet: QR-Variante, Verlauf, Kopfzeile, Reihenfolge/Stile, Anzahl Plakate, Ort (`kickoff.COPY["where"]`), Format (9:16?), Song.
2. `print`: Druckdateien A3 300 dpi mit QR-Check, **Testdruck** von 2–3 Extremen (Neon-Paletten liegen außerhalb CMYK).
3. `align`: Fotos entzerren (Merkmalsabgleich gegen den digitalen Render, Homographie; Rückfall: 4 Ecken von Hand).
4. Endkarte gestalten (heute Platzhalter: letztes Plakat digital, Ränder in Grundfarbe).
5. Musik + SFX auf den Wechseln (Klick-Spur zeigt das Raster), Synth-Hit auf dem Wechsel ins Digitale.
6. Resolve-Übergabe: Platten, Endkarte, Musik, Timeline mit den Schnittpunkten aus `Timeline` (Weg per API/FCPXML klären).

## Bekannte Grenzen

- Die Wände in der Vorschau sind erfunden (Platzhalter); echte Fotos in `photos/aligned/` ersetzen sie automatisch.
- Die Endkarte ist ein Platzhalter.
- Das Karussell bleibt auf dem Plakat stehen, das die Kadenz vorgibt (heute 14); bewusst wählen, sobald die Reihenfolge steht.
