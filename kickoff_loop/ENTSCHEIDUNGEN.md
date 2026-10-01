# Kick-off Loop · Entscheidungen mit Befund und Archiv

Nachschlagen, nicht beim Session-Start lesen. **Vor jedem Vorschlag hier und im Skill `spark-motion` prüfen**, ob die Idee
schon verworfen ist. Aktueller Stand und nächste Schritte: `CLAUDE.md`.

## Entscheidungen

| Datum | Entscheidung | Warum |
|---|---|---|
| 3.10. | ~~Z4/Z5~~ archiviert, W1/W2 geparkt; neue Enden (digitaler Loop, andere Bahn) beim Agenten `enden` | Vadim: „die Enden habe ich schon bewertet, deswegen machen wir die neuen. W1/W2 Idee cool, aber erstmal parken“ |
| 3.10. | Enden: **genau 1 digitaler Umlauf**, dann neue Bahn und weg. ~~O1–O3~~ (Bremsen + Zoom aus dem Stand, Schleuder seitlich, zur Kamera). O4/O5 Richtung ok, Ausführung nicht | Vadim: „nur noch EINEN Loop und dann zack, sonst zu teasing“; O4 „stoppt kurz, keine flüssige Linie“, O5 „schießt über, korrigiert, dann Zoom“ → „muss absolut clean und flüssig sein“, neue Session |
| 1.10. abends | Enden **O6/O7** gebaut (O4/O5 → `archiv/review/alt/`), wartet auf Vadim | Befund am alten Stand: O4 Bildtempo nach dem Wurf 46 → 3 px/Bild (Gerade mit exponentiellem Raumtempo wird in der Perspektive langsamer); O5 Wachstum x8.1 am Wechsel, Mitte bremst in 8 Bildern, Kern schrumpft gegen den Zoom (wirkt rückwärts). O6: 1/Z gesteuert, Bildtempo 50 → 86 px/Bild bis zum Fluchtpunkt. O7: Kamera taucht ab F29 ein, Zoomrate nur steigend, Mitte läuft ohne Umkehr aus (Ruhe ~(520, 1221)), Puppen bis zum Punkt, Dreiecksblende (Kasten kehrt den Kontrast um). Gates: Bahn clean + Stroboskop am Bild |
| 1.10. spät | O6/O7 Runde 2: Loop x1.6/Beat, O6 x8, O7 Zielpunkt [0.55, 0.5] (Hermite), Satz morpht in die Karte (kein Einfliegen, kein Neu-Erscheinen), Verlauf läuft in der Schrift (2 Stufen), Video 14.7 s (Karussell 2 Takte), JOIN US einfarbig | Vadim: „Wegschleudern zu langsam“, „Zoom nicht mittig, nervig“, „Text nicht verschwinden und neu kommen“, „nichts poppt ein, Jumping sieht scheiße aus“, „Video zu lang“, „JOIN US nie unterschiedliche Buchstabenfarben“. Befund: 3 Verlaufsstufen → Lesbarkeit 0.85, 2 → 0.95; Drehung x2 bei Loop x1.6 → Wagenrad |
| 3.10. | **Grund V3**: Verlauf radial vom Stern (je ferner, desto radialer), Rain/Melt zwischen den Dither-Stufen, Spannweite 1.8 | Vadim: „linear, aber mit Rain/Melt, subtil; Gradient soll mit dem Loop Sinn ergeben, dunkler um den Stern bei F17“ → „wir nehmen V3“. V1 (nur Melt), V2 (Fluchtpunkt fest) archiviert |
| 3.10. | **Grund bleibt linearer Verlauf** (kein `[ground]` in `loop.toml`). ~~Inseln I2–I4~~, ~~Fluss I5–I8~~, I1 geparkt („okay“) | Vadim: „die Hintergründe haben ihren 8-Bit-Dither-Flair verloren, da find ich den Linear-Gradient noch am besten, subtil reicht“. Befund: der Flair ist der **stetige** Lauf über die Bayer-Schwellen (jede Zeile eine andere Dichte); harte Stufen/Quadrate machen flache Flächen gleicher Dichte, hohe `gain` macht ganze Stufen. Code (`styles.ground_shape`, `grounds`) bleibt, ohne `[ground]` bitgleich |
| 3.10. | **S45 raus**, **S48c → S48e** (Poly-Glitch), **S58 → S58b** (ohne 1-px-Kante), **S60 → S60d** (ohne Pfütze, Halo ohne Lücke), **S59 → S59b** (ohne Pinselschlaufe), N1 in `loop.toml` | Vadim: S45 „öde“, S60b/c „beschissener“ als S60, „bei S59 den Halo/Kreis entfernen, danach approved“ |
| 2.10. | **Alle freigegebenen Sterne im Loop** (18), jeder Frame ein anderer Stern, nur S33 F1–4 doppelt (`repeat_ok`) | Vadim: „nimm alle Sterne rein, die ich approved habe", „immer Wechsel zwischen Frames", „nichts muss raus". S13 S14 S24 S26 S31 S31e S50 hatten Agenten am 1.10. wegen Messwerten ohne Rückfrage ausgeschlossen |
| 2.10. | Regel: Agenten werfen nichts Freigegebenes raus. Ein schlechter Messwert kommt in den Report, die Entscheidung trifft Vadim | s. o. |
| 2.10. | **Farbe C5b** (Split-Tone, Hell-Dunkel in 2 Blöcken) | Vadim: „c5b finde ich am besten, das ist Basis ab jetzt" |
| 2.10. | ~~Drop-Konzepte E1a–c~~ (Pixel-Explosion, Dimensionssprung, Wand) | Vadim: „alle E-Versionen sind scheiße". Stattdessen: Loop endet auf großem Stern in der Mitte → Infinite Zoom (beschleunigt/abbremsend) → Schwarz, ggf. Platzhalter-Info |
| 2.10. | Musik: Basis M2a, Video 16–20 s, Brumm-Fade-in, kurze Pause mit Hall vor dem Drop | Vadim: „springt zu sehr", „gesamtes Video nicht 30 s", „Loop zu langsam" |
| 2.10. | **Bahn B20c** (Ellipse ganz vor dem Betrachter, `ahead` 1.3, `front_dwell_frac` 0.6, `size` 0.85) | Vadim: zentral bildfüllend → links → hinter SPARK → rechts → zentral; „mehr große Sparks vorne". B20/B20b raus, B19 + B20d–g geparkt |
| 2.10. | `screen_frac` / `ends_dwell_frac` gebaut, nicht gewählt (B20d–g geparkt) | Befund B20c: sichtbarer Weg 0.08–0.26/Frame (×3.3). Gleichmäßig im Bild = ×1.0. Vadim blieb bei B20c |
| 2.10. | **T16 = 48 Wechsel pro Takt** (nicht 24) | 16.32/s × 2.94 s Takt. 24 wären 16tel-Triolen (8.16/s); CLAUDE.md hatte sich verrechnet (Musik-Agent fand es) |
| 2.10. | ~~Kamera-Stoß auf den Hits~~ (`punch_frac` 0) | Vadim: „diese kleinen Beat-Crop-ins weg" |
| 2.10. | ~~Blitz-Check als Gate~~ (`flash_gate` false) | Vadim: „Blitzcheck soll weg, Farben dürfen crazy gehen" |
| 2.10. | Farbe: Hell-Dunkel nicht in jedem Frame wechseln (C4/C5 → C4b/c, C5b/c) | Vadim: „zu hoher Kontrast zwischen zwei Frames". Befund: Grund ΔE ~0.8 in jedem Frame |
| 2.10. | ~~Musik M1a/M1b~~ (eigene Techno-Drums) | Vadim: „zu ernst, sehr trocken, nicht menschlich". Stattdessen IGORs Drums, Spaß, Sprung auf ~48 s (Tyler singt) |
| 1.10. | **Plakate und Video getrennt** | Vadim: „wir trennen echte Plakate vom Video komplett, also lösen sich da einige constraints". Leere Frames ok („drucke ja sowieso einige Plakate nur für das Video") |
| 1.10. | **Bahn B19: Ellipse** (`width` 0.5, `ahead` 0.85, `kepler_frac` 0, `height` 0.12), Stern größer als sein Vorbeiflug-Abstand | Befund (Skript, 32 Frames): perspektivisch korrekt (Kepler, B4–B10) ist der Stern nur 1 Frame pro Seite groß, eine gleichmäßige Kreisbahn läuft 6–8 von 16 Frames leer. Vadim: „an den Seiten riesig … elliptisch" und „man fühlt, wenn der Spark nicht genug Zeit hatte". Also Comic-Größe und echte Zeit. B19 gewählt aus B15–B20. `height` 0.12, weil die Riesen bei 0.33 unten aus dem Bild fallen |
| 1.10. | ~~B9/B10~~ (größer über Brennweite) | Vadim: „sieht praktisch flach aus". Tiefe = Größenverhältnis nah/fern, dort nur ×2.5 |
| 1.10. | ~~Bahn diagonal/senkrecht (B11–B13), Tiefenbumerang (B14)~~ | Vadim: „wir bleiben beim normalen Loop". `plane_roll_deg` bleibt als Regler (0) |
| 1.10. | ~~Kepler-Bahn B4/B4b~~ (Stern kleiner als Abstand) | Vadim: „die Sparks alle so klein". Kepler schnellt hinten, ist nah nur 1 Frame groß |
| 1.10. | **Farbe C1** (32 Frames, eine gemischte Reise über die dunklen Colorways), nicht C2 (Welt pro Durchgang) / C3 (4 Welten im Loop) | Vadim: „C1 am besten, gerne verrückter" → C1b–d |
| 1.10. | P6 (CGA) nicht verwendbar | Sein Grund dithert Schwarz + #FF55FF zu Lila. `load` prüft jetzt jedes Plakat, nicht nur Mischungen |
| 1.10. | Papier nur mit hartem Wechsel, nie gemischt mit Dunkel; P16↔P21 nicht mischen | Auf halbem Weg sind Grund und Tinte gleich hell (unlesbar, `load` bricht ab). P16↔P21 bei 50 % wird Mauve (#A05B86): Papiergruppen {P23 P22 P16} und {P21 P24} |
| 1.10. | **Tempo T16** = 16.32 Plakate/s (32tel-Triolen auf IGOR) | aus T8/T12/T16/T24 mit IGOR darunter |
| 1.10. | **Sterne** neu: S50 Fokuslinien, S48c/S48d Linsenfehler (chromatische Aberration), S54c Skizze Studie. ~~Aquarell S51/b/c~~ raus | Vadim direkt beim Sterne-Agenten: „s54c richtig gut, s48d auch richtig gut", „alles muss natürlich unter dem dither layer sein". Kein schwarzer Rand. S49 S52 S53 S55 nicht gewählt |
| 1.10. | Selbsttest Hand (S54-„Würfel"): längste gerade Schraffurkante am Titel/QR ≤ 20 Zellen, an festen Sternlagen | Alter S54: 79, S54b 9, S54c 13. Feste Lagen, weil Frame 1/16 der neuen Bahn leer sind (der Test war nach dem Bahnwechsel blind) |
| 1.10. | Selbsttest Bahn: geschlossen, links rein, rechts raus | Die Ellipse hatte ein vertauschtes Vorzeichen (Stern kam rechts herein); der Test schlägt daran an |
| 1.10. | Blitz-Check mit WCAG-Rot-Regel (R/(R+G+B) ≥ 0.8, Abstand u'v' > 0.2) | Rot gegen gleich helles Grau sah der alte Check nicht, der Selbsttest schlägt jetzt an |
| 1.10. | **QR glüht, R2 Licht**: Ruhezone 1 Modul (`quiet_cells` 2), Lichtabfall exponentiell über 12 Zellen, rund, JOIN US frei 4 Zellen darüber, kippt pro Buchstabe | Vadim wählte aus G1–G6 und R2–R6 („nicht so viel Padding"). Die Gauß-Kuppe liest sich als Box mit Saum, der Lichtabfall als Glühen |
| 1.10. | Selbsttest Glühen: pro Abstandsring nach außen nie heller **und alle Seiten gleich hell** | Der Ringtest allein ließ den verbeulten v003-Hof durch |
| 1.10. | JOIN US in der Tintenstufe (letzte Stufe) | Auf Papier war die hellste Stufe der Grund selbst, JOIN US verschwand im Glühen |
| 1.10. | Labor-Stile S15–S20, S25, S28 nicht im Loop | Ignorieren die Bahn, S25 braucht eine Zweitpalette |
| 1.10. | Zeitachse aus dem Musik-Raster (JSON) | Das Karussell folgt der Musik. `load` prüft, dass `burst_beats` zur Luft vor dem Drop passt |
| 1.10. | Lautheit als feste Verstärkung auf −14 LUFS statt `loudnorm` | Der Regler drückte Aufbau → Drop platt |
| 1.10. | ~~Maker-Night-Drop im Kick-off~~ | Der Beat gehört exklusiv der Maker Night. Nur IGOR, Custom-Mashup |
| 1.10. | ~~Hypno-Endkarte~~ (H1–H5) | Vadim: „schrecklich", Endkarte neu |
| 30.9. | Stern ist **6-zackig**, Drehung pro Loop ein Vielfaches von 60° | 72°/Loop gab 12° Sprung am Neustart |
| 30.9. | **Stern immer frontal** (Kipp-Scheibe gebaut und entfernt) | Vadim zu v004: „absolute Katastrophe" |
| 30.9. | **Titel fix** | Vadim: „die Titel bewegen sich ganz komisch". Selbsttest vergleicht Satzmasken |
| 30.9. | ~~Caption-Box~~ (v005), ~~verbeulter Hof~~ (v003) | „keinen harten QR-Code" / „als hätte es ein Dreijähriger gemalt" |
| 30.9. | Letzter Frame mit Stern voller Körper (S2) | Wird im Ausbruch bildfüllend. Ringe (S33): Blitz 40 % der Fläche, S2: 16 % |
| 30.9. | Kamera: exponentieller Zoom + Rollen −4° → 0° + Stoß 5 % auf jedem Hit | „zu wenig Bewegung". Rollen endet waagerecht (pixelgenauer Wechsel ins Digitale) |
| 30.9. | Digitalteil 24 fps: Ausbruch ½ Beat, 2 Negativ-Frames | „Framerate der digitalen Version ganz nice" |
| 30.9. | Grading: Umgebung jeder Platte auf mittlere Helligkeit 0.22 | Blitz v003 ohne: 45 % der Fläche, mit: 12 % |
| 30.9. | Resolve: Keyframes nur über Fusion, Stern-Editor statt Resolve-Rendering | `resolve/RECIPE.md`. Nur Python hält Pixelraster + Dither exakt |

## Archiv: Plakate = Frames (bis 1.10. abends)

Bis zur Trennung waren die Loop-Frames die Plakate. Das gilt nur noch, falls die Campus-Plakate aus Loop-Frames entstehen.

- **Aushang** = ungerade Framenummer, hängt auf dem Campus und muss allein tragen. **Fotoframe** = gerade, einmal gedruckt,
  fotografiert, wieder ab. 16 Frames = 8 Aushänge + 8 Fotoframes, Stil wechselt alle 2 Frames (Aushang + Fotoframe teilen ihn).
- Druck: A3 hoch (√2), dieselben Dateien auch A4 hoch. Plätze: 18 × A4 hoch, 56 × A3 hoch, 10 × A4 quer. Lieber mehrere
  Exemplare als mehr Motive. `print`: Aushänge 2-seitig (Rückseite „BITTE NICHT ABHÄNGEN"), Fotoframes einseitig, randlos.
- Shooting: Hochformat, Hauptkamera 1x, Plakat mittig auf ~1/3 der Fotohöhe, gerade von vorn, kein Blitz. Fotoframe am Ort
  seines Aushangs. 3–5 Fotos pro Frame, Name `NN_…`. `photos/aligned/NN.png` ersetzt in der Vorschau die Simulation.
- Stern-Editor in Resolve (`resolve/EDITOR.md`): Projekt `SPARK_Kickoff_Loop`, Timeline `Stern-Bahn`, 1 Timeline-Frame =
  1 Plakat-Frame, `push`/`pull`/`check`. Stand 16 Frames, am Bild nicht bestätigt.
- Bahn bis 1.10.: Kreis um den Betrachter, sichtbarer Bogen `sweep_deg` [-78, 73], `far_rush_frac` 0.7 (nah langsam). Der Stern
  verließ das Plakat nie, der Neustart sprang von rechts groß nach links groß (Vadim: „Loop nicht clean").
