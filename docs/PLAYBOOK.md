# Spark Motion Playbook

Stand 10.10.2026. Destilliert aus dem Kick-off-Loop (30.9.–9.10., 169 Commits auf `kickoff_loop/` + `src/kickoff_loop*`,
~90 Varianten nur fürs Ende, Endfassung F19 `5caa205`). Quellen: `kickoff_loop/docs/` (RETRO, ENTSCHEIDUNGEN, VERLAUF,
HANDOFF_ENDE, HANDOFF_FOTOS), `kickoff_loop/resolve/`, `src/kickoff_loop*.py`, `src/makernight_*.py`, Skill `spark-motion`, Git.
**Arbeitsteilung ab jetzt: Claude rendert Bausteine in Python, Vadim schneidet in DaVinci Resolve.** Belege in Klammern.
Schnellstart: Brief + Rezepte `BRIEF.md`, Resolve-Template + Effekte `RESOLVE.md`, Bausteine `src/kit.py`.

## 1. Ablauf für jedes neue Stück

Eine Runde = genau eine geänderte Achse (Bahn, Farbe, Tempo, Ende, Ton …), höchstens 3 Versionen. Viele Varianten nur als
Standbild-Bogen (RETRO §4.2; Vadim 8.10.: „eine Version statt vieler“). Vadim entscheidet an Bewegung mit Ton (VERLAUF).

| # | Schritt | Ergebnis | Zeit | Aufhören, wenn |
|---|---|---|---|---|
| 1 | **Brief**: Format (Story/Reel 9:16, Post 4:5, Loop, A3-Plakat, Teaser, Zumo-GIF), Länge, Pflichttext (Datum, Ort, QR-Ziel), Song oder prozedural, Abgabetermin | 5 Antworten | 10 min | alles beantwortet; Zahlen und Codes aus dem Diktat zurückgelesen („Vundzwanzig“ = 25, VERLAUF 2.10.). Fakten nie erfinden (Skill Gotchas) |
| 2 | **3 Standbilder je Idee**: Anfang, Höhepunkt, Schlussbild auf einem beschrifteten Bogen, 2–3 Ideen, geparkte Ideen wieder mit vorlegen | Vadim wählt **eine** Richtung | 30 min | Richtung steht. Nach 2 Bögen ohne Wahl: Brief neu statt weiterrendern (Ende-Suche I+II: ~48 Varianten ohne Zielbild verworfen, RETRO §3) |
| 3 | **Stills-Bogen** über die ganze Laufzeit (~10 Bilder, Skill Visual recipe 9) + `report.txt` mit Gates | Bogen + Report | 30 min | Gates grün, Vadim nickt den Ablauf ab. O12 fiel so am Standbild, Render abgebrochen (`3f984a1`) |
| 4 | **Video-Preview** mit Ton als Entwurf (`--draft`: Digitalteil auf Zweiern, Hardware-Encoder), flach in `Vorschau/<Code>_draft.mp4` | Video + Report | ≤ 30 min je Runde | „fast fertig“ → noch genau 1 Runde (F16 „fast fertig“ → F17 → F18a–d → F19). 3 Runden ohne „besser“ → zurück zu Schritt 2 |
| 5 | **Bausteine für Resolve** (seit 10.10. Standard): Grau-Elemente + Stems aus `src/kit.py`, Projekt `SPARK_Template` duplizieren, Lens/Glow/Journey als Effekte; nur was Resolve nicht kann (Bahnen, Fotos, Wortwand-Masken) rendert Python als eigenes Element | Resolve-Timeline, Export | 15 min | ein Befehl baut jeden Baustein aus Code + TOML (RETRO §4.5) |

Zeiten = Vorgabe, nicht gemessen. Gemessen: die Video-Runden am 8.10. lagen 6–31 min auseinander (F12 22:25 … F17 23:53, Git).

