#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "scikit-image"]
# ///
"""Sumo-Demo: zwei Zumo-Sprites im Ring (Iso), A rammt B von der Seite und schiebt ihn ueber die Kante.
Zeigt, wie die Sprites in einer kurzen Challenge-Animation sitzen; alle Werte in [demo] der zumo_sprites.toml.

Echte Pixel-Art statt Compositing: flache Flaechen in Palettenstufen, alles auf 12-fps-Ticks und ganzen Pixeln
(gepostert wie im Spiel), keine weichen Verlaeufe, kein Subpixel. Vadim 7.10. zur ersten Fassung: "zu fake".

  uv run src/zumo_sprites_demo.py      -> zumo_sprites/previz/now/demo_sumo.{gif,mp4} + demo_sumo_alpha.mov, Kopie in
                                          [export].dir/demo, oeffnet das GIF (transparent: fuer Slides und Videos)
"""
import math
import os
import shutil
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

import zumo_sprites as Z


def linear(keys, t):
    """Wert(e) zum Tick t aus [[tick, wert, ...], ...], linear dazwischen, auf ganze Pixel gerundet."""
    for k0, k1 in zip(keys, keys[1:]):
        if k0[0] <= t <= k1[0]:
            f = (t - k0[0]) / max(k1[0] - k0[0], 1)
            v = [int(round(a + (b - a) * f)) for a, b in zip(k0[1:], k1[1:])]
            return v if len(v) > 1 else v[0]
    v = [int(a) for a in keys[-1][1:]]
    return v if len(v) > 1 else v[0]


def stepped(keys, t):
    return [v for k, v in keys if k <= t][-1]


def ellipse(W, H, cx, cy, rx, ry):
    """Pixel-Ellipse: Pixelmitte innerhalb (gleiche Treppen links/rechts, oben/unten)."""
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1


def ring(d):
    """Flacher Pixel-Ring auf transparentem Grund (Index 0): Plattformkante, Flaeche, dicker weisser Rand, Kontur.
    Index 1..6 = Stufe 0..5."""
    W, H = d["size_px"]
    cx, cy = d["ring_center_px"]
    rx = d["ring_rx_px"]
    ry = round(rx * d["ring_ry_frac"])
    v_top, v_side, v_rim = d["ring_values"]
    bx, by = d["border_px"]
    idx = np.zeros((H, W), np.uint8)
    for k in range(d["ring_h_px"], 0, -1):                         # Kante: Ellipse nach unten verschoben
        idx[ellipse(W, H, cx, cy + k, rx, ry)] = 1 + v_side
    top = ellipse(W, H, cx, cy, rx, ry)
    idx[top] = 1 + v_rim
    idx[(idx > 0) & ~top & np.roll(top, 1, 0)] = 1 + d["lip_value"]   # Lippe: erste Kantenzeile unter dem Rand
    idx[ellipse(W, H, cx, cy, rx - bx, ry - by)] = 1 + v_top
    o = idx > 0
    edge = np.zeros_like(o)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        edge |= np.roll(np.roll(o, dy, 0), dx, 1)
    idx[edge & ~o] = 1 + d["ring_outline"]
    return idx


def on_ring(d, x, y):
    """Drehpunkt (relativ zur Ringmitte) liegt auf der Ringflaeche."""
    rx = d["ring_rx_px"]
    return (x / rx) ** 2 + (y / (rx * d["ring_ry_frac"])) ** 2 <= 1


def stamp(idx, rows, x, y, value):
    m = np.array([[c == "#" for c in r] for r in rows])
    h, w = m.shape
    ys, xs = np.nonzero(m)
    ys, xs = ys + y - h // 2, xs + x - w // 2
    ok = (ys >= 0) & (ys < idx.shape[0]) & (xs >= 0) & (xs < idx.shape[1])
    idx[ys[ok], xs[ok]] = value


def paste(dst, spr, x, y, pivot):
    """Sprite mit Drehpunkt auf (x, y) setzen (ganze Pixel), Index 0 = frei. Gibt die Maske zurueck."""
    x0, y0 = x - int(round(pivot[0])), y - int(round(pivot[1]))
    ys, xs = np.nonzero(spr)
    ty, tx = ys + y0, xs + x0
    ok = (ty >= 0) & (ty < dst.shape[0]) & (tx >= 0) & (tx < dst.shape[1])
    dst[ty[ok], tx[ok]] = spr[ys[ok], xs[ok]]
    m = np.zeros(dst.shape, bool)
    m[ty[ok], tx[ok]] = True
    return m


def _job(a):
    cfg, d, anim, fr = a
    return (d, anim, fr), Z.sprite(cfg, "tq", d, anim, fr)


