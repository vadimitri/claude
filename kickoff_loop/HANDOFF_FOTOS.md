# Handoff Campus-Fotos (7.10. abends) · Stand F5, wartet auf Vadims Urteil

Ergänzt `HANDOFF_ENDE.md` (Video-Ende, unberührt). Details und Befunde: `CLAUDE.md` Abschnitt „Campus-Fotos“.
Code: `src/kickoff_loop_photos.py`, Kamera in `src/kickoff_loop_video.py` (`camera`, `shoot`, `plate_size`).
Stellschrauben: `loop.toml` `[photos]` und `[video] shake_*`. Branch `claude/kickoff-loop`, alles gepusht.

## 1. Stand

- **Vorschau F5** `previz/review/F5/preview_draft.mp4` (10.3 s, `--draft`): 64/64 Plakate als echte Fotos, Ende = O17.
- Fotos: 362 in `photos/raw/` (IMG_0972–1142 vom 6.10., A3-Runde IMG_1143–1334 vom 7.10. aus `~/Movies/116_1001`,
  nur JPG). Ausgabe `photos/aligned/NN.png`, Bögen `photos/plates.png`, `colors.png`, `auswahl.png`, `report.txt`.
- Versionen zum Vergleichen (alle `previz/review/<F>/preview_draft.mp4`):

| Code | Was | Vadim |
|---|---|---|
| F1 | 29/64, Plakat = digital (3x3-Matrix), Wand gedimmt | „sehr gut“ (6.10.) |
| F2 | 62/64, A3-Runde bevorzugt, sonst wie F1 | „sieht aus wie digital, Hintergrund immer verändert“ |
| F3 | ein Weißabgleich + Belichtung fürs ganze Foto, Wand nie gedimmt | gut, „aber immer noch sehr viel verändert“ |
| F4 | nur Papierbogen korrigiert (0.7), Wand roh, 19 + 45 drin, Handkamera 6 px / 0.3° | „viel zu viel Bewegung“ |
| **F5** | F4 mit Handkamera 1.5 px / 0.05° (Sprung je Bild Median 2.3 px, max 6.4 px) | **offen** |

## 2. Entscheidungen (Vadim 7.10.)

- Neue A3-Fotos schlagen alte: `prefer_from = "IMG_1143"`.
- Wahl nach `photos/auswahl.png`: `pick` 2 = IMG_1184, 9 = IMG_0982, 15 = IMG_1016, 52 = IMG_1333 („die andere
  Version“, als Riffelblech-Szene gedeutet, nicht bestätigt). Alle anderen genannten „kann so bleiben“ = auto.
- **19** (nur an der Litfaßsäule, gewölbt): „einfach verzerren, sieht keiner“ → `corners` für IMG_1027 (Ecken der
  Druckfläche per Gelb-Segmentierung, am Bild geprüft) + `number`.
- **45** (kein Foto): „Hintergrund, der schon benutzt ist, realistisch reinschneiden“ → `composite = {45 = "IMG_1104"}`
  (Plakat 9 im Rahmen an der Holztür, frei seit 9 = IMG_0982). `montage`: print/45.png durch die umgekehrte
  Farbabbildung des Fotos, Lichtverlauf + Schärfe des echten Plakats übernommen, kein Rauschen nachgebaut.
- **46** (Küche, Druck magenta statt lila, Render-Vergleich zu knapp) → `number` für IMG_1303–1306.
- Bearbeitung: „Edits auf dem Plakat, Rest natürlich, keine sichtbare Maske, erkennbar, Saturation stimmt, nicht
  super krass klar“ → `wall_edit = false`, `poster_match_frac = 0.7`. Maske = Papierbogen bis zur Papierkante
  (`sheet`), weil der Druckerrand dasselbe Blatt ist und die Papierkante eine echte Kante im Foto.

## 3. Verworfen (nicht wiederholen)

