#!/usr/bin/env python3
"""Spark-Labor: neue Rollen fuer den Stern (Fraktale, Gitter, Verdeckung) auf dem Maker-Night-Raster.

Jeder Kandidat ist ein Wertfeld v in [0,1] auf dem logischen Raster (D3 Bayer 4x4, R = 4 px), optional mit
Zusatzebenen in einer zweiten Palette (Fenster). Nur Importe aus styles.py, keine Aenderung dort.

  uv run -q --with numpy --with pillow --with scipy --with scikit-image python src/lab_spark.py              # alle, lav 16x9
  uv run ... python src/lab_spark.py S31b S26 --pal all                                                  # Auswahl, 6 Pruefpaletten
  uv run ... python src/lab_spark.py S31 --kick --pal cherenkov                                          # Test mit Kick-off-Titel
  uv run ... python src/lab_spark.py posters [S31b S26]                                                  # A3 im echten Satz
  uv run ... python src/lab_spark.py html                                                                # nur Galerie
  uv run ... python src/lab_spark.py test                                                                # Selbsttest Handschraffur S54b/c
-> styles/lab/spark/<code>_<pal>_<fmt>.png, poster_<code>_<pal>.png, sheet_*.png, index.html
"""
import html
import os
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import (gaussian_filter, gaussian_filter1d, map_coordinates, binary_dilation, binary_erosion,
                           distance_transform_edt)

import styles
from styles import BASE, Ctx, dither, font, hexpal, line_mask, up
from makernight_sparks import star_r

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "styles", "lab", "spark")
D = "bayer4"
# Palette "hinter" dem Fenster (S25) bzw. zweite Lichtfarbe (S31c). Kick-off: kein Lila.
ALT = {"lav": "acid", "acid": "lav", "cga": "laser", "paper": "acid", "1bit": "acid", "riso": "riso",
       "cherenkov": "eclipse", "eclipse": "cherenkov", "phosphor": "eclipse", "laser": "cherenkov",
       "holo": "eclipse", "blueprint": "eclipse", "uv": "holo",
       "signal": "cherenkov", "lava": "klein", "kirsche": "holo", "klein": "lava", "minze": "orangerie",   # wie ALT2 im Kick-off
       "orangerie": "eis", "eis": "orangerie", "zitrone": "klein", "tokio": "eclipse", "cga0": "laser"}
TMP = os.path.join(OUT, "_kick")                                        # Vertragstest Kick-off-Satz, nicht in der Galerie
PALS16 = ["lav", "riso", "cherenkov", "eclipse", "cga", "phosphor"]     # Lab-Pruefpaletten 16x9


# ---------------------------------------------------------------- Geometrie in Seiteneinheiten (m = kurze Seite)

class G:
    """Geometrie fuer einen Kandidaten. Vertrag fuer Aufrufer (kickoff.py):
      g.K   = (x0, y0, R) in m-Einheiten (m = kurze Seite) ueberschreibt die Hauptplatzierung des Sterns
      g.rot = Grad, ueberschreibt die Eigendrehung (wo sinnvoll)
      g.lit = nach dem Aufruf: Maske der leuchtenden Sternpixel fuer die XOR-Regel (None = v >= 0.5)
    Plakatmodus (st["poster"]): Titelgeometrie kommt aus c.L (styles.layout-Schluessel), Schrift setzt der Aufrufer."""
    K = None
    rot = None

    def __init__(self, st, fmt, c=None):
        self.c = c = c or Ctx(st, fmt)
        self.poster = c.L if st.get("poster") else None
        self.lit = None                                      # Maske "leuchtender Stern" fuer die XOR-Regel der Schrift
        self.fmt, self.px, self.gh, self.gw = fmt, c.px, c.gh, c.gw
        self.m = min(c.W, c.H)
        self.X, self.Y = c.cx / self.m, c.cy / self.m
        self.A, self.B = c.W / self.m, c.H / self.m          # Seite in m-Einheiten
        self.tall = c.H > c.W
        self.pal, self.N = c.pal, c.N

    def at(self, wide, tall):
        return tall if self.tall else wide

    def pos(self, default):
        """Hauptplatzierung (x0, y0, R): Aufrufer-Override g.K oder der Vorschlag des Kandidaten."""
        return tuple(self.K) if self.K is not None else tuple(default)

    def ro(self, default):
        """Drehung: Aufrufer-Override g.rot oder die Eigendrehung des Kandidaten."""
        return self.rot if self.rot is not None else default


def sd(x, y, rot):
    """Normierte Sterndistanz (Spitze = 1) fuer lokale Koordinaten."""
    return np.hypot(x, y) / star_r(x, y, rot)


def star(g, x0, y0, R, rot):
    return sd(g.X - x0, g.Y - y0, rot) / R


def tips(rot):
    return [np.radians(rot + 30 + 60 * k) for k in range(6)]


def stamp(g, acc, x0, y0, R, rot, op="xor", val=True):
    """Stern nur im Fenster auswerten (fuer tausende kleine Sterne)."""
    px = g.px / g.m
    j0, j1 = max(0, int((x0 - R) / px) - 1), min(g.gw, int((x0 + R) / px) + 2)
    i0, i1 = max(0, int((y0 - R) / px) - 1), min(g.gh, int((y0 + R) / px) + 2)
    if j0 >= j1 or i0 >= i1:
        return
    w = sd(g.X[i0:i1, j0:j1] - x0, g.Y[i0:i1, j0:j1] - y0, rot) < R
    if op == "xor":
        acc[i0:i1, j0:j1] ^= w
    elif op == "max":
        acc[i0:i1, j0:j1] = np.where(w, np.maximum(acc[i0:i1, j0:j1], val), acc[i0:i1, j0:j1])
    else:
        acc[i0:i1, j0:j1] += w * val


def bg(g, lo=0.02, hi=0.07):
    nx, ny = g.X / g.A, g.Y / g.B
    return lo + hi * ((0.35 * nx + ny) / 1.35 if not g.tall else ny)


def title(g, dx=0.0, dy=0.0):
    """(Maske, Fuellwert, bbox in m) des Titels auf dem logischen Raster, Geometrie immer aus c.L
    (Zeilen, Grundlinien, Versalhoehe, Satzkante wie styles.layout; Kick-off: eine Zeile SPARK).
    Lab: dx, dy (m) verschieben den Titel, der Kandidat malt ihn selbst.
    Plakatmodus: kein Versatz, Maske zum Malen leer (Schrift setzt der Aufrufer); die echte Form liegt in g.T."""
    L = g.c.L
    if g.poster:
        dx = dy = 0.0
    cap = L["cap"]
    m = np.zeros((g.gh, g.gw), bool)
    rel = np.zeros((g.gh, g.gw), np.float32)
    for s, b in zip(L["title"], L["tb"]):
        b = b + dy * g.m
        m |= line_mask(s, "clash", cap, b, L["m"] + dx * g.m, g.px, m.shape)
        band = (g.c.cy <= b + 0.1 * cap) & (g.c.cy > b - 1.4 * cap)
        rel = np.where(band, np.clip((g.c.cy - (b - cap)) / cap, 0, 1), rel)
    g.T = m
    ys, xs = np.nonzero(m)
    bb = (xs.min() * g.px / g.m, ys.min() * g.px / g.m, (xs.max() + 1) * g.px / g.m, (ys.max() + 1) * g.px / g.m)
    return (np.zeros_like(m) if g.poster else m), 0.7 + 0.28 * (1 - rel), bb


def glow(d, w=0.35):
    return np.exp(-np.maximum(d - 1, 0) / w)


def ink(d, lo=0.64):
    """Glutverlauf im Stern wie S2."""
    return lo + (1 - lo) * np.clip(1 - d, 0, 1) ** 0.7


def nest(g, x0, y0, R, rot, K=None, ratio=0.74, step=30, warp=None):
    X, Y = (g.X - x0, g.Y - y0) if warp is None else warp
    par = np.zeros((g.gh, g.gw), bool)
    K = K or int(np.log(4 * g.px / g.m / R) / np.log(ratio)) + 1
    for k in range(K):
        par ^= sd(X, Y, rot + step * k) < R * ratio ** k
    return par


# ---------------------------------------------------------------- Kandidaten: f(g) -> v  oder  (v, [(v2, maske, palette)])

def c_sternkind(g):
    """Jede Spitze gebiert einen kleineren Stern, rekursiv, XOR-Paritaet."""
    x0, y0, R = g.pos(g.at((1.30, 0.52, 0.30), (0.60, 0.98, 0.25)))
    rot = g.ro(14)
    acc = np.zeros((g.gh, g.gw), bool)

    def rec(x, y, r, rot, n, back):
        stamp(g, acc, x, y, r, rot)
        if n:
            for a in tips(rot):
                if back is None or np.cos(a - back) > 0.4:          # nur nach aussen wachsen
                    rec(x + np.cos(a) * r * 1.02, y + np.sin(a) * r * 1.02, r * 0.42, rot, n - 1, a)

    rec(x0, y0, R, rot, 5, None)
    d = star(g, x0, y0, R * 1.5, rot)
    v = bg(g) + 0.10 * glow(d, 0.4)
    g.lit = acc
    return np.where(acc, ink(d, 0.6), v)


def c_flocke(g):
    """Sierpinski-Stern: aus jedem Stern faellt der gedrehte Kernstern heraus, jede Spitze ist wieder ein Stern."""
    x0, y0, R = g.at((1.30, 0.52, 0.46), (0.50, 0.86, 0.46))
    x, y = (g.X - x0) / R, (g.Y - y0) / R
    on = sd(x, y, 14) < 1
    lev = np.zeros(x.shape, np.float32)
    rot, s, t, hole = 14.0, 0.40, 0.60, 0.40
    for n in range(7):
        ins = sd(x, y, rot) < 1
        on &= ~(ins & (sd(x, y, rot + 30) < hole))
        lev += ins
        th = np.arctan2(y, x) - np.radians(rot + 30)
        ca = np.radians(rot + 30) + np.round(th / (np.pi / 3)) * np.pi / 3
        x, y = (x - t * np.cos(ca)) / s, (y - t * np.sin(ca)) / s
    d = star(g, x0, y0, R, 14)
    v = bg(g) + 0.12 * glow(d, 0.4)
    return np.where(on, 0.5 + 0.47 * np.clip(lev / 5, 0, 1), v)


def c_attraktor(g):
    """Chaos-Spiel: 6 Kontraktionen zu den Spitzen, leicht gedreht. Dichte = Sternstaub."""
    x0, y0, R = g.pos(g.at((1.28, 0.50, 0.46), (0.50, 0.84, 0.46)))
    rng = np.random.default_rng(5)
    p = rng.random((400000, 2)) - 0.5
    s, tw = 0.30, np.radians(11)
    rot = g.ro(14)
    T = np.array([[np.cos(a), np.sin(a)] for a in tips(rot)] + [[0.42 * np.cos(a - np.pi / 6), 0.42 * np.sin(a - np.pi / 6)]
                  for a in tips(rot)]) * (1 - s)
    Rm = s * np.array([[np.cos(tw), -np.sin(tw)], [np.sin(tw), np.cos(tw)]])
    H = np.zeros((g.gh, g.gw))
    step = g.px / g.m
    for n in range(40):
        k = rng.integers(0, 12, len(p))
        p = p @ Rm.T + T[k]
        if n > 12:
            j = ((x0 + p[:, 0] * R) / step).astype(int)
            i = ((y0 + p[:, 1] * R) / step).astype(int)
            ok = (i >= 0) & (i < g.gh) & (j >= 0) & (j < g.gw)
            np.add.at(H, (i[ok], j[ok]), 1)
    H = np.sqrt(H / np.percentile(H[H > 0], 99.8))
    halo = gaussian_filter(H, 10 * 4 / g.px * g.c.u)
    return np.clip(bg(g) + 0.3 * halo / halo.max() + 0.85 * np.clip(H, 0, 1) ** 1.3, 0, 1)


def hexlattice(g, a):
    """Naechster Punkt eines Hex-Gitters (Abstand a): lokale Koordinaten + Zentrum."""
    best = None
    for ox, oy in ((0, 0), (a / 2, a * np.sqrt(3) / 2)):
        cx = np.round((g.X - ox) / a) * a + ox
        cy = np.round((g.Y - oy) / (a * np.sqrt(3))) * a * np.sqrt(3) + oy
        dd = np.hypot(g.X - cx, g.Y - cy)
        if best is None:
            best = [dd, cx, cy]
        else:
            w = dd < best[0]
            best = [np.where(w, dd, best[0]), np.where(w, cx, best[1]), np.where(w, cy, best[2])]
    return g.X - best[1], g.Y - best[2], best[1], best[2]


def c_drehfeld(g):
    """Gitter gleich heller Sterne. Draussen wirbeln sie, im grossen Stern stehen sie still: ein Geheimbild aus Ordnung."""
    a = g.at(0.052, 0.052)
    lx, ly, cx, cy = hexlattice(g, a)
    x0, y0, R = g.at((1.20, 0.52, 0.58), (0.50, 0.80, 0.52))
    D = sd(cx - x0, cy - y0, 14) / R
    ang = np.degrees(np.arctan2(cy - y0, cx - x0))
    rot = np.where(D < 1, 14, 14 + 40 * np.sin(D * 5.5 - 1) + 0.5 * ang)
    m = sd(lx, ly, rot) < 0.62 * a
    lum = np.where(D < 1, 0.62, 0.40)
    return np.where(m, lum, bg(g))


def sd3(x, y, rot, a=0.45):
    """Dreistern: der Logo-Stern, jede zweite Spitze um a gekuerzt -> drei lange Spitzen, dreieckiger Umriss.
    rot = 0: lange Spitze zeigt nach oben."""
    th = np.arctan2(y, x) - np.radians(rot + 30)
    return np.hypot(x, y) / (star_r(x, y, rot) * (1 - a * 0.5 * (1 - np.cos(3 * th))))


def rings(d, K, ph=0.0):
    return (d * K + ph) % 1 < 0.5


def _interf_src(g, tall=(0.51, 0.71, 0.30)):
    """Hauptplatzierung (Mitte zwischen den Quellen); Quellen liegen relativ dazu, skaliert mit R."""
    x0, y0, R = g.pos(g.at((0.87, 0.54, 0.30), tall))
    return x0, y0, R, R / 0.30


def c_interferenz(g):
    """Zwei Hoehenlinien-Sterne (S5) ueber die ganze Seite, per XOR: Sternmoire."""
    x0, y0, R, k = _interf_src(g)
    o = g.at((0.15, -0.08), (0.11, -0.09))
    rot = g.ro(14)
    d1 = star(g, x0 - o[0] * k, y0 - o[1] * k, R, rot)
    d2 = star(g, x0 + o[0] * k, y0 + o[1] * k, R, rot + 30)
    x = rings(d1, 2.6) ^ rings(d2, 2.6)
    lum = 0.06 + 0.92 * np.exp(-0.5 * np.minimum(d1, d2))
    return np.where(x, lum, bg(g))


def c_interferenz3(g):
    """S18b: drei Quellen im Dreieck, zwei Sechssterne unten, ein Dreistern oben. Jede Welle laeuft nur ein paar
    Ringe weit, so bleibt jede Quelle als eigene Form lesbar; wo sich die Wellen treffen, XOR-Moire."""
    x0, y0, R, k = _interf_src(g, (0.50, 0.96, 0.30))              # hoch: Wellen unter dem Titel, nicht darin
    rot = g.ro(14)
    P = g.at(((-0.30, 0.10), (0.30, 0.14), (0.02, -0.22)), ((-0.20, 0.18), (0.20, 0.22), (0.0, -0.20)))
    (p1, p2, p3) = [(x0 + a * k, y0 + b * k) for a, b in P]
    d1, d2 = star(g, *p1, R, rot), star(g, *p2, R, rot + 30)
    d3 = sd3(g.X - p3[0], g.Y - p3[1], rot - 14) / (R * 1.15)
    K, dm = 2.2, 2.6
    x = (rings(d1, K) & (d1 < dm)) ^ (rings(d2, K) & (d2 < dm)) ^ (rings(d3, K) & (d3 < dm))
    lum = 0.06 + 0.92 * np.exp(-0.55 * np.minimum(np.minimum(d1, d2), d3))
    return np.where(x, lum, bg(g))


def c_interferenz3z(g):
    """S18c: Sechsstern und Dreistern auf derselben Mitte, beide Wellen laufen nur drei Ringe weit:
    ein dreizaehliges Moire-Emblem mit klarem Umriss."""
    x0, y0, R = g.pos(g.at((1.20, 0.50, 0.34), (0.50, 0.80, 0.34)))
    rot = g.ro(0)
    d1 = star(g, x0, y0, R, rot + 30)
    d3 = sd3(g.X - x0, g.Y - y0, rot) / (R * 1.08)
    x = (rings(d1, 2.6) & (d1 < 3.1)) ^ (rings(d3, 2.6) & (d3 < 3.1))
    lum = 0.06 + 0.92 * np.exp(-0.5 * np.minimum(d1, d3))
    return np.where(x, lum, bg(g))


def fold(x, y, n):
    """Dieder-Faltung D_n: Keil [0, pi/n], gespiegelt."""
    r, th = np.hypot(x, y), np.arctan2(y, x) % (2 * np.pi / n)
    th = np.minimum(th, 2 * np.pi / n - th)
    return r * np.cos(th), r * np.sin(th)


def c_kaleido(g):
    """12-fach gefaltetes Feld: versetzte Sterne im Keil, XOR. Mandala aus einer fremden Kultur."""
    x0, y0, R = g.pos(g.at((1.28, 0.52, 0.48), (0.50, 0.84, 0.48)))
    rot = g.ro(0)
    c, s_ = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    x, y = ((g.X - x0) * c + (g.Y - y0) * s_) / R, (-(g.X - x0) * s_ + (g.Y - y0) * c) / R
    r = np.hypot(x, y)
    x, y = fold(x, y, 6)
    par = sd(x, y, 0) < 1.0
    for (px_, py_, rr, ro) in ((0.55, 0.12, 0.34, 10), (0.30, 0.05, 0.22, 40), (0.80, 0.30, 0.20, 0), (0.62, 0.0, 0.12, 30),
                               (0.15, 0.0, 0.16, 0)):
        par ^= sd(x - px_, y - py_, ro) < rr
    par &= r < 1
    d = star(g, x0, y0, R, rot)
    g.lit = par
    return np.where(par, ink(d * 0.9, 0.55), bg(g) + 0.1 * glow(d, 0.4))


def _kframe(g, default, rot0=0):
    x0, y0, R = g.pos(g.at(*default))
    rot = g.ro(rot0)
    c, s_ = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    x, y = ((g.X - x0) * c + (g.Y - y0) * s_) / R, (-(g.X - x0) * s_ + (g.Y - y0) * c) / R
    return x0, y0, R, rot, x, y


def c_kaleido_siegel(g):
    """S19b: Siegel in der Sternsilhouette: alle Motive auf den Spiegelachsen (keine Herzen), Skalenring aus Strichen
    wie ein Messinstrument, Kreisbaender kippen die Paritaet."""
    x0, y0, R, rot, x, y = _kframe(g, ((1.28, 0.52, 0.50), (0.50, 0.84, 0.50)))
    r = np.hypot(x, y)
    D0 = sd(x, y, 0)
    fx, fy = fold(x, y, 6)
    par = np.zeros(r.shape, bool)
    for (rr, ph, sz, ro) in ((0.0, 0, 0.30, 0), (0.0, 0, 0.19, 30), (0.0, 0, 0.11, 0), (0.0, 0, 0.05, 30),
                             (0.40, 0, 0.12, 0), (0.43, 30, 0.07, 30),
                             (0.64, 0, 0.14, 30), (0.64, 0, 0.07, 0), (0.60, 30, 0.05, 0),
                             (0.86, 0, 0.07, 0)):
        a = np.radians(ph)
        par ^= sd(fx - rr * np.cos(a), fy - rr * np.sin(a), ro) < sz
    th = np.degrees(np.arctan2(y, x)) % 5
    lp = g.px / g.m / R
    tick = (r > 0.50) & (r < 0.55) & (th < 1.6)
    band = (r > 0.33) & (r < 0.33 + 1.5 * lp) | (r > 0.745) & (r < 0.745 + 1.5 * lp)
    par ^= band | tick
    par = (D0 < 1) & ~par                                 # Negativ: der Stern ist voll, die Motive sind ausgestanzt
    g.lit = par
    return np.where(par, ink(D0 * 0.95, 0.55), bg(g) + 0.12 * glow(D0, 0.35))


def c_kaleido_spiegel(g):
    """S19c: echtes Spiegelkabinett (p6m): drei Spiegel kacheln ein Sternmotiv unendlich, sichtbar durch den Stern."""
    x0, y0, R, rot, x, y = _kframe(g, ((1.28, 0.52, 0.52), (0.50, 0.84, 0.52)))
    D0 = sd(x, y, 0)
    a = 0.36
    best = None                                          # naechstes Zentrum eines Hex-Gitters in lokalen Koordinaten
    for ox, oy in ((0, 0), (a / 2, a * np.sqrt(3) / 2)):
        cx = np.round((x - ox) / a) * a + ox
        cy = np.round((y - oy) / (a * np.sqrt(3))) * a * np.sqrt(3) + oy
        dd = np.hypot(x - cx, y - cy)
        best = [dd, cx, cy] if best is None else [np.where(dd < best[0], v, b) for v, b in zip((dd, cx, cy), best)]
    lx, ly = fold(x - best[1], y - best[2], 6)
    lx, ly = lx / a, ly / a
    par = (sd(lx, ly, 0) < 0.40) ^ (sd(lx, ly, 30) < 0.24) ^ (sd(lx, ly, 0) < 0.12) \
        ^ (sd(lx - 0.5, ly - 0.2887, 0) < 0.16) ^ (sd(lx - 0.5, ly, 30) < 0.07) ^ (sd(lx - 0.27, ly - 0.07, 12) < 0.07)
    par = (D0 < 1) & ~par
    g.lit = par
    return np.where(par, ink(D0 * 0.95, 0.5), bg(g) + 0.12 * glow(D0, 0.35))


def c_kaleido_nest(g):
    """S19d: das XOR-Nest (S7), aus der Mitte geschoben und sechsfach gespiegelt: Rosette aus sechs Nestern."""
    x0, y0, R, rot, x, y = _kframe(g, ((1.28, 0.52, 0.52), (0.50, 0.84, 0.52)))
    D0 = sd(x, y, 0)
    fx, fy = fold(x, y, 6)
    ox = 0.42
    par = np.zeros(x.shape, bool)
    for k in range(7):
        par ^= sd(fx - ox, fy, 30 + 30 * k) < 0.5 * 0.74 ** k
    par ^= sd(x, y, 30) < 0.30
    par ^= sd(x, y, 0) < 0.16
    par &= D0 < 1
    par |= (D0 >= 0.8) & (D0 < 1)                                    # harter Rand: Spitzen spitz statt vom XOR abgerundet (Vadim)
    g.lit = par
    return np.where(par, ink(D0 * 0.9, 0.5), bg(g) + 0.12 * glow(D0, 0.35))


