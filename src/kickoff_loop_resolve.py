#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""Stern-Bahn-Editor in DaVinci Resolve: Vadim keyt den Flug des Sterns im Fusion-Tab, Python liest ihn zurueck.

Warum: Die Bahn ist Animation, und die animiert Vadim am liebsten selbst, mit Keyframes, in Resolve. Resolve zeigt dafuer
nur eine Hilfe (Plakat ohne Stern, weisser Stern, Satz halbtransparent darueber). Die echten Plakate (Palette, Dither,
Satz, QR) rendert weiter Python, aus der Bahn, die `pull` aus Resolve holt: je Frame (x, y, r, rot) wie `KL.orbit`.

  uv run src/kickoff_loop_resolve.py assets        Hilfsbilder → kickoff_loop/resolve/editor/ (layout, type_overlay, star)
  uv run src/kickoff_loop_resolve.py push          Projekt + Timeline "Stern-Bahn" bauen, Startbahn = KL.orbit
  uv run src/kickoff_loop_resolve.py push --force  bestehende Timeline neu bauen = auf KL.orbit zuruecksetzen (Keys weg!)
  uv run src/kickoff_loop_resolve.py pull          Bahn je Frame aus Resolve → kickoff_loop/star_path.json
  uv run src/kickoff_loop_resolve.py check         Selbsttest: push + pull auf Wegwerf-Timeline, Vergleich mit KL.orbit
  uv run src/kickoff_loop_resolve.py verify [k …]  Timeline-Frames k (ab 0) aus Resolve rendern, Stern-Silhouette gegen
                                                   Python (IoU) → kickoff_loop/resolve/editor/verify/

Konventionen (Resolve 21.1; Rundreise mit `check` gemessen, Bild-Pruefung `verify` noch offen, siehe EDITOR.md):
  unsere Bahn   x, y = Bruchteil von Plakatbreite/-hoehe, y nach unten; r = Spitzenradius / Plakatbreite;
                rot = Grad im Uhrzeigersinn (Bildkoordinaten, wie styles.star_r)
  Fusion Merge  Center = 0..1 je Achse, y nach OBEN; Angle = Grad GEGEN den Uhrzeigersinn;
  "Stern"       Size = Massstab von star.png in dessen Pixeln → r = Size * star_png_radius_px / Plakatbreite
  Zeit          Timeline-Frame k (ab Clipanfang, 0 …) = Comp-Zeit COMPN_RenderStart + k = Plakat-Frame k + 1