- **Ende zuerst**: das Schlussbild gehört in Schritt 2, nicht in Schritt 4 (RETRO §4.1).
- Was Vadim selbst keyen will, macht er in Resolve. Seit 10.10. rastert die **Spark Lens als DCTL in Resolve** genau wie
  numpy (Render = Referenz bei 99,999 %), also dürfen Bausteine grau bleiben und erst Resolve färbt (`RESOLVE.md`). Python
  backt nur noch, was Resolve nicht kann (Bahnen, Masken aus echten Pixeln, Foto-Ausrichtung).
- Variante = Mini-TOML mit nur dem geänderten Abschnitt, `load` ergänzt den Rest (VERLAUF „So arbeiten“). Code =
  Präfix + Nummer, Präfix je Achse eindeutig (Kollision F = Frame/Version, M = Musik/Mitternacht, RETRO §3).

## 2. Bausteine aus dem Kick-off-Loop

| Baustein | Was | Code | Wiederverwendbar |
|---|---|---|---|
| Plakat-Loop (Stop-Motion) | Plakatserie = Frames eines Loops (16–32 je Loop, 2 Welten = 64 Plakate), Satz steht, Stern wandert | `kickoff_loop.py` `frame`, `frames`, `layout`, `type_layers` | ja; Satz ist Kick-off-fest, neue Layouts über Hooks `layout`/`type_fn`/`spark_fn` |
| Bahn | Bumerang-Ellipse vor dem Betrachter, Stern frontal, Tiefe über Größe (B20c) | `kickoff_loop.orbit`, `star_at`, `[spark]` | ja |
| Colourway-Reise | Stationen in OKLab gemischt, Hell/Dunkel in Blöcken (C5b), Lila-Prüfung | `palette`, `station`, `mix_lab`, `is_lilac`, `[color]` | ja |
| Glühender QR | Platte in hellster Stufe, 1 Modul Ruhezone, exp. Lichtabfall über 12 Zellen, JOIN US frei darüber | `kickoff_loop.qr_glow`, `kickoff.check_qr` | ja |
| Verlauf je Schriftzeile | Grundlinie → Versalhöhe, ganze Stufen | `kickoff_loop.line_gradient` | ja (behebt den Band-Bug in `styles`/`kickoff`) |
| Schatten-Glühen | Halo um Schrift für Lesbarkeit, Bänder in Zweierpotenzen | `halo_field`, `[type.halo]` | ja, aber im Digitalteil übersprungen (RETRO §5) |
| Lichtschweif | Schrift x-mal um eine Mitte skaliert = Licht in Bewegungsrichtung (gelobt) | `kickoff_loop_end.glow_layer`, `flare_layer` | ja |
| Dunkler Spark | nur die Sternfläche dunkelt ab (OKLab), Grund + Schrift bleiben; füllt das Bild (O17) | `kickoff_loop_end.orbit_state`, `dark_palette` | ja |
| Druckrand / Papier → digital | Lichtabfall ins Weiß als umlaufende Welle; Digitalbild wächst aus dem Plakatrahmen | `edge_fade`, `kickoff_loop_video.paper_grow`, `paper_wipe` | bedingt |
| Druckmarken + Campus-Fotos | unsichtbare Marken (ΔE 0.012 < JND 0.02) → Nummer + Lage aus Handyfoto; Plakat im Licht des Fotos (MC3, `poster_mode = "light"`) | `kickoff_loop_marks.py`, `kickoff_loop_photos.py` | ja, für jede Plakat-Foto-Aktion |
| QR im Foto tauschen | QR in den Foto-Platten umfärben statt einkopieren (Rickroll-Fassung) | `kickoff_loop_social.py` | ja |
| Handkamera | exp. Zoom, Rollen −4° → 0°, Wackeln 1.5 px / 0.05°, Zoom nur mit dem Fotowechsel | `kickoff_loop_video.camera`, `[video]` | ja |
| Spark als Maske | Zellen des echten dunklen Sparks (< 0.12 Luma) = Fenster | `kickoff_loop_f16.dark_mask` | bedingt |
| Wortwand | Begriff in Zeilen übers ganze Bild, Loop läuft darin weiter, feste helle Colorway je Begriff | `f16.wall`, `wall_colors`, `lift` | bedingt |
| Vorhang | Loch = Plakat-Spark, springt im Loop-Tempo zur Seite | `f16.curtain`, `curtain_motion` | bedingt |
| Halos auf Bass-Stufen | Zeilen leuchten je Stufe ein, Halo wächst, nie kleiner | `f16.card`, `light_layer` | bedingt |
| Gates | Blitz (WCAG 2.3.1 + Rot), Lesbarkeit, QR, Schnitte auf dem Beat | `kickoff_loop_video.flash_check`, `kickoff.legible`, `f16.report` | ja |

