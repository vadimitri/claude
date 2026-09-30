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

## Neue Sterne (1.10., Agent)

Auftrag Vadim: „Spider-Verse ITSV & ATSV Inspo raussuchen, Animationsstile, coole Sparks kreieren.“ Code in
`src/lab_spark.py` (Abschnitt „Spider-Verse-Serie“), registriert in `kickoff.LAB`. Bogen: `previz/variants/stars_neu.png`
(jeder Stil an Frame 1 groß links / 9 fern / 16 groß rechts, Lesbarkeit im Kopf). Neu rendern:
`uv run src/kickoff_loop.py stars S48 S49 S50 S51 S52 S53 S54 S55` (schreibt `stars.png`).

Alle acht: **frontal**, 6-zackig, **folgen der Bahn** (Lage/Größe/Drehung über `_local(g)` aus `c.L["star"]`), nur
Palettenstufen auf dem Zellraster, `g.lit` gesetzt (Titel kippt per XOR), QR auf allen 16 Frames lesbar. Maße in Zellen
statt Sternradien, wo es Druck-/Strichgrößen sind (Versatz, Strichabstand, Rasterweite): gleich groß auf fernen und nahen
Sternen, druckgleich in A3. Lesbarkeit = Minimum über alle 16 Frames; **Frame 2 ist ein Bahn-Brennpunkt** (Sternspitze
sticht durch „KICK-OFF / 14.“, Datumsbuchstaben kippen halb): dort schon S2 0.96, S45/S47/S31g 0.95.

