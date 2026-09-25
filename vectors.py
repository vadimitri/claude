#!/usr/bin/env python3
"""SPARK Vectors: SVG-Assets fuer Figma. Alles echte Vektoren auf Basis des Master-Sterns (logo/spark_filled.svg).

  uv run --with numpy --with pillow python vectors.py        # alles nach vectors/ + vectors.html

vectors/<format>/templates  fertige Plakat-/Post-Layouts mit editierbarem Text (Clash Display + Satoshi)
vectors/<format>/solid      Vektor-Designs: Hintergruende, Heroes, Rahmen
vectors/<format>/dither     alle Stills-Designs als Pixel-Quadrate (ein Pfad pro Datei)
vectors/<format>/halftone   dasselbe als Rasterpunkte
vectors/_elements/...       formatfrei: icons, badges, corners, bands, dividers, patterns (nahtlos)
"""
import math
import os
import re
from functools import lru_cache
from xml.sax.saxutils import escape

import numpy as np
from PIL import ImageFont

from motionpack import BAYER, Grid, ss
from stills import DESIGNS as FIELDS, THIN, h, star_d

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = f"{ROOT}/vectors"
FORMATS = {"poster_a3": (842, 1191), "16x9": (1920, 1080), "9x16": (1080, 1920), "4x5": (1080, 1350), "1x1": (1080, 1080)}
INK = "#141414"
C = {"navy": "#1A3A6E", "paper": "#F2EFE6", "ink": INK, "yellow": "#FFF000", "blue": "#93BEFF",
     "violet": "#2A00B8", "orange": "#FF5A1F", "white": "#FFFFFF", "black": "#0B0B0B"}
FONT = {"display": ("ClashDisplay-Variable.ttf", "'Clash Display Variable', 'Clash Display', sans-serif"),
        "text": ("Satoshi-Variable.ttf", "'Satoshi Variable', 'Satoshi', sans-serif")}

# ---------------------------------------------------------------- Master-Stern (Spitze oben, Spitzenradius 1)

MASTER = ("M434.5 0C434.5 0 437.017 242.366 547.386 306.06C657.756 369.754 869 250.75 869 250.75C869 250.75 660.273 374.112 "
          "660.273 501.5C660.273 628.888 869 752.25 869 752.25C869 752.25 657.756 633.246 547.386 696.94C437.017 760.634 434.5 "
          "1003 434.5 1003C434.5 1003 431.983 760.634 321.614 696.94C211.244 633.246 0 752.25 0 752.25C0 752.25 208.727 628.888 "
          "208.727 501.5C208.727 374.112 0 250.75 0 250.75C0 250.75 211.244 369.754 321.614 306.06C431.983 242.366 434.5 0 434.5 0Z")
STAR = (np.array(re.findall(r"-?[\d.]+", MASTER), float).reshape(-1, 2) - (434.5, 501.5)) / 501.5


def f(x):
    return f"{x:.1f}".rstrip("0").rstrip(".") if abs(x - round(x)) > 0.05 else str(int(round(x)))


def star(x, y, r, rot=0.0):
    """Pfad-String des Spark-Sterns, Mitte (x, y), Spitzenradius r, rot in Grad."""
    if r < 0.5:
        return ""
    t = math.radians(rot)
    P = STAR @ np.array([[math.cos(t), math.sin(t)], [-math.sin(t), math.cos(t)]]) * r + (x, y)
    return (f"M{f(P[0,0])} {f(P[0,1])}" + "".join("C" + " ".join(f"{f(a)} {f(b)}" for a, b in P[i:i + 3])
                                                 for i in range(1, len(P), 3)) + "Z")


def circle(x, y, r):
    return f"M{f(x - r)} {f(y)}a{f(r)} {f(r)} 0 1 0 {f(2 * r)} 0a{f(r)} {f(r)} 0 1 0 {f(-2 * r)} 0z" if r > 0.3 else ""


def rect(x, y, w, h_):
    return f"M{f(x)} {f(y)}h{f(w)}v{f(h_)}h{f(-w)}z"


def poly(pts):
    return "M" + "L".join(f"{f(a)} {f(b)}" for a, b in pts) + "Z"


def path(d, fill=INK, evenodd=False, opacity=None):
    if not d:
        return ""
    return (f'<path d="{d}" fill="{fill}"' + (' fill-rule="evenodd"' if evenodd else "")
            + (f' fill-opacity="{opacity}"' if opacity is not None else "") + "/>")


def stroke(d, w, col=INK):
    return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{f(w) if w >= 1 else round(w, 2)}" stroke-linejoin="round"/>' if d else ""


def svg(W, H, body, bg=None, clip=True):
    bgr = f'<rect width="{W}" height="{H}" fill="{bg}"/>' if bg else ""
    if clip:
        body = f'<clipPath id="frame"><rect width="{W}" height="{H}"/></clipPath><g clip-path="url(#frame)">{body}</g>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">'
            f"{bgr}{body}</svg>")


def write(rel, content):
    p = f"{OUT}/{rel}.svg"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(content)


# ---------------------------------------------------------------- Leinwand

class Cv:
    """W x H, u = kurze Seite. Designs rechnen in u-Einheiten um die Mitte (wie stills.py)."""
    def __init__(self, W, H, col=INK):
        self.W, self.H, self.u, self.col = W, H, min(W, H), col
        self.ex, self.ey = W / 2 / self.u, H / 2 / self.u          # halbe Ausdehnung in u
        self.portrait = H > W

    def at(self, x, y):
        return self.W / 2 + x * self.u, self.H / 2 + y * self.u

    def star(self, x, y, r, rot=0.0):
        return star(*self.at(x, y), r * self.u, rot)

    def tiles(self, n, brick=False):
        """Kachelmitten: n Kacheln ueber die kurze Seite. -> Liste (px, py, xc, yc, ix, iy, L), t = Kachelgroesse px."""
        t = self.u / n
        out = []
        for iy in range(-1, math.ceil(self.H / t) + 1):
            off = 0.5 * (iy % 2) if brick else 0
            for ix in range(-1, math.ceil(self.W / t) + 1):
                px, py = (ix + 0.5 + off) * t, (iy + 0.5) * t
                xc, yc = (px - self.W / 2) / self.u, (py - self.H / 2) / self.u
                L = (py / self.H) if self.portrait else (px / self.W)
                dc = math.hypot(xc - self.ex, yc - self.ey) / (2 * min(self.ex, self.ey))
                out.append((px, py, xc, yc, ix, iy, min(max(L, 0), 1), dc))
        return out, t


def hsh(ix, iy, salt=0):
    return float(h(np.float64(ix), np.float64(iy), salt))


# ---------------------------------------------------------------- Vektor-Designs (solid)