„Bedingt“ = die Idee trägt, der Code hängt an Zwischenvideos (`Vorschau/F17B.mp4`) und an `_f16` und muss erst als
Funktion je Szene herausgelöst werden (RETRO §3 „Struktur“).

## 3. Musik

**Weg im Kick-off:** eigene Drums M1a/b („zu ernst, sehr trocken, nicht menschlich“), M2 Marimba raus, M3-Mashup
„nicht smooth“ → 2.10. „gib mir ne DaVinci-Timeline“ → 8.10. Resolve-Remix kann die Naht nicht (`songcut.py` Docstring).
Ergebnis: **Vadim wählt Stelle und Länge in Resolve, Claude schneidet ganze Takte in Python.**

Befund IGOR'S THEME (`ref/audio/igor_beats.json`, `resolve/schnitt/songcut/songcut.txt`): 81.606 BPM, Takt 2.94097 s,
16tel 0.1838 s, Taktstrich 1 = Songzeit 22.435 s. Der Drum-Loop wiederholt sich alle 4 Takte (gleiche Loop-Stelle
2.4–3.0 dB Spektralabstand, anderer Takt 5.7 dB). F19-Song M4a: Quelle ab 18.143 s, 4 Takte raus bei 5.89 s auf den Boom
des Drum-Einsatzes, Raster nach der Naht −0.4 ms (Gate 8 ms), Länge 13.03 s. Ereignisse immer auf dieses Raster, nie ab
dem synkopierten Drum-Boom zählen (VERLAUF F11).

**Kochrezept: neuen Song schneiden in 15 min**
1. Song nach `<projekt>/ref/audio/`. Vadim legt Start und grobe Länge in Resolve fest (so entstand `start_song_s` aus `song_F9a.wav`).
2. Raster als JSON im Format von `igor_beats.json` (`bpm`, `in_s`, `bar_s`, `sixteenth_s`, `beats_s`). Prüfen: Anschläge
   liegen ~20 ms am 16tel-Raster (IGOR 17–21 ms RMS). **Ein Skript dafür fehlt im Repo**; wie `igor_beats.json` am 30.9.
   entstand (`feaafc2`): unklar.
3. Länge des Drum-Musters bestimmen. Nur Vielfache davon rausschneiden: klingt durchgespielt; 3 Takte = hörbarer Musterwechsel.
4. `songcut.toml`: je Schnitt `at_s` + `bars`; `xfade_ms = 8` (equal-power, endet 12 ms vor der Transiente, die die Naht
   deckt), `snap_ms = 40` (Naht auf die stärkste Transiente), `fine_ms = 30` (Taktlänge am Loop nachmessen).
5. `uv run songcut.py songcut.toml test` (Gegenprobe: Sprung +⅓ 16tel muss anschlagen), dann ohne `test` → `<Code>.wav`,
   `songcut.png` (Wellenform, Naht rot, Taktstriche), `songcut.txt` (Raster nach der Naht ≤ 8 ms).
6. Ende: Nachhall statt Abriss (`f16.song_pad`: Rauschen RT60 3 s, Tiefpass 3.5 kHz, −12 dB, unter dem Song geduckt).
   Song kürzer als Video → bis `end_s` auffüllen, sonst kürzt `ffmpeg -shortest` das Bild (RETRO §5).
7. Lautheit mit `ebur128` messen, **feste** Verstärkung auf −14 LUFS, True Peak ≤ −1 dBTP. Kein `loudnorm`: drückt
   Aufbau → Drop platt (ENTSCHEIDUNGEN 1.10.). F19-Master nachgemessen 10.10.: −14.1 LUFS, LRA 5.2 LU.