| Code | Idee (1 Satz) | Quelle | Lesbarkeit min (F2) | Bahn |
|---|---|---|---|---|
| **S48 Fehldruck** | Zwei Druckplatten, die Farbplatte um ganze Zellen verrutscht (fern 3, nah 6 Zellen = Tiefe wie im Film), Ben-Day-Schatten auf der Schattenseite | ITSV Brooklyn/Miles, Farbversatz statt Unschärfe (Technik 05 oben) | 0.97 (0.95) | ja |
| **S49 Krackle** | Heller Stern, dunkler Spalt, Energiesaum in der Mittelstufe, Trauben schwarzer Kirby-Punkte stanzen ihn aus | Jack Kirby „Kirby Krackle“ ([Wikipedia](https://en.wikipedia.org/wiki/Kirby_Krackle)), ITSV-Kollider | 0.96 (0.95) | ja |
| **S50 Fokuslinien** | Keile vom Seitenrand laufen spitz auf den Stern zu, sparen Titelblock und JOIN US + QR aus wie Manga-Linien die Sprechblase | Manga shuuchuu-sen ([Japanese with Anime](https://www.japanesewithanime.com/2020/03/line-effects.html)), ITSV-Speedlines, Trigger/Gainax | 0.97 (0.94) | ja, Linien zielen immer auf den Stern |
| **S51 Aquarell** | Unruhige Lasur, die auf dem Stern sitzt und mitdreht, Pigmentrand als hellste harte Kante, Blütenränder innen | ATSV Gwen/Earth-65 „watercolor-wash“ ([AWN: sechs Stile](https://www.awn.com/news/spider-man-across-spider-verse-feature-six-different-art-styles)) | 0.97 (0.95) | ja |
| **S52 Zine** | Aus der Fotokopie geschnitten: gerade Scherenschnitte (6 pro Flanke, leicht daneben), Toner-Flecken, Klebeband über der unteren Spitze | ATSV Hobie/Spider-Punk: Xerox, Tape, Rasierklinge, Collage ([AWN: Spot + Hobie](https://awn.com/animationworld/unpacking-spot-and-hobies-disruptive-styles-spider-man-across-spider-verse)) | 0.96 (0.94) | ja |
| **S53 Spot** | Weißer Gesso-Stern mit schwarzen Tinten-Löchern (Portale, drehen mit), Bleistift-Konstruktion (Umkreis, Innenkreis, Achsen) scheint durch und läuft über den Umriss hinaus | ATSV The Spot: „gesso … you can still see the construction lines“, weiß mit schwarzen Portalen (AWN, s. o.; [Foundry](https://foundry.com/insights/film-tv/across-the-spider-verse-nuke-mari-katana)) | 0.97 (0.94) | ja |
| **S54 Skizze** | Pergament-Stern mit Federzeichnung: dunkle Kontur, Schraffur auf der Schattenseite (tief gekreuzt, 4 Zellen Abstand), Konstruktionslinien hell auf dem Grund | ATSV Leonardo-Vulture (Renaissance-Skizzenbuch) | 0.97 (0.94) | ja |
| **S55 Halbton** | Echtes Druckraster (runde Punkte, 45°, fest auf der Seite): der Stern fliegt unter der Rasterfolie durch, Punktgröße = Helligkeit, Halbton-Schein | ITSV Ben-Day als Licht (Technik 06 oben) | 0.97 (0.94) | ja, Raster steht, Stern wandert |

Meine Sichtung am Bogen: **S50, S55, S53 am stärksten** (sofort Comic, klein wie groß klar); S48 und S52 gut; S49 und
S51 leiser (bei ⅓ Größe subtil); S54 Geschmackssache (Pergament ist ein Fremdkörper in dunklen Colorways).

**Für Vadims neuen Wunsch „interdimensional, alle bunten Colorways“:** alle acht arbeiten nur mit Palettenstufen und
wirken deshalb in jeder Colorway. Am meisten „andere Dimension je Frame“: S48/S55 (Druck), S52 (Punk-Zine), S53 (Spot),
S54 (Renaissance), S51 (Gwen). Idee, nicht gebaut: den Stil-Zyklus als Dimensionssprung lesen (jeder Stil = eine Welt,
gekoppelt an eine Colorway-Station), dann ist die Farbreise zugleich eine Reise durch die Spider-Verse-Welten.

Unfertig / bewusst nicht gemacht:
- **Frame 2 ≤ 0.95 bei S50, S52–S55** (0.94): Bahn-Frage (Spitze im Datum), nicht Stil-Frage; Ausschneiden der Deko im
  Titelblock half nicht (gemessen). Lösung eher in `[spark]` (Bahn auf Frame 2) als im Stil.
- JOIN US auf großem, hellem Stern: kippt pro Buchstabe (Regel der Hauptsession); S50/S52/S53/S54 halten deshalb eine
  QR-Zone frei (`_qr_zone`, nimmt JOIN US 9 + 4 Zellen aus `[qr]` als Konstante `SV_LABEL_CELLS` an, bei Änderung nachziehen).
- Verworfen beim Bauen: S49 v1 (heller Saum ohne Spalt fraß die Silhouette, sah verbrannt aus → Nähe zur verworfenen
  Brand-Serie), S52 v1 (1 Stützpunkt pro Flanke = gerader Stern statt Spark-Profil; große Tonerflecken = Kuhflecken),
  S54 v1 (Schraffur in Sternradien → nah Balken statt Striche). Keine Schmelze, kein Glitch, kein Echo.
- Recherchiert, nicht umgesetzt: TMNT Mutant Mayhem (Notizheft-Kritzel, Risiko „Dreijähriger“), Puss in Boots (malerisch,
  auf dem Raster schwer), Mumbattan (Ornament ≈ S19d), Nueva York/Syd Mead (Linien-Gravur grenzt an verworfene Scanlines).
- `URTEIL` in `lab_spark.py` für S48–S55 ist ein Platzhalter („neu, Vadim hat noch nicht gewählt“).

Quellen (neu): [AWN: Spot + Hobie](https://awn.com/animationworld/unpacking-spot-and-hobies-disruptive-styles-spider-man-across-spider-verse),
[AWN: sechs Stile](https://www.awn.com/news/spider-man-across-spider-verse-feature-six-different-art-styles),
[Foundry: Spot-Pipeline](https://foundry.com/insights/film-tv/across-the-spider-verse-nuke-mari-katana),
[Kirby Krackle](https://en.wikipedia.org/wiki/Kirby_Krackle),
[Manga-Linien](https://www.japanesewithanime.com/2020/03/line-effects.html),
[SIGGRAPH: TMNT Mutant Mayhem](https://history.siggraph.org/?p=163057),
[AWN: Puss in Boots](https://www.awn.com/animationworld/puss-boots-last-wish-returns-its-fairy-tale-illustration-roots).

## Überarbeitung 1.10. (Vadims Urteil)

Urteil zu `stars_neu.png`: S50 rein wie er ist; S51 „bland“; S54 „zu perfekt“ + „getrennte Würfel“ (Schraffurblöcke,
gerade abgeschnitten an `_qr_zone`/`_type_zone`); S48 „zu Standard“ → chromatische Aberration, crazier. S49 S52 S53 S55
nicht gewählt. Bögen: `previz/review/S_rework_1.png` (Runde 1), `_2.png` (mutiger), `_2_farbe.png`, `_3.png` (alles im Korn).
**Endstand (Vadim): behalten S50, S48c, S48d, S54c. Aquarell (S51, S51b, S51c) raus.** „Alles muss unter dem Dither-Layer
sein“: keine Fläche liegt mehr auf einer exakten Stufe (`_dithered`, `_lightfield`, `DITHER_MIN/SPAN`), auch in S48.

| Code | Idee | Lesbarkeit min (F1/9/16) · F2 | Urteil |
|---|---|---|---|
| S48b Linsenfehler | 3 Platten, um die Plakatmitte verschieden skaliert/gedreht (laterale CA), Licht addiert sich, Außensaum Ben-Day | 0.974 · 0.96 | gut, nicht behalten |
| **S48c** Linsenfehler Bruch | S48b + waagerechte Bänder, die mit ihren Platten verrutschen (nie im Titelblock) | 0.974 · 0.96 | **behalten** |
| **S48d** Linsenfehler wild | Linsenfehler ×2, jedes Plakat ein eigener Fehldruck (Seed aus der Sternlage), Punkt- + Linienraster | 0.975 · 0.97 | **behalten** |
| S51b / S51c Aquarell | Pinselzüge mit Trockenkante, Blüten, Granulation, Spritzer / nasser | 0.975 · 0.96 / 0.95 | raus |
| S54b Skizze Hand | Flanken 3× gezogen, Überschwinger, Schraffur je Facette (1–3 Lagen nach Licht), Wisch-/Radierspur | 0.974 · 0.93 | Zwischenstand |
| **S54c** Skizze Studie | S54b + Konstruktion (Sechseck, Zirkelbögen je Flanke, Einstich), doppelte Schattenkontur, Kreuzkontur | 0.974 · 0.93 | **behalten** |

Befunde:
- **CA trägt nur in Rampen mit Farbwechsel.** In P13 P17 P18 P19 P20 P25 liegen Innen- und Außensaum in zwei Farben
  (blau|gelb, rot|lime, blau|orange), `_2_farbe.png`. In einfarbigen Rampen (P10 P11 P14 P15) nur hell/dunkel.
- Aquarell Runde 1: Rauschinseln mit Umrisslinie lesen sich als Landkarte (Nähe S16 „Europa“), deshalb Pinselzüge.
- „Würfel“ hat einen Selbsttest am fertigen Plakat: `uv run … python src/lab_spark.py test` misst die längste gerade
  Kante des Schraffurfelds an Titel/QR (S54 = 80 Zellen schlägt an, S54b 12, S54c 13, Grenze 20).
- **Frame 2 bleibt ein Bahnproblem:** S54b/S54c 0.93 (Pergament jetzt im Korn, vorher 0.94). Lösung in `[spark]`, nicht im Stil.
- S48c-Bänder grenzen an den verworfenen Glitch (S30b); Vadim will sie trotzdem. S50 hat noch flache Linien/Kontur
  (nicht angefasst, Auftrag „so wie er ist“); falls „alles im Korn“ auch S50 meint, ist das eine Zeile.