def d_echo(x=0.0, y=0.0, size=0.3, rings=7, step=1.28, fill_core=True):
    def g(cv):
        out = path(cv.star(x, y, size), cv.col) if fill_core else ""
        for k in range(1, rings + 1):
            out += stroke(cv.star(x, y, size * step ** k), cv.u * max(0.0025, 0.009 - 0.0009 * k), cv.col)
        return out
    return g


def d_contour(step=0.075, w=0.0035, bold=False):
    def g(cv):
        out, k = "", 1
        while step * k * 0.42 < math.hypot(cv.ex, cv.ey):
            ww = w * (1 + 2.5 * max(0, 1 - k / 6)) if bold else w
            out += stroke(cv.star(0, 0, step * k), cv.u * ww, cv.col)
            k += 1
        return out
    return g


def d_spiro(cv):
    return "".join(stroke(cv.star(0, 0, 0.46 * 0.93 ** k, 5 * k), cv.u * 0.003, cv.col) for k in range(14))


def d_evenodd(parts):
    return lambda cv: path("".join(cv.star(*p) for p in parts), cv.col, evenodd=True)


def wedges(cv, x, y, r1, r2, n, half_deg, start=-90.0, every=None):
    d = ""
    for k in range(n):
        a = math.radians(start + 360 * k / n)
        rr2 = r2[k % len(r2)] if isinstance(r2, tuple) else r2
        hw = math.radians(half_deg)
        X, Y = cv.at(x, y)
        pts = [(X + r * cv.u * math.cos(a + s * hw), Y + r * cv.u * math.sin(a + s * hw))
               for r, s in ((r1, -1), (rr2, -1), (rr2, 1), (r1, 1))]
        d += poly(pts)
    return d


def d_burst(y=0.0, size=0.2):
    return lambda cv: path(cv.star(0, y, size) + wedges(cv, 0, y, size * 1.3, (size * 2.9, size * 1.9), 12, 2.6), cv.col)


def d_sunburst(cv):
    far = math.hypot(cv.ex, cv.ey) * 1.1
    return path(wedges(cv, 0, 0, 0.0, far, 24, 3.75) , cv.col) + path(cv.star(0, 0, 0.16), cv.col)


def d_orbit(cv):
    d = cv.star(0, 0, 0.16)
    for k in range(12):
        a = 2 * math.pi * k / 12 - math.pi / 2
        d += cv.star(0.34 * math.cos(a), 0.34 * math.sin(a), 0.06 if k % 2 == 0 else 0.034, 30 * (k % 2))
    return path(d, cv.col)


def d_ring(n=24, r=0.38):
    def g(cv):
        d = cv.star(0, 0, 0.2)
        for k in range(n):
            a = 2 * math.pi * k / n - math.pi / 2
            d += cv.star(r * math.cos(a), r * math.sin(a), 0.035, math.degrees(a) + 90)
        return path(d, cv.col)
    return g


def d_extrude(cv, n=9, size=0.34):
    o = 0.014
    back = "".join(stroke(cv.star(-o * k * 0.5 + o * n * 0.25, o * k - o * n * 0.4, size), cv.u * 0.003, cv.col)
                   for k in range(n, 0, -1))
    return back + path(cv.star(o * n * 0.25, -o * n * 0.4, size), cv.col)


def clipped(cv, clips, body, uid):
    """body je Clip-Polygon/-Rect einmal, optional verschoben: clips = [(clip_d, dx, dy)]."""
    out = ""
    for i, (cd, dx, dy) in enumerate(clips):
        cid = f"{uid}{i}"
        out += (f'<clipPath id="{cid}"><path d="{cd}"/></clipPath>'
                f'<g clip-path="url(#{cid})"><g transform="translate({f(dx)} {f(dy)})">{body}</g></g>')
    return out


def d_explode(cv, size=0.36, push=0.05):
    body = path(cv.star(0, 0, size), cv.col)
    X, Y = cv.at(0, 0)
    R = size * cv.u * 1.2
    clips = []
    for k in range(6):
        a0, a1 = math.radians(-120 + 60 * k), math.radians(-60 + 60 * k)
        am = (a0 + a1) / 2
        dx, dy = push * cv.u * math.cos(am), push * cv.u * math.sin(am)
        pts = [(X + dx, Y + dy), (X + dx + R * 2 * math.cos(a0), Y + dy + R * 2 * math.sin(a0)),
               (X + dx + R * 2 * math.cos(a1), Y + dy + R * 2 * math.sin(a1))]
        clips.append((poly(pts), dx, dy))
    return clipped(cv, clips, body, "ex")


def d_sliced(cv, size=0.42, n=14):
    X, Y = cv.at(0, 0)
    top, H = Y - size * cv.u, 2 * size * cv.u
    d, y = "", top
    for k in range(n):
        band = H / n
        gap = band * (0.08 + 0.55 * (k / (n - 1)) ** 1.5)       # Luecken wachsen nach unten, Retro-Sunset
        d += rect(X - cv.u, y, 2 * cv.u, band - gap)
        y += band
    return clipped(cv, [(d, 0, 0)], path(cv.star(0, 0, size), cv.col), "sl")


def d_glitch(cv, size=0.42, bands=34, seed=5):
    X, Y = cv.at(0, 0)
    top, bh = Y - size * cv.u, 2 * size * cv.u / bands
    body = path(cv.star(0, 0, size), cv.col)
    clips = []
    for k in range(bands):
        shift = (hsh(k, 1, seed + 4) - 0.5) * 0.35 * cv.u if hsh(k, 0, seed) < 0.4 else 0
        clips.append((rect(X - cv.u, top + k * bh - 0.3, 2 * cv.u, bh + 0.6), shift, 0))
    return clipped(cv, clips, body, "gl")


def d_trail(cv, n=7):
    d = ""
    for k in range(n):
        s = k / (n - 1)
        x = -cv.ex * 0.75 + s * cv.ex * 1.35
        y = cv.ey * 0.7 - s * cv.ey * 1.2
        d += cv.star(x, y, 0.035 * 1.55 ** k, 8 * k)
    return path(d, cv.col)


def d_pattern(n=6, brick=False, size=lambda t: 0.36, rot=lambda t: 0.0):
    def g(cv):
        ts, t = cv.tiles(n, brick)
        return path("".join(star(px, py, size(tt) * t, rot(tt)) for tt in ts for px, py in [tt[:2]]), cv.col)
    return g


def d_scatter(seed, n=45, lo=0.02, hi=0.13, dust=0):
    def g(cv):
        rng = np.random.default_rng(seed)
        d = ""
        for _ in range(int(n * 4 * cv.ex * cv.ey)):
            x, y = rng.uniform(-cv.ex, cv.ex), rng.uniform(-cv.ey, cv.ey)
            d += cv.star(x, y, lo * (hi / lo) ** rng.random() ** 1.8, rng.uniform(0, 60))
        for _ in range(int(dust * 4 * cv.ex * cv.ey)):
            d += circle(*cv.at(rng.uniform(-cv.ex, cv.ex), rng.uniform(-cv.ey, cv.ey)), cv.u * rng.uniform(0.002, 0.005))
        return path(d, cv.col)
    return g