8. Claude hört nicht: prüfen über `songcut.png`, `showspectrumpic`/`showwavespic` (Skill Audio 6); Vadim hört ab.

Vor dem nächsten Song einmal verallgemeinern: `songcut.py` ist IGOR-fest (`PROJECT` = fester Pfad `motion-pack/kickoff_loop`,
Marken Drums/Run/Stopp im Bogen, Stopp = `length_s − 0.66`).

**Prozedurales Sound-Rezept** (`src/makernight_audio.py`, `src/makernight_loop.py`, Skill „Audio recipe“)
- Cue-Sheet aus dem Bild-Code, jeder SFX bildgenau: Knistern aufs Flackern, Sub-Boom auf die Zündung, Whoosh mit Pan,
  Riser, Tasten-Klick je Zeichen, Tape-Stop + Reverse-Sog beim Kollaps, Glas-Ping am Schluss.
- BPM + Rasterversatz so, dass der Haupt-Hit auf einen Beat fällt (120 BPM, Raster ab 0.15 s → Beat 16 = 8.15 s Titel).
- Drop: Aufbau 30 % leiser, ~0.2 s Luftloch (nur Reverse-Becken), dann Impact + Four-on-the-floor + Offbeat-Bass + Sidechain.
- Instrumente = kleine numpy-Funktionen (`kick`, `boom`, `bell`, `pluck`, `clap`, `hat`, `snare`, `key_click`, `saw` +
  `sweep_lp`, `reverb` = Faltung mit Rausch-IR). Master: Hochpass 25 Hz, `tanh`, Spitze normalisieren.
- Nahtloser Loop: 1 Zyklus trocken, Überhang auf den Anfang falten, ×3 kacheln, Effekte drauf, mittleren Zyklus nehmen
  (`makernight_loop.arrangement`).
- **Arp Dm9 → Bbmaj9 → C(add9) und der MN-Beat gehören exklusiv der Maker Night** (ENTSCHEIDUNGEN 1.10.). Kick-off = IGOR.
- Altlast: `makernight_audio.main` muxt noch mit `loudnorm=I=-14` → beim nächsten Anfassen auf feste Verstärkung.

## 4. Python-Pipeline

Aus dem Pack-Root (`uv run`). Dauer aus Doku/Commits; „unklar“ = nie notiert.

| Befehl | Ausgabe | Dauer |
|---|---|---|
| `src/kickoff_loop.py sheet [X.toml]` | Kontaktbogen + Loop-Video → `previz/now/` bzw. `previz/review/X/` | warm 4 s, kalt 15 s (`74b61df`) |
| `src/kickoff_loop.py stars [S..]` / `grounds` | Sterne an 3 Bahnstellen / blanker Grund → `previz/variants/` | 25 s / 3 s |
| `src/kickoff_loop.py test [N..]` | Selbsttest am fertigen Bild (Bahn, Titel fest, Glühen, Cache-Trace) | 5 s |
| `src/kickoff_loop.py preview X.toml --draft` | `*_draft.mp4` + `report_draft.txt`, Hardlink `Vorschau/<Code>_draft.mp4` | 9–40 s |
| `src/kickoff_loop.py preview X.toml [--master]` | Video, Bögen, Report, Config-Kopie; `--master` = x264 crf 16 | 33–70 s; Master unklar |
| `src/kickoff_loop_f16.py video\|sheet\|test\|still F.toml [beats] [--master]` | Ende F16–F19 auf Basis-Video | unklar |
| `src/kickoff_loop_photos.py [test]` | Fotos → `photos/aligned/NN.png` + Bögen + Report | 1–2 min / 3–10 s |
| `src/kickoff_loop_marks.py test` | Selbsttest Druckmarken → `previz/marks/` | 160 s |
| `src/kickoff_loop.py print` | A3-PDFs 300 dpi mit Marken → `print/` | unklar |
| `src/kickoff_loop_resolve.py schnitt` / `song X.toml` | Resolve-Projekt mit Loop auf dem Raster + Song + Marker / Vorschau + Song je Spur | 3 min / 10 s |
| `kickoff_loop/resolve/schnitt/songcut/songcut.py songcut.toml [test]` | Songschnitt WAV + Bogen + Report | unklar |
| `src/makernight_audio.py` / `src/makernight_loop.py` | Score + SFX, muxt `*_sound.*` / 16-s-Loop + 60-s-Fassungen | unklar |

