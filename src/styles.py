#!/usr/bin/env python3
"""SPARK Maker-Night-System: Keyvisual aus freigegebenen Bausteinen, als Board, Looks, Plakate und Bewegungstests.

Bausteine (Codes stabil, verworfene Codes werden nie neu vergeben):
  T Typo   D Dither   P Palette/Colorway   S Spark-Stern   K Komposition   R Pixelgroesse
Status pro Baustein: "ja" = freigegeben (Plakat-Mix), "neu" = zur Auswahl, "geparkt" = im Blick, nicht im Mix.

Grundidee: alles lebt auf EINEM logischen Pixelraster. Jede Ebene ist ein Wertfeld v in [0,1], das auf die
Palette gedithert wird. Exakte Palettenstufen bleiben flaechig, alles dazwischen wird Korn.

  uv run -q --with numpy --with pillow --with scipy --with qrcode python src/styles.py   # alles
  uv run ... python src/styles.py board | looks | posters | overlays | motion              # Teil
  uv run ... python src/styles.py posters 24 7                                            # 24 Unikat-Plakate, Seed 7
  uv run ... python src/styles.py one L2 a3                                               # ein Code
-> styles/  board/*.png, looks/<code>/<fmt>/*.png, posters/*.png, overlays/*.png, motion/*.mp4, index.html
"""
import html
import os
import subprocess
import sys
from collections import Counter
from itertools import product
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter, map_coordinates

from makernight import blue_noise
from makernight_sparks import star_r

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "styles")
FONTS = os.path.expanduser("~/Library/Fonts/")
# W, H, u: u = Displaypixel pro "1080p-Pixel". R und alle Masse skalieren mit u, damit ein Plakat wie der Screen aussieht.
# ponytail: A3 = 3504x4956 (300 dpi, 1-2 px kuerzer als 3508x4961), damit beide Seiten durch R*u teilbar sind.
SIZES = {"16x9": (1920, 1080, 1), "9x16": (1080, 1920, 1), "a3": (3504, 4956, 3)}
# QR = Telegram-Gruppe fuer Updates, bewusst ohne Beschriftung (man muss scannen, um es zu verstehen)
COPY = {"title": ("MAKER", "NIGHT"), "date": "20–21 NOV", "org": "SPARK", "qr_url": "https://t.me/+TnDm1terktk1ZTNi"}

# K = Komposition: wo der Stern sitzt (cx, cy relativ zu W/H, R relativ zur kurzen Seite), hoch / quer.
# Alle Schrift kippt dort in die Grundfarbe, wo sie ueber leuchtendem Stern liegt (XOR, haelt sie lesbar).
# only: Stern-Varianten, mit denen die Komposition funktioniert (Nest/Ringe hinter dem Titel = unlesbar).
KOMP = {
    "riese":   dict(port=(0.86, 0.68, 0.74), land=(0.82, 0.62, 0.70)),     # 2026-09-25: tiefer, groesser, mehr Anschnitt
    "aufgang": dict(port=(0.66, 0.90, 0.80), land=(0.70, 0.96, 0.95)),     # 2026-09-25: hoeher, weniger Leerraum
    "xor":     dict(port=(0.66, None, 0.86), land=(0.44, None, 0.80), only=("grad", "matrjoschka")),   # None = Titelmitte
    "koloss":  dict(port=(1.02, 0.70, 0.98), land=(0.98, 0.70, 0.95)),     # Mitte am rechten Rand, fuellt die untere Haelfte
    "ecke":    dict(port=(0.98, 1.00, 1.20), land=(1.00, 1.05, 1.10)),     # aus der Ecke unten rechts
    "kern":    dict(port=(0.58, 0.70, 0.64), land=(0.66, 0.60, 0.60)),     # sitzt im Leerraum, beide Seiten angeschnitten
    "sturz":   dict(port=(0.90, 0.30, 1.05), land=(0.86, 0.20, 0.90)),     # faellt von oben rechts durch den Titel
    "wand":    dict(port=(-0.04, 0.64, 1.00), land=(0.10, 0.70, 0.75)),     # aus der linken Kante, hinter QR und Schrift
}

PALS = {  # Grund -> Tinte (dunkel -> hell, bei Papier/Riso hell -> dunkel)
    "lav": ["#0A0711", "#221643", "#43287C", "#7049C4", "#AE93EE", "#F6F2FF"],
    "acid": ["#0A0711", "#221643", "#43287C", "#7049C4", "#AE93EE", "#D7FF3A"],
    "cga": ["#000000", "#FF55FF", "#55FFFF", "#FFFFFF"],
    "paper": ["#D6C8F4", "#B49DEB", "#8B68D8", "#6A3FB5", "#432379", "#150E26"],   # Hellton Lavendel statt Weiss
    # neue Dimensionen (Status "neu", zur Auswahl)
    "laser": ["#070608", "#2A080E", "#FF2A3D", "#FFFFFF"],                          # 1-Bit + Laserrot
    "phosphor": ["#030803", "#06240C", "#0E5A1E", "#1FA83A", "#5CFF6E", "#D8FFD8"],
    "cherenkov": ["#02030A", "#051238", "#0A2FA0", "#1F6BFF", "#6FD0FF", "#E8FBFF"],
    "uv": ["#0B0418", "#2A0B52", "#5A12A8", "#B01CFF", "#FF4FD8", "#FFE6FA"],
    "holo": ["#07060C", "#14215A", "#1C5A8C", "#2FB5A8", "#B8F07A", "#FFF2FB"],
    "eclipse": ["#050505", "#1A1408", "#4A3610", "#A87A1C", "#F2C14E", "#FFF6DA"],
    "blueprint": ["#0F2A6E", "#173A8A", "#2450A8", "#4F7FD0", "#A9C6F2", "#F4F8FF"],
    "riso": ["#FFD9EC", "#FF9FD2", "#FF48B0", "#3255A4", "#1B2A6B", "#0D1030"],
    # Kick-off-Kampagne (2026-09-25): wild, kein Lila. Rampen kreuzen den Farbkreis, der Dither mischt die Welten.
    "signal": ["#07080F", "#0B2A8F", "#0047FF", "#FF5A1F", "#FFB000", "#FFF4D6"],
    "lava": ["#0A0302", "#3A0A05", "#9E1B0A", "#FF4A12", "#FFB21F", "#FFF3C4"],
    "kirsche": ["#1A0003", "#5C0010", "#D1002C", "#FF3B5C", "#C8FF00", "#F4FFD0"],
    "klein": ["#000833", "#001A8C", "#002FA7", "#3D6BFF", "#FFE500", "#FFFBE0"],
    "minze": ["#D8FFF0", "#9FF5D6", "#3FD9B0", "#FF3D5A", "#B0122E", "#2A0510"],
    "orangerie": ["#FFE3CC", "#FFB27A", "#FF6A1F", "#1F4FD1", "#0E2A80", "#07122E"],
    "eis": ["#F2FBFF", "#BDEBFF", "#5CC8FF", "#0A84FF", "#003C99", "#001233"],
    "zitrone": ["#FFF36B", "#FFD21F", "#FF8A00", "#E0101E", "#5A0008", "#120003"],
    "tokio": ["#050508", "#08233A", "#00A8C8", "#00F0FF", "#FF2E88", "#FFE8F2"],
    "cga0": ["#000000", "#00AA00", "#FF5555", "#FFFF55"],
}

