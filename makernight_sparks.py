#!/usr/bin/env python3
"""MAKER NIGHT "Sparks make the night": 8,5-s-Teaser, 120 BPM, Bild und Ton in einem Skript.

Ein einziger Funke schweisst den Titel wie ein Laser: pro Buchstabe faehrt ein Kopf die Kontur ab
(skimage find_contours auf der Titelmaske), jeder Buchstabe startet auf einer 16tel-Note. Die Naht glueht
weiss und kuehlt zu Lavendel ab, Funken fliegen mit Schwerkraft. Drop bei 2,0 s: die Buchstaben laufen
weissgluehend voll. Dann Datum, ein angeschnittener Spark-Stern geht auf wie die Sonne (die Nacht endet
am 21.), am Ende zerfaellt die Schrift in Funken und der Funke am "M" zuendet neu: der Clip loopt nahtlos.

Stil: 4-px-Zellen, 6 Palettenstufen, Blue-Noise-Dither, leichter Verlauf ueberall. Schrift und Stern haben
scharfe Kanten (volle Aufloesung), ihre Fuellung ist gedithert: Riso-Look.

  uv run --with numpy --with pillow --with scipy --with scikit-image python makernight_sparks.py          # 16x9 + 9x16
  uv run --with numpy --with pillow --with scipy --with scikit-image python makernight_sparks.py 9x16     # ein Format
  uv run --with numpy --with pillow --with scipy --with scikit-image python makernight_sparks.py preview  # Stills
  uv run --with numpy --with pillow --with scipy --with scikit-image python makernight_sparks.py audio    # nur Ton
  ... makernight_sparks.py 16x9 prores                                                                   # + ProRes
-> makernight/sparks/  sparks_16x9.mp4, sparks_9x16.mp4 (H.264 + AAC, -14 LUFS), sparks.wav
"""
import json
import math
import os
import subprocess
import sys
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt, gaussian_filter, maximum_filter
from scipy.spatial import cKDTree
from skimage.measure import find_contours

from makernight import blue_noise, clip01, sm
from makernight_audio import SR, Bus, bell, boom, bp, clap, env, hat, hp, hz, kick, lp, pluck, reverb, saw, snare, sweep_lp
from makernight_loop import CHORDS as LOOP_CHORDS, fade
from vectors import STAR as MASTER

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "makernight", "sparks")
FONTS = os.path.expanduser("~/Library/Fonts")
FPS, DUR, CELL = 30, 8.5, 4
NF = int(round(DUR * FPS))
SIZES = {"16x9": (1920, 1080), "9x16": (1080, 1920)}

# dunkel -> hell: Nacht, Aubergine, Royal, Amethyst, Lavendel, Weissglut. Exakte Stufen k/5 bleiben flaechig.
PAL = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in
                ("#0A0711", "#221643", "#43287C", "#7049C4", "#AE93EE", "#F6F2FF")], np.float32)
N = len(PAL) - 1

COPY = {"title": "MAKER NIGHT", "sub": "is happening.", "date": "20–21 NOV", "cal": "Put it in your calendar."}

# x: linke Satzkante, big/small: die zwei Schriftgroessen, base: erste Titel-Grundlinie, gap: Luft vor dem Datum
# (in Versalhoehen), star: Mitte x, y und Spitzenradius des Sterns im Endstand (Mitte unter dem Rand = angeschnitten)
LAYOUT = {
    "16x9": dict(x=128, big=200, small=60, base=400, gap=0.85, title=("MAKER NIGHT",), date=("20–21 NOV",),
                 star=(1680, 1150, 700)),
    "9x16": dict(x=88, big=224, small=66, base=410, gap=0.6, title=("MAKER", "NIGHT"), date=("20–21", "NOV"),
                 star=(700, 2070, 760)),
}

# ---------------------------------------------------------------- Timeline (120 BPM, Bild und Ton lesen beide hier)

BEAT = 0.5
S16 = BEAT / 4
T_TRACE, TRACE_D = 0.25, 0.475            # ein Kopf pro Buchstabe, Start auf jeder 16tel -> letzter fertig bei 1,85
T_HUSH, T_DROP = 1.85, 2.0                # kurze Stille, dann laufen die Buchstaben weissgluehend voll
T_SUB, SUB_D = 2.5, 0.375                 # "is happening." per Zuendschnur
T_DATE, DATE_STEP, DATE_D = 4.0, S16 / 2, 0.25   # Datum als 32tel-Kaskade, jedes Zeichen glueht beim Schliessen auf
T_CAL, CAL_D = 6.0, 0.5                   # "Put it in your calendar."
T_CRUMBLE, T_PING = 7.5, 8.0              # Schrift zerfaellt; Funke am M zuendet neu -> Loop

DM9, BB, C9 = LOOP_CHORDS[:3]             # Dm9 | Bbmaj9 | C(add9), exakt wie im Loop


def chord(t):
    return DM9 if t < 4 else BB if t < 6 else C9


def flicker(frame):
    """Helligkeit des einzelnen Funkens am M (0..1) pro Frame. Bild und Knistern lesen denselben Wert."""
    x = (math.sin((frame % NF) * 12.9898 + 4.1) * 43758.5453) % 1
    return 0.25 if x < 0.3 else 0.55 + 0.45 * (x - 0.3) / 0.7


# ---------------------------------------------------------------- Geometrie

_EX = np.linspace(0, 1, 1001)
_EY = 0.5 * _EX + 0.5 * _EX * _EX * (3 - 2 * _EX)       # Kopf: halbe Geschwindigkeit an den Enden


def ease(x):
    return np.interp(x, _EX, _EY)


def ease_inv(y):
    return np.interp(y, _EY, _EX)