- **Cache** `_cache/`: Schlüssel = Stil-Dict + Hash der bildbestimmenden Quelltexte (`POSTER_SOURCES`, `DIGITAL_SOURCES`,
  `test` prüft per Trace). Foto-Phase liegt fertig kodiert als Segment (`_cache/video/photo_<key>.ts`, die 4 letzten,
  ~70 MB je Stück). Am 9.10. gelöscht (863 MB) → erster Lauf kalt.
- **Encoder**: Vorschau VideoToolbox q65 (Vadim 3.10.: Tempo vor Qualität), Master x264 `fast` crf 16, Share x264
  `veryslow` CRF 18 (`kickoff_loop/CLAUDE.md`).
- **Reports**: jede Vorschau schreibt `report.txt` mit Gates (Kopfzeile DRAFT beim Entwurf); Befund schlägt Meinung (`CLAUDE.md`).
- **Vorschau-Ordner**: flach `Vorschau/<Code>[_draft].mp4`, Pfad im Abschluss nennen. Falle Hardlink: nach `git mv`
  schreibt `ffmpeg -y` in die alte Datei → vorher löschen (RETRO §5).
- **Keine Worktrees** für Medienprojekte: Fotos, Audio, Cache, Druck sind gitignored und fehlen dort (Vadim 7.10.:
  „sieben Ordner tief“). Pool nur hinter `if __name__ == "__main__"`; Cache parallel = Temp-Datei je Thread (`978955f`).

## 5. Vadims Geschmack

| Ja | Beleg |
|---|---|
| Bayer 4×4 (D3) für alles, Verlauf + Korn statt Fläche | Skill-Tabelle D; HANDOFF_ENDE §1.7 |
| Glühen = exponentieller Lichtabfall; Lichtschweif `glow_layer` | ENTSCHEIDUNGEN 1.10.; HANDOFF_ENDE §2 |
| Stern 6-zackig, immer frontal, Drehung je Loop Vielfache von 60° | ENTSCHEIDUNGEN 30.9. (72° gab 12° Sprung) |
| Titel steht; Effekte laufen dahinter weiter und zeigen sich im Titel invertiert | 30.9. „die Titel bewegen sich ganz komisch“; `3ee4dc7` |
| Alle Colorways, „interdimensional“, gern verrückt | Skill Taste 1.10.; 2.10. „nimm alle Sterne rein, die ich approved habe“ |
| Momentum, absolut flüssig, Ereignisse auf dem Beat | 3.10. „muss absolut clean und flüssig sein“; „das Ende muss das Momentum vom Loop matchen“ |
| Echtes Material: echte Pixel, echte Fotos, Bearbeitung nur auf dem Plakat | F15 „warum ein neuer Spark statt der echten?“; HANDOFF_FOTOS §2 |
| Kurz: Kick-off-Video 10–15 s | 2.10. „gesamtes Video nicht 30 s“; F19 = 15.0 s |
| Der Stern füllt den leeren Raum, kein Weißraum | Skill-Tabelle K |

| Nie | Beleg |
|---|---|
| Lila im Kick-off (gehört der Maker Night), MN-Arp/Beat außerhalb der MN | Skill; ENTSCHEIDUNGEN 1.10. |
| Flache Farben, einzelne Buchstaben umfärben, Drop-Shadow, harte Boxen/Konturen um Schrift | HANDOFF_ENDE §1.7; v005 Caption-Box |
| Effekte hinter Titel/QR abgeschnitten | O13: „zum vierten Mal“ (`kickoff_loop_end.py:791`) |
| Pop-ins, Neu-Erscheinen, Springen | 1.10. „nichts poppt ein, Jumping sieht scheiße aus“; F14 „Titel poppen“ |
| Fade to Black, langweiliges Schwarz am Ende | O16 „einfach ein Fade to Black“; HANDOFF_ENDE §1.4 |
| Beat-Crop-ins / Kamera-Stöße | 2.10. „diese kleinen Beat-Crop-ins weg“ |
| Halo, das atmet oder schrumpft | F15 „Halos atmen zu viel, werden wieder weniger“ |
| Standard-Effekte (Dissolve, Wipes), CRT/Scanlines/Glitch-Look, Hypno-Tunnel | Skill-Tabelle F; H1–H5 „schrecklich“ |
| Agenten werfen Freigegebenes raus | 2.10.: 7 Sterne ohne Rückfrage entfernt → Regel |
| Schnelle Vollbild-Wechsel (Photosensitivität) | HANDOFF_ENDE §1.6 |