def c_kaleido_drei(g):
    """S19e: dreifaches Kaleidoskop (D3) aus Dreisternen, in der Silhouette eines Dreisterns."""
    x0, y0, R, rot, x, y = _kframe(g, ((1.28, 0.52, 0.52), (0.50, 0.84, 0.52)))
    D0 = sd3(x, y, 0)
    c, s_ = np.cos(np.radians(-30)), np.sin(np.radians(-30))   # Achse der langen Spitze (30 Grad) -> 0 Grad
    fx, fy = fold(x * c - y * s_, x * s_ + y * c, 3)           # Keil [0, 60]: 0 = lange Spitze, 60 = kurze Spitze
    par = np.zeros(x.shape, bool)
    # (Abstand, Achse 0|60, Groesse, Drehung): Drehung -30 = lange Spitze entlang Achse 0 nach aussen, 150 = nach innen,
    # 30 = entlang Achse 60 nach aussen
    for (rr, ax, sz, ro) in ((0.0, 0, 0.62, -30), (0.0, 0, 0.44, 30), (0.0, 0, 0.30, -30), (0.0, 0, 0.20, 30),
                             (0.0, 0, 0.12, -30), (0.0, 0, 0.06, 30),
                             (0.72, 0, 0.10, -30), (0.72, 0, 0.05, 30), (0.40, 60, 0.07, 30), (0.52, 0, 0.05, 150)):
        a = np.radians(ax)
        par ^= sd3(fx - rr * np.cos(a), fy - rr * np.sin(a), ro) < sz
    par = (D0 < 1) & ~par
    g.lit = par
    return np.where(par, ink(D0 * 0.9, 0.5), bg(g) + 0.12 * glow(D0, 0.35))


def c_wirbel(g):
    """Das XOR-Nest, im Log-Polar-Raum verdrillt: ein unendlicher Spiralschlund."""
    x0, y0, R = g.at((1.30, 0.50, 0.62), (0.72, 1.02, 0.66))
    x, y = g.X - x0, g.Y - y0
    r = np.hypot(x, y) + 1e-6
    al = 0.55 * np.log(r / R)
    xr, yr = x * np.cos(al) - y * np.sin(al), x * np.sin(al) + y * np.cos(al)
    par = nest(g, x0, y0, R, 14, ratio=0.8, warp=(xr, yr))
    d = star(g, x0, y0, R, 14)
    g.lit = par
    return np.where(par, ink(d, 0.6), bg(g) + 0.13 * glow(d, 0.3))


def c_anschnitt(g):
    """Riesiges Nest, Zentrum ausserhalb der Seite: nur die Spitzen ragen herein. Titel frei."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.66, 1.10, 1.05), (1.30, 1.02, 0.92)))
    rot = g.ro(22)
    d = star(g, x0, y0, R, rot)
    par = nest(g, x0, y0, R, rot)
    g.lit = par
    v = np.where(par, ink(d, 0.5), bg(g) + 0.12 * glow(d, 0.25))
    return np.where(t, fill, v)


def c_rahmen(g):
    """Stern so gross, dass die Seite in ihm liegt: die Ecken sind das Aussen, die Spitzen reissen den Rand auf."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos((g.A / 2, g.B / 2, g.at(1.18, 0.98)))
    d = star(g, x0, y0, R, g.ro(g.at(0, 30)))
    ins = d < 1
    rings = ((d * 9) % 1 < 0.5) & ~ins
    v = np.where(ins, bg(g, 0.04, 0.10) + 0.12 * np.clip(d, 0, 1) ** 4, np.where(rings, 0.38 + 0.4 * glow(d, 0.15), 0.0))
    v = np.where(ins & (d > 0.975), 0.9, v)
    g.lit = v >= 0.5
    return np.where(t, fill, v)


def c_fenster(g):
    """Der Stern als Fenster: dahinter dieselbe Nacht in einer anderen Dimension (fremde Palette, Nest, 30 Grad verdreht)."""
    t, fill, _ = title(g)
    x0, y0, R = g.at((1.30, 0.62, 0.44), (0.60, 0.98, 0.44))
    d = star(g, x0, y0, R, 14)
    ox, oy, Rn = x0 + 0.18 * R, y0 - 0.12 * R, 1.7 * R            # das andere Universum liegt versetzt und groesser
    dn = star(g, ox, oy, Rn, 44)
    par = nest(g, ox, oy, Rn, 44)
    inside_v = np.where(par & (dn < 1), ink(dn, 0.5), 0.06 + 0.16 * np.clip(1 - d, 0, 1))
    v = bg(g) + 0.14 * glow(d, 0.3)
    v = np.where((d < 1) & (d >= 0.955), g.c.lvl(g.N), v)          # Fensterrahmen: flach, hellste Stufe
    g.lit = d < 1
    v = np.where(t, fill, v)
    return v, [(inside_v, (d < 0.955), ALT)]


def clean(m, n=1):
    """Maske ohne haardünne Spitzen (Oeffnung): keine 1-px-Splitter, die Buchstaben zerhacken."""
    return binary_dilation(binary_erosion(m, iterations=n), iterations=n) & m


def c_xortitel_alt(g):
    """Erste Fassung von S26 (Stern unter dem Titel, halb angeschnitten). Nur zum Vergleich."""
    t, fill, bb = title(g)
    x0, y0, R = g.at(((bb[0] + bb[2]) * 0.62, bb[3] + 0.02, 0.50), (0.62, (bb[1] + bb[3]) / 2 + 0.02, 0.52))
    d = star(g, x0, y0, R, 14)
    s = d < 1
    v = np.where(s, ink(d, 0.55), bg(g) + 0.14 * glow(d, 0.3))
    return np.where(t & s, 0.0, np.where(t, fill, v))


def c_xortitel(g):
    """Glutstern mittig hinter dem Titel; wo die Schrift ihn kreuzt, kippt sie ins Negativ.
    Fix: Stern sitzt auf der Titelzeile statt darunter (vorher hing er unter der Zeile, nur die Spitzen kreuzten
    die Schrift, schief um 14 Grad), Spitzen stehen senkrecht, haardünne Spitzenenden sind weggeoeffnet (keine Splitter in den Buchstaben),
    der Stern hat eine flache Kante statt Dunst."""
    t, fill, bb = title(g)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    R0 = min(g.at(0.40, 0.54) * w, 0.55 * g.B, 0.46 * g.A)
    x0, y0, R = g.pos((bb[0] + 0.58 * w, (bb[1] + bb[3]) / 2 + 0.25 * h, R0))
    d = star(g, x0, y0, R, g.ro(0))
    s = clean(d < 1, 1)
    g.lit = s
    v = np.where(s, ink(d, 0.5), bg(g) + 0.10 * glow(d, 0.18))
    return np.where(t & s, 0.0, np.where(t, fill, v))


def c_durchblick(g):
    """Die Buchstaben sind Fenster: durch sie sieht man ein riesiges XOR-Nest, das hinter der Seite liegt."""
    t, fill, bb = title(g)
    x0, y0, R = g.at(((bb[0] + bb[2]) * 0.55, (bb[1] + bb[3]) / 2, 0.62), (0.52, (bb[1] + bb[3]) / 2, 0.62))
    d = star(g, x0, y0, R, 14)
    par = nest(g, x0, y0, R, 14)
    ghost = np.where(par & (d < 1), 0.1 + 0.08 * (1 - np.clip(d, 0, 1)), bg(g))
    g.lit = par & (d < 1)
    lit = np.where(par & (d < 1), fill + 0.02, 0.44)
    return np.where(t, lit, ghost)


def c_finsternis(g):
    """Sternfinsternis: ein schwarzer Stern schiebt sich vor den hellen, die Korona glueht nach aussen."""
    x0, y0, R = g.at((1.28, 0.52, 0.34), (0.60, 0.98, 0.38))
    d = star(g, x0, y0, R, 14)
    o = star(g, x0 + 0.035, y0 - 0.02, R * 0.97, 14)
    cor = gaussian_filter((d < 1).astype(float), 18 * 4 / g.px * g.c.u)
    v = bg(g) + 0.62 * cor + 0.22 * glow(d, 0.5)
    v = np.where(d < 1, 0.97, v)
    return np.where(o < 1, 0.0, np.clip(v, 0, 1))


def c_aufgang(g):
    """Der Stern geht hinter der Titelzeile auf: Grundlinie = Horizont, Buchstaben als Silhouette."""
    L = g.c.L
    dy = g.at(0.64, 0.60) * g.B - L["tb"][-1] / g.m                 # Lab: Titel auf den Horizont schieben
    t, fill, bb = title(g, dy=dy)
    hz = bb[3]
    x0, y0, R = g.pos(g.at(((bb[0] + bb[2]) * 0.55, hz + 0.03, 0.60), ((bb[0] + bb[2]) / 2, hz + 0.03, 0.62)))
    d = star(g, x0, y0, R, g.ro(0))
    up_ = g.Y < hz
    v = np.where(d < 1, ink(d, 0.55), bg(g) + 0.16 * glow(d, 0.35))
    v = np.where(up_, v, 0.0)
    band = (g.Y >= hz) & (g.Y < hz + g.px / g.m * 1.01)
    v = np.where(band, 0.8, v)
    g.lit = (d < 1) & up_
    return np.where(t, np.where(d < 1, 0.0, fill), v)


def c_versatz_alt(g):
    """Erste Fassung von S30 (ein Band, darin 30 Grad weiter). Nur zum Vergleich."""
    x0, y0, R = g.at((1.30, 0.55, 0.42), (0.52, 0.82, 0.44))
    h = g.at(0.13, 0.12)
    inb = np.abs(g.Y - y0 + 0.03) < h / 2
    d0 = star(g, x0, y0, R, 14)
    p0 = nest(g, x0, y0, R, 14)
    p1 = ~nest(g, x0, y0, R * 1.15, 44)
    d1 = star(g, x0, y0, R * 1.15, 44)
    v0 = np.where(p0, ink(d0, 0.58), bg(g) + 0.12 * glow(d0, 0.3))
    v1 = np.where(p1 & (d1 < 1.0), ink(d1, 0.58), bg(g) + 0.12 * glow(d1, 0.3))
    return np.where(inb, v1, v0)


def _slats(g, x0, y0, R, hb):
    """Bandindex je Zeile (Baender hb logische Pixel hoch, auf dem Raster), Fugen = letzte Zeile jedes Bands."""
    row = np.floor((g.Y - (y0 - R)) * g.m / g.px + 1e-6)
    k = np.floor(row / hb)
    return k, (row % hb) == hb - 1


def c_versatz(g):
    """Zeilensprung: der Stern als zwei Halbbilder. Gerade Baender zeigen ihn jetzt, ungerade einen Moment spaeter
    (ein Stueck weiter und gedreht): der Kamm einer Videoaufnahme, die ihn in Bewegung erwischt hat."""
    x0, y0, R = g.pos(g.at((1.24, 0.52, 0.40), (0.52, 0.82, 0.40)))
    rot = g.ro(14)
    hb = max(3, round(0.016 * g.m / g.px))
    k, _ = _slats(g, x0, y0, R, hb)
    odd = k % 2 == 1
    dx = 0.42 * R
    xa, xb = x0 - dx / 2, x0 + dx / 2
    da, db = star(g, xa, y0, R, rot), star(g, xb, y0 - 0.06 * R, R, rot + 24)
    va = np.where(da < 1, ink(da, 0.55), bg(g) + 0.10 * glow(da, 0.3))
    vb = np.where(db < 1, ink(db, 0.55), bg(g) + 0.10 * glow(db, 0.3))
    g.lit = np.where(odd, db < 1, da < 1)
    return np.where(odd, vb, va)


def c_verschluss(g):
    """S30b Rolling Shutter: der Stern wird Streifen fuer Streifen abgetastet, waehrend er sich dreht.
    Jeder Streifen ein spaeterer Moment: der Stern verdreht sich treppenartig von oben nach unten."""
    x0, y0, R = g.pos(g.at((1.28, 0.52, 0.44), (0.52, 0.82, 0.44)))
    rot = g.ro(14)
    hb = max(4, round(0.05 * g.m / g.px))
    k, seam = _slats(g, x0, y0, R, hb)
    nk = np.ceil(2 * R * g.m / g.px / hb)
    tt = np.clip(k / max(nk - 1, 1), 0, 1)
    rk = rot + 75 * tt
    sx = x0 + 0.34 * R * (tt - 0.5)
    X, Y = g.X - sx, g.Y - y0
    d = np.hypot(X, Y) / star_r(X, Y, rk) / R
    par = np.zeros(d.shape, bool)
    for j in range(int(np.log(4 * g.px / g.m / R) / np.log(0.74)) + 1):
        par ^= np.hypot(X, Y) / star_r(X, Y, rk + 30 * j) < R * 0.74 ** j
    par &= d < 1
    d0 = star(g, x0, y0, R, rot)
    ghost = (d0 < 1) & ~(d < 1)
    g.lit = par & ~seam
    v = np.where(par, ink(d, 0.55), np.where(ghost, 0.17, bg(g) + 0.12 * glow(np.minimum(d, d0), 0.3)))
    return np.where(seam & (d < 1.05), 0.0, v)


def c_loch(g):
    """Ein Loch im Raum: die Seite ist hell, der Stern ein Schacht, der ins Schwarze faellt."""
    x0, y0, R = g.at((1.25, 0.52, 0.40), (0.50, 0.84, 0.42))
    d = star(g, x0, y0, R, 14)
    nx = g.X / g.A
    ring = ((np.log(np.maximum(d, 1)) * 9) % 1 < 0.5) * np.exp(-(d - 1) / 0.8)
    outside = 0.44 + 0.08 * nx + 0.14 * ring + 0.3 * np.exp(-(d - 1) / 0.05)
    k = np.floor(np.log(np.maximum(d, 1e-4)) / np.log(0.78))
    # jeder Ring eine Stufe tiefer, gedreht: Treppe nach innen
    x, y = g.X - x0, g.Y - y0
    rk = np.zeros(d.shape)
    for i in range(14):
        rk += sd(x, y, 14 + 12 * i) < R * 0.8 ** i
    inner = np.where(rk % 2 == 1, 0.34 * 0.82 ** rk, 0.02)
    return np.where(d < 1, inner, np.clip(outside, 0, 1))


def c_fluessig(g):
    """Das Nest in geschmolzenem Raum: Koordinaten sinus-verbogen wie ein Demoszene-Plasma."""
    x0, y0, R = g.at((1.25, 0.52, 0.46), (0.50, 0.84, 0.46))
    x, y = g.X - x0, g.Y - y0
    for f, a, ph in ((5.0, 0.10, 0.3), (11.0, 0.035, 1.7)):
        x, y = x + a * np.sin(f * y + ph), y + a * np.sin(f * x + 2 * ph)
    par = nest(g, x0, y0, R, 14, warp=(x, y))
    d = sd(x, y, 14) / R
    return np.where(par, ink(d, 0.6), bg(g) + 0.12 * glow(d, 0.3))


def radial(g, src, x0, y0, n=96, reach=0.97, decay=0.985, order=0):
    """Radiale Unschaerfe zur Lichtquelle (x0, y0): Summe von src entlang der Strecke Pixel -> Quelle."""
    ci, cj = y0 * g.m / g.px - 0.5, x0 * g.m / g.px - 0.5
    ii, jj = np.mgrid[0:g.gh, 0:g.gw].astype(np.float32)
    acc = np.zeros(src.shape)
    src = src.astype(np.float32)
    for s in range(n):
        f = 1 - s / n * reach
        acc += map_coordinates(src, (ci + (ii - ci) * f, cj + (jj - cj) * f), order=order, cval=0) * (decay ** s)
    return acc


def _gl(g, default, rot0=14):
    t, fill, bb = title(g)
    x0, y0, R = g.pos(default(bb))
    rot = g.ro(rot0)
    d = star(g, x0, y0, R, rot)
    return t, fill, bb, x0, y0, R, rot, d, binary_dilation(g.T, iterations=1)


def _lit_band(g, v, tt, thr=0.3, per_pixel=False):
    """XOR-Maske: im Lab der Titel als Silhouette. Im Plakat Titel + Datum ganz (Silhouette vor dem Licht),
    die Kopfzeile kippt pixelweise, wo das Licht hell ist (sonst verschwindet sie im Strahl).
    per_pixel: normale XOR-Regel ueberall (fuer Licht mit harten Schatten, sonst verschwindet Schrift im Dunkel)."""
    g.lit = (v > thr) | tt & (v >= 0.2)
    if per_pixel:
        g.lit = v >= thr
    elif g.poster:                         # Band, aber nur wo ueberhaupt Licht ist (sonst verschwindet Schrift im Dunkel)
        L, yd = g.poster, g.Y * g.m
        g.lit = (yd > L["meta"] + L["sc"]) & (yd < L["db"] + 0.3 * L["capd"]) & (v >= 0.2) | (yd <= L["meta"] + L["sc"]) & (v >= 0.5)


def _paint(g, t, fill, v):
    """Lab-Titel nach der XOR-Regel: Silhouette, wo Licht dahinter ist, sonst normale Fuellung."""
    return np.clip(np.where(t, np.where(g.lit, 0.0, fill), v), 0, 1)


def c_gegenlicht(g):
    """Der Stern steht hinter dem Titel; sein Licht bricht in Strahlen durch die Luecken der Buchstaben."""
    t, fill, bb, x0, y0, R, rot, d, tt = _gl(g, lambda bb: g.at(((bb[0] + bb[2]) * 0.5, (bb[1] + bb[3]) * 0.5, 0.40),
                                                                  ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, 0.40)))
    src = np.where(tt, 0, np.where(d < 1, 1.0, 0.0))
    acc = radial(g, src, x0, y0)
    rays = acc / acc.max()
    halo = np.exp(-np.hypot(g.X - x0, g.Y - y0) / 0.45)             # Streulicht: die ganze Titelzone steht im Gegenlicht
    v = bg(g) + 0.95 * rays ** 0.8 + 0.3 * halo
    v = np.where(d < 1, ink(d, 0.75), v)
    _lit_band(g, v, tt)
    return _paint(g, t, fill, v)


def _behind(bb):
    """Standard fuer S31b ff.: Stern hinter der oberen Titelmitte (Licht faellt durch die Zeile nach unten)."""
    return ((bb[0] + bb[2]) * 0.5, bb[1] + 0.40 * (bb[3] - bb[1]), 0.62 * (bb[3] - bb[1]) + 0.12)


def shafts(g, x0, y0, d, tt, n=200, gamma=0.75, core=0.6):
    """Volumetrische Lichtschaechte: Emitter (Stern + Streulicht), von der Schrift beschnitten, radial verschmiert.
    Normiert auf den Rand des Sterns, faellt mit der Entfernung von selbst (~1/r)."""
    emit = np.where(d < 1, 1.0, core * np.exp(-(d - 1) / 0.25))
    emit = np.where(tt, 0.0, emit)
    acc = radial(g, emit, x0, y0, n=n, reach=0.995, decay=1.0, order=1) / n
    ref = np.percentile(acc[(d > 1.0) & (d < 1.3)], 90) + 1e-6
    return np.clip(acc / ref, 0, 1.2) ** gamma


def c_lichtfall(g):
    """S31b Lichtfall: lange Schaechte, fast ohne Abklingen; die Schatten der Buchstaben ziehen bis an den Seitenrand
    und das Licht faellt ueber die ganze untere Haelfte."""
    t, fill, bb, x0, y0, R, rot, d, tt = _gl(g, _behind)
    rays = shafts(g, x0, y0, d, tt, gamma=0.7)
    v = bg(g, 0.0, 0.04) + 0.96 * rays
    v = np.where(d < 1, ink(d, 0.8), v)
    _lit_band(g, v, tt, 0.45)
    return _paint(g, t, fill, v)


def c_lichtfall_kurz(g):
    """S31b2 (Vergleich): kurze, schnell abklingende Strahlen, nur ein Kranz um die Zeile."""
    t, fill, bb, x0, y0, R, rot, d, tt = _gl(g, _behind)
    rays = shafts(g, x0, y0, d, tt, gamma=1.6)
    v = bg(g) + 0.95 * rays
    v = np.where(d < 1, ink(d, 0.8), v)
    _lit_band(g, v, tt, 0.45)
    return _paint(g, t, fill, v)


def c_zweitlicht(g):
    """S31c Zweitfarbe: Stern und Titelsilhouette in der eigenen Palette, das Licht dahinter in einer zweiten
    (Tscherenkow-Blau mit Gold, CGA mit Laserrot, ...)."""
    t, fill, bb, x0, y0, R, rot, d, tt = _gl(g, lambda bb: _behind(bb)[:2] + (1.0 * (bb[3] - bb[1]) + 0.14,))
    rays = shafts(g, x0, y0, d, tt, gamma=0.75)
    v2 = 0.01 + 0.97 * rays
    star_ = d < 1
    v = np.where(star_, ink(d, 0.8), 0.0)
    _lit_band(g, np.where(star_, 1.0, rays), tt, 0.45)
    return _paint(g, t, fill, v), [(v2, ~star_ & ~(t > 0), ALT)]


def rim(g, x0, y0, n=2):
    """Pixel direkt vor den Buchstaben auf der Seite zum Licht: dort streift das Gegenlicht die Kante."""
    T = g.T
    ux, uy = g.X - x0, g.Y - y0
    r = np.hypot(ux, uy) + 1e-9
    di, dj = np.round(uy / r).astype(int), np.round(ux / r).astype(int)
    ii, jj = np.mgrid[0:g.gh, 0:g.gw]
    out = np.zeros(T.shape, bool)
    for k in range(1, n + 1):
        out |= T[np.clip(ii + k * di, 0, g.gh - 1), np.clip(jj + k * dj, 0, g.gw - 1)]
    return out & ~T


def c_randlicht(g):
    """S31d Randlicht: die Buchstaben sind schwarze Koerper vor dem Stern; wo das Licht ihre Kanten streift,
    brennt eine harte, flache Lichtkante. Dazu weiche Schaechte."""
    t, fill, bb, x0, y0, R, rot, d, tt = _gl(g, _behind)
    rays = shafts(g, x0, y0, d, tt, gamma=0.8)
    r = np.hypot(g.X - x0, g.Y - y0)
    rl = rim(g, x0, y0, max(1, round(g.m / g.px / 260)))
    rl &= radial(g, (g.T & (d >= 1)).astype(np.float32), x0, y0, n=220, reach=1.0, decay=1.0) < 0.5   # nur wo Licht hinkommt
    hot = np.exp(-np.maximum(r - R, 0) / (0.9 * R))
    v = bg(g, 0.0, 0.04) + 0.85 * rays
    v = np.where(d < 1, ink(d, 0.8), v)
    v = np.where(rl & (hot > 0.35), 1.0, np.where(rl, np.maximum(v, 0.35 + 0.6 * hot), v))
    _lit_band(g, v, tt, 0.45)
    return _paint(g, t, fill, v)


def _gap_y(g):
    """Hoehe (m) fuer den Lichtstreif: im Durchschuss zwischen den ersten beiden Titelzeilen,
    bei einer Zeile knapp unter der Grundlinie."""
    L = g.c.L
    tb, cap = L["tb"], L["cap"]
    y = (tb[0] + tb[1] - cap) / 2 if len(tb) > 1 else tb[0] + 0.2 * cap
    return y / g.m


