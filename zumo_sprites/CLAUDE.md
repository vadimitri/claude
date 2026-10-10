# Zumo-Sprites · Handbuch

8-Bit-Sprites des Pololu Zumo 2040 fuer die Maker Night (Spumo, Spormula E, Area Capture): suess, aus jeder Richtung,
animiert, als System nutzbar (Figma, Resolve/AE, Python-Motion, Slack/Telegram). Gerendert aus dem echten STEP, nicht
nachgezeichnet. Logik `src/zumo_sprites.py`, alle Werte `zumo_sprites.toml`, Demo `src/zumo_sprites_demo.py`.

## Befehle (aus dem Repo-Root)

```
uv run src/zumo_sprites.py variants          Variantenbogen Z1..Z9 -> previz/now/variants.png (Vadim waehlt per Code)
uv run src/zumo_sprites.py look Z4           eine Variante gross, 8 Ansichten, Echtfarben + P1 -> previz/now/look_Z4.png
uv run src/zumo_sprites.py eyes Z4           Augenbogen E1..E6 (3/4 + Heck, idle + win) -> previz/now/eyes_Z4.png (~30 s)
uv run src/zumo_sprites.py sheet [Z4]        alle Richtungen x Paletten + 4 GIFs -> previz/now/
uv run src/zumo_sprites.py test [Z4]         Selbsttest am fertigen Sprite (Loop, Ketten, Augen, Durchsicht, Leinwand)
uv run src/zumo_sprites.py export Z4         alles -> ~/Nextcloud/Sporga/assets/motion/zumo/sprites/Z4/ (~5 min; bis 8.10.
                                             lagen Exporte in ~/vault/Notes/03 Work/Spark/Assets/Zumo Sprites/)
uv run src/zumo_sprites_demo.py              Sumo-Demo (Iso, P1, Z7) -> previz/now/demo_sumo.{gif,mp4} + demo_sumo_alpha.mov,
                                             Kopie nach <export>/demo/ (GIF + ProRes 4444 transparent, MP4 auf Nacht-Grund)
uv run --with trimesh --with networkx src/zumo_sprites.py mesh    nur wenn sich das glb aendert -> ref/zumo_mesh.npz
```
`--no-open` unterdrueckt das Oeffnen. Quelle: `~/Movies/ZumoWire/zumo.glb` (aus dem Pololu-STEP, siehe ZumoWire/README).

## Pipeline

STEP-Mesh (oder Spielzeug-Modell) -> Rasterizer mit 6x6 Supersampling -> pro Pixel Mehrheitswahl Material (gewichtet) ->
Licht in 3 Baendern (Cel) -> Kettenstollen ueber die Bogenlaenge der Kette (laufen mit) -> Material-Inseln < 3 px weg ->
Vertiefung -1, Lichtkante oben/links +1, Innenlinien hinter Tiefenspruengen -> Augen und LEDs als Stempel -> Kontur.
Gerechnet wird im Wertraum 0..5 (Index 1..6, 0 = frei, ab 10 LED-Akzente); Farbe erst beim Export ueber die Palette.

## Export (pro Variante ein Ordner)

- `sheets/<palette>/<ansicht>_<anim>.png` (+ `@4x`): P-Mode-PNG, Zeile = Richtung (Reihenfolge `dirs_deg`), Spalte = Frame.
  Umfaerben = Palette tauschen (Aseprite, Python). Paletten: `natural` (Echtfarben), `value` (exakte Graustufen k/5 fuer
  die Spark Lens in Figma), `P1`.
- `seq/<natural|value>/<ansicht>_<richtung>/<anim>/0000.png`: @4x RGBA-Sequenzen fuer Resolve/AE (4 px = Raster R3 bei 1080p;
  `value` + Spark Lens in Resolve = jede Colorway).
- `gif/`: alle Animationen @4x mit 1-Bit-Transparenz (Slack, Telegram, Web). `index.html` = Galerie mit Grundwahl.
- `atlas.json`: Rahmengroesse, Drehpunkt (Bodenpunkt unter der Robotermitte, in allen Frames gleich), Richtungen, fps.