def _profile():
    """R(theta) des Master-Sterns (vectors.STAR, kubische Beziers), 0,1-Grad-Schritte, Spitze oben = 1."""
    tt = np.linspace(0, 1, 200, endpoint=False)[:, None]
    pts = np.concatenate([(1 - tt) ** 3 * MASTER[i - 1] + 3 * (1 - tt) ** 2 * tt * MASTER[i]
                          + 3 * (1 - tt) * tt ** 2 * MASTER[i + 1] + tt ** 3 * MASTER[i + 2]
                          for i in range(1, len(MASTER), 3)])
    ang = np.degrees(np.arctan2(pts[:, 1], pts[:, 0])) % 360
    o = np.argsort(ang)
    return np.interp(np.arange(3600) / 10, ang[o], np.hypot(pts[o, 0], pts[o, 1]), period=360)


PROF = _profile()


def star_r(dx, dy, rot):
    """Radius des Sterns (Spitze = 1) in Richtung (dx, dy), rot in Grad."""
    a = (np.degrees(np.arctan2(dy, dx)) - rot) % 360
    return np.interp(a, np.arange(3601) / 10, np.append(PROF, PROF[0]))


def star_alpha(x, y, R, rot, W, H):
    """Scharfe (antialiaste) Sternmaske als Fenster: (y0, y1, x0, x1, alpha) oder None."""
    x0, x1 = max(0, int(x - R) - 1), min(W, int(x + R) + 2)
    y0, y1 = max(0, int(y - R) - 1), min(H, int(y + R) + 2)
    if x0 >= x1 or y0 >= y1:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx, dy = xx - x, yy - y
    return y0, y1, x0, x1, np.clip(star_r(dx, dy, rot) * R - np.hypot(dx, dy) + 0.5, 0, 1)


# ---------------------------------------------------------------- Typo

def font(name, size, var):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    f.set_variation_by_name(var)
    return f


