#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "scikit-image"]
# ///
"""Spark Flow als Video: das langsam fliessende Graufeld aus Figma (Shader-Fill "Spark Flow", Komponente Gradient/Flow),
gedithert wie die Spark Lens (Zellraster, Bayer 4x4, 6 Stufen). Warum hier nochmal: Figmas Server-Videoexport rendert
eigene Shader nicht (gemessen 7.10.: mit Lens schwarz, ohne Lens weiss). Dieselbe Mathe wie der WGSL-Shader, gegen
die echte GPU geprueft (Abweichung < 1/2 Graustufe), also ist ein Video von hier das, was Figma live zeigt.

  uv run src/flow.py sheet            Kontaktbogen Stil x Palette x 4 Zeitpunkte  -> flow/sheet.png
  uv run src/flow.py render [name]    Loops aus flow.toml [[render]]               -> flow/out/<name>.mp4 (+ .mov)
  uv run src/flow.py test             Selbsttest: Naht, GPU-Referenzpixel, Dither = Lens
Vorschauen landen zusaetzlich flach in Vorschau/ des Hauptcheckouts (Hardlink, auch aus einem Worktree).
"""
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import styles as S

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "flow" / "flow.toml"
P_KEY = {code: key for code, key, *_ in next(a for a in S.AXES if a[0] == "P")[3]}   # "P11" -> "cherenkov"
STEPS = 6                                                                            # Lens: 6 Colorway-Stufen
KNOBS = ("width_px", "height_px", "cell_px", "fps", "loop_s", "angle_deg", "low", "high", "seed", "prores")


def load(path=CONFIG):
    """Config lesen und pruefen, bevor irgendwas rendert. Jeder [[render]] = defaults + Stil + eigene Werte."""
    cfg = tomllib.loads(path.read_text())
    errs = []
    for r in cfg.get("render", []):
        r.update({k: v for k, v in cfg["defaults"].items() if k not in r})
        if r.get("style") not in cfg["style"]:
            errs.append(f"{r.get('name')}: style {r.get('style')!r} fehlt in [style.*]")
        if r.get("palette") not in P_KEY:
            errs.append(f"{r.get('name')}: palette {r.get('palette')!r} unbekannt (P1, P5 ... P26)")
        if not 0 <= r.get("low", 0) < r.get("high", 1) <= 1:
            errs.append(f"{r.get('name')}: braucht 0 <= low < high <= 1")
        if r.get("width_px", 0) % r.get("cell_px", 1) or r.get("height_px", 0) % r.get("cell_px", 1):
            errs.append(f"{r.get('name')}: width_px/height_px muessen Vielfache von cell_px sein")
        missing = [k for k in KNOBS if k not in r]
        if missing:
            errs.append(f"{r.get('name')}: es fehlen {missing} (in [defaults] oder im [[render]])")
    if errs:
        sys.exit("flow.toml:\n  " + "\n  ".join(errs))
    return cfg


def pal6(code):
    """6 Stufen RGB; 4-stufige Paletten (P6, P9, P26) gedoppelt 0 1 1 2 2 3 wie kickoff_loop.station und Figma."""
    pal = S.hexpal(P_KEY[code])
    return pal[np.round(np.arange(STEPS) * (len(pal) - 1) / (STEPS - 1)).astype(int)].astype(np.uint8)