# Codename pro Colorway, steht rechts in der Kopfzeile (ersetzt "DIM 042 · <deutscher Name>", 2026-09-25)
CODENAME = {"lav": "NIGHTSHADE", "acid": "ACID RAIN", "cga": "MODE 04H", "paper": "PAPER MOON", "laser": "RED LASER",
            "phosphor": "P1 GREEN", "cherenkov": "CHERENKOV", "uv": "BLACKLIGHT", "holo": "HOLOFOIL", "eclipse": "TOTALITY",
            "blueprint": "CYANOTYPE", "riso": "FLUO PINK", "signal": "SIGNAL FLARE", "lava": "MOLTEN", "kirsche": "CHERRY BOMB",
            "klein": "IKB 191", "minze": "MINT CONDITION", "orangerie": "SAFETY ORANGE", "eis": "ABSOLUTE ZERO",
            "zitrone": "HAZARD", "tokio": "AFTERHOURS", "cga0": "PALETTE ZERO"}
assert set(CODENAME) == set(PALS)


def lila(p):
    """True, wenn die Palette Lila enthaelt (Farbton 250-300 Grad, gesaettigt, sichtbar). Lila gehoert der Maker Night."""
    import colorsys
    return any(250 <= h * 360 < 300 and s > 0.3 and v > 0.12
               for h, s, v in (colorsys.rgb_to_hsv(*[int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]) for c in PALS[p]))

# Datei, Variation, native Pixelgroesse (None = Vektorfont, wird in Zielgroesse gerastert), native Versalhoehe
FONTSPEC = {
    "clash": ("ClashDisplay-Variable.ttf", "Bold", None, None),
    "departure": ("DepartureMono-Regular.otf", None, 11, 8),
}
F_LO, F_HI = 0.7, 0.98          # Titel-Fuellung: unten Lavendel, oben fast Weissglut


def font(name, size, var=None):
    f = ImageFont.truetype(FONTS + name, size)
    if var:
        f.set_variation_by_name(var)
    return f


def hexpal(p):
    return np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in PALS[p]], np.float32)


# ---------------------------------------------------------------- Dither: Wertfeld (logisch) -> Palettenindex (voll)

def bayer(n):
    m = np.zeros((1, 1))
    while len(m) < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / m.size


BN = blue_noise(128, 5)