Resolve-Zugriff: externes Python (uv) mit DaVinciResolveScript; Resolve muss laufen, Preferences > System > General >
External scripting = Local. Bedienung, gepruefte API-Punkte, offene Punkte: kickoff_loop/resolve/EDITOR.md.
"""
import glob
import json
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kickoff as K                      # noqa: E402
import kickoff_loop as KL                # noqa: E402
import styles as S                       # noqa: E402

OUT = os.path.join(KL.PROJECT, "resolve", "editor")
ASSETS = {k: os.path.join(OUT, f"{k}.png") for k in ("layout", "type_overlay", "star")}
SEQ = os.path.join(OUT, "layout_seq")    # layout.png als Bildsequenz (Hardlinks): ein Standbild nimmt in Resolve immer
                                         # die Standard-Standbilddauer (5 s), eine Sequenz laesst sich framegenau setzen
VERIFY = os.path.join(OUT, "verify")

# Vorschlag fuer loop.toml [resolve]. Steht der Abschnitt dort, gilt er (Schluessel fuer Schluessel); bis dahin diese Werte.
RESOLVE_DEFAULT = dict(
    project="SPARK_Kickoff_Loop",   # Resolve-Projekt (nur fuer den Editor)
    timeline="Stern-Bahn",          # Timeline mit dem Editor-Clip; check baut daneben "<timeline> Test" und loescht sie
    fps=24,                         # Wiedergabe im Editor. 1 Timeline-Frame = 1 Plakat-Frame, fps ist nur Vorschau
    key_every=4,                    # Startkeyframes aus KL.orbit alle n Frames (weiche Kurven, gut zu bearbeiten).
                                    # Haelt die Kurve die Toleranzen nicht, nimmt push automatisch 2, dann 1
    clip_max_frames=480,            # so lang darf Vadim den Clip in Resolve ziehen (Laenge der Sequenz; Hardlinks)
    star_png_radius_px=1024,        # Spitzenradius in star.png. Groesser = schaerfer bei grossen Sternen
    overlay_alpha_frac=0.6,         # Deckkraft der Satz-Hilfe (Titel, Datum, JOIN US, QR mit Hof) ueber dem Stern
    path_file="star_path.json",     # Ausgabe von pull, relativ zu kickoff_loop/
    tol_pos_frac=0.005,             # check: Lage, Abweichung als Bruchteil der Plakatbreite (x und y)
    tol_size_frac=0.01,             # check: Groesse, relativ
    tol_rot_deg=1.0,                # check: Drehung
    iou_min=0.95,                   # verify: Stern-Silhouette Resolve vs. Python, Schnitt / Vereinigung
)

# Technische Konstanten
RESOLVE_MODULES = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"  # README 21.1
OFF_CANVAS_STAR = (-10.0, -10.0, 0.01)   # Stern (x, y, r) weit ausserhalb: Plakat ohne Stern und ohne sein Glimmen
                                         # (styles.background: Glimmen faellt mit exp(-Abstand / R), hier ~ e^-1000)
PLAIN_SPARK = "S2"                       # Stil fuer layout.png: zeichnet nur in der Silhouette (Labor-Sterne wie S19d
                                         # brauchen den Stern im Bild und brechen ab, wenn er draussen liegt)
STAR_PAD_PX = 8                          # Rand um den Stern in star.png (Antialiasing + Filter des Merge)
DERIV_STEP = 1e-3                        # Frames, zentrale Differenz fuer die Steigung von KL.orbit an den Keyframes
MARKER_COLOR = "Sky"                     # Timeline-Marker der Aushaenge
FLOW = dict(MediaIn1=(0, 1), Stern=(2, 1), SternBild=(2, -1), Satz=(3.5, 1), SatzBild=(3.5, -1), MediaOut1=(5, 1))
                                         # Knoten im Fusion-Flow (Rasterkoordinaten, Standard: MediaIn1 (0, 1), Out (5, 1))
DIFF_MIN = 0.06                          # verify: nur Pixel messen, wo ein weisser Stern das Bild um mehr als das aendert
                                         # (0..1, groesster Kanal); unter heller Schrift/QR-Hof ist Weiss nicht erkennbar
PNG_CODEC = ("png", "RGB8")              # verify: Resolve-Renderformat (GetRenderCodecs("png"), Befund 30.9.)
RENDER_TIMEOUT_S = 120


def load():
    """loop.toml + [resolve] (oder RESOLVE_DEFAULT) lesen und pruefen, bevor Resolve angefasst wird."""
    cfg = KL.load()
    rc = dict(RESOLVE_DEFAULT, **cfg.get("resolve", {}))
    bad = sorted(set(rc) - set(RESOLVE_DEFAULT))
    assert not bad, f"[resolve]: unbekannte Schluessel {bad}. Erlaubt: {sorted(RESOLVE_DEFAULT)}"
    assert int(rc["key_every"]) >= 1, "[resolve].key_every: mindestens 1 (Keyframe alle n Frames)"
    assert rc["clip_max_frames"] >= KL.count(cfg), "[resolve].clip_max_frames: mindestens [loop].frames"
    assert rc["star_png_radius_px"] >= 64, "[resolve].star_png_radius_px: zu klein fuer eine brauchbare Hilfe"
    assert 0 < rc["overlay_alpha_frac"] <= 1, "[resolve].overlay_alpha_frac: 0..1"
    assert 0 < rc["iou_min"] <= 1, "[resolve].iou_min: 0..1"
    cfg["resolve"] = rc
    return cfg


def poster_px():
    """Breite, Hoehe des Vorschau-Plakats (= Timeline) in Pixeln."""
    return S.SIZES[KL.PREVIEW][:2]


# ---------------------------------------------------------------- Hilfsbilder

def star_alpha(R, rot, w, h, cx, cy):
    """Antialiaste Sternmaske 0..1 in einem w x h-Bild: Mitte (cx, cy) in Pixelkanten-Koordinaten, Spitzenradius R px,
    Drehung rot (Grad, Uhrzeigersinn). Dieselbe Form wie im Plakat (styles.star_r), dort aber auf 4-px-Zellen."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
    return np.clip(S.star_r(dx, dy, rot) * R - np.hypot(dx, dy) + 0.5, 0, 1)


