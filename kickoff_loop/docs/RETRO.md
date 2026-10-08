# Retro Kick-off Loop (SPARK Kick-off 14.10.2026)

Stand 9.10., Endfassung F19 (`Vorschau/F19.mp4`, Commit 5caa205). Grundlage: 165 Commits auf `kickoff_loop/` + `src/kickoff_loop*` (alle Branches), `kickoff_loop/CLAUDE.md`, `ENTSCHEIDUNGEN.md`, `HANDOFF_ENDE.md`, `HANDOFF_FOTOS.md`. Zeiten nach Git. Die Datumsangaben in der Doku laufen dem Git bis zu 2 Tage voraus (z. B. „Vadims Urteil 3.10.“ in 97fecac vom 1.10.).

## 1. Zeitachse

| Zeit (Git) | Phase | Commits | Iterationen |
|---|---|---|---|
| 30.9. 21:03 bis 1.10. abends | Loop-System: Bahn, Farbe, Tempo, Musik, Sterne, Grund, Render-Pipeline; bis zu 6 Agenten in Worktrees | ~77 | v003–v022, B4–B20g, C1–C6, M1–M3, S48–S60, I1–I8, V1–V3 |
| 30.9. bis 3.10. | Ende-Suche I | ~38 | H1–H5, Z1–Z9, W1/W2, E1a–c, D1a–d, O1–O13: ~40 Varianten, alle verworfen, O13 nie beurteilt |
| 2.10. + 6.10. vormittags | Plakate: Druckmarken, Ort, Satzkante, Glühen je Plakat. **Abgenommen + gedruckt 6.10. 12:43**, QR 64/64 | ~20 | INK Runde 1+2 |
| 6.10. 12:40–13:18 | Ende-Suche II | 5 | O14–O17, M1–M4 (8 Varianten in 38 min). 21:47 Neustart per `HANDOFF_ENDE` (Vadim: „so kommen wir nicht weiter“) |
| 6.10. 22:07 bis 7.10. 21:16 | Campus-Fotos | 6 | F1–F5, 362 Fotos, 64/64 zugeordnet |
| 7.10. 22:00 bis 8.10. 00:12 | Ende-Suche III: Papier → digital, Blau/Rot-Ende | 5 | F6–F8, F9a–f, F10a–i (18) |
| 8.10. 20:02–23:53 | Ende-Suche IV: Match Cuts, Wortwand im dunklen Spark | 10 | MC1–6, F11a–g2, F12a–g, F13–F17 (26) |
| 9.10. 00:14 | Endfassung | 1 | F18a–d, F19 Master |

Bilanz: Plakate nach 6 Tagen fertig. Das Ende brauchte ~90 Varianten über 8 Tage. Kern von F19 lag früh vor: Wortwand = W1 (1.10., „Idee cool, erstmal parken“), dunkler Spark füllt das Bild = O17 (6.10.), Leuchten = `glow_layer` aus O8 (2.10.).

## 2. Was gut lief

- **Befund vor Meinung**: O4/O5 vermessen (Bildtempo 46 → 3 px/Bild, Wachstum x8.1 am Wechsel), daraus O6/O7 gezielt gebaut. Farbsprünge je Loop 29 → 3 (C4 → C4b) gemessen. T16-Rechenfehler (24 statt 48 Wechsel/Takt) fand der Musik-Agent.
- **Selbsttests mit Gegenprobe**: Bahn-Check (alte O4/O5 schlagen an), „Halo nie kleiner“ (F15 0.58 % schlägt an, F19 0.03 %). F19-Report: 5/5 Schnitte auf dem Beat, Gegenprobe +3 Bilder 0/5.
- **Druckmarken zahlten sich aus**: 141/170 Fotos per Marke erkannt, +5 per QR/ECC, unsichtbar (ΔE 0.012 < JND 0.02). Fotos F1 → F5 in einem Tag.
- **Render-Tempo**: Inhalts-Cache + Foto-Segment: `preview` warm 117 → 33 s, kalt 330 → 57 s, `sheet` 15 → 4 s, nur Ende geändert ~9 s.
- **Stills vor Video**: O12 an Standbildern verworfen, Render abgebrochen. `HANDOFF_ENDE` macht daraus die Regel „3 Standbilder → Vadim → erst dann `preview`“.
- **Mini-TOMLs je Variante** (nur der geänderte Abschnitt): Entscheidungen wirkten automatisch auf alle offenen Varianten. Plakate 8 Tage vor dem Event gedruckt.

## 3. Wo Zeit verbrannt wurde

**Ende ohne Zielbild.** ~48 Varianten aus Phase I+II komplett verworfen. Begriffe kamen rein (W1, O9–O13), flogen raus (O15: „Begriffe ganz raus“), kamen wieder (F9 bis F19). Die geparkte W1-Idee kam erst als F11b nach 7 Tagen zurück. Varianten je Runde stiegen (F9: 6, F10: 9, F11: 8, F12: 7), obwohl Vadim am 8.10. „eine Version statt vieler“ wollte; der Skill sagt noch „4–6 variants“.