def tile(t, shape):
    return np.tile(t, (shape[0] // t.shape[0] + 1, shape[1] // t.shape[1] + 1))[:shape[0], :shape[1]]


def dither(v, N, D, px, seed=0, shift=(0, 0)):
    """shift (Zellen y, x): Schwellenmuster verschieben. Wechselt es von Bild zu Bild, "kocht" das Korn wie
    handgezeichnete Linien (Boil); bleibt es (0, 0), ist alles wie immer. px = 1: Palettenindex je Zelle."""
    thr = {"blue": lambda s: tile(np.roll(BN, (seed * 37 % 128, seed * 71 % 128), (0, 1)), s),
           "bayer2": lambda s: tile(bayer(2), s), "bayer4": lambda s: tile(bayer(4), s),
           "lines": lambda s: np.broadcast_to(((np.arange(s[0]) % 4 + 0.5) / 4)[:, None], s),
           "white": lambda s: np.random.default_rng(7 + seed).random(s)}[D](v.shape)
    thr = np.roll(thr, shift, (0, 1)) if any(shift) else thr
    x = np.clip(v, 0, 1) * N + 1e-4
    lo = np.floor(x)
    return up(np.clip(lo + (x - lo > thr), 0, N).astype(np.int8), px)


# ---------------------------------------------------------------- Typo auf dem logischen Raster

def line_mask(s, T, cap_px, base, x, px, shape, right=False):
    """Bool-Maske (logisch) einer Zeile, Tinte beginnt bei x (right: endet bei x), Grundlinie bei base (Displaypixel)."""
    name, var, native, ncap = FONTSPEC[T]
    cap = cap_px / px
    if native:
        k, f = max(1, round(cap / ncap)), font(name, native, var)
    else:
        f0 = font(name, 100, var)
        k, f = 1, font(name, max(6, round(100 * cap / -f0.getbbox("H", anchor="ls")[1])), var)
    if not native:                                # Clash-Wortabstand (0,21 Versal) ist fuer Plakatsatz zu eng
        s = s.replace(" ", "  ")
    if "–" in s and f.getmask("–").getbbox() is None:
        s = s.replace("–", "-")
    l, t, r, b = f.getbbox(s, anchor="ls")
    im = Image.new("L", (r - l + 2, b - t + 2))
    ImageDraw.Draw(im).text((1 - l, 1 - t), s, font=f, fill=255, anchor="ls")
    m = up(np.asarray(im) > 127, k)
    top, left = round(base / px) + (t - 1) * k, round(x / px) - (m.shape[1] - k if right else k)
    out = np.zeros(shape, bool)
    y0, x0 = max(0, top), max(0, left)
    y1, x1 = min(shape[0], top + m.shape[0]), min(shape[1], left + m.shape[1])
    if y0 < y1 and x0 < x1:
        out[y0:y1, x0:x1] = m[y0 - top:y1 - top, x0 - left:x1 - left]
    return out


def width_per_cap(s, T="clash"):
    """Breite einer Zeile in Versalhoehen (Vektorfont), um Titel auf ein Mass zu setzen."""
    f = font(FONTSPEC[T][0], 200, FONTSPEC[T][1])
    l, _, r, _ = f.getbbox(s.replace(" ", "  "), anchor="ls")
    return (r - l) / -f.getbbox("H", anchor="ls")[1]


def down(a, px):
    h, w = a.shape
    return a.reshape(h // px, px, w // px, px).mean((1, 3))


def up(a, px):
    return np.repeat(np.repeat(a, px, 0), px, 1)


# ---------------------------------------------------------------- Szene

class Ctx:
    def __init__(self, st, fmt):
        self.st, self.fmt = st, fmt
        self.W, self.H, self.u = SIZES[fmt]
        self.px = st["R"] * self.u
        self.gw, self.gh = self.W // self.px, self.H // self.px
        self.pal = hexpal(st["P"])
        self.N = len(self.pal) - 1
        yy, xx = np.mgrid[0:self.gh, 0:self.gw].astype(np.float32)
        self.yy, self.xx = yy, xx
        self.cy, self.cx = (yy + 0.5) * self.px, (xx + 0.5) * self.px   # Zellmitten in Displaypixeln
        self.layers = []                                                  # (name, alpha voll, v logisch, flach, eigenes D)
        lum = self.pal @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        self.lo, self.hi = int(lum.argmin()), int(lum.argmax())           # QR: dunkelste Module auf hellster Platte
        self.L = st.get("layout", layout)(self)                            # Kampagne kann eigenen Satz mitbringen

    def lvl(self, k):
        """Exakte Palettenstufe (rendert flaechig, ohne Korn)."""
        return min(max(k, 0), self.N) / self.N

    @property
    def ink(self):
        """Stufe fuer kleine Schrift: zweithellste, bei 1-/2-Bit die hellste."""
        return self.lvl(self.N - 1 if self.N > 2 else self.N)

    def add(self, name, mask, v, D=None):
        flat = round(v * self.N) if np.isscalar(v) and abs(v * self.N - round(v * self.N)) < 1e-6 else None
        self.layers.append((name, up(mask.astype(np.float32), self.px), np.where(mask, v, np.nan), flat, D))


def star_d(c, cx, cy, R, rot):
    dx, dy = c.cx - cx, c.cy - cy
    rr = np.hypot(dx, dy)
    return rr / (star_r(dx, dy, rot) * R), rr


def layout(c):
    """Satz in Displaypixeln: Kopfzeile, Titel (auf Mass gesetzt), Datum, QR-Block unten links, Stern laut K."""
    W, H, px = c.W, c.H, c.px
    port, short = H > W, min(W, H)
    snap = lambda v: round(v / px) * px                                        # noqa: E731
    m = snap(0.07 * short)
    sc = 0.026 * short                                                         # Kleintext-Versalhoehe
    title = COPY["title"] if port else (" ".join(COPY["title"]),)
    measure = W - 2 * m if port else 0.6 * W
    cap = (measure / px // max(map(width_per_cap, title))) * px
    meta = m + snap(sc)
    tb = [meta + snap(0.4 * cap) + cap + i * snap(1.14 * cap) for i in range(len(title))]
    capd = snap((0.46 if port else 0.5) * cap)
    db = tb[-1] + snap(0.42 * cap) + capd
    q = qr_matrix()
    qs = (len(q) + 6) * 2 * px                                                 # Modul = 2 logische Pixel, 3 Module Rand
    qbot = H - m
    k = KOMP[c.st["K"]]
    fx_, fy, fr = k["port" if port else "land"]
    cy = (tb[0] + tb[-1]) / 2 - cap / 2 if fy is None else fy * H
    return dict(m=m, sc=sc, title=title, cap=cap, tb=tb, meta=meta, capd=capd, db=db, q=q, qs=qs, qbot=qbot, star=(fx_ * W, cy, fr * short, c.st.get("rot", 14)))


def qr_matrix():
    import qrcode
    q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(COPY["qr_url"])
    q.make(fit=True)
    return np.array(q.get_matrix(), bool)


def ground_shape(c, lin):
    """Form des Grunds, 0..1 auf dem Zellraster. Ohne st["ground"] (alle Projekte bis 3.10.) der lineare Verlauf lin,
    bitgleich wie bisher. Vadim 3.10.: "nicht einfach von oben nach unten ein Linear-Gradient". Werte aus [ground]:
      mode = islands: Metaballs (Summe von Gauss-Glocken), jede Insel faehrt ueber einen Umlauf (st["loop"]) einen
        geschlossenen Kreis, der Loop bleibt nahtlos. islands, size_frac [min, max] (Radius, kurze Seite), drift_frac
        (Kreisradius der Fahrt), warp_frac (wellige Kueste).
      mode = flow (Vadim 3.10.: "harte Landmassen, aber mehr Stufen, eher ein Gradient, der flowy ist, im 8-Bit-Style"):
        Verlauf in Richtung angle_deg, die Koordinaten von waves Wellen (zufaellige Richtung, wave_freq Perioden pro
        kurzer Seite) quer verbogen, nacheinander (das Verbiegen faltet sich: fliesst statt wellt). Jede Welle laeuft
        flow_per_loop Perioden pro Umlauf weiter (ganzzahlig: nahtlos, 0 = steht). islands > 0 mischt Inseln dazu.
      Fuer beide: terraces (0 = weich, n = harte Hoehenstufen), blocks_cells (0 = aus, k = Feld nur je k x k Zellen
      ausgewertet: grobe Quadrate), gain (Hoehe, 1 = so hell wie der lineare Verlauf unten), lin_frac (Rest des alten
      Verlaufs), seed."""
    gd = c.st.get("ground")
    if not gd or gd["mode"] == "linear":
        return lin
    m = min(c.W, c.H)
    b = gd.get("blocks_cells", 0) * c.px
    X, Y = ((np.floor(c.cx / b) + 0.5) * b / m, (np.floor(c.cy / b) + 0.5) * b / m) if b else (c.cx / m, c.cy / m)
    lp = c.st.get("loop") or {}
    t = 2 * np.pi * lp.get("i", 0) / max(lp.get("n", 1), 1)
    rng = np.random.default_rng(gd["seed"])
    if gd["mode"] == "islands":
        f = _islands(gd, rng, X, Y, t, c.W / m, c.H / m)
    else:
        a = np.radians(gd["angle_deg"])
        for _ in range(gd["waves"]):
            d, fr, ph = rng.uniform(0, 2 * np.pi), rng.uniform(*gd["wave_freq"]), rng.uniform(0, 2 * np.pi)
            w = gd["warp_frac"] * np.sin(2 * np.pi * fr * (X * np.cos(d) + Y * np.sin(d)) + ph + gd["flow_per_loop"] * t)
            X, Y = X - w * np.sin(d), Y + w * np.cos(d)       # quer zur Welle schieben
        corners = np.array([0, c.W / m]) [:, None] * np.cos(a) + np.array([0, c.H / m])[None] * np.sin(a)
        f = np.clip((X * np.cos(a) + Y * np.sin(a) - corners.min()) / np.ptp(corners), 0, 1)
        if gd.get("islands"):
            f = (f + _islands(gd, np.random.default_rng(gd["seed"] + 1), X, Y, t, c.W / m, c.H / m)) / 2
    if gd["terraces"]:
        f = np.floor(f * gd["terraces"] + 0.5) / gd["terraces"]
    return gd["lin_frac"] * lin + gd["gain"] * f


def _islands(gd, rng, X, Y, t, A, B):
    """Inselfeld 0..1 auf der Seite A x B (kurze Seite = 1): Metaballs, fahren pro Umlauf einen Kreis."""
    if gd["mode"] == "islands" and gd["warp_frac"]:          # Kueste: Koordinaten mit zwei Wellen verbiegen
        a, b = rng.uniform(0, 2 * np.pi, 2)
        X, Y = (X + gd["warp_frac"] * np.sin(9 * Y + a + t), Y + gd["warp_frac"] * np.sin(7 * X + b - t))
    f = np.zeros(X.shape)
    for _ in range(gd["islands"]):
        x0, y0 = rng.uniform(0, A), rng.uniform(0, B)
        r, ph = rng.uniform(*gd["size_frac"]), rng.uniform(0, 2 * np.pi)
        x0, y0 = x0 + gd["drift_frac"] * np.cos(t + ph), y0 + gd["drift_frac"] * np.sin(t + ph)
        f += np.exp(-((X - x0) ** 2 + (Y - y0) ** 2) / r ** 2)
    return np.clip(f, 0, 1)


def ground(c):
    """Der blanke Grund ohne Stern-Schein (fuer Hintergrund-Boegen)."""
    nx, ny = (c.xx + 0.5) / c.gw, (c.yy + 0.5) / c.gh
    grad = (0.35 * nx + ny) / 1.35 if c.W > c.H else ny
    neb = gaussian_filter(np.random.default_rng(26).standard_normal((c.gh, c.gw)), 88 * c.u / c.px)
    return 0.025 + 0.085 * ground_shape(c, grad ** 1.3) + 0.01 * neb / neb.std()


def background(c):
    v = ground(c)
    cx, cy, R, rot = c.L["star"]
    d, rr = star_d(c, cx, cy, R, rot)
    return v + np.where(d > 1, 0.15 * np.exp(-(d - 1) / 0.3) + 0.16 * np.exp(-rr / R / 1.6), 0)


def spark(c):
    S = c.st["S"]
    cx, cy, R, rot = c.L["star"]
    d, _ = star_d(c, cx, cy, R, rot)
    grad = 0.64 + 0.36 * np.clip(1 - d, 0, 1) ** 0.7
    m, D = d < 1, None
    if S == "lines":                              # Verlauf als Linienraster, nur im Stern (Rest bleibt D)
        D = "lines"
    elif S == "contour":                          # Hoehenlinien des Sterns
        band = (d * 7 + c.st.get("phase", 0)) % 1               # phase: Palette-Cycling-Ringe
        m, grad = m & (band < 0.4), 0.62 + 0.38 * np.clip(1 - d, 0, 1)
    elif S == "matrjoschka":                      # 3-5 Sterne ineinander, dazwischen Luft, die mit Rauschen ausdithert
        n, r = c.st.get("dolls", 4), 0.64
        q = np.log(np.maximum(d, 1e-6)) / np.log(r)               # 0 am Aussenrand, +1 pro Puppe
        k, f = np.floor(q), q - np.floor(q)
        shell = (f < 0.42) | (k >= n - 1)
        noise = np.random.default_rng(c.st.get("seed", 0) + 5).random(d.shape) - 0.5
        fade = np.exp(-(f - 0.42) / 0.16)                           # Puppe laeuft nach innen in Korn aus
        val = 0.60 + 0.38 * np.clip(k / (n - 1), 0, 1)
        grad = np.where(shell, val, np.clip(0.16 + (val - 0.16) * fade + 0.22 * noise * (1 - fade), 0, 1))
        m = d < 1
        c.star_m = m & shell
        c.add("spark", m, grad)
        return
    elif S == "nest":                             # XOR-Nest; nest_phase > 0: Tunnel, die Sterne wachsen stetig nach aussen
        ph = c.st.get("nest_phase", 0.0)          # (Hypno-Loop). Alle Sterne bleiben im XOR, auch wenn sie das Bild schon
        m = np.zeros(d.shape, bool)               # fuellen: so kippt die Paritaet nie (Rezept "Infinite Nest tunnel")
        for k in range(6 if ph == 0 else 12 + int(np.ceil(ph))):      # Tunnel: neue Sterne entstehen winzig (0.74^11)
            dk, _ = star_d(c, cx, cy, R * 0.74 ** (k - ph), rot + 30 * (k - ph))
            m ^= dk < 1
        if ph:
            m &= d < 1                            # Tunnel nur im Fenster des aeussersten Sterns, der Satz bleibt frei
    c.star_m = m
    c.add("spark", m, grad, D=D)


def type_layers(c):
    L, px, W = c.L, c.px, c.W
    x, sc, cap = L["m"], L["sc"], L["cap"]
    shape = (c.gh, c.gw)
    flip = lambda v: np.where(c.star_m, c.lvl(0), v)                         # noqa: E731

    def fill(bases, capL):                        # gedithterter Verlauf in den Buchstaben: unten Lavendel, oben Weissglut
        rel = np.zeros(shape, np.float32)
        for b in bases:
            band = (c.cy <= b + 0.1 * capL) & (c.cy > b - 1.4 * capL)
            rel = np.where(band, np.clip((c.cy - (b - capL)) / capL, 0, 1), rel)
        return F_LO + (F_HI - F_LO) * (1 - rel)

    for name, lines, bases, capL in (("title", L["title"], L["tb"], cap), ("date", (COPY["date"],), [L["db"]], L["capd"])):
        mk = np.zeros(shape, bool)
        for s, b in zip(lines, bases):
            mk |= line_mask(s, "clash", capL, b, x, px, shape)
        c.add(name, mk, flip(fill(bases, capL)))

    small = lambda s, b, xx, right=False: line_mask(s, "departure", sc, b, xx, px, shape, right)   # noqa: E731
    c.add("meta", small(COPY["org"], L["meta"], x) | small(CODENAME[c.st["P"]], L["meta"], W - x, True), flip(c.ink))

    q, qs = L["q"], L["qs"]
    top, left = round((L["qbot"] - qs) / px), round(x / px)
    n = qs // px
    plate = np.zeros(shape, bool)
    plate[top:top + n, left:left + n] = True
    mods = np.zeros(shape, bool)
    mods[top + 6:top + n - 6, left + 6:left + n - 6] = up(q, 2)
    c.add("qr", plate, c.lvl(c.hi))
    c.add("qr", mods, c.lvl(c.lo))


# ---------------------------------------------------------------- Render

def render(st, fmt="16x9", layers=True):
    """-> (frame RGB uint8, {ebene: RGBA uint8}). layers=False: nur das Bild, das Ebenen-Dict bleibt leer, und das
    Bild wird auf dem Zellraster zusammengesetzt (px x px weniger Pixel) und erst am Ende hochskaliert. Bitgleich, weil
    jede Eingabe (Index aus dither, Ebenen-Alpha aus Ctx.add) pro Zelle konstant ist; das wird je Ebene geprueft,
    sonst rechnet es in voller Aufloesung wie bisher. Zusammen ~3-5x schneller (Befund 2.10.: kickoff.frame_of warf
    pro Ebene ein volles RGBA-Float-Bild weg, das Zusammensetzen war 2/3 der Renderzeit)."""
    c = Ctx(st, fmt)
    bg = background(c)
    st.get("spark_fn", spark)(c)
    st.get("type_fn", type_layers)(c)
    V = bg.copy()
    for _, _, v, _, _ in c.layers:
        V = np.where(np.isnan(v), V, v)
    D, sd, sh = st["D"], st.get("seed", 0), tuple(st.get("dither_shift", (0, 0)))
    p = c.px
    cells = not layers and c.gh * p == c.H and c.gw * p == c.W and all(
        np.array_equal(up(a[::p, ::p], p), a) for _, a, *_ in c.layers)
    q = 1 if cells else p                                  # Pixel pro Zelle, in denen zusammengesetzt wird
    idx_bg, idx = dither(bg, c.N, D, q, sd, sh), dither(V, c.N, D, q, sd, sh)
    frame = c.pal[idx_bg]
    out = {"bg": np.dstack([c.pal[idx_bg], np.full((c.H, c.W), 255, np.float32)])} if layers else {}
    full = None                                   # c.pal[idx] ist fuer alle Ebenen ohne eigenes D gleich: einmal rechnen
    for name, a, _, flat, own in c.layers:
        a = a[::p, ::p] if cells else a
        if flat is not None:
            col = c.pal[flat]
        elif own:
            col = c.pal[dither(V, c.N, own, q, sd, sh)]
        else:
            full = c.pal[idx] if full is None else full
            col = full
        frame += a[..., None] * (col - frame)
        if layers:
            rgba = out.get(name, np.zeros((c.H, c.W, 4), np.float32))
            rgba[..., :3] += a[..., None] * (col - rgba[..., :3])
            rgba[..., 3] = np.maximum(rgba[..., 3], a * 255)
            out[name] = rgba
    frame = np.clip(frame, 0, 255).astype(np.uint8)
    return up(frame, p) if cells else frame, {k: np.clip(v, 0, 255).astype(np.uint8) for k, v in out.items()}


# ---------------------------------------------------------------- Bausteine (Stand: Feedback 2026-09-25)

BASE = dict(T="clashbit", D="bayer4", P="lav", S="grad", K="riese", R=4)

# (Achse, Name, Beschreibung, [(Code, Wert, Titel, Text, Status)])
# Status: ja = im Plakat-Mix, neu = zur Auswahl (Board + Review-Serie), geparkt = im Blick, nicht im Mix.
# Verworfen und nie wieder vergeben: D4 D5-D9 D10, P2 (1-Bit pur), P3, P4 (Orange-Lila), P7, alle F (F5 CRT raus 2026-09-25),
# R2 R4+, S1 S3 S4 S6 S8-S11, T1 T3+, M1 M2 (Spin) M3 M4 M6 M7 (Schreibmaschine) M8 (Sine-Scroller) M9 M10 (CRT-Aufbau).
# Lila (P1 P5 P8 P12) gehoert exklusiv der Maker Night, die Kick-off-Kampagne (src/kickoff.py) nimmt nur Paletten ohne lila().
AXES = [
    ("T", "Typo", "Clash Display Bold direkt auf dem Pixelraster. Kleintext DepartureMono in nativen Vielfachen.", [
        ("T2", "clashbit", "Clash-Bit", "Bleibt Spark, wird 8-Bit.", "ja"),
    ]),
    ("D", "Dither", "Wie Verlaeufe zu Pixeln werden. D3 ist der Hauptdither, die anderen sind geparkt.", [
        ("D3", "bayer4", "Bayer 4x4", "Die Kreuze. Hauptdither fuer alles.", "ja"),
        ("D1", "blue", "Blue Noise", "Gleichmaessiges Korn, bleibt fuer den 15-fps-Boil in Bewegung.", "geparkt"),
        ("D2", "bayer2", "Bayer 2x2", "Grobes Schachbrett.", "geparkt"),
    ]),
    ("P", "Colorway", "Jede Farbrampe ist eine eigene Dimension. Der Hauptregler fuer Abwechslung auf den Plakaten.", [
        ("P1", "lav", "Lavendel-Nacht", "Basis.", "ja"),
        ("P5", "acid", "Acid", "Lila-Rampe, hellste Stufe Giftgruen.", "ja"),
        ("P6", "cga", "CGA", "Schwarz/Magenta/Cyan/Weiss.", "ja"),
        ("P8", "paper", "Papier", "Invertiert, Hellton Lavendel.", "ja"),
        ("P9", "laser", "Laser", "Ersatz fuer 1-Bit: Schwarz/Weiss mit Laserrot als einziger Farbe.", "ja"),
        ("P10", "phosphor", "Phosphor", "Gruener Terminal-Monitor.", "ja"),
        ("P11", "cherenkov", "Tscherenkow", "Reaktorblau: Schwarz, elektrisches Blau, Weissblau.", "ja"),
        ("P12", "uv", "Schwarzlicht", "Tiefes Violett, Fluo-Pink.", "ja"),
        ("P13", "holo", "Holo", "Schillernd: Nachtblau, Petrol, Limette, Perlweiss.", "ja"),
        ("P14", "eclipse", "Eklipse", "Schwarz und Gold, Korona.", "ja"),
        ("P15", "blueprint", "Blaupause", "Heller Blaugrund, weisse Zeichnung.", "ja"),
        ("P16", "riso", "Riso", "Fluo-Pink-Papier, Riso-Blau als Tinte.", "ja"),
        ("P17", "signal", "Signal", "Kobalt kippt in Orange und Bernstein.", "neu"),
        ("P18", "lava", "Lava", "Schwarz, Glutrot, Orange, Gelb.", "neu"),
        ("P19", "kirsche", "Kirsche", "Kirschrot, die hellste Stufe Limette.", "neu"),
        ("P20", "klein", "Klein-Blau", "Ultramarin mit Sonnengelb.", "neu"),
        ("P21", "minze", "Minze", "Riso: Mintpapier, rote Tinte.", "neu"),
        ("P22", "orangerie", "Orangerie", "Riso: Orangepapier, blaue Tinte.", "neu"),
        ("P23", "eis", "Eis", "Weisses Papier, Cyan bis Tiefblau.", "neu"),
        ("P24", "zitrone", "Zitrone", "Gelbes Papier, Orange, Signalrot.", "neu"),
        ("P25", "tokio", "Tokio", "Nacht, Cyan, Neonpink.", "neu"),
        ("P26", "cga0", "CGA 0", "Die andere CGA-Palette: Gruen, Rot, Gelb.", "neu"),
    ]),
    ("S", "Spark", "Wie der Stern auf dem Raster lebt. Harte Treppenkanten, kein Antialiasing.", [
        ("S2", "grad", "Verlauf", "Geditherter Glutverlauf zur Mitte.", "ja"),
        ("S7", "nest", "XOR-Nest", "Das Nest aus dem Teaser, pixelgenau.", "ja"),
        ("S33", "matrjoschka", "Matrjoschka", "Nachfolger von S5: 4 Sterne ineinander, viel Luft, jede Puppe laeuft in Korn aus.", "neu"),
        ("S5", "contour", "Hoehenlinien", "Linien zu duenn (2026-09-25). Bleibt fuer M5 Palette Cycling.", "geparkt"),
        ("S12", "lines", "Linien-Stern", "Raus aus dem Mix, lebt nur im Laser-Look L5.", "geparkt"),
    ]),
    ("K", "Komposition", "Wo der Stern steht und was er mit der Schrift macht. Schrift sitzt immer gleich.", [
        ("K1", "riese", "Riese", "Stern riesig, tief, vom rechten Rand angeschnitten.", "ja"),
        ("K2", "aufgang", "Aufgang", "Stern geht vom unteren Rand auf, jetzt hoeher.", "neu"),
        ("K3", "xor", "XOR-Titel", "Stern hinter dem Titel, groesser, die Schrift kippt in den Grund.", "neu"),
        ("K4", "koloss", "Koloss", "Mitte auf dem rechten Rand, der Stern fuellt die ganze untere Haelfte.", "neu"),
        ("K5", "ecke", "Ecke", "Riesig aus der Ecke unten rechts.", "neu"),
        ("K6", "kern", "Kern", "Sitzt im Leerraum, links und rechts angeschnitten.", "neu"),
        ("K7", "sturz", "Sturz", "Faellt von oben rechts durch den Titel.", "neu"),
        ("K8", "wand", "Wand", "Waechst aus der linken Kante hinter QR und Schrift.", "neu"),
    ]),
    ("R", "Pixelgroesse", "Displaypixel pro logischem Pixel (bei 1080p; Plakate skalieren mit).", [
        ("R3", 4, "grob (480x270)", "Standard: das 8-Bit muss man sehen.", "ja"),
        ("R1", 2, "fein (960x540)", "Filigran.", "geparkt"),
    ]),
]
AX = {key: items for key, _, _, items in AXES}


def ja(key, also=()):
    return [(code, val) for code, val, *_, s in AX[key] if s == "ja" or s in also]


def st_of(codes):
    """'D3 P5 S7 K1' -> Stil-Dict."""
    st = dict(BASE)
    for code in codes.split():
        key = code[0]
        st[key] = next(val for c, val, *_ in AX[key] if c == code)
    return st


# Looks = kuratierte Kombis aus freigegebenen Bausteinen, als Frame + Figma-Ebenen, in 16x9, 9x16 und A3
LOOKS = [
    ("glut", "Lavendel-Glut", "Die Basis, Stern hinter dem Titel.", "P1 S2 K3"),
    ("acidnest", "Acid Nest", "Lila + Giftgruen, Nest.", "P5 S7 K1"),
    ("paper", "Papier", "Heller Grund fuer Druck.", "P8 S2 K2"),
    ("cgakreuz", "CGA-Kreuz", "Bayer-Kreuze in CGA, Nest.", "P6 S7 K1"),
    ("laser", "Laser", "Schwarz/Weiss mit Laserrot, Linien-Stern.", "P9 S12 K1"),
    ("acidring", "Acid-Matrjoschka", "Puppen in Giftgruen, aufgehend.", "P5 S33 K2"),
    ("papernest", "Papier-Nest", "Nest auf hellem Grund.", "P8 S7 K2"),
]


FPS = 30
MOTIONS = [  # (code, datei, titel, text, dauer s, stil, f(t, frame) -> Overrides); verworfen: M1-M4, M6-M10. Neu: styles/lab/motion
    ("M5", "palette_cycle", "Palette Cycling", "Hoehenlinien fliessen nach innen, der Stern steht.",
     2.0, st_of("S5"), lambda t, f: dict(phase=t)),
]


def motion_frame(args):
    mi, f = args
    *_, st, fn = MOTIONS[mi]
    return render({**st, **fn(f / FPS, f)})[0]


def motions(pool, only=None):
    d = os.path.join(OUT, "motion")
    os.makedirs(d, exist_ok=True)
    for mi, (code, key, *_, dur, st, fn) in enumerate(MOTIONS):
        if only and code != only:
            continue
        path = os.path.join(d, f"{code}_{key}.mp4")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080",
                               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                               "-pix_fmt", "yuv420p", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
        for fr in pool.imap(motion_frame, [(mi, f) for f in range(round(dur * FPS))], chunksize=2):
            ff.stdin.write(fr.tobytes())
        ff.stdin.close()
        ff.wait()
        print(code, end=" ", flush=True)
    print()


def catalog():
    """[(code, style, titel, text, achse, status)] fuer das Board: BASE mit genau einer geaenderten Achse."""
    return [(code, {**BASE, key: val}, t, tx, key, s) for key, _, _, items in AXES for code, val, t, tx, s in items]


def save(a, path, dpi=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.fromarray(a)
    if a.ndim == 3 and a.shape[2] == 3 and len(np.unique(a.reshape(-1, 3), axis=0)) <= 256:
        im = im.quantize(256, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)   # verlustfrei, ~10x kleiner
    im.save(path, optimize=True, **({"dpi": (dpi, dpi)} if dpi else {}))


def job_board(item):
    save(render(item[1], "a3")[0], os.path.join(OUT, "board", f"{item[0]}.png"))
    return item[0]


def job_look(args):
    i, fmt = args
    key, _, _, codes = LOOKS[i]
    frame, layers = render(st_of(codes), fmt)
    d = os.path.join(OUT, "looks", f"L{i + 1}_{key}", fmt)
    save(frame, os.path.join(d, "frame.png"), 300 if fmt == "a3" else None)
    for k, v in layers.items():
        save(v, os.path.join(d, f"layer_{k}.png"))
    return f"L{i + 1} {fmt}"


def poster_set(n, seed, also=("neu",)):
    """n Unikat-Plakate aus P x S x K (ja + neu, nur lila Paletten), keine Kombi doppelt, dazu eigene Drehung und Korn."""
    combos = [(p, s, k) for p, s, k in product(ja("P", also), ja("S", also), ja("K", also))
              if s[1] in KOMP[k[1]].get("only", (s[1],)) and lila(p[1])]      # Maker Night = die lila Welten, bunt = Kick-off
    rng = np.random.default_rng(seed)
    rest, combos, cnt = [combos[j] for j in rng.permutation(len(combos))], [], Counter()
    while rest:                                   # gierig reihum: immer die Kombi mit den bisher seltensten Bausteinen
        c = min(rest, key=lambda c: sum(cnt[x] for x in c))     # ponytail: O(n^2), n ~ 150
        rest.remove(c)
        combos.append(c)
        cnt.update(c)
    out = []
    for i, ((pc, p), (sc, s), (kc, k)) in enumerate(combos[:n]):
        st = dict(BASE, P=p, S=s, K=k, rot=float(rng.uniform(0, 60)), seed=int(rng.integers(1000)))
        out.append((f"{seed:02d}-{i + 1:02d}__{pc}-{sc}-{kc}", st))
    return out


def job_poster(item):
    name, st = item
    save(render(st, "a3")[0], os.path.join(OUT, "posters", f"{name}.png"), 300)
    return name


def overlays():
    """Formatfreie Alpha-Overlays fuer Figma: Korn in den freigegebenen Rastern."""
    d = os.path.join(OUT, "overlays")
    W, H = 1920, 1080
    for px in (2, 4):
        for name, t in (("bluenoise", BN), ("bayer2", bayer(2)), ("bayer4", bayer(4))):
            for lvl in (0.25, 0.5):
                on = up(tile(t, (H // px, W // px)) < lvl, px)
                save(np.dstack([np.full((H, W, 3), 255, np.uint8), (on * 255).astype(np.uint8)]),
                     f"{d}/{name}_{int(lvl * 100)}pct_R{px}.png")
    return len(os.listdir(d))


# ---------------------------------------------------------------- Galerie + Glossar

GLOSSARY = [
    ("Raster & Pixel", [
        ("Logisches Pixel / virtuelle Aufloesung", "Das Pixel des 'Spiels' (z. B. 480x270), das mit Faktor R hochskaliert wird."),
        ("Nearest Neighbour", "Hochskalieren ohne Weichzeichnen: jedes Pixel wird ein harter Block."),
        ("Mixels", "Gemischte Pixelgroessen in einem Bild (feine Vektorkante auf grobem Korn). Stilbruch."),
        ("Aliasing / Jaggies", "Treppenkanten schraeger Linien. Bei Drehung 'krabbeln' sie."),
        ("Pixel-perfect", "Alles auf demselben Raster, nur ganzzahlige Skalierung und Verschiebung."),
    ]),
    ("Dither", [
        ("Dithering", "Zwischentoene aus Mustern weniger Farben erzeugen."),
        ("Ordered Dither (Bayer)", "Feste Schwellenmatrix, erzeugt Schachbrett (D2) und Kreuze (D3)."),
        ("Blue Noise", "Zufaelliges, aber gleichmaessiges Korn ohne Muster (D1)."),
        ("Stehendes vs. kochendes Korn", "Korn fix (gedruckt) oder jede n Frames neu (boil): 15 fps boil = analog."),
    ]),
    ("Farbe", [
        ("Palette / Rampe / Colorway", "Die feste Liste erlaubter Farben, dunkel nach hell."),
        ("Gradient Map", "Helligkeitswert wird auf die Palette abgebildet."),
        ("Palette Cycling", "Farben rotieren durch die Palette, Bild steht (M5)."),
        ("Hue-crossing Ramp", "Rampe, die durch den Farbkreis springt (Kobalt -> Orange): der Dither mischt zwei Farbwelten (P17)."),
        ("CGA", "PC-Palette von 1981 (P6)."),
    ]),
    ("Bewegung", [
        ("Demoszene", "Seit den 80ern: Echtzeit-Grafik-und-Musik-Kunst auf C64/Amiga/PC. Die Quelle von 'Techno + 8-Bit'."),
    ]),
    ("Sound", [
        ("Chiptune", "Musik mit (oder im Stil von) Soundchips alter Konsolen."),
        ("Arpeggio (Chip-Arp)", "Akkord als sehr schnelle Tonfolge: der typische 8-Bit-Akkord."),
        ("Bitcrush", "Aufloesung und Abtastrate kuenstlich senken: Lo-Fi-Knirschen."),
    ]),
]

CSS = """:root{--bg:#0A0711;--fg:#F1ECFF;--mut:#9B8FC0;--line:#2A1F4A;--acc:#AE93EE;--lime:#D7FF3A}
body{margin:0;padding:24px 16px 80px;background:var(--bg);color:var(--fg);font:14px/1.5 ui-monospace,Menlo,monospace}
main{max-width:1500px;margin:auto}h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:40px 0 4px;color:var(--acc)}
h3{font-size:13px;margin:18px 0 4px;color:var(--acc)}p.d{color:var(--mut);margin:0 0 14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px}.grid.tall{grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}
figure{margin:0}video{width:100%;display:block;border:1px solid var(--line)}img{width:100%;display:block;image-rendering:pixelated;border:1px solid var(--line)}
figcaption{margin-top:6px}figcaption span{color:var(--mut);font-size:12px}a{color:var(--acc)}
nav a{margin-right:14px}code{font-size:11px;color:var(--fg)}.st{font-size:10px;padding:0 4px;border:1px solid var(--line);color:var(--mut)}
.st.ja{color:var(--lime);border-color:var(--lime)}.st.neu{color:#FF4FD8;border-color:#FF4FD8}table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid var(--line);padding:4px 10px;text-align:left;vertical-align:top}
dl{display:grid;grid-template-columns:minmax(160px,300px) 1fr;gap:4px 16px;margin:0}dt{color:var(--fg)}dd{margin:0;color:var(--mut)}
details{border:1px solid var(--line);padding:10px 14px;margin-top:16px}summary{cursor:pointer;color:var(--acc)}
@media(max-width:640px){dl{grid-template-columns:1fr}dd{margin-bottom:8px}}"""


def gallery():
    esc = html.escape
    badge = lambda s: f'<span class="st {s}">{s}</span>'      # noqa: E731
    system = "".join(f"<tr><th>{k} {esc(n)}</th><td>" + "<br>".join(f"<b>{c}</b> {esc(t)} {badge(s)}" for c, _, t, _, s in items)
                     + "</td></tr>" for k, n, _, items in AXES)
    parts = []
    for key, name, desc, _ in AXES:
        figs = "".join(f'<figure><a href="board/{c}.png"><img loading="lazy" src="board/{c}.png"></a>'
                       f'<figcaption><b>{c}</b> {esc(t)} {badge(s)}<br><span>{esc(tx)}</span></figcaption></figure>'
                       for c, _, t, tx, k, s in catalog() if k == key)
        parts.append(f'<h2 id="{key}">{key} · {esc(name)}</h2><p class="d">{esc(desc)}</p><div class="grid tall">{figs}</div>')
    looks = "".join(
        f'<figure><a href="looks/L{i + 1}_{k}/16x9/frame.png"><img loading="lazy" src="looks/L{i + 1}_{k}/16x9/frame.png"></a>'
        f'<figcaption><b>L{i + 1}</b> {esc(n)} · <code>{codes}</code><br><span>{esc(tx)}<br>'
        f'<a href="looks/L{i + 1}_{k}/9x16/frame.png">9x16</a>'
        + f' · <a href="looks/L{i + 1}_{k}/a3/frame.png">A3</a>'
        + f' · Ebenen: <code>looks/L{i + 1}_{k}/</code></span></figcaption></figure>' for i, (k, n, tx, codes) in enumerate(LOOKS))
    pdir = os.path.join(OUT, "posters")
    pl = sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []
    posters = "".join(f'<figure><a href="posters/{p}"><img loading="lazy" src="posters/{p}"></a>'
                      f'<figcaption><code>{esc(p[:-4].replace("__", " · ").replace("-", " "))}</code></figcaption></figure>' for p in pl)
    mot = "".join(f'<figure><video src="motion/{c}_{k}.mp4" autoplay loop muted playsinline></video>'
                  f'<figcaption><b>{c}</b> {esc(t)}<br><span>{esc(tx)}</span></figcaption></figure>'
                  for c, k, t, tx, *_ in MOTIONS)
    gl = "".join(f"<h3>{esc(g)}</h3><dl>" + "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in items) + "</dl>"
                 for g, items in GLOSSARY)
    npool = len(ja("P", ("neu",))) * len(ja("S", ("neu",))) * len(ja("K", ("neu",)))
    page = f"""<!doctype html><html lang="de"><meta charset="utf-8"><title>SPARK Style Board</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style><main><h1>SPARK Maker Night · System</h1>
<p class="d">Nur noch freigegebene Bausteine. Codes bleiben stabil, verworfene Codes werden nie neu vergeben.
<span class="st ja">ja</span> = im Plakat-Mix, <span class="st neu">neu</span> = zur Auswahl, <span class="st geparkt">geparkt</span> = im Blick.
Ziele: Plakate (jedes ein Unikat), Motion-Teaser fuer Telegram/Slack, Stills fuer Banner.</p>
<nav><a href="#sys">System</a><a href="#posters">Plakate</a>{" ".join(f'<a href="#{k}">{k} {esc(n)}</a>' for k, n, _, _ in AXES)}
<a href="#L">L Looks</a><a href="#M">M Bewegung</a><a href="#G">Glossar</a>
<a href="../kickoff/index.html">Kick-off-Kampagne</a><a href="lab/spark/index.html">Labor: neue Sterne S13+</a><a href="lab/motion/index.html">Labor: neue Bewegung M11+</a></nav>
<h2 id="sys">System</h2><table>{system}</table>
<p class="d">Plakat-Mix = jede Kombi P x S x K aus <span class="st ja">ja</span> + <span class="st neu">neu</span> ({npool} Kombis), D3 fest, dazu eigene Sterndrehung und Korn:
<code>python src/styles.py posters 24 7</code> (24 Plakate, Seed 7).</p>
<h2 id="posters">Plakate · A3 300 dpi</h2><p class="d">Dateiname = Seed-Nummer · Codes. Neuer Seed = neue Serie, keine Kombi doppelt pro Serie.</p>
<div class="grid tall">{posters}</div>
{"".join(parts)}
<h2 id="L">L · Looks</h2><p class="d">Kuratierte Kombis, neu aus den freigegebenen Bausteinen. Pro Look und Format frame.png + layer_bg / spark /
title / date / copy als PNG mit Alpha (in Figma uebereinander = exakt der Frame).</p>
<div class="grid">{looks}</div>
<h2 id="M">M · Bewegung</h2><p class="d">Bewegungsideen, jetzt in freigegebenen Stilen. 2-3 s, nahtlos loopend wo moeglich.</p><div class="grid">{mot}</div>
<p class="d">Overlays fuer Figma/Resolve (Blue-Noise-/Bayer-Korn) in <code>overlays/</code>.</p>
<h2 id="G">Glossar</h2><details><summary>aufklappen</summary>{gl}</details>
<p class="d" style="margin-top:30px">Erzeugt von <code>src/styles.py</code>.</p></main></html>"""
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)


def main():
    args = sys.argv[1:]
    words = [a for a in args if not a.isdigit()]
    nums = [int(a) for a in args if a.isdigit()]
    what = set(words) or {"board", "looks", "posters", "overlays", "motion"}
    if "one" in args:
        code = args[args.index("one") + 1]
        fmt = next((a for a in args if a in SIZES), "16x9")
        if code.startswith("M"):
            with Pool() as pool:
                motions(pool, code)
        elif code.startswith("L"):
            print(job_look((int(code[1:]) - 1, fmt)))
        else:
            print(job_board(next(x for x in catalog() if x[0] == code)))
        return
    with Pool() as pool:
        if "board" in what:
            for c in pool.imap_unordered(job_board, catalog()):
                print(c, end=" ", flush=True)
            print()
        if "looks" in what:
            for c in pool.imap_unordered(job_look, [(i, f) for i in range(len(LOOKS)) for f in SIZES]):
                print(c, end=" | ", flush=True)
            print()
        if "posters" in what:
            for c in pool.imap_unordered(job_poster, poster_set(*(nums + [12, 1])[:2])):
                print(c, end=" ", flush=True)
            print()
        if "motion" in what:
            motions(pool)
    if "overlays" in what:
        print("overlays", overlays())
    gallery()
    print(os.path.join(OUT, "index.html"))


if __name__ == "__main__":
    assert len({code for _, _, _, items in AXES for code, *_ in items}) == sum(len(i) for *_, i in AXES), "Code doppelt"
    main()