def assets(cfg):
    """layout.png (Frame 1 ohne Stern), type_overlay.png (nur der Satz, halbtransparent), star.png (weiss, rot = 0).
    Alle PNGs mit geradem (nicht vormultipliziertem) Alpha; der Loader in Fusion multipliziert selbst."""
    rc = cfg["resolve"]
    W, H = poster_px()
    st = KL.poster_style(cfg, 0)
    st["star"], st["S"] = OFF_CANVAS_STAR, KL.S_CODES[PLAIN_SPARK]
    layout = K.frame_of(dict(st), KL.PREVIEW)
    _, layers = S.render(dict(st), KL.PREVIEW)
    rgba = np.zeros((H, W, 4), np.float32)
    for name, lay in layers.items():                        # alles ausser Grund und Stern = Satz (Titel, Datum, QR, CTA)
        if name in ("bg", "spark"):
            continue
        a = lay[..., 3:] / 255.0
        rgba[..., :3] += a * (lay[..., :3] - rgba[..., :3])
        rgba[..., 3:] = np.maximum(rgba[..., 3:], a)
    rgba[..., 3] *= rc["overlay_alpha_frac"] * 255
    R = rc["star_png_radius_px"]
    side = 2 * (R + STAR_PAD_PX)
    star = np.dstack([np.full((side, side, 3), 255.0), 255 * star_alpha(R, 0.0, side, side, side / 2, side / 2)])
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(layout).save(ASSETS["layout"])
    Image.fromarray(np.round(rgba).astype(np.uint8), "RGBA").save(ASSETS["type_overlay"])
    Image.fromarray(np.round(star).astype(np.uint8), "RGBA").save(ASSETS["star"])
    return f"{W}x{H} layout + type_overlay, star {side}x{side} (Spitzenradius {R} px) → {OUT}"


def layout_sequence(cfg):
    """layout.png als Sequenz layout.0000.png … (Hardlinks, kein Platz). Printf-Muster fuer ImportMedia."""
    if not all(os.path.exists(p) for p in ASSETS.values()):
        print(assets(cfg))
    n = cfg["resolve"]["clip_max_frames"]
    os.makedirs(SEQ, exist_ok=True)
    for i in range(n):
        p = os.path.join(SEQ, f"layout.{i:04d}.png")
        if not (os.path.exists(p) and os.path.samefile(p, ASSETS["layout"])):
            if os.path.exists(p):
                os.remove(p)
            os.link(ASSETS["layout"], p)
    return os.path.join(SEQ, "layout.%04d.png"), n


# ---------------------------------------------------------------- Bahn ⇄ Fusion

def to_fusion(p, W, R_png):
    """(x, y, r, rot) unserer Bahn → Kanaele des Merge "Stern": Center X/Y (y nach oben), Size, Angle (gegen Uhrzeiger)."""
    x, y, r, rot = p
    return dict(X=x, Y=1 - y, Size=r * W / R_png, Angle=-rot)


def from_fusion(center, size, angle, W, R_png):
    """Umkehrung von to_fusion. center = Fusion-Punkt {1: x, 2: y, 3: z}."""
    return [center[1], 1 - center[2], size * R_png / W, -angle]


def key_times(n, every):
    """Keyframe-Zeiten (Frames ab 0): alle `every` Frames plus der letzte Frame, damit die Kurve den Clip abdeckt."""
    t = list(range(0, n, every))
    return t + [n - 1] if t[-1] != n - 1 else t


def orbit_keys(cfg, every):
    """{Kanal: (Zeiten, Werte, Steigungen)} aus KL.orbit. Steigung = Ableitung der Bahn an der Keyframe-Zeit: mit
    Henkeln bei 1/3 des Segments ergibt das in Fusion eine kubische Hermite-Kurve, die der Bahn eng folgt."""
    rc, W = cfg["resolve"], poster_px()[0]
    f = lambda t: to_fusion(KL.orbit(cfg, t), W, rc["star_png_radius_px"])        # noqa: E731
    ts = key_times(KL.count(cfg), every)
    out = {}
    for ch in ("X", "Y", "Size", "Angle"):
        v = [f(t)[ch] for t in ts]
        m = [(f(t + DERIV_STEP)[ch] - f(t - DERIV_STEP)[ch]) / (2 * DERIV_STEP) for t in ts]
        out[ch] = (ts, v, m)
    return out


