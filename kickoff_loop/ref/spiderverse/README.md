# Spider-Verse → Kick-off Loop · Referenzboard

Stand 30.9. Quellen: *Into the Spider-Verse* (ITSV, 2018) und *Across the Spider-Verse* (ATSV, 2023).
Board: `board.png` (12 Kacheln, ★ = die 4 stärksten für dieses Stück). Stills in `img/`, Herkunft:
[film-grab ITSV](https://film-grab.com/2019/11/12/spider-man-into-the-spider-verse/) (Nr. = Galerie-Nummer),
[film-grab ATSV](https://film-grab.com/2023/12/11/spider-man-across-the-spider-verse/),
[marilajane: Animation Techniques](https://marilajane.substack.com/p/into-the-spider-verse-animation-techniques) (03, 04, 08).
Nur Referenz, nicht fürs Posting.

Bereits verworfen und hier bewusst ausgespart: Glitch, CRT/Scanlines/LCD, HUD, Sternenfeld, Copper Bars, Blenden/Wipes,
Echo-Kopien als Stil, Spark-Burst/Explosion, weiche Typo. Wo eine Spider-Verse-Technik daran grenzt, steht die Abgrenzung dabei.

## Techniken

| # | Technik | Was (Film) | Wo sehen | Bei uns (Pixel · Dither · Plakat · Stop-Motion) |
|---|---|---|---|---|
| 01 ★ | **Mischraten: Zweier, Dreier, Einser** | Figuren auf 2ern (12 Posen/s), Kamera und Hintergrund auf 1ern. Miles auf 2ern, Peter B. auf 1ern = Können als Bildrate. Hobie mischt 2/3/4 innerhalb einer Figur | [beforesandafters: Hobie](https://beforesandafters.com/2023/06/17/the-across-the-spider-verse-spider-punk-character-hobie-was-animated-with-different-frame-rates-for-different-parts-of-his-own-body-and-accessories/), [marilajane](https://marilajane.substack.com/p/into-the-spider-verse-animation-techniques) · Bild 01 (ATSV #35) | Plakate laufen **auf Dreiern** (8 fps in 24er-Timeline), der Zoom auf Einsen: das ist exakt das Spider-Verse-Prinzip, so lassen. Im Digitalteil springt der Stern auf **Einser** = „jetzt kann er es“. Der Ratenwechsel ist das Ereignis, nicht ein Effekt |
| 02 | **Speedlines + Smear statt Motion Blur** | Kein Motion Blur; Tempo über harte Linien, Smears, gestreckte Geometrie | [Cartoon Brew: „If it's not broke, break it“](https://www.cartoonbrew.com/feature-film/if-its-not-broke-break-it-sony-imageworks-renegade-approach-to-spider-man-into-the-spider-verse-167321.html), [J.-D. Haas, Animationsanalyse (Video)](https://www.youtube.com/watch?v=Dhmc67KcUvQ) · Bild 02 (ITSV #22) | Nur auf dem schnellen Bahnstück (fern, `far_rush_frac`): 3–5 Linien, 1 Zelle dick, parallel zur Flugrichtung hinter dem Stern, Länge ∝ Bildgeschwindigkeit, Palettenstufe 2. Nah: keine. Smear höchstens auf **einem** Zwischenframe (ein Körper, entlang der Bahn gestreckt, kein Echo) |
| 03 ★ | **Impact Frame** | 1–3 Frames: Bild auf 2 Farben reduziert, Figur als Silhouette, dann normal weiter | Bild 03 („KRACK“, ITSV), ATSV #15 (Spot, Schwarz/Weiß-Tusche) | Auf dem Synth-Hit (Wechsel ins Digitale) **2 Frames @24 fps**: ganzes Bild in 2 Stufen der aktuellen Colorway (dunkelste/hellste), Stern + SPARK als flache Silhouette. **Keine** Partikel, keine Zacke = kein Burst. `flash_check`: eine Umkehr = 1 Blitz, unter 3/s |
| 04 | **Lautwort / Typo als Grafik** | Lautwörter perspektivisch im Bild, mit Rasterfüllung und Kontur | Bild 04 („PONK“, ITSV), ITSV #35 („BLAH… BLAH…“), [No Film School: Comic-Panels](https://nofilmschool.com/comic-panels-in-spiderverse-movies) | Kein Lautwort erfinden. Aber „14.10.“ und „17:00“ im Digitalteil wie ein Lautwort setzen: auf dem Schlag in **einem** Frame voll da (kein Einblenden), 1 Zelle Tuschekontur + Versatzplatte (s. 05) |
| 05 ★ | **Farbversatz statt Tiefenunschärfe** | Unschärfe wird durch verrutschte Druckplatten ersetzt: je weiter von der Schärfeebene, desto größer der Versatz | [Cartoon Brew](https://www.cartoonbrew.com/feature-film/if-its-not-broke-break-it-sony-imageworks-renegade-approach-to-spider-man-into-the-spider-verse-167321.html) („color passes were not aligned… made you feel like it was blurry“), [marilajane](https://marilajane.substack.com/p/into-the-spider-verse-animation-techniques) · Bild 05 (ITSV #37, Peter B. vorn doppelt) | Stern bekommt eine zweite Platte in einer **Palettenstufe** (nie RGB), um N **ganze Zellen** versetzt, N = Abstand zur Schärfeebene (fern 2, Mitte 0, ganz nah 3–4). Richtung fest (unten rechts, wie verrutschter Druck), kein Zittern. Titel bleibt deckungsgleich = Schärfeebene. Abgrenzung zu Glitch: fest, palettentreu, tiefengesteuert |
| 06 | **Ben-Day / Halbton als Licht** | Licht und Schatten als sichtbares Punktraster statt Verlauf | Bild 06 (ITSV #64), [GarageFarm: Look in Blender nachgebaut](https://blog.garagefarm.net/blog/recreating-the-spider-verse-look-in-the-blender-node-editor) | Bayer 4×4 ist schon unser Halbton. Neu: **Licht pro Facette** des Sterns (12 Dreiecke, Grat hell/dunkel), feste Lichtrichtung → Dither-Stufe je Facette ändert sich beim Überschlag (s. a) |
| 07 ★ | **Caption Box** | Rechteckiger Textkasten, harte Kontur, flache Füllung, Versalien; erzählt statt Voice-over, sitzt wie aufgeklebt im Bild | Bild 07 (ITSV #16 „EVERYONE KNOWS“), ITSV #34, [No Film School](https://nofilmschool.com/comic-panels-in-spiderverse-movies) | Ersetzt den Hof um JOIN US + QR, s. (b) |
| 08 | **Panel-Split** | Bild in Panels mit Stegen geteilt, Panels poppen einzeln auf, frieren unabhängig ein | Bild 08 (Spider-People-Reihe, ITSV), ITSV #17, [No Film School](https://nofilmschool.com/comic-panels-in-spiderverse-movies) | Das „Aufklappen“ ins 9:16 als Comicseite, s. (c) |
| 09 | **Leap of Faith: Kamera kopfüber** | Kamera steht auf dem Kopf, Miles fällt und wirkt, als steige er | Bild 09 (ITSV #55), [No Film School: beste Shots Lord & Miller](https://nofilmschool.com/best-shots-in-lord-miller) | Kamerarolle im Digitalteil, s. (d) |
| 10 | **Stimmungsfarbe (Gwens Welt)** | Hintergrund färbt sich mit der Emotion um („mood ring“), Aquarell-Lagen | Bild 10 (ATSV #2), [BTL News (Produktionsdesign)](https://www.btlnews.com/?p=126308), [AWN: sechs Stile](https://www.awn.com/news/spider-man-across-spider-verse-feature-six-different-art-styles) | Farbreise gibt es. Zuspitzen: sie bleibt weich, **außer einmal**: beim Hit springt die Colorway in einem Frame auf die der Endkarte. Der einzige harte Farbschritt im Stück |
| 11 | **Tusche + Schraffur statt Shading** | Handgezogene Tuschelinien über CG, Schraffur statt Verlauf; ATSV hatte ein eigenes Inking-Team | Bild 11 (ITSV #26), [beforesandafters: Inking-Team](https://beforesandafters.com/2023/06/28/this-was-the-first-cg-animated-movie-ive-ever-heard-of-that-actually-had-a-dedicated-inking-team/) | Stern-Kontur 1 Zelle in der dunkelsten Stufe, **Dicke = Nähe** (fern 1, nah 3 Zellen). Rückseite der Scheibe als 45°-Schraffur (jede 3. Diagonale) statt Bayer → Vorder-/Rückseite beim Überschlag unterscheidbar |
| 12 | **Grafische Bühne** | Im Schlüsselmoment fällt die Welt weg: Figur vor flacher Farbfläche + grobem Raster | Bild 12 (ATSV #27) | Erster Digitalframe nach dem Impact: Umgebung weg, nur Palettenfläche + ein großes Bayer-Feld, Stern groß. Die gelbe Zacke aus dem Still **nicht** übernehmen (= Burst, verworfen) |

## Empfehlungen

**(a) Bumerang als 3D-Drehung lesbar machen.** Die Scheibe überschlägt sich schon (v004, `tumble_turns`); flach
gestaucht liest sie sich aber als „wird dünner“, nicht als „dreht sich“. Spider-Verse-Mittel, nach Wirkung sortiert:
1. **Vorder- ≠ Rückseite** (11): vorn Bayer-Füllung, hinten 45°-Schraffur oder eine Stufe dunkler. Erst dann sieht man
   den Überschlag, sonst ist Rückseite = Vorderseite gespiegelt.
2. **Hochkant = Kante mit Dicke:** bei ¼ und ¾ (`thin_min_frac`) keine dünne Scheibe, sondern ein Band in der
   dunkelsten Stufe, 2–3 Zellen dick, wie ein ausgeschnittener Comic-Gegenstand.
3. **Licht pro Facette** (06): Grat-Facetten wechseln die Dither-Stufe mit dem Winkel zur festen Lichtquelle.
4. **Tiefe über Platten** (05) und **Konturdicke** (11): fern Versatz 2 + dünne Kontur, nah Kontur 3 Zellen.
5. **Verdeckung:** auf dem fernen Bogen hinter dem Titel, auf dem nahen davor (falls heute immer gleich). Stärkstes
   2D-Tiefensignal, kostet nichts; Lesbarkeit A bleibt, weil nah nur die Randzacken über den Satz ragen (messen).
6. Rund um die Hochkant-Frames 2 **Drehbögen** (kurze gebogene Linien, 1 Zelle) an den Spitzen in Überschlagrichtung.
   Keine Kopien des Sterns.

**(b) JOIN US + QR als Caption Box statt Hof.** Das weiche, runde Glühen ist genau das, was Spider-Verse nie macht.
- **Rechteckiger Kasten, harte Ecken**, flach in der hellsten Palettenstufe, **kein Dither im Kasten**.
  Der Innenrand ist die Ruhezone des QR (4 Module): die Form ist funktional begründet, nicht Deko.
- **Kontur 1 Zelle** in der dunkelsten Stufe.
- **Versatzplatte statt Glow:** derselbe Kasten ein zweites Mal in der Akzentstufe, 2 Zellen nach unten rechts
  (verrutschter Druck, wie 05).
- **JOIN US als Reiter:** eigener kleiner Kasten oben links auf der Kante, andere Füllung (Akzent), 1 Zelle überlappend,
  wie „EVERYONE KNOWS“. Nicht drehen: QR und Kasten bleiben achsparallel auf dem Raster (Decode + saubere Treppen).
- Im Video: im Digitalteil **in einem Frame** da (auf dem Schlag), steht still auf Einsen, während der Stern läuft.
  Gates: `check_qr`, `legible`. Der Hof-Block in `[qr]` (`halo_*`) würde durch `box_*`-Werte ersetzt.

**(c) Übergang Stop-Motion → Digital.** Kein Überblender nötig, die Naht sind drei Schläge:
1. **Match-Cut** (steht schon im Plan): Plakat füllt das Bild, letzte Platte und erster Digitalframe deckungsgleich.
2. **Impact Frame** (03) auf dem Synth-Hit, 2 Frames, 2 Stufen der Colorway. Er kaschiert den Medienwechsel
   (Papier/Wand → reine Pixel) und gibt dem Hit ein Bild.
3. **Ratenwechsel** (01): ab da Stern und Kamera auf Einsen. Das Aufklappen als **Panel-Split** (08): das Plakat zerfällt
   an 2-Zellen-Stegen in 3 Panels (Titel / Stern / QR-Box), jedes springt auf einem eigenen 16tel an seine Endlage
   (hart, kein Gleiten), dann schließen sich die Stege zur Endkarte. Das sind Layoutwechsel auf Schlag, kein Wipe.

**(d) Kamera.** Vadims Entscheidung „Zoom kontinuierlich, nicht schneller werden“ bleibt für den Plakatteil.
- Plakatteil: Plakate auf Dreiern, Zoom auf Einsen (01). Zusätzlich möglich: eine leise **Rolle** von 0 auf 3–4° über
  den ganzen Zoom (gleichmäßig), damit die Fahrt nicht nur Maßstab ist.
- Digitalteil: **Stoßzoom** auf dem Hit (+8 % in 2 Frames, 6 Frames Ausklang, kein Ease-in), **Verwackeln in ganzen
  Zellen** (±1 Zelle, 3 Frames) beim Impact, **Parallaxe**: Titel, Stern, QR-Box als 3 Ebenen, Kamera schiebt leicht,
  die Ebenen laufen verschieden schnell.
- **Leap-of-Faith-Rolle** (09), Option: wenn der Stern heranfliegt, rollt die Kamera um genau 60° mit ihm. Der Stern
  sieht wegen seiner Symmetrie unverändert aus, die Welt kippt: Kamerabewegung, ohne dass der Stern „dreht“.
  Nur vor dem Einrasten des Satzes, Endkarte steht gerade (Lesbarkeit).

## Quellen

- Cartoon Brew, Sony Imageworks' Ansatz (Motion Blur, Druckversatz, Kirby-Punkte, Linien, Einser/Zweier, Smears):
  https://www.cartoonbrew.com/feature-film/if-its-not-broke-break-it-sony-imageworks-renegade-approach-to-spider-man-into-the-spider-verse-167321.html
- Jean-Denis Haas (ILM), Animationsanalyse ITSV (Video, via Cartoon Brew):
  https://www.cartoonbrew.com/educational/an-animation-analysis-of-spider-verse-by-animator-jean-denis-haas-170700.html
- beforesandafters, Hobie mit Mischraten: https://beforesandafters.com/2023/06/17/the-across-the-spider-verse-spider-punk-character-hobie-was-animated-with-different-frame-rates-for-different-parts-of-his-own-body-and-accessories/
- beforesandafters, Inking-Team ATSV: https://beforesandafters.com/2023/06/28/this-was-the-first-cg-animated-movie-ive-ever-heard-of-that-actually-had-a-dedicated-inking-team/
- marilajane, Techniken mit Stills (Zweier/Einser, Halbton, Druckversatz, Lautwörter): https://marilajane.substack.com/p/into-the-spider-verse-animation-techniques
- No Film School, Comic-Panels, Textkästen, Split-Screens: https://nofilmschool.com/comic-panels-in-spiderverse-movies
- GarageFarm, Look in Blender nachgebaut (Halbton, Linien): https://blog.garagefarm.net/blog/recreating-the-spider-verse-look-in-the-blender-node-editor
- Stills: film-grab (Links oben). Zeitmarken in Videos habe ich nicht geprüft; statt Timecodes stehen Galerie-Nummern.
