# Handoff Video-Ende (6.10. nachmittags) · ersetzt Schritt 1 der „Übergabe Video“ in `CLAUDE.md`

Zwei Agenten nacheinander, jeder mit frischem Kontext:
**A. Aufräum-Agent**: misst, was den Kontext aufbläht, räumt auf (Abschnitt 3 + 4). Baut nichts Neues.
**B. Bau-Agent**: baut das Ende neu nach Abschnitt 1 (Abschnitt 5). Liest nur dieses Doc, die gekürzte
`CLAUDE.md` und die Dateien, die er anfasst.

## 1. Was Vadim will (Stand 6.10., verbindlich)

Video ~10–11 s (passt so). Beat-Einstieg/Musik schneidet Vadim selbst in Resolve.
1. **Digitalstart** (Karussell-Ende, 5.88 s): JOIN US + QR fliegen **nach unten links** raus, KICK-OFF/Datum/Ort
   **nach links**, nicht quer übers Bild. SPARK bleibt.
2. **Standard-Loop läuft digital weiter** (Plakat je Bild wie im Karussell), keine Begriffe, kein Tauchen in einen
   einzelnen Stern mit Wechseln.
3. **Die Sparks werden dunkler**, nicht das Bild. Grund + Schrift bleiben in ihrer Colorway. Der dunkle Spark kommt auf
   die Kamera zu und füllt das Bild, Schwarz ist dann nur noch der letzte kleine Schritt. (O17: „schon deutlich besser“.)
4. **Kein langweiliges Schwarz am Ende**: ab ~7 s ein „Midnight“-Moment. Das Leuchten am SPARK-Schriftzug (heute das
   Zoom-Glühen, das beim Schwarz verschwindet) soll **entstehen** statt verschwinden; KICK-OFF / 14.10. / 17:00 /
   D-SCHOOL **entstehen genauso**, „wie eine Corona bei einer Finsternis“, „gar nicht so kompliziert“.
   Datumsblock **früher** und **smoother** als in O17. Schluss: SPARK oben, Datumsblock groß mittig.
5. Kleiner Disconnect Plakat-Endloop → Digitalbeginn: **geparkt**, bis die Campus-Fotos da sind.
6. Photosensitivität: Warnung kommt rein, trotzdem keine schnellen Vollbild-Wechsel.
7. Weiter gültig: nie flache Farben (Verlauf + Bayer), nie einzelne Buchstaben umfärben, kein Drop-Shadow, keine
   harten Boxen/Konturen um Schrift, Effekte nie von QR/Titel blockiert.

## 2. Verworfen in dieser Session (nicht wiederholen)

| Code | Was | Vadim |
|---|---|---|
| O14 | Stern + Colorway jedes Bild, Begriffe alle ~3 Bilder oben links | zu schnell, zu viel Änderung, Begriffe gehören mittig |
| O15 | Begriffe mittig mit Glühen, Stern dreht in Stufen (⅓ Beat) | „funktioniert nicht richtig“ → Begriffe ganz raus |
| O16 | ganze Palette abgedunkelt | „einfach ein Fade to Black“ |
| O17 | **nur Sternfläche dunkel**, Anflug füllt das Bild, 4 Bilder auf Schwarz, Datum pixelt mittig ein | **Basis**; Wegflug quer, Schwarz langweilig, Datum zu spät |
| M1–M4 | Corona = Distanz-Glühen um Schrift (hell / „Finsternis“ mit schwarzer Schrift) | „sieht leider auch scheiße aus“ |

Befund zu M1–M4: Ein Distanz-Glühen (`distance_transform_edt` + exp) um Clash-Bit-Schrift liest sich
nah an der Schrift als **flacher Sticker-Rand**, auch mit steilem Kern und 85 % Spitze. Das gelobte Leuchten oben ist
etwas anderes: `glow_layer` = die Schrift, mehrfach **um die Zoom-Mitte skaliert** (Lichtschweif in Bewegungsrichtung).
Die Corona sollte von dort ausgehen (z. B. Schweif wächst statt schrumpft, auch für den Datumsblock), nicht vom
Distanz-Glühen. Ungetestet, Vadim zuerst an 3 Standbildern zeigen.
Der Fix der Flugrichtung aus M1–M4 (`orbit_dissolve_out`, je Gruppe eigene Mitte in `finale_layers`) ist am Bogen
richtig (QR unten links, Datum links), Vadim hat ihn nicht einzeln beurteilt.

## 3. Was den Kontext aufbläht (gemessen 6.10.), für Agent A