Verworfen, nicht wieder vorschlagen:

| Code | Was | Vadim |
|---|---|---|
| v003 / v004 / v005 | verbeulter Hof / Kipp-Scheibe / Caption-Box | „als hätte es ein Dreijähriger gemalt“ / „absolute Katastrophe“ / „keinen harten QR-Code“ |
| H1–H5 | Hypno-Endkarte | „schrecklich“ |
| E1a–c | Drop: Pixel-Explosion, Dimensionssprung, Wand | „alle E-Versionen sind scheiße“ |
| M1a/b | eigene Techno-Drums | „zu ernst, sehr trocken, nicht menschlich“ |
| B4 / B9–B10 | Kepler-Bahn / größer über Brennweite | „die Sparks alle so klein“ / „sieht praktisch flach aus“ |
| C4 / C5 | Hell/Dunkel in jedem Frame | „zu hoher Kontrast zwischen zwei Frames“ |
| I2–I8 | Hintergrund-Inseln/Fluss | „8-Bit-Dither-Flair verloren“ |
| O4 / O5 | Wurf-Enden | „stoppt kurz“ / „schießt über, korrigiert, dann Zoom“ |
| O14 / O15 / O16 | Begriffe jedes Bild / mittig / Palette abgedunkelt | „zu schnell“ / „funktioniert nicht richtig“ / „Fade to Black“ |
| M1–M4 (6.10.) | Corona als Distanz-Glühen | „sieht leider auch scheiße aus“ (Befund: Sticker-Rand) |
| F4 | Handkamera 6 px / 0.3° | „viel zu viel Bewegung“ |
| F6 / F7 | Papier rein + raus / Schnitt auf Weiß | „scheiße“ / „noch viel schlechter“ |
| F14 / F15 | Masken-Ende, Zwerg / Geometrie-Stern | „Zwerg, Titel poppen“ / „Mismatch, Posterization fehlt, spackt“ |

## 6. Zeitfresser → Abkürzung

