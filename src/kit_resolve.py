"""Spark Kit -> DaVinci Resolve: legt das Projekt SPARK_Template an bzw. frischt es auf (Bins, Timelines, Lens).

Laeuft IN Resolve (Python 3.14 der App), nicht mit uv:
  - per MCP "DaVinci Resolve" run_script_unsafe:  import runpy; result = runpy.run_path("<pfad>/src/kit_resolve.py")["build"](resolve)
  - oder Workspace > Scripts, bzw. ResolvePython src/kit_resolve.py
Medien kommen aus [publish].dir (Team-Nextcloud), damit die Links dauerhaft gueltig sind: vorher `uv run src/kit.py publish`.

Sicherheitsriegel: Projektwechsel schliesst das offene Projekt. Ist TRMNL (Vadims Live-Schnitt) offen, bricht das Skript ab.
"""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = tomllib.loads((ROOT / "kit" / "kit.toml").read_text())
NEVER_CLOSE = {"TRMNL"}                       # Vadims Live-Schnitt: nie schliessen, nie anfassen
BINS = {"01 Spark": ["elements/spark_spin_S2.mov", "elements/spark_nest_S7.mov", "elements/spark_cover_{fmt}.mov",
                     "elements/wordmark_SPARK.png", "elements/logo_spark.png", "elements/qr_*.png",
                     "elements/wall_*_{fmt}.png"],
        "02 Gruende": ["elements/flow_drift_{fmt}.mp4", "elements/flow_tide_{fmt}.mp4", "elements/nest_tunnel_{fmt}.mp4"],
        "03 Zumo": ["zumo/scenes/*/*_value.mov", "zumo/emoji/*.gif"],
        "04 Sound": ["sound/*.wav"],
        "05 Brand": ["brand/colorways.png", "brand/lens_testchart.png"]}


def files(base, pattern, fmts):
    pats = [pattern.format(fmt=f) for f in fmts] if "{fmt}" in pattern else [pattern]
    return sorted({str(p) for pat in pats for p in base.glob(pat)})


