# SPARK Motion Pack

Alles prozedural (Python + ffmpeg). Skripte in `src/`, jede Ausgabe in ihrem eigenen Ordner, jede Galerie als `index.html` darin.

| Ordner | Was | Erzeugt von |
|---|---|---|
| `editor/` | **Live-Editor** (Browser, GPU): alle Sterne als Shader, Vorlagen Kick-off/Maker Night/Event/Folie, Formate A3/9x16/16x9/1x1/4x5, Kampagne + Varianten + Balance | `cd editor && npm run dev -- --port 5199` |
| `kickoff/` | **Kick-off-Kampagne** 14.10.: bunte Unikat-Plakate ohne Lila, QR eingebettet, Hex-Easter-Egg | `src/kickoff.py` |
| `styles/` | **Maker-Night-System**: freigegebene Bausteine (Codes D/P/S/F/R), Unikat-Plakate A3, Looks mit Figma-Ebenen, Bewegungstests | `src/styles.py` |
| `makernight/sparks/` | „Sparks make the night“, v1 + **v2 (Pixelraster, Clash-Bit)** | `src/makernight_sparks.py` |
| `makernight/teaser/` | 14,5-s-Teaser lila→lavendel + Sound | `src/makernight.py`, `src/makernight_audio.py` |
| `makernight/loop/` | nahtlose Musik-Loops | `src/makernight_loop.py` |
| `pack/` | Transitions, Accents, Loops (ProRes-Alpha, MP4, GIF) | `src/motionpack.py`, `src/gallery.py` |
| `stills/` | PNG-Stills mit Alpha für Figma/Poster | `src/stills.py` |
| `vectors/` | SVG-Templates und Elemente | `src/vectors.py` |

Aufruf immer aus diesem Ordner: `uv run --with numpy --with pillow --with scipy --with scikit-image python src/<skript>.py …`

## Kick-off-Kampagne (`kickoff/`) · 14.10., 17:00

`kickoff/index.html` öffnen. Bunte Plakate auf dem Maker-Night-System, aber **ohne Lila** (Lila gehört exklusiv der Maker Night, `styles.lila()` prüft das).
Satz: Codename-Kopfzeile, riesiges SPARK, KICK-OFF + Datum, JOIN US mittig über dem eingebetteten QR (Verlauf in den zwei hellsten Stufen, Platte dithert in den Grund aus).
Jeder QR wird nach dem Rendern mit OpenCV dekodiert, sonst bricht der Lauf ab.
Lesbarkeit (`legible()`, 0..1) ist gemessen: A >= 0.95 fuer sichtbare Orte, B >= 0.88, C = Kunst, je versteckter desto wilder.
Sterne im Kick-off (Stand 26.9.): S2 S7 S33 + Labor S13 S14 S19d S23 S24 S26 S31 S31b–f S36 S40. Raus: S19c, S34 S35 S37 S38 S39 S41 S42 S43. Ort ist noch offen: `COPY["where"]` in `src/kickoff.py`.

**Easter Egg:** Kopfzeile links `07/18 7075` = Nummer der Colorway + Hex-Stück. Alle 18 sammeln, nach Nummer reihen, `xxd -r -p` → `SECRET` in `src/kickoff.py`.

```sh
uv run -q --with numpy --with pillow --with scipy --with qrcode --with scikit-image --with opencv-python-headless python src/kickoff.py 24 1
uv run ... python src/kickoff.py one P17 S33 K1 9x16      # ein Plakat; Labor-Sterne per Code, z. B. S31
uv run ... python src/kickoff.py fav                       # nur Favoriten (FAV in kickoff.py), laufen in jeder Serie mit
uv run ... python src/kickoff.py edit                      # Editor: http://localhost:8765, P/S/K + Stern frei platzieren, Live-Vorschau, Export
uv run ... python src/kickoff.py grid                      # alle P x S x K als Vorschau + gemessene Lesbarkeit A/B/C -> kickoff/grid/index.html
```

## Maker-Night-System (`styles/`)

