#!/usr/bin/env python3
"""SPARK Motion Pack - prozedurale Transitions / Loops / Akzente in 1-Bit-, Halftone- und Solid-Optik.

Jeder Effekt ist ein *Feld* v(x, y) in [0, 1] (1 = Vordergrund). Ein Stil macht daraus Pixel:
  dots      geordnetes Bayer-Dither, 8-px-Bloecke (der E-Ink-Look)
  fine      dasselbe, 4-px-Bloecke
  halftone  Rasterpunkte, deren Radius mit v waechst
  solid     glatte Kante, kein Raster
Transitions laufen ueber p = 0..2: 0->1 zudecken, bei 1 ist das Bild voll bedeckt, 1->2 aufdecken.
Erste Haelfte allein = "in", zweite Haelfte allein = "out" (einfach in der Mitte trimmen).

Aufruf (uv bringt numpy + pillow mit):
  uv run --with numpy --with pillow python motionpack.py              # Standard-Pack
  uv run --with numpy --with pillow python motionpack.py check        # nur Selbsttest
  uv run --with numpy --with pillow python motionpack.py one iris_spark 16x9 halftone spark mp4
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

FPS = 25
ROOT = os.path.dirname(os.path.abspath(__file__))
POSTER = "/Users/vadim/Nextcloud/Sporga/assets/digital/assets/spark_poster.png"
ASPECTS = {"9x16": (1080, 1920), "16x9": (1920, 1080), "1x1": (1080, 1080), "gif": (480, 480)}
PALETTES = {                          # (Vordergrund, Hintergrund)
    "mono": ("#FFFFFF", "#000000"), "ink": ("#141414", "#F2EFE6"), "spark": ("#FFFFFF", "#1A3A6E"),
    "navy": ("#1A3A6E", "#FFFFFF"), "red": ("#E5352B", "#0B0B0B"), "yellow": ("#F5C518", "#0B0B0B"),
}


# ---------------------------------------------------------------- Sternform (Spark-Logo)

def _star_profile():
    """R(theta) des Spark-Sterns aus dem Poster, 360 Strahlen, Spitze = 1."""
    try:
        a = np.asarray(Image.open(POSTER).getchannel("A")) > 127
    except OSError:                   # ponytail: Fallback-Formel, falls das Poster fehlt
        t = np.radians(np.arange(360))
        return 0.38 + 0.62 * np.abs(np.cos(3 * t)) ** 6
    ys, xs = np.nonzero(a)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    r = np.arange(0, max(a.shape), 0.5)
    out = []
    for k in range(360):
        t = math.radians(k)
        x = (cx + r * math.cos(t)).astype(int)
        y = (cy + r * math.sin(t)).astype(int)
        ok = (x >= 0) & (x < a.shape[1]) & (y >= 0) & (y < a.shape[0])
        inside = np.zeros_like(ok)
        inside[ok] = a[y[ok], x[ok]]
        out.append(r[np.argmin(inside)] if not inside.all() else r[-1])
    out = np.array(out)
    out = np.mean([np.roll(out, 60 * k) for k in range(6)], axis=0)   # exakt 6-fach symmetrisch -> Rotation loopt
    return out / out.max()


STAR = _star_profile()


# ---------------------------------------------------------------- Raster, auf dem Felder rechnen

class Grid:
    def __init__(self, gw, gh, seed=7):
        self.w, self.h = gw, gh
        y, x = np.mgrid[0:gh, 0:gw].astype(np.float32)
        self.nx, self.ny = (x + 0.5) / gw, (y + 0.5) / gh
        s = min(gw, gh)
        self.cx, self.cy = (x + 0.5 - gw / 2) / s, (y + 0.5 - gh / 2) / s     # Mitte = 0, kurze Seite = 1
        d = np.hypot(self.cx, self.cy)
        self.R = d / d.max()                                                # 0 Mitte .. 1 Ecke
        self.theta = np.arctan2(self.cy, self.cx)
        self.A = ((np.arctan2(self.cx, -self.cy) / (2 * np.pi)) % 1.0)      # Uhrzeiger ab 12 Uhr
        self.portrait = gh > gw
        self.L = self.ny if self.portrait else self.nx                      # lange Achse
        self.rng = np.random.default_rng(seed)
        self.H = self.rng.random((gh, gw)).astype(np.float32)               # Rauschen pro Zelle

    def star(self, rot_deg=0.0):
        """Sternfoermiger Abstand, 0 Mitte .. 1 = Stern deckt das ganze Bild."""
        k = np.floor(np.degrees(self.theta) - rot_deg).astype(int) % 360
        s = np.hypot(self.cx, self.cy) / STAR[k]
        return s / s.max()

    def tiles(self, n):
        """Zufallswert pro Kachel, n Kacheln ueber die kurze Seite."""
        s = min(self.w, self.h)
        ix = (self.nx * self.w * n / s).astype(int)
        iy = (self.ny * self.h * n / s).astype(int)
        table = np.random.default_rng(3).random((iy.max() + 1, ix.max() + 1))
        return table[iy, ix].astype(np.float32)


def ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def cover(m, p, soft=0.25):
    """Generische Wisch-Transition: m in [0,1] = Reihenfolge, in der Pixel bedeckt werden."""
    if p <= 1:
        return ss((p * (1 + soft) - m) / soft)
    return 1 - ss(((p - 1) * (1 + soft) - m) / soft)


# ---------------------------------------------------------------- Effekte

def _norm(m):
    return (m - m.min()) / (m.max() - m.min() + 1e-9)


def _thirds(g, p):
    k = np.clip((g.L * 3).astype(int), 0, 2)
    order = np.array([0.0, 1.0, 0.5])[k]              # erst oben, dann unten, zuletzt Mitte (wie v01)
    local = np.abs(g.L * 3 - k - 0.5) * 2              # 0 Drittelmitte .. 1 Kante
    return cover(0.45 * order + 0.55 * local, p, 0.2)


def _ripple(metric):
    def f(g, p):
        m = metric(g)
        front = 1.35 * (p / 2) ** 0.8
        amp = 1 - ss((p - 1.5) / 0.5)
        v = sum(a * np.exp(-((m - (front - 0.09 * k)) / 0.035) ** 2) for k, a in ((0, 1), (1, .6), (2, .35), (3, .2)))
        return np.clip(v, 0, 1) * amp
    return f


def _flash(g, p):
    seq = [0, .35, 1, 0, 1, 1, .6, 1, 1, 1, 1, 1, 1, .6, 1, 0, 1, .35, .1, 0]   # E-Ink-Vollrefresh-Flackern
    return np.full_like(g.nx, seq[min(len(seq) - 1, round(p / 2 * (len(seq) - 1)))])


TRANSITIONS = {
    "wipe_left":    lambda g, p: cover(g.nx, p),
    "wipe_up":      lambda g, p: cover(1 - g.ny, p),
    "wipe_diag":    lambda g, p: cover((g.nx + g.ny) / 2, p),
    "iris":         lambda g, p: cover(g.R, p),
    "iris_spark":   lambda g, p: cover(g.star(), p, 0.2),
    "spark_spin":   lambda g, p: cover(g.star(90 * p), p, 0.2),
    "diamond":      lambda g, p: cover(_norm(np.abs(g.cx) + np.abs(g.cy)), p),
    "clock":        lambda g, p: cover(g.A, p, 0.12),
    "spiral":       lambda g, p: cover(_norm(g.A + 2.5 * g.R), p, 0.15),
    "thirds":       _thirds,
    "blinds":       lambda g, p: cover(0.75 * ((g.L * 8) % 1) + 0.25 * np.floor(g.L * 8) / 8, p, 0.15),
    "tiles":        lambda g, p: cover(g.tiles(6), p, 0.08),
    "dissolve":     lambda g, p: cover(g.H, p, 0.05),
    "ripple":       _ripple(lambda g: g.R),
    "ripple_spark": _ripple(lambda g: g.star()),
    "eink_flash":   _flash,
}

ACCENTS = {                           # One-Shots fuer Beats, p = 0..1, nie voll deckend
    "ring_pulse": lambda g, p: np.exp(-((g.R - 1.2 * p ** 0.7) / 0.04) ** 2) * (1 - p),
    "spark_pop":  lambda g, p: ss((0.25 + 0.55 * ss(p * 2.5) - g.star()) / 0.08) * (1 - ss((p - 0.3) / 0.7)),
    "flash":      lambda g, p: np.full_like(g.nx, (1 - p) ** 2),
    "burst":      lambda g, p: ((g.H < 0.12) * np.exp(-((g.R - p * (0.4 + 0.8 * g.tiles(40))) / 0.05) ** 2)) * (1 - p),
}


def _static(g, t):
    return (np.random.default_rng(int(t * 1000)).random(g.nx.shape) < 0.45).astype(np.float32) * 0.9


LOOPS = {                             # t = 0..1, nahtlos
    "rings_flow":  lambda g, t: (0.5 + 0.5 * np.cos(2 * np.pi * (6 * g.R - t))) * (1 - 0.6 * g.R),
    "spark_flow":  lambda g, t: (0.5 + 0.5 * np.cos(2 * np.pi * (5 * g.star() - t))) * (1 - 0.5 * g.R),
    "spark_rotate": lambda g, t: np.clip((0.75 - g.star(60 * t)) * 2.2, 0, 1),        # 6 Zacken -> 60 Grad = Loop
    "breathe":     lambda g, t: np.clip(1.05 - 1.15 * g.R + 0.22 * np.sin(2 * np.pi * t), 0, 1),
    "plasma":      lambda g, t: (np.sin(2 * np.pi * (2 * g.nx + t)) + np.sin(2 * np.pi * (3 * g.ny - t))
                                 + np.sin(2 * np.pi * (4 * g.R - 2 * t))) / 6 + 0.5,
    "sparkle":     lambda g, t: (g.tiles(40) < 0.3) * np.clip(np.cos(2 * np.pi * (t + g.H)), 0, 1) ** 10,
    "stripes":     lambda g, t: 0.5 + 0.5 * np.sin(2 * np.pi * (3 * (g.cx + g.cy) - t)),
    "scan":        lambda g, t: np.clip(0.12 + np.exp(-(((g.ny - t) % 1 - 0.5) / 0.07) ** 2), 0, 1),
    "tiles_twinkle": lambda g, t: (0.5 + 0.5 * np.cos(2 * np.pi * (t + g.tiles(8)))) ** 2,
    "waves":       lambda g, t: 0.5 + 0.5 * np.sin(2 * np.pi * (4 * g.ny + 0.12 * np.sin(2 * np.pi * (2 * g.nx + t)) - t)),
    "gradient":    lambda g, t: 0.5 + 0.5 * np.sin(2 * np.pi * (g.nx + 0.3 * g.ny - t)),
    "static":      _static,
}

KINDS = {"transition": (TRANSITIONS, 21, 2.0), "accent": (ACCENTS, 15, 1.0), "loop": (LOOPS, 50, 1.0)}


def kind_of(name, prefer=None):
    for k, (table, _, _) in KINDS.items():
        if name in table and (prefer is None or k == prefer):
            return k
    raise KeyError(name)


# ---------------------------------------------------------------- Stile: Feld -> Alpha (uint8, volle Aufloesung)

def _bayer(n=8):
    m = np.array([[0]])
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / (n * n)


BAYER = _bayer(8)


class Style:
    def __init__(self, style, W, H):
        self.style, self.W, self.H = style, W, H
        unit = max(3, round(8 * min(W, H) / 1080))
        self.cell = {"dots": unit, "fine": max(2, unit // 2), "halftone": unit * 2, "solid": 4}[style]
        gw, gh = math.ceil(W / self.cell), math.ceil(H / self.cell)
        self.grid = Grid(gw, gh)
        if style in ("dots", "fine"):
            self.thr = np.tile(BAYER, (gh // 8 + 1, gw // 8 + 1))[:gh, :gw]
        if style == "halftone":
            y, x = np.mgrid[0:H, 0:W]
            c = self.cell
            self.d = np.hypot(x % c - c / 2 + 0.5, y % c - c / 2 + 0.5)
            self.iy, self.ix = y // c, x // c

    def render(self, v):
        v = np.clip(v, 0, 1)
        c, W, H = self.cell, self.W, self.H
        if self.style in ("dots", "fine"):
            a = ((v > self.thr) * 255).astype(np.uint8)
            return np.repeat(np.repeat(a, c, 0), c, 1)[:H, :W]
        if self.style == "halftone":
            r = 0.72 * c * np.sqrt(v)[self.iy, self.ix]                     # Flaeche ~ v, bei 1 voll
            return (np.clip(r - self.d + 0.5, 0, 1) * 255).astype(np.uint8)
        big = np.asarray(Image.fromarray(v.astype(np.float32), "F").resize((W, H), Image.BILINEAR))
        return (np.clip((big - 0.5) / 0.03 + 0.5, 0, 1) * 255).astype(np.uint8)    # solid: glatte Kante


def frames(name, kind, style):
    table, n, span = KINDS[kind]
    fn = table[name]
    for f in range(n):
        p = span * f / (n - 1) if kind != "loop" else f / n
        yield style.render(fn(style.grid, p))


# ---------------------------------------------------------------- Ausgabe

def _rgb(hexcol):
    return np.array([int(hexcol[i:i + 2], 16) for i in (1, 3, 5)], np.float32)


def encode(path, W, H, fmt, alphas, palette="mono"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    src = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo",
           "-s", f"{W}x{H}", "-r", str(FPS)]
    if fmt == "mov":                  # weiss + Alpha: in jedem NLE umfaerbbar, Difference/Screen/Normal
        cmd = src + ["-pix_fmt", "rgba", "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444",
                     "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", path]
    elif fmt == "mp4":                # fertig eingefaerbt, laeuft in PowerPoint/Keynote/Web
        cmd = src + ["-pix_fmt", "rgb24", "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "slow",
                     "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-tag:v", "avc1", path]
    else:                             # gif
        cmd = src + ["-pix_fmt", "rgb24", "-i", "-", "-vf",
                     "split[a][b];[a]palettegen=max_colors=32:reserve_transparent=0[p];[b][p]paletteuse=dither=none",
                     "-loop", "0", path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    fg, bg = (_rgb(c) for c in PALETTES[palette])
    for a in alphas:
        if fmt == "mov":
            px = np.empty((H, W, 4), np.uint8)
            px[..., :3] = 255
            px[..., 3] = a
        else:
            k = (a.astype(np.float32) / 255)[..., None]
            px = (bg + (fg - bg) * k).astype(np.uint8)
        proc.stdin.write(px.tobytes())
    proc.stdin.close()
    assert proc.wait() == 0, path


def job(spec):
    name, kind, aspect, style, palette, fmt = spec
    W, H = ASPECTS[aspect]
    sub = {"mov": f"mov_alpha/{aspect}/{kind}", "mp4": f"mp4/{aspect}/{palette}",
           "gif": f"gif/{style}" if palette == "mono" else f"gif/color_{palette}"}[fmt]
    path = f"{ROOT}/{sub}/{name}__{style}.{fmt}" if fmt != "gif" else f"{ROOT}/{sub}/{name}.gif"
    encode(path, W, H, fmt, frames(name, kind, Style(style, W, H)), palette)
    return path


def default_jobs():
    everything = [(n, k) for k, (t, _, _) in KINDS.items() for n in t]
    loops = [(n, "loop") for n in LOOPS]
    jobs = [(n, k, a, s, "mono", "mov") for n, k in everything for a in ("9x16", "16x9")
            for s in ("dots", "halftone", "solid")]
    jobs += [(n, k, a, s, pal, "mp4") for n, k in loops for a in ("16x9", "9x16", "1x1")
             for pal in ("mono", "ink", "spark", "navy") for s in ("dots", "halftone")]
    jobs += [(n, k, "gif", s, "mono", "gif") for n, k in everything for s in ("dots", "halftone", "solid")]
    jobs += [(n, k, "gif", "dots", pal, "gif") for n, k in everything for pal in ("spark", "red", "yellow", "ink")]
    return jobs


# ---------------------------------------------------------------- Selbsttest

def check():
    for aspect in ("9x16", "16x9"):
        st = Style("dots", *ASPECTS[aspect])
        for name in TRANSITIONS:
            if name.startswith("ripple") or name == "eink_flash":
                continue
            fr = [st.render(TRANSITIONS[name](st.grid, p)).mean() / 255 for p in (0.0, 1.0, 2.0)]
            assert fr[0] < 0.02 and fr[1] > 0.97 and fr[2] < 0.02, (name, aspect, fr)
        for name, fn in LOOPS.items():
            if name == "static":
                continue
            assert (np.abs(fn(st.grid, 0.0) - fn(st.grid, 1.0)) > 1e-2).mean() < 1e-3, (name, "Loop nicht nahtlos")
    print("check ok")


if __name__ == "__main__":
    check()
    if sys.argv[1:2] == ["check"]:
        sys.exit()
    if sys.argv[1:2] == ["one"]:      # one <name> <aspect> <style> <palette> <fmt> [kind]
        name, aspect, style, palette, fmt = sys.argv[2:7]
        print(job((name, kind_of(name, (sys.argv[7:8] or [None])[0]), aspect, style, palette, fmt)))
        sys.exit()
    jobs = default_jobs()
    with Pool(max(1, os.cpu_count() - 2)) as pool:
        for i, path in enumerate(pool.imap_unordered(job, jobs), 1):
            if i % 50 == 0 or i == len(jobs):
                print(f"{i}/{len(jobs)}", flush=True)
