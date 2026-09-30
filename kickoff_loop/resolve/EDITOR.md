# Stern-Editor in Resolve (Stand 30.9. abends)

Vadim keyt den Flug des Sterns in Resolve, Python liest die Bahn je Frame zurück und rendert die echten Plakate.
Code: `src/kickoff_loop_resolve.py`. Hilfsbilder und Renders liegen in `resolve/editor/` (nicht im Git, reproduzierbar).

## Was in Resolve steht

- Projekt **`SPARK_Kickoff_Loop`**, 1168 × 1652 (= Vorschau-Plakat, 1 px = 1 Plakatpixel), 24 fps.
- Timeline **`Stern-Bahn`**: ein Clip auf V1 (`layout.[0000-0479].png`, Bildsequenz aus Hardlinks auf `layout.png`),
  genau N = `[loop].frames` Frames. 1 Timeline-Frame = 1 Plakat-Frame (Timeline-Frame 0 = Frame 1).
  Marker „Aushang 01", „Aushang 03" … auf jedem Aushang (Timeline-Frames 0, 2, 4 …).
- Fusion-Comp des Clips: `MediaIn1` (Plakat ohne Stern) → Merge **`Stern`** (Vordergrund Loader `SternBild` = `star.png`)
  → Merge `Satz` (Vordergrund Loader `SatzBild` = `type_overlay.png`, Satz mit 60 % Deckkraft) → `MediaOut1`.
- Animiert sind nur am Merge **`Stern`**: `Center` (XY-Path, Kurven X/Y), `Size`, `Angle`. Startwerte = `KL.orbit`,
  Keyframes alle 4 Frames mit weichen Henkeln.

## So bearbeitet Vadim die Bahn

1. Fusion-Seite, Timeline `Stern-Bahn`, Knoten **`Stern`** anklicken (Viewer auf `MediaOut1`).
2. Im Viewer den Stern ziehen (Center), Size/Angle im Inspector oder an den Viewer-Griffen; an jedem Frame, an dem
   er etwas setzt, entsteht ein Keyframe. Kurven im Spline-Editor: `X`, `Y` (unter XYPath1), `Size`, `Angle`.
3. Nicht ändern: star.png/Loader, Knotennamen `Stern`, Timeline-Name. Clip länger ziehen geht bis 480 Frames: `pull`
   liefert dann entsprechend mehr Frames.
4. Danach `pull` → `kickoff_loop/star_path.json`, dann in `loop.toml` `[spark].source = "resolve"`.

Konventionen: `Center` 0..1 je Achse, y nach **oben** (unser y = 1 − Y); `Angle` gegen den Uhrzeigersinn (unser
rot = −Angle); `r` (Spitzenradius / Plakatbreite) = `Size` × 1024 / 1168.

## Befehle (aus dem Pack-Root)

| Befehl | Was | Stand |
|---|---|---|
| `uv run src/kickoff_loop_resolve.py assets` | `layout.png`, `type_overlay.png`, `star.png` | ✓ |
| `… push` | Projekt + Timeline bauen, Startbahn aus `KL.orbit` (N aus `[loop].frames`). Bricht ab, wenn `Stern-Bahn` schon existiert | ✓ |
| `… push --force` | Timeline neu = zurück auf `KL.orbit` (**Vadims Keys weg**). Nach Änderungen an `[spark]`/`[loop].frames` nötig | ✓ (30.9. mit height 0.33 gelaufen) |
| `… pull` | Bahn je Frame (N = Cliplänge) → `kickoff_loop/star_path.json` `{"frames", "source": "resolve", "path": [[x, y, r, rot] …]}` | ✓ |
| `… check` | Rundreise auf Wegwerf-Timeline `Stern-Bahn Test`: push → pull → gegen `KL.orbit`, Marker. Vadims Timeline bleibt unberührt | ✓ Lage 0.00052 Plakatbreite (Toleranz 0.005), Größe 0.086 % (1 %), Drehung 0.000° (1°), 24 Marker |
| `… verify [k …]` | Frames aus Resolve rendern (PNG), Stern-Silhouette gegen Python, IoU ≥ 0.95 | **✗ offen**, siehe unten |

## Geprüft (Resolve 21.1, 30.9.)

- Externes Python (uv, 3.11–3.13) verbindet über `DaVinciResolveScript` (Pfad `…/Developer/Scripting/Modules`).
- `ImportMedia([{"FilePath": …}])` für eine **Einzeldatei** liefert `None`; mit `%04d`-Muster + Start/EndIndex klappt es.
- Ein Standbild landet immer mit der Standard-Standbilddauer (120 Frames) in der Timeline, `endFrame` wird ignoriert →
  darum die Bildsequenz. Bei Sequenzen ist `endFrame` in `AppendToTimeline` **exklusiv** (0..47 ergab 47 Frames;
  `RECIPE.md` sagt inklusiv, das stimmt hier nicht).
- Comp-Zeit = Quellframe: `COMPN_RenderStart` = linker Rand des Clips, `COMPN_RenderEnd` inklusiv.
- `BezierSpline.SetKeyFrames`: im Python-API sind `LH`/`RH` **relativ** zum Key (`{1: dt, 2: dv}`), nicht absolut
  (`RECIPE.md` [A] falsch). Mit Henkeln bei 1/3 rechnet Fusion exakt eine kubische Hermite-Kurve (Abweichung 0.0).
- `tool.GetInput("Center", t)` liefert den ausgewerteten Wert je Frame, egal welcher Modifier dahinter hängt.
- `Timeline.AddMarker(frameId)`: frameId relativ zum Timeline-Start.

## Offen / nicht geprüft

1. **Bild-Prüfung scheitert**: Renders über die Render-Queue (`verify`) zeigen nur das Plakat, **ohne die Fusion-Comp**
   (auch ein Test mit einem weißen Background-Knoten statt Loader blieb unsichtbar: 0 % geänderte Pixel). Ob der Stern
   im Fusion-Viewer erscheint, ist ungesehen (kein Bildschirmzugriff). Also sind **y-Richtung, Drehsinn und
   Size-Maßstab nur gerechnet, nicht am Bild bestätigt**; `check` prüft nur die Rundreise (ein symmetrischer Fehler in
   to/from_fusion fiele dort nicht auf). Nächster Schritt: Vadim öffnet die Fusion-Seite und schaut, ob der weiße
   Stern bei Frame 0 links groß angeschnitten, bei Frame 24 klein in der Mitte, bei Frame 47 rechts steht. Dann
   Render-Weg klären (Render-Cache? Comp erst nach Öffnen in der Fusion-Seite aktiv? `ExportCurrentFrameAsStill`?)
   und `verify` laufen lassen.
2. Loader-Pfade zeigen in diesen Worktree (`.claude/worktrees/kickoff-loop/…`). Nach dem Merge in den Hauptcheckout
   `push --force` von dort (oder Pfade in den Loadern umhängen).
3. `[resolve]` fehlt noch in `loop.toml`; der Code nimmt bis dahin `RESOLVE_DEFAULT` (Werte siehe dort, alle Schlüssel
   können einzeln in die TOML).
4. Mehr Frames (z. B. 64): `[loop].frames` ändern, `push --force`. Die Sequenz reicht bis 480 (`clip_max_frames`).
