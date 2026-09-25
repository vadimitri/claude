#!/usr/bin/env python3
"""MAKER NIGHT Teaser: 14,5 s, Lila bis Lavendel, Spark-Nest-Tunnel mit Grain-Dither.

Dramaturgie: Funke zuendet -> grainy Stern blueht auf -> Nest dreht sich ein -> Flug durch den
Nest-Tunnel -> Titel "MAKER NIGHT / is happening." -> alles faellt in den Funken zurueck.
Jedes Bild ist ein Feld v in [0, 1] auf einem 2-px-Raster, das per Blue-Noise-Dither auf eine
8-Farben-Palette gemappt wird. Exakte Stufen (k/7) bleiben flaechig, alles dazwischen wird Korn.

  uv run --with numpy --with pillow --with scipy python makernight.py 16x9            # MP4 + ProRes
  uv run --with numpy --with pillow --with scipy python makernight.py 9x16
  uv run --with numpy --with pillow --with scipy python makernight.py 16x9 preview    # Stills
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

from motionpack import Grid
from stills import _DEG, _PROF

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "makernight")
FPS, DUR, CELL = 30, 14.5, 2
SIZES = {"16x9": (1920, 1080), "9x16": (1080, 1920)}
FONTS = os.path.expanduser("~/Library/Fonts")

# dunkel -> hell: Fast-Schwarz, Aubergine, Dunkellila, Royal, Amethyst, Lavendel, Flieder, Weisslavendel
PAL = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in
                ("#09070E", "#150E26", "#28174A", "#432379", "#6A3FB5", "#9B7BE3", "#C9B8F7", "#F1ECFF")],
               np.float32)
N = len(PAL) - 1
LVL = 1 / N                                    # eine Palettenstufe im Feld

COPY = {"label": "SPARK PRESENTS", "title": "MAKER NIGHT", "sub": "is happening.",
        "tl": "SPARK", "tr": "2026", "bl": "HPI POTSDAM"}


# ---------------------------------------------------------------- Zeit

def sm(a, b, t):
    x = min(max((t - a) / (b - a), 0.0), 1.0)
    return x * x * (3 - 2 * x)


def clip01(x):
    return min(max(x, 0.0), 1.0)


def out_expo(x):
    return 1 - 2 ** (-10 * x) if x < 1 else 1.0


def out_back(x, s=1.4):
    x -= 1
    return 1 + x * x * ((s + 1) * x + s)


# Tunnel-Phase und Drehung als Integral eines Geschwindigkeitsprofils: Gas geben, gleiten, bremsen
_TT = np.arange(0, DUR + 0.01, 1 / 600)
_V = np.array([0.05 + 2.95 * sm(5.0, 6.5, t) - 2.88 * sm(7.2, 8.4, t) for t in _TT])
_W = np.array([10 + 70 * sm(5.0, 6.5, t) - 74 * sm(7.2, 8.4, t) for t in _TT])
_PHASE, _DRIFT = np.cumsum(_V) / 600, np.cumsum(_W) / 600


def phase(t):
    return float(np.interp(t, _TT, _PHASE)), float(np.interp(t, _TT, _DRIFT)), float(np.interp(t, _TT, _V))


# ---------------------------------------------------------------- Felder

class G:
    """Raster plus Winkel/Radius, einmal pro Prozess."""
    def __init__(self, W, H):
        self.gw, self.gh = W // CELL, H // CELL
        g = Grid(self.gw, self.gh)
        self.cx, self.cy, self.R = g.cx, g.cy, g.R
        self.r = np.hypot(g.cx, g.cy)
        self.ang = np.degrees(np.arctan2(g.cy, g.cx)) % 360
        self.rmax = float(self.r.max())
        self.px = 1 / min(self.gw, self.gh)


def sd(g, size, rot=0.0):
    """< 1 innerhalb eines Spark-Sterns mit Spitzenradius size."""
    return g.r / (np.interp((g.ang - rot) % 360, _DEG, _PROF) * size + 1e-9)


PMIN = float(_PROF.min())


def nest(g, ph, drift, scale, spin, base=0.5, ratio=0.78):
    """Unendliches Nest: Stern k hat Groesse base*ratio^(k-ph), jeder zweite dreht gegenlaeufig, XOR-Paritaet.
    Sterne, die den ganzen Frame decken, zaehlen nur als Konstante: Paritaet bleibt beim Zoom stetig."""
    cnt = np.zeros(g.r.shape, np.int16)
    smin = np.full(g.r.shape, 9.0, np.float32)
    for k in range(0, int(ph) + 24):
        s = base * ratio ** (k - ph) * scale
        if s < 0.012:
            break
        if s * PMIN > g.rmax:
            cnt += 1
            continue
        sign = 1 if k % 2 == 0 else -1
        inside = sd(g, s, 30 * (k - ph) + sign * (drift + spin)) < 1
        cnt += inside
        smin = np.where(inside, s, smin)
    on = (cnt % 2).astype(bool)
    near = np.clip(1 - smin / 0.62, 0, 1)
    return np.where(on, 0.52 + 0.46 * near, 0.07 + 0.13 * near)


def grainy(g, size, rot=0.0):
    return np.clip((1.15 - sd(g, size, rot)) / 0.6, 0, 1) ** 0.9


def ring(g, size, width=1.3):
    """Sternkontur, width Rasterzellen dick (grob: d-Abstand * Radius)."""
    return (np.abs(sd(g, size) - 1) * g.r < width * g.px).astype(np.float32)


def field(g, t):
    ph, drift, vel = phase(t)
    v = (LVL * 0.95) * (1 - g.R) ** 1.4 * sm(0.0, 0.6, t) * (1 - sm(14.1, 14.5, t))   # Hintergrund-Glimmen

    # A: Funke und grainy Stern
    if 0.3 < t < 0.75:
        flick = 1.0 if (int(t * 30) % 3) else 0.4
        v = np.maximum(v, grainy(g, 0.03 * sm(0.3, 0.5, t), 0) * flick)
    if 0.7 <= t < 2.8:
        e = out_expo(clip01((t - 0.7) / 1.1))
        size = 0.34 * e + 0.25 * sm(1.9, 2.8, t)
        v = np.maximum(v, grainy(g, size, -90 * (1 - e)) * (1 - sm(1.9, 2.7, t)))
        for j in range(3):                               # Zuend-Echo
            x = clip01((t - 0.72 - 0.14 * j) / 1.2)
            if 0 < x < 1:
                v = np.maximum(v, ring(g, 0.1 + 1.1 * out_expo(x), 1.6 - 0.3 * j) * 0.62 * (1 - x))

    # B/C/D/E: Nest eindrehen, Tunnel, dimmen hinter dem Titel, Kollaps
    if t > 1.9:
        e = out_back(clip01((t - 1.9) / 1.2))
        spin = 110 * (1 - min(1.0, out_expo(clip01((t - 1.9) / 1.4))))
        col = 1 - sm(13.3, 14.05, t) ** 2
        col = col * col * (3 - 2 * col) if col < 1 else 1.0
        spin += 220 * sm(13.3, 14.05, t) ** 2
        if col > 0.01:
            bright = 1 - 0.6 * sm(7.9, 8.9, t)
            v = np.maximum(v, nest(g, ph, drift, e * col, spin) * bright)

    # Maker-Raster hinter dem Titel, exakt eine Palettenstufe -> flaechige Linien
    gl = sm(8.6, 9.6, t) * (1 - sm(13.2, 13.6, t))
    if gl > 0:
        n = 10
        fx = np.abs((g.cx * n + 0.5) % 1 - 0.5) / n
        fy = np.abs((g.cy * n + 0.5) % 1 - 0.5) / n
        lines = ((np.minimum(fx, fy) < 0.6 * g.px) & (g.R < 0.25 + 0.75 * gl)).astype(np.float32)
        v = np.maximum(v, lines * LVL)

    # E: finaler Funke
    if 13.85 < t < 14.4:
        x = clip01((t - 13.85) / 0.55)
        v = np.maximum(v, grainy(g, 0.2 * math.sin(math.pi * x) ** 0.7, 360 * x))
        v = np.maximum(v, ring(g, 0.15 + 1.4 * out_expo(x), 1.4) * 0.7 * (1 - x))

    # Bloom (mehr bei Tunnelspeed), Vignette
    bloom = 0.5 + 0.25 * min(vel / 3, 1)
    v = v + bloom * gaussian_filter(v, 9) * 0.6
    return np.clip(v * (1 - 0.3 * g.R ** 2), 0, 1)


# ---------------------------------------------------------------- Dither

def blue_noise(n=128, seed=3):
    """Hochpass-gefiltertes Weissrauschen, rangtransformiert: gleichmaessiges Korn ohne Bayer-Muster."""
    w = np.random.default_rng(seed).random((n, n))
    f = np.hypot(*np.meshgrid(np.fft.fftfreq(n), np.fft.fftfreq(n)))
    w = np.real(np.fft.ifft2(np.fft.fft2(w) * f ** 1.5))
    return (np.argsort(np.argsort(w.ravel())).reshape(n, n) + 0.5) / (n * n)


def dither(v, thr):
    x = v * N
    lo = np.floor(x)
    idx = np.clip(lo + (x - lo > thr), 0, N).astype(np.int8)
    return PAL[idx]


# ---------------------------------------------------------------- Typo

def font(name, size, var=None):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    if var:
        f.set_variation_by_name(var)
    return f


def draw_text(d, s, f, x, y, track=0.0, align="l"):
    """Baseline bei y, Laufweite track (in px), align l/c/r. Gibt (x0, x1) zurueck."""
    ws = [f.getlength(c) for c in s]
    total = sum(ws) + track * (len(s) - 1)
    x0 = x - {"l": 0, "c": total / 2, "r": total}[align]
    cx = x0
    for c, w in zip(s, ws):
        d.text((cx, y), c, font=f, fill=255, anchor="ls")
        cx += w + track
    return x0, x0 + total


def cap(f):
    return -f.getbbox("H", anchor="ls")[1]


class Type:
    """Statische Textmasken + Layout, einmal pro Prozess."""
    def __init__(self, W, H):
        self.W, self.H = W, H
        portrait = H > W
        lines = COPY["title"].split() if portrait else [COPY["title"]]
        title = font("ClashDisplay-Variable.ttf", 200, "Semibold")
        widest = max(title.getlength(s) - 0.02 * 200 * (len(s) - 1) for s in lines)
        size = int(200 * (0.84 if portrait else 0.7) * W / widest)
        title = font("ClashDisplay-Variable.ttf", size, "Semibold")
        c = cap(title)
        gap = c * 1.22
        yc = H * (0.45 if portrait else 0.47)
        base0 = yc - (len(lines) - 1) * gap / 2 + c / 2
        im = Image.new("L", (W, H))
        d = ImageDraw.Draw(im)
        x0s = []
        for i, s in enumerate(lines):
            x0s.append(draw_text(d, s, title, W / 2, base0 + i * gap, -0.02 * size, "c")[0])
        self.title = np.asarray(im, np.float32) / 255
        self.left = min(x0s)
        cols = np.nonzero(self.title.max(0))[0]
        self.tx0, self.tx1 = cols.min(), cols.max()

        self.mono = font("DepartureMono-Regular.otf", 44 if not portrait else 55)
        self.small = font("DepartureMono-Regular.otf", 22)
        self.sub_y = base0 + (len(lines) - 1) * gap + c * 0.55 + cap(self.mono) + 18
        im = Image.new("L", (W, H))
        draw_text(ImageDraw.Draw(im), COPY["label"], self.small, self.left + 4, base0 - c - 34, 3)
        self.label = np.asarray(im, np.float32) / 255

        m = 48 if not portrait else 56
        im = Image.new("L", (W, H))
        d = ImageDraw.Draw(im)
        L = 26
        for sx, sy in ((m, m), (W - m, m), (m, H - m), (W - m, H - m)):   # Eckwinkel
            dx, dy = (1 if sx < W / 2 else -1), (1 if sy < H / 2 else -1)
            d.line([(sx, sy + dy * L), (sx, sy), (sx + dx * L, sy)], fill=255, width=2)
        ty, by = m + 26 + cap(self.small), H - m - 22
        draw_text(d, COPY["tl"], self.small, m + 36, ty - 26 + 2, 3)
        draw_text(d, COPY["tr"], self.small, W - m - 36, ty - 26 + 2, 3, "r")
        draw_text(d, COPY["bl"], self.small, m + 36, by + 2, 3)
        self.hud = np.asarray(im, np.float32) / 255
        self.m, self.by = m, by

    def dynamic(self, t, frame):
        """Getippte Zeile mit Block-Cursor + Timecode, pro Frame."""
        im = Image.new("L", (self.W, self.H))
        d = ImageDraw.Draw(im)
        n = int(len(COPY["sub"]) * clip01((t - 9.3) / 1.0))
        x1 = draw_text(d, COPY["sub"][:n], self.mono, self.left + 4, self.sub_y)[1] if n else self.left + 4
        if 9.1 < t < 13.25 and (n < len(COPY["sub"]) or int(t * 2.2) % 2 == 0):
            ch = cap(self.mono)
            d.rectangle([x1 + 6, self.sub_y - ch, x1 + 6 + ch * 0.62, self.sub_y], fill=255)
        s = frame % FPS
        tc = f"MN26  {int(t) // 60:02d}:{int(t) % 60:02d}:{s:02d}"
        draw_text(d, tc, self.small, self.W - self.m - 36, self.by + 2, 3, "r")
        sub = np.asarray(im, np.float32) / 255
        return sub


# ---------------------------------------------------------------- Frame

_P = {}


def init(W, H):
    _P["g"] = G(W, H)
    _P["type"] = Type(W, H)
    _P["bn"] = blue_noise()


def up(a):
    return np.repeat(np.repeat(a, CELL, 0), CELL, 1)


def render(frame):
    g, ty, bn = _P["g"], _P["type"], _P["bn"]
    t = frame / FPS
    # Korn "kocht" mit 15 fps: Schwelle alle 2 Frames verschoben, stehende Flaechen flimmern nicht nervoes
    rng = np.random.default_rng(frame // 2)
    oy, ox = rng.integers(0, bn.shape[0], 2)
    tile = np.roll(bn, (oy, ox), (0, 1))
    thr = np.tile(tile, (g.gh // bn.shape[0] + 1, g.gw // bn.shape[1] + 1))[:g.gh, :g.gw]
    rgb = up(dither(field(g, t), thr))

    still = np.tile(bn, (g.gh // bn.shape[0] + 1, g.gw // bn.shape[1] + 1))[:g.gh, :g.gw]
    noise = up(still)
    xn = np.clip((np.arange(ty.W) - ty.tx0) / max(ty.tx1 - ty.tx0, 1), 0, 1)[None, :]
    gone = noise > 1 - sm(13.2, 13.65, t)                           # Grain-Dissolve raus
    p = sm(8.15, 9.05, t) * 1.45
    reveal = ((xn * 0.6 + noise * 0.4) < p) & ~gone                 # Grain-Wipe rein, links nach rechts
    front = ((xn * 0.6 + noise * 0.4) < p + 0.05) & ~reveal & (0 < p < 1.4) & ~gone
    layers = [(ty.title * reveal, PAL[7]), (ty.title * front, PAL[5]),
              (ty.label * (noise < sm(8.7, 9.3, t)) * ~gone, PAL[5]),
              (ty.dynamic(t, frame) * (t > 9.0) * ~gone, PAL[6]),
              (ty.hud * (noise < sm(9.0, 9.8, t)) * ~gone, PAL[4])]
    for a, c in layers:
        rgb += a[..., None] * (c - rgb)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def main():
    fmt = sys.argv[1] if len(sys.argv) > 1 else "16x9"
    W, H = SIZES[fmt]
    os.makedirs(OUT, exist_ok=True)
    total = int(DUR * FPS)
    if "preview" in sys.argv:
        times = [0.5, 1.4, 2.4, 3.8, 5.8, 6.8, 7.8, 8.6, 10.5, 13.9]
        init(W, H)
        for tt in times:
            Image.fromarray(render(int(tt * FPS))).save(os.path.join(OUT, f"preview_{fmt}_{tt:04.1f}.png"))
        return
    mp4 = os.path.join(OUT, f"makernight_{fmt}.mp4")
    mov = os.path.join(OUT, f"makernight_{fmt}_prores.mov")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", mp4,
                           "-c:v", "prores_ks", "-profile:v", "3", mov], stdin=subprocess.PIPE)
    with Pool(initializer=init, initargs=(W, H)) as pool:
        for i, fr in enumerate(pool.imap(render, range(total), chunksize=4)):
            ff.stdin.write(fr.tobytes())
            if i % 60 == 0:
                print(f"{fmt} {i}/{total}", flush=True)
    ff.stdin.close()
    ff.wait()
    print(mp4)


if __name__ == "__main__":
    main()