def edge_tiles(tt, cv, t):
    px, py = tt[:2]
    return min(px, cv.W - px, py, cv.H - py) / t          # Abstand zum Rand in Kacheln


def d_frame_stars(n=11):
    def g(cv):
        ts, t = cv.tiles(n)
        d = ""
        for tt in ts:
            e = edge_tiles(tt, cv, t)
            s = 0.4 if 0 < e < 1 else 0.16 if 0 < e < 2 else 0
            d += star(tt[0], tt[1], s * t, 30 * ((tt[4] + tt[5]) % 2))
        return path(d, cv.col)
    return g


def tile_rects(n, rule, gap=0.07, brick=False):
    """rule(tt, cv, t) -> 0/1 (oder Deckkraft 0..1). Mehrere Deckkraft-Stufen -> je ein Pfad."""
    def g(cv):
        ts, t = cv.tiles(n, brick)
        levels = {}
        for tt in ts:
            v = float(rule(tt, cv, t))
            if v > 0.01:
                levels.setdefault(round(v, 2), []).append(rect(tt[0] - t / 2 + gap * t / 2, tt[1] - t / 2 + gap * t / 2,
                                                              t * (1 - gap), t * (1 - gap)))
        return "".join(path("".join(ds), cv.col, opacity=None if v >= 0.99 else v) for v, ds in sorted(levels.items()))
    return g


def pixel_star(n=16, size=0.44, dissolve=False):
    def rule(tt, cv, t):
        d = float(star_d(np.float64(tt[2]), np.float64(tt[3]), size))
        return d < 1 or (dissolve and hsh(tt[4], tt[5], 3) < 0.85 * math.exp(-(d - 1) * 2.2))
    return tile_rects(n, rule, 0.1)


def d_of_sparks(n=13):
    def g(cv):
        ts, t = cv.tiles(n)
        d = ""
        for px, py, xc, yc, *_ in ts:  # noqa
            big = float(star_d(np.float64(xc), np.float64(yc), 0.5))
            d += star(px, py, 0.48 * t * max(0, 1.3 - big) ** 0.5)
        return path(d, cv.col)
    return g


def d_graph(n=12, stars=False, w=0.0018):
    def g(cv):
        t = cv.u / n
        ox, oy = (cv.W / 2) % t, (cv.H / 2) % t
        d = "".join(f"M{f(ox + i * t)} 0V{cv.H}" for i in range(int(cv.W / t) + 1))
        d += "".join(f"M0 {f(oy + j * t)}H{cv.W}" for j in range(int(cv.H / t) + 1))
        out = stroke(d, cv.u * w, cv.col)
        if stars:
            s = "".join(star(ox + i * t, oy + j * t, 0.32 * t) for i in range(int(cv.W / t) + 1)
                        for j in range(int(cv.H / t) + 1) if hsh(i, j, 7) < 0.22)
            out += path(s, cv.col)
        return out
    return g


def d_quadtree(cv, levels=4, seed=0):
    d = []

    def rec(x, y, s, lvl):
        if lvl < levels and hsh(x * 7.1 + seed, y * 3.3, lvl) < 0.55:
            for dx in (0, s / 2):
                for dy in (0, s / 2):
                    rec(x + dx, y + dy, s / 2, lvl + 1)
        elif hsh(x * 1.7, y * 9.1 + seed, lvl + 50) < 0.45:
            gp = cv.u * 0.004
            d.append(rect(x + gp / 2, y + gp / 2, s - gp, s - gp))
    s0 = cv.u / 3
    for i in range(math.ceil(cv.W / s0)):
        for j in range(math.ceil(cv.H / s0)):
            rec(i * s0, j * s0, s0, 0)
    return path("".join(d), cv.col)


def d_dots(n=40, fn=lambda tt, cv: tt[6]):
    """Vektor-Halftone: Kreisraster, Radius aus fn (0..1)."""
    def g(cv):
        ts, t = cv.tiles(n)
        return path("".join(circle(tt[0], tt[1], 0.72 * t * math.sqrt(max(0, min(1, fn(tt, cv))))) for tt in ts), cv.col)
    return g


def d_checker_ramp(n=16):
    def g(cv):
        ts, t = cv.tiles(n)
        d = ""
        for px, py, xc, yc, ix, iy, L, _ in ts:
            if (ix + iy) % 2 == 0:
                s = t * L
                d += rect(px - s / 2, py - s / 2, s, s)
        return path(d, cv.col)
    return g


def d_stripes_ramp(n=24):
    def g(cv):
        t = cv.H / n
        return path("".join(rect(0, j * t, cv.W, t * (0.08 + 0.84 * (j + 0.5) / n)) for j in range(n)), cv.col)
    return g


def d_corner_brackets(cv):
    m, L, w = cv.u * 0.05, cv.u * 0.12, cv.u * 0.006
    d = ""
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        x = m if sx > 0 else cv.W - m
        y = m if sy > 0 else cv.H - m
        d += f"M{f(x)} {f(y + sy * L)}V{f(y)}H{f(x + sx * L)}"
    s = "".join(star(x, y, cv.u * 0.022) for x in (cv.W / 2,) for y in (m, cv.H - m))
    return stroke(d, w, cv.col) + path(s, cv.col)


def d_frame_line(cv):
    m = cv.u * 0.05
    s = "".join(star(x, y, cv.u * 0.028, 0) for x in (m, cv.W - m) for y in (m, cv.H - m))
    s += "".join(star(x, y, cv.u * 0.014) for x, y in ((cv.W / 2, m), (cv.W / 2, cv.H - m), (m, cv.H / 2), (cv.W - m, cv.H / 2)))
    return stroke(rect(m, m, cv.W - 2 * m, cv.H - 2 * m), cv.u * 0.003, cv.col) + path(s, cv.col)


def ramp(tt, cv, t, a=1.4, b=0.25):
    return hsh(tt[4], tt[5]) < ss(tt[6] * a - b)