def field(w, h, t, loop_s=24.0, angle_deg=-60.0, glow=0.0, flow=0.6, size=1.0, low=0.0, high=1.0, seed=0.0, cell=1):
    """Grauwert 0..1 je Zelle, Zeile fuer Zeile wie fs_main im Shader. Abgetastet, wo die Lens abtastet (Zellmitte
    ci*cell + cell//2, Pixelmitte +0.5). Alle Zeitterme sind ganzzahlige Vielfache von 2 pi t / loop -> nahtlos."""
    x = (np.arange(w // cell) * cell + cell // 2 + 0.5) / w
    y = (np.arange(h // cell) * cell + cell // 2 + 0.5) / h
    ar, sc = w / h, max(0.1, size)
    px, py = (x[None, :] - 0.5) * ar / sc, (y[:, None] - 0.5) / sc
    T = 2 * np.pi * ((t / max(1.0, loop_s)) % 1)
    s = seed * 1.618
    qx = px + flow * 0.22 * (np.sin(1.7 * py + T + s) + 0.5 * np.sin(3.1 * py - 2 * T + 2 * s))
    qy = py + flow * 0.22 * (np.sin(1.3 * px - T + 0.7 + s) + 0.5 * np.sin(2.9 * px + 2 * T + 1.9))
    th = np.radians(angle_deg) + 0.35 * np.sin(T + s)
    ext = 0.5 * np.hypot(ar, 1) / sc
    ramp = np.clip(0.5 + (qx * np.cos(th) + qy * np.sin(th)) / (2 * ext), 0, 1)
    lights = [((np.cos(T + s), np.sin(T + 0.5 + s)), 0.30),                       # Lissajous-Bahnen, ganzzahlig
              ((np.cos(T + 2.1 + s), np.sin(2 * T + 1.8 + s)), 0.22),
              ((np.cos(2 * T + 4.2 + s), np.sin(T + 3.1 + s)), 0.16)]
    e = sum(np.exp(-np.hypot(qx - 0.36 * ar * cx / sc, qy - 0.30 * cy / sc) / (r / sc)) for (cx, cy), r in lights)
    g = 1 - np.exp(-1.1 * e)
    f = np.clip(1 - (1 - ramp * (1 - 0.6 * glow)) * (1 - glow * g), 0, 1)          # Lichter per Screen
    f = f * f * (3 - 2 * f)
    return low + (high - low) * f


def frame(r, style, t):
    """Ein RGB-Bild: Feld je Zelle -> Bayer 4x4 auf 6 Stufen (styles.dither = Regel der Lens) -> Palette."""
    v = field(r["width_px"], r["height_px"], t, r["loop_s"], r["angle_deg"], low=r["low"], high=r["high"],
              seed=r["seed"], cell=r["cell_px"], **style)
    return pal6(r["palette"])[S.dither(v, STEPS - 1, "bayer4", r["cell_px"])]


def vorschau(path):
    """Hardlink nach Vorschau/ im Hauptcheckout (git common dir), damit Vadim alles an einem Ort findet."""
    common = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True).stdout.strip()
    dst = Path(common).parent / "Vorschau" / ("flow_" + path.name)
    dst.parent.mkdir(exist_ok=True)
    dst.unlink(missing_ok=True)
    os.link(path, dst)
    return dst


def render(cfg, only=None):
    out = ROOT / "flow" / "out"
    out.mkdir(parents=True, exist_ok=True)
    for r in cfg["render"]:
        if only and r["name"] != only:
            continue
        n = round(r["fps"] * r["loop_s"])                    # genau eine Schleife: Bild n waere wieder Bild 0
        W, H = r["width_px"], r["height_px"]
        mp4 = out / f"{r['name']}.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(r["fps"]), "-i", "-",
               "-c:v", "libx264", "-crf", "12", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               str(mp4)]
        if r["prores"]:
            cmd += ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le", str(out / f"{r['name']}.mov")]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(n):
            ff.stdin.write(frame(r, cfg["style"][r["style"]], i / r["fps"]).tobytes())
        ff.stdin.close()
        if ff.wait():
            sys.exit(f"ffmpeg fehlgeschlagen bei {r['name']}")
        print(f"{r['name']}: {n} Bilder, {r['loop_s']} s Loop -> {mp4}  (Vorschau: {vorschau(mp4)})")


def sheet(cfg):
    """Stil x Palette, je times_frac der Schleife. Kacheln 480x270 mit 2-px-Zellen = 4 px bei 1080p."""
    sh, d = cfg["sheet"], cfg["defaults"]
    rows = []
    for name, style in cfg["style"].items():
        for p in sh["palettes"]:
            r = {**d, "palette": p, "width_px": 480, "height_px": 270, "cell_px": 2}
            tiles = [frame(r, style, f * d["loop_s"]) for f in sh["times_frac"]]
            row = Image.fromarray(np.concatenate(tiles, 1))
            ImageDraw.Draw(row).text((8, 6), f"{name} · {p} {S.CODENAME[P_KEY[p]]}", fill=tuple(int(c) for c in pal6(p)[5]))
            rows.append(np.asarray(row))
    path = ROOT / "flow" / "sheet.png"
    Image.fromarray(np.concatenate(rows, 0)).save(path)
    print(f"{path}  (Vorschau: {vorschau(path)})")


def test():
    """Misst am fertigen Feld/Bild. Die Referenzpixel kommen aus dem WGSL-Shader auf echter WebGPU (Deno, 7.10.):
    480x270, cell 1. Driftet die Formel hier oder im Shader, schlaegt der Test an."""
    a = field(480, 270, 0.0, glow=0.3, flow=1.0, size=0.7, seed=2)
    b = field(480, 270, 24.0, glow=0.3, flow=1.0, size=0.7, seed=2)
    assert np.abs(a - b).max() < 1e-9, "Naht: Bild 0 != Bild nach einer Schleife"
    gpu = [  # (Parameter, t_s, [(y, x, Grauwert 0..255 vom Shader)])
        (dict(glow=0.6, flow=0.45), 6.0,
         [(0, 0, 72), (50, 100, 119), (135, 240, 137), (200, 400, 117), (269, 479, 104), (30, 420, 167)]),
        (dict(glow=0.3, flow=1.0, size=0.7, seed=3, angle_deg=20), 13.7,
         [(0, 0, 10), (50, 100, 89), (135, 240, 146), (200, 400, 187), (269, 479, 220), (30, 420, 159)]),
    ]
    for kw, t, pts in gpu:
        v = field(480, 270, t, **kw)
        for y, x, ref in pts:
            assert abs(v[y, x] * 255 - ref) <= 1.0, f"Shader-Referenz {kw} t={t} ({y},{x}): {v[y, x] * 255:.1f} != {ref}"
    lv = np.repeat(np.arange(STEPS)[None, :] / (STEPS - 1), 4, 0)        # exakte Stufen k/5 bleiben flaechig (Lens-Regel)
    assert (S.dither(lv, STEPS - 1, "bayer4", 1) == np.arange(STEPS)).all(), "exakte Stufe nicht flaechig"
    print("flow test ok: Naht exakt, 12 GPU-Referenzpixel <= 1/255, exakte Stufen flaechig")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sheet"
    if cmd == "test":
        test()
    elif cmd == "render":
        render(load(), sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "sheet":
        sheet(load())
    else:
        sys.exit(__doc__)
