# Resolve 21.1 per Skript: Schnitt, Keyframes, Render

Stand 2026-09-30, Resolve Studio 21.1. **Nichts davon ist live getestet**: Resolve lief nicht und durfte nicht gestartet
werden (TRMNL-Schnitt). Grundlage sind die 21.1-Stubs (`DaVinciResolveScript.pyi`, `fusion_api.pyi`), `README.md` +
`CHANGELOG.md` unter `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/`, die
Blackmagic-Beispiele und -Templates dort sowie das Handbuch (`~/.claude/references/davinci-resolve-manual/`).

Kennzeichnung: **[S]** steht so in Stub/README/Changelog 21.1 · **[B]** belegt durch Blackmagic-Beispiel/Template/Handbuch ·
**[A]** Annahme, vor Gebrauch mit dem Selbsttest (unten) prüfen.

## Kurzbefund

| Frage | Antwort |
|---|---|
| Projekt/Timeline 1080x1920 @ 24 | ja, `SetSettings` mit String-Werten [S] |
| Clips an exakte Record-Frames/Spuren | ja, `AppendToTimeline([{...recordFrame, trackIndex, mediaType}])` [S] |
| Standbild genau 3 Frames | ja: `endFrame` ist **inklusiv** (`0..23` = 24 Frames, Blackmagic-Beispiel 7) [B]; bei Stills [A] |
| Inspector-Keyframes (Zoom/Position/Rotation) | **nein**: `SetProperties` setzt nur statische Werte, 21.1 hat keine Keyframe-API für TimelineItems [S] |
| Keyframes trotzdem | Fusion-Comp pro Clip (BezierSpline, Easing exakt steuerbar) [S+B], oder FCPXML-Import [B+A], oder in numpy backen |
| Speed Ramps / Retime-Kurven | nur konstant: `SetSpeed({"Percentage": ...})` (neu 21.1) [S]; Rampen nur über FCPXML/Fusion/Backen |
| Dynamic Zoom | nur an/aus + Ease [S]; Start-/End-Rahmen nicht setzbar [S] |
| Marker auf Beats | `Timeline.AddMarker(frameId:int, ...)`: ganze Frames, keine Subframes per API [S] |
| Render H.264/H.265/ProRes | ja: `SetCurrentRenderFormatAndCodec` + `SetRenderSettings` + `AddRenderJob` + `StartRendering` [S+B] |

## 0. Verbinden (Sicherheitsriegel zuerst)

Einstellung: Preferences > System > General > External scripting = Local. 21.1 bringt ein eigenes Python 3.14 mit, das
`DaVinciResolveScript` ohne Umgebungsvariablen importiert [S]:
`"/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython" skript.py`.
Mit `uv run` stattdessen `RESOLVE_SCRIPT_API`, `RESOLVE_SCRIPT_LIB`, `PYTHONPATH` setzen (README, Abschnitt External Interpreters).

```python
import DaVinciResolveScript as dvr
resolve = dvr.scriptapp("Resolve")
pm = resolve.GetProjectManager()
NAME = "SPARK_kickoff_loop"
cur = pm.GetCurrentProject()
# CreateProject/LoadProject schliessen das offene Projekt -> nie, waehrend der TRMNL-Schnitt offen ist.
if cur and cur.GetName() not in (NAME, "Untitled Project"):
    raise SystemExit(f"Anderes Projekt offen ({cur.GetName()}), Abbruch.")
```

## 1. Projekt + Timeline 1080x1920, 24 fps

