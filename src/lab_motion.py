#!/usr/bin/env python3
"""Motion-Labor: neue Bewegungsideen fuer das Maker-Night-System (Codes ab M11) -> styles/lab/motion/.

Runde 2 nach Sichtung der Kontaktbogen (Runde 1 liegt in styles/lab/motion/_v1/): nur noch fuenf Stuecke, jedes mit
Bogen (Anlauf -> Treffer -> Ausklang) auf dem 120-BPM-Raster (Schlag = 0,5 s), gesetzt im aktuellen Plakatsatz
(Meta-Zeile, Clash-Titel auf Mass, Datum, XOR-Regel: Schrift kippt ueber leuchtenden Sternpixeln in den Grund).
Verworfen: interferenz (Flimmer-Demo), kaleido (Plasma-Filter), bittiefe (zu leise), rotozoom (Sternfeld), kristall (Rauschen).

Baut eigene Frames aus den Bausteinen von styles.py (nur Import). EIN logisches Raster (480x270, R = 4 px),
D3 Bayer 4x4, nearest-neighbour hoch. Jede Idee ist f(t, T) -> RGB auf dem Raster und periodisch in T (nahtlos).

  uv run -q --with numpy --with pillow --with scipy --with qrcode --with scikit-image python src/lab_motion.py sheet [key ...]
  uv run ... python src/lab_motion.py mp4 [key ...]      # MP4 (crf 16) + Nahtpruefung
  uv run ... python src/lab_motion.py html                # Galerie index.html
"""
import os
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image
from scipy.interpolate import CubicHermiteSpline
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates

from makernight_sparks import PROF
from styles import CODENAME, COPY, F_HI, F_LO, PALS, Ctx, bayer, line_mask, tile, up

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "styles", "lab", "motion")
W, H, PX, FPS = 1920, 1080, 4, 30
GW, GH = W // PX, H // PX
YY, XX = np.mgrid[0:GH, 0:GW].astype(np.float32)
CX, CY = (XX + 0.5) * PX, (YY + 0.5) * PX          # Zellmitten in Displaypixeln
B4 = tile(bayer(4), (GH, GW)).astype(np.float32)
B16 = tile(up(bayer(4), 4), (GH, GW)).astype(np.float32)          # Bayer als Motiv: eine Matrixzelle = 4x4 Rasterpixel
BEAT = 0.5                                          # 120 BPM

# Sternprofil 6-fach symmetrisiert (Abweichung vorher < 1 %): 60-Grad-Drehungen schliessen Loops pixelgenau
_P6 = np.mean([np.roll(PROF, 600 * k) for k in range(6)], 0)
_P6 = np.append(_P6, _P6[0])
PMIN = float(_P6.min())

# Plakatsatz 16x9 aus styles.layout (K1 Riese): Rand, Titel, Datum, Meta-Zeile, Stern
_L = Ctx(dict(T="clashbit", D="bayer4", P="lav", S="grad", K="riese", F=(), R=4), "16x9").L
MARG, CAP, TB, CAPD, DB, META, SC = _L["m"], _L["cap"], _L["tb"][0], _L["capd"], _L["db"], _L["meta"], _L["sc"]
STAR = _L["star"]
TITLE = " ".join(COPY["title"])
INK = 0.8                                            # Kleintext: exakte Stufe 4/5, flaechig


def star_r(dx, dy, rot):
    return np.interp((np.degrees(np.arctan2(dy, dx)) - rot) % 360, np.arange(3601) / 10, _P6)


def sd(x, y, cx, cy, R, rot):
    """(d, rr): d < 1 im Stern (Spitze = R), rr = Abstand zur Mitte."""
    dx, dy = x - cx, y - cy
    rr = np.hypot(dx, dy)
    return rr / (star_r(dx, dy, rot) * R + 1e-9), rr


# Fallback, falls styles.PALS sich aendert (Lab-Stuecke haengen nur an diesen Rampen)
_PALS_LAB = {"lav": ["#0A0711", "#221643", "#43287C", "#7049C4", "#AE93EE", "#F6F2FF"],
             "paper": ["#D6C8F4", "#B49DEB", "#8B68D8", "#6A3FB5", "#432379", "#150E26"],
             "uv": ["#0B0418", "#2A0B52", "#5A12A8", "#B01CFF", "#FF4FD8", "#FFE6FA"],
             "acid": ["#0A0711", "#221643", "#43287C", "#7049C4", "#AE93EE", "#D7FF3A"]}


def pal(p):
    return np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in PALS.get(p, _PALS_LAB[p])], np.float32)


def dith(v, N, thr=B4):
    x = np.clip(v, 0, 1) * N + 1e-4
    lo = np.floor(x)
    return np.clip(lo + (x - lo > thr), 0, N).astype(np.int16)