| Quelle | Größe | Problem |
|---|---|---|
| `kickoff_loop/CLAUDE.md` | 66 KB (~16k Tokens), 21 Abschnitte | wird beim Arbeiten im Ordner geladen; 80 % sind Runden-Historie O6–O13, Stand 2.10./3.10. |
| `ENTSCHEIDUNGEN.md` | 12 KB | ok als Archiv, nicht mitladen |
| Skill `spark-motion` | 15 KB | lädt bei jedem Motion-Job |
| `src/kickoff_loop_end.py` | 1702 Zeilen, 84 `orbit_*`-Schlüssel, 65 Versions-Kommentare O6–O18 | jede Runde hat Schalter + Zweige ergänzt, nichts gelöscht |
| `kickoff_loop.py` / `_video.py` / `_digital.py` | 1415 / 1369 / 444 Zeilen | dto. |
| `preview`-Ausgabe | 64-Zeilen-Tabelle auf stdout je Lauf | landet im Kontext, wenn man `tail` vergisst |
| `previz/` | 7.5 GB, `_cache` 718 MB | Review-Ordner O6–O17, M1–M4, INK, RAND, S58b_S60d |
| Git | 3 alte `worktree-agent-*` Worktrees + 8 Branches | |

Dazu kostet jede Video-Runde ~1–1.5 min Render + Bildprüfung. Pro Runde 2–3 Fehlrenders (Fehler erst am Bild
gesehen), deshalb wurde es teuer.

## 4. Aufräumen (Agent A), vor dem Löschen Vadim fragen

1. `CLAUDE.md` auf ≤ 2 Seiten: Übergabe (→ dieses Doc), Befehle, Ordner/Code, Checks, Regeln. Runden-Historie
   (Finale O8–O13, Bahn-Enden, Stand 2.10./3.10.) wörtlich nach `ENTSCHEIDUNGEN.md` bzw. `archiv/`.
2. Toten Code der verworfenen Enden löschen: Begriffe (`finale_words`, `word_layer`, `word_slot`, `stop_sparks`,
   `frame_slot`, `colour_tour`, `WORD_*`), Karte/Morph/Flow/Throw/Vortex/Matrjoschka-Reste, Corona aus M1–M4, falls B
   sie nicht nutzt. Vorher prüfen, welche TOMLs (`loop.toml`, `O17`) die Schlüssel brauchen; `kickoff_loop_end.py
   test` und `preview --draft` von O17 müssen danach bitgleich laufen.
3. Report-Fehler beheben: „Finale“-Lesbarkeit misst noch die alte Datumsstelle (`K._EXTRA["date"]` von der
   Plakatposition), zeigt deshalb 0.64 C, obwohl der Block mittig klar steht. `preview` soll die 64-Zeilen-Tabelle nur in
   `report.txt` schreiben.
4. `previz/review/`: O17 + M2 behalten (Bezug), Rest nach `archiv/review/alt/` (mp4 sind gitignored). Lose Dateien:
   `previz/marks/photo_01.jpg`, `O12a|O12b/digital.ts`, `O7/test*`.
5. Alte `worktree-agent-*` Worktrees/Branches: nur mit Vadims OK entfernen.
6. Stand Git: Branch `claude/kickoff-loop`, linear (Video-Runden O14–M4 + Druck-Runde des anderen Agenten:
   Druckrand, Rückseite, Duplex-PDFs), gepusht, 145 Commits vor `main`. Merge nach `main` entscheidet Vadim.

## 5. Neu bauen (Agent B)

Start: `previz/review/O17/O17.toml` (+ `orbit_dissolve_out = true` aus `M1.toml`). Relevanter Code:
`orbit_state` (Abdunkeln `orbit_darken`, `dark_palette`), `zoom_sparks` + `zoom_card_type` in `kickoff_loop_digital.py`
(Palette je Zelle), `finale_layers`/`_fly` (Wegflug), `glow_layer` (Leuchten oben), `corona_layer` (M, verworfen).
Ablauf: Idee → **3 Standbilder** (7.0 s, 8.0 s, Schlussbild) als beschrifteter Bogen → Vadim → erst dann `preview`
(volle 24 fps; `--draft` rendert den Digitalteil auf Zweiern). Render: `uv run src/kickoff_loop.py preview <toml>`
(~70 s), Streifen: `ffmpeg -ss 6.6 -i preview.mp4 -vf "select='not(mod(n\,5))',scale=180:-1,tile=14x1" -frames:v 1 s.png`.
Fallen: Papier-Colorways (Stufe 0 = hellstes Weiß) kehren hell/dunkel-Regeln um, immer per Luminanz entscheiden;
Labor-Sterne malen ihre Ebene `spark` über die ganze Seite, Abdunkeln nur über `pal_map` + Sternsilhouette;
`orbit_loops` 2 bricht den Bahn-Check (Zoomrate x0.09), Beschleunigung 1.0 lässt den Stern aus dem Bild laufen.
Danach weiter mit Schritt 2–5 der „Übergabe Video“ in `CLAUDE.md` (Sprung am Eintauchen, Master, Resolve, Fotos).
