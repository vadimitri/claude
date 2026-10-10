# Ready-Kit · „Ich will X“ → läuft

Claude stellt **genau diese Fragen in einer AskUserQuestion-Runde** (Standard vorausgewählt), dann wird gebaut.
Antwort „Standard“ reicht. Ablauf und Geschmacksregeln: `PLAYBOOK.md`. Resolve: `RESOLVE.md`.

## Brief (6 Fragen)

| # | Frage | Standard |
|---|---|---|
| 1 | **Was + Kanal?** Story · Post · Loop (Screen) · Plakat A3 · Teaser · Zumo-GIF/Emoji | Story 9:16 (Telegram + Instagram) |
| 2 | **Fakten?** Anlass, Datum, Uhrzeit, Ort, Link/QR. Nie erfinden, fehlt etwas → Platzhalter `XX` | siehe Fakten unten |
| 3 | **Eine Zeile Botschaft?** (Spark-Voice, Skill `spark-slack-post`) | Anlass + Datum, sonst nichts |
| 4 | **Colorway?** P-Code aus `brand/colorways.png` | Maker Night P1 · Kick-off P11 |
| 5 | **Länge + Ton?** | Story 8 s (4 Takte), MN-Loop; Post still; Teaser 15 s |
| 6 | **Wer schneidet, bis wann?** | Claude Bausteine, Vadim schneidet in Resolve; Deadline = Datum − 2 Tage |

## Rezepte

| Wunsch | Claude macht | Vadim macht | Runden |
|---|---|---|---|
| **Story** (Ankündigung, Reminder) | fehlende Bausteine (`kit.py`), sonst nichts | Template duplizieren → *Story 9x16*: Grund + Spark + Text+ + Blende auf Takt 3, Lens-Colorway wählen, Export | 1 |
| **Post** (Feed 4:5, Still) | `kit.py look <bild> P1` für Fotos im Spark-Look | Timeline *Post 4x5*, ein Standbild exportieren (Deliver > TIFF/PNG oder Viewer > Grab Still) | 1 |
| **Loop** (Screen, Event) | Loop-Länge = Vielfaches der Element-Loops (2,5 s / 4 s / 24 s) prüfen | Elemente hintereinander, kein Text, der sich einzeln ändert | 1 |
| **Plakat A3** | `uv run -q --with numpy --with pillow --with scipy --with qrcode --with scikit-image python src/styles.py posters 24 7` (MN-Unikate, QR geprüft) bzw. `kickoff.py` | Auswahl per Code, Druck | 1–2 |
| **MN-Teaser** (9:16 + 16:9, Sound) | 3 Standbilder Anfang/Höhepunkt/Schluss → Vadim wählt → Bausteine | Schnitt in beiden Timelines, Riser → Hit auf Titel | 2–3 |
| **Zumo-GIF/Emoji** | `uv run src/zumo_scenes.py sheet` → Auswahl → `scenes`/`emoji`/`mascot` | einfügen, Slack-Emoji hochladen | 1 |
| **Crew-Recruiting** | wie Story, Botschaft „Bau die Arena mit“, Deadline 21.10. | | 1 |
| **Kick-off Day-of** | aus `kickoff_loop/final/SPARK_Kickoff_F19S_social.mp4` (Rickroll-QR, Ort HPI) bzw. `…F19_share.mp4` | Story mit „HEUTE 17:00“ als Text+ | 1 |
| **Recap** (Fotos vom Abend) | `kit.py look` je Foto oder Lens mit Photo fade | Fotos in *Story*, Lens nur auf Grafik, Photo fade auf den Fotos | 1 |

## Fakten (Stand 10.10.2026, vor Gebrauch prüfen)

- **Kick-off** Mi 14.10.2026, 17:00, D-SCHOOL (d-school EG). Video fertig: `kickoff_loop/final/`.
- **Maker Night** 20.–21.11.2026 (Aufbau 19.11.), 48 Teilnehmende, Zumo-Challenges Spumo, Spormula E, Area Capture. Ort: `XX`.
- **Crew-Einstieg** bis Mi 21.10.
- **QR/Link**: Telegram `t.me/+TnDm1terktk1ZTNi` (steht so auf allen Plakaten).

## Regeln, die jedes Stück erfüllt (Gate vor dem Zeigen)

Effekte nie hinter Titel/QR · nie flache Farbe, nie einzelne Buchstaben umfärben · kein Drop-Shadow · Stern frontal,
ganz im Bild oder ganz raus (keine abgeschnittenen Sparks) · keine Standard-Effekte (Dissolve, Wipes) · keine Füllsätze
(„is happening.“) · Pixel nur ganzzahlig skalieren · Ton auf den Takt · Lila = Maker Night.