```python
proj = pm.LoadProject(NAME) or pm.CreateProject(NAME)        # CreateProject -> None, wenn Name existiert [S]
ok = proj.SetSettings({                                       # Werte als Strings; False + Fehlerliste bei Problemen [S]
    "timelineFrameRate": "24",                                # vor dem ersten Timeline/Import setzen [A: danach gesperrt]
    "timelineResolutionWidth": "1080",
    "timelineResolutionHeight": "1920",
    "timelinePixelAspectRatio": "square",
    "timelineOutputResMatchTimelineRes": "1",
    "timelineInputResMismatchBehavior": "scaleToFit",
    "timelineSampleRate": "48000",
})
assert ok, "SetSettings fehlgeschlagen"
mp = proj.GetMediaPool()
tl = mp.CreateEmptyTimeline("loop_v003")
proj.SetCurrentTimeline(tl)
tl.SetStartTimecode("00:00:00:00")      # dann gilt recordFrame == Frame ab Timeline-Anfang
# Alternativ pro Timeline: tl.SetSettings({"useCustomSettings": "1", "timelineResolutionWidth": "1080", ...})
# (andere Keys greifen nur mit useCustomSettings = "1") [S]
```

## 2. Import + Platzieren

```python
imp = lambda d: mp.ImportMedia([d])[0]          # Dict-Form; Listen-von-Pfaden-Form ist deprecated [S]
seq   = imp({"FilePath": "/abs/frames/f_%04d.png", "StartIndex": 0, "EndIndex": 31})   # PNG-Sequenz = 1 Clip [S]
still = imp({"FilePath": "/abs/posters/plakat_a.png"})   # Name ohne Ziffern am Ende, sonst ggf. als Sequenz gruppiert [A]
ovl   = imp({"FilePath": "/abs/overlay_4444.mov"})
ovl.SetClipProperty("Alpha mode", "Straight")   # 'None' | 'Straight' | 'Premultiplied' [S]; passend zum Encoder waehlen
wav   = imp({"FilePath": "/abs/igor.wav"})

tl.AddTrack("video")                 # -> V2
tl.AddTrack("audio", "stereo")       # -> A2
t0 = tl.GetStartFrame()

def put(mpi, src_in, n, rec, track, media_type=1):
    """n Frames ab Quellframe src_in auf Spur track bei Record-Frame rec (relativ zum Timeline-Start).
    endFrame ist inklusiv [B], mediaType 1 = nur Video, 2 = nur Audio [S]; startFrame/recordFrame sind float [S]."""
    it = mp.AppendToTimeline([{"mediaPoolItem": mpi, "startFrame": src_in, "endFrame": src_in + n - 1,
                               "recordFrame": t0 + rec, "trackIndex": track, "mediaType": media_type}])[0]
    assert (it.GetStart(), it.GetDuration()) == (t0 + rec, n), (it.GetStart(), it.GetDuration())   # Befund statt Annahme
    return it

put(still, 0, 3, rec=0, track=1)        # Standbild genau 3 Frames (Still-Laenge = Pref "Standard still duration")
put(seq, 0, 32, rec=3, track=1)
put(ovl, 0, 48, rec=0, track=2)
```

Einfacher Überblendeffekt ohne Keyframes, neu in 21.1 [S]: `it.SetFades({"FadeIn": 6, "FadeOut": 6})`,
`it.AddTransition({"type": "Cross Dissolve", "category": "simple", "position": "end", "alignment": "center", "duration": 6})`,
Stop-Motion ohne Blending: `it.SetProperties({"RetimeProcess": resolve.RETIME_NEAREST})`.

## 3. Audio mit Quell-Versatz + Beat-Marker

```python
FPS = 24
put(wav, src_in=1.25 * FPS, n=int(12.0 * FPS), rec=0, track=1, media_type=2)   # WAV ab 1.25 s, 12 s lang
# Audio-trackIndex zaehlt Audiospuren (Bug dazu gefixt in 20.2.2) [S]. Samplegenau: WAV vorher mit ffmpeg schneiden.
# Project.InsertAudioToCurrentTrackAtPlayhead(path, startOffsetInSamples, durationInSamples) existiert [S],
# braucht aber Playhead + "aktuelle Spur", die sich per API nicht waehlen laesst -> fuer Batch ungeeignet.

for i, t in enumerate(beats_s):
    tl.AddMarker(round(t * FPS), "Sky", f"beat {i}", "", 1, f"beat:{i}")
    # (frameId:int, color, name, note, duration, customData) [S]; frameId relativ zum Timeline-Start [A]
assert len(tl.GetMarkers()) == len(beats_s)
```