`styles/index.html` öffnen. Codes sind stabil, verworfene Codes werden nie neu vergeben. Quelle der Wahrheit: `AXES` in `src/styles.py`.
`ja` = im Plakat-Mix, `neu` = zur Auswahl, `geparkt` = im Blick. Stand 2026-09-25 abends:

| Achse | ja | neu / geparkt |
|---|---|---|
| **T** Typo | T2 Clash-Bit | |
| **D** Dither | D3 Bayer 4x4 | geparkt: D1, D2 |
| **P** Colorway | P1 P5 P6 P8 P9–P16 | neu: P17–P26. Maker-Night-Plakate nur Lila (P1 P5 P8 P12), alles Bunte = Kick-off |
| **S** Spark | S2 Verlauf, S7 XOR-Nest | neu: S33 Matrjoschka; geparkt: S5 (nur M5), S12 (nur Look L5); Labor S13+ in `styles/lab/spark/` |
| **K** Komposition | K1 Riese | neu: K2 Aufgang, K3 XOR-Titel, K4 Koloss, K5 Ecke, K6 Kern, K7 Sturz, K8 Wand |
| **R** Pixel | R3 = 4 px bei 1080p | geparkt: R1 |

Raus: alle F (CRT), S12 aus dem Mix, Bewegung M2/M3/M6. Bewegung kommt jetzt aus dem Labor (`styles/lab/motion/`, M11–M15).
Kopfzeile rechts = Codename der Colorway (`CODENAME`), kein „DIM 042“ mehr.

```sh
python src/styles.py                    # alles
python src/styles.py board|looks|posters|overlays|motion
python src/styles.py posters 24 7       # 24 Plakate, Serie 7
python src/styles.py one L2 a3          # ein Code (D/P/S/K/R, L, M), Format 16x9|9x16|a3
```

## Motion Pack (`pack/`)

Galerie: `pack/index.html`.

### Was ist drin

| Ordner | Wofür | Format |
|---|---|---|
| `pack/mov_alpha/{9x16,16x9}/{transition,accent,loop}/` | DaVinci, Premiere, Final Cut, After Effects, Keynote | ProRes 4444 **mit Alpha**, weiß. Jede Farbe über Tint/Color, jeder Composite Mode |
| `pack/mp4/{16x9,9x16,1x1}/{mono,ink,spark,navy}/` | PowerPoint, Keynote, Web, Hintergründe | H.264, fertig eingefärbt, nahtlose Loops |
| `pack/gif/{dots,halftone,solid}/` | Slack, Notion, Web, Vorschau | 480×480, Weiß auf Schwarz |
| `pack/gif/color_{spark,red,yellow,ink}/` | dasselbe in Farbe | 480×480, Stil „dots“ |

**Stile:** `dots` = 1-Bit-Bayer-Dither (E-Ink) · `halftone` = Rasterpunkte · `solid` = glatte Kante · `fine` (nur per `one`) = feinere Dither-Punkte

## Typen

- **transition** (21 Frames, 0,84 s): deckt das Bild zu und wieder auf. **Frame 10 ist voll bedeckt, dort liegt der Schnitt.**
  Nur die erste Hälfte verwenden = Intro/Outro-Blende nach Weiß, nur die zweite = Reveal aus Weiß.
  `wipe_left wipe_up wipe_diag iris iris_spark spark_spin diamond clock spiral thirds blinds tiles dissolve ripple ripple_spark eink_flash`
- **accent** (15 Frames): Beat-Akzente, decken nie ganz zu. `ring_pulse spark_pop flash burst`
- **loop** (50 Frames = 2 s, nahtlos): Hintergründe, Zwischenscreens, Folien. `rings_flow spark_flow spark_rotate breathe plasma sparkle stripes scan tiles_twinkle waves gradient static`

## In Resolve

