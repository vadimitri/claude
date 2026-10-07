#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "scikit-image"]
# ///
"""Sumo-Demo: zwei Zumo-Sprites im Ring (Iso), Anlauf, Aufprall mit Funke, Gerangel, einer fliegt raus.
Zeigt, wie die Sprites in einer kurzen Challenge-Animation sitzen; alle Werte in [demo] der zumo_sprites.toml.

Echte Pixel-Art statt Compositing: flache Flaechen in Palettenstufen, alles auf 12-fps-Ticks und ganzen Pixeln
(gepostert wie im Spiel), keine weichen Verlaeufe, kein Subpixel. Vadim 7.10. zur ersten Fassung: "zu fake".

  uv run src/zumo_sprites_demo.py      -> zumo_sprites/previz/now/demo_sumo.{mp4,gif}, oeffnet das GIF
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

import zumo_sprites as Z


def linear(keys, t):
    """Wert zum Tick t aus [[tick, wert], ...], linear dazwischen, auf ganze Pixel gerundet."""
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return int(round(v0 + (v1 - v0) * (t - t0) / max(t1 - t0, 1)))
    return int(keys[-1][1])


def stepped(keys, t):
    return [v for k, v in keys if k <= t][-1]


def ellipse(W, H, cx, cy, rx, ry):
    """Pixel-Ellipse: Pixelmitte innerhalb (gleiche Treppen links/rechts, oben/unten)."""
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1


def ring(d):
    """Flacher Pixel-Ring: Plattformkante (vorne sichtbar), Flaeche, weisser Rand. Index 1..6 = Stufe 0..5."""
    W, H = d["size_px"]
    cx, cy = d["ring_center_px"]
    rx = d["ring_rx_px"]
    ry = round(rx * d["ring_ry_frac"])
    v_top, v_side, v_rim = d["ring_values"]
    bx, by = d["border_px"]
    idx = np.ones((H, W), np.uint8)                                # Grund = Stufe 0
    for k in range(d["ring_h_px"], 0, -1):                         # Kante: Ellipse nach unten verschoben
        idx[ellipse(W, H, cx, cy + k, rx, ry)] = 1 + v_side
    idx[ellipse(W, H, cx, cy, rx, ry)] = 1 + v_rim
    idx[ellipse(W, H, cx, cy, rx - bx, ry - by)] = 1 + v_top
    return idx


def stamp(idx, rows, x, y, value):
    m = np.array([[c == "#" for c in r] for r in rows])
    h, w = m.shape
    ys, xs = np.nonzero(m)
    ys, xs = ys + y - h // 2, xs + x - w // 2
    ok = (ys >= 0) & (ys < idx.shape[0]) & (xs >= 0) & (xs < idx.shape[1])
    idx[ys[ok], xs[ok]] = value


def paste(dst, spr, x, y, pivot):
    """Sprite mit Drehpunkt auf (x, y) setzen (ganze Pixel), Index 0 = frei."""
    x0, y0 = x - int(round(pivot[0])), y - int(round(pivot[1]))
    ys, xs = np.nonzero(spr)
    ty, tx = ys + y0, xs + x0
    ok = (ty >= 0) & (ty < dst.shape[0]) & (tx >= 0) & (tx < dst.shape[1])
    dst[ty[ok], tx[ok]] = spr[ys[ok], xs[ok]]


def _job(a):
    cfg, d, anim, fr = a
    return (d, anim, fr), Z.sprite(cfg, "tq", d, anim, fr)


def main():
    cfg = Z.load(variant=Z.load()["demo"]["variant"])
    d = cfg["demo"]
    W, H = d["size_px"]
    cx, cy = d["ring_center_px"]
    n_spr = cfg["anims"]["drive"]["frames"]
    jobs = [(cfg, dd, a, fr) for dd, anims in ((0, d["anims_a"]), (180, d["anims_b"]))
            for a in {a for _, a in anims} for fr in range(n_spr)]
    with Pool() as pool:
        spr = dict(pool.map(_job, jobs))
    _, _, pivot = Z.view_canvas(cfg, cfg["views"]["tq"]["pitch_deg"])
    base = ring(d)
    lut = np.array(Z.lut(cfg, d["palette"]), np.uint8).reshape(256, 3)
    sx, sy = d["shadow_px"]
    t_imp = d["impact_tick"]
    ticks = []
    for t in range(d["ticks"]):
        idx = base.copy()
        k = t % n_spr
        jit = 0
        if stepped(d["anims_a"], t) == "push" and t < d["keys_a"][-3][0]:
            jit = d["jitter_px"] * (1 if t % 2 else -1)
        ax, bx = cx + linear(d["keys_a"], t) + jit, cx + linear(d["keys_b"], t) + jit
        fall = linear(d["fall_b"], t)
        off_ring = bx - cx > d["ring_rx_px"]
        for x, y in ((ax, cy), (bx, cy + (d["ring_h_px"] if off_ring else 0))):
            idx[ellipse(W, H, x, y, sx, sy)] = 1                   # flacher Schatten, Stufe 0
        paste(idx, spr[(180, stepped(d["anims_b"], t), k)], bx, cy + fall, pivot)
        paste(idx, spr[(0, stepped(d["anims_a"], t), k)], ax, cy, pivot)
        if t_imp <= t < t_imp + len(d["spark"]):
            stamp(idx, d["spark"][t - t_imp], (ax + bx) // 2, cy + d["spark_y_px"], 6)
        if t_imp <= t < t_imp + len(d["shake_px"]):
            dx, dy = d["shake_px"][t - t_imp]
            idx = np.roll(idx, (dy, dx), (0, 1))
        ticks.append(lut[idx])
    out = os.path.join(Z.PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    px, hold = d["px"], d["video_fps"] // d["tick_fps"]
    mp4 = os.path.join(out, "demo_sumo.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W * px}x{H * px}", "-r", str(d["video_fps"]), "-i", "-", "-vf",
                           "scale=out_color_matrix=bt709:out_range=tv", "-colorspace", "bt709", "-color_primaries",
                           "bt709", "-color_trc", "bt709", "-c:v", "libx264", "-preset", "slow", "-crf", "12",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    for fr in ticks:
        big = np.kron(fr, np.ones((px, px, 1), np.uint8)).tobytes()
        for _ in range(hold):
            ff.stdin.write(big)
    ff.stdin.close()
    ff.wait()
    gif = os.path.join(out, "demo_sumo.gif")
    ims = [Image.fromarray(np.kron(fr, np.ones((2, 2, 1), np.uint8))) for fr in ticks]
    ims[0].save(gif, save_all=True, append_images=ims[1:], duration=round(1000 / d["tick_fps"]), loop=0)
    print(mp4, gif, sep="\n")
    if "--no-open" not in sys.argv:
        subprocess.run(["open", gif])


if __name__ == "__main__":
    main()
