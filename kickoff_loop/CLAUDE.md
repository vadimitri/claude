# Kick-off Loop · SPARK Kick-off 14.10., 17:00

Session-Start: diese Datei, dann `uv run src/kickoff_loop.py sheet` (zeigt den Stand in ~10 s). Stellschrauben: `loop.toml`.
Regeln fürs Pack: `../CLAUDE.md`. **Vor Vorschlägen** `ENTSCHEIDUNGEN.md` (Befunde, Verworfenes, Archiv) und Skill `spark-motion`.

## Stand 1.10. abends

Der **Video-Loop ist von den Campus-Plakaten getrennt**. Für den Loop gelten keine Druck-Regeln mehr: leere Frames sind ok,
kein Frame muss allein tragen. Die Plakate kommen eigens (offen).

In `loop.toml` steht, was Vadim gewählt hat:
- **Farbe C1**: 32 Frames pro Loop, eine gemischte Reise über die dunklen Colorways.
- **Bahn B19**: Ellipse um den Betrachter. Der Stern ist links riesig, fliegt in die Tiefe, kommt rechts riesig zurück
  und ist hinter dem Kopf 5 Frames weg (F1–2, F30–32).
- **Tempo T16**: 16.32 Plakate/s = 32tel-Triolen auf IGOR (81.6 BPM). Das steht noch **nicht** im Code, siehe unten.

In `previz/review/` liegt, was offen ist (alles andere in `review/alt/`):
- `C1b/C1c/C1d_B19`: „verrückter" auf B19.
  - C1b: harte Sprünge, Mini-Welten, Papier-Blöcke.
  - C1c: Split-Tone, Grund und Licht aus verschiedenen Colorways.
  - C1d: Regenbogen-Mischung, bunter.
  - Urteil offen.
- `B20` / `B20b` (2.10.): neue Bahn. Die Ellipse liegt ganz vor dem Betrachter (`ahead` > 1). F1 zentral bildfüllend,
  dann links, kleiner, hoch hinter SPARK (Fernpunkt = Fluchtpunkt auf Titelhöhe), rechts zurück, F32 wieder zentral.
  Keine leeren Frames. B20b holt weiter aus, F1–2 sind dort nur noch Lichtfläche.
  Befund: Lesbarkeit min 0.83 / 0.82, weil der kleine Stern ~16 Frames hinter dem Titel steht.
- `tempo_T16.mp4`: Tempo mit IGOR darunter.
- `S_rework_3.png`: die gewählten neuen Sterne.

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
4. **Zeitachse T16**: Das Raster kennt nur 16tel-Teiler (`load`: `16 % per`). 32tel-Triolen = 24 Wechsel pro Takt. Dann
   `preview` und der Blitz-Check bei 16/s (C1 wechselt jeden Frame die Farbe).
5. Farbe: Urteil C1b–d. Bei C1c dithert Rot auf Blau kariert (~335°, Magenta, nicht Lila). Vadim ansehen lassen.
6. **Musik** nur IGOR, Custom-Mashup: Wo IGORs Drums kommen, etwas Eigenes. Maker Night fliegt raus
   (`kickoff_loop_music.py`, `[mashup]`). Das Raster-Format bleibt (`GRID_KEYS`).
7. **Endkarte neu**, keine Hypno. Heute Platzhalter (Nest-Tunnel). Boil (`boil`) nur mit Vadims Ja.

**So arbeiten** (hat getragen):
- Varianten als volle TOML-Kopie in `previz/review/<Code>.toml`, rendern mit `sheet <datei>`. Vadim schaut im Finder und
  antwortet mit Codes. Veraltetes nach `review/alt/`.