SOLID = {
    "spark_mark":          lambda cv: path(cv.star(0, 0, 0.4), cv.col),
    "spark_outline":       lambda cv: stroke(cv.star(0, 0, 0.4), cv.u * 0.012, cv.col) + stroke(cv.star(0, 0, 0.32), cv.u * 0.004, cv.col),
    "spark_echo":          d_echo(),
    "spark_echo_corner":   lambda cv: d_echo(cv.ex, cv.ey, 0.45, 10, 1.3)(cv),
    "spark_echo_rise":     lambda cv: d_echo(0, cv.ey, 0.35, 10, 1.3)(cv),
    "spark_echo_side":     lambda cv: d_echo(-cv.ex, 0, 0.4, 10, 1.3)(cv),
    "spark_contour":       d_contour(),
    "spark_contour_bold":  d_contour(0.1, 0.004, bold=True),
    "spark_spiro":         d_spiro,
    "spark_nest":          d_evenodd([(0, 0, s, 30 * k) for k, s in enumerate((0.48, 0.38, 0.29, 0.2, 0.11))]),
    "spark_twelve":        d_evenodd([(0, 0, 0.42, 0), (0, 0, 0.42, 30)]),
    "spark_duo":           d_evenodd([(-0.11, 0, 0.34), (0.11, 0, 0.34)]),
    "spark_trio":          d_evenodd([(-0.14, 0.06, 0.28), (0.14, 0.06, 0.28), (0, -0.14, 0.28)]),
    "spark_burst":         d_burst(),
    "spark_burst_rise":    lambda cv: d_burst(cv.ey * 0.8, 0.22)(cv),
    "spark_sunburst":      d_sunburst,
    "spark_orbit":         d_orbit,
    "spark_ring":          d_ring(),
    "spark_extrude":       d_extrude,
    "spark_explode":       d_explode,
    "spark_sliced":        d_sliced,
    "spark_glitch":        d_glitch,
    "spark_trail":         d_trail,
    "spark_of_sparks":     d_of_sparks(),
    "spark_pixel":         pixel_star(),
    "spark_pixel_fine":    pixel_star(30),
    "spark_pixel_dissolve": pixel_star(22, dissolve=True),
    "spark_pattern":       d_pattern(),
    "spark_pattern_dense": d_pattern(12, True, rot=lambda t: 30 * (t[5] % 2)),
    "spark_pattern_mixed": d_pattern(8, True, size=lambda t: 0.42 if hsh(t[4], t[5]) < 0.5 else 0.17,
                                     rot=lambda t: 30 * (hsh(t[4], t[5], 1) < 0.5)),
    "spark_pattern_grow":  d_pattern(10, size=lambda t: 0.03 + 0.43 * t[6] ** 1.3),
    "spark_pattern_wave":  d_pattern(12, size=lambda t: 0.06 + 0.38 * (0.5 + 0.5 * math.cos(2 * math.pi * 2.2 * math.hypot(t[2], t[3])))),
    "spark_pattern_corner": d_pattern(11, size=lambda t: 0.46 * max(0.0, 1 - t[7] / 1.25) ** 1.3),
    "spark_pattern_hole":  d_pattern(12, size=lambda t: 0.44 * float(ss((star_d(np.float64(t[2]), np.float64(t[3]), 0.45) - 0.9) / 1.2))),
    "spark_scatter_1":     d_scatter(1),
    "spark_scatter_2":     d_scatter(2, 30, 0.03, 0.2),
    "spark_scatter_3":     d_scatter(3, 90, 0.015, 0.07),
    "spark_constellation": d_scatter(4, 25, 0.012, 0.05, dust=260),
    "spark_graph":         d_graph(stars=True),
    "frame_stars":         d_frame_stars(),
    "frame_tiles":         tile_rects(18, lambda tt, cv, t: hsh(tt[4], tt[5]) < ss(1 - edge_tiles(tt, cv, t) / (cv.u / t / 2) * 3.2)),
    "frame_brackets":      d_corner_brackets,
    "frame_line":          d_frame_line,
    "tiles_scatter":       tile_rects(8, lambda tt, cv, t: hsh(tt[4], tt[5]) < 0.35),
    "tiles_scatter_fine":  tile_rects(20, lambda tt, cv, t: hsh(tt[4], tt[5]) < 0.3),
    "tiles_scatter_micro": tile_rects(48, lambda tt, cv, t: hsh(tt[4], tt[5]) < 0.25),
    "tiles_ramp":          tile_rects(16, ramp),
    "tiles_ramp_fine":     tile_rects(36, ramp),
    "tiles_corner":        tile_rects(16, lambda tt, cv, t: hsh(tt[4], tt[5]) <
                                      ss(1.5 - 1.6 * math.hypot(tt[2] - cv.ex, tt[3] - cv.ey) / math.hypot(cv.ex, cv.ey))),
    "tiles_band":          tile_rects(24, lambda tt, cv, t: hsh(tt[4], tt[5]) < math.exp(-(tt[3] / 0.14) ** 2)),
    "tiles_center":        tile_rects(20, lambda tt, cv, t: hsh(tt[4], tt[5]) < ss(1.2 - 2.4 * math.hypot(tt[2], tt[3]))),
    "tiles_mosaic":        tile_rects(8, lambda tt, cv, t: math.floor(hsh(tt[4], tt[5]) * 5) / 4, 0.0),
    "tiles_mosaic_ramp":   tile_rects(14, lambda tt, cv, t: min(1, max(0, round((tt[6] + (hsh(tt[4], tt[5]) - 0.5) * 0.5) * 4) / 4)), 0.0),
    "tiles_quadtree":      d_quadtree,
    "tiles_checker_ramp":  d_checker_ramp(),
    "halftone_ramp":       d_dots(40),
    "halftone_radial":     d_dots(40, lambda tt, cv: 1.1 - 1.2 * math.hypot(tt[2], tt[3]) / math.hypot(cv.ex, cv.ey)),
    "halftone_spark":      d_dots(44, lambda tt, cv: 1.25 - float(star_d(np.float64(tt[2]), np.float64(tt[3]), 0.46))),
    "stripes_ramp":        d_stripes_ramp(),
    "graph_grid":          d_graph(),
    "graph_grid_fine":     d_graph(24, w=0.0012),
}


# ---------------------------------------------------------------- Stills-Felder als Vektor (dither / halftone)

def field(name, W, H, cell):
    g = Grid(math.ceil(W / cell), math.ceil(H / cell))
    return np.clip(FIELDS[name](g), 0, 1)