## 4. Keyframes

**Befund [S]:** `TimelineItemProperties` kennt `Pan, Tilt, ZoomX, ZoomY, ZoomGang, RotationAngle, AnchorPointX/Y, Pitch,
Yaw, FlipX/Y, Crop*, Opacity, CompositeMode, DynamicZoomEnabled, DynamicZoomEase, RetimeProcess, ...`, alle statisch.
`SetProperties` hat keinen Zeitparameter; kein TimelineItem-Aufruf setzt Keyframes, auch nicht in 21.1 (CHANGELOG).
Die 21er Keyframe-Neuheiten (4-Punkt-Bezier-Retime, Loop/Ping-Pong, Subframes) sind nur in der Oberfläche.

### Weg A: Fusion-Comp pro Clip (empfohlen, wenn in Resolve animiert werden soll)

Signaturen [S]: `TimelineItem.AddFusionComp()`, `GetFusionCompByIndex(i)`, `Composition.AddTool/FindTool/Lock/Unlock`,
`Operator.ConnectInput/AddModifier/SetInput(id, value, time)`, `Link.GetConnectedOutput/GetTool`,
`BezierSpline.SetKeyFrames(dict, replace)/GetKeyFrames()`.
Keyframe-Format [B] (`Developer/Fusion Templates/Generators/Gradient.setting`):
`[0] = { 0.63, RH = { 39.67, 0.3667 } }, [119] = { -0.16, LH = { 79.33, 0.1033 } }`. Die Henkel sind **absolute**
(Frame, Wert)-Punkte; Standard = je 1/3 des Segments. Eine Fusion-Kurve ist damit genau ein kubischer Bezier in (t, v),
also dasselbe wie CSS `cubic-bezier(x1, y1, x2, y2)` → Easing lässt sich exakt aus der TOML übernehmen.
Nachgerechnet: `ease_keys` mit `bez=(1/3, 1/3, 2/3, 2/3)` ergibt für das Template-Segment genau dessen Henkel.
Zeitbasis [B] (Handbuch 065): Global Range der Comp = ganze Quelldauer, Render Range = sichtbares In..Out des Clips.
Also relativ zu `COMPN_RenderStart` keyen.

```python
def spline_of(tool, inp):
    """BezierSpline hinter einem Input; legt ihn an, falls der Input noch nicht animiert ist."""
    out = getattr(tool, inp).GetConnectedOutput()
    if out is None:
        tool.AddModifier(inp, "BezierSpline")
        out = getattr(tool, inp).GetConnectedOutput()
    return out.GetTool()

def ease_keys(spline, keys, bez=(0.42, 0.0, 0.58, 1.0)):
    """keys = [(frame, wert), ...]; bez = CSS-cubic-bezier je Segment (x = Zeitanteil, y = Wertanteil).
    Python-Form der Lua-Tabelle: {frame: {1: wert, 'RH': {1: t, 2: v}, 'LH': {...}}} [A: mit GetKeyFrames() gegenpruefen]."""
    x1, y1, x2, y2 = bez
    kf = {}
    for (ta, va), (tb, vb) in zip(keys, keys[1:]):
        dt, dv = tb - ta, vb - va
        kf.setdefault(ta, {1: va})["RH"] = {1: ta + x1 * dt, 2: va + y1 * dv}
        kf.setdefault(tb, {1: vb})["LH"] = {1: ta + x2 * dt, 2: va + y2 * dv}
    spline.SetKeyFrames(kf, True)        # replace=True
    # Linear: {"Flags": {"Linear": True}} [B]; Halten (Stop-Motion): {"Flags": {"StepIn": True}} [A]

it = put(still, 0, 24, rec=35, track=1)
comp = it.AddFusionComp()                        # neue Comp: MediaIn1 -> MediaOut1 [A: Standardnamen]
comp.Lock()
mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
xf = comp.AddTool("Transform")
xf.ConnectInput("Input", mi)
mo.ConnectInput("Input", xf)
s0 = comp.GetAttrs()["COMPN_RenderStart"]        # [A: Attributname aus Fusion-Scripting-Guide, nicht im Stub]
ease_keys(spline_of(xf, "Size"),  [(s0, 1.0), (s0 + 12, 1.35), (s0 + 23, 1.0)])      # Size 1.0 = 100 %
ease_keys(spline_of(xf, "Angle"), [(s0, 0.0), (s0 + 23, 8.0)], bez=(0, 0, 1, 1))     # Grad, gegen Uhrzeigersinn
xf.AddModifier("Center", "XYPath")               # Punkt-Input: X/Y als eigene Kurven, 0..1 normiert, 0.5 = Mitte
xy = xf.Center.GetConnectedOutput().GetTool()
ease_keys(spline_of(xy, "X"), [(s0, 0.5), (s0 + 23, 0.55)])
ease_keys(spline_of(xy, "Y"), [(s0, 0.5), (s0 + 23, 0.45)])
comp.Unlock()
print(spline_of(xf, "Size").GetKeyFrames())      # Befund: Form + Henkel wie geschrieben?
# Pixelraster (end_cell_px): Filter des Transform auf Nearest stellen, Input-ID via xf.GetInputList() suchen [A]
# Wiederverwenden: it.ExportFusionComp(pfad, 1) / anderes_item.ImportFusionComp(pfad) [S]
```