def main():
    cfg = Z.load(variant=Z.load()["demo"]["variant"])
    d = cfg["demo"]
    W, H = d["size_px"]
    cx, cy = d["ring_center_px"]
    n_spr = cfg["anims"]["drive"]["frames"]
    da, db = d["dir_a"], d["dir_b"]
    jobs = [(cfg, dd, a, fr) for dd, anims in ((da, d["anims_a"]), (db, d["anims_b"]))
            for a in {a for _, a in anims} for fr in range(n_spr)]
    with Pool() as pool:
        spr = dict(pool.map(_job, jobs))
    _, _, pivot = Z.view_canvas(cfg, cfg["views"]["tq"]["pitch_deg"])
    base = ring(d)
    t_imp = d["impact_tick"]
    V = Z.get_mesh(cfg)[0] - Z.PIVOT                               # A trifft B an der Flanke (Richtungen senkrecht):
    reach = (V[:, 0].max() + np.abs(V[:, 2]).max()) / cfg["render"]["mm_per_px"]   # Schildspitze + halbe Breite
    ticks, report = [], []
    for t in range(d["ticks"]):
        idx = base.copy()
        k = t % n_spr
        jit = (1 if t % 2 else -1) if d["jitter"][0] <= t < d["jitter"][1] else 0
        (ax, ay), (bx, by) = linear(d["keys_a"], t), linear(d["keys_b"], t)
        ax, bx = ax + jit, bx + jit
        fall = linear(d["fall_b"], t)
        bots = [(ay, "a", ax, ay, 0, spr[(da, stepped(d["anims_a"], t), k)]),
                (by + fall, "b", bx, by, fall, spr[(db, stepped(d["anims_b"], t), k)])]
        for _, _, x, y, f, _ in bots:
            if on_ring(d, x, y) and not f:                         # Schatten nur auf dem Ring (Grund ist transparent)
                sh = ellipse(W, H, cx + x, cy + y, *d["shadow_px"]) & (base == 1 + d["ring_values"][0])
                idx[sh] = 1
        for _, name, x, y, f, s in sorted(bots, key=lambda b: b[0]):   # weiter hinten zuerst
            paste(idx, s, cx + x, cy + y + f, pivot)
        if t == t_imp:                                             # Gate am Boden (im Bild ueberdecken sich die Sprites in
            dist = math.hypot(bx - ax, (by - ay) / d["ring_ry_frac"])   # Iso auch ohne Beruehrung): Abstand der Drehpunkte
            report.append(f"Kontakt Tick {t}: Abstand {dist:.1f} px, Schild + halbe Breite {reach:.1f} px (Gate +-1.5)")
            assert abs(dist - reach) <= 1.5, report[-1]
        if t_imp <= t < t_imp + len(d["spark"]):
            stamp(idx, d["spark"][t - t_imp], cx + (ax + bx) // 2, cy + (ay + by) // 2 + d["spark_y_px"], 6)
        if t_imp <= t < t_imp + len(d["shake_px"]):
            dx, dy = d["shake_px"][t - t_imp]
            idx = np.roll(idx, (dy, dx), (0, 1))
        ticks.append(idx)
    out = os.path.join(Z.PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    pal = Z.lut(cfg, d["palette"])
    lut = np.array(pal, np.uint8).reshape(256, 3)
    px, hold, fps = d["px"], d["video_fps"] // d["tick_fps"], d["video_fps"]
    big = lambda a, n: np.kron(a, np.ones((n, n) + (1,) * (a.ndim - 2), np.uint8))

    def ffmpeg(path, pix_in, args):
        return subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", pix_in,
                                 "-s", f"{W * px}x{H * px}", "-r", str(fps), "-i", "-", *args, path], stdin=subprocess.PIPE)

    mp4 = os.path.join(out, "demo_sumo.mp4")                      # Vorschau auf Maker-Night-Grund
    mov = os.path.join(out, "demo_sumo_alpha.mov")                # ProRes 4444 mit Alpha (Resolve, AE)
    f1 = ffmpeg(mp4, "rgb24", ["-vf", "scale=out_color_matrix=bt709:out_range=tv", "-colorspace", "bt709",
                               "-color_primaries", "bt709", "-color_trc", "bt709", "-c:v", "libx264", "-preset", "slow",
                               "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    f2 = ffmpeg(mov, "rgba", ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                              "-vendor", "apl0"])
    alpha = np.full(256, 255, np.uint8)
    alpha[0] = 0
    for fr in ticks:
        ground = np.where(fr == 0, 1 + d["preview_ground"], fr)
        rgb, rgba = big(lut[ground], px).tobytes(), big(np.dstack([lut[fr], alpha[fr]]), px).tobytes()
        for _ in range(hold):
            f1.stdin.write(rgb)
            f2.stdin.write(rgba)
    for f in (f1, f2):
        f.stdin.close()
        f.wait()
    gif = os.path.join(out, "demo_sumo.gif")                      # transparent, 1-Bit-Alpha (Index 0)
    ims = [Z.indexed(fr, pal, d["gif_px"]) for fr in ticks]
    ims[0].save(gif, save_all=True, append_images=ims[1:], duration=round(1000 / d["tick_fps"]), loop=0,
                transparency=0, disposal=2)
    with open(os.path.join(out, "demo_report.txt"), "w") as f:
        f.write("\n".join(report) + "\n")
    dst = os.path.join(os.path.expanduser(cfg["export"]["dir"]), "demo")
    os.makedirs(dst, exist_ok=True)
    for p in (mp4, mov, gif):
        shutil.copy(p, dst)
    print(*report, mp4, mov, gif, f"-> {dst}", sep="\n")
    if "--no-open" not in sys.argv:
        subprocess.run(["open", gif])


if __name__ == "__main__":
    main()