def dither_path(v, cell, ox=0.0, oy=0.0):
    thr = np.tile(BAYER, (v.shape[0] // 8 + 1, v.shape[1] // 8 + 1))[:v.shape[0], :v.shape[1]]
    m = (v > thr).astype(np.int8)
    d = []
    for j, row in enumerate(m):                     # ponytail: nur Zeilen-Runs zusammengefasst, reicht fuer Figma
        e = np.diff(np.concatenate([[0], row, [0]]))
        for a, b in zip(np.nonzero(e == 1)[0], np.nonzero(e == -1)[0]):
            d.append(rect(ox + a * cell, oy + j * cell, (b - a) * cell, cell))
    return "".join(d)


def halftone_path(v, cell, ox=0.0, oy=0.0):
    ys, xs = np.nonzero(v > 0.004)
    return "".join(circle(ox + (x + 0.5) * cell, oy + (y + 0.5) * cell, 0.72 * cell * math.sqrt(v[y, x])) for y, x in zip(ys, xs))


def dither_svg(name, W, H, n=96, col=INK):
    cell = max(4, round(min(W, H) / n))
    return svg(W, H, path(dither_path(field(name, W, H, cell), cell), col))


def halftone_svg(name, W, H, n=64, col=INK):
    cell = max(6, round(min(W, H) / n))
    return svg(W, H, path(halftone_path(field(name, W, H, cell), cell), col))


# ---------------------------------------------------------------- Text

@lru_cache(None)
def _font(kind, weight):
    ft = ImageFont.truetype(os.path.expanduser(f"~/Library/Fonts/{FONT[kind][0]}"), 200)
    ft.set_variation_by_axes([weight])
    return ft


def tw(s, kind="display", weight=600, size=100, ls=0.0):
    return _font(kind, weight).getlength(s) * size / 200 + ls * size * max(0, len(s) - 1)


def fit(s, width, kind="display", weight=600, ls=0.0):
    return width / tw(s, kind, weight, 1, ls)


def text(x, y, s, size, kind="display", weight=600, fill=INK, anchor="start", ls=0.0, extra=""):
    return (f'<text x="{f(x)}" y="{f(y)}" font-family="{FONT[kind][1]}" font-size="{f(size)}" font-weight="{weight}" '
            f'fill="{fill}" letter-spacing="{round(ls * size, 2)}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')


# ---------------------------------------------------------------- Elemente (formatfrei)

def hero(design, x, y, size, col):
    """Design auf quadratischer Leinwand size x size, zentriert auf (x, y)."""
    return f'<g transform="translate({f(x - size / 2)} {f(y - size / 2)})">{design(Cv(size, size, col))}</g>'


def text_ring(words, cv, r=0.4, size=0.075, weight=600, col=INK):
    """Buchstaben einzeln im Kreis (Figma kennt kein textPath), Sterne als Trenner."""
    items = []
    for w in words:
        items += list(w) + ["*"]
    fs = size * cv.u
    widths = [fs * 0.9 if c == "*" else tw(c, "display", weight, fs) for c in items]
    R = r * cv.u
    spare = (2 * math.pi * R - sum(widths)) / len(items)
    X, Y = cv.at(0, 0)
    out, dstar, a = "", "", -math.pi / 2
    for c, w in zip(items, widths):
        mid = a + (w / 2) / R
        px, py = X + R * math.cos(mid), Y + R * math.sin(mid)
        deg = math.degrees(mid) + 90
        if c == "*":
            dstar += star(px, py, fs * 0.36, deg)
        elif c != " ":
            bx, by = X + (R - fs * 0.35) * math.cos(mid), Y + (R - fs * 0.35) * math.sin(mid)
            out += text(bx, by, c, fs, weight=weight, fill=col, anchor="middle",
                        extra=f' transform="rotate({f(deg)} {f(bx)} {f(by)})"')
        a += (w + spare) / R
    return out + path(dstar, col)


def zigzag(cv, n=24, r1=0.48, r2=0.42):
    X, Y = cv.at(0, 0)
    return poly([(X + cv.u * (r1 if k % 2 == 0 else r2) * math.cos(math.pi * k / n - math.pi / 2),
                  Y + cv.u * (r1 if k % 2 == 0 else r2) * math.sin(math.pi * k / n - math.pi / 2)) for k in range(2 * n)])


def ticker(words, W=3000, H=300, weight=600, col=INK):
    fs = H * 0.62
    y = H / 2 + fs * 0.36
    out, d, x = "", "", 0.0
    while x < W:
        for w in words:
            out += text(x, y, w, fs, weight=weight, fill=col, ls=-0.01)
            x += tw(w, "display", weight, fs, -0.01) + fs * 0.35
            d += star(x + fs * 0.32, H / 2, fs * 0.36)
            x += fs * 0.64 + fs * 0.35
    return svg(W, H, out + path(d, col))


ICON_KEYS = ["spark_mark", "spark_outline", "spark_nest", "spark_twelve", "spark_duo", "spark_trio", "spark_burst", "spark_orbit",
             "spark_ring", "spark_extrude", "spark_explode", "spark_sliced", "spark_glitch", "spark_of_sparks", "spark_pixel",
             "spark_pixel_fine", "spark_pixel_dissolve", "spark_spiro", "halftone_spark"]

ICONS_EXTRA = {
    "spark_echo_small":   d_echo(0, 0, 0.17, 4, 1.3),
    "spark_in_circle":    lambda cv: path(circle(*cv.at(0, 0), 0.46 * cv.u) + cv.star(0, 0, 0.36), cv.col, evenodd=True),
    "spark_in_square":    lambda cv: path(rect(cv.u * 0.06, cv.u * 0.06, cv.u * 0.88, cv.u * 0.88) + cv.star(0, 0, 0.38), cv.col, evenodd=True),
    "spark_contour_inside": lambda cv: "".join(stroke(cv.star(0, 0, 0.45 * k / 7), cv.u * 0.006, cv.col) for k in range(1, 8)),
    "spark_double_outline": lambda cv: stroke(cv.star(0, 0, 0.44), cv.u * 0.006, cv.col) + stroke(cv.star(0, 0, 0.38), cv.u * 0.006, cv.col)
                                       + path(cv.star(0, 0, 0.26), cv.col),
    "spark_dither":       lambda cv: path(dither_path(field("spark_grainy", cv.W, cv.H, cv.u / 110), cv.u / 110), cv.col),
    "spark_halftone_shade": lambda cv: path(halftone_path(field("spark_shade", cv.W, cv.H, cv.u / 60), cv.u / 60), cv.col),
    "spark_dither_glow":  lambda cv: path(dither_path(field("spark_glow", cv.W, cv.H, cv.u / 110), cv.u / 110), cv.col),
}

BADGES = {
    "badge_ring_makernight": lambda cv: text_ring(["SPARK", "MAKER NIGHT"], cv) + stroke(circle(*cv.at(0, 0), 0.47 * cv.u), cv.u * 0.006, cv.col)
                                        + path(cv.star(0, 0, 0.24), cv.col),
    "badge_ring_build":      lambda cv: text_ring(["BUILD", "SOLDER", "HACK", "REPEAT"], cv, size=0.08) + path(cv.star(0, 0, 0.24), cv.col),
    "badge_ring_club":       lambda cv: path(circle(*cv.at(0, 0), 0.49 * cv.u) + circle(*cv.at(0, 0), 0.3 * cv.u), cv.col, evenodd=True)
                                        + text_ring(["SPARK", "THE MAKER CLUB"], cv, 0.39, 0.07, col=C["white"]) + path(cv.star(0, 0, 0.2), cv.col),
    "badge_starburst":       lambda cv: path(zigzag(cv) + cv.star(0, 0, 0.3), cv.col, evenodd=True),
    "badge_starburst_solid": lambda cv: path(zigzag(cv, 16, 0.49, 0.4), cv.col),
    "badge_circle_echo":     lambda cv: path(circle(*cv.at(0, 0), 0.4 * cv.u) + cv.star(0, 0, 0.3), cv.col, evenodd=True)
                                        + stroke(circle(*cv.at(0, 0), 0.45 * cv.u), cv.u * 0.008, cv.col),
    "badge_pixel":           tile_rects(20, lambda tt, cv, t: math.hypot(tt[2], tt[3]) < 0.47
                                        and float(star_d(np.float64(tt[2]), np.float64(tt[3]), 0.34)) > 1, 0.1),
    "badge_stamp":           lambda cv: stroke(circle(*cv.at(0, 0), 0.47 * cv.u), cv.u * 0.01, cv.col)
                                        + stroke(circle(*cv.at(0, 0), 0.43 * cv.u), cv.u * 0.004, cv.col) + d_ring(30, 0.36)(cv),
}

CORNERS = {                                      # Leinwand 1000x1000, Motiv sitzt oben links; in Figma drehen/spiegeln
    "corner_echo":     d_echo(-0.5, -0.5, 0.3, 9, 1.28),
    "corner_contour":  lambda cv: "".join(stroke(cv.star(-0.5, -0.5, 0.09 * k), cv.u * 0.004, cv.col) for k in range(1, 16)),
    "corner_burst":    lambda cv: path(cv.star(-0.5, -0.5, 0.2) + wedges(cv, -0.5, -0.5, 0.28, (1.1, 0.7), 24, 1.9), cv.col),
    "corner_tiles":    tile_rects(16, lambda tt, cv, t: hsh(tt[4], tt[5]) < ss(1.3 - 1.25 * math.hypot(tt[2] + 0.5, tt[3] + 0.5))),
    "corner_pixels":   tile_rects(40, lambda tt, cv, t: hsh(tt[4], tt[5], 2) < ss(1.1 - 1.3 * math.hypot(tt[2] + 0.5, tt[3] + 0.5))),
    "corner_stars":    d_pattern(10, size=lambda t: 0.46 * max(0, 1 - math.hypot(t[2] + 0.5, t[3] + 0.5) / 1.1) ** 1.2),
    "corner_scatter":  lambda cv: path("".join(cv.star(-0.5 + x, -0.5 + y, s, r) for x, y, s, r in (
        (lambda rng: [(a, b, 0.14 * (1 - math.hypot(a, b) / 1.0) ** 2 + 0.01, rng.uniform(0, 60))
                      for a, b in rng.random((70, 2)) ** 1.6])(np.random.default_rng(9)))), cv.col),
}

BAND_W, BAND_H = 3000, 360
BANDS = {
    "band_tiles":     tile_rects(12, lambda tt, cv, t: hsh(tt[4], tt[5]) < math.exp(-(tt[3] / 0.3) ** 2)),
    "band_pixels":    tile_rects(28, lambda tt, cv, t: hsh(tt[4], tt[5], 4) < math.exp(-(tt[3] / 0.28) ** 2)),
    "band_stars":     d_pattern(2, size=lambda t: 0.4 if t[4] % 2 == 0 else 0.2, rot=lambda t: 30 * (t[4] % 4 == 1)),
    "band_stars_grow": d_pattern(2, size=lambda t: 0.04 + 0.4 * t[6]),
    "band_checker":   lambda cv: path("".join(rect(i * cv.H / 3, j * cv.H / 3, cv.H / 3, cv.H / 3)
                                              for i in range(int(cv.W / cv.H * 3) + 1) for j in range(3) if (i + j) % 2 == 0), cv.col),
    "band_halftone":  d_dots(8, lambda tt, cv: 1 - abs(tt[2]) / cv.ex),
    "band_contour":   lambda cv: "".join(stroke(cv.star(0, 0, 0.3 * k), cv.u * 0.006, cv.col) for k in range(1, 40)),
}

DIV_W, DIV_H = 2000, 60
DIVIDERS = {
    "div_star":        lambda cv: stroke(f"M0 30H{980 - 36}M{1020 + 36} 30H2000", 3) + path(star(1000, 30, 28)),
    "div_star_double": lambda cv: stroke(f"M0 22H2000M0 38H2000", 2) + path(star(1000, 30, 30)) ,
    "div_stars":       lambda cv: path("".join(star(30 + i * 60, 30, 16 if i % 2 else 9) for i in range(34))),
    "div_dots_star":   lambda cv: path("".join(circle(20 + i * 40, 30, 5) for i in range(50) if abs(20 + i * 40 - 1000) > 50)
                                       + star(1000, 30, 28)),
    "div_pixel_fade":  lambda cv: path("".join(rect(x + 2, 22, 12, 16) for i in range(125) for x in [i * 16]
                                               if hsh(i, 0, 8) < 1 - abs(x - 1000) / 1000)),
    "div_tiles":       lambda cv: path("".join(rect(i * 40, 10, 36, 40) for i in range(50) if hsh(i, 1, 3) < 0.6)),
}


def seamless(d_fn, S=400):
    """Kachel fuer Figma-Musterfuellung: Motiv an allen 9 Nachbarpositionen zeichnen, auf S x S geclippt."""
    return svg(S, S, "".join(f'<g transform="translate({dx} {dy})">{d_fn(S)}</g>'
                             for dx in (-S, 0, S) for dy in (-S, 0, S)))


def pat_halftone(S, n=10):
    d = ""
    for i in range(n):
        for j in range(n):
            v = 1.1 - float(star_d(np.float64((i + 0.5) / n - 0.5), np.float64((j + 0.5) / n - 0.5), 0.45))
            d += circle((i + 0.5) * S / n, (j + 0.5) * S / n, S / n * 0.72 * math.sqrt(min(1, max(0, v))))
    return path(d)


PATTERNS = {
    "pat_star_grid":   lambda S: path(star(0, 0, S * 0.14) + star(S / 2, S / 2, S * 0.14)),
    "pat_star_mixed":  lambda S: path(star(0, 0, S * 0.16) + star(S / 2, S / 2, S * 0.16, 30)
                                      + star(S / 2, 0, S * 0.06) + star(0, S / 2, S * 0.06, 30)),
    "pat_star_dense":  lambda S: path("".join(star((i + 0.5 * (j % 2)) * S / 4, (j + 0.5) * S / 4, S * 0.05, 30 * (j % 2))
                                              for i in range(4) for j in range(4))),
    "pat_graph_star":  lambda S: stroke(f"M0 0H{S}M0 {S}H{S}M0 0V{S}M{S} 0V{S}", S * 0.006)
                                 + stroke(f"M{S/2} 0V{S}M0 {S/2}H{S}", S * 0.003) + path(star(0, 0, S * 0.07)),
    "pat_pixel_star":  lambda S: tile_rects(16, lambda tt, cv, t: float(star_d(np.float64(tt[2]), np.float64(tt[3]), 0.36)) < 1, 0.1)(Cv(S, S)),
    "pat_tiles":       lambda S: path("".join(rect(i * S / 8 + 1.5, j * S / 8 + 1.5, S / 8 - 3, S / 8 - 3)
                                              for i in range(8) for j in range(8) if hsh(i, j, 12) < 0.35)),
    "pat_halftone":    lambda S: pat_halftone(S),
    "pat_scatter":     lambda S: path("".join(star(x * S, y * S, S * s, r) for x, y, s, r in
                                              [(a, b, 0.02 + 0.07 * c ** 3, 60 * e) for a, b, c, e in np.random.default_rng(11).random((18, 4))])),
    "pat_diagonal":    lambda S: path("".join(star(k * S / 4, k * S / 4, S * 0.08, 15 * k) for k in range(4))
                                      + "".join(star(k * S / 4 + S / 2, k * S / 4, S * 0.03) for k in range(4))),
}


# ---------------------------------------------------------------- Plakat- und Post-Templates

COPY = {"club": "The Maker Club", "title": ("Maker", "Night"), "sub": "Build, solder, hack. Robot sumo included.",
        "date": "XX.XX.", "time": "18:00", "place": "HPI · Raum XX"}


def layout(W, H, fg, col_graphic, bg, graphic, accent=None):
    u = min(W, H)
    m = 0.06 * u
    stacked = H / W >= 1.25
    out = graphic
    # Kopf: Wortmarke + Stern rechts + Linie
    s1 = 0.1 * u
    out += text(m, m + s1 * 0.78, "Spark", s1, weight=600, fill=fg, ls=-0.01)
    out += text(m, m + s1 * 0.78 + s1 * 0.52, COPY["club"], s1 * 0.4, "text", 700, fg)
    out += path(star(W - m - s1 * 0.5, m + s1 * 0.55, s1 * 0.55), accent or fg)
    y_rule = m + s1 * 1.55
    out += f'<rect x="{f(m)}" y="{f(y_rule)}" width="{f(W - 2 * m)}" height="{f(max(1.5, u * 0.003))}" fill="{fg}"/>'
    # Fuss: Datum / Ort
    if stacked:
        sd = 0.105 * u
        yb = H - m
        out += text(m, yb, COPY["place"], sd * 0.42, "text", 700, fg)
        out += f'<rect x="{f(m)}" y="{f(yb - sd * 0.75)}" width="{f(W * 0.34)}" height="{f(max(1.5, u * 0.003))}" fill="{fg}"/>'
        out += text(m, yb - sd * 1.05, COPY["time"], sd, weight=500, fill=fg)
        out += text(m, yb - sd * 2.05, COPY["date"], sd, weight=500, fill=fg)
        foot_top = yb - sd * 2.9
    else:
        sd = 0.058 * u
        yb = H - m
        row = f'{COPY["date"]}  ·  {COPY["time"]}  ·  {COPY["place"]}'
        out += text(m, yb, row, sd, weight=500, fill=fg)
        out += f'<rect x="{f(m)}" y="{f(yb - sd * 1.35)}" width="{f(W - 2 * m)}" height="{f(max(1.5, u * 0.003))}" fill="{fg}"/>'
        foot_top = yb - sd * 1.8
    # Titel: so gross wie Breite und Hoehe erlauben
    width = (W - 2 * m) * (0.95 if stacked else 0.56)
    sub_size = 0.036 * u
    avail = foot_top - y_rule - sub_size * 2.4
    S = min(min(fit(t, width, ls=-0.02) for t in COPY["title"]), avail / 1.9)
    y1 = y_rule + S * 0.92
    out += text(m - S * 0.04, y1, COPY["title"][0], S, weight=600, fill=fg, ls=-0.02)
    out += text(m - S * 0.04, y1 + S * 0.86, COPY["title"][1], S, weight=600, fill=fg, ls=-0.02)
    out += text(m, y1 + S * 0.86 + sub_size * 1.9, COPY["sub"], sub_size, "text", 500, fg)
    return svg(W, H, out, bg)


def focus(W, H):
    """Wo das Hero-Motiv sitzt: unten rechts (hoch), rechts (quer)."""
    if H / W >= 1.25:                            # rechts unten, frei von Titel (oben) und Datum (links unten)
        return W * 0.76, H * 0.77, W * 0.78
    if W / H > 1.5:
        return W * 0.78, H * 0.56, H * 1.0
    return W * 0.76, H * 0.68, W * 0.6


def full(key):
    return lambda W, H, col: SOLID[key](Cv(W, H, col))


def at_focus(key, scale=1.0, dither=None):
    def g(W, H, col):
        x, y, s = focus(W, H)
        s *= scale
        if dither:
            cell = s / 90
            return f'<g transform="translate({f(x - s / 2)} {f(y - s / 2)})">' + path(dither_path(field(dither, s, s, cell), cell), col) + "</g>"
        return hero(SOLID[key], x, y, s, col)
    return g


def layers(*gs):
    return lambda W, H, col: "".join(g(W, H, c or col) for g, c in gs)


TEMPLATES = {                                    # bg, Text, Grafikfarbe, Grafik, Akzent
    "yellow_echo":    (C["yellow"], INK, INK, full("spark_echo_corner"), None),
    "navy_grow":      (C["navy"], C["paper"], C["paper"], full("spark_pattern_corner"), None),
    "paper_pixel":    (C["paper"], INK, C["navy"], at_focus("spark_pixel_dissolve"), C["navy"]),
    "blue_contour":   (C["blue"], C["violet"], "#5A4BFF", layers((full("graph_grid"), "#B8D3FF"), (at_focus("spark_echo", 1.0), None)), None),
    "black_tiles":    (C["black"], C["white"], C["white"], layers((full("tiles_corner"), None), (at_focus("spark_mark", 0.45), C["orange"])), C["orange"]),
    "orange_burst":   (C["orange"], INK, INK, at_focus("spark_burst", 1.0), None),
    "violet_nest":    (C["violet"], C["white"], C["blue"], at_focus("spark_nest", 1.25), C["blue"]),
    "paper_halftone": (C["paper"], C["navy"], C["navy"], at_focus("halftone_spark", 1.1), None),
    "blue_pixelgrid": (C["blue"], C["violet"], C["violet"], layers((full("graph_grid"), "#B8D3FF"), (at_focus("", 1.0, "spark_grainy"), None)), None),
    "black_glitch":   (C["black"], C["white"], C["white"], at_focus("spark_glitch", 1.0), C["orange"]),
    "paper_sliced":   (C["paper"], INK, C["orange"], at_focus("spark_sliced", 1.05), C["orange"]),
    "yellow_orbit":   (C["yellow"], INK, INK, at_focus("spark_orbit", 1.15), None),
    "paper_ring":     (C["paper"], C["navy"], C["navy"], at_focus("spark_ring", 1.1), C["navy"]),
    "navy_explode":   (C["navy"], C["paper"], C["yellow"], at_focus("spark_explode", 1.1), C["yellow"]),
}


# ---------------------------------------------------------------- Galerie + main

def gallery():
    import json
    idx = {}
    for dp, _, fs in os.walk(OUT):
        rel = os.path.relpath(dp, OUT)
        svgs = sorted(x for x in fs if x.endswith(".svg"))
        if svgs:
            idx[rel] = svgs
    page = """<!doctype html><html lang="de"><head><meta charset="utf-8"><title>SPARK Vectors</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--bg:#0b0b0b;--fg:#f2efe6;--mut:#8a877f;--line:#262626}
@media (prefers-color-scheme:light){:root{--bg:#f2efe6;--fg:#141414;--mut:#6b675e;--line:#d8d3c6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 ui-monospace,Menlo,monospace;padding:24px 16px}
h1{font-size:28px;margin:0 0 4px}p{color:var(--mut);margin:0 0 16px;max-width:80ch}
nav{position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:1;display:flex;flex-wrap:wrap;gap:6px}
button{font:inherit;background:none;color:var(--fg);border:1px solid var(--line);padding:5px 10px;cursor:pointer}
button[aria-pressed=true]{background:var(--fg);color:var(--bg)}
h2{font-size:15px;margin:28px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--w,200px),1fr));gap:14px}
figure{margin:0}img{width:100%;display:block;background:#F2EFE6}
figcaption{margin-top:6px;font-size:12px;color:var(--mut);word-break:break-all}
</style></head><body><h1>SPARK Vectors</h1>
<p>SVG für Figma: Datei reinziehen oder kopieren und einfügen. Formen sind echte Pfade, also Farbe direkt am Layer ändern.
Templates nutzen Clash Display und Satoshi, die Texte bleiben editierbar. Ordner: <code>vectors/</code>.</p>
<nav id="nav"></nav><main id="main"></main><script>
const IDX=__IDX__;const TABS=["_elements","poster_a3","16x9","9x16","4x5","1x1"];
let cur="poster_a3";try{cur=localStorage.getItem("vtab")||cur}catch(e){}
function draw(){
 document.getElementById("nav").innerHTML=TABS.map(t=>`<button data-t="${t}" aria-pressed="${t===cur}">${t.replace("_elements","elements")}</button>`).join("");
 const w=cur==="16x9"?"300px":"180px";
 document.getElementById("main").innerHTML=Object.keys(IDX).filter(k=>k.split("/")[0]===cur).sort((a,b)=>(a.endsWith("templates")?-1:0)-(b.endsWith("templates")?-1:0)).map(k=>
  `<h2>${k} · ${IDX[k].length}</h2><div class="grid" style="--w:${k.includes("band")||k.includes("divider")?"420px":w}">`+IDX[k].map(n=>
  `<figure><img loading="lazy" src="vectors/${k}/${n}" alt="${n}"><figcaption>${n.replace(".svg","")}</figcaption></figure>`).join("")+"</div>").join("");
}
document.getElementById("nav").onclick=e=>{const t=e.target.dataset.t;if(!t)return;cur=t;try{localStorage.setItem("vtab",t)}catch(e){};draw()};draw();
</script></body></html>"""
    open(f"{ROOT}/vectors.html", "w", encoding="utf-8").write(page.replace("__IDX__", json.dumps(idx)))


def build_format(fmt):
    W, H = FORMATS[fmt]
    for name, (bg, fg, gc, g, acc) in TEMPLATES.items():
        write(f"{fmt}/templates/{name}", layout(W, H, fg, gc, bg, g(W, H, gc), acc))
    for name, fn in SOLID.items():
        write(f"{fmt}/solid/{name}", svg(W, H, fn(Cv(W, H))))
    for name in FIELDS:
        write(f"{fmt}/dither/{name}", dither_svg(name, W, H))
        if name not in THIN:
            write(f"{fmt}/halftone/{name}", halftone_svg(name, W, H))
    return fmt


def build_elements():
    S = 1000
    for k in ICON_KEYS:
        write(f"_elements/icons/{k}", svg(S, S, SOLID[k](Cv(S, S))))
    for k, fn in ICONS_EXTRA.items():
        write(f"_elements/icons/{k}", svg(S, S, fn(Cv(S, S))))
    for k, fn in BADGES.items():
        write(f"_elements/badges/{k}", svg(S, S, fn(Cv(S, S))))
    for k, fn in CORNERS.items():
        write(f"_elements/corners/{k}", svg(S, S, fn(Cv(S, S))))
    for k, fn in BANDS.items():
        write(f"_elements/bands/{k}", svg(BAND_W, BAND_H, fn(Cv(BAND_W, BAND_H))))
    write("_elements/bands/band_ticker_makernight", ticker(["MAKER NIGHT"]))
    write("_elements/bands/band_ticker_spark", ticker(["SPARK", "THE MAKER CLUB"]))
    write("_elements/bands/band_ticker_build", ticker(["BUILD", "SOLDER", "HACK", "REPEAT"], weight=500))
    for k, fn in DIVIDERS.items():
        write(f"_elements/dividers/{k}", svg(DIV_W, DIV_H, fn(Cv(DIV_W, DIV_H))))
    for k, fn in PATTERNS.items():
        write(f"_elements/patterns/{k}", seamless(fn))
    return "_elements"


def check():
    d = star(0, 0, 1)
    assert d.startswith("M0 -1") and d.count("C") == 12, d[:40]
    assert abs(fit("Maker", 500) * tw("Maker", size=1) - 500) < 1e-6
    for name, fn in SOLID.items():
        body = fn(Cv(1080, 1350))
        assert "<path" in body and "nan" not in body, name
    print("check ok", len(SOLID), "solid,", len(TEMPLATES), "templates")


if __name__ == "__main__":
    import shutil
    import sys
    from multiprocessing import Pool
    check()
    if sys.argv[1:2] == ["check"]:
        sys.exit()
    shutil.rmtree(OUT, ignore_errors=True)
    with Pool(6) as pool:
        for r in pool.imap_unordered(build_format, list(FORMATS)):
            print(r, flush=True)
    print(build_elements())
    gallery()
    n = sum(len([x for x in fs if x.endswith(".svg")]) for _, _, fs in os.walk(OUT))
    print(n, "SVGs")