Ansichten: `top` 16 Richtungen (Arena, Linienrennen), `tq` 8 Richtungen bei 30 Grad (= echtes 2:1-Iso), `side` 2, `front` 2
(270 = zur Kamera, 90 = Heck). Richtung = Fahrtrichtung im Bild, 0 = rechts, 90 = weg/oben, 270 = zur Kamera.
Animationen (8 Frames, 12 fps): drive, reverse, turn_left, turn_right, idle, push, win, ko, sleep, love.

## Entscheidungen (mit Befund)

- **Spielzeug-Modell statt CAD als Standard** (7.10.): das STEP-Mesh bei 2 mm/px rauscht (hundert SMD-Teile, Schrauben,
  Elko-Cluster werden Flecken). Das Spielzeug-Modell nimmt die Masse aus dem STEP (Kettenschleife, Achsen, Platine, OLED,
  Schild, IR-Halter, per Bounding-Box gemessen, Konstanten oben im Spielzeug-Abschnitt) und baut sie aus Grundkoerpern.
  Z1 = CAD bleibt als Vergleich.
- **Augen = Stempel, nicht Textur**: verzerrte Augen (Foreshortening) lesen sich nicht. Draufsicht: Lage aus dem 3D, Gesicht
  dreht mit. Sonst Zeichner-Logik: beide Augen auf einer Zeile, 1 px in Fahrtrichtung (Befund: physikalisch standen sie bei
  Fahrt nach rechts uebereinander). Runde 3x4-Augen lasen sich als "+" (Funkeln) -> 2x3-Bloecke.
- **Licht frontal oben links** (-0.5, 0.6, 0.7): Deckel hell, Kameraseite mittel, rechte Flanke Schatten. Vorher lag die
  ganze Kameraseite im Schatten und die Ketten verschwanden in 3/4.
- **Schwarz lebt in Stufen 0..3**, Stahl 3..5, Gesicht 5. Schild mit Bayer-4x4-Verlauf (D3 des Systems), oben fast weiss.
- **Rueckscheibe hinter jedem Ritzel + Hals unter dem Kopf**: sonst sieht man durch die Speichen das andere Ritzel bzw.
  der angehobene Kopf schwebt. Beides im Selbsttest.
- **Kontur**: dunkel (Z4) fuer helle Gruende, Sticker-Kontur Stufe 4 (Z7) fuer dunkle Maker-Night-Gruende.
- **Schild = Keil, Unterkante vorne** (Vadim 7.10.: war falsch herum). Befund CAD: Unterkante x 57.8..58.9 mm, Oberkante
  ~49.6. Die Bounding-Box sagt nicht, welche Diagonale: Richtung immer an Vertices in Hoehenbaendern pruefen.