def build(resolve, colorway=None):
    rep = []
    base = Path(CFG["publish"]["dir"]).expanduser()
    r = CFG["resolve"]
    fps = CFG["elements"]["fps"]
    fmts = CFG["elements"]["formats"]
    pm = resolve.GetProjectManager()
    cur = pm.GetCurrentProject()
    if cur and cur.GetName() in NEVER_CLOSE:
        raise SystemExit(f"{cur.GetName()} ist offen (Live-Schnitt): Abbruch, nichts geaendert.")
    if cur and cur.GetName() != r["project"]:
        pm.SaveProject()
        rep.append(f"gespeichert + geschlossen: {cur.GetName()}")
    proj = pm.LoadProject(r["project"])
    fresh = proj is None
    if fresh:
        proj = pm.CreateProject(r["project"])
        w, h = fmts[next(iter(r["timelines"].values()))]
        ok = proj.SetSettings({"timelineFrameRate": str(fps), "timelinePlaybackFrameRate": str(fps),
                               "timelineResolutionWidth": str(w), "timelineResolutionHeight": str(h),
                               "timelineOutputResMatchTimelineRes": "1", "timelineSampleRate": "48000"})
        rep.append(f"Projekt neu, Settings {'ok' if ok else 'FEHLER'}")
    mp = proj.GetMediaPool()
    root = mp.GetRootFolder()
    have = {f.GetName(): f for f in root.GetSubFolderList()}
    items = {}
    for bin_name, pats in BINS.items():
        folder = have.get(bin_name) or mp.AddSubFolder(root, bin_name)
        mp.SetCurrentFolder(folder)
        known = {c.GetClipProperty("File Path"): c for c in folder.GetClipList()}
        new = [p for pat in pats for p in files(base, pat, fmts) if p not in known]
        got = mp.ImportMedia(new) if new else []
        for c in list(known.values()) + list(got or []):
            items[Path(c.GetClipProperty("File Path")).name] = c
        rep.append(f"{bin_name}: {len(known)} da, {len(got or [])} neu")
    mp.SetCurrentFolder(have.get("06 Footage") or mp.AddSubFolder(root, "06 Footage"))
    mp.SetCurrentFolder(root)

    code = colorway or r["default_colorway"]
    lut = f"Spark/Colorways/{code} {dict(_codenames())[code]}.dctl"
    tls = {proj.GetTimelineByIndex(i + 1).GetName() for i in range(proj.GetTimelineCount())}
    if "00 Lens-Test" not in tls and items.get("lens_testchart.png"):
        # Testbild mit der Lens als Clip-LUT: Render dieses Bildes = numpy-Referenz (kit.lens), Befund 10.10.: 99.999 %
        tl = mp.CreateEmptyTimeline("00 Lens-Test")
        got = mp.AppendToTimeline([{"mediaPoolItem": items["lens_testchart.png"], "trackIndex": 1,
                                    "recordFrame": tl.GetStartFrame()}]) or []
        rep.append(f"00 Lens-Test: LUT {'ok' if got and got[0].GetNodeGraph().SetLUT(1, lut) else 'FEHLER'}")
    for tl_name, fmt in r["timelines"].items():
        if tl_name in tls:
            rep.append(f"Timeline {tl_name}: existiert, unveraendert (Vadims Arbeit)")
            continue
        tl = mp.CreateEmptyTimeline(tl_name)
        proj.SetCurrentTimeline(tl)
        w, h = fmts[fmt]
        tl.SetSettings({"useCustomSettings": "1", "timelineResolutionWidth": str(w), "timelineResolutionHeight": str(h)})
        for _ in range(4):
            tl.AddTrack("video")
        tl.AddTrack("audio", "stereo")
        for i, n in enumerate(["Grund", "Spark", "Titel", "Zumo", "Lens"], 1):
            tl.SetTrackName("video", i, n)
        for i, n in enumerate(["Musik", "SFX"], 1):
            tl.SetTrackName("audio", i, n)
        bar = round(4 * 60 / CFG["sound"]["bpm"] * fps)          # Takt in Bildern (120 BPM, 24 fps: 48)
        start = tl.GetStartFrame()
        clip = lambda n: items.get(n)
        place = []
        if clip(f"flow_drift_{fmt}.mp4"):
            place.append({"mediaPoolItem": clip(f"flow_drift_{fmt}.mp4"), "startFrame": 0, "endFrame": 4 * bar - 1,
                          "trackIndex": 1, "recordFrame": start, "mediaType": 1})
        ncov = round(CFG["elements"]["cover_s"] * fps)
        if clip("spark_spin_S2.mov"):
            n = round(CFG["elements"]["spin_loop_s"] * fps)
            end = 2 * bar - ncov                                    # Spin bis zur Blende, Schleife fuer Schleife
            for k in range(-(-end // n)):
                place.append({"mediaPoolItem": clip("spark_spin_S2.mov"), "startFrame": 0,
                              "endFrame": min(n, end - k * n) - 1, "trackIndex": 2, "recordFrame": start + k * n})
        if clip(f"spark_cover_{fmt}.mov"):                          # Blende endet genau auf Takt 3 (Schnitt auf dem Beat)
            place.append({"mediaPoolItem": clip(f"spark_cover_{fmt}.mov"), "trackIndex": 2,
                          "recordFrame": start + 2 * bar - ncov})
        if clip(f"nest_tunnel_{fmt}.mp4"):
            place.append({"mediaPoolItem": clip(f"nest_tunnel_{fmt}.mp4"), "startFrame": 0, "endFrame": 2 * bar - 1,
                          "trackIndex": 1, "recordFrame": start + 2 * bar, "mediaType": 1})
        if clip("MN_loop_full.wav"):
            place.append({"mediaPoolItem": clip("MN_loop_full.wav"), "startFrame": 0, "endFrame": 4 * bar - 1,
                          "trackIndex": 1, "recordFrame": start, "mediaType": 2})
        for name, at in (("riser_2bar.wav", 0), ("hit_impact.wav", 2 * bar)):
            if clip(name):
                place.append({"mediaPoolItem": clip(name), "trackIndex": 2, "recordFrame": start + at, "mediaType": 2})
        got = mp.AppendToTimeline(place) or []
        for b in range(r["marker_bars"]):
            tl.AddMarker(b * bar, "Lavender" if b % 4 else "Purple", f"Takt {b + 1}", "", 1)
        # Lens: Spur "Lens" bleibt leer. Befund 10.10.: die API kann weder einen Adjustment Clip einfuegen
        # (InsertGenerator/InsertFusionGenerator "Adjustment Clip" -> None) noch die Timeline-Grade fuellen (0 Nodes,
        # SetLUT und ApplyGradeFromDRX wirkungslos). Einmal von Hand: Adjustment Clip auf "Lens", LUT setzt lens_on().
        rep.append(f"Timeline {tl_name} {w}x{h}: {len(got)}/{len(place)} Clips, {r['marker_bars']} Taktmarker")
    rep += lens_on(proj, lut)
    pm.SaveProject()
    return rep


def lens_on(proj, lut):
    """Setzt die Lens-LUT auf jeden Adjustment Clip jeder Timeline (egal auf welcher Spur) und meldet, wenn darueber
    noch Spuren liegen: was ueber der Lens liegt, bleibt ungerastert (Titel, Zumo muessen darunter)."""
    rep = []
    for i in range(proj.GetTimelineCount()):
        tl = proj.GetTimelineByIndex(i + 1)
        n = tl.GetTrackCount("video")
        adj = [(k, it) for k in range(1, n + 1) for it in (tl.GetItemListInTrack("video", k) or [])
               if it.GetName() == "Adjustment Clip"]
        if not adj:
            if not tl.GetName().startswith("00"):
                rep.append(f"Lens {tl.GetName()}: kein Adjustment Clip -> Effects > Adjustment Clip auf die oberste Spur")
            continue
        ok = sum(bool(it.GetNodeGraph() and it.GetNodeGraph().SetLUT(1, lut)) for _, it in adj)
        top = max(k for k, _ in adj)
        warn = f", ACHTUNG liegt auf V{top}, nicht ganz oben (V{n}): auf die oberste Spur ziehen" if top < n else ""
        rep.append(f"Lens {tl.GetName()}: {ok}/{len(adj)} Adjustment Clips mit {lut}{warn}")
    return rep


def _codenames():
    """P-Code -> Codename, ohne styles.py zu importieren (laeuft im Python von Resolve ohne numpy)."""
    lens = Path(CFG["lens"]["resolve_dir"]) / "Colorways"
    return [(p.stem.split(" ", 1)[0], p.stem.split(" ", 1)[1]) for p in lens.glob("*.dctl")]


if __name__ == "__main__":
    import DaVinciResolveScript as dvr
    print("\n".join(build(dvr.scriptapp("Resolve"))))