def c_flare(g):
    """S31e Flare: der Stern sitzt im Durchschuss, ein anamorpher Lichtbalken laeuft durch die Zeilenluecke ueber
    die ganze Seite, Geisterbilder (Sterne, ein Ring) liegen auf der Achse durch die Seitenmitte."""
    t, fill, bb, x0, y0, R, rot, d, tt = _gl(g, lambda bb: ((bb[0] + bb[2]) * 0.5, _gap_y(g), 0.5 * (bb[3] - bb[1]) + 0.1))
    rays = shafts(g, x0, y0, d, tt, gamma=1.2)
    lp = g.px / g.m
    dy_, dx_ = np.abs(g.Y - y0), np.abs(g.X - x0)
    core = (dy_ < 1.01 * lp) * 1.0
    wing = np.exp(-dy_ / (0.012 + 0.02 * np.exp(-dx_ / 0.5))) * np.exp(-dx_ / (0.9 * g.A))
    v = bg(g, 0.0, 0.04) + 0.7 * rays + 0.75 * wing
    v = np.where(core > 0, np.maximum(v, 0.6 + 0.4 * np.exp(-dx_ / (0.8 * g.A))), v)
    cx, cy = g.A / 2, g.B / 2
    ax, ay = cx - x0, cy - y0
    n_ = np.hypot(ax, ay) + 1e-6
    if n_ < 0.15:                                                    # Stern schon mittig: Achse nach unten
        ax, ay, n_ = 0.0, g.B * 0.5, g.B * 0.5
    ux, uy = ax / n_, ay / n_
    L_ = np.hypot(g.A, g.B)
    for tq, sz, ro, lv in ((0.28, 0.05, 30, 0.42), (0.42, 0.018, 0, 0.8), (0.60, 0.11, 30, 0.22), (0.78, 0.035, 0, 0.55)):
        gx, gy = x0 + ux * tq * L_, y0 + uy * tq * L_
        dg = star(g, gx, gy, sz, rot + ro)
        v = np.where(dg < 1, np.maximum(v, lv * (0.75 + 0.25 * (1 - dg))), v)
    rr = np.hypot(g.X - (x0 + ux * 0.5 * L_), g.Y - (y0 + uy * 0.5 * L_))
    v = np.where(rr < 0.26, np.maximum(v, 0.16 + 0.06 * (rr / 0.26) ** 4), v)   # Bokeh-Scheibe, Rand etwas heller
    v = np.where(d < 1, ink(d, 0.8), v)
    _lit_band(g, v, tt, 0.45, per_pixel=True)
    return _paint(g, t, fill, v)


def c_strahlenkranz(g):
    """S31f Strahlenkranz: harte Lichtkeile strahlen vom Stern hinter dem Titel ueber die ganze Seite,
    die Buchstaben werfen ihre Schatten hinein."""
    t, fill, bb, x0, y0, R, rot, d, tt = _gl(g, _behind)
    X, Y = g.X - x0, g.Y - y0
    r = np.hypot(X, Y)
    th = np.arctan2(Y, X) - np.radians(rot)
    n = 24
    wob = 0.5 + 0.5 * np.cos(n * th + 0.9 * np.sin(3 * th))
    beam = np.clip((wob - 0.35) / 0.4, 0, 1)
    occ = radial(g, (g.T & (d >= 1)).astype(np.float32), x0, y0, n=220, reach=1.0, decay=1.0) > 0.5
    vis = ~occ
    I = beam * np.exp(-np.maximum(r - R, 0) / (0.95 * g.B)) * vis
    halo = np.exp(-np.maximum(r - R, 0) / 0.35)                      # Glut hinter der Zeile, damit die Silhouette steht
    v = bg(g, 0.0, 0.03) + 0.62 * I + 0.45 * halo
    v = np.where(d < 1, ink(d, 0.8), v)
    _lit_band(g, v, tt, 0.45, per_pixel=True)
    return _paint(g, t, fill, v)


def c_linse(g):
    """Ein Sternfoermiges Vergroesserungsglas ueber dem Titel: darin die Schrift riesig, in fremder Farbe."""
    t, fill, bb = title(g)
    x0, y0, R = g.at((bb[2] - 0.26, (bb[1] + bb[3]) / 2 + 0.05, 0.36), (0.60, bb[3] - 0.08, 0.40))
    d = star(g, x0, y0, R, 14)
    k = 2.0
    ci, cj = y0 * g.m / g.px - 0.5, x0 * g.m / g.px - 0.5
    ii, jj = np.mgrid[0:g.gh, 0:g.gw].astype(np.float32)
    mag = map_coordinates(t.astype(np.float32), (ci + (ii - ci) / k, cj + (jj - cj) / k), order=0) > 0.5
    lens_bg = 0.45 + 0.55 * np.clip(1 - d, 0, 1) ** 0.8
    inside = np.where(mag, 0.0, lens_bg + 0.2)
    v = np.where(t, fill, bg(g) + 0.10 * glow(d, 0.2))
    v = np.where((d < 1) & (d > 0.95), 0.0, v)
    return v, [(inside, d < 0.95, ALT)]


def c_luecke(g):
    """Die Seite ist aus grob gekachelten Bloecken gebaut; der Stern ist die Luecke, wo Kacheln fehlen."""
    b = g.at(0.034, 0.034)
    x0, y0, R = g.at((1.22, 0.50, 0.42), (0.50, 0.82, 0.42))
    bi, bj = np.floor(g.Y / b), np.floor((g.X - (g.A % b) / 2) / b)
    cx, cy = (bj + 0.5) * b + (g.A % b) / 2, (bi + 0.5) * b
    D = sd(cx - x0, cy - y0, 14) / R
    ly, lx = g.Y - bi * b, g.X - (g.A % b) / 2 - bj * b
    gap = g.px / g.m * 1.01
    tile_ = (lx > gap) & (ly > gap)
    rng = np.random.default_rng(3)
    jitter = rng.random((int(bi.max()) + 2, int(bj.max()) + 2))[bi.astype(int), bj.astype(int)]
    val = 0.16 + 0.22 * (1 - np.clip((D - 1) / 1.6, 0, 1)) + 0.08 * jitter
    rim = (D >= 1) & (D < 1.18)
    val = np.where(rim, 0.78, val)
    return np.where(tile_ & (D >= 1), val, np.where(D < 1, 0.0, bg(g, 0.0, 0.03)))


def c_escher(g):
    """Kleiner und kleiner: ein konformes Sternparkett, das sich zum Zentrum ins Unendliche zieht (Escher)."""
    x0, y0, R = g.at((1.25, 0.52, 0.55), (0.5, 0.84, 0.5))
    x, y = g.X - x0, g.Y - y0
    r = np.hypot(x, y) + 1e-6
    n = 12
    P = 2 * np.pi / n
    u = np.log(r / R)
    v = np.arctan2(y, x) + 0.35 * u
    ring = np.floor(u / P)
    v = v + (ring % 2) * P / 2
    lu, lv = (u / P % 1 - 0.5) * P, (v / P % 1 - 0.5) * P
    par = sd(lv, lu, 0) < 0.42 * P
    d = star(g, x0, y0, R, 14)
    par ^= d < 0.62
    lum = 0.25 + 0.72 * np.clip(1 - r / (R * 1.6), 0, 1) ** 0.7
    return np.where(par & (r < R * 1.6) & (r > 0.004), lum, bg(g))


# ---------------------------------------------------------------- Brand-Serie (S34 ff.): eingebrannt, verkohlt, geschmolzen
# Wertraum = Hitze: auf Nachtpaletten glueht es, auf Papierpaletten (Riso, Eis, Zitrone) wird dieselbe Hitze zu Brandspur.

def fbm(g, s, seed=0, octs=4, X=None, Y=None):
    """fBm-Wertrauschen, Massstab s in m (aufloesungsunabhaengig), grob in [-1, 1], fester Seed."""
    X, Y = (g.X if X is None else X), (g.Y if Y is None else Y)
    rng = np.random.default_rng(seed)
    acc, tot = np.zeros(np.shape(X), np.float32), 0.0
    for o in range(octs):
        lat, f, a = rng.random((64, 64)).astype(np.float32), 2 ** o / s, 0.5 ** o
        acc += a * map_coordinates(lat, ((Y * f) % 64, (X * f) % 64), order=3, mode="grid-wrap")
        tot += a
    return np.clip((acc / tot - 0.5) * 3.2, -1, 1)


def cells(g, s, seed=0, X=None, Y=None):
    """Voronoi (Zellgroesse s in m): Abstand zum naechsten und zweitnaechsten Kern (in Zellen), Zufallswert der
    Zelle und ihr Kern in m."""
    X, Y = (g.X if X is None else X), (g.Y if Y is None else Y)
    u, w = X / s, Y / s
    iu, iw = np.floor(u), np.floor(w)
    J = np.random.default_rng(seed).random((3, 97, 97))
    f1, f2 = np.full(u.shape, 9.0), np.full(u.shape, 9.0)
    h, ku, kw = np.zeros(u.shape), np.zeros(u.shape), np.zeros(u.shape)
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            cu, cw = iu + a, iw + b
            ki, kj = (cw % 97).astype(int), (cu % 97).astype(int)
            pu, pw = cu + J[0, ki, kj], cw + J[1, ki, kj]
            dd = np.hypot(pu - u, pw - w)
            nr = dd < f1
            f2 = np.where(nr, f1, np.minimum(f2, dd))
            h, ku, kw = np.where(nr, J[2, ki, kj], h), np.where(nr, pu, ku), np.where(nr, pw, kw)
            f1 = np.where(nr, dd, f1)
    return f1, f2, h, ku * s, kw * s


def dots(g, acc, xs, ys, vals):
    """Punkte (m) ins logische Raster, es gilt das Maximum."""
    i, j = np.floor(ys * g.m / g.px).astype(int), np.floor(xs * g.m / g.px).astype(int)
    ok = (i >= 0) & (i < g.gh) & (j >= 0) & (j < g.gw)
    np.maximum.at(acc, (i[ok], j[ok]), np.broadcast_to(vals, xs.shape)[ok])


def c_brandmal(g):
    """S34 Brandmal: mit dem Eisen in die Seite gebrannt. Weissgluehender Abdruckrand, verkohltes Inneres mit
    gluehenden Rissen, aussen ein Sengring, der in Fingern und Russflecken ausfranst."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.22, 0.56, 0.42), (0.56, 1.02, 0.42)))
    d = star(g, x0, y0, R, g.ro(14))
    n1, n2 = fbm(g, 0.35 * R, 341), fbm(g, 0.07 * R, 342)
    dn = d + 0.05 * n1 + 0.025 * n2                                   # das Eisen drueckt nicht ueberall gleich
    f1, f2, h, _, _ = cells(g, 0.10 * R, 34, g.X + 0.015 * R * n2, g.Y)
    hot = np.clip((dn - 0.35) / 0.65, 0, 1) ** 1.5                  # zum Rand hin heisser
    crack = (f2 - f1) < 0.06 + 0.10 * hot
    v_in = np.where(crack, 0.45 + 0.55 * hot, 0.10 + 0.10 * h + 0.18 * hot)
    w = np.clip(0.20 + 0.18 * n1 + 0.06 * n2, 0.03, None)             # Sengring mit Fingern
    sc = np.exp(-np.maximum(dn - 1, 0) / w)
    soot = (n2 > 0.35) & (sc > 0.15) & (sc < 0.7)                      # Russflecken im Sengring
    v_out = bg(g) + 0.85 * sc ** 1.4 - 0.25 * soot * sc
    rim_ = (dn >= 0.88) & (dn < 1)
    v = np.where(dn < 1, np.where(rim_, 1.0, v_in), v_out)
    g.lit = clean(rim_, 1)
    return _paint(g, t, fill, np.clip(v, 0, 1))


def c_durchgebrannt(g):
    """S35 Durchgebrannt: die Seite brennt entlang des Sterns durch. Das Loch ist Nichts, davor ein Glutsaum,
    ein verkohlter Rand und Brandnester, die sich vor der Front in die Seite fressen."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.22, 0.56, 0.44), (0.56, 1.02, 0.44)))
    d = star(g, x0, y0, R, g.ro(14))
    n1, n2, n3 = fbm(g, 0.30 * R, 351), fbm(g, 0.06 * R, 352), fbm(g, 0.10 * R, 353)
    P = d - 1 + 0.12 * n1 + 0.035 * n2                                # Brandfront, < 0 = weg
    nests = (0.55 - n3) * 0.9 + 0.8 * np.maximum(P, 0)             # kleine Loecher kurz vor der Front
    P = np.minimum(P, nests)
    page = bg(g, 0.28, 0.08) + 0.03 * n2
    sear = np.clip((P - 0.08) / 0.40, 0, 1)                          # 0 an der Kohle, 1 = unversehrte Seite
    v = np.where(P < 0, 0.0, np.where(P < 0.035, 1.0, np.where(P < 0.075, 0.62, 0.03 + (page - 0.03) * sear ** 0.8)))
    g.lit = clean((P >= 0) & (P < 0.075), 1)
    return _paint(g, t, fill, v)