**Verworfen, mit Grund**: H1–H5 „schrecklich“ · E1 „alle scheiße“ · O4 „stoppt kurz“, O5 „schießt über“ · O11 Disconnect bei 7 s · O12 „sieht scheiße aus“ (unklar woran) · O13 nie beurteilt · O16 „Fade to Black“ · M1–M4 Corona „auch scheiße“ · F7 „noch viel schlechter“ (2 Bilder Weiß) · F14 „Zwerg, Titel poppen“ · F15 „warum ein neuer Spark statt der echten?“

**Wiederkehrende Fehlerklassen**
1. *Effekte hinter Titel/QR blockiert*: Vadim „dreimal“, dann „zum vierten Mal“ (O13). Der zugesagte Selbsttest am fertigen Bild wurde nie gebaut (steht noch in „Offen“, Kommentar `kickoff_loop_end.py:792`).
2. *Sprünge an Nahtstellen*: Loop-Neustart (bis 1.10.), 72°/Loop = 12° Sprung, O4/O5, O11, F7, F14, F15 (Maske jedes 2. Bild neben dem Spark: Draft auf Zweiern, Maske auf Einern). „Satz-Sprung am Eintauchen“ seit 6.10. als Risiko notiert, nie geprüft. Der Bahn-Check deckt nur die Bahn ab, kein Schnitt-Gate.
3. *Nachgebaut statt echt*: F15 geometrischer Stern statt MC3-Pixel; M1–M4 Distanz-Glühen statt dem gelobten `glow_layer`.
4. *Druck vs. Video*: `type_layers` überspringt im Digitalteil `[type.ink]`/`[type.halo]`; nach dem Druck gingen Satzänderungen nur noch über Sonderwege (`card_drop_chars` in F19).
5. *Report-Rauschen*: bekannte Fehlmessungen („0/64 in Stufe A“, „Finale 0.64 C“) stehen seit 6.10. im Report, auch im Basis-Report der Endfassung (F17B). Rote Tests als „Altfehler“ mitgeschleppt (`words_selftest` KeyError 'new' seit O16).
6. *Agenten entscheiden selbst*: 7 freigegebene Sterne am 1.10. wegen Messwerten ohne Rückfrage entfernt.

**Struktur und Kontext**
- `kickoff_loop/CLAUDE.md`: 7.9 KB (1.10., gerade „schlank“ gemacht) → 65 KB (6.10.) → 90 KB (9.10.). Aufräum-Agent A aus `HANDOFF_ENDE` lief nie: `kickoff_loop_end.py` 1702 → 1981 Zeilen, `finale_words`/`word_layer`/`stop_sparks` noch drin, 110 `orbit_*`-Schlüssel. Übergabe-Liste nummeriert 1–5, 10, 8, 7, 6.
- Ein Skript je Version (`_f11` … `_f16`, je 500–730 Zeilen, umbenannt statt erweitert). F19 lebt in `kickoff_loop_f16.py` und baut auf einem Zwischen-Video `Vorschau/F17B.mp4` + `resolve/schnitt/M4a.wav` auf. Beides gitignored, `songcut.py` ebenfalls.
- Worktrees: 1.10. bis zu 6 Agenten-Worktrees ohne die gitignorierten Medien. 7.10. Regel „keine Worktrees“ (Vadim: „sieben Ordner tief“). Trotzdem liefen F11–F19 im Worktree `f11` (Pfad in `F19/report.txt`); `f11` und `match-cuts` existieren noch.
- Vorschauen über 5 Ordnertypen verteilt (`review/`, `archiv/…/alt|geparkt/`, `vNNN/`, `now/`, `variants/`), 7.5 GB am 6.10. Flaches `Vorschau/` erst ab 7.10.
- Code-Kollision: F = Bahnframe (F1–F32) und Version (F1–F19), M = Musik (M1–M3) und Mitternacht (M1–M4). „F12“ oder „F16 → F17“ sind doppeldeutig.
- Rückfragen: Diktat-Fehllesung („Vundzwanzig“ als 25), Deutungen ohne Bestätigung (Plakat 52, „Daniela ganz zu sehen?“). Je Runde 2–3 Fehlrenders, Fehler erst am Bild gesehen (`HANDOFF_ENDE`).

## 4. Verbesserungen fürs nächste Motion-Projekt