Speed Ramp in Fusion: Tool `TimeStretcher` (Input `SourceTime`) mit `ease_keys` animieren [A].

### Weg B: FCPXML erzeugen und importieren (native Inspector-Keyframes)

Handbuch [B] (024, "About Supported Opacity, Position, Scale, and Rotation Settings"): XML-Import aus FCP X übernimmt
Opacity/Position/Scale/Rotation **inklusive Keyframes** in den Edit-Inspector, Ken Burns → Dynamic Zoom, variable
Geschwindigkeit inklusive Bezier-Übergängen (FCPX `timeMap`). 21 kann FCPXML bis FCP 12 [S whats_new].
API: `mp.ImportTimelineFromFile("/abs/loop.fcpxml", {"timelineName": "loop_xml", "importSourceClips": True})` [S].
Offen [A]: Im Dialog braucht das die Option "Use sizing information"; `ImportOptions` für XML hat dafür **keinen** Key
(nur AAF hat `useSizingInfo`) [S]. Ob der API-Import Transforms übernimmt, ist ungeprüft. Einheiten der FCPXML-Position
und die Übersetzung von `interp="ease"` ebenfalls [A].

### Weg C: in numpy backen

Der Pack rendert Zoom/Drehung schon selbst, pixelgenau (`end_cell_px`). Resolve nur zum Zusammensetzen, für Audio und den
Render nutzen. Das ist der einzige Weg, der das Pixelraster garantiert und ohne Annahmen auskommt.

### Dynamic Zoom / Retime

```python
it.SetProperties({"DynamicZoomEnabled": True, "DynamicZoomEase": resolve.DYNAMIC_ZOOM_EASE_IN_AND_OUT})  # [S]
# Start-/End-Rechteck: kein Key -> nur Standardbewegung [S: fehlt]
it.SetSpeed({"Percentage": 50.0, "PitchCorrection": False, "RippleTimeline": False})  # konstant, 0.0 = Standbild [S, neu 21.1]
```

## 5. Render

