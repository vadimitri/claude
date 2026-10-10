# SPARK Motion Generator · Arbeitsweise

`~/Developer/spark/motion/generator` (ex `motion-pack`, umgezogen 10.10.; `~/Movies/SPARK_Motion_Pack` zeigt hierher).
Alles prozedural: Python (numpy/scipy/pillow) + ffmpeg, **keine KI-Dienste** (kein Suno/ElevenLabs/Remotion, keine
Recherche-Phase; Vadim: „raw Claude Code“). Designsystem (Codes, Taste, Rezepte, Verworfenes): Skill `spark-motion`.

## Neues Stück („ich will X“)

1. `docs/BRIEF.md`: 6 Fragen in einer Runde, Rezept je Format (Story, Post, Loop, Plakat, Teaser, Zumo-GIF).
2. `docs/PLAYBOOK.md`: Ablauf in 5 Schritten, Geschmack, Zeitfresser, Checkliste. Ende/Schlussbild zuerst, max. 3
   Versionen je Runde, eine Achse.
3. **Claude rendert Bausteine, Vadim schneidet in Resolve** (Vadim 10.10.): `src/kit.py` → Projekt `SPARK_Template`,
   Anleitung `docs/RESOLVE.md`. Kick-off-Effekte (Lens, Glow, Journey, Boil, QR, Wortwand) sind Resolve-Effekte/Elemente.

## Wo ist die Wahrheit (Vadim 10.10.: Split nach Art)

| Was | Quelle | Gespiegelt nach |
|---|---|---|
| Paletten, Dither, Raster, Sterne, Codes | `src/styles.py` (`PALS`, `AXES`), `src/lab_spark.py` (`URTEIL`) | Figma-Variablen `Palette`/`Colorway`, Resolve-DCTLs (`kit.py lens`) |
| Lens-Mathe | `kit.lens` (= `styles.dither`) | Resolve `Spark Lens.dctl`, Figma-Shader „Spark Lens“ v6 (`195f988d`) |
| Marke, Komponenten, Format-Templates, Design Guide | Figma `Spark_Design` (auVIiSNupWpSpzoCjxoVxV, Seite „Start here“) | |
| Folien | Figma Slides `Spark Deck` (ZJlDUBLLwlG5A6aIeYDnSa) | |
| Fertige Team-Assets (Loops, Stems, QR, Zumo-GIFs, Maskottchen) | `~/Nextcloud/Sporga/assets/motion/` (`kit.py publish`) | Resolve-Bins verlinken dorthin |
| Schnitt | Resolve `SPARK_Template` (duplizieren, nie direkt bearbeiten) | |

Typo: Titel **Clash-Bit** (T2 = Clash Display Bold, Wortabstand doppelt), kurzer Text Departure Mono (Vielfache von
11 px), langer Text Google Sans Flex (Design Guide 10.10.).

## Ordner

| Ordner | Was | Handbuch |
|---|---|---|
| `kit/` | Bausteine für Resolve (Lens/Glow-DCTLs, Grau-Elemente, Sound, QR, Wortwand); Ausgabe `kit/out/` (gitignored) | `docs/RESOLVE.md` |
| `kickoff_loop/` | Kick-off-Video **abgeschlossen** (F19, 9.10.), Lieferung `final/` | `kickoff_loop/CLAUDE.md`, Retro `kickoff_loop/docs/RETRO.md` |
| `zumo_sprites/` | 8-Bit-Zumo: Sprites Z4 (+E5), Challenge-Szenen, Maskottchen, Emoji | `zumo_sprites/CLAUDE.md` |
| `makernight/`, `styles/`, `stills/`, `vectors/`, `pack/`, `flow/` | Maker-Night-System (Lila exklusiv MN), Galerien, Spark Flow | `README.md` |
| `editor/` | Browser-Live-Editor (Svelte/WebGPU) | `editor/README.md` |
| `docs/` | Playbook, Brief, Resolve-Anleitung | |
| `Vorschau/` | alle Versionsvideos flach (gitignored), Pfad im Abschluss nennen | |

Projektschema: `<projekt>/` mit `CLAUDE.md` (≤ 120 Zeilen: Stand, Befehle, Entscheidungen mit Befund, Offen) + `<projekt>.toml`
(alle Stellschrauben), Code `src/<projekt>.py` (+ `_*.py`), PEP-723-Kopf → `uv run src/<projekt>.py <befehl>`.