def hermite(keys, t):
    """Wert der Fusion-Kurve (Bezier mit Henkeln bei 1/3, = kubische Hermite) bei Zeit t. Befund 30.9.: Resolve rechnet
    genau so (Abweichung 0.0 an einer Parabel)."""
    ts, v, m = keys
    j = min(np.searchsorted(ts, t, side="right") - 1, len(ts) - 2)
    h = ts[j + 1] - ts[j]
    s = (t - ts[j]) / h
    return ((2 * s**3 - 3 * s**2 + 1) * v[j] + (s**3 - 2 * s**2 + s) * h * m[j]
            + (-2 * s**3 + 3 * s**2) * v[j + 1] + (s**3 - s**2) * h * m[j + 1])


def path_error(cfg, path):
    """Groesste Abweichung einer Bahn [[x, y, r, rot], …] von KL.orbit: Lage (Bruchteil der Plakatbreite), Groesse
    (relativ), Drehung (Grad). y zaehlt in Plakatbreiten, damit beide Achsen dieselbe Toleranz in Pixeln haben."""
    W, H = poster_px()
    ref = np.array([KL.orbit(cfg, i) for i in range(len(path))])
    p = np.array(path)
    pos = np.maximum(np.abs(p[:, 0] - ref[:, 0]), np.abs(p[:, 1] - ref[:, 1]) * H / W)
    return dict(pos=float(pos.max()), size=float(np.max(np.abs(p[:, 2] / ref[:, 2] - 1))),
                rot=float(np.max(np.abs(p[:, 3] - ref[:, 3]))))


def within(cfg, err):
    rc = cfg["resolve"]
    return err["pos"] <= rc["tol_pos_frac"] and err["size"] <= rc["tol_size_frac"] and err["rot"] <= rc["tol_rot_deg"]


def fmt_err(err):
    return f"Lage {err['pos']:.5f} Plakatbreite, Groesse {100 * err['size']:.3f} %, Drehung {err['rot']:.3f}°"


def choose_keys(cfg):
    """Groesster Keyframe-Abstand (key_every, sonst 2, sonst 1), dessen Kurve KL.orbit innerhalb der Toleranz trifft.
    Geprueft an der vorhergesagten Kurve (hermite); check misst danach, was Resolve wirklich liefert."""
    rc, W = cfg["resolve"], poster_px()[0]
    n = KL.count(cfg)
    for every in sorted({int(rc["key_every"]), 2, 1}, reverse=True):
        if every > rc["key_every"]:
            continue
        keys = orbit_keys(cfg, every)
        path = [from_fusion({1: hermite(keys["X"], t), 2: hermite(keys["Y"], t)}, hermite(keys["Size"], t),
                            hermite(keys["Angle"], t), W, rc["star_png_radius_px"]) for t in range(n)]
        err = path_error(cfg, path)
        if within(cfg, err) or every == 1:
            return every, keys, err


# ---------------------------------------------------------------- Resolve

def connect():
    sys.path.append(RESOLVE_MODULES)
    import DaVinciResolveScript as dvr
    r = dvr.scriptapp("Resolve")
    if r is None:
        sys.exit("Resolve laeuft nicht oder External scripting ist aus (Preferences > System > General > Local)")
    return r


def open_project(r, cfg, create=False):
    """Editor-Projekt laden (oder anlegen). Ein anderes offenes Projekt wird vorher gespeichert, sonst Abbruch;
    ein leeres "Untitled Project" (Resolve-Start) wird einfach verlassen."""
    rc = cfg["resolve"]
    pm = r.GetProjectManager()
    cur = pm.GetCurrentProject()
    if cur and cur.GetName() == rc["project"]:
        return cur
    if cur and not (cur.GetName().startswith("Untitled Project") and cur.GetTimelineCount() == 0):
        assert pm.SaveProject(), f"offenes Projekt '{cur.GetName()}' liess sich nicht speichern, Abbruch"
    pm.GotoRootFolder()
    proj = pm.LoadProject(rc["project"])
    if proj is None:
        assert create, f"Resolve-Projekt '{rc['project']}' fehlt, erst: push"
        proj = pm.CreateProject(rc["project"])
        assert proj, f"Resolve-Projekt '{rc['project']}' liess sich nicht anlegen"
    return proj