def paint(v, p):
    P = pal(p)
    return P[dith(v, len(P) - 1)]


def sm(a, b, t):
    x = np.clip((t - a) / (b - a), 0, 1)
    return x * x * (3 - 2 * x)


def glide(vel, T, n=4000):
    """Weg 0..1 ueber T als Integral eines Geschwindigkeitsprofils (nie Positionen lerpen)."""
    tt = np.linspace(0, T, n + 1)
    v = vel(tt)
    c = np.concatenate([[0], np.cumsum((v[1:] + v[:-1]) / 2)])
    c /= c[-1]
    return lambda t: float(np.interp(t, tt, c))


def bump(s, c, w, P=None):
    """Gauss-Buckel bei c; mit Periode P zyklisch (Abstand zum naechsten Vielfachen)."""
    d = s - c if P is None else (s - c + P / 2) % P - P / 2
    return np.exp(-(d / w) ** 2)


# ---------------------------------------------------------------- Satz (Clash auf dem Raster, Tinte = Wertfeld)

@lru_cache(None)
def mask(s, T, cap, base, x, right=False, center=False, k=1):
    """Bool-Maske einer Zeile. k > 1: k-fach feiner je Displaypixel (fuer Zoom-Abtastung). Pixelfont bleibt logisch."""
    if k > 1 and T == "clash":
        return line_mask(s, T, cap, base, x, 1 / k, (H * k, W * k), right)
    m = line_mask(s, T, cap, base, x, PX, (GH, GW), right)
    if center:
        cols = np.nonzero(m.any(0))[0]
        m = np.roll(m, (GW - 1 - cols.max() - cols.min()) // 2, 1)
    return m if k == 1 else up(m, PX * k)


def fill(y, base, cap, lo=F_LO, hi=F_HI):
    """Geditherter Verlauf in den Buchstaben: unten Lavendel, oben fast Weissglut (wie das Plakat)."""
    rel = np.clip((y - (base - cap)) / cap, 0, 1)
    return lo + (hi - lo) * (1 - rel)


def meta(p, k=1):
    return (mask(COPY["org"], "departure", SC, META, MARG, k=k)
            | mask(CODENAME[p], "departure", SC, META, W - MARG, True, k=k))


@lru_cache(None)
def block(p, k=1):
    """Plakatsatz: [(Maske, Grundlinie, Versalhoehe)], Grundlinie None = Kleintext."""
    return ((mask(TITLE, "clash", CAP, TB, MARG, k=k), TB, CAP), (mask(COPY["date"], "clash", CAPD, DB, MARG, k=k), DB, CAPD),
            (meta(p, k), None, None))


def at(m, x, y, k):
    """Maske (k-fach fein) an beliebigen Displaykoordinaten abtasten."""
    ix, iy = np.floor(x * k).astype(int), np.floor(y * k).astype(int)
    ok = (ix >= 0) & (ix < W * k) & (iy >= 0) & (iy < H * k)
    out = np.zeros(x.shape, bool)
    out[ok] = m[iy[ok], ix[ok]]
    return out


def type_v(x, y, p, k=None):
    """(innen, Wert) des Plakatsatzes; k None = x, y sind das Raster selbst."""
    inside, val = np.zeros(x.shape, bool), np.zeros(x.shape, np.float32)
    for m, base, cap in block(p, k or 1):
        mm = m if k is None else at(m, x, y, k)
        val = np.where(mm, fill(y, base, cap) if base else INK, val)
        inside |= mm
    return inside, val


def poster_v(x, y, p="lav", rot=14, star="lit", scale=1.0, k=None):
    """Wertfeld des Plakats (K1) an Displaykoordinaten x, y; star: "lit" | "halo" (nur Schein) | "window" (Fenster)."""
    cx, cy, R, _ = STAR
    grad = (0.35 * np.clip(x / W, 0, 1) + np.clip(y / H, 0, 1)) / 1.35
    v = 0.025 + 0.085 * grad ** 1.3
    d, rr = sd(x, y, cx, cy, R * scale, rot)
    lit = d < 1 if star == "lit" else np.zeros(d.shape, bool)
    if star in ("lit", "halo"):
        v = v + np.where(d > 1, 0.15 * np.exp(-(d - 1) / 0.3) + 0.16 * np.exp(-rr / R / 1.6), 0)
        v = np.where(lit, 0.64 + 0.36 * np.clip(1 - d, 0, 1) ** 0.7, v)
    tm, tv = type_v(x, y, p, k)
    return np.where(tm, np.where(lit, 0.0, tv), v), d, tm      # XOR-Regel


# ---------------------------------------------------------------- M11 Finsternis

EC = (960, 400, 250)                                             # Sonne: Mitte + Spitzenradius (Displaypixel)
EC_CAP, EC_TB, EC_CAPD, EC_DB = 92, 850, 44, 934
EC_HIT = 2.0                                                     # Schlag 4: Totalitaet (Schatten deckt, Spitzen fluchten)


def pal_mix(p, q, m):
    """Palette p -> q, global ueberblendet (jedes Frame bleibt bei 6 Farben: das Licht selbst wechselt)."""
    return pal(p) * (1 - m) + pal(q) * m


@lru_cache(None)
def _ecl():
    cx, cy, R = EC
    d, rr = sd(CX, CY, cx, cy, R, 14)
    out = np.clip(d - 1, 0, None)
    return d, out, mask(TITLE, "clash", EC_CAP, EC_TB, 0, center=True), mask(COPY["date"], "clash", EC_CAPD, EC_DB, 0, center=True)


@lru_cache(None)
def _ec_scale(T):
    """Groesse des dunklen Sterns relativ zur Sonne: waechst aus der Mitte (sanfter Antritt), deckt auf Schlag 4
    genau (1,0), schwillt nach, zieht sich schneller zurueck und ist zum Loop-Punkt wieder ein Punkt."""
    return CubicHermiteSpline([0, EC_HIT, EC_HIT + 0.45, T], [0, 1.0, 1.13, 0], [0, 0.32, 0, 0])


def ec_state(t, T):
    """(Skala, Drehversatz in Grad): dreht sich beim Wachsen in die Flucht der Spitzen (0 Grad auf dem Treffer)."""
    s = max(0.0, float(_ec_scale(T)(t)))
    return s, 30 * (1 - 2 * t / T)                               # +30 -> -30 (= +30, Stern ist 60-Grad-symmetrisch)


def ec_occ(t, T, step=1):
    """Deckungsgrad 0..1 (Anteil der Sonne hinter dem dunklen Stern)."""
    d = _ecl()[0][::step, ::step]
    s, off = ec_state(t, T)
    if s < 1e-3:
        return 0.0
    cx, cy, R = EC
    do, _ = sd(CX[::step, ::step], CY[::step, ::step], cx, cy, R * s, 14 + off)
    return float(((d < 1) & (do < 1)).sum()) / float((d < 1).sum())


def finsternis(t, T):
    """Der dunkle Stern waechst aus der Mitte des Funkens und dreht dabei in die Flucht. Je mehr er deckt, desto
    heller glueht der Rest, die Korona waechst aus den Spitzen, das Licht kippt nach Schwarzlicht. Dann zurueck."""
    cx, cy, R = EC
    d, out, tm, dm = _ecl()
    s, off = ec_state(t, T)
    sun = d < 1
    if s > 1e-3:
        do, rro = sd(CX, CY, cx, cy, R * s, 14 + off)
        moon = do < 1
    else:
        do, rro, moon = np.full(d.shape, 9.0, np.float32), np.hypot(CX - cx, CY - cy), np.zeros(d.shape, bool)
    occ = float((sun & moon).sum()) / float(sun.sum())
    k = occ ** 1.6                                               # Totalitaet zaehlt erst spaet
    free = sun & ~moon
    glow = gaussian_filter(free.astype(np.float32), 9)
    reach = 0.18 + 0.2 * k                                       # Korona greift mit der Deckung weiter aus
    corona = np.where(d > 1, 0.5 * np.exp(-out / reach) + 0.3 * np.exp(-out / (4 * reach)), 0)
    v = (0.03 + 0.07 * (CY / H) ** 1.3) * (1 - 0.6 * k) + (0.3 + 0.3 * k) * glow
    v = v + (0.12 + 0.85 * k) * corona
    v = np.where(free, 0.64 + 0.36 * np.clip(1 - d, 0, 1) ** 0.7 + 0.45 * k, v)      # der Rest glueht auf
    edge = (do >= 1) & (rro * (1 - 1 / np.maximum(do, 1e-6)) < 1.3 * PX)          # Lichtsaum um den Schatten
    v = np.where(moon, 0.0, np.where(edge & (v > 0.12), np.maximum(v, 0.72 + 0.3 * k), v))
    for m, base, cap in ((tm, EC_TB, EC_CAP), (dm, EC_DB, EC_CAPD)):
        v = np.where(m, fill(CY, base, cap), v)
    v = np.where(meta("lav"), INK, v)
    P = pal_mix("lav", "uv", 0.85 * sm(0.25, 1.0, occ))
    return P[dith(v, len(P) - 1)]


# ---------------------------------------------------------------- M12 Sternlicht (3D: Relief + wanderndes Licht)

SL_CAP, SL_TB, SL_CAPD, SL_DB = 132, 606, 48, 700
SL_STAR = (960, 540, 470)                                        # Relief-Stern hinter dem Titel (Displaypixel)
SL_HS, SL_HL, SL_HD = 26.0, 6.0, 4.5                             # Hoehen in Rasterpixeln: Stern-Spitze, Titel, Datum
SL_HMAX = SL_HS + SL_HL
SL_MID = 4.0                                                     # Schlag 8: Licht steht in der Mitte


@lru_cache(None)
def _sl3d():
    """Hoehenfeld auf dem 480x270-Raster: Stern als Pyramide mit Graten, Titel und Datum darauf gepraegt (1,5-px-Fase).
    Liefert (h, Normalen, Albedo)."""
    tm = mask(TITLE, "clash", SL_CAP, SL_TB, 0, center=True)
    dm = mask(COPY["date"], "clash", SL_CAPD, SL_DB, 0, center=True)
    cx, cy, R = SL_STAR
    d, _ = sd(CX, CY, cx, cy, R, 14)
    hs = SL_HS * np.clip(1 - d, 0, 1) ** 0.85                   # Grate laufen in die Spitzen
    bev = lambda m: np.clip(distance_transform_edt(m) / 1.5, 0, 1) ** 0.8          # noqa: E731
    h = (hs + SL_HL * bev(tm) + SL_HD * bev(dm)).astype(np.float32)
    gy, gx = np.gradient(gaussian_filter(h, 0.6))
    n = np.stack([-gx, -gy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=0)
    alb = np.where(tm, 1.0, np.where(dm, 0.8, np.where(d < 1, 0.52, 0.1))).astype(np.float32)
    alb = np.where(meta("lav"), 0.7, alb)                        # Kopfzeile flach aufgedruckt
    gloss = np.clip((1 - n[2]) * 10, 0, 1) * (h > 0.5)           # Glanz nur auf Schraegen (Fasen, Grate), nie auf der Flaeche
    return h, n, alb, gloss


def _bez(p, u):
    p = np.asarray(p, np.float64)
    return ((1 - u) ** 3) * p[0] + 3 * ((1 - u) ** 2) * u * p[1] + 3 * (1 - u) * u * u * p[2] + u ** 3 * p[3]


# Lichtweg in Rasterkoordinaten (x, y, z): zwei kubische Bezier, in der Mitte C1-stetig (gleiche Tangente)
_SL_A = [(-230, 235, 40), (-40, 290, 46), (130, 240, 80), (240, 200, 92)]
_SL_B = [_SL_A[3], tuple(2 * np.array(_SL_A[3]) - np.array(_SL_A[2])), (560, 40, 50), (710, 70, 40)]


@lru_cache(None)
def _sl_u(T):
    """Weg 0..1: kommt aus dem Dunkel, bremst weich in die Mitte (Schlag 8), zieht mit Ease-in/-out wieder hinaus."""
    return glide(lambda s: 0.22 + bump(s, T * 0.24, T * 0.13) + bump(s, T * 0.76, T * 0.13), T)


def sl_light(t, T):
    """(Position x, y, z im Raster, Intensitaet): Licht blendet am Rand des Loops ganz aus (Start = komplett dunkel)."""
    u = _sl_u(T)(t)
    p = _bez(_SL_A, 2 * u) if u < 0.5 else _bez(_SL_B, 2 * u - 1)
    inten = sm(0.0, T * 0.22, t) * (1 - sm(T * 0.8, T, t))
    return p, inten


def sternlicht(t, T):
    """Relief bei Streiflicht: erst ist alles Nacht, dann streift ein Licht von links ueber MAKER, die Schatten der
    Buchstaben laufen ueber die Grate des Sterns, das Licht steigt in die Mitte und zieht rechts wieder hinaus."""
    h, n, alb, gloss = _sl3d()
    (lx, ly, lz), inten = sl_light(t, T)
    x, y = XX + 0.5, YY + 0.5
    dx, dy, dz = lx - x, ly - y, lz - h
    dist = np.sqrt(dx * dx + dy * dy + dz * dz)
    lam = np.clip((n[0] * dx + n[1] * dy + n[2] * dz) / dist, 0, 1)
    hx = dx / dist
    hy = dy / dist
    hz_ = dz / dist + 1                                          # Blinn: Halbvektor zu Blick (0, 0, 1)
    spec = np.clip((n[0] * hx + n[1] * hy + n[2] * hz_) / np.sqrt(hx * hx + hy * hy + hz_ * hz_), 0, 1) ** 36
    # weicher Schatten: Strahl zum Licht durchs Hoehenfeld; Rand = kleinster Winkelabstand zwischen Licht und Horizont
    dh = np.hypot(dx, dy) + 1e-6
    slope = dz / dh
    reach = np.minimum(dh, np.clip((SL_HMAX - h) / np.maximum(slope, 1e-3), 0, 700))
    marg = np.full_like(h, 9.0)
    ux, uy = dx / dh, dy / dh
    for i in range(1, 49):
        s = 0.6 + reach * (i / 48) ** 1.4
        hs = map_coordinates(h, (y - 0.5 + uy * s, x - 0.5 + ux * s), order=1, mode="nearest")
        marg = np.minimum(marg, slope - (hs - h) / s)
    shadow = sm(-0.05, 0.05, marg)                               # Flaechenlicht ~ 3 Grad: weicher Halbschatten
    att = 1 / (1 + (dist / 420) ** 2)
    light = inten * att * 1.9
    x_ = alb * light * (lam * shadow + 0.08) + 0.6 * light * gloss * spec * shadow   # 0,08 = Streulicht im Schatten
    v = 0.018 + 1 - np.exp(-1.25 * x_)                            # weiche Schulter statt Ausbrennen
    return paint(v, "lav")


# ---------------------------------------------------------------- M13 Portal

PT_PALS = ("lav", "paper", "uv")                                # kein Gruen: Nacht -> Papier -> Schwarzlicht
PT_F = 0.19                                                       # Massstab der naechsten Dimension im Fenster
PT_K = 3                                                          # Masken 3-fach fein (Titel bleibt beim Zoom scharf)


@lru_cache(None)
def _pt_lam():
    """Weg in Dimensionen (1 pro Sekunde): halten, Zurueckziehen auf dem Offbeat, Sturz, Landung auf dem Schlag."""
    P, n = 1.0, 6000
    s = np.linspace(0, P, n, endpoint=False)
    v = 0.006 + 1.0 * bump(s, 0.86, 0.075, P) - 0.07 * bump(s, 0.6, 0.06, P) - 0.06 * bump(s, 0.04, 0.035, P)
    c = np.cumsum(v) / v.sum()
    return s, c - np.interp(0.25, s, c)                            # Mitte der Haltephase = genau gerahmt


def portal_lam(t):
    s, c = _pt_lam()
    return int(t // 1.0) + float(np.interp(t % 1.0, s, c))


def portal(t, T):
    """Droste-Tauchgang: der Stern ist ein Fenster in dieselbe Nacht in der naechsten Farbwelt (Codename wechselt mit)."""
    lam = portal_lam(t)
    L = int(np.floor(lam))
    frac = lam - L
    cx, cy, R, _ = STAR
    x = cx + (CX - cx) * PT_F ** frac
    y = cy + (CY - cy) * PT_F ** frac
    sc = PT_F ** -frac                                             # Displaypixel pro Ebeneneinheit
    lvl = np.full(x.shape, L, np.int16)
    val = np.zeros(x.shape, np.float32)
    rim = np.zeros(x.shape, bool)
    todo = np.ones(x.shape, bool)
    for k in range(5):
        p = PT_PALS[(L + k) % 3]
        v, d, tm = poster_v(x, y, p, 14 + 60 * frac * (k == 0), "window", k=PT_K)
        rr = np.hypot(x - cx, y - cy)
        edge = (d >= 1) & ((rr - rr / np.maximum(d, 1e-6)) * sc < 1.3 * PX) & ~tm
        here = todo & ((d >= 1) | tm)                               # Satz liegt ueber dem Fenster
        val[here] = v[here]
        rim |= here & edge
        lvl[todo] = L + k
        todo &= (d < 1) & ~tm
        if not todo.any():
            break
        x = np.where(todo, cx + (x - cx) / PT_F, x)
        y = np.where(todo, cy + (y - cy) / PT_F, y)
        sc *= PT_F
    out = np.zeros((GH, GW, 3), np.float32)
    for li in np.unique(lvl):
        P = pal(PT_PALS[li % 3])
        m = lvl == li
        out[m] = P[dith(val, len(P) - 1)][m]
        out[rim & m] = P[-1]                                       # Fensterrand in der Tinte der aeusseren Welt
    return out


# ---------------------------------------------------------------- M14 Kreuz-Welle

KW_HIT = 2.0                                                     # Treffer auf Schlag 4 jeder Haelfte (Drop in der Musik)
KW_WAVE = 1.65                                                   # Welle rollt 1,65 s, dann Ruhe bis zum naechsten Einatmen


def kw_scale(s, half):
    """Atmen: weich einatmen (zieht sich zusammen), auf dem Treffer ein Impuls, gedaempfte Feder aus (Position stetig)."""
    if s < KW_HIT:
        return 1 - 0.07 * sm(0.35, KW_HIT, s) ** 1.4
    e = s - KW_HIT
    w, tau = 2 * np.pi / 1.1, 0.42
    spring = np.exp(-e / tau) * (-0.07 * np.cos(w * e) + 0.13 * np.sin(w * e))
    return 1 + spring * (1 - sm(1.2, half - KW_HIT, e))


@lru_cache(None)
def _kw_u(span):
    return glide(lambda e: (1 - np.exp(-e / 0.12)) * np.exp(-e / 0.75) + 0.03, span)   # Antritt, gleiten, ausrollen


@lru_cache(None)
def _kw_rot(T):
    """Drehung als Integral: nach jedem Treffer nimmt der Stern Fahrt auf und laeuft aus (60 Grad pro Loop)."""
    return glide(lambda s: 0.25 + bump(s, KW_HIT + 0.55, 0.55, T) + bump(s, T / 2 + KW_HIT + 0.55, 0.55, T), T)


def kw_beat(t):
    """Kick-Glut: kleiner Lichtschub im Stern auf jedem Schlag, der in der Musik einen Kick hat."""
    nb = int(t // BEAT)
    e = t - nb * BEAT
    s = (nb * BEAT) % 4.0
    on = not (1.5 <= s < KW_HIT)                                 # im Luftloch vor dem Drop kein Kick
    return 0.05 * np.exp(-e / 0.14) * on


def kreuzwelle(t, T):
    """Der Stern holt Luft und schlaegt: eine Sternwelle aus wachsenden Bayer-Kreuzen rollt Nacht <-> Papier."""
    half = T / 2
    s = t % half
    a, b = ("lav", "paper") if t < half else ("paper", "lav")
    scale = kw_scale(s, half)
    u = _kw_u(KW_WAVE)(min(s - KW_HIT, KW_WAVE)) if s >= KW_HIT else 0.0
    rot = 14 + 60 * _kw_rot(T)(t)
    pulse = kw_beat(t)
    va, d, _ = poster_v(CX, CY, a, rot, scale=scale)
    vb = poster_v(CX, CY, b, rot, scale=scale)[0]
    lit = d < 1
    va = np.where(lit, va + pulse, va)
    vb = np.where(lit, vb + pulse, vb)
    cx, cy = STAR[:2]
    dx, dy = CX - cx, CY - cy
    band = 460
    dw = np.hypot(dx, dy) / (0.2 + 0.8 * star_r(dx, dy, 14 + 40 * u))    # Front in Sternform, dreht beim Wachsen
    rho = -band + u * (2000 / (0.2 + 0.8 * PMIN) + 2 * band)
    w = np.clip((rho - dw) / band, 0, 1)
    flip = w > B16                                               # grosse Kreuze wachsen im Band (4 logische px je Zelle)
    crest = 0.26 * np.exp(-((rho - dw - band * 0.5) / 110) ** 2) * (0 < u < 1)
    return np.where(flip[..., None], paint(vb + crest, b), paint(va + crest, a))


# ---------------------------------------------------------------- M15 Nest-Puls

@lru_cache(None)
def _np_beat():
    return glide(lambda e: np.exp(-e / 0.055) + 0.004, BEAT)       # ein Schlag = ein Ring, harter Antritt


def nestpuls(t, T):
    """Acid-Nest (P5 S7 K1) im Takt: jeder Schlag zieht einen Ring nach vorn, der aeussere Stern steht still."""
    nb = int(t // BEAT)
    e = t - nb * BEAT
    ph = nb + _np_beat()(e)
    drift = 60 * t / T
    cx, cy, R, rot = STAR
    ratio = 0.74
    d0, _ = sd(CX, CY, cx, cy, R, rot)
    star = d0 < 1
    cnt = np.zeros((GH, GW), np.int16)
    for k in range(int(ph) - 12, int(ph) + 30):                   # Ring k hat Groesse R * ratio^(k - ph)
        s = R * ratio ** (k - ph)
        if s * PMIN > R:                                           # deckt den ganzen Stern: nur zaehlen
            cnt += 1
            continue
        if s < 2:
            break
        cnt += sd(CX, CY, cx, cy, s, rot + 30 * (k - ph) + (1 if k % 2 == 0 else -1) * drift)[0] < 1
    lit = star & (cnt % 2 == 1)
    v = poster_v(CX, CY, "acid", rot, star="halo")[0]
    kick = 0.06 * np.exp(-e / 0.12)
    v = np.where(lit, 0.64 + kick + 0.36 * np.clip(1 - d0, 0, 1) ** 0.7, v)
    tm, tv = type_v(CX, CY, "acid")
    v = np.where(tm, np.where(lit, 0.0, tv), v)                    # XOR-Regel
    return paint(v, "acid")


# ---------------------------------------------------------------- Katalog

# (Schluessel, Code, Titel, Beschreibung, Dauer s, f, Einsatz)
IDEAS = [
    ("finsternis", "M11", "Finsternis", "Der dunkle Stern wächst aus der Mitte des Funkens und dreht sich dabei in die Flucht der Spitzen. "
     "Je mehr er deckt, desto heller glüht der Rest, die Korona greift aus und das Licht kippt nach Schwarzlicht. Auf Schlag 4 "
     "Totalität, dann zieht er sich zurück.", 4.0, finsternis, "Intro / Opener, Screen-Loop am Eingang"),
    ("sternlicht", "M12", "Sternlicht", "3D-Relief im Streiflicht: erst ist alles Nacht. Ein Licht kommt von links, streift MAKER, "
     "die Buchstabenschatten laufen über die Grate des Sterns, auf einer Bezierkurve weich in die Mitte und mit Ease-in/-out "
     "rechts wieder hinaus.", 8.0, sternlicht, "Titelkarte vor einem Video, Story-Intro, ruhiger Screen-Loop"),
    ("portal", "M13", "Portal", "Der Stern ist ein Fenster in die nächste Dimension: halten, zurückziehen, eintauchen, auf dem Schlag "
     "landen. Nacht, Papier, Schwarzlicht. Der Codename wechselt mit.", 3.0, portal, "Loop auf Screens, Übergang zwischen Colorways"),
    ("kreuzwelle", "M14", "Kreuz-Welle", "Der Stern atmet ein und schlägt auf den Drop: eine Welle aus wachsenden Bayer-Kreuzen rollt "
     "Nacht und Papier, die Drehung nimmt nach jedem Treffer Fahrt auf und läuft aus.", 8.0, kreuzwelle,
     "Übergang Nacht <-> Papier, Schnitt im Aftermovie, Loop zur Musik"),
    ("nestpuls", "M15", "Nest-Puls", "Das Acid-Nest im Takt: jeder Schlag zieht einen Ring nach vorn, der äußere Stern und der Satz stehen still.",
     4.0, nestpuls, "Hintergrund-Loop zur Musik (120 BPM), DJ-Screen"),
]
SOUND = ("M14", "M11", "M12", "M13")                               # mit Ton (src/lab_motion_audio.py)
BY = {i[0]: i for i in IDEAS}


def frame(key, f):
    T, fn = BY[key][4], BY[key][5]
    n = round(T * FPS)
    return np.clip(up(fn((f % n) / FPS, n / FPS), PX), 0, 255).astype(np.uint8)


def job(a):
    return frame(*a)


def sheet(pool, key, times=None):
    T = BY[key][4]
    n = round(T * FPS)
    fs = [round(x * FPS) for x in times] if times else [round(n * k / 12) for k in range(12)]
    ims = pool.map(job, [(key, f) for f in fs])
    s = Image.new("RGB", (1920, 360 * ((len(fs) + 2) // 3)))
    for i, im in enumerate(ims):
        s.paste(Image.fromarray(im).resize((640, 360), Image.LANCZOS), ((i % 3) * 640, (i // 3) * 360))
    os.makedirs(os.path.join(OUT, "sheets"), exist_ok=True)
    p = os.path.join(OUT, "sheets", f"{key}.png")
    s.save(p)
    return p


def mp4(pool, key):
    code, T = BY[key][1], BY[key][4]
    n = round(T * FPS)
    path = os.path.join(OUT, f"{code}_{key}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
    for fr in pool.imap(job, [(key, f) for f in range(n)], chunksize=2):
        ff.stdin.write(fr.tobytes())
    ff.stdin.close()
    ff.wait()
    return path


def seam(key):
    """Naht: Schritt letzter Frame -> erster Frame gegen den typischen Schritt (Median) mitten im Clip."""
    T, fn = BY[key][4], BY[key][5]
    n = round(T * FPS)
    g = lambda f: fn((f % n) / FPS, n / FPS)                        # noqa: E731
    step = lambda f: float(np.abs(g(f + 1) - g(f)).mean())         # noqa: E731
    return round(step(n - 1), 2), round(float(np.median([step(f) for f in range(0, n, max(1, n // 12))])), 2)


CHANGES = {  # Runde 3 nach Vadims Feedback (Vorversion zum Vergleich in _v2/)
    "M14": "Halb so schnell (8 s) und fließend: weiches Einatmen, Feder nach dem Treffer ohne Sprung, Welle mit Antritt, Gleiten, "
           "Ausrollen, Drehung nimmt nach jedem Treffer Fahrt auf. Neu mit Ton: die Arp-Melodie aus dem Teaser (C, Dm9, Bbmaj9, Dm9), "
           "Four-on-the-floor, Offbeat-Bass, Clap, Sidechain-Pumpen. Build mit Snare-Roll und Riser, während der Stern einatmet, "
           "0,2 s Luftloch, Drop genau wenn die Welle losrollt. Der Stern glüht auf jedem Kick leicht auf.",
    "M11": "Der dunkle Stern fliegt nicht mehr vorbei: er wächst aus der Mitte des Funkens und dreht sich dabei in die Flucht der "
           "Spitzen. Mit der Deckung greift die Korona aus, der Rest glüht auf, das Licht kippt von Lavendel nach Schwarzlicht und "
           "wieder zurück. Kein Acid-Farbschlag mehr. Ton: Einatmen folgt dem Wachsen, Totalität auf Schlag 4.",
    "M12": "Kein Blob mehr. Echtes 3D-Relief (Höhenfeld auf dem 480x270-Raster: Stern als Pyramide mit Graten, Titel und Datum "
           "aufgeprägt), Lambert, weiche Schlagschatten per Ray-March, Glanz nur auf Fasen. Start komplett dunkel, das Licht kommt "
           "von links über MAKER, auf einer Bezierkurve langsam in die Mitte und mit Ease-in/-out rechts hinaus. 8 s statt 4 s. "
           "Ton neu: Dunkel ist fast Stille, das Pad öffnet mit dem Licht, Glasakkord in der Mitte.",
    "M13": "Kein Grün mehr: Nacht, Papier, Schwarzlicht (P12). Ton deutlich weicher: Sub-Schlag statt Kick, Dreieck-Plucks mit "
           "langsamem Anstieg, kein offener Hat, Sturzrauschen nur bis ca. 1,7 kHz, Tiefpass 9 kHz auf der Summe.",
}


def gallery():
    from html import escape as esc
    try:
        from styles import CSS
    except ImportError:
        CSS = "body{background:#0A0711;color:#F1ECFF;font:15px/1.5 system-ui}video,img{width:100%}"
    by_code = {i[1]: i for i in IDEAS}

    def fig(key, code, title, text, T, _, use, sound=False):
        src = f"{code}_{key}{'_sound' if sound else ''}.mp4"
        attrs = "controls loop playsinline preload=metadata" if sound else "autoplay loop muted playsinline"
        note = f'<br><span><b>Neu:</b> {esc(CHANGES[code])}</span>' if sound and code in CHANGES else ""
        old = (f' <a href="_v2/{code}_{key}{"_sound" if code != "M14" else ""}.mp4">Vorversion</a>'
               if sound and code in CHANGES else "")
        return (f'<figure><video src="{src}" {attrs}></video><figcaption><b>{code}</b> {esc(title)}'
                f'{" · mit Ton" if sound else ""} <span class="st">{T:g} s</span>{old}<br><span>{esc(text)}</span>'
                f'{note}<br><span>Einsatz: {esc(use)}</span></figcaption></figure>')
    top = "".join(fig(*by_code[c], sound=True) for c in SOUND)
    alle = "".join(fig(*i) for i in IDEAS)
    sheets = "".join(f'<figure><img src="sheets/{i[0]}.png" loading=lazy><figcaption><b>{i[1]}</b> {esc(i[2])}</figcaption></figure>'
                     for i in IDEAS)
    page = f"""<!doctype html><html lang="de"><meta charset="utf-8"><title>SPARK Motion-Labor</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style><main>
<nav><a href="../../index.html">&larr; Style Board</a></nav>
<h1>Motion-Labor · M11–M15</h1>
<p class="d">Kurze Intros für das Maker-Night-System. 1920x1080, 30 fps, D3 Bayer 4x4, ein Pixelraster (R = 4 px), Satz wie das Plakat.
Jedes Stück hat einen Bogen auf dem 120-BPM-Raster: Anlauf, Treffer auf dem Schlag, Ausklang. Alle loopen nahtlos.
Runde 3 nach Feedback: M11–M14 überarbeitet, M15 unverändert. Die Vorversionen liegen in <code>_v2/</code>.</p>
<h2>Mit Ton</h2><p class="d">Ton aus demselben Code wie das Bild, jeder Effekt sitzt auf seinem Frame. -14 LUFS, True Peak unter -1 dB.
Kopfhörer empfohlen.</p><div class="grid">{top}</div>
<h2>Alle Stücke</h2><div class="grid">{alle}</div>
<details><summary>Kontaktbögen (12 Frames je Stück) und aussortierte Ideen</summary>
<p class="d">Aussortiert nach Runde 1 (Bögen in <code>_v1/</code>): Interferenz (Flimmer-Demo, Schrift unlesbar), Kaleido (wirkt wie ein
Plasma-Filter), Bit-Tiefe (zu leise, nah an M5), Rotozoom (liest sich als Sternfeld), Kristall (weißes Rauschen = D10).</p>
<div class="grid">{sheets}</div></details></main>"""
    path = os.path.join(OUT, "index.html")
    with open(path, "w") as f:
        f.write(page)
    return path


if __name__ == "__main__":
    cmd, keys = sys.argv[1], sys.argv[2:] or [i[0] for i in IDEAS]
    os.makedirs(OUT, exist_ok=True)
    if cmd == "html":
        sys.exit(print(gallery()))
    with Pool() as pool:
        for k in keys:
            if cmd == "sheet":
                print(sheet(pool, k), seam(k), flush=True)
            elif cmd == "mp4":
                print(mp4(pool, k), seam(k), flush=True)