def text_mask(s, f, ox, base):
    """Scharfe Maske in voller Aufloesung, Bounding Box auf das Zellraster ausgerichtet (+2 Zellen Rand)."""
    l, t, r, b = f.getbbox(s, anchor="ls")
    x0 = (int(ox + l) // CELL - 2) * CELL
    y0 = (int(base + t) // CELL - 2) * CELL
    x1 = (-int(-(ox + r)) // CELL + 3) * CELL
    y1 = (-int(-(base + b)) // CELL + 3) * CELL
    im = Image.new("L", (x1 - x0, y1 - y0))
    ImageDraw.Draw(im).text((ox - x0, base - y0), s, font=f, fill=255, anchor="ls")
    return x0, y0, np.asarray(im, np.float32) / 255


def place(s, f, x, track, word):
    """(Zeichen, Ursprung-x) einer Zeile mit Kerning, Laufweite und extra Wortabstand; Tinte beginnt genau bei x."""
    ox, out, extra = x - f.getbbox(s[0], anchor="ls")[0], [], 0.0
    for i, c in enumerate(s):
        extra += word if c == " " else 0.0
        out.append((c, ox + f.getlength(s[:i + 1]) - f.getlength(c) + track * i + extra))
    return out


def cells(m):
    """Vollaufloesung -> Zellmittel."""
    h, w = m.shape
    return m.reshape(h // CELL, CELL, w // CELL, CELL).mean((1, 3))


W0, W1 = 4.5, 4.0          # Nahtbreite in px (kalt), plus Aufschlag an der frischen, fluessigen Stelle
F_LO, F_HI = 0.7, 0.98     # Fuellung kalt: unten Amethyst/Lavendel, oben fast Weissglut
LINE_V = 0.8               # kleine Zeilen: flach Lavendel


class Glyph:
    """Ein Buchstabe: scharfe Maske, Kontur als Bahn fuer den Schweisskopf, Karten fuer Naht, Fuellung, Abkuehlen."""
    def __init__(self, ch, f, ox, base, cap, t0, dur, t_fill, W, sc, seed):
        x0, y0, m = text_mask(ch, f, ox, base)
        h, w = m.shape
        self.x0, self.y0, self.m, self.t0, self.dur, self.t_fill, self.sc = x0, y0, m, t0, dur, t_fill, sc
        inside = m > 0.5
        din = distance_transform_edt(inside).astype(np.float32)

        # Konturen im Uhrzeigersinn (y nach unten: Flaeche > 0), aussen zuerst mit Start unten links,
        # Loecher danach, jeweils ab dem Punkt, der dem letzten Start am naechsten liegt
        def area(c):
            return 0.5 * np.sum(c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1])
        cs = [c[:, ::-1] - 1 for c in find_contours(np.pad(m, 1), 0.5)]
        cs = [c[:-1] if np.allclose(c[0], c[-1]) else c for c in cs]
        cs = sorted((c if area(c) > 0 else c[::-1] for c in cs if len(c) > 8), key=lambda c: -abs(area(c)))
        ys, xs = np.nonzero(inside)
        start = np.array([xs.min(), ys.max()], float)
        P, S, off = [], [], 0.0
        for c in cs:
            c = np.roll(c, -np.argmin(((c - start) ** 2).sum(1)), 0)
            c = np.vstack([c, c[:1]])
            s = off + np.concatenate([[0], np.cumsum(np.hypot(*np.diff(c, axis=0).T))])
            if S:
                s[0] += 1e-3
            P.append(c)
            S.append(s)
            off, start = s[-1], c[0]
        self.P, self.S, self.L = np.vstack(P), np.concatenate(S), off
        tree = cKDTree(self.P)

        def tpass(q):
            return t0 + dur * ease_inv(self.S[tree.query(q)[1]] / self.L)

        by, bx = np.nonzero((m > 0.02) & (din <= (W0 + W1 + 2) * sc))
        self.i_band = (y0 + by) * W + x0 + bx
        self.m_band, self.d_band = m[by, bx], din[by, bx]
        self.tp = tpass(np.stack([bx, by], 1).astype(float))
        ay, ax = np.nonzero(m > 0.02)
        self.i_all, self.m_all, self.d_all = (y0 + ay) * W + x0 + ax, m[ay, ax], din[ay, ax]
        self.inner = self.i_all[self.m_all > 0.5]

        hc, wc = h // CELL, w // CELL
        self.sl = (slice(y0 // CELL, y0 // CELL + hc), slice(x0 // CELL, x0 // CELL + wc))
        self.cov = cells(m)
        self.on = self.cov > 0.001
        cy, cx = np.mgrid[0:hc, 0:wc] * CELL + CELL / 2 - 0.5
        self.tp_c = tpass(np.stack([cx.ravel(), cy.ravel()], 1)).reshape(hc, wc)
        dc = cells(din)
        self.F = F_LO + (F_HI - F_LO) * (1 - np.clip((y0 + cy - (base - cap)) / cap, 0, 1))
        rn = np.random.default_rng(seed).random((hc, wc))
        self.tau = (0.1 + 0.6 * (dc / max(dc.max(), 1)) ** 0.8) * (0.8 + 0.4 * rn)   # dicke Stellen kuehlen langsamer
        self.flood = max(float(din.max()), 1.0) / 0.06                                 # in 2 Frames voll

    def at(self, t):
        s = self.L * ease(np.clip((np.asarray(t) - self.t0) / self.dur, 0, 1))
        return self.x0 + np.interp(s, self.S, self.P[:, 0]), self.y0 + np.interp(s, self.S, self.P[:, 1])

    def head(self, t):
        return self.at(t) if self.t0 <= t < self.t0 + self.dur else None

    def draw(self, t, A, V, Hh):
        if t < self.t0:
            return
        if t < self.t_fill:                       # Naht: nur hinter dem Kopf, frisch dicker und weiss
            age = t - self.tp
            w = (W0 + W1 * np.exp(-np.clip(age, 0, None) / 0.06)) * self.sc
            a = self.m_band * (age >= 0) * np.clip(w - self.d_band + 0.5, 0, 1)
            A[self.i_band] = np.maximum(A[self.i_band], a)
            ac = t - self.tp_c
            heat = np.where(ac >= 0, np.exp(-np.clip(ac, 0, None) / 0.18), 0)
            v = np.where(ac >= 0, 0.8 + 0.2 * heat, 0)
        else:                                     # Fuellung laeuft von der Naht nach innen voll, dann Abkuehlen
            dt = t - self.t_fill
            a = self.m_all * (self.d_all <= W0 * self.sc + self.flood * dt)
            A[self.i_all] = np.maximum(A[self.i_all], a)
            heat = np.exp(-dt / self.tau)
            v = self.F + (1 - self.F) * heat
        on = self.on
        V[self.sl][on] = np.maximum(V[self.sl][on], v[on])
        Hh[self.sl][on] = np.maximum(Hh[self.sl][on], heat[on])


class Line:
    """Kleine Zeile (Satoshi): ein Funke laeuft wie eine Zuendschnur durch und legt sie von links frei."""
    def __init__(self, s, f, x, base, cap, t0, dur, W):
        ox = x - f.getbbox(s, anchor="ls")[0]
        x0, y0, m = text_mask(s, f, ox, base)
        h, w = m.shape
        ys, xs = np.nonzero(m > 0.02)
        self.xa, self.xb, self.hy, self.t0, self.dur = x0 + xs.min(), x0 + xs.max(), base - 0.4 * cap, t0, dur

        def tpass(X):
            return t0 + dur * (X - self.xa) / (self.xb - self.xa)
        self.i_all, self.m_all, self.tp = (y0 + ys) * W + x0 + xs, m[ys, xs], tpass(x0 + xs)
        self.inner = self.i_all[self.m_all > 0.5]
        hc, wc = h // CELL, w // CELL
        self.sl = (slice(y0 // CELL, y0 // CELL + hc), slice(x0 // CELL, x0 // CELL + wc))
        self.cov = cells(m)
        self.on = self.cov > 0.001
        self.tp_c = np.broadcast_to(tpass(x0 + np.arange(wc) * CELL + CELL / 2), (hc, wc))

    def at(self, t):
        return self.xa + (self.xb - self.xa) * np.clip((np.asarray(t) - self.t0) / self.dur, 0, 1), \
            np.full(np.shape(t), self.hy)

    def head(self, t):
        return self.at(t) if self.t0 <= t < self.t0 + self.dur else None

    def draw(self, t, A, V, Hh):
        if t < self.t0:
            return
        A[self.i_all] = np.maximum(A[self.i_all], self.m_all * (t >= self.tp))
        ac = t - self.tp_c
        heat = np.where(ac >= 0, np.exp(-np.clip(ac, 0, None) / 0.15), 0)
        v = np.where(ac >= 0, LINE_V + (1 - LINE_V) * heat, 0)
        on = self.on
        V[self.sl][on] = np.maximum(V[self.sl][on], v[on])
        Hh[self.sl][on] = np.maximum(Hh[self.sl][on], heat[on])


class Star:
    """Der riesige, angeschnittene Spark-Stern: geht bei T_DATE auf wie die Sonne, ab T_CRUMBLE wieder unter."""
    def __init__(self, cx, cy, R):
        self.cx, self.cy, self.R = cx, cy, R

    def state(self, t):
        if not T_DATE - 0.6 < t < T_PING + 0.25:
            return None
        rise = 1 - (1 - clip01((t - T_DATE) / 1.5)) ** 3
        sink = clip01((t - T_CRUMBLE) / 0.6) ** 2
        y = self.cy + self.R * (1.3 * (1 - rise) - 0.06 * clip01((t - T_DATE - 1.5) / 2.0) + 1.4 * sink)
        rot = 30 * (1 - rise) - 2.5 * (t - T_DATE)       # gegen den Uhrzeigersinn: linker Arm sinkt vom Datum weg
        amp = sm(T_DATE - 0.6, T_DATE + 0.9, t) * (1 - sm(T_CRUMBLE, T_PING + 0.1, t))
        return self.cx, y, rot, amp


# ---------------------------------------------------------------- Funken

class Sparks:
    """Funken als geschlossene Flugbahnen (Schwerkraft + Luftwiderstand): jedes Frame direkt ausrechenbar."""
    def __init__(self):
        self.parts = []

    def add(self, b, x, y, vx, vy, life, drag=2.0, grav=2400.0, heat=1.0):
        n = len(b)
        self.parts.append(np.stack([b, x, y, vx, vy, life, np.full(n, drag), np.full(n, grav), np.full(n, heat)]))

    def done(self):
        self.b, self.x, self.y, self.vx, self.vy, self.life, self.k, self.g, self.h = np.concatenate(self.parts, 1)
        self.id = np.arange(len(self.b))

    def pos(self, i, age):
        k = self.k[i]
        e = (1 - np.exp(-k * age)) / k
        return self.x[i] + self.vx[i] * e, self.y[i] + self.vy[i] * e + self.g[i] / k * (age - e)

    def field(self, t, frame, gw, gh):
        S = np.zeros(gh * gw, np.float32)
        for shift in (0.0, DUR):                  # Funken aus dem vorigen Durchlauf fliegen ueber die Loop-Naht
            age = t + shift - self.b
            i = np.nonzero((age >= 0) & (age < self.life))[0]
            if not len(i):
                continue
            a = age[i]
            heat = self.h[i] * np.clip(1.35 * (1 - a / self.life[i]) ** 0.5, 0, 1)   # lange weiss, dann schnell aus
            heat *= 0.8 + 0.2 * ((np.sin(self.id[i] * 12.9898 + frame * 78.233) * 43758.5453) % 1)
            for j in range(9):                    # Bewegungsunschaerfe ueber ein Frame
                x, y = self.pos(i, np.maximum(a - j / 8 / FPS, 0))
                ix, iy = np.floor(x / CELL).astype(int), np.floor(y / CELL).astype(int)
                ok = (ix >= 0) & (ix < gw) & (iy >= 0) & (iy < gh)
                np.maximum.at(S, iy[ok] * gw + ix[ok], heat[ok] * (1 - 0.06 * j))
        S = S.reshape(gh, gw)
        return np.maximum(S, 0.55 * maximum_filter(S * (S > 0.8), 3))            # heisse Funken strahlen


def spray(rng, n, sc, lo=220, hi=1100, up=380):
    ang = rng.uniform(0, 2 * np.pi, n)
    sp = np.exp(rng.uniform(math.log(lo), math.log(hi), n))
    return np.cos(ang) * sp * sc, (np.sin(ang) * sp - up) * sc


# ---------------------------------------------------------------- Szene

class Scene:
    def __init__(self, fmt):
        W, H = SIZES[fmt]
        L = LAYOUT[fmt]
        self.W, self.H, self.gw, self.gh = W, H, W // CELL, H // CELL
        sc = self.sc = min(W, H) / 1080
        big = font("ClashDisplay-Variable.ttf", L["big"], "Semibold")
        small = font("Satoshi-Variable.ttf", L["small"], "Medium")
        cap, capS = -big.getbbox("H", anchor="ls")[1], -small.getbbox("H", anchor="ls")[1]
        pitch, gapS, gapB = 1.25 * cap, 0.34 * cap + capS, (1 + L["gap"]) * cap
        track = -0.02 * L["big"]
        tb = [L["base"] + i * pitch for i in range(len(L["title"]))]
        sub = tb[-1] + gapS
        db = [sub + gapB + i * pitch for i in range(len(L["date"]))]
        cal = db[-1] + gapS

        self.glyphs, self.title, self.date = [], [], []
        for lines, bases, out in ((L["title"], tb, self.title), (L["date"], db, self.date)):
            for s, base in zip(lines, bases):
                for c, ox in place(s, big, L["x"], track, 0.12 * L["big"]):
                    if c == " ":
                        continue
                    i = len(out)
                    if out is self.title:
                        t0, dur, tf = T_TRACE + i * S16, TRACE_D, T_DROP
                    else:
                        t0, dur = T_DATE + i * DATE_STEP, DATE_D
                        tf = t0 + dur
                    out.append(Glyph(c, big, ox, base, cap, t0, dur, tf, W, sc, 50 + len(self.glyphs)))
                    self.glyphs.append(out[-1])
        self.lines = [Line(COPY["sub"], small, L["x"], sub, capS, T_SUB, SUB_D, W),
                      Line(COPY["cal"], small, L["x"], cal, capS, T_CAL, CAL_D, W)]
        self.mx, self.my = (float(v) for v in self.title[0].at(0.0))     # Anfang des M
        self.star = Star(*L["star"])

        gh, gw = self.gh, self.gw
        yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
        nx, ny = (xx + 0.5) / gw, (yy + 0.5) / gh
        grad = (0.35 * nx + ny) / 1.35 if W > H else ny
        rng = np.random.default_rng(26)
        neb = gaussian_filter(rng.standard_normal((gh, gw)), 22)
        self.bg = (0.025 + 0.085 * grad ** 1.3 + 0.01 * neb / neb.std()).astype(np.float32)
        bn = blue_noise(128, 5)
        self.thr = np.tile(bn, (gh // 128 + 1, gw // 128 + 1))[:gh, :gw].astype(np.float32)

        cov = np.zeros((gh, gw), np.float32)
        for g in self.glyphs + self.lines:
            cov[g.sl] = np.maximum(cov[g.sl], g.cov)
        self.t_d = (T_CRUMBLE + 0.3 * nx + 0.12 * ny + 0.035 * self.thr).astype(np.float32)   # Zerfall links -> rechts

        sp = Sparks()
        for g in self.glyphs + self.lines:        # Funkenflug hinter jedem Kopf
            n = rng.poisson((450 if isinstance(g, Glyph) else 220) * g.dur)
            b = rng.uniform(g.t0, g.t0 + g.dur, n)
            x, y = g.at(b)
            x2, y2 = g.at(b - 0.02)
            vx, vy = spray(rng, n, sc)
            sp.add(b, x, y, vx - 0.2 * (x - x2) / 0.02, vy - 0.2 * (y - y2) / 0.02, rng.uniform(0.25, 0.8, n))
        for win in ((T_PING, DUR), (0.0, T_TRACE)):   # der einzelne Funke am M spuckt
            n = rng.poisson(110 * (win[1] - win[0]))
            vx, vy = spray(rng, n, sc, 150, 700, 250)
            sp.add(rng.uniform(*win, n), np.full(n, self.mx), np.full(n, self.my), vx, vy, rng.uniform(0.2, 0.55, n))
        n = 45                                    # Neuzuendung am Ende
        vx, vy = spray(rng, n, sc, 300, 1000, 300)
        sp.add(np.full(n, T_PING), np.full(n, self.mx), np.full(n, self.my), vx, vy, rng.uniform(0.3, 0.7, n))

        def burst(g, n, t, spd, life):
            i = rng.choice(g.inner, n)
            vx = rng.normal(0, 0.4 * spd, n) * sc
            vy = -(0.25 + rng.random(n) ** 1.5) * spd * sc
            sp.add(t + rng.uniform(0, 0.06, n), (i % W).astype(float), (i // W).astype(float), vx, vy,
                   rng.uniform(*life, n), drag=1.6)
        for g in self.title:                      # Drop: Funkenstoss aus allen Buchstaben
            burst(g, 220, T_DROP, 1100, (0.5, 1.3))
        for g in self.date:                       # jedes Datumszeichen ploppt beim Schliessen
            burst(g, 60, g.t_fill, 700, (0.3, 0.8))

        ci = np.nonzero((cov > 0.3).ravel() & (rng.random(gh * gw) < 0.2))[0]   # Zerfall: Text wird zu Glut
        n = len(ci)
        sp.add(self.t_d.ravel()[ci] + rng.uniform(0, 0.02, n), (ci % gw + 0.5) * CELL, (ci // gw + 0.5) * CELL,
               rng.normal(60, 280, n) * sc, -rng.uniform(200, 800, n) * sc, rng.uniform(0.3, 0.6, n),
               drag=2.2, grav=2000.0)
        sp.done()
        self.sparks = sp

    def heads(self, t, frame):
        """Aktive Funken: (x, y, Helligkeit, Groesse)."""
        r = np.random.default_rng(10_000 + frame)
        hs = []
        if t < T_TRACE or t >= T_PING:
            b = flicker(frame)
            boost = 1 + 1.4 * math.exp(-(t - T_PING) / 0.07) if t >= T_PING else 1.0
            hs.append((self.mx, self.my, min(1.3 * b * boost, 1.3), (0.8 + 0.8 * b) * boost))
        for g in self.glyphs:
            p = g.head(t)
            if p is not None:
                hs.append((float(p[0]), float(p[1]), 0.75 + 0.25 * r.random(), 0.8 + 0.5 * r.random()))
        for g in self.lines:
            p = g.head(t)
            if p is not None:
                hs.append((float(p[0]), float(p[1]), 0.6 + 0.2 * r.random(), 0.5 + 0.3 * r.random()))
        return hs, r


# ---------------------------------------------------------------- Frame

_S = {}


def init(fmt):
    _S["s"] = Scene(fmt)


def dither(v, thr):
    x = np.clip(v, 0, 1) * N
    lo = np.floor(x)
    return np.clip(lo + (x - lo > thr), 0, N).astype(np.int8)


def paint(idx, y0, y1):
    c0, c1 = y0 // CELL, -(-y1 // CELL)
    return PAL[np.repeat(np.repeat(idx[c0:c1], CELL, 0), CELL, 1)][y0 - c0 * CELL:y1 - c0 * CELL]


def blend(rgb, idx, a):
    """Scharfe Maske a (voll) ueber rgb, Farbe aus dem geditherten Zellfeld idx (oder fester Farbe)."""
    rows = np.nonzero(a.max(1) > 0)[0]
    if not len(rows):
        return
    y0, y1 = rows[0], rows[-1] + 1
    c = paint(idx, y0, y1) if isinstance(idx, np.ndarray) and idx.ndim == 2 else idx
    rgb[y0:y1] += a[y0:y1, :, None] * (c - rgb[y0:y1])


def glow(G, x, y, amp, sig):
    s = sig / CELL
    gh, gw = G.shape
    cx, cy = x / CELL, y / CELL
    x0, x1 = max(0, int(cx - 3 * s)), min(gw, int(cx + 3 * s) + 2)
    y0, y1 = max(0, int(cy - 3 * s)), min(gh, int(cy + 3 * s) + 2)
    if x0 < x1 and y0 < y1:
        gx = np.exp(-((np.arange(x0, x1) + 0.5 - cx) ** 2) / (2 * s * s))
        gy = np.exp(-((np.arange(y0, y1) + 0.5 - cy) ** 2) / (2 * s * s))
        G[y0:y1, x0:x1] += amp * np.outer(gy, gx)


def render(frame):
    S = _S["s"]
    t = frame / FPS
    W, H, gw, gh, sc = S.W, S.H, S.gw, S.gh, S.sc

    # Schrift: scharfe Alpha (voll), Wert + Resthitze pro Zelle
    A = np.zeros(H * W, np.float32)
    V = np.zeros((gh, gw), np.float32)
    Hh = np.zeros((gh, gw), np.float32)
    for g in S.glyphs + S.lines:
        g.draw(t, A, V, Hh)
    A = A.reshape(H, W)
    if t >= T_CRUMBLE - 0.15:                     # Zerfall: Zelle glueht auf und ist weg
        pre = np.clip(1 - (S.t_d - t) / 0.12, 0, 1) * (V > 0)
        V += (1 - V) * pre
        Hh = np.maximum(Hh, pre)
        A *= np.repeat(np.repeat(S.t_d > t, CELL, 0), CELL, 1)

    # Licht: Koepfe, Resthitze, Blitz im Drop
    G = np.zeros((gh, gw), np.float32)
    hs, r = S.heads(t, frame)
    for x, y, a, _ in hs:
        glow(G, x, y, 0.55 * a, 7 * sc)
        glow(G, x, y, 0.35 * a, 40 * sc)
        glow(G, x, y, 0.12 * a, 150 * sc)
    hot = Hh * cells(A)
    if hot.max() > 0.01:
        G += 0.6 * gaussian_filter(hot, 2.5) + 0.6 * gaussian_filter(hot, 14)
    amb = 0.035 * min(sum(h[2] for h in hs), 3) ** 0.5
    flash = 0.16 * math.exp(-(t - T_DROP) / 0.08) if t >= T_DROP else 0.0

    # Hintergrund: Verlauf + Sternglut, Korn kocht mit 7,5 fps
    boil = np.random.default_rng(frame // 4).integers(0, 128, 2)
    v = S.bg + G + amb + flash
    st = S.star.state(t)
    if st:
        x, y, rot, amp = st
        cy, cx = (np.mgrid[0:gh, 0:gw].astype(np.float32) + 0.5) * CELL
        dx, dy = cx - x, cy - y
        rr = np.hypot(dx, dy)
        d = rr / (star_r(dx, dy, rot) * S.star.R)
        v = v + amp * np.where(d > 1, 0.22 * np.exp(-(d - 1) / 0.35) + 0.2 * np.exp(-rr / S.star.R / 1.6), 0)
    rgb = paint(dither(v, np.roll(S.thr, tuple(boil), (0, 1))), 0, H)

    # Stern: scharfe Kante, gedithertes Gluehen; das Korn wandert mit dem Stern
    if st:
        win = star_alpha(x, y, S.star.R, rot, W, H)
        if win:
            y0, y1, x0, x1, a = win
            full = np.zeros((H, W), np.float32)
            full[y0:y1, x0:x1] = a * amp ** 0.5
            vs = 0.7 + 0.3 * np.clip(1 - d, 0, 1) ** 0.8 + 0.5 * G
            blend(rgb, dither(vs, np.roll(S.thr, (int(y // CELL), int(x // CELL)), (0, 1))), full)

    # Schrift: scharfe Kante, gedruckte (stehende) Koernung
    blend(rgb, dither(V + 0.4 * G, S.thr), A)

    # Koepfe: kleine Spark-Sterne, Weissglut
    Ah = np.zeros((H, W), np.float32)
    for x, y, a, size in hs:
        win = star_alpha(x, y, 30 * sc * size, r.uniform(0, 60), W, H)
        if win:
            y0, y1, x0, x1, al = win
            Ah[y0:y1, x0:x1] = np.maximum(Ah[y0:y1, x0:x1], al * min(1.0, 0.4 + a))
    blend(rgb, PAL[N], Ah)

    # Funken vor allem (Palette ist in allen Kanaelen monoton -> max = hellere Stufe)
    sp = S.sparks.field(t, frame, gw, gh)
    if sp.max() > 0:
        idx = dither(sp, np.roll(S.thr, tuple(r.integers(0, 128, 2)), (0, 1)))
        rgb = np.maximum(rgb, paint(idx, 0, H))

    k = frame - int(round(T_DROP * FPS))          # kurzer Ruck im Drop, in ganzen Zellen
    if 0 <= k < 3:
        rgb = np.roll(rgb, ((4, -4), (-4, 4), (0, 4))[k], (0, 1))
    return np.clip(rgb, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- Ton

def sizzle(sec, seed, lo=2500, hi=11000, rate=220):
    """Schweissen: Rauschband, zerhackt von Knister-Impulsen (Poisson), kurze Blende an beiden Enden."""
    r = np.random.default_rng(seed)
    n = int((sec + 0.08) * SR)
    t = np.arange(n) / SR
    k = r.poisson(rate * sec)
    imp = np.zeros(n)
    imp[r.integers(0, int(sec * SR), k)] = r.random(k) ** 1.5
    crack = np.convolve(imp, np.exp(-np.arange(int(0.012 * SR)) / (0.0025 * SR)))[:n]
    y = bp(r.standard_normal(n), lo, hi) * (0.08 + 1.8 * crack) + 0.7 * hp(r.standard_normal(n), 5000) * crack
    return y * np.clip(t / 0.006, 0, 1) * np.clip((sec + 0.06 - t) / 0.06, 0, 1)


def click(r, dec=0.0012):
    k = int(0.012 * SR)
    return hp(r.standard_normal(k), 2200) * np.exp(-np.arange(k) / SR / dec)


def sweep_pan(sig, p0, p1):
    a = (np.linspace(p0, p1, len(sig)) + 1) * np.pi / 4
    return np.stack([sig * np.cos(a), sig * np.sin(a)], 1) * np.sqrt(2)


def pad(bus, notes, t0, t1):
    """Das Pad aus dem Loop: 4 detunte Saws pro Ton, 20 ms Crossfade in den naechsten Akkord."""
    for m in notes:
        for pan, det in ((-0.8, -0.004), (0.8, 0.004), (-0.3, 0.0015), (0.3, -0.0015)):
            bus.add(fade(saw(hz(m), t1 - t0 + 0.02, det)) * 0.06, t0, pan=pan)


def tape_stop(x, t0, sec):
    i0, k = int(t0 * SR), int(sec * SR)
    pos = i0 + np.cumsum((1 - np.linspace(0, 1, k)) ** 1.6)
    y = x.copy()
    for c in range(2):
        y[i0:i0 + k, c] = np.interp(pos, np.arange(len(x)), x[:, c]) * np.linspace(1, 0, k) ** 0.5
    y[i0 + k:] = 0
    return y


def write_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def loudnorm(src, dst, I=-14, TP=-1, LRA=11):
    """Zwei Durchgaenge: messen, dann linear auf -14 LUFS (Instagram/YouTube)."""
    af = f"loudnorm=I={I}:TP={TP}:LRA={LRA}"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", af + ":print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    af += (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=json")
    err = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-i", src, "-af", af, "-ar", str(SR), "-c:a", "pcm_s16le",
                          dst], capture_output=True, text=True, check=True).stderr
    return json.loads(err[err.rindex("{"):err.rindex("}") + 1])["normalization_type"]


def sound():
    n, nt = int(round(DUR * SR)), int(round((DUR + 3) * SR))
    T = np.arange(nt) / SR
    r = np.random.default_rng(21)
    build, pads, music, kicks, fx = (Bus(nt) for _ in range(5))
    n_title = len(COPY["title"].replace(" ", ""))
    n_date = len(COPY["date"].replace(" ", ""))

    # Aufbau (0,25-1,85): Dm9 aus Pad und Arp, der Filter oeffnet sich unter dem Schweissen
    pad(build, DM9, T_TRACE, T_HUSH)
    prog = lambda s: clip01((s - T_TRACE) / (T_HUSH - T_TRACE))                # noqa: E731
    b = np.stack([sweep_lp(build.x[:, c], lambda s: 300 * (1750 / 300) ** prog(s)) for c in range(2)], 1)
    b *= (np.clip((T - T_TRACE) / 0.3, 0, 1) * (0.55 + 0.45 * np.clip((T - T_TRACE) / 1.6, 0, 1)))[:, None]

    # Drop: Akkorde je 1 Takt, Pad wie im Loop bei 1750 Hz
    for t0, t1 in ((T_DROP, 4.0), (4.0, 6.0), (6.0, 8.0)):
        pad(pads, chord(t0), t0, t1)
    pl = np.stack([lp(pads.x[:, c], 1750) for c in range(2)], 1)

    # Arp: die Loop-Melodie, 16tel ab dem ersten Buchstaben (jede Note = ein Buchstabe startet)
    for i in range(int(T_TRACE / S16), int(8.0 / S16)):
        t = i * S16
        if T_HUSH <= t < T_DROP:
            continue
        c = chord(t)
        seq = [c[2] + 12, c[4] + 12, c[3] + 12, c[1] + 12, c[2] + 24, c[4] + 12, c[3] + 12, c[0] + 24]
        x = prog(t)
        cut, g = (900 + 4100 * x ** 1.5, 0.22 * (0.5 + 0.5 * x)) if t < T_DROP else (5000, 0.22)
        music.add(pluck(hz(seq[i % 8]), cut), t, g * (1 if i % 4 == 0 else 0.7), pan=0.35 * np.sin(i * 1.3))

    # Drums aus dem Loop: Four-on-the-floor, Offbeat-Bass, Hats, Clap auf 2 und 4, Snare-Fill am Ende
    for k in range(int(T_DROP / BEAT), int(8.0 / BEAT)):
        tb = k * BEAT
        root = chord(tb)[0] - 12
        kicks.add(kick(1.1), tb, 0.9)
        music.add(np.tanh(2 * lp(saw(hz(root), 0.22) + saw(hz(root), 0.22, 0.007), 420)) * env(0.22, 0.004, 0.12),
                  tb + BEAT / 2, 0.42)
        music.add(hat(open_=(k % 2 == 1)), tb + BEAT / 2, 0.16, pan=0.25)
        for q in (0.25, 0.75):
            music.add(hat(), tb + BEAT * q, 0.07, pan=-0.3)
        if k % 2 == 1:
            music.add(clap(), tb, 0.5)
    for j in range(8):
        music.add(snare(1.2), 8.0 - 2 * BEAT + j * S16, 0.1 + 0.03 * j, pan=r.uniform(-0.2, 0.2))

    side = np.where(T >= T_DROP, 1 - 0.75 * np.exp(-((T - T_DROP) % BEAT) / 0.11), 1.0)
    m = (music.x + pl) * side[:, None] + kicks.x + b
    m = m + 0.28 * reverb(m, 2.0, 5000)
    m *= np.interp(T, [0, T_HUSH, T_HUSH + 0.02, T_DROP - 0.01, T_DROP], [1, 1, 0.1, 0.1, 1])[:, None]
    m = tape_stop(m, T_CRUMBLE, T_PING - T_CRUMBLE)

    # FX: Knistern am M auf den hellen Frames (vorn und hinten, laeuft ueber die Loop-Naht)
    for f in list(range(int(T_TRACE * FPS))) + list(range(int(T_PING * FPS), NF)):
        fl = flicker(f)
        if fl > 0.7:
            for _ in range(1 + int(fl * 3)):
                fx.add(click(r, r.uniform(0.0006, 0.002)), f / FPS + r.uniform(0, 1 / FPS), 0.32 * fl,
                       pan=r.uniform(-0.75, -0.35))
    # Zischen wandert mit den Koepfen von links nach rechts
    for i in range(n_title):
        fx.add(sizzle(TRACE_D, 100 + i), T_TRACE + i * S16, 0.13, pan=-0.7 + 1.4 * i / (n_title - 1))
    for i in range(n_date):
        fx.add(sizzle(DATE_D, 200 + i), T_DATE + i * DATE_STEP, 0.12, pan=-0.6 + 1.2 * i / (n_date - 1))
        note = (86, 89, 93, 94, 96, 98, 101, 105)[i % 8]                   # Glassplitter aus Bbmaj9
        fx.add(bell(hz(note), 0.5, 0.12), T_DATE + i * DATE_STEP + DATE_D, 0.035, pan=-0.6 + 1.2 * i / (n_date - 1))
    for t0, dur, seed in ((T_SUB, SUB_D, 300), (T_CAL, CAL_D, 301)):         # Zuendschnur
        fx.add(sweep_pan(sizzle(dur, seed, 4000, 12000, 200), -0.6, 0.4), t0, 0.07)
    # 1,85: Reverse-Becken in die Stille, 2,0: Boom
    k = int(0.9 * SR)
    cym = (hp(r.standard_normal(k), 4000) + 0.3 * bp(r.standard_normal(k), 6000, 9500)) * np.linspace(0, 1, k) ** 3
    fx.add(cym, T_DROP - 0.9, 0.4)
    fx.add(boom(), T_DROP, 0.8)
    # 7,5: Schrift zerfaellt -> Glut knistert von links nach rechts, 8,0: Glas-Ping, der Funke zuendet neu
    for j in range(140):
        tt = T_CRUMBLE + 0.45 * (j / 140) ** 0.9 + r.uniform(0, 0.02)
        fx.add(click(r, r.uniform(0.0008, 0.003)), tt, r.uniform(0.04, 0.14), pan=-0.7 + 1.4 * (tt - T_CRUMBLE) / 0.47)
    k = int(0.5 * SR)
    fx.add(lp(r.standard_normal(k), 3000) * np.sin(np.pi * np.arange(k) / k) ** 2, T_CRUMBLE, 0.05)
    fx.add(bell(hz(93), 1.2, 0.5), T_PING, 0.22, pan=-0.45)
    fx.add(bell(hz(100), 1.2, 0.4), T_PING + 0.03, 0.08, pan=0.2)

    f = fx.x + 0.4 * reverb(fx.x, 2.8, 7000, seed=2)
    mix = m + f
    out = mix[:n].copy()
    out[:nt - n] += mix[n:]                       # Fahnen hinter 8,5 s auf den Anfang falten: nahtloser Loop
    out = hp(out.T, 25).T
    out = np.tanh(out * 1.3) / np.tanh(1.3)
    out *= 0.9 / np.abs(out).max()
    os.makedirs(OUT, exist_ok=True)
    raw, wav = os.path.join(OUT, "sparks_raw.wav"), os.path.join(OUT, "sparks.wav")
    write_wav(raw, out)
    kind = loudnorm(raw, wav)
    os.remove(raw)
    print(wav, kind)
    return wav


# ---------------------------------------------------------------- Ausgabe

def video(fmt, wav, prores=False):
    W, H = SIZES[fmt]
    mp4 = os.path.join(OUT, f"sparks_{fmt}.mp4")
    color = ["-vf", "scale=out_color_matrix=bt709:out_range=tv",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav,
           "-map", "0:v", "-map", "1:a", *color, "-c:v", "libx264", "-preset", "slow", "-crf", "14",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", "-shortest", mp4]
    if prores:
        cmd += ["-map", "0:v", "-map", "1:a", *color, "-c:v", "prores_ks", "-profile:v", "3",
                "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s16le", "-shortest", mp4[:-4] + "_prores.mov"]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(initializer=init, initargs=(fmt,)) as pool:
        for i, fr in enumerate(pool.imap(render, range(NF), chunksize=2)):
            ff.stdin.write(fr.tobytes())
            if i % 60 == 0:
                print(f"{fmt} {i}/{NF}", flush=True)
    ff.stdin.close()
    ff.wait()
    print(mp4)


PREVIEW = (0.0, 0.3, 0.6, 1.0, 1.4, 1.9, 2.03, 2.2, 2.7, 3.5, 4.2, 4.6, 5.3, 6.3, 7.2, 7.6, 7.8, 8.1, 8.4)


def preview(fmts):
    for fmt in fmts:
        init(fmt)
        ims = []
        for tt in PREVIEW:
            im = Image.fromarray(render(int(round(tt * FPS))))
            im.save(os.path.join(OUT, f"preview_{fmt}_{tt:04.2f}.png"))
            ims.append(im)
        W, H = SIZES[fmt]
        cols = 5 if W > H else 7
        s = 384 / W
        tw, th = int(W * s), int(H * s)
        sheet = Image.new("RGB", (cols * tw, -(-len(ims) // cols) * th))
        for i, im in enumerate(ims):
            sheet.paste(im.resize((tw, th), Image.LANCZOS), ((i % cols) * tw, (i // cols) * th))
        sheet.save(os.path.join(OUT, f"contact_{fmt}.png"))
        print(fmt, "preview ok")


def main():
    args = sys.argv[1:]
    fmts = [a for a in args if a in SIZES] or list(SIZES)
    os.makedirs(OUT, exist_ok=True)
    if "preview" in args:
        preview(fmts)
        return
    wav = sound()
    if "audio" in args:
        return
    for fmt in fmts:
        video(fmt, wav, "prores" in args)


if __name__ == "__main__":
    main()
