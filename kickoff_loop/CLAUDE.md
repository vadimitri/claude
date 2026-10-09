# Kick-off Loop · SPARK Kick-off 14.10.2026 · **abgeschlossen (9.10.)**

Endfassung **F19** (Master, x264). Plakate abgenommen + gedruckt 6.10. Projekt ruht; Code bleibt Basis für Neues.
Pack-Regeln: `../CLAUDE.md`. Vor Vorschlägen: `docs/ENTSCHEIDUNGEN.md` + `docs/RETRO.md` (Fehler-Gedächtnis).

## Wo liegt was

| Pfad | Inhalt | Git |
|---|---|---|
| `final/` | **Lieferung**: `SPARK_Kickoff_F19_master.mp4`, Druck-PDFs (Hardlinks, kein Extra-Platz) | nein |
| `final/` (Social, 9.10.) | `…F19S_social` (Rickroll-QR + HPI), `…F19_rickroll` (Rickroll-QR, Rest F19: verlustfreier Schnitt bei Bild 217 = Keyframe, 0–216 aus F19S), je `_share` = x264 veryslow CRF 18 (37 MB, SSIM 0.993) | nein |
| `loop.toml` | alle Stellschrauben (Plakat-Abschnitte `[type]`, `[color]`, `[styles]`, `[spark]` = Druckstand, nicht ändern) | ja |
| `previz/review/F19/` | Endfassung: `F19.toml` (Basis `F17B/F17B.toml`) + Video + Report | toml, report |
| `previz/archiv/` | alle älteren Varianten (`review/F1…F18d, MC3, O17, alt/, geparkt/`), `versionen/v001…v022`, Musik | toml, report |
| `previz/now/`, `variants/`, `marks/` | Kratzflächen der Befehle `sheet` / `stars` / Marken-Selbsttest | Reports |
| `photos/` | Campus-Fotos: `raw/` (Originale, 362 JPG, **nicht löschen**), `aligned/` (Platten, MC3-Look), Bögen | nein |
| `print/` | Druckdateien A3 300 dpi mit Marken (`NN.png`, Einzel-PDFs) | nein |
| `ref/` | `audio/` (IGOR + Raster), `spiderverse/`, `picks_2026-09-26/` | teils |
| `resolve/` | `RECIPE.md`, `EDITOR.md`; `schnitt/`: `songcut/` (Songschnitt, im Git) + `M4a.wav` (F19-Song) | md, py |
| `docs/` | `ENTSCHEIDUNGEN.md`, `RETRO.md`, `VERLAUF.md` (altes Handbuch O6→F19), `HANDOFF_*.md` | ja |
| `../Vorschau/` | **alle Versionsvideos flach** (F13…F19, MC3, F18-Vergleich); `F17B*.mp4` = Eingang von F19, nicht löschen | nein |

Code: `../src/kickoff_loop*.py` (`kickoff_loop.py` Plakat/Satz/Selbsttest, `_video` Timeline/Kamera/Ende,
`_f16` Wortwand + Masken-Spark (F16–F19), `_photos` Campus-Fotos, `_end` Ausstiege, `_marks` Druckmarken,
`_music`, `_resolve`, `_digital`). Befehle + Cache-Logik: `docs/VERLAUF.md` Abschnitt „Befehle“.

## Social-Fassung (F19S, 9.10.)

QR → Rickroll (`youtu.be`, gleiche QR-Version), Endbild HPI: Schalter `SPARK_SOCIAL=1` (`styles.py`), nur mit
`F17BS`/`F19S` (load prueft `[video].social`). Fotos: `uv run src/kickoff_loop_social.py` → `photos/aligned_social/`
(Befund `previz/review/F17BS/social_qr.txt`, 64/64 lesbar), dann `F17BS` preview `--master`, dann `F19S` video `--master`.

## Neu rendern (F19)

```
uv run src/kickoff_loop_f16.py video kickoff_loop/previz/review/F19/F19.toml --master   # aus dem Pack-Root
```
Eingänge, die **nicht** im Git sind und bleiben müssen: `Vorschau/F17B.mp4` (Master-Basis) + `Vorschau/F17B_draft.mp4`
(Draft-Basis), `resolve/schnitt/M4a.wav` (Songschnitt; neu: `cd resolve/schnitt/songcut && uv run songcut.py songcut.toml`,
geprüft 9.10.: ergibt F19-Audio bitgleich), `photos/`. Varianten-Loop (`F17B`) selbst: `uv run src/kickoff_loop.py preview
kickoff_loop/previz/review/F17B/F17B.toml [--master]`.
`_cache/` beim Aufräumen gelöscht (863 MB) → erster `kickoff_loop.py`-Lauf kalt. Resolve-Medien (`loop_igor.mp4`,
Song-WAVs, `ref/`-Previews) gelöscht; neu mit `uv run src/kickoff_loop_resolve.py schnitt` (~3 min), Timelines im Projekt
`SPARK_Kickoff_Schnitt` sind bis dahin offline.