Clip auf eine Spur über das Video legen und im Inspector den Composite Mode wählen:
- **Difference** invertiert das Video unter den Punkten, wie das Intro in v01.
- **Normal** legt weiße Punkte oder Flächen drüber (Umfärben: Color › Offset, oder Fusion-Tint).
- **Screen** / **Add** hellt auf und lässt das Video durchscheinen.
- **Als Übergang:** Den Transition-Clip so über den Schnitt legen, dass sein Frame 10 genau auf dem Schnitt liegt. In Normal deckt Weiß den Schnitt ab, in Difference passiert der Wechsel unter invertierten Punkten.
- **Als echte Maske zwischen zwei Clips:** in Fusion das Overlay als Mask auf ein Merge legen.

Falls Resolve das Alpha nicht erkennt: Clip Attributes › Alpha Mode › Straight.

## Neu rendern, andere Farben oder Größen

```sh
uv run --with numpy --with pillow python src/motionpack.py                     # ganzes Pack (~2 min)
uv run --with numpy --with pillow python src/motionpack.py one iris_spark 16x9 halftone spark mp4
#                                                     name   aspect style  palette fmt [kind]
```

Aspects: `9x16 16x9 1x1 gif`. Palettes: `mono ink spark navy red yellow`, eigene trägst du oben in `PALETTES` ein.
Formate: `mov` (Alpha), `mp4`, `gif`. `spark_spin` gibt es als Transition und als Loop (`spark_rotate`).
Einen neuen Effekt legst du mit einer Zeile in `TRANSITIONS` / `ACCENTS` / `LOOPS` an: eine Funktion `(grid, p) → Feld 0..1`.

## Stills für Figma, Poster, Social (`stills/`)

Standbilder als **PNG mit Alpha**, Galerie in `stills/index.html`. Erzeugt von `stills.py`.

`stills/<format>/<farbe>/<name>__<stil>.png`

| Format | Pixel | Wofür |
|---|---|---|
| `poster_a3` | 3508 × 4961 | A3 hoch, 300 dpi (skaliert sauber auf A2/A1, da Punktraster) |
| `16x9` | 3840 × 2160 | Slides, Screens, Beamer, YouTube |
| `9x16` | 1080 × 1920 | Story, Reel, Status |
| `4x5` | 1080 × 1350 | Instagram-Feed |
| `1x1` | 1080 × 1080 | Quadrat-Post, Profil |

