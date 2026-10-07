# Zumo-Sprites · Handbuch

8-Bit-Sprites des Pololu Zumo 2040 fuer die Maker Night (Spumo, Spormula E, Area Capture): suess, aus jeder Richtung,
animiert, als System nutzbar (Figma, Resolve/AE, Python-Motion, Slack/Telegram). Gerendert aus dem echten STEP, nicht
nachgezeichnet. Logik `src/zumo_sprites.py`, alle Werte `zumo_sprites.toml`, Demo `src/zumo_sprites_demo.py`.

## Befehle (aus dem Repo-Root)

```
uv run src/zumo_sprites.py variants          Variantenbogen Z1..Z7 -> previz/now/variants.png (Vadim waehlt per Code)
uv run src/zumo_sprites.py look Z4           eine Variante gross, 8 Ansichten, Echtfarben + P1 -> previz/now/look_Z4.png
uv run src/zumo_sprites.py sheet [Z4]        alle Richtungen x Paletten + 4 GIFs -> previz/now/
uv run src/zumo_sprites.py test [Z4]         Selbsttest am fertigen Sprite (Loop, Ketten, Augen, Durchsicht, Leinwand)
uv run src/zumo_sprites.py export Z4         alles -> ~/vault/Files/03 Work/Spark/Assets/Zumo Sprites/Z4/ (~5 min)
uv run src/zumo_sprites_demo.py              Sumo-Demo (Iso, P1, Z7) -> previz/now/demo_sumo.{mp4,gif}
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
- `seq/natural/<ansicht>_<richtung>/<anim>/0000.png`: @4x RGBA-Sequenzen fuer Resolve/AE (4 px = Raster R3 bei 1080p).
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
- Ritzelkreise mit 36/18 Segmenten (durch 6 teilbar): 60 Grad Drehung = deckungsgleich, Loop nahtlos.
- Pool: `OPENBLAS_NUM_THREADS=1` (gemessen: Export 6 min, Systemzeit > Nutzerzeit durch BLAS-Ueberbuchung).

## Varianten (Codes stabil, nie umnummerieren)

Z1 CAD 2 mm/px · Z2 Spielzeug 2 mm/px · Z3 Chibi 2 mm/px (Kopf 1.3) · **Z4 Chibi 2.6 mm/px (Standard-Vorschlag)** ·
Z5 Mini 3.2 mm/px · Z6 Gross 1.5 mm/px · Z7 = Z4 mit Sticker-Kontur.

## Stand 7.10. (Nacht)

Exportiert: Z4, Z7. Demo `demo_sumo` (Z7, P1). Selbsttest gruen fuer Z2-Z7 (Z1: Loop/Durchsicht nicht geprueft, die
STEP-Ritzel haben keine 60-Grad-Symmetrie).

## Offen

- Vadims Wahl: Groesse/Variante (Z-Code), Kontur, welche Paletten exportiert werden sollen.
- Demos fuer Spormula E (Linie folgen, Draufsicht 16 Richtungen) und Area Capture (Schleife faehrt, Flaeche fuellt sich in
  Bayer) — gleicher Aufbau wie `zumo_sprites_demo.py`.
- Zwischenrichtungen fuer `tq` (16 statt 8) falls Kurvenfahrten in Iso gebraucht werden: eine Zeile in `[views.tq]`.
- Schattenebene als eigene Ebene (heute in der Demo gezeichnet).
