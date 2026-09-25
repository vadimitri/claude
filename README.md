# SPARK Motion Pack

Eine Galerie aller Clips findest du in `index.html` (im Browser öffnen). Alles wird aus `motionpack.py` erzeugt.

## Was ist drin

| Ordner | Wofür | Format |
|---|---|---|
| `mov_alpha/{9x16,16x9}/{transition,accent,loop}/` | DaVinci, Premiere, Final Cut, After Effects, Keynote | ProRes 4444 **mit Alpha**, weiß. Jede Farbe über Tint/Color, jeder Composite Mode |
| `mp4/{16x9,9x16,1x1}/{mono,ink,spark,navy}/` | PowerPoint, Keynote, Web, Hintergründe | H.264, fertig eingefärbt, nahtlose Loops |
| `gif/{dots,halftone,solid}/` | Slack, Notion, Web, Vorschau | 480×480, Weiß auf Schwarz |
| `gif/color_{spark,red,yellow,ink}/` | dasselbe in Farbe | 480×480, Stil „dots“ |

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
uv run --with numpy --with pillow python motionpack.py                     # ganzes Pack (~2 min)
uv run --with numpy --with pillow python motionpack.py one iris_spark 16x9 halftone spark mp4
#                                                     name   aspect style  palette fmt [kind]
```

Aspects: `9x16 16x9 1x1 gif`. Palettes: `mono ink spark navy red yellow`, eigene trägst du oben in `PALETTES` ein.
Formate: `mov` (Alpha), `mp4`, `gif`. `spark_spin` gibt es als Transition und als Loop (`spark_rotate`).
Einen neuen Effekt legst du mit einer Zeile in `TRANSITIONS` / `ACCENTS` / `LOOPS` an: eine Funktion `(grid, p) → Feld 0..1`.

## Stills für Figma, Poster, Social (`stills/`)

Standbilder als **PNG mit Alpha**, Galerie in `stills.html`. Erzeugt von `stills.py`.

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
uv run --with numpy --with pillow python stills.py                          # alles (~10 min)
uv run --with numpy --with pillow python stills.py one spark_echo 16x9 dots # ein Design
```
Neues Design: eine Zeile in `SPARK` oder `TILES`, Funktion `grid → Feld 0..1`. Bausteine: `star_d`, `star_line`, `fill`, `cells`, `h`.

## SVG für Figma (`vectors/`)

Echte Vektoren auf Basis des Master-Sterns (`Sporga/assets/digital/logo/spark_filled.svg`). Galerie: `vectors.html`. Erzeugt von `vectors.py` (~3 s).

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

| Skript | Ergebnis in `makernight/` |
|---|---|
| `makernight.py 16x9` / `9x16` (`preview` = Stills) | 14,5-s-Clip lila→lavendel: `*.mp4` (Master), `*_share.mp4` (~30 MB), `*_prores.mov` |
| `makernight_audio.py` | `makernight.wav` + alle Videos als `*_sound.*` (-14 LUFS) |
| `makernight_loop.py` | `loop/loop_full.wav` (mit Drums), `loop/loop_bed.wav` (nur Pad+Arp), je 16 s nahtlos + `_60s.wav/.m4a` |

Texte: `COPY` in `makernight.py`. Farben: `PAL`. Nahtlos loopen nur die `.wav` (AAC hat Encoder-Lücken).

### „Sparks make the night“ (`makernight_sparks.py`)

8,5 s bei 120 BPM, Bild und Ton kommen aus einem Skript. Ein Funke schweißt den Titel: Pro Buchstabe fährt ein Kopf die Kontur ab, jeder startet auf einer 16tel. Bei 2,0 s kommt der Drop, dann das Datum. Ein angeschnittener Spark-Stern geht auf wie die Sonne. Am Ende zerfällt die Schrift in Funken, und der Funke am „M“ zündet neu. Bild und Ton loopen nahtlos.
Stil: 4-px-Zellen, 6 Palettenstufen, scharfe Kanten, geditherte Füllung (Riso). Texte stehen in `COPY`, Layout pro Format in `LAYOUT`, Timing oben in der Timeline (Bild und Ton lesen dieselben Werte).

| Aufruf | Ergebnis in `makernight/sparks/` |
|---|---|
| `makernight_sparks.py` | `sparks_16x9.mp4`, `sparks_9x16.mp4` (H.264 + AAC, -14 LUFS), `sparks.wav` |
| `makernight_sparks.py 9x16` / `16x9 prores` | ein Format / zusätzlich ProRes 422 HQ |
| `makernight_sparks.py preview` | Stills der Schlüsselmomente + `contact_*.png` |
| `makernight_sparks.py audio` | nur `sparks.wav` |

```sh
uv run --with numpy --with pillow --with scipy --with scikit-image python makernight_sparks.py
```
Braucht Clash Display und Satoshi (Fontshare) in `~/Library/Fonts`.
Wie und warum das so gebaut ist: Skill `spark-motion` (`~/.claude/skills/spark-motion/SKILL.md`).
```sh
uv run --with numpy --with pillow --with scipy python makernight.py 16x9
uv run --with numpy --with scipy python makernight_audio.py
uv run --with numpy --with scipy python makernight_loop.py
```