**Farben:** `white` und `navy` (#1A3A6E). **Stile:** `dots`, `fine`, `grain` (Zufallskorn wie im Spark-Wallpaper), `halftone`, `solid` (Grauverläufe gibt es nicht als `solid`).

**Umfärben in Figma:** PNG einfügen, farbiges Rechteck (oder Verlauf) darüberlegen, beide auswählen, PNG liegt unten, dann **Use as mask** (⌥⌘M).
Die Figuren skalieren mit dem Format mit, deshalb nicht ein 1x1 auf Postergröße ziehen, sondern das passende Format nehmen.

```sh
uv run --with numpy --with pillow python src/stills.py                          # alles (~10 min)
uv run --with numpy --with pillow python src/stills.py one spark_echo 16x9 dots # ein Design
```
Neues Design: eine Zeile in `SPARK` oder `TILES`, Funktion `grid → Feld 0..1`. Bausteine: `star_d`, `star_line`, `fill`, `cells`, `h`.

## SVG für Figma (`vectors/`)

Echte Vektoren auf Basis des Master-Sterns (`Sporga/assets/digital/logo/spark_filled.svg`). Galerie: `vectors/index.html`. Erzeugt von `vectors.py` (~3 s).

| Ordner | Inhalt |
|---|---|
| `<format>/templates/` | 14 fertige Maker-Night-Layouts je Format, Text editierbar (Clash Display + Satoshi). Platzhalter `XX.XX.` / `Raum XX` ersetzen |
| `<format>/solid/` | 61 Vektor-Designs: Heroes, Hintergründe, Rahmen (`frame_*`), Muster, Kacheln |
| `<format>/dither/`, `halftone/` | alle Stills-Designs als Pixel-Quadrate bzw. Rasterpunkte (ein Pfad pro Datei) |
| `_elements/icons` | 27 Einzel-Sterne, 1000×1000 |
| `_elements/badges` | Sticker, Textringe ("SPARK · MAKER NIGHT"), Starbursts |
| `_elements/corners` | Motiv oben links, in Figma drehen/spiegeln für die anderen Ecken |
| `_elements/bands` | 3000×360 Streifen: Ticker-Text, Kacheln, Sterne (Header/Footer) |
| `_elements/dividers` | 2000×60 Trennlinien |
| `_elements/patterns` | nahtlose 400×400-Kacheln für Figma-Musterfüllungen |

Formate: `poster_a3` 842×1191 (A3 in pt), `16x9` 1920×1080, `9x16` 1080×1920, `4x5` 1080×1350, `1x1` 1080×1080.
Farbe ändern: Layer auswählen, Fill ändern. Texte der Templates stehen oben in `vectors.py` (`COPY`), Farbkombis in `TEMPLATES`.

## Maker-Night-Teaser + Sound (`makernight*.py`)

| Skript | Ergebnis |
|---|---|
| `makernight.py 16x9` / `9x16` (`preview` = Stills) | `makernight/teaser/`: 14,5-s-Clip lila→lavendel: `*.mp4` (Master), `*_share.mp4` (~30 MB), `*_prores.mov` |
| `makernight_audio.py` | `makernight/teaser/makernight.wav` + alle Videos als `*_sound.*` (-14 LUFS) |
| `makernight_loop.py` | `makernight/loop/loop_full.wav` (mit Drums), `loop/loop_bed.wav` (nur Pad+Arp), je 16 s nahtlos + `_60s.wav/.m4a` |

Texte: `COPY` in `makernight.py`. Farben: `PAL`. Nahtlos loopen nur die `.wav` (AAC hat Encoder-Lücken).

### „Sparks make the night“ (`makernight_sparks.py`)

8,5 s bei 120 BPM, Bild und Ton aus einem Skript. Ein Funke schweißt den Titel: pro Buchstabe fährt ein Kopf die Kontur ab, jeder startet auf einer 16tel. Bei 2,0 s der Drop (Buchstaben laufen weißglühend voll, Blitz, Ruck), dann das Datum, ein angeschnittener Spark-Stern geht auf wie die Sonne, am Ende zerfällt die Schrift in Glut und der Funke am „M“ zündet neu. Bild und Ton loopen nahtlos.

**v2 (2026-09-25):** alles auf einem logischen Pixelraster (`px=4` → 480x270, nearest-neighbour hochskaliert), Schrift und Stern ohne Antialiasing (Treppenkanten, die beim Drehen krabbeln), kleine Zeilen in DepartureMono, **kein Funken-Platzen mehr** im Drop und am Datum. Titelschrift nur noch Clash-Bit (Terminal Grotesque / TRMNL21 sind mit T3/T5 rausgeflogen). v1 (`sparks_16x9.mp4`, `sparks_9x16.mp4`) bleibt zum Vergleich liegen.

| Aufruf | Ergebnis in `makernight/sparks/` |
|---|---|
| `makernight_sparks.py` | `sparks_v2_clash_16x9.mp4`, `…_9x16.mp4` (H.264 + AAC, -14 LUFS), `sparks.wav` |
| `makernight_sparks.py 9x16 px=6` / `16x9 prores` | ein Format, gröberes Raster / zusätzlich ProRes 422 HQ |
| `makernight_sparks.py preview` | Stills der Schlüsselmomente + Kontaktbogen (landen im Ordner, `_preview/` sammelt alte) |
| `makernight_sparks.py audio` | nur `sparks.wav` |

Braucht Clash Display und Satoshi (Fontshare) in `~/Library/Fonts`.
Wie und warum das so gebaut ist: Skill `spark-motion` (`~/.claude/skills/spark-motion/SKILL.md`).
```sh
uv run --with numpy --with pillow --with scipy python src/makernight.py 16x9
uv run --with numpy --with scipy python src/makernight_audio.py
uv run --with numpy --with scipy python src/makernight_loop.py
```