| Zeitfresser | Umfang (Beleg) | Nächstes Mal |
|---|---|---|
| Ende ohne Zielbild | ~90 Varianten über 8 Tage; der Kern (W1 1.10., O17 6.10., `glow_layer` 2.10.) lag früh vor (RETRO §1) | Schlussbild in Schritt 2; geparkte Ideen jede Runde wieder vorlegen |
| Zu viele Varianten je Runde | F9 6, F10 9, F11 8, F12 7; Skill sagt „Offer 4–6 variants“ | max. 3, eine Achse; Skill-Regel ersetzen |
| Regel nicht als Gate | Effekte hinter Titel/QR 4× angemahnt, Gate nie gebaut (RETRO §3.1) | jede harte Regel am selben Tag als Gate am fertigen Bild |
| Sprünge an Nahtstellen | Loop-Neustart, O4/O5, O11, F7, F14, F15 (RETRO §3.2) | Naht-Gate an jedem Schnitt: Helligkeit, Maske, Tempo vorher/nachher |
| Nachbau statt echt | F15 Geometrie-Stern, M1–M4 Distanz-Glühen | gelobte Funktion bzw. echte Pixel wiederverwenden |
| Musik per Agent komponiert | M1 → M2 → M3 verworfen (1.–2.10.), `songcut` erst 8.10. | Vadim wählt Stelle in Resolve, Claude schneidet Takte (Abschnitt 3) |
| Ein Skript je Version | `_f11` … `_f16` je 500–730 Zeilen; F19 = 3 Stufen über `Vorschau/F17B.mp4` + `M4a.wav` | ein Modul, eine Funktion je Szene; Master aus einem Befehl |
| Kontext-Aufblähung | `kickoff_loop/CLAUDE.md` 7.9 → 90 KB; `_end.py` 1702 → 1981 Zeilen; Aufräum-Agent lief nie | `CLAUDE.md` ≤ 120 Zeilen, Verlauf nach `docs/`; verworfener Code im selben Commit raus |
| Agenten-Worktrees | bis 6 parallel am 1.10., ohne Medien; „sieben Ordner tief“ | kein Worktree für Medien; Agenten nur für reine Code-Module |
| Fehlrenders | 2–3 je Runde, Fehler erst am Bild gesehen (HANDOFF_ENDE §3) | erst Bogen + Selbsttest, dann Video |
| Report-Rauschen | „0/64 in Stufe A“, „Finale 0.64 C“ vom 6.10. bis in F17B | Fehlmessung sofort fixen oder löschen, rote Tests nie stehen lassen |
| Vorschau-Chaos | 5 Ordnertypen, 7.5 GB (6.10.) | `Vorschau/<Code>.mp4` ab Tag 1 |
| Langsamer Render | `preview` warm 117 s / kalt 330 s vor `74b61df` | Inhalts-Cache + Foto-Segment ab Tag 1 (danach 33 / 57 s) |
| Diktat und Deutung | „Vundzwanzig“ = 25; Plakat 52 und „Daniela ganz zu sehen?“ nie bestätigt | Zahlen, Codes, Deutungen in einer Zeile zurückfragen |

## 7. Checkliste vor dem Zeigen

Am fertigen Bild gemessen, nicht an der Palette (VERLAUF „So arbeiten“). Fehlt das Gate, steht „von Hand“.
- [ ] **Titel/QR**: Effekte laufen hinter Titel und QR weiter. Gate fehlt (RETRO §3.1) → von Hand an 3 Standbildern.
- [ ] **Keine flache Farbe**: jede Fläche im Korn zwischen zwei Stufen; exakte Stufen k/5 rendern flach (Skill). Kein Lila
      (`is_lilac`, `load` bricht ab).
- [ ] **Nahtstellen**: Loop-Neustart (Stern betritt und verlässt das Bild ganz, Drehung Vielfaches von 60°); an jedem Schnitt
      Helligkeit, Maskendeckung, Tempo vorher/nachher; Entwurf auf Zweiern gegen Master auf Einern (F15).
- [ ] **Beat**: Schnitte auf dem Raster, Gegenprobe +3 Bilder schlägt an (F19: 5/5 ok, Gegenprobe 0/5).
- [ ] **Lesbarkeit**: `kickoff.legible` ≥ 0.95 auf jedem Bild mit Text; QR dekodiert (`check_qr`, ≥ 2 von 4 Modulgrößen).
- [ ] **Blitz**: `flash_check` (≤ 3/s auf ≤ 25 % der Fläche, Rot-Regel). Gate seit 2.10. aus („Farben dürfen crazy gehen“),
      Messwert trotzdem in den Report; keine schnellen Vollbild-Wechsel, Warnung beim Posten (HANDOFF_ENDE §1.6).
- [ ] **Halos**: nie kleiner (F19: größter Rückgang 0.03 %/Bild, Gate 0.3).
- [ ] **Ränder**: keine schwarzen Ecken durch Rollen/Wackeln (`plate_size`, HANDOFF_FOTOS §4).
- [ ] **Ton**: −14 LUFS statisch, True Peak ≤ −1 dBTP, Song reicht bis `end_s`, Ende klingt aus.
- [ ] **9:16**: Text frei von der Reels-UI unten/rechts. Im Kick-off nie geprüft (VERLAUF „Offen“) → von Hand.
- [ ] **Report sauber**: keine bekannten Fehlmessungen, kein roter Test als „Altfehler“.
- [ ] **Abschluss**: Pfad `Vorschau/<Code>.mp4` nennen und in einer Zeile, welche Achse sich geändert hat.