| Was | Befund |
|---|---|
| Grau-Korrelation der Wand für „deutlich anderes Foto“ | trennt nicht (Serienbild 0.33–0.68, andere Szene 0–0.69) → Median-ΔE OK, `variant_de` 0.07 |
| Plakat relativ zur Grauachse der Matrix (Foto-Weiß behalten) | kippt bunte Plakate: 16 schwarz, 35 gelbgrün, 59 rot, 02 lila |
| ... mit begrenzter Grauachse | zahmer, aber trüb |
| Plakat aufs gemessene Papierweiß skaliert | trüb (21 grau statt rosa) |
| Maskenkante am Druck statt am Papier | harte Stufe rohes/korrigiertes Papier (16, 21 oben) |
| Seite ohne sichtbare Papierkante = 0 | dito; jetzt Breite der Gegenseite (Druck liegt mittig) |
| Handkamera 6 px / 0.3° | „viel zu viel Bewegung“ |

## 4. Nebenbei behoben

- **Schwarze Ecken** in den ersten ~12 Bildern aller Versionen bis F3 (Rollen −4° über den Plattenrand):
  `plate_size` hat jetzt Rand für Rollen + Wackeln (gerade, Zoom-Ende bleibt pixelgenau).
- Durch den größeren Rand kippte die automatische Wahl bei 12 Plakaten → Abdeckung zählt wieder nur den
  ungedrehten Startausschnitt (Wahl identisch zum Bogen, den Vadim gesehen hat).

## 5. Offen

1. **Vadims Urteil zu F5**: Bewegung (`shake_px`, `shake_rot_deg`) und Stärke (`poster_match_frac`). 52 bestätigen.
2. Die `aligned/*.png` sind mit dem Rand für F4-Wackeln gebaut (etwas größer als für F5 nötig, mittig, harmlos).
   Beim nächsten Foto-Lauf schrumpft er von selbst.
3. Schnitt Foto → digital (5.88 s): mit natürlichen Fotos größerer Sprung (gedeckt → leuchtend). Steht als „Disconnect“
   (geparkt) in `HANDOFF_ENDE.md` 1.5.
4. Danach wie „Übergabe Video“ in `CLAUDE.md`: Ende (HANDOFF_ENDE), `preview` ohne `--draft`, `--master`, Resolve
   `kickoff_loop_resolve.py schnitt`.
5. Report-Zeilen „Lesbarkeit ... 0/64 in Stufe A“ und „Finale 0.64 C“ sind bekannte Messfehler (HANDOFF_ENDE 4.3),
   nicht von den Fotos.
6. Fremde, nicht committete Dateien im Worktree (`previz/marks/photo_01.jpg`, `O12a|O12b/digital.ts`, `O7/test*`,
   `O14/report_draft.txt`, `RAND/O13_rand/report_draft.txt`) und `print/rest_duplex.pdf` (6.10. mittags, Herkunft
   unklar): nicht angefasst.

## 6. Befehle (aus dem Pack-Root)

```sh
uv run src/kickoff_loop_photos.py            # Fotos → aligned/ + Bögen + report.txt (~2 min, Erkennung gemerkt)
uv run src/kickoff_loop_photos.py test       # Selbsttest: Farbe, wenig Bearbeitung, Papierkante, Auswahl (~10 s)
uv run src/kickoff_loop.py preview kickoff_loop/previz/review/F5/F5.toml --draft    # Video (~20 s)
uv run src/kickoff_loop.py test              # Selbsttest Video inkl. Foto-Segment-Cache
```
Neue Fotos: `rsync -a --include='IMG_*.JPG' --exclude='*' <quelle>/ kickoff_loop/photos/raw/`, dann wie oben.
Foto erzwingen `[photos].pick = {NN = "IMG_...."}`, Nummer erzwingen `number`, Lage von Hand `corners`,
Montage `composite`. `print/nachdruck.pdf` entsteht nur, wenn ein Plakat ohne Foto bleibt (jetzt keins).