## Code

- **Keine Gestaltungswerte im Code.** Alles Drehbare kommentiert in der TOML, Einheit im Namen (`_s`, `_deg`, `_frac`,
  `_px`, `_cells`). Systemkonstanten in `src/styles.py`. Technische Konstanten mit Namen + Herkunft der Zahl.
- `load()` prüft die Config zuerst und sagt in Klartext, was falsch ist.
- Docstrings: was und **warum**, Deutsch, im Code ASCII (ue/oe/ae).
- Bestehendes wiederverwenden (`kickoff.py`/`styles.py` Hooks `layout`, `type_fn`, `spark_fn`; gelobte Funktionen statt
  Nachbau). `motion/emoji/emoji.py` (Session spark-emoji) importiert `kickoff_loop.load/poster_style` + `styles.render`:
  deren Signatur und das `star`-Format nicht brechen.
- Renders nach Inhalt cachen, Pools nur hinter `if __name__ == "__main__"`, `OPENBLAS_NUM_THREADS=1`.

## Prüfen statt Anschauen

Jede Vorschau schreibt `report.txt` mit Gates; Befund schlägt Meinung. QR dekodieren (`kickoff.check_qr`, `kit.qr_reads`),
Lesbarkeit (`kickoff.legible` ≥ 0.95), Blitz (`kickoff_loop_video.flash_check`), Resolve-Render gegen numpy-Referenz
(`kit.py test`, Testtimelines `00 Lens-Test`/`00 Glow-Test`). Selbsttests messen am fertigen Bild und schlagen am alten
Fehler nachweislich an.

## Git

Repo `vadimitri/claude`, Branch `main`. **Keine Worktrees für Medienprojekte** (Fotos, Audio, Cache, Druck, Resolve-Medien
sind gitignored und fehlen dort; Vadim 7.10.: „sieben Ordner tief“, er hat `.claude/worktrees/` einmal komplett gelöscht).
Erzwingt der Session-Wächter einen Worktree: eigener Branch, oft committen, vor dem Merge Vadim fragen, danach Worktree
entfernen. Nur eigene Pfade committen (`git commit -- <pfade>`), andere Sessions lassen oft Änderungen liegen.
Render-Ausgaben gitignored (reproduzierbar), Configs/Reports/kleine Referenzen nicht.

## Bekannte Schulden

- `src/styles.py` und `src/kickoff.py` haben Layout-Verhältnisse als nackte Zahlen; beim Anfassen benennen.
- Verlaufs-Bug (Band über Zeilengrenzen) in `styles.type_layers` und `kickoff.type_layers`; Lösung `kickoff_loop.line_gradient`.
- `songcut.py` ist IGOR-fest (Pfad, Marken), vor dem nächsten Song verallgemeinern; Beat-Raster-Skript fehlt (PLAYBOOK §3).
- `makernight_audio.main` muxt mit `loudnorm` statt fester Verstärkung.

## Offen (10.10.)

- Vadim: Adjustment Clip in `Wide 16x9` auf V5 hochziehen (`kit_resolve.lens_on` warnt). Backups `Spark_Design` +
  `Spark Deck` per Figma *File > Save local copy* nach `~/vault/Notes/03 Work/Spark/Assets/Figma/`.
- Zumo: Szenen/Maskottchen/Emoji abnehmen (Bogen `zumo_sprites/previz/scenes/sheet.png`); veröffentlicht sind sie schon
  (`Sporga/assets/motion/zumo/`, Sprites Z4 inkl. `value`-Sequenzen unter `zumo/sprites/Z4/`). Offen dort: Arena weiß mit
  schwarzem Rand laut Skill `zumo-2040` (Szene folgt der dunklen Demo), Simulator-Anbindung (Draufsicht-Sheets + `atlas.json`).
- Figma: Maskottchen-SVGs + Emoji in Spark_Design aufnehmen (Session spark-design-guide hat Start here umgebaut, war beendet).
- Spark Glow mit eigener Licht-Rampe (Kick-off: glimmend rot → weiß in OKLab) gibt es nur als „zweite Lens mit eigener
  Colorway“; eine echte Zweitpalette für Licht fehlt.