def project_settings(proj, cfg):
    """Timeline = Plakat in Vorschaugroesse (1 Pixel = 1 Plakatpixel), fps laut [resolve]."""
    W, H = poster_px()
    want = {"timelineResolutionWidth": str(W), "timelineResolutionHeight": str(H),
            "timelinePixelAspectRatio": "square", "timelineFrameRate": str(cfg["resolve"]["fps"])}
    for k, v in want.items():
        if str(proj.GetSetting(k)).split(".")[0] != v:
            proj.SetSetting(k, v)                     # Bildrate ist gesperrt, sobald es eine Timeline gibt
    got = {k: str(proj.GetSetting(k)).split(".")[0] for k in want}
    assert got == want, f"Projekteinstellungen: will {want}, Resolve hat {got}"


def layout_clip(proj, cfg):
    """Media-Pool-Clip der Layout-Sequenz (wiederverwendet, sonst importiert)."""
    mp = proj.GetMediaPool()
    pattern, n = layout_sequence(cfg)
    for c in mp.GetRootFolder().GetClipList() or []:
        if os.path.dirname(c.GetClipProperty("File Path")) == SEQ and int(c.GetClipProperty("Frames")) == n:
            return c
    mp.SetCurrentFolder(mp.GetRootFolder())
    got = mp.ImportMedia([{"FilePath": pattern, "StartIndex": 0, "EndIndex": n - 1}])
    assert got, f"Resolve importiert {pattern} nicht"
    return got[0]


def timeline_by_name(proj, name):
    for i in range(1, proj.GetTimelineCount() + 1):
        tl = proj.GetTimelineByIndex(i)
        if tl.GetName() == name:
            return tl
    return None


def loader(comp, path, name):
    t = comp.AddTool("Loader", *FLOW[name])
    t.SetAttrs({"TOOLS_Name": name})
    t.SetInput("Clip", path)
    t.SetInput("Loop", 1)                             # Standbild auf jedem Frame der Comp
    t.SetInput("PostMultiplyByAlpha", 1)              # PNG hat gerades Alpha, Fusion rechnet vormultipliziert
    return t


def spline(tool, inp):
    """BezierSpline hinter einem Input (legt ihn an)."""
    assert tool.AddModifier(inp, "BezierSpline"), f"{tool.Name}.{inp}: keine Animation moeglich"
    return getattr(tool, inp).GetConnectedOutput().GetTool()


def set_curve(sp, keys, t0):
    """Keyframes mit Henkeln bei 1/3 des Nachbarsegments. Befund 30.9.: im Python-API sind LH/RH RELATIV zum Key
    ({1: dt, 2: dv}), nicht absolut wie in .setting-Dateien."""
    ts, v, m = keys
    kf = {}
    for i, t in enumerate(ts):
        e = {1: float(v[i])}
        if i > 0:
            d = (t - ts[i - 1]) / 3
            e["LH"] = {1: -d, 2: -float(m[i]) * d}
        if i < len(ts) - 1:
            d = (ts[i + 1] - t) / 3
            e["RH"] = {1: d, 2: float(m[i]) * d}
        kf[float(t0 + t)] = e
    sp.SetKeyFrames(kf, True)