def c_schmelze(g):
    """S36 Schmelze: der Stern sackt zusammen und laeuft aus. Tropfen ziehen mit der Schwerkraft nach unten,
    einige erreichen den Seitenrand und sammeln sich dort als Lache."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.20, 0.40, 0.38), (0.56, 0.80, 0.38)))
    rot = g.ro(14)
    s = np.clip((g.Y - (y0 - R)) / (2 * R), 0, 1)                     # 0 oben, 1 unten
    d = sd((g.X - x0) / (1 + 0.28 * s ** 2), g.Y - y0 - 0.32 * R * s ** 2, rot) / R   # unten breit gelaufen, abgesackt
    M = d < 1
    lp = g.px / g.m
    X1 = g.X[0]
    rng = np.random.default_rng(36)
    L = 0.012 + 0.025 * np.clip(fbm(g, 0.05 * R, 361)[0] + 0.3, 0, 1)   # ueberall ein wenig Lauf
    hl = np.zeros(g.gw, bool)
    pool = np.zeros(g.gw)
    bulbs = []
    rows = np.arange(g.gh)[:, None]
    last = np.maximum.accumulate(np.where(M, rows, -10 ** 6), axis=0)
    for k in range(16):
        xk = x0 + R * rng.uniform(-0.9, 0.9)
        wk = R * rng.uniform(0.025, 0.07)
        lk = 9.0 if k % 4 == 0 else R * rng.uniform(0.15, 1.3)         # jeder vierte laeuft bis unten
        u = (X1 - xk) / wk
        L = np.maximum(L, lk * np.clip(1 - u ** 2, 0, 1) ** 0.25)
        hl |= (u > -0.75) & (u < -0.35)
        if lk > 5:
            pool += 0.035 * np.exp(-((X1 - xk) / (4 * wk + 0.03)) ** 2)
        else:
            j = int(np.clip(round(xk / lp), 0, g.gw - 1))
            if M[:, j].any():
                bulbs.append((xk, np.nonzero(M[:, j])[0].max() * lp + lk, 1.25 * wk))
    dist = (rows - last) * lp
    drip = (last >= 0) & (dist <= L[None, :]) & ~M
    for bx, by, br in bulbs:
        drip |= np.hypot(g.X - bx, g.Y - by) < br
    ii, jj = np.mgrid[0:g.gh, 0:g.gw].astype(np.float32)
    wob = 0.05 * R * np.clip(dist / R, 0, 1) * np.sin(g.Y / (0.12 * R) + 3 * fbm(g, 0.3 * R, 362)) / lp   # Laeufe schlingern
    warp = lambda m: map_coordinates(m.astype(np.float32), (ii, jj + wob), order=0) > 0.5            # noqa: E731
    hl2, drip = warp(drip & hl[None, :]), warp(drip) & ~M
    pl = g.Y > g.B - 0.012 - pool[None, :]
    v = bg(g) + 0.12 * glow(d, 0.3)
    v = np.where(pl, np.where(g.Y < g.B - 0.012 - pool[None, :] + 1.5 * lp, 1.0, 0.72), v)
    v = np.where(drip, np.where(hl2, 1.0, 0.92 - 0.35 * np.clip(dist / 0.8, 0, 1)), v)
    v = np.where(M, ink(d, 0.6), v)
    g.lit = clean((M | drip | pl) & (v >= 0.5), 1)
    return _paint(g, t, fill, v)


def c_einbrennen(g):
    """S37 Einbrennen: der Stern hat sich in den Schirm gebrannt. Er selbst hell, dahinter eine Kette von
    Nachbildern in der Zweitfarbe (wie auf der Netzhaut), jedes blasser und in mehr Zeilen zerfallen."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.30, 0.62, 0.36), (0.62, 1.10, 0.36)))
    rot = g.ro(14)
    d = star(g, x0, y0, R, rot)
    a = np.radians(g.at(165, 150))                                  # nach links unten, weg vom Titel
    ii = np.arange(g.gh)[:, None]
    v2, m2 = np.zeros(d.shape), np.zeros(d.shape, bool)
    for k in range(9, 0, -1):                                        # hinten zuerst, das juengste liegt oben
        off = 0.30 * R * k ** 1.15
        dk = star(g, x0 + off * np.cos(a), y0 + off * np.sin(a), R * (1 + 0.06 * k), rot - 6 * k)
        sk = (dk < 1) & ((ii % (1 + k // 2 + 1)) < 2 if k > 1 else True)   # zerfaellt in Zeilen
        edge = (dk < 1) & (dk > 1 - 0.10)
        lvl = 0.95 * 0.8 ** k
        v2 = np.where(sk | edge, np.where(edge, min(1.0, 1.4 * lvl), lvl), np.where(dk < 1, 0.0, v2))
        m2 |= dk < 1
    s = d < 1
    v = np.where(s, ink(d, 0.75), bg(g) + 0.14 * glow(d, 0.3))
    g.lit = clean(s, 1)
    return _paint(g, t, fill, v), [(v2, m2 & ~s & ~(t > 0), ALT)]


def c_glut(g):
    """S38 Glut: der Stern ist ein Haufen Glutbrocken, zum Rand hin kaelter und broeckelnd; Funken steigen
    in kurzen, geraden Bahnen auf (Belichtung 1/15 s)."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.22, 0.60, 0.42), (0.56, 1.06, 0.42)))
    rot = g.ro(14)
    d = star(g, x0, y0, R, rot)
    f1, f2, h, kx, ky = cells(g, 0.075 * R, 38)
    dk = sd(kx - x0, ky - y0, rot) / R
    keep = h > 0.3 * np.clip((dk - 1.05) / 0.3, 0, 1)                # am Rand fallen Brocken heraus
    ember = (d < 1) & keep & ((f2 - f1) > 0.12)
    heat = (0.35 + 0.65 * h ** 0.7) * np.clip(1.25 - 0.45 * dk, 0.5, 1)
    core = np.clip(1 - f1 / 0.8, 0, 1)
    v = bg(g) + 0.24 * glow(d, 0.3)
    v = np.where((d < 1) & ~ember, 0.06, v)                          # Asche zwischen den Brocken
    v = np.where(ember, np.clip(0.2 + heat * (0.3 + 0.8 * core), 0, 1), v)
    acc = np.zeros(d.shape)
    rng = np.random.default_rng(380)
    lp = g.px / g.m
    for _ in range(220):
        th = rng.uniform(0, 2 * np.pi)
        r0 = R * star_r(np.cos(th), np.sin(th), rot) * rng.uniform(0.5, 1.0)
        sx, sy = x0 + r0 * np.cos(th), y0 + r0 * np.sin(th)
        fly = R * rng.exponential(0.7)                                # wie weit er schon ist
        a = np.radians(-90 + rng.normal(0, 30)) + 0.4 * np.cos(th)
        hx, hy = sx + fly * np.cos(a) + 0.2 * fly * np.cos(th), sy + fly * np.sin(a)
        ln = R * rng.uniform(0.05, 0.22)                                # Strich = Bewegung waehrend der Belichtung
        tt = np.linspace(0, 1, max(3, int(ln / lp * 1.5)))
        lv = np.clip(1.2 - fly / (3 * R), 0.6, 1)
        dots(g, acc, hx - ln * np.cos(a) * (1 - tt), hy - ln * np.sin(a) * (1 - tt), lv * (0.3 + 0.7 * tt))
    v = np.maximum(v, acc)
    g.lit = clean(ember & (v >= 0.5), 1)
    return _paint(g, t, fill, v)


def c_filmbrand(g):
    """S39 Filmbrand: der Stern brennt durch die Emulsion. Er selbst ausgeblendet weiss, drumherum schmilzt der
    Film in Blasen, gross am Stern, klein nach aussen, jede mit verkohltem Saum."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.22, 0.56, 0.40), (0.56, 1.02, 0.40)))
    d = star(g, x0, y0, R, g.ro(14))
    n1, n2 = fbm(g, 0.4 * R, 391), fbm(g, 0.05 * R, 392)
    dw = d + 0.10 * n1 + 0.03 * n2
    zone = np.clip(1 - (dw - 1) / 1.3, 0, 1)
    v = bg(g, 0.02, 0.04) + 0.30 * zone ** 3 + 0.5 * np.exp(-np.maximum(dw - 1.05, 0) / 0.18)   # Emulsion glueht am Stern
    for s, sd_, gain in ((0.16 * R, 393, 0.62), (0.06 * R, 394, 0.55)):
        f1, _, h, _, _ = cells(g, s, sd_, g.X + 0.2 * s * n2, g.Y)
        rb = gain * zone ** 1.6 * (0.55 + 0.45 * h)
        bub = f1 < rb
        seam = (f1 >= rb) & (f1 < rb + 0.16) & (rb > 0.08)
        v = np.where(seam, 0.0, v)
        v = np.where(bub, np.where(f1 > rb - 0.1, 0.75, 1.0), v)
    s_ = dw < 1
    v = np.where(s_, 1.0, np.where((dw < 1.05), 0.0, v))
    g.lit = clean(s_, 1)
    return _paint(g, t, fill, v)


def _gray_scott(F, k, V0, n):
    """Gray-Scott-Reaktionsdiffusion auf festem Raster, F und k duerfen Felder sein."""
    U, V = np.ones(V0.shape), V0.astype(float)
    for _ in range(n):
        lu = np.roll(U, 1, 0) + np.roll(U, -1, 0) + np.roll(U, 1, 1) + np.roll(U, -1, 1) - 4 * U
        lv = np.roll(V, 1, 0) + np.roll(V, -1, 0) + np.roll(V, 1, 1) + np.roll(V, -1, 1) - 4 * V
        uvv = U * V * V
        U += 0.16 * lu - uvv + F * (1 - U)
        V += 0.08 * lv + uvv - (F + k) * V
    return V


def c_verkohlung(g):
    """S40 Verkohlung: Reaktionsdiffusion frisst sich durch den Stern. Innen dichtes Labyrinth wie verkohlte
    Maserung, am Rand loest es sich in Punkte auf, die nach aussen absterben."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.22, 0.56, 0.44), (0.56, 1.02, 0.44)))
    rot = g.ro(14)
    N, ext = 300, 1.5 * R                                             # festes Rechenraster um den Stern
    q = (np.arange(N) + 0.5) / N * 2 * ext - ext
    QX, QY = np.meshgrid(q, q)
    dq = sd(QX, QY, rot) / R
    w = np.clip((dq - 0.92) / 0.35, 0, 1)
    F, k = 0.037 + (0.026 - 0.037) * w, 0.060 + (0.061 - 0.060) * w + 0.012 * np.clip((dq - 1.3) / 0.3, 0, 1)
    V0 = (np.random.default_rng(40).random((N, N)) < 0.02) * (dq < 1) * 0.5
    V = _gray_scott(F, k, V0, 4000)
    ci, cj = (g.Y - y0 + ext) / (2 * ext) * N - 0.5, (g.X - x0 + ext) / (2 * ext) * N - 0.5
    Vg = map_coordinates(V, (ci, cj), order=1, cval=0)
    d = star(g, x0, y0, R, rot)
    pat = np.clip((Vg - 0.12) / 0.2, 0, 1)
    v = np.where(d < 1, 0.18 + 0.82 * pat, bg(g) + 0.1 * glow(d, 0.3) + 0.7 * pat)
    g.lit = clean((d < 1) & (pat > 0.5), 1)
    return _paint(g, t, fill, v)


def c_zerfall(g):
    """S41 Zerfall: der Stern zerbroeselt von unten zu Pixelsand. Die Koerner rieseln in Stroemen herab und
    tuermen sich am Seitenrand zu Haufen (fallender Sand, ein zellulaerer Automat, Momentaufnahme mitten im Fall)."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.22, 0.40, 0.40), (0.56, 0.80, 0.40)))
    rot = g.ro(14)
    d = star(g, x0, y0, R, rot)
    S = d < 1
    e = (g.Y - y0) / R + 0.25 * (g.X - x0) / R + 0.45 * fbm(g, 0.25 * R, 411)
    rng = np.random.default_rng(41)
    thr = 0.05 + 0.45 * rng.random(S.shape)                         # Kruemelzone statt glatter Kante
    gone = S & (e > thr)
    snap = int(0.95 * g.gh)                                          # so viele Schritte, dann Foto
    lo, hi = e[gone].min(), e[gone].max()
    rel = np.where(gone, ((hi - e) / (hi - lo + 1e-6) * 1.15 * snap).astype(int), -1)   # unten zuerst
    stay = S & ~(gone & (rel < snap))                                # spaeter Freigegebenes haengt noch
    sand = np.zeros(S.shape, bool)
    hh = np.arange(g.gh)[:, None]
    for step in range(snap):
        sand |= rel == step
        occ = stay | sand
        below = np.roll(occ, -1, 0)
        below[-1] = True
        mv = sand & ~below
        sand = (sand & ~mv) | np.roll(mv, 1, 0)
        occ = stay | sand
        for dj in ((1, -1) if step % 2 else (-1, 1)):             # abrutschen, abwechselnd links und rechts
            diag = np.roll(np.roll(occ, -1, 0), -dj, 1)
            sl = sand & np.roll(occ, -1, 0) & ~diag & ~np.roll(occ, -dj, 1) & (hh < g.gh - 1)
            sand = (sand & ~sl) | np.roll(np.roll(sl, 1, 0), dj, 1)
            occ = stay | sand
    v = bg(g) + 0.10 * glow(d, 0.3)
    v = np.where(sand, g.c.lvl(g.N - 2) + (g.c.lvl(g.N) - g.c.lvl(g.N - 2)) * (rng.random(S.shape) < 0.45), v)   # flache Stufen, kein Korn im Korn
    v = np.where(stay, ink(d, 0.6), v)
    g.lit = clean(stay, 1)
    return _paint(g, t, fill, v)


def c_fata(g):
    """S42 Fata Morgana: der Stern ist so heiss, dass die Luft flimmert. Eine Hitzesaeule steigt in gewellten
    Schlieren auf, die oberen Spitzen wabern, und unter der Zeile erscheint der Titel ein zweites Mal, gespiegelt."""
    t, fill, bb = title(g)
    x0, y0, R = g.pos(g.at((1.22, 0.66, 0.40), (0.56, 1.10, 0.40)))
    rot = g.ro(14)
    lp = g.px / g.m
    up_ = np.maximum(y0 - g.Y, 0)
    col = np.exp(-((g.X - x0) / (0.9 * R + 0.35 * up_)) ** 2)            # Saeule, nach oben breiter
    heat = col * np.exp(-up_ / (2.5 * R)) * np.clip((y0 + 0.3 * R - g.Y) / (0.6 * R), 0, 1)
    turb = fbm(g, 0.5 * R, 421, 3, X=g.X, Y=g.Y * 0.35) + 0.5 * fbm(g, 0.15 * R, 422, 3, X=g.X, Y=g.Y * 0.5)
    dx = heat * R * (0.05 * np.sin(g.Y / (0.05 * R) + 2.5 * turb) + 0.05 * turb)
    d = sd(g.X + dx * (g.Y < y0) - x0, g.Y - y0, rot) / R
    ph = (g.X - x0 + 0.25 * R * turb * (1 + up_ / R)) / (0.045 * R)
    schl = (np.sin(ph) > 0.55) * heat                                 # Schlieren: gewellte Hitzelinien
    cap = bb[3] - bb[1]
    my = 2 * bb[3] + 0.25 * cap - g.Y                                # Spiegelbild unter der Zeile
    wav = 0.006 * np.sin(g.Y / 0.008 + 2 * turb) + 0.012 * turb
    mir = map_coordinates(g.T.astype(np.float32), (my / lp - 0.5, (g.X + wav) / lp - 0.5), order=0, cval=0) > 0.5
    fade = np.clip(1 - (g.Y - bb[3]) / (1.15 * cap), 0, 1) * (g.Y > bb[3])
    v = bg(g) + 0.16 * glow(d, 0.4) + 0.2 * heat + 0.45 * schl
    hi = 0.6 if not g.poster else 0.15                               # Plakat: leise, darunter steht das Datum
    v = np.where(mir & (fade > 0), np.maximum(v, 0.2 + hi * fade), v)
    v = np.where(d < 1, ink(d, 0.7), v)
    g.lit = clean(d < 1, 1)
    return _paint(g, t, fill, np.clip(v, 0, 1))


def c_wunderkerze(g):
    """S43 Wunderkerze: der Stern mit einer Wunderkerze in die Nacht gemalt (Langzeitbelichtung). Die Spur
    gluehend, ueberall spruehen verzweigte Funken, am Kopf der Kerze ein Funkenball."""
    t, fill, _ = title(g)
    x0, y0, R = g.pos(g.at((1.22, 0.56, 0.42), (0.56, 1.02, 0.42)))
    rot = g.ro(14)
    lp = g.px / g.m
    th0 = np.radians(rot + 30)
    th = th0 + np.linspace(0, 2 * np.pi * 0.94, 4000)
    rr = R * star_r(np.cos(th), np.sin(th), rot)
    px_, py_ = x0 + rr * np.cos(th), y0 + rr * np.sin(th)
    age = np.linspace(0.45, 1.0, th.size)                             # alte Spur dunkler
    acc = np.zeros((g.gh, g.gw))
    for ox, oy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        dots(g, acc, px_ + ox * lp, py_ + oy * lp, age)
    acc = np.maximum(acc, gaussian_filter(acc, 1.0) * 1.4)
    rng = np.random.default_rng(43)

    def spark(x, y, a, ln, lv, depth):
        tt = np.linspace(0, 1, max(4, int(ln / lp * 1.6)))
        xs, ys = x + ln * np.cos(a) * tt, y + ln * np.sin(a) * tt
        dots(g, acc, xs, ys, lv * (1 - 0.5 * tt))
        if depth:
            for _ in range(rng.integers(2, 4)):                        # Wunderkerzenfunken gabeln am Ende
                spark(xs[-1], ys[-1], a + rng.normal(0, 0.5), ln * rng.uniform(0.15, 0.35), lv * 0.9, depth - 1)

    for n in range(300):
        i = int(th.size * rng.random() ** 0.6)
        spark(px_[i], py_[i], rng.uniform(0, 2 * np.pi), R * rng.exponential(0.09), 0.5 + 0.5 * age[i], int(rng.random() < 0.5))
    hx, hy = px_[-1], py_[-1]
    for n in range(90):                                              # Funkenball am Kopf
        spark(hx, hy, rng.uniform(0, 2 * np.pi), R * rng.uniform(0.1, 0.5), 1.0, 1)
    hr = np.hypot(g.X - hx, g.Y - hy)
    d = star(g, x0, y0, R, rot)
    v = bg(g) + 0.10 * glow(d, 0.3) + 0.5 * np.exp(-hr / (0.06 * R))
    v = np.maximum(v, np.clip(acc, 0, 1))
    v = np.where(hr < 0.035 * R + lp, 1.0, v)
    g.lit = clean(acc > 0.6, 1)
    return _paint(g, t, fill, np.clip(v, 0, 1))


# ---------------------------------------------------------------- Licht-Serie (S44 ff.): der Stern als Koerper im Licht
# Fuer den Kick-off-Loop (30.9.): Hoehenrelief auf dem Stern, festes Licht von oben (leicht links vorn), Bayer 4x4.
# Der Stern steht immer frontal (Vadim 30.9.: keine 3D-Kippung); er dreht sich aber in sich (spin_deg), das feste Licht
# wandert dabei ueber Firste und Flaechen: so liest sich der flache Stern als Koerper, ohne die Silhouette zu verlassen
# (Relief und Schatten liegen nur innen, aussen nur ein leiser Schein).
LIGHT = np.array([-0.25, -0.60, 0.76]) / np.linalg.norm([-0.25, -0.60, 0.76])   # x rechts, y unten, z zum Betrachter
# (fast von oben: der Stern kommt links ins Bild und geht rechts raus, beide Seiten brauchen Licht auf den Spitzen)
VIEW = np.array([0.0, 0.0, 1.0])
TIP_DEG, INNER_R = 30, 0.45                     # Logo-Profil (makernight_sparks.PROF): Spitzen bei rot+30+60k, Kerben r=0.45
PLACE = ((1.20, 0.52, 0.48), (0.56, 0.80, 0.48))   # Lab-Platzierung (quer, hoch); im Loop setzt kickoff.spark g.K


def _local(g, rot0=14):
    """Hauptplatzierung + Sternkoordinaten in Sternradien."""
    x0, y0, R = g.pos(g.at(*PLACE))
    rot = g.ro(rot0)
    return x0, y0, R, rot, (g.X - x0) / R, (g.Y - y0) / R


def _shade(h, x, y, amp, e=2e-3):
    """Lambert + Glanz eines Hoehenfelds h(x, y) (Sternradien). amp = Reliefhoehe: groesser = steilere Flanken."""
    h0 = h(x, y)
    nx, ny = -amp * (h(x + e, y) - h0) / e, -amp * (h(x, y + e) - h0) / e
    nn = np.sqrt(nx * nx + ny * ny + 1)
    lam = (nx * LIGHT[0] + ny * LIGHT[1] + LIGHT[2]) / nn
    H = (LIGHT + VIEW) / np.linalg.norm(LIGHT + VIEW)
    spec = np.clip((nx * H[0] + ny * H[1] + H[2]) / nn, 0, 1) ** 24
    return np.clip(lam, 0, 1), spec


def _facets(x, y, rot, amp):
    """Kristall: jede Spitze ein First, jede Kerbe ein Tal, 12 ebene Flaechen (Sektoren zu 30 Grad). Pro Pixel die
    (nicht normierte) Normale seiner Flaeche: Ebene durch Mitte (Hoehe amp), Spitze und Kerbe (Hoehe 0)."""
    th = (np.degrees(np.arctan2(y, x)) - rot - TIP_DEG) % 360
    j = np.floor(th / 30).astype(int)                                       # Sektor 0..11, gerade = Spitze -> Kerbe
    tip = np.radians(rot + TIP_DEG + 60 * ((j + 1) // 2))
    kerbe = np.radians(rot + TIP_DEG + 30 + 60 * (j // 2))
    tx, ty = np.cos(tip), np.sin(tip)
    ix, iy = INNER_R * np.cos(kerbe), INNER_R * np.sin(kerbe)
    det = tx * iy - ty * ix                                                 # m mit m.T = 1, m.I = 1 -> h = amp (1 - m.p)
    mx, my = (iy - ty) / det, (tx - ix) / det
    return amp * mx, amp * my


def c_relief(g):
    """S44 Relief: der Stern als geschliffene Pyramide (Firste zu den Spitzen), im Streiflicht von oben;
    Lambert + Glanz im Bayer-Korn. Dreht sich der Stern, wandert das Licht ueber die Firste."""
    x0, y0, R, rot, x, y = _local(g)
    d = sd(x, y, rot)
    lam, spec = _shade(lambda a, b: 1 - sd(a, b, rot), x, y, 0.45)
    v = np.where(d < 1, 0.40 + 0.60 * lam + 0.45 * spec, bg(g) + 0.10 * glow(d, 0.3))   # 0.40 = Umgebungslicht
    g.lit = (d < 1) & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_facette(g):
    """S45 Facette: derselbe Kristall als Cel-Shading. Jede der 12 Flaechen ein flacher Ton; Licht = exakte Stufen
    (flaechig), Schatten = Zwischenwert, den Bayer 4x4 zu einem regelmaessigen Punktraster macht (Ben-Day auf dem
    Pixelraster)."""
    x0, y0, R, rot, x, y = _local(g)
    d = sd(x, y, rot)
    mx, my = _facets(x, y, rot, 0.9)
    lam = (mx * LIGHT[0] + my * LIGHT[1] + LIGHT[2]) / np.sqrt(mx * mx + my * my + 1)
    N = g.N
    tone = np.select([lam > 0.80, lam > 0.55, lam > 0.30],                        # 4 Toene: 2 flach, 2 als Punktraster
                     [1.0, (N - 1) / N, (N - 2 + 0.5) / N], (N - 3 + 0.25) / N)
    v = np.where(d < 1, tone, bg(g) + 0.10 * glow(d, 0.3))
    g.lit = (d < 1) & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_stufen(g):
    """S46 Stufen: die Matrjoschka-Schalen (S33) als Stufenpyramide gebaut, im Streiflicht. Jede Stufe eine flache
    Terrasse (exakte Stufe, heller nach oben), die Kante zum Licht leuchtet, zur anderen Seite faellt ein Schlagschatten
    auf die Stufe darunter (im Punktraster)."""
    x0, y0, R, rot, x, y = _local(g)
    d = sd(x, y, rot)
    T, rise = 5, 0.05                           # Stufen; Stufenhoehe in Sternradien (bestimmt die Schattenlaenge)
    step = lambda a, b: np.ceil(np.clip(1 - sd(a, b, rot), 1e-6, 1) * T)   # noqa: E731  Terrasse 1 (aussen) .. T
    k0 = step(x, y)
    lh = np.hypot(LIGHT[0], LIGHT[1])
    ux, uy, tan = LIGHT[0] / lh, LIGHT[1] / lh, LIGHT[2] / lh   # Richtung zum Licht, Steigung des Lichtstrahls
    shadow = np.zeros(d.shape, bool)
    for s in np.linspace(0.005, 0.10, 10):                  # liegt eine hoehere Stufe zwischen Pixel und Licht?
        shadow |= (step(x + s * ux, y + s * uy) - k0) * rise > s * tan
    lip = (step(x + 0.025 * ux, y + 0.025 * uy) < k0) & ~shadow   # Stufenkante, die zum Licht schaut
    N = g.N
    top = np.round(N - 2 + (k0 - 1) / (T - 1) * 2) / N          # Terrassen: exakte Stufen N-2 (aussen) .. N (Gipfel)
    v = np.where(shadow, top - 1.25 / N, top)                   # Schatten: eine Stufe tiefer + Punktraster
    v = np.where(lip, 1.0, v)
    v = np.where(d < 1, v, bg(g) + 0.10 * glow(d, 0.3))
    g.lit = (d < 1) & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_praegung(g):
    """S47 Praegung: das XOR-Nest (S7) als Hochdruck. Die leuchtenden Flaechen sind erhabene Platten, das Licht von
    oben setzt an jede Plattenkante eine Lichtkante (zum Licht) und einen Schatten (vom Licht weg). Aussenring = Platte:
    die Silhouette bleibt der volle Stern."""
    x0, y0, R, rot, x, y = _local(g)
    d = sd(x, y, rot)
    par = np.zeros(d.shape, bool)
    for k in range(6):                                           # wie styles.spark "nest": 6 Sterne, 0.74, +30 Grad
        par ^= sd(x, y, rot + 30 * k) < 0.74 ** k
    h = gaussian_filter(par.astype(np.float32), 0.8)
    lh = np.hypot(LIGHT[0], LIGHT[1])
    off = (LIGHT[1] / lh * 1.5, LIGHT[0] / lh * 1.5)             # 1.5 Zellen zum Licht hin (Zeile, Spalte)
    edge = h - map_coordinates(h, (g.c.yy + off[0], g.c.xx + off[1]), order=1, mode="nearest")
    v = np.where(par, 0.60 + 0.30 * np.clip(1 - d, 0, 1), 0.20 * (d < 1)) - 1.1 * edge
    v = np.where(d < 1, v, bg(g) + 0.10 * glow(d, 0.3))
    g.lit = (d < 1) & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_lampe(g):
    """S31g Lampe: der Stern selbst ist die Lichtquelle (Gegenlicht, silhouettentreu): er glueht, seine Spitzen werfen
    Lichtbahnen ueber die Seite, der Titel wirft Schatten hinein. Kerben bleiben dunkel, der Umriss steht."""
    t, fill, bb = title(g)
    x0, y0, R, rot, x, y = _local(g)
    d = sd(x, y, rot)
    tt = binary_dilation(g.T, iterations=1)
    emit = np.where(tt, 0.0, np.where(d < 1, 1.0, 0.5 * np.exp(-(d - 1) / 0.15)))
    acc = radial(g, emit, x0, y0, n=120, reach=0.99, decay=0.99, order=1)
    ring = acc[(d > 1.0) & (d < 1.2)]                   # Saum direkt am Stern; leer, wenn der Stern nur mit einer Spitze
    ref = (np.percentile(ring, 90) if ring.size else acc.max()) + 1e-6   # hereinragt (Bahn neben dem Plakat)
    rays = np.clip(acc / ref, 0, 1) ** 2.2              # hoher Exponent: Bahnen aus den Spitzen, Kerben bleiben dunkel
    v = bg(g, 0.0, 0.04) + 0.75 * rays
    v = np.where(d < 1, ink(d, 0.8), v)
    g.lit = v >= 0.5                                     # normale XOR-Regel: Schrift kippt auf hellen Bahnen
    return _paint(g, t, fill, np.clip(v, 0, 1))


def c_interferenz_innen(g):
    """S18d Moire im Stern: zwei Hoehenlinien-Sterne (S18), um 30 Grad verdreht und leicht versetzt, per XOR, aber nur
    in der Silhouette; harter Rand, damit die Spitzen spitz bleiben. Das Moire dreht mit, der Umriss steht."""
    x0, y0, R, rot, x, y = _local(g)
    d = sd(x, y, rot)
    d1, d2 = sd(x + 0.10, y - 0.06, rot), sd(x - 0.10, y + 0.06, rot + 30)
    par = (rings(d1, 5.0) ^ rings(d2, 5.0)) & (d < 0.86)
    par |= (d >= 0.86) & (d < 1)
    g.lit = par
    return np.where(par, ink(d * 0.9, 0.55), bg(g) + 0.12 * glow(d, 0.3))


# ---------------------------------------------------------------- Spider-Verse-Serie (1.10., Kick-off-Loop)
# Alle frontal, silhouettentreu, folgen der Bahn (_local). Inspiration + Quellen: kickoff_loop/ref/spiderverse/README.md.

SV_LABEL_CELLS = 13          # JOIN US ueber der QR-Platte: Versalhoehe 9 + Abstand 4 Zellen (loop.toml [qr])
ZINE_CUTS = 6                # S52: gerade Schnitte pro halber Flanke (Spitze → Kerbe); 1 = gerader Stern, Kurve weg
SV_CELL_MIN = 1.3            # kleinste Punkt-/Kreisgroesse in Zellen: darunter zerfaellt ein Kreis auf dem Raster


def _cell(g):
    """Eine Zelle in m-Einheiten (kurze Seite = 1)."""
    return g.px / g.m


def _polar(x0, y0, R, rot, a, dval):
    """Punkt in Sternkoordinaten → Seite (m): Winkel a relativ zur Drehung (Grad), dval = Anteil des Sternprofils in
    dieser Richtung (1 = auf dem Umriss). Dreht mit dem Stern."""
    th = np.radians(rot + a)
    r = dval * R * star_r(np.cos(th), np.sin(th), rot)
    return x0 + r * np.cos(th), y0 + r * np.sin(th)


def _disk(g, acc, cx, cy, rad, lobes=None):
    """Kreis (m) in die Maske acc odern, nur im Fenster gerechnet. lobes = (Anzahl, Tiefe, Phase): Tintenklecks statt
    Kreis (Radius schwankt mit dem Winkel)."""
    rad = max(rad, SV_CELL_MIN * _cell(g))
    px = _cell(g)
    j0, j1 = max(0, int((cx - 1.3 * rad) / px) - 1), min(g.gw, int((cx + 1.3 * rad) / px) + 2)
    i0, i1 = max(0, int((cy - 1.3 * rad) / px) - 1), min(g.gh, int((cy + 1.3 * rad) / px) + 2)
    if j0 >= j1 or i0 >= i1:
        return
    dx, dy = g.X[i0:i1, j0:j1] - cx, g.Y[i0:i1, j0:j1] - cy
    r = rad
    if lobes:
        k, depth, ph = lobes
        r = rad * (1 + depth * np.sin(k * np.arctan2(dy, dx) + ph))
    acc[i0:i1, j0:j1] |= dx * dx + dy * dy < r * r


def _qr_zone(g, pad_cells=6):
    """JOIN US + QR-Platte (unten links, kickoff.layout) plus Rand, in m: dort keine kleinteiligen Details, sonst
    verschwinden Buchstaben von JOIN US beim Kippen (Befund 1.10.: S50-Linie, S53-Loch unter dem N)."""
    L, c = g.c.L, _cell(g)
    label = SV_LABEL_CELLS * c
    x1 = (L.get("x0", L["m"]) + L["qs"]) / g.m + pad_cells * c
    y0 = (L["qbot"] - L["qs"]) / g.m - label - pad_cells * c
    return (g.X < x1) & (g.Y > y0)


def _type_zone(g):
    """Titelblock (SPARK bis Datum, ganze Breite) in m: dort keine Deko ausserhalb der Grundform, sonst sinkt die
    Lesbarkeit und der Satz wird unruhig (Konstruktionslinien, Halbton-Schein, Schraffur)."""
    L = g.c.L
    return g.Y < (L["db"] + 0.6 * L["capd"]) / g.m


def _star_noise(g, x, y, rot, sigma, seed):
    """Weiches Rauschen in Sternkoordinaten (dreht mit dem Stern, steht auf ihm fest), -1..1 grob normiert."""
    n = gaussian_filter(np.random.default_rng(seed).standard_normal((160, 160)), sigma)
    n /= 2.5 * n.std()
    a = np.radians(-rot)
    u, w = x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)       # zurueckgedreht: Muster sitzt auf dem Stern
    return map_coordinates(n, ((w + 1.6) / 3.2 * 159, (u + 1.6) / 3.2 * 159), order=1, mode="grid-wrap")


def c_fehldruck(g):
    """S48 Fehldruck (ITSV, Miles' Brooklyn): der Stern in zwei Druckplatten, die Farbplatte um ganze Zellen nach unten
    rechts verrutscht. Versatz = Tiefe wie im Film (Unschaerfe = Plattenversatz): fern 3 Zellen, ganz nah 6. Nur Schwarz-
    platte = hellste Stufe, Uebereinander = eine Stufe tiefer mit Ben-Day-Schatten (Bayer als Punktraster) auf der
    lichtabgewandten Seite, nur Farbplatte = Mittelstufe. Der Umriss der Schwarzplatte ist der Stern.
    Vadim 1.10.: "richtig gut", alles unter den Dither -> auch die hellen Flaechen tragen jetzt einen Lichtverlauf (Korn)."""
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    k = int(np.clip(round(2 + 5 * R), 3, 6))                           # fern 3, nah 6 Zellen (A3: 3-6 mm)
    d = sd(x, y, rot)
    key, col = d < 1, sd(x - k * c / R, y - k * c / R, rot) < 1
    lh = np.hypot(LIGHT[0], LIGHT[1])
    lit_side = (x * LIGHT[0] + y * LIGHT[1]) / lh                     # > 0: zum Licht (oben links)
    over = np.where(lit_side > -0.12, (N - 1) / N, (N - 1.5) / N)     # Schatten: Ben-Day, halb Punkte eine Stufe tiefer
    off = 1 / N - _dithered(1, _lightfield(x, y, d), N)               # Vadim 1.10.: alles unter den Dither (auch das Weiss)
    v = np.select([key & col, key, col], [over - off, 1.0 - off, (N - 2.5) / N - 0.5 * off], bg(g) + 0.10 * glow(d, 0.3))
    g.lit = key & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_krackle(g):
    """S49 Krackle (Jack Kirby, ITSV-Kollider): um den Stern steht ein Energiesaum in der Mittelstufe, getrennt durch
    einen dunklen Spalt (die Silhouette bleibt der Stern), und Kirby-Punkte (Trauben schwarzer Kreise) stanzen den
    Saum aus, dicht an seiner Aussenkante. Saum fern breit, nah schmal (in Seiteneinheiten begrenzt, Titel)."""
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    d = sd(x, y, rot)
    gap = 1 + 2.5 * c / R                                              # dunkler Spalt: 2-3 Zellen
    E = gap + min(0.55, 0.09 / R)                                      # Saum in Sternprofilen
    dots = np.zeros(d.shape, bool)
    rng = np.random.default_rng(49)
    for _ in range(60):                                                # Trauben
        a, t = rng.uniform(0, 360), rng.uniform(0.45, 1.05)
        cx, cy = _polar(x0, y0, R, rot, a, gap + (E - gap) * t)
        size = (E - gap) * R * rng.uniform(0.16, 0.34)
        for j in range(rng.integers(2, 6)):                            # Hauptpunkt + Trabanten
            s_ = size * (1 if j == 0 else rng.uniform(0.3, 0.6))
            o = 0 if j == 0 else size * rng.uniform(1.0, 1.6)
            b = rng.uniform(0, 2 * np.pi)
            _disk(g, dots, cx + o * np.cos(b), cy + o * np.sin(b), s_)
    field = (d >= gap) & (d < E) & ~dots
    fade = np.clip((E - d) / (E - gap), 0, 1)                           # Saum innen heller
    v = np.where(d < 1, ink(d, 0.8), np.where(field, (N - 3 + 1.2 * fade) / N, bg(g)))
    g.lit = (d < 1) | (field & (v >= 0.5))
    return np.clip(v, 0, 1)


def c_fokus(g):
    """S50 Fokuslinien (Manga shuuchuu-sen, ITSV-Speedlines): Keile aus dem Seitenrand laufen spitz auf den Stern zu und
    enden in verschiedenem Abstand vor ihm. Sie sparen den Titelblock aus wie Manga-Linien die Sprechblase (Lesbarkeit).
    JOIN US + QR ebenso. Der Stern: voller Koerper mit dunkler Innenkontur (ausgeschnittene Comicform)."""
    title(g)
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    d = sd(x, y, rot)
    rr, ang = np.hypot(g.X - x0, g.Y - y0), np.arctan2(g.Y - y0, g.X - x0)
    rng = np.random.default_rng(50)
    lines = np.zeros(d.shape, bool)
    for a in np.sort(rng.uniform(0, 2 * np.pi, 110)):
        r0 = R * star_r(np.cos(a), np.sin(a), rot) * rng.uniform(1.3, 2.0)
        w = c * rng.uniform(0.5, 1.8)                                  # halbe Breite am Rand (m)
        da = np.abs((ang - a + np.pi) % (2 * np.pi) - np.pi)
        lines |= (rr > r0) & (da * rr < w * np.clip((rr - r0) / 0.35, 0, 1))
    L = g.c.L
    lines &= ~_type_zone(g) & ~_qr_zone(g)                               # Titelblock und JOIN US + QR bleiben frei
    rim = (d >= 1 - 2 * c / R) & (d < 1)
    v = np.where(d < 1, np.where(rim, (N - 2) / N, ink(d, 0.8)), np.where(lines, (N - 2) / N, bg(g)))
    g.lit = (d < 1) & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_aquarell(g):
    """S51 Aquarell (ATSV, Gwens Earth-65): Lasur mit Pigmentrand. Innen eine unruhige Lasur (weiches Rauschen, das auf
    dem Stern sitzt und mitdreht, Koernung im Bayer), am Umriss sammelt sich das Pigment zur harten, hellsten Kante,
    innen stehen Rueckfluss-Raender (Blueten) als feine helle Linien. Der Umriss bleibt scharf: nasse Farbe auf trockenem
    Papier."""
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    d = sd(x, y, rot)
    wash = 0.70 + 0.16 * _star_noise(g, x, y, rot, 9, 51) + 0.05 * _star_noise(g, x, y, rot, 1.2, 52)
    bloom = np.abs(_star_noise(g, x, y, rot, 7, 53) - 0.25) < 0.9 * c / R          # Bluetenrand: knapp 2 Zellen
    rim = d >= 1 - max(0.05, 2.5 * c / R)
    v = np.where(rim, 1.0, np.where(bloom & (d < 0.9), 1.0, np.clip(wash, 0.54, 0.9)))
    v = np.where(d < 1, v, bg(g) + 0.08 * glow(d, 0.25))
    g.lit = d < 1
    return np.clip(v, 0, 1)


def c_zine(g):
    """S52 Zine (ATSV, Hobie/Spider-Punk): der Stern mit der Schere aus einer Fotokopie geschnitten. Umriss aus geraden
    Schnitten (ZINE_CUTS pro Flanke, leicht daneben), Kopierer-Toner (kleine Flecken) und dunkle Kopierkante im hellen
    Papier, ein Streifen Klebeband ueber einer Spitze (durchscheinend: Schachbrett)."""
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    rng = np.random.default_rng(52)
    pts = []
    for a in np.arange(TIP_DEG, TIP_DEG + 360, 60 / ZINE_CUTS):          # gerade Schnitte, Stuetzpunkte auf dem Profil
        tip = (a - TIP_DEG) % 60 == 0
        pts.append(_polar(x0, y0, R, rot, a, 1 if tip else 1 + rng.uniform(-0.03, 0.015)))

    def cut(dx, dy):
        im = Image.new("1", (g.gw, g.gh), 0)
        ImageDraw.Draw(im).polygon([((px + dx) / c - 0.5, (py + dy) / c - 0.5) for px, py in pts], fill=1)
        return np.asarray(im, bool)
    body = cut(0, 0)
    free = ~_qr_zone(g)
    toner = (_star_noise(g, x, y, rot, 0.7, 54) > 0.5) & free           # Kopierer: kleine Tonerflecken
    edge = body & ~binary_erosion(body) & free                           # Kopierkante: 1 Zelle dunkel am Schnitt
    a = np.radians(rot + 90)                                             # Klebeband quer ueber die untere Spitze
    tx, ty = _polar(x0, y0, R, rot, 90, 0.86)
    u = (g.X - tx) * np.cos(a) + (g.Y - ty) * np.sin(a)
    w = -(g.X - tx) * np.sin(a) + (g.Y - ty) * np.cos(a)
    tape = (np.abs(u) < 0.09 * R) & (np.abs(w) < 0.30 * R)
    checker = (g.c.yy + g.c.xx) % 2 == 0
    v = np.where(body, np.where(toner | edge, (N - 3) / N, 1.0), bg(g))
    v = np.where(tape, np.where(checker, (N - 1) / N, (N - 2) / N), v)
    g.lit = (body | tape) & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_spot(g):
    """S53 Spot (ATSV, The Spot): weisser Gesso-Stern mit schwarzen Tintenloechern (Portale), darunter scheinen die
    Bleistift-Konstruktionslinien durch (Umkreis, Innenkreis, drei Achsen durch die Spitzen, ueber den Umriss hinaus).
    Loecher sind Kleckse (Radius schwankt mit dem Winkel), sitzen fest auf dem Stern und drehen mit."""
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    d = sd(x, y, rot)
    rr = np.hypot(x, y)
    w = max(0.006, 0.6 * c / R)                                           # Bleistift: gut 1 Zelle
    con = (np.abs(rr - 1) < w) | (np.abs(rr - INNER_R) < w)
    for k in range(3):
        a = np.radians(rot + TIP_DEG + 60 * k)
        con |= (np.abs(-x * np.sin(a) + y * np.cos(a)) < w) & (rr < 1.18)
    con &= ~_type_zone(g)
    holes = np.zeros(d.shape, bool)
    rng = np.random.default_rng(53)
    for a, dv, s in [(0, 0.0, 0.16)] + [(rng.uniform(0, 360), rng.uniform(0.25, 0.8), rng.uniform(0.05, 0.13))
                                        for _ in range(11)]:
        cx, cy = _polar(x0, y0, R, rot, a, dv)
        _disk(g, holes, cx, cy, s * R, (int(rng.integers(3, 6)), 0.12, rng.uniform(0, 6.3)))
    holes &= (d < 0.92) & ~_qr_zone(g)
    v = np.where(d < 1, np.where(holes, 0.0, np.where(con, (N - 2) / N, 1.0)),
                 np.where(con, (N - 3) / N, bg(g) + 0.06 * glow(d, 0.25)))
    g.lit = (d < 1) & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_skizze(g):
    """S54 Skizze (ATSV, Leonardos Vulture aus dem Renaissance-Skizzenbuch): der Stern als Pergament mit Federzeichnung.
    Dunkle Kontur, Schraffur auf der lichtabgewandten Seite (45 Grad, im tiefen Schatten gekreuzt), Konstruktion
    (Umkreis, Achsen) laeuft hell ueber den Umriss hinaus auf den dunklen Grund."""
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    d = sd(x, y, rot)
    rr = np.hypot(x, y)
    w = max(0.006, 0.55 * c / R)
    a = np.radians(-rot)
    u, t = x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)
    sp = 4 * c / R                                                         # Strichabstand 4 Zellen (Feder auf Papier)
    lh = np.hypot(LIGHT[0], LIGHT[1])
    lit_side = (x * LIGHT[0] + y * LIGHT[1]) / lh
    h1 = ((u + t) / np.sqrt(2) / sp) % 1 < 0.3
    h2 = ((u - t) / np.sqrt(2) / sp) % 1 < 0.3
    hatch = ((h1 & (lit_side < 0.0)) | (h2 & (lit_side < -0.35))) & ~_qr_zone(g)
    outline = d >= 1 - 2 * c / R                                          # Kontur 2 Zellen
    con = np.abs(rr - 1.0) < w
    for k in range(3):
        b = np.radians(rot + TIP_DEG + 60 * k)
        con |= (np.abs(-x * np.sin(b) + y * np.cos(b)) < w) & (rr < 1.25)
    con &= ~_type_zone(g)
    outline &= ~_type_zone(g)
    hatch &= ~_type_zone(g)
    v = np.where(d < 1, np.where(outline | hatch, (N - 4) / N, (N - 1) / N),
                 np.where(con, (N - 3) / N, bg(g)))
    g.lit = (d < 1) & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_halbton(g):
    """S55 Halbton (ITSV, Ben-Day als Licht): ein echtes Druckraster (runde Punkte, 45 Grad, fest auf der SEITE, nicht
    auf dem Stern): der Stern fliegt unter dem Raster durch wie ein Motiv unter der Rasterfolie. Punktgroesse = Helligkeit,
    innen verschmelzen die Punkte zur Flaeche. Aussen ein Halbton-Schein. Keine Bayer-Mischung: nur flache Stufen."""
    x0, y0, R, rot, x, y = _local(g)
    N = g.N
    d = sd(x, y, rot)
    p = 5.0                                                                # Rasterweite in Zellen
    uu, ww = (g.c.xx - g.c.yy) / np.sqrt(2) / p, (g.c.xx + g.c.yy) / np.sqrt(2) / p
    dist = p * np.hypot(uu - np.round(uu), ww - np.round(ww))              # Abstand zum naechsten Punktmittelpunkt (Zellen)
    tone = np.where(d < 1, 0.35 + 0.65 * np.clip(1 - d, 0, 1) ** 0.6, 0.45 * glow(d, 0.28))
    dot = dist < p * np.sqrt(np.clip(tone, 0, 1) / np.pi) * 1.25
    v = np.where(d < 1, np.where(dot, 1.0, (N - 2) / N),
                 np.where(dot & (tone > 0.04) & ~_type_zone(g), (N - 3) / N, bg(g)))
    g.lit = (d < 1) & (v >= 0.5)
    return np.clip(v, 0, 1)


# ---------------------------------------------------------------- Ueberarbeitung 1.10. (Vadims Urteil zu S48, S51, S54)
# Vadim 1.10.: S50 bleibt wie er ist. S51 rein, aber "ein bisschen bland" -> S51b. S54 "hat Potenzial, sieht aber zu
# perfekt aus" + "diese getrennten Wuerfel sehen komisch aus" (Schraffurfelder, gerade abgeschnitten an _qr_zone und
# _type_zone, in Stufenbloecken) -> S54b. S48 "von der Idee cool, zu Standard": chromatische Aberration, crazier -> S48b/c.
# Die Originale bleiben zum Vergleich stehen. Alles nur Palettenstufen auf dem Zellraster, Stern frontal, folgt der Bahn.

# Vadim 1.10.: "alles muss unter dem Dither-Layer sein und gedithered werden" -> keine Flaeche auf einer exakten Stufe
DITHER_MIN = 0.15            # Flaechen liegen mindestens so viel (Anteil einer Stufe) unter ihrer Stufe: nie ganz flach
DITHER_SPAN = 0.7            # und bis zu so viel mehr im Schatten (Licht von oben links + zur Mitte, _lightfield)
HAND_STEP_CELLS = 0.45       # Stuetzpunktabstand der Handstriche: < 1/sqrt(2) Zelle, sonst reisst eine Diagonale im Raster
# S48b/c Linsenfehler: drei Platten, jede um die Plakatmitte (optische Achse) skaliert. So waechst der Versatz mit dem
# Abstand zur Mitte wie bei echter lateraler chromatischer Aberration: gross am Rand (Frame 1, 16), klein in der Mitte.
# Dazu ein fester Fehldruck in Zellen (damit auch der ferne Stern in der Mitte Saeume hat) und etwas Drehung.
CA_SCALE = (0.09, 0.0, -0.07)              # Platte A (aussen), B (Passer = der Stern selbst), C (innen)
CA_SHIFT_CELLS = ((5, 3), (0, 0), (-4, -3))
CA_ROT_DEG = (3.5, 0.0, -3.0)
CA_DOT_CELLS = 4.0           # Platte A ausserhalb des Passers als Ben-Day-Raster (45 Grad, fest auf der Seite), Rasterweite
CA_DOT_FILL = 0.45           # Flaechendeckung der Punkte
# Stufe je Ueberdruck, als Abstand zur hellsten Stufe N (Licht addiert sich: alle drei = hellste Stufe). In Colorways mit
# Farbwechsel in der Rampe (P13 P17 P18 P19 P20 P25) liegen A-Saum und C-Saum in verschiedenen Farbtoenen (blau|gelb),
# in einfarbigen Rampen (P10 P11 P14 P15) nur in Helligkeit und Saettigung.
CA_TOP = {"ABC": 0, "BC": 0.5, "AC": 1.5, "AB": 2, "C": 1, "B": 2, "A": 3}
CA_WILD_GAIN = 2.0           # S48d: Linsenfehler (Skalierung, Drehung) so viel staerker als S48b
CA_WILD_JITTER_CELLS = (3, 8)  # S48d: Fehldruck je Plakat, Zellen (mal 0.5 + Radius): springt von Frame zu Frame
CA_LINE_CELLS = 3            # S48d: Linienraster des Innensaums, Abstand in Zellen (45 Grad)
CA_STRIP_CELLS = (2, 15)     # S48c: Hoehe der Baender in Zellen
CA_STRIP_P = 0.5             # S48c: Anteil der Baender, die verrutschen
CA_STRIP_SHIFT = (6, 24)     # S48c: groesster Bandversatz in Zellen, fern .. nah (waechst mit dem Radius)
# S51b Aquarell in Lagen
AQ_BASE = 0.44               # Grundlasur (Wertraum 0..1; 0.44 = Stufe 2 mit etwas 3 bei 6 Stufen)
AQ_GLAZE = 0.17              # jede Lasur hebt um knapp eine Stufe; zwei uebereinander = zwei Stufen
AQ_STROKES = ((-25, -0.30, 0.42, 5101), (40, 0.20, 0.38, 5104), (95, 0.05, 0.30, 5107))   # Pinselzuege: Winkel (Grad,
                             # auf dem Stern), Querversatz, halbe Breite (Sternradien), Seed. Der letzte endet im Stern
AQ_EDGE_CELLS = 3.0          # Trockenkante: Pigment klingt nach innen ueber so viele Zellen ab (exp)
AQ_STROKES_WET = AQ_STROKES[:2] + ((5, -0.55, 0.22, 5110), (-60, 0.45, 0.2, 5113)) + AQ_STROKES[2:]   # S51c: 5 Zuege
AQ_WET_DARK = 0.22           # S51c: Nass-in-Nass-Tupfer nimmt so viel Wert weg (gut eine Stufe), Gauss-Rand
AQ_BLOOMS_WET = 5            # S51c: Blueten
AQ_FLICK = 40                # S51c: Striche im gerichteten Spritzer (bei Radius 1)
AQ_BLOOMS = 3                # Rueckfluss-Blueten (Blumenkohlrand) pro Stern
AQ_SPATTER = 70              # Spritzer pro Stern bei Radius 1 (skaliert mit dem Umfang), meist 1 Zelle
AQ_DROP_CELLS = (1.3, 2.0)   # Radius der wenigen grossen Tropfen in Zellen (druckgleich)
# S54b Skizze von Hand
SK_HATCH_CELLS = 4.0         # Abstand der Schraffurstriche (Feder), Zellen: gleich auf fernen und nahen Sternen
SK_HATCH_PRESS = (0.4, 0.58) # Druck der Schraffur (Kontur 1.0): Mittelton, Kreuzungen werden dunkler
SK_LAYER_LAM = (0.5, 0.0, -0.28)   # Licht der Flaeche (Lambert, Facetten wie S45) unter diesen Grenzen: 1, 2, 3 Lagen
SK_OVER_CELLS = (3, 9)       # Ueberschwinger an den Spitzen (Zellen, dazu bis 5 % Sternradius)
SK_INSET_CELLS = 1.5         # Kontur so weit innen: der Hauptstrich liegt dunkel auf dem Pergament statt halb auf dem Grund
SK_KEEP_CELLS = (1.0, 6.0)
SK_KEEP_WAVE_CELLS = 9.0     # dazu eine langsame Welle (0..9 Zellen): der Abstand zur Sperrzone schwankt entlang der Kante   # die Hand setzt so viele Zellen vor Titel/QR ab, je Strich zufaellig: Kante franst aus


def _lightfield(x, y, d):
    """Weiches Licht auf dem Stern, 0..1: zur Lichtseite (LIGHT, oben links) und zur Mitte heller (wie S2). Traegt den
    Verlauf, der jede Flaeche unter den Dither legt."""
    side = np.clip((x * LIGHT[0] + y * LIGHT[1]) / np.hypot(LIGHT[0], LIGHT[1]), -1, 1)
    return 0.55 * (0.5 + 0.5 * side) + 0.45 * np.clip(1 - d, 0, 1) ** 0.7


def _dithered(level, L, N):
    """Palettenstufe level (0..N) als Wert, der nie genau auf einer Stufe liegt: je nach Licht L zwischen DITHER_MIN und
    DITHER_MIN + DITHER_SPAN Stufen darunter. Exakte Stufen rendern flach (Skill: Rezept 3), so bekommt jede Flaeche Korn."""
    return (level - DITHER_MIN - DITHER_SPAN * (1 - L)) / N


def _dense(pts, step):
    """Polylinie (n, 2) auf gleichmaessige Stuetzpunkte im Abstand step (m)."""
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.r_[0, np.cumsum(seg)]
    t = np.linspace(0, s[-1], max(2, int(s[-1] / step) + 2))
    return np.c_[np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])]


def _wob(rng, n, corr):
    """Glattes Zittern entlang eines Strichs: n Werte in -1..1, Korrelation ueber corr Stuetzpunkte."""
    corr = max(1.0, corr)
    pad = int(3 * corr) + 1
    w = gaussian_filter1d(rng.standard_normal(n + 2 * pad), corr)[pad:pad + n]
    return w / (np.abs(w).max() + 1e-9)


def _extend(pts, a, b):
    """Strich an beiden Enden tangential verlaengern (m): die Hand bremst nicht rechtzeitig (Ueberschwinger)."""
    k = min(3, len(pts) - 1)
    e0, e1 = pts[0] - pts[k], pts[-1] - pts[-1 - k]
    e0, e1 = e0 / (np.hypot(*e0) + 1e-12), e1 / (np.hypot(*e1) + 1e-12)
    return np.r_[[pts[0] + a * e0], pts, [pts[-1] + b * e1]]


def _pen(g, acc, pts, p, free=None, margin=0.0):
    """Handstrich ins Zellraster. pts (n, 2) in m, dicht (HAND_STEP_CELLS); p = Druck je Punkt 0..1. Pro Strich zaehlt
    jede Zelle einmal (hoechster Druck), Striche addieren sich (Kreuzung = mehr Tinte). free = Abstand zur Sperrzone in
    Zellen: der Strich setzt ab, wo er naeher als margin kommt. Weil margin je Strich anders ist, franst die Kante aus,
    statt als gerade Blockkante zu stehen (Befund S54: "getrennte Wuerfel")."""
    c = _cell(g)
    i, j = np.floor(pts[:, 1] / c).astype(int), np.floor(pts[:, 0] / c).astype(int)
    ok = (i >= 0) & (i < g.gh) & (j >= 0) & (j < g.gw) & (np.broadcast_to(p, i.shape) > 0)
    if free is not None:
        ok &= free[np.clip(i, 0, g.gh - 1), np.clip(j, 0, g.gw - 1)] > margin
    if not ok.any():
        return
    k, pp = i[ok] * g.gw + j[ok], np.broadcast_to(p, i.shape)[ok]
    o = np.lexsort((pp, k))
    k, pp = k[o], pp[o]
    last = np.r_[np.nonzero(np.diff(k))[0], len(k) - 1]                 # je Zelle der hoechste Druck
    acc.reshape(-1)[k[last]] += pp[last]


def _flank(x0, y0, R, rot, k, a0=0.0, a1=1.0, n=240):
    """Flanke k des Sterns (Spitze k -> Kerbe -> Spitze k+1) als Punktfolge in m, nur der Anteil a0..a1."""
    a = TIP_DEG + 60 * k + 60 * np.linspace(a0, a1, n)
    th = np.radians(rot + a)
    r = R * star_r(np.cos(th), np.sin(th), rot)
    return np.c_[x0 + r * np.cos(th), y0 + r * np.sin(th)]


def _keep_free(g):
    """Abstand (Zellen) zu Titelblock und JOIN US + QR: dort zeichnet die Hand nicht."""
    return distance_transform_edt(~(_type_zone(g) | _qr_zone(g)))


def _star_noise2(g, x, y, rot, sig, seed):
    """Wie _star_noise, aber anisotrop: sig = (quer, laengs) → Streifen entlang der Sternachse u (Pinselzug)."""
    n = gaussian_filter(np.random.default_rng(seed).standard_normal((160, 160)), sig)
    n /= 2.5 * n.std()
    a = np.radians(-rot)
    u, w = x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)
    return map_coordinates(n, ((w + 1.6) / 3.2 * 159, (u + 1.6) / 3.2 * 159), order=1, mode="grid-wrap")


def _ca_strips(g, y0, R):
    """S48c: die Seite in waagerechte Baender zerbrochen (nur ueber dem Stern, nie im Titelblock). Etwa jedes zweite Band
    verrutscht, jede Platte darin etwas anders: der Passer bricht an den Bandkanten. Versatz je Zeile in Zellen, (A, B, C)."""
    rng = np.random.default_rng(483)
    c = _cell(g)
    top = int((g.c.L["db"] + 0.6 * g.c.L["capd"]) / g.px) + 2           # erste Zeile unter dem Titelblock
    y_a, y_b = max(top, int((y0 - R) / c)), min(g.gh, int((y0 + R) / c) + 1)
    big = CA_STRIP_SHIFT[0] + (CA_STRIP_SHIFT[1] - CA_STRIP_SHIFT[0]) * min(1.0, R)
    sh = np.zeros((3, g.gh, 1))
    r = y_a
    while r < y_b:
        h = int(rng.integers(*CA_STRIP_CELLS))
        if rng.random() < CA_STRIP_P:
            base = rng.choice([-1, 1]) * rng.uniform(0.35, 1) * big
            sh[:, r:r + h, 0] = np.round(base + rng.normal(0, 0.3 * big, 3)[:, None])
        r += h
    return sh


def _fehldruck_ca(g, strips, wild=False):
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    ox, oy = g.A / 2, g.B / 2                                            # optische Achse = Plakatmitte
    sh = _ca_strips(g, y0, R) if strips else np.zeros((3, 1, 1))
    gain, jit = 1.0, np.zeros((3, 2))
    if wild:                                                             # S48d: jedes Plakat ein eigener Fehldruck
        rng = np.random.default_rng(int(abs(x0 * 9973 + y0 * 7919 + R * 6007) * 1e4) % 2 ** 31)
        gain = CA_WILD_GAIN
        mag = rng.uniform(*CA_WILD_JITTER_CELLS) * (0.5 + min(R, 1.0))
        a = rng.uniform(0, 2 * np.pi)
        jit = np.array([[np.cos(a), np.sin(a)], [0, 0], [-np.cos(a + 0.6), -np.sin(a + 0.6)]]) * mag
    pl = []
    for s, (mx, my), dr, shx, (jx, jy) in zip(CA_SCALE, CA_SHIFT_CELLS, CA_ROT_DEG, sh, jit):
        k = 1 + gain * s
        dr = gain * dr
        xc, yc = ox + (x0 - ox) * k + (mx + jx) * c, oy + (y0 - oy) * k + (my + jy) * c
        pl.append(sd((g.X - shx * c - xc) / (R * k), (g.Y - yc) / (R * k), rot + dr) < 1)
    A, B, C = pl
    top = np.select([A & B & C, B & C, A & C, A & B, C, B, A],
                    [CA_TOP[k] for k in ("ABC", "BC", "AC", "AB", "C", "B", "A")], -1.0)
    d = sd(x, y, rot)
    uu = (g.c.xx - g.c.yy) / np.sqrt(2) / CA_DOT_CELLS
    ww = (g.c.xx + g.c.yy) / np.sqrt(2) / CA_DOT_CELLS
    dot = np.hypot(uu - np.round(uu), ww - np.round(ww)) < np.sqrt(CA_DOT_FILL / np.pi)
    top = np.where(A & ~B & ~C & ~dot, -1.0, top)                         # Aussensaum nur als Punkte
    if wild:                                                             # Innensaum als Linienraster (zweiter Raster-Typ)
        hatch = ((g.c.xx - g.c.yy) % CA_LINE_CELLS) < 1
        top = np.where(C & ~B & ~A & ~hatch, -1.0, top)
    ink = (top >= 0)
    v = np.where(ink, _dithered(N - top, _lightfield(x, y, d), N), bg(g) + 0.10 * glow(d, 0.3))   # jede Platte im Korn
    # Keine Tuschekontur (Vadim 1.10. zu S48b/S48c: "schwarzen Rand weg"): nur die Platten tragen die Form.
    g.lit = ink & (v >= 0.5)
    return np.clip(v, 0, 1)


def c_fehldruck_ca(g):
    """S48b Linsenfehler (ITSV, Miles: Farbplatten verrutscht, mehrfarbige Saeume): drei Platten des Sterns, jede um die
    Plakatmitte anders skaliert und gedreht (laterale chromatische Aberration). Licht addiert sich: wo alle drei liegen, die
    hellste Stufe; zur Mitte hin ein Saum in der zweithellsten, nach aussen zwei dunklere. Am Plakatrand (Frame 1, 16)
    reissen die Platten weit auseinander, in der Mitte bleiben schmale Saeume. Aussensaum als Ben-Day-Punkte.
    Vadim 1.10.: gut, aber "schwarzen Rand weg" -> Tuschekontur entfernt."""
    return _fehldruck_ca(g, strips=False)


def c_fehldruck_wild(g):
    """S48d Linsenfehler wild: S48b mit doppeltem Linsenfehler, und jedes Plakat ist ein eigener Fehldruck (Platten
    springen von Frame zu Frame in eine andere Richtung, Seed aus der Sternlage). Aussensaum Ben-Day-Punkte, Innensaum
    Linienraster: zwei Rasterarten wie im Comicdruck. Ohne Baender (kein Glitch)."""
    return _fehldruck_ca(g, strips=False, wild=True)


def c_fehldruck_bruch(g):
    """S48c Linsenfehler + Bruch: wie S48b, dazu zerbricht der Stern in waagerechte Baender, die mit ihren Platten
    verrutschen (Miles' Glitch in ITSV). Nie im Titelblock. Grenzt an den verworfenen Glitch (S30b); Vadim 1.10.: behalten."""
    return _fehldruck_ca(g, strips=True)


def c_aquarell_lagen(g):
    """S51b Aquarell in Lagen (ATSV, Gwens Earth-65), S51 "ein bisschen bland" -> mehr Malerei. Blasse, wolkige
    Grundlasur; darueber breite Pinselzuege (Lasuren), jeder mit welligem Rand, der beim Trocknen Pigment gesammelt hat:
    hell an der Kante, nach innen exponentiell abklingend (Bayer-Verlauf); wo sich Zuege ueberlagern, mehr Pigment = eine
    Stufe heller. In einem Zug Borstenstreifen (trockener Pinsel), Rueckfluss-Blueten mit Blumenkohlrand, Granulation
    (Pigmentkoerner), feine Spritzer um den Stern. Pigmentrand am Umriss unterschiedlich dick. Befund Runde 1:
    Rauschinseln mit Umrisslinie lesen sich als Landkarte (Naehe S16 "Europa"), deshalb Zuege statt Inseln."""
    return _aquarell(g, wet=False)


def c_aquarell_nass(g):
    """S51c Aquarell nass (mutiger als S51b): fuenf Zuege mit harter Trockenlinie an der Kante, mehr und staerkere
    Blueten, ein Nass-in-Nass-Einlauf (dunkler Tupfer mit weich auslaufendem Rand auf der Schattenseite) und ein
    gerichteter Spritzer (kurze Striche in Wurfrichtung) statt nur runder Tropfen."""
    return _aquarell(g, wet=True)


def _aquarell(g, wet):
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    d = sd(x, y, rot)
    rng = np.random.default_rng(511)
    inside = d < 1
    free = _keep_free(g)
    calm = free < 3 + 3 * (0.5 + 0.5 * _star_noise(g, x, y, rot, 2, 5130))    # Ruhe vor Titel/QR, ausgefranst
    ec = max(AQ_EDGE_CELLS * c / R, 0.012)                                     # Abklingen der Trockenkante (Sternradien)
    v = AQ_BASE + 0.06 * _star_noise(g, x, y, rot, 10, 511)                  # Grundlasur, wolkig
    strokes = AQ_STROKES_WET if wet else AQ_STROKES
    for k, (ang, off, hw, seed) in enumerate(strokes):                       # Pinselzuege (in Sternkoordinaten, drehen mit)
        a = np.radians(ang - rot)
        u = x * np.cos(a) + y * np.sin(a)                                    # laengs des Zugs
        w = -x * np.sin(a) + y * np.cos(a) - off                             # quer
        w = w + 0.05 * _star_noise(g, x, y, rot, 4, seed) + 0.015 * _star_noise(g, x, y, rot, 1, seed + 1)
        sdist = hw * (1 + 0.15 * np.tanh(u)) - np.abs(w)                     # > 0 im Zug, am Rand 0; Zug wird zum Ende breiter
        if k == len(strokes) - 1:                                            # letzter Zug endet im Stern (Pinsel abgesetzt)
            sdist = np.minimum(sdist, 0.35 + 0.06 * _star_noise(g, x, y, rot, 2, seed + 2) - u)
        zug = (sdist > 0) & inside
        pool = np.exp(-np.maximum(sdist, 0) / ec) * ~calm                    # Pigment an der Trockenkante
        v = v + zug * (AQ_GLAZE + 0.9 / N * pool)
        if wet:                                                              # harte Trockenlinie genau an der Kante
            v = np.where(zug & (sdist < c / R) & ~calm, (N - 0.3) / N, v)
        if k == 1:                                                           # trockener Pinsel: Borstenstreifen laengs
            brist = _star_noise2(g, u, w, 0, (0.5, 14), seed + 3) > 0.2
            v = np.where(zug & brist & ~calm, v + 0.7 / N, v)
    if wet:                                                                  # Nass in nass: dunkler Tupfer, weich auslaufend
        ex, ey = _polar(x0, y0, R, rot, np.degrees(np.arctan2(-LIGHT[1], -LIGHT[0])) - rot + rng.uniform(-40, 40), 0.45)
        rr = np.hypot(g.X - ex, g.Y - ey) / (0.32 * R) * (1 + 0.25 * _star_noise(g, x, y, rot, 3, 5160))
        v = v - AQ_WET_DARK * np.exp(-rr ** 2) * inside
    for _ in range(AQ_BLOOMS_WET if wet else AQ_BLOOMS):                     # Rueckfluss: Blumenkohlrand, innen blasser
        cx, cy = _polar(x0, y0, R, rot, rng.uniform(0, 360), rng.uniform(0.1, 0.6))
        rad = R * rng.uniform(0.12, 0.24)
        dx, dy = g.X - cx, g.Y - cy
        ang, rr = np.arctan2(dy, dx), np.hypot(dx, dy)
        wob = sum(rng.uniform(0.03, 0.09) * np.sin(k * ang + rng.uniform(0, 6.3)) for k in (5, 8, 13, 21, 34))
        rb = rad * (1 + wob)
        bl = (rr < rb) & inside
        v = np.where(bl, v - 0.08 + 0.7 / N * np.exp(-(rb - rr) / (ec * R)) * ~calm, v)
    grain = gaussian_filter(np.random.default_rng(5150).standard_normal(d.shape), 0.6)   # Papierkorn: fest auf der Seite
    gran = (grain > np.quantile(grain, 0.93)) & (v > AQ_BASE + AQ_GLAZE) & ~calm
    v = np.where(gran, v + 0.8 / N, v)
    rim = d >= 1 - (1.0 + 2.5 * (0.5 + 0.5 * _star_noise(g, x, y, rot, 6, 5120))) * c / R
    v = np.where(inside, np.where(rim, 1.0, np.clip(v, 0.3, (N - 0.15) / N)), bg(g) + 0.08 * glow(d, 0.25))
    drops = np.zeros(d.shape, bool)
    for _ in range(int(AQ_SPATTER * (0.3 + R))):                             # Spritzer: nah am Stern dicht, weiter weg einzeln
        cx, cy = _polar(x0, y0, R, rot, rng.uniform(0, 360), 1.03 + 0.5 * rng.random() ** 2)
        i, j = int(cy / c), int(cx / c)
        big = rng.random() < 0.12
        if 0 <= i < g.gh and 0 <= j < g.gw and free[i, j] > 2 + rng.uniform(*SK_KEEP_CELLS):
            if big:
                _disk(g, drops, cx, cy, rng.uniform(*AQ_DROP_CELLS) * c)
            else:                                                            # die meisten: 1 Zelle, manchmal 2
                drops[i, j] = True
                if rng.random() < 0.4:
                    drops[min(i + 1, g.gh - 1), j] = True
    if wet:                                                                  # gerichteter Spritzer: kurze Striche in Wurfrichtung
        fa = rng.uniform(0, 360)
        e = np.array([np.cos(np.radians(rot + fa)), np.sin(np.radians(rot + fa))])
        for _ in range(int(AQ_FLICK * (0.3 + R))):
            cx, cy = _polar(x0, y0, R, rot, fa + rng.normal(0, 22), 1.05 + 0.45 * rng.random())
            i, j = int(cy / c), int(cx / c)
            if 0 <= i < g.gh and 0 <= j < g.gw and free[i, j] > 3 + rng.uniform(*SK_KEEP_CELLS):
                ln = rng.uniform(2, 6) * c
                pts = _dense(np.array([[cx, cy], [cx + ln * e[0], cy + ln * e[1]]]), HAND_STEP_CELLS * c)
                ii, jj = (pts[:, 1] / c).astype(int), (pts[:, 0] / c).astype(int)
                ok = (ii >= 0) & (ii < g.gh) & (jj >= 0) & (jj < g.gw)
                drops[ii[ok], jj[ok]] = True
    drops &= ~inside
    v = np.where(drops, (N - 1) / N, v)
    g.lit = inside | drops
    return np.clip(v, 0, 1)


def c_skizze_hand(g):
    """S54b Skizze von Hand (ATSV Leonardo-Vulture; Vadim: S54 "zu perfekt", "getrennte Wuerfel"). Jede Flanke mehrfach
    gezogen: eine leichte Anlage, der Hauptstrich, ein Stueck nachgezogen, jede leicht versetzt, mit Ueberschwingern an
    den Spitzen (die Striche kreuzen sich dort). Schraffur folgt der Form: jede der 12 Flaechen hat ihre eigenen
    Richtungen (parallel zu ihren Kanten), je dunkler die Flaeche im Licht, desto mehr Lagen (1-3, gekreuzt), Strich fuer
    Strich mit Zittern, Druck (setzt kraeftig an, laeuft duenn aus), Enden mal drueber, mal zu kurz. Konstruktion
    freihaendig (Umkreis mehr als eine Runde, Achsen ueber die Spitzen, Masstriche). Wischspur auf der Schattenseite,
    eine Radierspur. Tinte kippt wie die Schrift: auf dem Pergament dunkel, auf dem Grund hell. Ungleicher Druck =
    Zwischenwerte, die Bayer zu gebrochenen Strichen macht (Bleistift auf Korn)."""
    return _skizze(g, study=False)


def c_skizze_studie(g):
    """S54c Skizze Studie (mutiger als S54b): dazu die Geometrie, aus der der Stern konstruiert ist, wie auf einem
    Leonardo-Blatt: Sechseck durch die Spitzen (Lineal, ueber die Ecken hinaus), je Flanke der Zirkelbogen, dem sie folgt
    (ueber die Spitzen weitergezogen), Zirkeleinstich in der Mitte. Kontur auf der Schattenseite doppelt (schwerer Strich),
    in den dunkelsten Flaechen Kreuzkontur-Schraffur, die der Flankenkurve folgt, kraeftigere Wischspur."""
    return _skizze(g, study=True)


def _skizze(g, study):
    x0, y0, R, rot, x, y = _local(g)
    N, c = g.N, _cell(g)
    rng = np.random.default_rng(541)
    d = sd(x, y, rot)
    step = HAND_STEP_CELLS * c
    wave = SK_KEEP_WAVE_CELLS * (0.5 + 0.5 * _star_noise(g, x, y, rot, 3, 5470))  # die Hand umfaehrt Titel/QR in Wellen
    free = _keep_free(g) - wave
    line, lead = np.zeros((g.gh, g.gw), np.float32), np.zeros((g.gh, g.gw), np.float32)

    def stroke(acc, pts, base, amp_cells, corr=0.2, taper_cells=5.0, flick=0.0, clip=None):
        pts = _dense(pts, step)
        n = len(pts)
        tg = np.gradient(pts, axis=0)
        tg /= np.hypot(*tg.T)[:, None] + 1e-12
        pts = pts + np.c_[-tg[:, 1], tg[:, 0]] * (amp_cells * c * _wob(rng, n, corr * n))[:, None]
        s = np.arange(n) * step
        p = base * (0.72 + 0.28 * _wob(rng, n, 0.12 * n)) * np.clip(np.minimum(s, s[-1] - s) / (taper_cells * c), 0.2, 1)
        p = p * (1 - flick * (s / max(s[-1], 1e-9)) ** 1.5)                 # setzt kraeftig an, laeuft duenn aus
        if clip is not None:                                               # Schraffur: im Stern, Ende mal drueber, mal kurz
            p = np.where(sd((pts[:, 0] - x0) / R, (pts[:, 1] - y0) / R, rot) < 1 + clip * c / R, p, 0)
        _pen(g, acc, pts, p, free, rng.uniform(*SK_KEEP_CELLS))

    # Konstruktion (Bleistift, leicht): Umkreis mehr als eine Runde, Innenkreis angerissen, Achsen, Masstriche an den Spitzen
    for rad, turns, base in ((1.03, rng.uniform(1.05, 1.2), 0.55), (INNER_R * 1.05, rng.uniform(0.45, 0.7), 0.4)):
        t = rng.uniform(0, 2 * np.pi) + np.linspace(0, 2 * np.pi * turns, 900)
        rc = R * rad * (1 + 0.01 * rng.standard_normal())
        cx, cy = x0 + rng.normal(0, 1.2 * c), y0 + rng.normal(0, 1.2 * c)
        stroke(lead, np.c_[cx + rc * np.cos(t), cy + rc * np.sin(t)], base, 1.0 + 0.004 * R / c, corr=0.05, taper_cells=12)
    for k in range(3):
        a = np.radians(rot + TIP_DEG + 60 * k + rng.normal(0, 0.8))
        e = np.array([np.cos(a), np.sin(a)])
        l0, l1 = R * rng.uniform(1.12, 1.3), R * rng.uniform(1.12, 1.3)
        stroke(lead, np.array([[x0, y0] - l0 * e, [x0, y0] + l1 * e]), 0.45, 0.4, corr=0.3, taper_cells=8)
    for k in range(6):
        tx, ty = _polar(x0, y0, R, rot, TIP_DEG + 60 * k, 1)
        a = np.radians(rot + TIP_DEG + 60 * k + 90 + rng.normal(0, 4))
        h = rng.uniform(3, 6) * c
        stroke(lead, np.array([[tx - h * np.cos(a), ty - h * np.sin(a)], [tx + h * np.cos(a), ty + h * np.sin(a)]]),
               0.6, 0.2, taper_cells=1.5)

    if study:                                                              # Geometrie des Sterns, wie konstruiert
        tips6 = [np.array(_polar(x0, y0, R, rot, TIP_DEG + 60 * k, 1)) for k in range(7)]
        for k in range(6):                                                 # Sechseck durch die Spitzen, ueber die Ecken hinaus
            pa, pb = tips6[k], tips6[k + 1]
            e = (pb - pa) / np.hypot(*(pb - pa))
            o0, o1 = rng.uniform(4, 10) * c + 0.05 * R, rng.uniform(4, 10) * c + 0.05 * R
            stroke(lead, np.array([pa - o0 * e, pb + o1 * e]), 0.5, 0.35, corr=0.3, taper_cells=6)
            nb = np.array(_polar(x0, y0, R, rot, TIP_DEG + 60 * k + 30, 1))    # Zirkelbogen: Kreis durch Spitze, Kerbe, Spitze
            ax, ay, bx, by, qx, qy = *pa, *nb, *pb
            dd = 2 * (ax * (by - qy) + bx * (qy - ay) + qx * (ay - by))
            ux = ((ax * ax + ay * ay) * (by - qy) + (bx * bx + by * by) * (qy - ay) + (qx * qx + qy * qy) * (ay - by)) / dd
            uy = ((ax * ax + ay * ay) * (qx - bx) + (bx * bx + by * by) * (ax - qx) + (qx * qx + qy * qy) * (bx - ax)) / dd
            rc = np.hypot(ax - ux, ay - uy)
            t0, t1 = np.arctan2(ay - uy, ax - ux), np.arctan2(qy - uy, qx - ux)
            t1 = t0 + (t1 - t0 + np.pi) % (2 * np.pi) - np.pi                 # kurzer Bogen von Spitze zu Spitze
            ext = (t1 - t0) * rng.uniform(0.15, 0.35)
            t = np.linspace(t0 - ext, t1 + ext, 300)
            stroke(lead, np.c_[ux + rc * np.cos(t), uy + rc * np.sin(t)], 0.45, 0.6, corr=0.08, taper_cells=8)
        t = np.linspace(0, 2 * np.pi, 60)                                  # Zirkeleinstich
        stroke(lead, np.c_[x0 + 2.5 * c * np.cos(t), y0 + 2.5 * c * np.sin(t)], 0.8, 0.2, taper_cells=1)
        for a in (0, np.pi / 2):
            e = np.array([np.cos(a + np.radians(rot)), np.sin(a + np.radians(rot))]) * 5 * c
            stroke(line, np.array([[x0, y0] - e, [x0, y0] + e]), 0.8, 0.1, taper_cells=1)

    # Kontur: jede Flanke dreimal (Anlage leicht und versetzt, Hauptstrich, Stueck nachgezogen), Ueberschwinger an den Spitzen
    for k in range(6):
        nrm = np.radians(rot + TIP_DEG + 60 * k + 30)                      # Kerbenrichtung: zeigt die Flanke weg vom Licht?
        shadow = np.cos(nrm) * LIGHT[0] + np.sin(nrm) * LIGHT[1] < 0
        passes = ((2.6, 1.4, 0.5, True), (0.5, 0.6, 1.0, True), (1.2, 0.9, 0.85, False))
        if study and shadow:
            passes += ((0.4, 0.5, 1.0, True),)                            # Schattenseite: schwerer, zweiter Hauptstrich
        for jit, amp, base, whole in passes:
            a0, a1 = (0.0, 1.0) if whole else tuple(sorted(rng.uniform(0, 1, 2)))
            if a1 - a0 < 0.25:
                continue
            kk = 1 + rng.normal(0, 0.004 + 0.5 * jit * c / R) - SK_INSET_CELLS * c / R   # Hauptstrich auf dem Pergament
            pts = _flank(x0 + rng.normal(0, jit * c), y0 + rng.normal(0, jit * c), R * kk, rot + rng.normal(0, 0.6 * jit), k,
                         a0, a1)
            ov = [(rng.uniform(*SK_OVER_CELLS) * c + 0.05 * R * rng.random()) if (whole and rng.random() < 0.8) else 0.0
                  for _ in (0, 1)]
            stroke(line, _extend(pts, *ov), base, amp, corr=0.12, taper_cells=4)
            if study and shadow and whole and base == 1.0:                 # doppelter Strich: 1 Zelle weiter innen
                pts2 = _flank(x0, y0, R * (kk - c / R), rot, k, a0, a1)
                stroke(line, pts2, 0.9, 0.5, corr=0.12, taper_cells=6)

    # Schraffur, die der Form folgt: 12 Flaechen, Richtungen parallel zu ihren Kanten, Lagen nach Licht
    for j in range(12):
        a_s, a_e = TIP_DEG + 30 * j, TIP_DEG + 30 * (j + 1)
        T = np.array(_polar(x0, y0, R, rot, a_s if j % 2 == 0 else a_e, 1))
        Kn = np.array(_polar(x0, y0, R, rot, a_e if j % 2 == 0 else a_s, 1))
        C0 = np.array([x0, y0])
        cen = (T + Kn + C0) / 3
        mx, my = _facets(np.array([(cen[0] - x0) / R]), np.array([(cen[1] - y0) / R]), rot, 0.9)
        lam = float(((mx * LIGHT[0] + my * LIGHT[1] + LIGHT[2]) / np.sqrt(mx * mx + my * my + 1))[0])
        layers = int(np.searchsorted(-np.array(SK_LAYER_LAM), -lam))       # hell: keine Lage, tiefster Schatten: 3
        for P, Q, O in ((T, Kn, C0), (C0, T, Kn), (C0, Kn, T))[:layers]:
            PQ = Q - P
            h = abs(PQ[0] * (O - P)[1] - PQ[1] * (O - P)[0]) / (np.hypot(*PQ) + 1e-12)
            nl = int(h / (SK_HATCH_CELLS * c * rng.uniform(0.9, 1.1)))
            base = rng.uniform(*SK_HATCH_PRESS)
            for t in (np.arange(nl) + 0.5 + rng.uniform(-0.2, 0.2, nl)) / max(nl, 1) * 0.96:
                a, b = P + t * (O - P), Q + t * (O - Q)
                L = np.hypot(*(b - a))
                if L < 2 * c:
                    continue
                e = (b - a) / L
                q = np.array([-e[1], e[0]])
                a = a - e * rng.uniform(-2.0, 1.5) * c + q * rng.normal(0, 0.5) * c
                b = b + e * rng.uniform(-2.0, 1.5) * c + q * rng.normal(0, 0.5) * c
                m = (a + b) / 2 + q * rng.normal(0, 0.6) * c                   # leicht gebogen (Handgelenk)
                tt = np.linspace(0, 1, 12)[:, None]
                bez = (1 - tt) ** 2 * a + 2 * tt * (1 - tt) * m + tt ** 2 * b
                stroke(line, bez, base * rng.uniform(0.8, 1.1), 0.3, corr=0.3, taper_cells=2, flick=0.55,
                       clip=rng.uniform(-2.0, 1.0))
        if study and layers >= 2:                                         # Kreuzkontur: Kurven parallel zur Flanke
            lo, hi = sorted((a_s, a_e))
            f = 0.95
            while f > 0.4:
                aa = np.radians(rot + np.linspace(lo - 2, hi + 2, 40))
                rr = f * R * star_r(np.cos(aa), np.sin(aa), rot)
                stroke(line, np.c_[x0 + rr * np.cos(aa), y0 + rr * np.sin(aa)], rng.uniform(*SK_HATCH_PRESS), 0.3,
                       corr=0.3, taper_cells=2, flick=0.4, clip=rng.uniform(-2.0, 0.5))
                f -= SK_HATCH_CELLS * 1.3 * c / (0.7 * R) * rng.uniform(0.85, 1.15)

    # Wischspur: Handballen hat die Schraffur auf der Schattenseite verzogen; Radierspur: Papier heller, Striche als Geist
    sm_dir = np.array([-LIGHT[1], LIGHT[0]]) / np.hypot(LIGHT[0], LIGHT[1])
    smear = sum(np.roll(line, (int(round(k * sm_dir[1])), int(round(k * sm_dir[0]))), (0, 1)) * (1 - k / 12)
                for k in range(12)) / 6
    lx, ly = x * LIGHT[0] + y * LIGHT[1], -x * LIGHT[1] + y * LIGHT[0]
    blob = ((lx + 0.45) / 0.28) ** 2 + ((ly - rng.uniform(-0.2, 0.2)) / 0.5) ** 2 < 1 + 0.3 * _star_noise(g, x, y, rot, 3, 5420)
    blob &= free > 3
    ea = np.radians(rot + rng.uniform(0, 180))
    ec = np.array(_polar(x0, y0, R, rot, rng.uniform(0, 360), rng.uniform(0.35, 0.6)))
    eu = (g.X - ec[0]) * np.cos(ea) + (g.Y - ec[1]) * np.sin(ea)
    ev = -(g.X - ec[0]) * np.sin(ea) + (g.Y - ec[1]) * np.cos(ea)
    eh = max(0.05 * R, 4 * c)                                               # Radiergummi: Stadion mit ausgefranstem Rand
    erased = (np.hypot(np.maximum(np.abs(eu) - 0.2 * R, 0), ev) < eh * (1 + 0.25 * _star_noise(g, x, y, rot, 1.5, 5430)))
    erased &= free > 3
    sm = (0.55, 0.2) if study else (0.35, 0.12)                             # Wischspur: Anteil verzogene Tinte, Grauschleier
    ink = np.clip(line + 0.55 * lead + blob * (sm[0] * np.clip(smear, 0, 1) + sm[1]), 0, 1)
    ink = np.where(erased, 0.3 * ink, ink)                                  # Striche nur noch als Geist, Papier bleibt
    paper = d < 1
    pv = (N - 1 + DITHER_MIN + DITHER_SPAN * _lightfield(x, y, d)) / N     # Pergament im Licht: Korn zwischen 2 hellsten Stufen
    v_in = pv - (pv - 0.5 / N) * ink
    v_out = bg(g) + ((N - 2) / N - bg(g)) * np.clip(0.9 * line + 1.0 * lead, 0, 1)
    v = np.where(paper, v_in, v_out)
    g.lit = paper & (v >= 0.5)
    return np.clip(v, 0, 1)


CANDS = [  # (code, fn, titel, beschreibung); Varianten (Buchstaben-Suffix) stehen unter ihrem Stamm
    ("S13", c_sternkind, "Sternkind", "Jede Spitze gebiert einen kleineren Stern, der nach aussen weiterwaechst: Stern-Koch-Kurve."),
    ("S14", c_attraktor, "Sternstaub", "Chaos-Spiel-Attraktor aus zwoelf Sternpunkten, leicht verdreht: der Stern als Staubgalaxie."),
    ("S15", c_wirbel, "Schlund", "Das XOR-Nest im Log-Polar-Raum verdrillt: eine unendliche Spirale nach innen."),
    ("S16", c_escher, "Kleiner und kleiner", "Konformes Sternparkett, das sich zum Zentrum ins Unendliche zieht (Escher)."),
    ("S17", c_drehfeld, "Drehfeld", "Gitter kleiner Sterne, draussen verdreht, im grossen Stern ausgerichtet: ein Geheimbild aus Ordnung."),
    ("S18", c_interferenz, "Interferenz", "Zwei Hoehenlinien-Sterne ueber die ganze Seite, XOR: Sternmoire."),
    ("S18b", c_interferenz3, "Interferenz Drei", "Dritte Quelle: ein Dreistern (Logo-Profil mit drei Spitzen) mischt sein Dreiecksmoire hinein."),
    ("S18c", c_interferenz3z, "Dreieckszentrum", "Der Dreistern als Zentrum, zwei kleine Sechssterne flankieren: das Moire bekommt eine dreieckige Ordnung."),
    ("S19", c_kaleido, "Kaleidoskop", "Zwoelffach gefaltetes Feld aus versetzten Sternen, XOR: ein Siegel aus einer fremden Kultur."),
    ("S19b", c_kaleido_siegel, "Siegel", "Kaleidoskop in der Sternsilhouette: Sternringe und Kreisbaender kippen die Paritaet nach aussen."),
    ("S19c", c_kaleido_spiegel, "Spiegelkabinett", "Echtes Kaleidoskop (drei Spiegel, p6m): ein Sternmotiv unendlich gekachelt, sichtbar durch den Stern."),
    ("S19d", c_kaleido_nest, "Nest-Rosette", "Das XOR-Nest aus der Mitte geschoben und sechsfach gespiegelt."),
    ("S19e", c_kaleido_drei, "Dreifach", "Dreifaches Kaleidoskop aus Dreisternen, in Dreisternsilhouette."),
    ("S20", c_fluessig, "Plasma-Nest", "Das Nest in sinus-verbogenem Raum, die Spitzen zuengeln wie Flammen."),
    ("S21", c_loch, "Schacht", "Die Seite ist hell, der Stern ein Loch, das in Stufen ins Schwarze faellt."),
    ("S22", c_luecke, "Luecke", "Die Seite aus groben Kacheln, der Stern ist die Luecke, wo Kacheln fehlen."),
    ("S23", c_anschnitt, "Anschnitt", "Riesiges Nest, Mitte ausserhalb der Seite: nur die Spitzen ragen herein."),
    ("S24", c_rahmen, "Rahmen", "Die ganze Seite liegt im Stern, die Ecken sind das Aussen."),
    ("S25", c_fenster, "Fenster", "Der Stern als Fenster in eine andere Palette und ein anderes Universum."),
    ("S26", c_xortitel, "Kippschrift", "Glutstern mittig hinter dem Titel; wo die Schrift ihn kreuzt, kippt sie ins Negativ."),
    ("S27", c_durchblick, "Durchblick", "Die Buchstaben sind Fenster auf ein riesiges XOR-Nest hinter der Seite."),
    ("S28", c_finsternis, "Finsternis", "Ein schwarzer Stern schiebt sich vor den hellen, die Korona glueht."),
    ("S29", c_aufgang, "Aufgang", "Der Stern geht hinter der Titelzeile auf, die Buchstaben stehen als Silhouette davor."),
    ("S30", c_versatz, "Versatz: Zeilensprung", "Der Stern als Halbbilder: jedes zweite Band zeigt ihn einen Moment spaeter, gedreht und verschoben."),
    ("S30b", c_verschluss, "Versatz: Rolling Shutter", "Band fuer Band abgetastet, waehrend er sich dreht: der Stern verdreht sich treppenartig."),
    ("S31", c_gegenlicht, "Gegenlicht", "Stern hinter dem Titel, Lichtstrahlen brechen durch die Buchstabenluecken."),
    ("S31b", c_lichtfall, "Lichtfall", "Lange Schaechte ohne Abklingen: die Buchstabenschatten ziehen bis an den Rand, Licht faellt ueber die untere Haelfte."),
    ("S31c", c_zweitlicht, "Zweitlicht", "Stern in der eigenen Palette, das Licht dahinter in einer zweiten (Blau mit Gold, CGA mit Laserrot)."),
    ("S31d", c_randlicht, "Randlicht", "Schwarze Buchstabenkoerper, harte Lichtkante wo das Gegenlicht sie streift, weiche Schaechte."),
    ("S31e", c_flare, "Flare", "Anamorpher Lichtstreif, Geisterbilder auf der Achse durch die Seitenmitte, kurze Strahlen."),
    ("S31f", c_strahlenkranz, "Strahlenkranz", "Harte Lichtkeile strahlen vom Stern hinter dem Titel ueber die ganze Seite, mit Buchstabenschatten."),
    ("S32", c_linse, "Linse", "Sternfoermige Lupe ueber dem Titel, darin die Schrift riesig in fremder Farbe."),
    ("S34", c_brandmal, "Brandmal", "Mit dem Eisen eingebrannt: weissgluehender Rand, verkohltes Inneres mit Glutrissen, Sengring mit Fingern."),
    ("S35", c_durchgebrannt, "Durchgebrannt", "Die Seite brennt entlang des Sterns durch: Loch, Glutsaum, Kohlerand, Brandnester vor der Front."),
    ("S36", c_schmelze, "Schmelze", "Der Stern sackt ab und laeuft aus: Tropfen mit Glanzkante, unten eine Lache."),
    ("S37", c_einbrennen, "Einbrennen", "Burn-in: eine Kette von Nachbildern in der Zweitfarbe, jedes blasser und in Zeilen zerfallen."),
    ("S38", c_glut, "Glut", "Der Stern als Haufen Glutbrocken, aussen kalt und broeckelnd, Funken fliegen nach oben."),
    ("S39", c_filmbrand, "Filmbrand", "Der Stern brennt durch die Emulsion: weiss ausgeblendet, drumherum Blasen mit Kohlesaum."),
    ("S40", c_verkohlung, "Verkohlung", "Reaktionsdiffusion: innen Labyrinth wie verkohlte Maserung, aussen Punkte, die absterben."),
    ("S41", c_zerfall, "Zerfall", "Der Stern zerbroeselt zu Pixelsand, der herabrieselt und sich unten tuermt."),
    ("S42", c_fata, "Fata Morgana", "Die Hitze ueber dem Stern flimmert: Spitzen zittern, der Titel spiegelt sich zerrissen in der Luft."),
    ("S43", c_wunderkerze, "Wunderkerze", "Mit der Wunderkerze in die Nacht gemalt: gluehende Spur, verzweigte Funken, Funkenball am Kopf."),
    # Licht-Serie fuer den Kick-off-Loop (30.9.): Stern als Koerper im Licht, immer frontal
    ("S44", c_relief, "Relief", "Geschliffene Sternpyramide im Streiflicht, Lambert + Glanz im Bayer-Korn."),
    ("S45", c_facette, "Facette", "Derselbe Kristall als Cel-Shading: 12 flache Toene, Schatten als Ben-Day-Punktraster aus Bayer 4x4."),
    ("S46", c_stufen, "Stufen", "Matrjoschka als Stufenpyramide: Terrassen, Lichtkanten, Schlagschatten auf die Stufe darunter."),
    ("S47", c_praegung, "Praegung", "Das XOR-Nest als Hochdruck: erhabene Platten mit Lichtkante und Schatten."),
    ("S31g", c_lampe, "Lampe", "Der Stern ist die Lampe: Lichtbahnen aus den Spitzen, Titelschatten, Umriss bleibt."),
    ("S18d", c_interferenz_innen, "Moire im Stern", "Zwei Hoehenlinien-Sterne per XOR, nur in der Silhouette, harter Rand."),
    ("S48", c_fehldruck, "Fehldruck", "ITSV Brooklyn: zwei Druckplatten, Farbplatte verrutscht (fern 2, nah 4 Zellen), Ben-Day-Schatten."),
    ("S48b", c_fehldruck_ca, "Linsenfehler", "ITSV Miles: drei Platten, um die Plakatmitte verschieden skaliert (chromatische Aberration), Licht addiert sich."),
    ("S48c", c_fehldruck_bruch, "Linsenfehler Bruch", "Wie S48b, der Stern zerbricht in verrutschte Baender (ITSV-Glitch; Vadim behaelt ihn)."),
    ("S48d", c_fehldruck_wild, "Linsenfehler wild", "S48b doppelt, jedes Plakat ein eigener Fehldruck, Punkt- und Linienraster in den Saeumen."),
    ("S49", c_krackle, "Krackle", "Jack Kirby / ITSV-Kollider: heller Energiesaum, schwarze Kirby-Punkte stanzen den Raum aus."),
    ("S50", c_fokus, "Fokuslinien", "Manga shuuchuu-sen / ITSV-Speedlines: Keile vom Rand auf den Stern, Titelblock bleibt frei."),
    ("S51", c_aquarell, "Aquarell", "ATSV Gwen (Earth-65): Lasur mit Pigmentrand und Rueckfluss-Blueten, scharfer Umriss."),
    ("S51b", c_aquarell_lagen, "Aquarell Lagen", "Lasuren mit Trockenrand uebereinander, Blumenkohl-Blueten, Pinselzug, Granulation, Spritzer."),
    ("S51c", c_aquarell_nass, "Aquarell nass", "S51b mutiger: fuenf Zuege mit Trockenlinie, Nass-in-Nass-Tupfer, gerichteter Spritzer."),
    ("S52", c_zine, "Zine", "ATSV Hobie: aus der Fotokopie geschnitten, Toner, Klebeband, harter Schlagschatten."),
    ("S53", c_spot, "Spot", "ATSV The Spot: Gesso-Stern mit Tintenloechern, Bleistift-Konstruktion scheint durch."),
    ("S54", c_skizze, "Skizze", "ATSV Leonardo-Vulture: Pergament, Federschraffur, Konstruktion ueber den Umriss hinaus."),
    ("S54b", c_skizze_hand, "Skizze Hand", "Mehrfach gezogene Konturen, Ueberschwinger, Schraffur je Flaeche, Wisch- und Radierspur."),
    ("S54c", c_skizze_studie, "Skizze Studie", "S54b + Konstruktion wie auf einem Leonardo-Blatt: Sechseck, Zirkelboegen, doppelte Schattenkontur."),
    ("S55", c_halbton, "Halbton", "ITSV Ben-Day: echtes Druckraster fest auf der Seite, der Stern fliegt darunter durch."),
]
BY = {c[0]: c for c in CANDS}
CMP = {"S26v1": c_xortitel_alt, "S30v1": c_versatz_alt, "S31b2": c_lichtfall_kurz}   # alte Fassungen, nur Vergleich
PARENT = {c: c.rstrip("bcdefgh") for c in BY}
# Urteil (1-5, wofuer, Satz). Vadim 2026-09-25: raus = S15 S16 S17 S20 S21 S22 S25 S27 S28 S32. Varianten: meine Sichtung.
URTEIL = {"S13": (4, "beides", "Vadim: cool, bleibt."),
          "S14": (4, "beides", "Vadim: super, sehr typisch Informatik. Bleibt."),
          "S15": (1, "raus", "Vadim: tacky."),
          "S16": (1, "raus", "Vadim: sieht aus wie Europa, komisch."),
          "S17": (1, "raus", "Vadim: raus."),
          "S18": (3, "beides", "Vadim: interessant, dritte Quelle dazu (S18b, S18c)."),
          "S18b": (4, "beides", "Drei Wellen mit endlicher Reichweite: jede Quelle bleibt lesbar, der Dreistern oben ist eindeutig."),
          "S18c": (3, "beides", "Ruhiger, symmetrisch; eher Emblem als Moire."),
          "S19": (3, "beides", "Vadim: cool, mehr Varianten und cooler (S19b-e)."),
          "S19b": (4, "beides", "Staerkste S19: Motive nur auf den Spiegelachsen, liest sich wie ein Abzeichen."),
          "S19c": (3, "beides", "Echtes Spiegelgitter; dicht, nah an Schneeflocke."),
          "S19d": (4, "beides", "Am meisten Informatik: das Nest als Mosaik."),
          "S19e": (3, "beides", "Dreieckig, eigenstaendig, etwas Triforce."),
          "S20": (1, "raus", "Vadim: raus."),
          "S21": (1, "raus", "Vadim: raus."),
          "S22": (1, "raus", "Vadim: raus."),
          "S23": (4, "Plakat", "Vadim: gut."),
          "S24": (4, "Plakat", "Vadim: gut."),
          "S25": (1, "raus", "Vadim: schlecht."),
          "S26": (4, "Plakat", "Vadim: cool, aber der Stern sah komisch aus. Fix: er hing unter der Zeile, oben angeschnitten, "
                              "schraeg; haardünne Spitzen zerhackten die Buchstaben. Jetzt mittig, ganz im Bild, Spitzen senkrecht, "
                              "Spitzenenden weggeoeffnet."),
          "S27": (1, "raus", "Vadim: raus."),
          "S28": (1, "raus", "Vadim: raus (als Standbild)."),
          "S29": (3, "Plakat", "Vadim: ok, bleibt."),
          "S30": (4, "beides", "Vadim: hat was, aber unklar was passiert. Neu: zwei Halbbilder im Kamm, der Versatz ist sofort lesbar."),
          "S30b": (3, "beides", "Treppenverdrehung klar, im Standbild etwas unruhig; stark als Bewegung."),
          "S31": (5, "beides", "Vadim: sehr, sehr cool. Tiefer ins Licht: S31b-f."),
          "S31b": (5, "beides", "Staerkste: Schaechte bis an den Rand, die Titel-Silhouette steht im Licht."),
          "S31c": (5, "beides", "Blau/Gold und CGA/Laserrot: zwei Farben ohne Lila, sofort Plakat."),
          "S31d": (4, "beides", "Lichtkante nur wo Licht hinkommt (Schattentest), sonst wirkt sie wie Outline."),
          "S31e": (3, "beides", "Balken im Durchschuss ist schoen, Geister bleiben leise. Eher Bewegung."),
          "S31f": (5, "beides", "Harte Lichtkeile mit Buchstabenschatten: Buehnenlicht, sehr Rave."),
          "S32": (1, "raus", "Vadim: raus.")}
# Brand-Serie 2026-09-26 (Vadim: zu zahm, wilder; eingebrannt, verkohlt, geschmolzen). Meine Sichtung.
URTEIL.update({"S34": (5, "beides", "Staerkste der Serie: Glutrand + Kohlerisse; auf Riso eine echte Brandspur im Papier. Kick-off P18/P16, K1/K4."),
               "S35": (4, "beides", "Loch mit Glutsaum, sehr plakativ. Seite ist hell (Grund 0.3), Titel bleibt lesbar. P11/P18, K6."),
               "S36": (4, "beides", "Liest sich sofort als Schmelze; auf Tscherenkow eher Eiszapfen. P14/P18, K1 oder K7 (tropft durch den Titel)."),
               "S37": (4, "beides", "Nachbilder in der Zweitfarbe, Zeilen zerfallen: Rave-Plakat. Kette laeuft nach links unten. K1 ja, K4 zu gross."),
               "S38": (3, "beides", "Glutbrocken + Funken, Stern lesbar; im A3 (K1) am besten, im 16x9 etwas koernig."),
               "S39": (3, "beides", "Weisser Stern, Blasen mit Kohlesaum. Grosse weisse Flaeche, im Plakat sehr laut. P14 K1."),
               "S40": (5, "beides", "Reaktionsdiffusion: Labyrinth im Stern, Punkte als Umriss. Wirkt wie ein Organismus, Tokio K6 top."),
               "S41": (3, "beides", "Pixelsand-Automat, im 16x9 stark; in grossen K liegt der Stern zu tief, zu wenig Fallhoehe."),
               "S42": (2, "beides", "Hitzeschlieren wirken wie Flammen (Naehe zu S20); Spiegeltitel im Plakat nur leise. Eher raus."),
               "S43": (3, "beides", "Wunderkerzen-Lichtmalerei, thematisch perfekt; bei riesigem R werden die Linien zu duenn (K6 statt K1).")})
URTEIL.update({c: (1, "raus", "Vadim 26.9.: nicht meins.") for c in "S19c S34 S35 S37 S38 S39 S41 S42 S43".split()})
# Kick-off-Loop 30.9.: S36 raus (Vadim: "schmilzt, sieht scheisse aus"); neue silhouettentreue Stile fuer den Bumerang
URTEIL.update({"S36": (1, "raus", "Vadim 30.9.: schmilzt, sieht scheisse aus."),
               "S44": (4, "Loop", "Relief im Streiflicht: dreht sich der Stern, wandert das Licht ueber die Firste."),
               "S45": (4, "Loop", "Cel-Shading mit Ben-Day aus Bayer: grafisch, klein sehr klar."),
               "S46": (4, "Loop", "Stufenpyramide mit Schlagschatten: Matrjoschka als Architektur."),
               "S47": (4, "Loop", "Nest als Praegung: S7 mit Licht und Schatten an jeder Plattenkante."),
               "S31g": (4, "Loop", "Gegenlicht, das die Silhouette haelt: Strahlen aus den Spitzen, Titel steht hell davor."),
               "S18d": (3, "Loop", "Moire nur im Stern: S18 ohne die Titel-Zerstoerung.")})
# Spider-Verse-Serie 1.10. (Sterne-Fork, Vadim: "Spider-Verse-Inspo, coole Sparks"): meine Sichtung, Vadim waehlt noch
URTEIL.update({c: (3, "Loop", "neu, Vadim hat noch nicht gewaehlt.") for c in "S48 S49 S50 S51 S52 S53 S54 S55".split()})
# Vadims Urteil 1.10. zum Bogen stars_neu.png (S48-S55) und zu den Ueberarbeitungen (Boegen previz/review/S_rework_1-3.png).
# Endstand 1.10.: behalten S50, S48c, S48d, S54c. Alles unter den Dither (keine Flaeche auf einer exakten Stufe). Aquarell raus.
URTEIL.update({"S50": (5, "Loop", "Vadim 1.10.: kommt rein, so wie er ist."),
               "S48c": (5, "Loop", "Vadim 1.10.: behalten. Ohne Tuschekontur (\"schwarzen Rand weg\"), alles im Korn. Die "
                                   "Baender grenzen an den verworfenen Glitch (S30b), Vadim will sie trotzdem."),
               "S48d": (5, "Loop", "Vadim 1.10.: \"richtig gut\", behalten. Jedes Plakat ein eigener Fehldruck, Punkt- + "
                                   "Linienraster in den Saeumen, alles im Korn."),
               "S54c": (5, "Loop", "Vadim 1.10.: \"richtig gut\", behalten. Handzeichnung + Konstruktion (Sechseck, "
                                   "Zirkelboegen), Pergament im Korn."),
               "S48": (3, "nicht gewaehlt", "Vadim 1.10.: Idee cool, zu Standard -> S48b-d; zu S_rework_2 \"richtig gut\", "
                                            "aber behalten werden S48c/S48d. Helle Flaechen jetzt im Korn."),
               "S48b": (3, "nicht gewaehlt", "Vadim 1.10.: gut (schwarzen Rand weg), behalten werden aber S48c/S48d."),
               "S54": (2, "nicht gewaehlt", "Vadim 1.10.: Potenzial, aber zu perfekt; getrennte Wuerfel -> S54c."),
               "S54b": (3, "nicht gewaehlt", "Zwischenstand zu S54c (von Hand, ohne Konstruktion). Behalten wird S54c."),
               "S51": (1, "raus", "Vadim 1.10.: erst \"kommt rein, bland\", dann \"Aquarell raus\"."),
               "S51b": (1, "raus", "Vadim 1.10.: Aquarell raus. Befund Runde 1: Rauschinseln mit Umriss = Landkarte (S16)."),
               "S51c": (1, "raus", "Vadim 1.10.: Aquarell raus."),
               **{c: (2, "nicht gewaehlt", "Vadim 1.10.: nicht gewaehlt (nicht verworfen).") for c in "S49 S52 S53 S55".split()}})
KEPT =[c for c in BY if URTEIL[c][1] != "raus"]

# Kick-off-Sichtung 2026-09-25 nachts (Vadim)
URTEIL.update({"S29": (1, "raus", "Vadim: alles schwarz, Stil komplett raus."),
               "S30": (1, "raus", "Vadim: Stil raus."), "S30b": (1, "raus", "Vadim: Glitch-Look, komplett raus."),
               "S19b": (1, "raus", "Vadim: diese Art Fraktal ist nichts."),
               "S18b": (2, "geparkt", "Vadim: Dreistern-Sachen erstmal parken."), "S18c": (2, "geparkt", "Vadim: Dreistern parken."),
               "S19e": (2, "geparkt", "Vadim: Dreistern parken."),
               "S19d": (4, "beides", "Vadim: cool, Spitzen waren zu rund -> harter Rand."),
               "S31e": (4, "beides", "Vadim: der gluehende Stern muss viel groesser, wie eine Sonne.")})


# ---------------------------------------------------------------- Render

def fn(code):
    return BY[code][1] if code in BY else CMP[code]


def kick_layout(c):
    """Test-Satz wie die Kick-off-Kampagne: eine riesige Titelzeile SPARK, sonst dieselben Schluessel wie styles.layout."""
    L, px = dict(c.L), c.px
    snap = lambda v: round(v / px) * px                                        # noqa: E731
    port = c.H > c.W
    cap = ((c.W - 2 * L["m"]) * (1.0 if port else 0.72) / px // styles.width_per_cap("SPARK")) * px
    tb = [L["meta"] + snap(0.4 * cap) + cap]
    L.update(title=("SPARK",), cap=cap, tb=tb, db=tb[-1] + snap(0.42 * cap) + L["capd"])
    return L


def render(code, pal="lav", fmt="16x9", kick=False):
    g = G({**BASE, "P": pal, "D": D, "R": 4}, fmt)
    if kick:
        g.c.L = kick_layout(g.c)
    r = fn(code)(g)
    v, extra = (r if isinstance(r, tuple) else (r, []))
    img = g.pal[dither(v, g.N, D, g.px)]
    for v2, mask, p2 in extra:
        p2 = p2[pal] if isinstance(p2, dict) else p2
        pl = hexpal(p2)
        col = pl[dither(v2, len(pl) - 1, D, g.px)]
        img = np.where(up(mask, g.px)[..., None], col, img)
    return img.astype(np.uint8)


# ---------------------------------------------------------------- Plakat im echten Layout (styles.render, K-Satz, XOR-Regel)

# code -> [(palette, dim)]: Top-Auswahl als A3 im echten Satz
POSTERS = {"S31": [("cherenkov", 731), ("eclipse", 137)], "S31b": [("cherenkov", 312), ("riso", 213)],
           "S31c": [("cherenkov", 313), ("cga", 331)], "S31d": [("eclipse", 314), ("phosphor", 413)],
           "S31e": [("eclipse", 315), ("cherenkov", 513)], "S31f": [("riso", 316), ("eclipse", 613)],
           "S18b": [("cherenkov", 182), ("riso", 281)], "S19b": [("eclipse", 192), ("cga", 291)],
           "S19c": [("phosphor", 193), ("cherenkov", 391)], "S19d": [("riso", 194)], "S19e": [("eclipse", 195)],
           "S26": [("cherenkov", 262), ("riso", 626)], "S30": [("phosphor", 302), ("cga", 203)],
           "S30b": [("cherenkov", 303), ("eclipse", 330)],
           "S34": [("eclipse", 341), ("riso", 342)], "S36": [("eclipse", 361), ("cherenkov", 362)],
           "S37": [("cherenkov", 371)], "S40": [("cherenkov", 401), ("riso", 402)]}
PCODE = {"lav": "P1", "acid": "P5", "cga": "P6", "paper": "P8", "laser": "P9", "phosphor": "P10", "cherenkov": "P11",
         "uv": "P12", "holo": "P13", "eclipse": "P14", "blueprint": "P15", "riso": "P16"}


def poster(code, pal="lav", dim=42):
    """Kandidat als Stern-Ebene in styles.render(): ganzes Feld als Ebene 'spark', c.star_m = leuchtende Pixel,
    Zusatzpaletten (Fenster) danach ausserhalb der Schrift einsetzen."""
    got = {}
    spark0, type0 = styles.spark, styles.type_layers

    def my_spark(c):
        g = G(c.st, c.fmt, c)
        r = fn(code)(g)
        v, extra = (r if isinstance(r, tuple) else (r, []))
        c.star_m = g.lit if g.lit is not None else v >= 0.5
        c.add("spark", np.ones(v.shape, bool), np.clip(v, 0, 1))
        got.update(g=g, extra=extra)

    def my_type(c):
        n = len(c.layers)
        type0(c)
        got["type"] = np.maximum.reduce([a for _, a, *_ in c.layers[n:]]) > 0

    styles.spark, styles.type_layers = my_spark, my_type
    try:
        frame = styles.render(dict(styles.st_of(f"{PCODE[pal]} K1"), poster=True, dim=dim), "a3")[0]
    finally:
        styles.spark, styles.type_layers = spark0, type0
    g = got["g"]
    for v2, mask, p2 in got["extra"]:
        pl = hexpal(p2[pal] if isinstance(p2, dict) else p2)
        col = pl[dither(v2, len(pl) - 1, D, g.px)]
        frame = np.where((up(mask, g.px) & ~got["type"])[..., None], col, frame).astype(np.uint8)
    return frame


def job_poster(args):
    code, pal, dim = args
    p = os.path.join(OUT, f"poster_{code}_{pal}.png")
    Image.fromarray(poster(code, pal, dim)).quantize(256, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE) \
        .save(p, optimize=True, dpi=(300, 300))
    return p


def job(args):
    code, pal, fmt, kick = (*args, False)[:4]
    a = render(code, pal, fmt, kick)
    p = os.path.join(OUT if not kick else TMP, f"{code}_{pal}_{fmt}.png")
    im = Image.fromarray(a).quantize(256, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
    im.save(p, optimize=True, **({"dpi": (300, 300)} if fmt == "a3" else {}))
    return p


def sheet(files, path, cols=4, tw=480):
    ims = [Image.open(f).convert("RGB") for f in files]
    th = round(tw * ims[0].height / ims[0].width)
    rows = -(-len(ims) // cols)
    S = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 30) + 8), (10, 7, 17))
    dr = ImageDraw.Draw(S)
    f = font("DepartureMono-Regular.otf", 22)
    for n, (fn, im) in enumerate(zip(files, ims)):
        x, y = 8 + n % cols * (tw + 8), 8 + n // cols * (th + 30)
        S.paste(im.resize((tw, th), Image.Resampling.BOX), (x, y))
        dr.text((x, y + th + 4), os.path.basename(fn)[:-4], font=f, fill=(241, 236, 255))
    S.save(path)


def gallery():
    esc = html.escape
    files = set(os.listdir(OUT))
    CSS = """:root{--bg:#0A0711;--fg:#F1ECFF;--mut:#9B8FC0;--line:#2A1F4A;--acc:#AE93EE;--lime:#D7FF3A}
body{margin:0;padding:24px 16px 80px;background:var(--bg);color:var(--fg);font:14px/1.5 ui-monospace,Menlo,monospace}
main{max-width:1500px;margin:auto}h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:40px 0 4px;color:var(--acc)}
h3{font-size:14px;margin:18px 0 2px}p.d{color:var(--mut);margin:0 0 10px;max-width:110ch}
.row{display:grid;grid-template-columns:2fr 1fr;gap:12px;align-items:start}
.alts{display:grid;grid-template-columns:1fr 1fr;gap:6px}.pg{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:22px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px}.pair.one{grid-template-columns:1fr}
.var{border-left:2px solid var(--line);padding-left:14px;margin-left:4px}
img{width:100%;display:block;image-rendering:pixelated;border:1px solid var(--line)}a{color:var(--acc)}code{color:var(--lime)}
.r{font-size:11px;padding:0 5px;border:1px solid var(--line);color:var(--mut);margin-left:6px}.r.top{color:var(--lime);border-color:var(--lime)}
.r.raus{color:#6A5E8C;text-decoration:line-through}.raus{opacity:.4}nav a{margin-right:10px}
@media(max-width:800px){.row{grid-template-columns:1fr}}"""
    img = lambda f, alt: f'<a href="{f}"><img src="{f}" loading="lazy" alt="{esc(alt)}"></a>'   # noqa: E731

    def tag(code):
        n, use, _ = URTEIL[code]
        return f'<span class="r{" top" if n >= 4 else " raus" if use == "raus" else ""}">{n}/5 · {use}</span>'

    def block(code, head="h2"):
        _, _, t, desc = BY[code]
        raus = URTEIL[code][1] == "raus"
        order = ["lav", "acid", "cga", "paper"] if raus else ["cherenkov", "riso", "eclipse", "cga", "phosphor", "lav"]
        have = [f"{code}_{p}_16x9.png" for p in order if f"{code}_{p}_16x9.png" in files]
        if not have:
            return ""
        note = URTEIL[code][2]
        return (f'<{head}><code>{code}</code> {esc(t)}{tag(code)}</{head}><p class="d">{esc(desc)}{" " + esc(note) if note else ""}</p>'
                f'<div class="row">{img(have[0], code)}<div class="alts">{"".join(img(f, f) for f in have[1:])}</div></div>')

    posters = []
    for code in sorted(POSTERS, key=lambda c: (-URTEIL[c][0], c)):
        ps = [f"poster_{code}_{p}.png" for p, _ in POSTERS[code] if f"poster_{code}_{p}.png" in files]
        if ps:
            _, _, t, desc = BY[code]
            posters.append(f'<figure style="margin:0"><div class="pair{" one" if len(ps) == 1 else ""}">'
                           + "".join(img(f, f"{code} {f}") for f in ps)
                           + f'</div><h3><code>{code}</code> {esc(t)}{tag(code)}</h3><p class="d">{esc(desc)}</p></figure>')
    parents = [c for c in BY if PARENT[c] == c]
    kept = [c for c in parents if URTEIL[c][1] != "raus"]
    raus = [c for c in parents if URTEIL[c][1] == "raus"]
    parts = []
    for code in kept + raus:
        kids = [k for k in BY if PARENT[k] == code and k != code]
        inner = block(code) + "".join(f'<div class="var">{block(k, "h3")}</div>' for k in kids)
        parts.append(f'<section id="{code}" class="{"raus" if code in raus else ""}">{inner}</section>')
    nav = " ".join(f'<a href="#{c}">{c}</a>' for c in kept)
    doc = (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>Spark-Labor</title><style>{CSS}</style></head><body><main><h1>Spark-Labor: S13 und folgende</h1>'
           f'<p class="d">Neue Rollen fuer den Stern. Stand nach Vadims Urteil vom 25.09.: behalten, Varianten darunter '
           f'(Buchstaben-Suffix), raus ausgegraut am Ende. D3 Bayer 4x4, R = 4 px, ein Raster. '
           f'Platzierung per <code>g.K = (x0, y0, R)</code>, Drehung per <code>g.rot</code>.</p><nav>{nav}</nav>'
           f'<h2>Plakate im echten Satz · A3</h2><p class="d">Kandidat als Stern-Ebene in <code>styles.render()</code>: '
           f'Titel, Datum, QR, Kopfzeile und XOR-Regel aus styles.py. Sortiert nach Bewertung.</p><div class="pg">{"".join(posters)}</div>'
           f'<h2>Alle Kandidaten · 16x9</h2><p class="d">Gross: Tscherenkow. Rechts: Riso, Eklipse, CGA, Phosphor, Lavendel. '
           f'Ausgegraut = raus (alte Renderings).</p>'
           f'{"".join(parts)}</main></body></html>')
    with open(os.path.join(OUT, "index.html"), "w") as fh:
        fh.write(doc)


HAND_EDGE_ZONE_CELLS = 10    # Selbsttest S54b: gemessen wird nur so nah an Titelblock / JOIN US + QR (Zellen)
HAND_EDGE_MAX_CELLS = 20     # Selbsttest S54b: laengste gerade (achsparallele) Kante eines Schraffurfelds, Zellen. S54 hat
                             # dort 80 (Kante von _qr_zone/_type_zone). Gemessen 1.10.: S54b 12, S54c 13 = drei Striche
                             # (Abstand 4 Zellen), die zufaellig auf derselben Zeile absetzen; ein Wuerfel ist feldbreit


def selftest_hand(codes=("S54", "S54b", "S54c"), frames=(0, 15)):
    """Selbsttest am fertigen Plakat des Loops (Frame 1 und 16: grosser Stern an QR bzw. Titel): Schraffurfelder duerfen
    nicht an einer geraden Kante enden (Vadim 1.10. zu S54: "diese getrennten Wuerfel sehen komisch aus"). Tinte = Zellen
    im Stern, dunkler als die zwei hellsten Stufen (Pergament); Feld = Tinte geschlossen (5x5); gemessen wird die
    laengste waagerechte bzw. senkrechte Feldkante am Rand von Titelblock / JOIN US + QR. S54 muss anschlagen (Nachweis, dass der Test sieht),
    S54b/S54c muessen durchgehen. Liefert {code: laengste Kante} und bricht ab, wenn das nicht stimmt."""
    import kickoff_loop as KL
    from scipy.ndimage import binary_closing
    cfg = KL.load()
    got = {}
    for code in codes:
        worst = 0
        for i in frames:
            st = KL.poster_style(cfg, i)
            st["S"] = "lab:" + code
            img = KL.frame(cfg, i, style=st).astype(np.float32) @ KL.LUMA
            c = styles.Ctx(st, KL.PREVIEW)
            g = G(st, KL.PREVIEW, c)
            cx, cy, R, _ = c.L["star"]
            g.K, g.rot = (cx / g.m, cy / g.m, R / g.m), st.get("rot")
            x0, y0, R, rot, x, y = _local(g)
            inner = sd(x, y, rot) < 1 - 4 * _cell(g) / R
            lum = img[c.px // 2::c.px, c.px // 2::c.px][:g.gh, :g.gw]
            pl = hexpal(st["P"]).astype(np.float32) @ KL.LUMA                  # Pergament liegt im Korn zwischen den 2
            ink = inner & (lum < (pl[-2] + pl[-3]) / 2)                       # hellsten Stufen: Tinte = ab 3.-hellster
            field = binary_closing(ink, np.ones((5, 5), bool)) & inner
            fr = _keep_free(g)
            near = (fr < HAND_EDGE_ZONE_CELLS) & inner                        # nur am Rand von Titel/QR (dort sassen die
            out = fr > 0                                                      # Wuerfel); Kanten ganz in der Zone (JOIN US)
            for f, m, o in ((field, near, out), (field.T, near.T, out.T)):   # zaehlen nicht, Grate duerfen gerade sein
                edge = (f[:-1] ^ f[1:]) & m[:-1] & m[1:] & (o[:-1] | o[1:])   # Feld endet zur naechsten Zeile hin
                for row in edge:
                    runs = np.diff(np.r_[0, row.astype(np.int8), 0])
                    if runs.any():
                        worst = max(worst, int((np.nonzero(runs == -1)[0] - np.nonzero(runs == 1)[0]).max()))
        got[code] = worst
    print("Selbsttest Hand (laengste gerade Schraffurkante, Zellen):", got, "Grenze", HAND_EDGE_MAX_CELLS)
    assert got.get("S54", HAND_EDGE_MAX_CELLS + 1) > HAND_EDGE_MAX_CELLS, "Test blind: S54 (Wuerfel) schlaegt nicht an"
    bad = {k: v for k, v in got.items() if k != "S54" and v > HAND_EDGE_MAX_CELLS}
    assert not bad, f"gerade Schraffurkanten (Wuerfel): {bad}"
    return got


def main():
    """Argumente: Codes (S31b ...; ohne = alle behaltenen), --pal a,b | all, --fmt 16x9|9x16|a3, --kick (Test mit
    Kick-off-Titel SPARK nach styles/lab/spark/_kick/), --sheet name. 'posters [codes]' = A3 im echten Satz, 'html' = Galerie.
    'test' = Selbsttest der Handschraffur (S54b/c gegen S54) am fertigen Loop-Plakat."""
    os.makedirs(OUT, exist_ok=True)
    args = sys.argv[1:]
    if args == ["test"]:
        selftest_hand()
        return
    if args == ["sheet"] or args == ["html"]:
        gallery()
        return
    if args and args[0] == "posters":             # posters [S31b S26 ...]
        want = args[1:] or list(POSTERS)
        with Pool(4) as pool:                     # A3-Ebenen sind gross: mehr Prozesse = Swap
            files = list(pool.imap(job_poster, [(c, p, d) for c in want for p, d in POSTERS[c]]))
        print("\n".join(os.path.relpath(f, ROOT) for f in files))
        sheet(files, os.path.join(OUT, "sheet_posters.png"), cols=min(8, len(files)), tw=300)
        gallery()
        return
    fmt = args[args.index("--fmt") + 1] if "--fmt" in args else "16x9"
    pals = args[args.index("--pal") + 1].split(",") if "--pal" in args else ["lav"]
    pals = PALS16 if pals == ["all"] else pals
    kick = "--kick" in args
    name = args[args.index("--sheet") + 1] if "--sheet" in args else None
    codes = [a for a in args if a in BY or a in CMP] or KEPT
    os.makedirs(TMP, exist_ok=True)
    jobs = [(c, p, fmt, kick) for c in codes for p in pals]
    with Pool() as pool:
        files = list(pool.imap(job, jobs))
    for f in files:
        print(os.path.relpath(f, ROOT))
    if len(files) > 1:
        tag = name or ("_".join(pals) + "_" + fmt + ("_kick" if kick else ""))
        cols = len(pals) if 1 < len(pals) <= 6 else (4 if fmt != "a3" else 6)
        sheet(files, os.path.join(TMP if kick else OUT, f"sheet_{tag}.png"), cols=cols, tw=480 if fmt != "a3" else 300)
    if not kick:
        gallery()


if __name__ == "__main__":
    main()