```python
proj.SetCurrentTimeline(tl)
proj.SetCurrentRenderMode(1)                       # 1 = Single clip [S]
print(proj.GetRenderFormats())                     # {Name: Endung}; format-Argument = Endung ("mov", "mp4") [B]
print(proj.GetRenderCodecs("mp4"))                 # {Beschreibung: Codec-Name}; die Werte uebergeben [S]

def render(fmt, codec, name, **extra):
    assert proj.SetCurrentRenderFormatAndCodec(fmt, codec), (fmt, codec)
    assert proj.SetRenderSettings({
        "SelectAllFrames": True, "TargetDir": "/abs/kickoff_loop/resolve/out", "CustomName": name,
        "FormatWidth": 1080, "FormatHeight": 1920, "FrameRate": 24.0,
        "ExportVideo": True, "ExportAudio": True, "AudioCodec": "aac", "AudioSampleRate": 48000, **extra})
    job = proj.AddRenderJob()
    proj.StartRendering([job])                     # Job-IDs, keine Indizes [S]
    return job

job = render("mp4", "H264", "loop_v003_h264", VideoQuality="Best")          # 0 = auto, int = Bitrate, oder 'Least'..'Best' [S]
# render("mp4", "H265", "loop_v003_h265", EncodingProfile="Main10")        [S]
# render("mov", "ProRes422HQ", "loop_v003_pr")                              Codec-Name belegt [B, Beispiel 3]
# render("mov", "ProRes4444", "loop_v003_alpha", ExportAlpha=True, AlphaMode=1, ExportAudio=False)  # 1 = Straight [S]; Name [A]
import time
while proj.IsRenderingInProgress():
    time.sleep(1)
print(proj.GetRenderJobStatus(job))                # JobStatus 'Complete' | 'Failed' (+ Error) ... [S]
```

Codec-Strings `H264`/`H265`/`ProRes4444` sind [A]; die gültigen Namen liefert `GetRenderCodecs`.
21.0.4 hat `UseFullExtents`, `AddFrameHandles`, `DataBurnIn` in `SetRenderSettings` ergänzt [S].

## 6. Was 21.x dafür bringt

- **21.1 API** [S CHANGELOG]: `TimelineItem.SetSpeed/GetSpeed`, `SetFades/GetFades`, `AddTransition`, `GetType`,
  mehr Audio-Properties in `SetProperties`, eingebautes Python 3.14 (`ResolvePython`), `resolve.GetCurrentProject()` usw.,
  Render-/Projekteinstellungs-Presets per API. **Keine** Keyframe-API.
- **21.0**: Keyframing mit 4-Punkt-Bezier-Retime, Ease-Optionen, Loop/Ping-Pong, Subframe-Keyframes/Marker. Nur in der
  Oberfläche; per API liefern `GetStart(True)`/`GetDuration(True)` Subframes [S], `AddMarker` nimmt nur `int`.
- **21.0**: Lottie (`.lottie`) und OGraf (`.json`) als Medien mit Alpha (Handbuch 019) [B]. Denkbar: prozedural erzeugtes
  Lottie mit Bezier-Keyframes importieren. Ob `ImportMedia` das annimmt und wie scharf es rendert: [A].
- **21.0**: Fusion-Animation von Fairlight-Audio treiben (nur Oberfläche). KI-APIs (Speech, IntelliSearch, Slate, Deblur,
  Audio-Klassifizierung) gibt es, sind nach Pack-Regel (keine KI-Dienste) aber tabu.
- Headless: `Resolve -nogui`, Scripting läuft weiter [S]. Es läuft aber nur eine Resolve-Instanz, also nicht parallel zum
  TRMNL-Schnitt.

## Selbsttest (einmal ausführen, wenn Resolve frei ist, in einem Wegwerf-Projekt)

Klärt alle [A]-Punkte an echten Rückgabewerten:
1. `put(still, 0, 3, ...)` → Assert `GetDuration() == 3` (Still + inklusives `endFrame`).
2. `tl.AddMarker(0, ...)` → `tl.GetMarkers()` hat Schlüssel `0` (frameId relativ zum Start).
3. `ease_keys` → `GetKeyFrames()` gibt dieselben Henkel zurück; ein Frame-Export per `proj.ExportCurrentFrameAsStill`
   bei s0 und s0+12 zeigt den Zoom.
4. `comp.GetAttrs()["COMPN_RenderStart"]` existiert, Werkzeugnamen `MediaIn1`/`MediaOut1` stimmen.
5. `GetRenderCodecs("mov")`/`("mp4")` ausgeben und die Codec-Namen hier eintragen.
6. FCPXML mit einem Scale-Keyframe importieren → `it.GetProperties()["ZoomX"]` und Inspector prüfen.