def build(proj, cfg, name, keys):
    """Timeline `name`: ein Clip (Layout-Sequenz, genau N Frames), Fusion-Comp
    MediaIn1 → Merge "Stern" (Vordergrund star.png, animiert) → Merge "Satz" (type_overlay.png) → MediaOut1,
    Marker auf jedem Aushang. Gibt die Timeline zurueck."""
    n = KL.count(cfg)
    mp = proj.GetMediaPool()
    clip = layout_clip(proj, cfg)
    tl = mp.CreateEmptyTimeline(name)
    assert tl, f"Timeline '{name}' liess sich nicht anlegen"
    proj.SetCurrentTimeline(tl)
    t0 = tl.GetStartFrame()
    # endFrame ist hier EXKLUSIV (Befund 30.9.: 0..47 ergab 47 Frames)
    it = mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": 0, "endFrame": n, "recordFrame": t0,
                               "trackIndex": 1, "mediaType": 1}])[0]
    assert it.GetDuration() == n, f"Clip hat {it.GetDuration()} statt {n} Frames"
    comp = it.AddFusionComp()
    ct0 = comp.GetAttrs()["COMPN_RenderStart"]
    comp.Lock()
    mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
    star, over = loader(comp, ASSETS["star"], "SternBild"), loader(comp, ASSETS["type_overlay"], "SatzBild")
    mg = comp.AddTool("Merge", *FLOW["Stern"])
    mg.SetAttrs({"TOOLS_Name": "Stern"})
    sa = comp.AddTool("Merge", *FLOW["Satz"])
    sa.SetAttrs({"TOOLS_Name": "Satz"})
    assert mg.ConnectInput("Background", mi) and mg.ConnectInput("Foreground", star)
    assert sa.ConnectInput("Background", mg) and sa.ConnectInput("Foreground", over) and mo.ConnectInput("Input", sa)
    assert mg.AddModifier("Center", "XYPath"), "Stern.Center: XYPath fehlt"
    xy = mg.Center.GetConnectedOutput().GetTool()
    for tool, inp, ch in ((xy, "X", "X"), (xy, "Y", "Y"), (mg, "Size", "Size"), (mg, "Angle", "Angle")):
        set_curve(spline(tool, inp), keys[ch], ct0)
    comp.Unlock()
    for i in range(n):
        if KL.is_key(cfg, i):
            tl.AddMarker(i, MARKER_COLOR, f"Aushang {i + 1:02d}", "Plakat-Frame, haengt auf dem Campus", 1, f"frame:{i + 1}")
    return tl


def editor_clip(tl):
    """(TimelineItem, Comp, Merge "Stern") des Editor-Clips auf V1."""
    for it in tl.GetItemListInTrack("video", 1) or []:
        for j in range(1, it.GetFusionCompCount() + 1):
            comp = it.GetFusionCompByIndex(j)
            mg = comp.FindTool("Stern")
            if mg:
                return it, comp, mg
    sys.exit(f"Timeline '{tl.GetName()}': kein Clip mit Fusion-Knoten 'Stern' auf V1")


def read_path(cfg, tl):
    """Bahn je Timeline-Frame aus dem Merge "Stern" (ausgewertet, egal ob XYPath, Path oder Ausdruck dahinter).
    N = Laenge des Clips auf der Timeline."""
    rc, W = cfg["resolve"], poster_px()[0]
    it, comp, mg = editor_clip(tl)
    n = int(it.GetDuration())
    a = comp.GetAttrs()
    t0 = a["COMPN_RenderStart"]
    if a["COMPN_RenderEnd"] - t0 + 1 != n:
        print(f"  Hinweis: Comp-Bereich {t0:.0f}..{a['COMPN_RenderEnd']:.0f}, Clip {n} Frames; es gilt der Clip")
    return [from_fusion(mg.GetInput("Center", t0 + k), mg.GetInput("Size", t0 + k), mg.GetInput("Angle", t0 + k),
                        W, rc["star_png_radius_px"]) for k in range(n)]


# ---------------------------------------------------------------- Befehle

def push(cfg, force=False):
    rc = cfg["resolve"]
    every, keys, err = choose_keys(cfg)
    r = connect()
    proj = open_project(r, cfg, create=True)
    old = timeline_by_name(proj, rc["timeline"])
    if old and not force:
        sys.exit(f"Timeline '{rc['timeline']}' gibt es schon (Vadims Keys). Neu auf KL.orbit: push --force")
    project_settings(proj, cfg)
    if old:
        assert proj.GetMediaPool().DeleteTimelines([old]), "alte Timeline liess sich nicht loeschen"
    tl = build(proj, cfg, rc["timeline"], keys)
    proj.SetCurrentTimeline(tl)
    r.OpenPage("fusion")
    r.GetProjectManager().SaveProject()
    return (f"{rc['project']} / {tl.GetName()}: {KL.count(cfg)} Frames, Keyframes alle {every} Frames "
            f"(Kurve vs. Bahn: {fmt_err(err)})")