- **Kette nur in der Kettenschleife** (Vadim 8.10.: "von vorne sind die Ketten nicht sichtbar, der Verlauf geht nicht bis
  an die Raender"). Befund: die Band-Regel (Kette optisch 4.5 mm dick) markierte alles bei |z| 35..49.5 mm als Kette,
  auch ausserhalb der Schleife -> die Schildraender wurden Kette, in allen Ansichten. Jetzt nur 0 <= Abstand <= Band; der
  Selbsttest misst es (5632 falsche Abtastungen von vorne mit dem alten Fehler). Schild hat jetzt Kettenbreite (99 mm).
- **Referenzen**: Pololu-Guide in `~/Nextcloud/Sporga/projects/makernight2026/hardware/zumo_2040/polulu_zumo_guide/images/`
  (0J12327 = 3/4 vorne mit Schild, 0J12328 oben, 0J12330 Seite, 0J12331 = **hinten** (nicht vorne!), 0J3930/0J3931
  Masszeichnungen Chassis, 0J6259 IR-LEDs in schwarzen Schrumpfschlauch-Roehrchen oben an der Front).
- **Augen abschaltbar** (`[eyes] show`): Vadim findet sie suess, will aber auch den Zumo "wie er ist" (OLED schwarz) -> Z8, Z9.
- **Demo = echte Pixel-Art** (Vadim 7.10. zur ersten Fassung: Ring "zu High Fidelity", Bewegung "nicht posterized", "zu
  fake"): flache Flaechen in Palettenstufen, kein Bayer-Lichtkegel, keine weichen Verlaeufe; alles auf 12-fps-Ticks und
  ganzen Pixeln, Keys linear (kein Smoothstep), Funke als Stempel. Das gilt fuer jede Szene mit diesen Sprites.
- **Augenregel E5** (Vadim 8.10.: 3/4 vorne/hinten "nicht so suess", mit dem Keil nach oben wirkt er "andersrum").
  Befund: das OLED steht physikalisch nach hinten (Pololu-Text von vorne kopfueber, Foto 0J12327), ein aufrechtes Gesicht
  von hinten liest sich als Front. E5: tq 45/90/135 ohne Augen (Hinterkopf), tq 225/315 Augen 20 % nach vorne und auf
  der Bildschirmebene (Iso-Treppe, 2 px Versatz). Codes E1..E6 in `[eye_styles]`, Bogen `eyes`, Wahl `[eyes] style`.
  **Die Ansichten, die Vadim gut fand, bleiben unangetastet** (Vadim 8.10.): Draufsicht, Seite, Front (auch Heck
  front 90), tq 0/180/270. Gemessen: Augen in 207/207 Sprites pixelgleich zum Stand 8.10., Draufsicht/Seite/Front 0 px.
- **3/4 bereinigt** (`[views.tq] tidy`, Vadim 8.10.: "manche 3/4 sehen nur verpixelt aus"). Befund: die Vertiefung
  (tiefer als das Minimum im Umkreis) dunkelte in 3/4 steile Ebenen fleckig ab, 406 px auf dem ebenen Schild in tq 225.
  Jetzt nur konkav (tiefer als die Mitte zweier gegenueberliegender Nachbarn) + Wert-Inseln < 3 px gehen im Umfeld auf
  (Bolzen, Linsen, Elkos ausgenommen; 5 px frisst die Ritzel). Beides nur in tq; Selbsttest misst den Schild.
- **Demo v3** (Vadim 8.10.): schneller (10 px/Tick), A (315) rammt B (225) an der Flanke und schiebt ihn ueber die
  vordere Kante (Fall vor der weissen Kante bleibt sichtbar), Rand 8/4 px, Kante weiss mit 1-px-Lippe Stufe 4, Ring mit
  Kontur, Grund transparent (Slides, Videos). Kontakt-Gate am Boden statt im Bild: in Iso ueberdecken sich die Sprites
  auch ohne Beruehrung (430 px), deshalb Abstand der Drehpunkte = Schildspitze + halbe Breite (37.7 px) +- 1.5.
- Ritzelkreise mit 36/18 Segmenten (durch 6 teilbar): 60 Grad Drehung = deckungsgleich, Loop nahtlos.
- Pool: `OPENBLAS_NUM_THREADS=1` (gemessen: Export 6 min, Systemzeit > Nutzerzeit durch BLAS-Ueberbuchung).

## Varianten (Codes stabil, nie umnummerieren)

Z1 CAD 2 mm/px · Z2 Spielzeug 2 mm/px · Z3 Chibi 2 mm/px (Kopf 1.3) · **Z4 Chibi 2.6 mm/px (Vadim 8.10.: gewaehlt)** ·
Z5 Mini 3.2 mm/px · Z6 Gross 1.5 mm/px · Z7 = Z4 mit Sticker-Kontur · Z8 = Z4 ohne Augen · Z9 = Z7 ohne Augen ·
Z10 = Z6 ohne Augen (Detail-Grossaufnahmen). Vadim 8.10.: Z4 mit Augen ist der Look, Z8 (ohne Augen) und Z7 (Sticker)
bleiben parallel, Z10 fuer Detail-Shots. Augenregel: E1 Stand 8.10. · E2 Hinterkopf · E3 + nach vorne ·
E4 + 3/4-Gesicht (fernes Auge schmal) · **E5 + Bildschirmebene (Standard)** · E6 = E4 + Bildschirmebene.

## Szenen, Maskottchen, Emoji (10.10.)

Logik `src/zumo_scenes.py`, alle Werte `zumo_sprites/scenes.toml`, Ausgaben in `previz/` (gitignored, reproduzierbar).
Sprites kommen unveraendert aus `zumo_sprites.py` (Z7 in den Szenen, Z4 fuer Maskottchen und Emoji).

```
uv run src/zumo_scenes.py sheet       Kontaktbogen: je Szene 4 Keyframes (P1 + natural), Maskottchen, Emoji
                                      -> previz/scenes/sheet.png (~1 s mit Sprite-Cache, ~5 s kalt)
uv run src/zumo_scenes.py scenes [spumo|spormula|capture]   -> previz/scenes/<name>/
                                      <name>.gif (P1, transparent, 540 px) + _ground.gif + _natural(_ground).gif,
                                      _1080x1080.mp4 + _1080x1920.mp4 (P1 auf Grund, Loop 3x), _alpha_value.mov
                                      (ProRes 4444, exakte Grautoene k/5: in Resolve faerbt die Spark Lens)
uv run src/zumo_scenes.py mascot      -> previz/mascot/mascot_{P1,natural,1c}.{svg,png} (PNG 300 dpi, 25.1 cm breit)
uv run src/zumo_scenes.py emoji       -> previz/emoji/zumo-<name>.gif (Slack 128 px, natural), emoji/P1/,
                                      emoji/telegram/zumo-<name>.png (512 px, statisch)
uv run src/zumo_scenes.py test        Selbsttest an den fertigen Dateien -> previz/scenes/report.txt
uv run src/zumo_scenes.py all         scenes + mascot + emoji + sheet + test (~2 min, Rechner unter Last)
```

Szenen (je 48 Ticks = 4 s bei 12 fps, nahtlos):
- **spumo** (Iso): Choreografie der Demo v3 (A rammt B an der Flanke, schiebt ihn ueber die Kante), dann KO-Sterne ueber
  B, B verpufft, A faehrt rueckwaerts zurueck, B faellt am Start vom Himmel (Schatten vorab, Staub beim Landen).
- **spormula** (Draufsicht): Kamera faehrt mit dem Feld (zwei Zumos auf Spur B), der dritte kommt auf dem zweiten Pfad
  (Spur A), ueberholt beide und kreuzt die Ziellinie als Erster; Sterne aus der Zielflagge. Bodencodes (2 Querbalken)
  vor dem Ziel.
- **capture** (Draufsicht): Rechteckschleife wie `tracking/zumo_schleife.py` (geradeaus, 90 Grad auf der Stelle), Spur
  in Teamfarbe, zurueck im Land fuellt sich die Flaeche in 4 Zeilenbaendern, Freudensprung, dann an die neue Kante.
- Emoji: idle, love (Herzen steigen), win, ko (Sterne kreisen), sleep (Z steigen), drive, push, spin (8 Richtungen).

Entscheidungen (mit Befund):
- **Szene = reine Funktion Tick -> Index-Bild**, Loop nahtlos am Zustand statt modulo: der Test rechnet Tick 48 weiter
  und vergleicht mit Tick 0 (alle drei 0 px). Gegenprobe Tick 40 (1892 / 3348 / 4528 px). Von Hand eingebaut 10.10.:
  Endkey von A 2 px daneben -> "weicht in 855 px ab", Test rot.
- **Lineare Keys gemessen**: Schrittweite pro Tick schwankt je Abschnitt hoechstens 1 px (Iso: 1 Schritt). Smoothstep
  eingebaut -> 6 Abschnitte rot. Iso-Diagonalen laufen in ganzen Schritten (2 px x, 1 px y); getrennt gerundet faellt die
  Treppe um 1 px aus der Diagonale.
- **Ganze Pixel und nur Palettenfarben** an jedem GIF-Tick und PNG (k x k-Bloecke einfarbig). Weiche Skalierung
  (bilinear + quantize) eingebaut -> rot. ProRes value gemessen: Abweichung von k/5 hoechstens 1/255, keine Buntheit,
  Alpha 1 Bit.
- **GIF-Dauer 8/9/8 Hundertstel** = genau 12 fps: 1000/12 ms gibt es im GIF nicht (die Demo speichert 80 ms = 12.5 fps).
- **Spumo-Reset**: A faehrt mit 4 Iso-Schritten/Tick zurueck und steht, bevor B landet. Befund: mit 2 Schritten/Tick
  landete B bei Tick 41 genau im Kontaktabstand neben A, die Sprites ueberlappten.
- **Spormula ohne Weiche pro Weltperiode**: gerechnet, das Ueberholen braucht ~20 Ticks bei 6 px/Tick Kamera, die Weiche
  waere laenger als die Periode (288 px). Deshalb zwei durchgehende Pfade; nahtlos, weil der Ueberholer bei Tick 0 und
  48 ausserhalb des Bildes ist (Gate). Gate: Ueberholer im Ziel bei Tick 34, Fuehrender bei 39. Funke der Demo (Stufe 5)
  waere auf der weissen Flaeche unsichtbar -> Sterne ueber der Flagge.
- **Capture**: Kamera faehrt nur im letzten Abschnitt mit (Land rueckt um die Schleifenbreite 96 px nach), sonst steht
  das Bild und die Schleife ist lesbar. Land Stufe 3: Stufe 2 auf der Plane (1) war im Kontaktbogen kaum zu sehen.
- **Teamfarben** = Index 20+ mit eigener Farbe je Palette (natural: Magenta) oder Stufe (P1, value). Schluessel `step`,
  nicht `value`: eine Palette heisst `value` (Kollision, beim ersten Lauf gefunden).
- **Maskottchen tq 315 love + Herz** (wie A, der Sieger): verglichen tq 270/225/315, front 270. Front und tq 270 sind ein
  Kasten mit Gesicht, 3/4 zeigt Ketten und Ritzel. 1c = Stufe 0 (Kontur, Innenlinien, OLED), Augen bleiben Shirt;
  tq 315 hat weniger Ritzel-Flecken als 225. SVG: Laeufe zu Rechtecken, gleiche Farben zu einem Pfad vereint (in P1
  leuchten LEDs und Herz in Stufe 5: der Test fand SVG 14 px vs PNG 43 px, solange es zwei Pfade gleicher Farbe gab).
- **Emoji**: ein Massstab fuers Set (x2 Slack, x8 Telegram), Sticker-Ring Stufe 5 um den Zumo (dunkle Kontur fuer
  helles Slack, weisser Ring fuer dunkles), Partikel mit Kontur 0. 5-28 KB.
- **Sprite-Cache nach Inhalt** (`previz/scenes/_cache/`, Hash aus zumo_sprites.toml + .py), unter 24 Sprites ohne Pool.
  Gemessen bei Last 25 auf 12 Kernen: 80 Sprites im Pool 53 s, `sheet` braucht jetzt 25 Sprites (5 s kalt, 1 s warm).

Offen:
- Arena: Skill `zumo-2040` sagt, die MakerNight-Arena ist weiss mit schwarzem Rand (invers zum Dohyo); die Szene folgt
  der abgenommenen Demo (dunkel, weisser Rand). Umstellen = `ring_values` in `[spumo]`.
- Regeln: aktuell nur `archive/2026-09-27_vor_neustart/knowledgebase/disziplinen.md` + `tracking/README.md` (Nextcloud).
  Spormula: Pfade, Codes, Runden ja; Zielflagge und das Ueberholen auf dem zweiten Pfad sind Darstellung, keine Regel.
- 9:16 ist die Szene mittig auf Grund (viel Leerraum oben/unten); eigenes Hochformat-Layout, falls fuer Stories gebraucht.
- Simulator (`tracking/sim`, HTML-Replays mit Kontur) nutzt die Sprites noch nicht; Quelle waeren die Draufsicht-Sheets +
  `atlas.json` aus `export`.
- Kopie in den Vault (`[export].dir`) wie bei der Demo: noch nicht.

## Stand 8.10. (Abend)

Branch `claude/zumo-sprites` (Worktree erzwungen). Exportiert: Z4, Z7, Z8, Z9, Z10 mit E5 + 3/4-Bereinigung,
`augen_E1-E6.png` im Vault. Demo v3 (Z7, P1, transparent). Selbsttest gruen fuer Z2-Z10.

## Offen

- Vadim: E5 abnehmen oder anderen E-Code waehlen (eine Zeile `[eyes] style`, dann Export neu).
- Sprites + Demo in die Spark-Vorlagen in Figma (Vadim 8.10.: "muss es in Figma in unserer Spark Template haben").
  Sheets `value` sind die Graustufen fuer die Spark Lens.
- Demos fuer Spormula E (Linie folgen, Draufsicht 16 Richtungen) und Area Capture (Schleife faehrt, Flaeche fuellt sich flach,
  Tick fuer Tick) — gleicher Aufbau wie `zumo_sprites_demo.py`.
- Zwischenrichtungen fuer `tq` (16 statt 8) falls Kurvenfahrten in Iso gebraucht werden: eine Zeile in `[views.tq]`.
- Schattenebene als eigene Ebene (heute in der Demo gezeichnet).
