#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "scikit-image"]
# ///
"""Sumo-Demo: zwei Zumo-Sprites im Ring (Iso), Anlauf, Aufprall mit Spark-Stern, Gerangel, einer fliegt raus.
Zeigt, wie die Sprites in einer kurzen Challenge-Animation sitzen; alle Werte in [demo] der zumo_sprites.toml.

  uv run src/zumo_sprites_demo.py      -> zumo_sprites/previz/now/demo_sumo.{mp4,gif}, oeffnet das GIF
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

import zumo_sprites as Z
from makernight_sparks import star_alpha
from styles import bayer


def ease(t):
    return t * t * (3 - 2 * t)


def keyed(keys, f):
    """Wert zum Frame f aus [[frame, wert], ...], dazwischen weich (smoothstep)."""
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            return v0 + (v1 - v0) * ease((f - f0) / max(f1 - f0, 1))
    return keys[-1][1]


def stepped(keys, f):
    return [v for k, v in keys if k <= f][-1]


def _job(a):
    cfg, d, anim, fr = a
    return (d, anim, fr), Z.sprite(cfg, "tq", d, anim, fr)


def background(d):
    """Ring als Plattform im Licht: Wertfeld (Stufen als float) -> Bayer 4x4 -> Index 1..6."""
    W, H = d["size_px"]
    cx, cy = d["ring_center_px"]
    rx, ry, h = d["ring_rx_px"], d["ring_rx_px"] * d["ring_ry_frac"], d["ring_h_px"]
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    r_top = np.hypot((xx - cx) / rx, (yy - cy) / ry)                     # 1 = Ringkante oben
    r_bot = np.hypot((xx - cx) / rx, (yy - cy - h) / ry)
    lo, hi = d["ring_light"]
    v = d["ground_light"] * np.exp(-np.maximum(r_bot - 1, 0) * rx / d["glow_cells"] * 3)   # Schein auf dem Boden
    side = (r_bot <= 1) & (yy > cy) & (r_top > 1)                          # sichtbare Plattformkante (vorne)
    v = np.where(side, 1.4, v)
    top = r_top <= 1
    v = np.where(top, lo + (hi - lo) * np.exp(-r_top * rx / d["glow_cells"] * 2.2), v)
    border = top & (r_top > 1 - d["border_px"] / rx)
    v = np.where(border, 5.0, v)
    thr = np.tile(bayer(4), (H // 4 + 1, W // 4 + 1))[:H, :W]
    return (np.clip(np.floor(v + thr), 0, 5) + 1).astype(np.uint8), top


def paste(dst, spr, x, y, pivot):
    """Sprite mit Drehpunkt auf (x, y) setzen, Index 0 = frei."""
    h, w = spr.shape
    x0, y0 = int(round(x - pivot[0])), int(round(y - pivot[1]))
    ys, xs = np.nonzero(spr)
    ys, xs = ys + y0, xs + x0
    ok = (ys >= 0) & (ys < dst.shape[0]) & (xs >= 0) & (xs < dst.shape[1])
    dst[ys[ok], xs[ok]] = spr[ys[ok] - y0, xs[ok] - x0]


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
    bg, top = background(d)
    lut = np.array(Z.lut(cfg, d["palette"]), np.uint8).reshape(256, 3)
    sx, sy = d["shadow_px"]
    f_imp, radii = d["impact"]
    frames = []
    for f in range(d["frames"]):
        idx = bg.copy()
        k = (f // d["sprite_every"]) % n_spr
        jit = 0
        if stepped(d["anims_a"], f) == "push" and f < d["keys_a"][-3][0]:
            jit = d["jitter_px"] * (1 if (f // 3) % 2 else -1)
        ax, bx = cx + keyed(d["keys_a"], f) + jit, cx + keyed(d["keys_b"], f) + jit
        by = cy + keyed(d["fall_b"], f)
        for x, y in ((ax, cy), (bx, cy + (d["ring_h_px"] if bx - cx > d["ring_rx_px"] else 0))):   # Schatten
            yy, xx = np.mgrid[0:H, 0:W] + 0.5
            idx[np.hypot((xx - x) / sx, (yy - y) / sy) <= 1] = 1
        paste(idx, spr[(180, stepped(d["anims_b"], f), k)], bx, by, pivot)
        paste(idx, spr[(0, stepped(d["anims_a"], f), k)], ax, cy, pivot)
        if f_imp <= f < f_imp + len(radii):                       # Aufprall: Spark-Stern an der Kontaktstelle
            R = radii[f - f_imp]
            win = star_alpha((ax + bx) / 2, cy - 15, R, 0, W, H)
            if win:
                y0, y1, x0, x1, al = win
                idx[y0:y1, x0:x1][al >= 0.5] = 6
        if f_imp <= f < f_imp + len(d["shake_px"]):
            dx, dy = d["shake_px"][f - f_imp]
            idx = np.roll(idx, (dy, dx), (0, 1))
        frames.append(lut[idx])
    out = os.path.join(Z.PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    px = d["px"]
    mp4 = os.path.join(out, "demo_sumo.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W * px}x{H * px}", "-r", str(d["fps"]), "-i", "-", "-vf",
                           "scale=out_color_matrix=bt709:out_range=tv", "-colorspace", "bt709", "-color_primaries",
                           "bt709", "-color_trc", "bt709", "-c:v", "libx264", "-preset", "slow", "-crf", "12",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    for fr in frames:
        ff.stdin.write(np.kron(fr, np.ones((px, px, 1), np.uint8)).tobytes())
    ff.stdin.close()
    ff.wait()
    gif = os.path.join(out, "demo_sumo.gif")
    ims = [Image.fromarray(np.kron(fr, np.ones((2, 2, 1), np.uint8))) for fr in frames]
    ims[0].save(gif, save_all=True, append_images=ims[1:], duration=round(1000 / d["fps"]), loop=0)
    print(mp4, gif, sep="\n")
    if "--no-open" not in sys.argv:
        subprocess.run(["open", gif])


if __name__ == "__main__":
    main()