def pull(cfg):
    rc = cfg["resolve"]
    r = connect()
    proj = open_project(r, cfg)
    tl = timeline_by_name(proj, rc["timeline"])
    assert tl, f"Timeline '{rc['timeline']}' fehlt, erst: push"
    path = read_path(cfg, tl)
    out = os.path.join(KL.PROJECT, rc["path_file"])
    with open(out, "w") as f:
        json.dump({"frames": len(path), "source": "resolve", "path": [[round(v, 6) for v in p] for p in path]}, f)
    msg = f"{len(path)} Frames → {out}"
    if len(path) == KL.count(cfg):
        msg += f"; Abweichung von KL.orbit: {fmt_err(path_error(cfg, path))}"
    return msg


def check(cfg):
    """Selbsttest ohne Vadims Timeline anzufassen: Wegwerf-Timeline bauen (wie push), zuruecklesen (wie pull),
    je Frame gegen KL.orbit, danach loeschen. Schlaegt an, wenn eine Konvention (y-Achse, Drehsinn, Size, Henkel,
    Zeitbasis, Cliplaenge) nicht stimmt."""
    rc = cfg["resolve"]
    name = f"{rc['timeline']} Test"
    every, keys, pred = choose_keys(cfg)
    r = connect()
    proj = open_project(r, cfg, create=True)
    project_settings(proj, cfg)
    cur = proj.GetCurrentTimeline()
    old = timeline_by_name(proj, name)
    if old:
        proj.GetMediaPool().DeleteTimelines([old])
    tl = build(proj, cfg, name, keys)
    try:
        path = read_path(cfg, tl)
        marks = tl.GetMarkers()
    finally:
        if cur:
            proj.SetCurrentTimeline(cur)
        proj.GetMediaPool().DeleteTimelines([tl])
    n = KL.count(cfg)
    assert len(path) == n, f"Resolve liefert {len(path)} Frames, [loop].frames = {n}"
    err = path_error(cfg, path)
    assert within(cfg, err), f"Rundreise weicht ab: {fmt_err(err)} (Toleranz {rc['tol_pos_frac']}, " \
                             f"{100 * rc['tol_size_frac']} %, {rc['tol_rot_deg']}°)"
    keyf = [i for i in range(n) if KL.is_key(cfg, i)]
    assert sorted(marks) == keyf, f"Marker {sorted(marks)} statt {keyf}"
    return (f"check ok: {n} Frames, Keyframes alle {every}; Resolve vs. KL.orbit {fmt_err(err)} "
            f"(vorhergesagt {fmt_err(pred)}); {len(marks)} Aushang-Marker")


def render_frames(proj, tl, frames):
    """Timeline-Frames als PNG aus Resolve (Render-Queue, je Frame ein Job, danach wieder entfernt)."""
    W, H = poster_px()
    proj.SetCurrentTimeline(tl)
    assert proj.SetCurrentRenderFormatAndCodec(*PNG_CODEC), f"Renderformat {PNG_CODEC} fehlt"
    t0, jobs, dirs = tl.GetStartFrame(), [], []
    for k in frames:
        d = os.path.join(VERIFY, f"{k:03d}")
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        assert proj.SetRenderSettings({"SelectAllFrames": False, "MarkIn": t0 + k, "MarkOut": t0 + k, "TargetDir": d,
                                       "CustomName": f"stern_{k:03d}", "FormatWidth": W, "FormatHeight": H,
                                       "ExportVideo": True, "ExportAudio": False}), "SetRenderSettings abgelehnt"
        jobs.append(proj.AddRenderJob())
        dirs.append(d)
    try:
        assert proj.StartRendering(jobs), "StartRendering abgelehnt"
        t = time.time()
        while proj.IsRenderingInProgress():
            assert time.time() - t < RENDER_TIMEOUT_S, "Render dauert zu lange"
            time.sleep(0.3)
        status = [proj.GetRenderJobStatus(j) for j in jobs]
    finally:
        for j in jobs:
            proj.DeleteRenderJob(j)
    out = []
    for k, d, st in zip(frames, dirs, status):
        files = sorted(glob.glob(os.path.join(d, "*.png")))
        assert len(files) == 1, f"Frame {k}: {st}, Dateien {files}"
        out.append(np.asarray(Image.open(files[0]).convert("RGB")))
    return out