1. Ende zuerst: Tag 1 Storyboard mit 3 Standbildern (Anfang, Höhepunkt, Schlussbild) je Idee, Vadim wählt eine Richtung, erst dann Code. Geparkte Ideen jede Runde wieder vorlegen.
2. Je Runde 1 Version (höchstens 3) und genau eine geänderte Achse. Viele Varianten nur auf Standbild-Bögen.
3. `CLAUDE.md` hart ≤ 120 Zeilen (Stand, Befehle, Regeln, Offen), Rundenverlauf in `docs/VERLAUF.md`. `test` schlägt an, wenn die Datei > 12 KB wird.
4. Verworfene Variante: Code im selben Commit löschen, keine Schalter-Sammlung. Ein Ende-Modul mit einer Funktion je Szene statt `_fNN.py` je Version.
5. Die Endfassung baut ein Befehl aus Code + TOML. Keine Zwischen-Videos aus `Vorschau/` als Eingang, Audio-Schnitt-Skripte ins Git.
6. Ein Vorschau-Ordner `Vorschau/<Code>.mp4` ab Tag 1, keine Hardlinks, keine Worktrees. Agenten nur für reine Code-Module, Ergebnis als Patch.
7. Jede harte Regel von Vadim wird am selben Tag ein Gate am fertigen Bild (Effekte hinter Titel/QR, keine flache Farbe, Halo nie kleiner), dazu ein Naht-Gate an jedem Schnitt (Helligkeit, Maskendeckung, Tempo vorher/nachher). Fehlmessungen sofort fixen oder löschen, rote Tests nie stehen lassen.
8. Ein Präfix je Achse, das sonst nirgends vorkommt (F ist der Frame), Datum in der Doku aus `date`.

## 5. Fehler-Gedächtnis

- Gerade mit exponentiellem Raumtempo wird in der Perspektive langsamer (O4) → 1/Z steuern (`orbit_path = "throw"`).
- Zoom ohne Deckel läuft über `float` (O8) bzw. rendert > 3 min je Bild (S54c bei 13 904 px) → `orbit_zoom_max_per_frame`, `orbit_wall_r_frac`.
- 6-Zack-Stern: Drehung über 30°/Bild wirkt rückwärts (`orbit_spin_speedup`); Drehung je Loop nur Vielfache von 60°.
- Hermite aufs Ziel bremst mit Ruck, smoothstep springt am Wechsel x2.2 → Tempo v0·(1 − u^p)² (`orbit_dive_target_ease`), smootherstep.
- Glühen: exp-Abfall = Licht, Gauß-Kuppe = Box, Distanz-Glühen = Sticker-Rand; gelobt ist `glow_layer` (Schrift um die Zoom-Mitte skaliert).
- Papier-Colorways: Stufe 0 = Weiß, hell/dunkel per Luminanz (`KD.luma_to_base`); Papier nie mit Dunkel mischen, OKLab-Mischungen können Lila werden (`is_lilac`).
- Labor-Sterne ändern 26–89 % der Fläche außerhalb ihres Sterns → Abdunkeln nur über `pal_map` + Silhouette, Wortwand mit S2 (`wall_style`).
- `type_layers` überspringt im Digitalteil `[type.ink]`/`[type.halo]` (`if not lp["digital"]`) → Satz springt am Eintauchen.
- Draft = Digitalteil auf Zweiern: Masken aus dem ersten Bild des Paars (`mc3_dt`), `--master` auf Einern.
- `previz/review/<Code>/preview_draft.mp4` ist Hardlink auf `Vorschau/`: nach `git mv` schreibt `ffmpeg -y` in die alte Datei → vorher löschen.
- `ffmpeg -shortest` kürzt aufs Audio (M4a.wav 13.03 s) → `song_pad.wav` bis `end_s`. `loudnorm` drückt den Drop platt → feste Verstärkung auf −14 LUFS.
- T16 = 48 Wechsel/Takt (16.32/s × 2.94 s). Ereignisse auf `igor_beats.json`, nie ab dem synkopierten Drum-Boom zählen.
- Selbsttests: Masken nicht in place verändern (`m &= level != 0` → Fehlalarm), `SELFTEST_FRAMES` an feste Sternlagen (sonst nach Bahnwechsel blind), Gegenprobe mit dem alten Fehler.
- Cache parallel: Temp-Datei je Thread (`qr_scan` → FileNotFoundError).
- Rollen/Wackeln über den Plattenrand → schwarze Ecken; `plate_size` braucht Rand für Rollen + Wackeln.
- Fotos: Farbmatrix auf der Wand kippt sie (Holztür rot) → Wand nur Grauachse, Plakat `poster_mode = "light"` statt Leuchtkasten.
- Varianten-TOMLs zeigen auf verschobene Pfade (`MC3.toml` → `aligned_MC3`) → `load` muss Pfade prüfen.
- F19 neu rendern ist dreistufig: `kickoff_loop.py preview …/F17B/F17B.toml --master` (→ `Vorschau/F17B.mp4`), `resolve/schnitt/songcut/songcut.py songcut.toml` (→ `M4a.wav`), dann `kickoff_loop_f16.py video …/F19/F19.toml --master`. `kickoff_loop.py preview F19.toml` reicht nicht.