- Befund zuerst rechnen, dann rendern. Die Bahn-Suche lief als Skript über die Parameter, schneller als Bögen raten.
- Agenten in eigenen Worktrees, klare Dateigrenzen: Farbe → Farbteil von `kickoff_loop.py`, Sterne → `lab_spark.py`.

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
| `uv run src/kickoff_loop.py sheet [review/X.toml]` | Kontaktbogen + Loop-Video → `previz/now/` bzw. `previz/review/X_*` (+ Report), öffnet beides | ~10 s |
| `uv run src/kickoff_loop.py stars [S..]` | Sterne-Bogen an 3 Bahnstellen → `previz/variants/stars.png` | ~25 s |
| `uv run src/kickoff_loop.py test [N..]` | Selbsttest am fertigen Bild (+ Bahn, Blitz) | ~5 s |
| `uv run --with numpy --with pillow --with scipy --with qrcode --with scikit-image --with opencv-python-headless python src/lab_spark.py test` | Selbsttest Sterne (Hand-Schraffur) | ~20 s |
| `uv run src/kickoff_loop.py preview [A\|B]` | neue Version `previz/vNNN/` (Video, Bogen, Report). **Bricht heute** (Schritt 2) | ~1 min |
| `uv run src/kickoff_loop.py frames` / `variants` / `boil` / `print` / `resolve` | Frames rendern / QR-Varianten / Boil-Test / Druck-PDFs / Resolve-Bausteine | |
| `uv run src/kickoff_loop_music.py` | Musik + Raster → `ref/audio/mashup_*.wav/.json` | ~5 s |

Frames sind nach Inhalt gecacht (`_cache/`, Schlüssel inkl. Hash aller `src/*.py`).

## Ordner und Code

| Pfad | Inhalt | Git |
|---|---|---|
| `loop.toml` | alle Stellschrauben, kommentiert, Einheit im Namen | ja |
| `previz/review/` | offene Varianten (`<Code>.toml` im Git) + Bögen/Videos; `alt/` = Verworfenes | toml ja |
| `previz/vNNN/`, `previz/now/`, `previz/variants/`, `previz/music/` | Versionen / Kratzfläche / Bögen / Hörversionen | Reports ja |
| `ref/audio/` | `igors_theme.mp3` (nicht im Git), `igor_beats.json` (IGOR-Raster, Drums ab 22.435 s), `mashup_*.json` | teils |
| `ref/spiderverse/` | Recherche + Notizen zu allen Labor-Sternen | README ja |
| `resolve/` | `RECIPE.md`, `EDITOR.md` (Stern-Editor, Stand 16 Frames) | md ja |

`src/kickoff_loop.py`: Config, Farbreise (Welten, Split, Regenbogen), Bahn (`orbit`), Satz, QR-Glühen, Rendern, Selbsttest.
`src/kickoff_loop_video.py`: Timeline, Kamera, Ausbruch/Impact/Endkarte, Blitz-Check (inkl. Rot), sheet/preview.
`src/kickoff_loop_music.py`: Mashup + Raster. Sterne: S2/S7/S33 in `src/styles.py`, Labor in `src/lab_spark.py` (`URTEIL`).

## Checks (stehen in jedem Report)

QR je Frame dekodiert · Titel-Lesbarkeit ≥ 0.95 (`kickoff.legible`) · Blitz ≤ 3/s auf ≤ 25 % der Fläche + Rot-Regel ·
kein Lila (auch im Korn, `load` bricht ab) · Selbsttests schlagen nachweislich am alten Fehler an.

## Offen (nach den nächsten Schritten)

- **Campus-Plakate** als eigenes Konzept (z. B. die stärksten Loop-Frames). Plätze: 18 × A4 hoch, 56 × A3 hoch, 10 × A4 quer.
- Ort (`kickoff.COPY["where"]`) fehlt, für Endkarte und Plakate.
- Zeigt das Video Campus-Fotos oder nur Simulation? Davon hängen `align` und das Shooting ab (Archiv in `ENTSCHEIDUNGEN.md`).
- Resolve-Stern-Editor kennt 32 Frames und leere Frames noch nicht.
- 9:16-Sicherheitszonen der Endkarte (Reels-UI unten/rechts).
- `SV_LABEL_CELLS` in `lab_spark.py` spiegelt `[qr]` (Versalhöhe 9 + Abstand 4). Ändert sich JOIN US, dort nachziehen.