def silhouette_iou(img, p):
    """IoU der Stern-Silhouette: Resolve-Render gegen Python (star_alpha an der Bahn p = (x, y, r, rot)).
    Resolve-Silhouette = Pixel, die naeher an "Plakat mit weissem Stern" liegen als an "Plakat ohne Stern" (beides in
    Python aus layout.png + type_overlay.png gemischt). Gemessen wird nur, wo ein weisser Stern etwas aendern wuerde."""
    W, H = poster_px()
    L = np.asarray(Image.open(ASSETS["layout"]).convert("RGB"), np.float64) / 255
    ov = np.asarray(Image.open(ASSETS["type_overlay"]).convert("RGBA"), np.float64) / 255
    oa = ov[..., 3:]
    without = L * (1 - oa) + ov[..., :3] * oa
    white = 1 * (1 - oa) + ov[..., :3] * oa
    meas = np.abs(white - without).max(-1) > DIFF_MIN
    got = img / 255.0
    res = np.abs(got - white).max(-1) < np.abs(got - without).max(-1)
    x, y, r, rot = p
    py = star_alpha(r * W, rot, W, H, x * W, y * H) > 0.5
    inter, union = (res & py & meas).sum(), ((res | py) & meas).sum()
    iou = inter / union if union else 1.0
    expect = np.where(py[..., None], white, without)
    resid = float(np.abs(got - expect)[meas & (py == binary_erosion(py, iterations=2))].mean())
    return iou, py, res, float(1 - meas.mean()), resid


def verify(cfg, frames=None):
    """Rendert Frames der Stern-Bahn aus Resolve und misst die Silhouette gegen Python (IoU >= iou_min).
    Die Bahn kommt dabei aus Resolve (wie pull): geprueft wird die Umrechnung, nicht ob Vadims Bahn KL.orbit ist.
    Schreibt je Frame verify/NNN_cmp.png: Render, Python-Umriss magenta."""
    rc = cfg["resolve"]
    r = connect()
    proj = open_project(r, cfg)
    tl = timeline_by_name(proj, rc["timeline"])
    assert tl, f"Timeline '{rc['timeline']}' fehlt, erst: push"
    path = read_path(cfg, tl)
    n = len(path)
    frames = frames or [0, n // 2, n - 1]
    assert all(0 <= k < n for k in frames), f"Frames 0..{n - 1}"
    imgs = render_frames(proj, tl, frames)
    r.OpenPage("fusion")
    lines, fails = [], []
    for k, img in zip(frames, imgs):
        iou, py, res, skip, resid = silhouette_iou(img, path[k])
        edge = py & ~binary_erosion(py)
        cmp = img.copy()
        cmp[edge] = (255, 0, 255)
        Image.fromarray(cmp).save(os.path.join(VERIFY, f"{k:03d}_cmp.png"))
        x, y, rr, rot = path[k]
        lines.append(f"  Timeline-Frame {k:3d} (Plakat {k + 1:2d}): IoU {iou:.4f}  Flaeche Resolve {res.mean():.3f} / "
                     f"Python {py.mean():.3f}, nicht messbar {100 * skip:.1f} %, Restfehler {resid:.4f}  "
                     f"[x {x:.3f} y {y:.3f} r {rr:.3f} rot {rot:.1f}]")
        if iou < rc["iou_min"]:
            fails.append(k)
    report = "\n".join(lines)
    assert not fails, f"IoU unter {rc['iou_min']} auf {fails}\n{report}"
    return f"verify ok (IoU >= {rc['iou_min']}), Bilder in {VERIFY}\n{report}"


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    cfg = load()
    if cmd == "assets":
        print(assets(cfg))
    elif cmd == "push":
        print(push(cfg, force="--force" in args))
    elif cmd == "pull":
        print(pull(cfg))
    elif cmd == "check":
        print(check(cfg))
    elif cmd == "verify":
        print(verify(cfg, [int(a) for a in args[1:]] or None))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
