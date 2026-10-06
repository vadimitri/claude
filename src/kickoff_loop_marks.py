#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""Druckmarken des Kick-off-Loops: ein unsichtbares Muster im Druckbild, aus dem ein Handyfoto die Frame-Nummer und
die Lage des Plakats (Homographie) zurueckgibt. Nur im Druck (kickoff_loop.print_files), nie im Video.

  Fotos entzerren + Farbe: src/kickoff_loop_photos.py (nutzt detect/aligned von hier)
  uv run src/kickoff_loop_marks.py test [N..]        Selbsttest an simulierten Fotos des fertigen Druckbilds
                                                     → kickoff_loop/previz/marks/ (report.txt, compare.png)

Verfahren (Stellschrauben in loop.toml [marks], Befund in kickoff_loop/CLAUDE.md "Druckmarken"):
  Muster   Das Zellraster ist in Quadrate ("Chips", chip_cells Zellen) geteilt, jeder Chip ist + oder -, je 2 x 2 Chips
           ausgeglichen (zweimal +, zweimal -): kein Gleichanteil. Jede Palettenfarbe c wird im Chip + zu b + a, im
           Chip - zu b - a (b = c oder knapp daneben, lineares Licht: aus Abstand mischt das Auge genau b zurueck).
  Hub a    je Palettenfarbe die Richtung mit dem meisten Kamerasignal (CAM_AXIS, Blau minus Gelb), bei hoechstens
           amp_ok Abweichung nach dem Augenfilter (S-CIELAB) aus view_m, auf dem Ausdruck UND am Bildschirm gemessen.
           Am Gamut-Rand (Fast-Schwarz, B = 255) wird die Basis b bis tone_ok nach innen geschoben, damit Platz ist.
  Inhalt   Schachbrett aus 2x2-Bloecken: die eine Haelfte "Sync" (in allen Frames gleich, liefert die Lage), die
           andere der Code der Frame-Nummer (Zufallsmuster, Seed = Nummer). Die Nummer ist der Code, der am
           entzerrten Bild am staerksten korreliert (~15000 Code-Chips zusammen, z-Wert gegen Zufall).
           QR, Ruhezone und Gluehen bleiben frei (Scanner).
  Erkennen QR lesen (steht in jedem Frame an derselben Stelle) → grobe Lage, ECC auf der QR-Platte → Perspektive.
           Entzerren, Marke vom Plakat trennen (je Zelle minus gleichfarbige Nachbarn), Sync in 35 Feldern suchen
           → Punktpaare → Homographie (RANSAC), zweimal, dann die Nummer.
"""
import io
import os
import sys
import time
from functools import lru_cache

import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter

import kickoff_loop as KL

OUT = os.path.join(KL.PROJECT, "previz", "marks")
SYNC_SEED = 0x5A4C                # Seed des Sync-Musters. Fest: gedruckte Plakate bleiben lesbar, nie aendern
CODE_SEED = 0xC0DE                # Code von Frame n = Zufall(CODE_SEED, n); ebenso fest
BALANCED = np.array([[1, 1, -1, -1], [1, -1, 1, -1], [1, -1, -1, 1],
                     [-1, -1, 1, 1], [-1, 1, -1, 1], [-1, 1, 1, -1]], np.int8)   # alle 6 ausgeglichenen 2x2-Bloecke
DIRECTIONS = 800                  # Richtungen im linearen RGB, unter denen je Palettenfarbe gewaehlt wird (~4 Grad Raster)
BISECT_STEPS = 16                 # shifted_colors: Halbierungen fuer die groesste erlaubte Hublaenge (2^-16 genau)
LIN_STEP = 1e-4                   # Schritt fuer die Ableitung dOKLab/dlin (vorwaerts: an der 0 gibt es kein Minus)
BIL_RADIUS_CELLS = 4              # signal(): Nachbarn bis zu diesem Abstand (Zellen) vergleichen
BIL_SIGMA = 2.5                   # ... raeumliches Gewicht, Gauss-Sigma in Zellen (~ ein Chip-Paar)
BIL_TAU = 10.0                    # ... Farbgewicht, Sigma in 8-bit-Stufen: Hub der Marke im Foto ~3-8, Abstand zweier
                                  #     Palettenstufen >= ~20 (Befund: 5 trennt die Marke mit ab, 20 laesst Kanten durch)
FIELD_STRIDE_FRAC = 0.5           # Felder ueberlappen um die Haelfte: doppelt so viele Punkte bei gleicher Feldgroesse
QR_TEMPLATE_CELLS = 3             # _qr_ecc: Vorlage = QR-Module + so viele Zellen Rand (Ruhezone 2 + 1; das Gluehen
                                  # dahinter faellt je Frame anders aus)
ECC_ITER = 100                    # ... hoechstens so viele Schritte
ECC_BLUR_CELLS = 1                # ... Gauss vor dem Vergleich, Fenster in Zellen: glaettet Bayer-Korn und Marke
ECC_MIN_CC = 0.6                  # ... unter dieser Korrelation gilt ECC als daneben (Befund: getroffen 0.89-0.96)
POLISH_BELOW_FIELDS = 30          # polish nur bei weniger Sync-Feldern: mit vielen sind die Marken genauer (Befund
                                  # Frame 1/21: 0.03 % → 0.10-0.13 % mit ECC; Frame 40: 0.80 % → 0.17 %)
POLISH_PX = 2                     # polish(): Render auf 2 px pro Zelle (Foto ~3 px/Zelle; 4 waere nur langsamer)
POLISH_MIN_CC = 0.7               # ... Korrelation, ab der der Render als passend gilt
POLISH_MAX_CELLS = 3.0            # ... so weit darf ECC eine Plakatecke gegenueber den Marken verschieben (Marken
                                  #     liegen bei <= 0.8 % = 2.3 Zellen; mehr hiesse: ECC rastet falsch ein)
CAM_AXIS = np.array([-0.5, -0.5, 1.0]) / np.sqrt(1.5)   # Kamera liest Blau minus Gelb (R, G, B im Foto). Alle drei
                                  # Komponenten != 0: jede Farbe mit Luft in irgendeinem Kanal kann darauf Signal geben
SYNC_Z_MIN = 4.0                  # Feld zaehlt ab diesem z (Rauschen ohne Marken: Median 3.3, max 4.8); was trotzdem
                                  # zufaellig drueber liegt, wirft RANSAC raus (Zufallsgipfel liegen auf keiner Ebene)
MIN_FIELDS = 12                   # ... und mindestens so viele Felder (4 Punkte reichen fuer H, RANSAC braucht Reserve)
CODE_Z_MIN = 8.0                  # Nummer gilt ab diesem z-Wert (Zufall: Maximum ueber 64 Codes ~2.4, > 5 praktisch nie)
RANSAC_PX = 2.0                   # Punktpaar ist Ausreisser ab diesem Abstand im Foto
FINE_SEARCH_CELLS = 4             # Suchradius im letzten Durchgang (Lage dann auf ~1 Zelle; 4 statt 2, sonst hat die
                                  # Karte zu wenig Werte fuer den z-Wert und gute Felder fallen raus)
QR_SCALES = (0.5, 0.35, 0.7, 1.0, 0.25)   # Grobsuche: Foto so verkleinert dem QR-Leser geben (OpenCV liest je nach
                                          # Modulgroesse; 12-MP-Foto, Modul ~6 px → 0.5 gibt ~3 px, wie im Druck-Check)

# S-CIELAB (Zhang & Wandell 1997, Parameter der Referenzimplementierung scielab.m): Ortsfilter des Auges je
# Gegenfarbkanal als Summe von Gauss-Kernen exp(-r^2/s^2), s in Grad Sehwinkel, mit Gewicht. Hier auf OKLab L/a/b
# angewendet (Naeherung: OKLab ist ebenfalls ein Gegenfarbraum: Helligkeit, Rot-Gruen, Blau-Gelb).
SCIELAB = (((0.05, 1.00327), (0.225, 0.114416), (7.0, -0.117686)),
           ((0.0685, 0.616725), (0.826, 0.383275)),
           ((0.0920, 0.567885), (0.6451, 0.432115)))
JND_OK = 0.02                     # eben merklicher Unterschied in deltaE OK (CSS Color 4, Gamut-Mapping: JND 0.02)
A3_CELL_MM = 297 / 292            # Zellgroesse im A3-Druck (Breite / Zellen), ~1 mm. A4: 0.71 mm (weniger sichtbar)
CLOSE_M = 0.3                     # Bericht: Sichtbarkeit auch aus 30 cm (Nase am Plakat), ohne Gate

# Simuliertes Foto (Selbsttest), aus dem Shooting-Plan (ENTSCHEIDUNGEN: Hochformat, Hauptkamera 1x, Plakat ~1/3 der
# Fotohoehe, von vorn, kein Blitz) und dem Auftrag (Perspektive +/- 20 Grad, Unschaerfe, Rauschen, WB, JPEG q80, Druck):
PHOTO_WH = (3000, 4000)           # 12 MP Hochformat
PHOTO_F_PX = 2900                 # 26 mm KB-aequivalent: f = 2000 px / tan(34.7 Grad) auf der langen Seite
SIM_TILT_DEG = 20                 # Gieren/Nicken bis +/- 20 Grad
SIM_ROLL_DEG = 5                  # Rollen bis +/- 5 Grad (Handy gerade gehalten)
SIM_HEIGHT_FRAC = (0.28, 0.40)    # Plakathoehe / Fotohoehe ("~1/3")
SIM_SHIFT_FRAC = 0.08             # Plakatmitte bis so weit von der Bildmitte (Bruchteil der Bildgroesse)
SIM_SRC_PX = 6                    # Druckbild fuer die Simulation auf 6 px/Zelle gemittelt (0.5 mm, feiner als das Foto)
SIM_BLUR_PX = (0.8, 2.5)          # Optik + Fokus: Gauss-Sigma im Foto. Vadim 2.10.: Fotos sind nicht pixelgenau scharf;
                                  # 2.5 px = 0.8 Zellen, das Bayer-Korn ist dann schon halb verwaschen
SIM_SHAKE_PX = (0.0, 4.0)         # Verwacklung: Bewegungsunschaerfe, Laenge in Fotopixeln, Richtung zufaellig
SIM_NOISE = (2.0, 5.0)            # Sensorrauschen, Sigma in 8-bit-Stufen (Innenraum ohne Blitz)
SIM_CHROMA_NR_PX = 1.5            # Farbrausch-Filter der Handy-Kamera: glaettet Cb/Cr mit diesem Sigma, Y nicht
SIM_WB = 0.15                     # Weissabgleich: Kanalfaktoren 1 +/- 0.15
SIM_EXPOSURE = (0.75, 1.15)       # Belichtung (Faktor auf lineares Licht)
SIM_JPEG_Q = 80                   # JPEG-Qualitaet, Pillow-Standard 4:2:0 (Farbe in halber Aufloesung)
PRINT_PAPER = 0.88                # Ausdruck: Papierweiss reflektiert ~88 % (relativ zu dem, was die Kamera als Weiss nimmt)
PRINT_BLACK = 0.03                # ... Tiefschwarz ~3 % (Dichte ~1.5, Laser/Tinte auf Normalpapier)
PRINT_GAMMA = 1.15                # ... Tonwertzunahme: Mitteltoene dunkler (lineare Helligkeit ^ 1.15)
PRINT_DESAT = 0.85                # ... CMYK-Gamut: Buntheit auf 85 % (gesaettigte RGB-Toene sind nicht druckbar)
CORNER_GATE_FRAC = 0.005          # Gate: Eckfehler < 0.5 % der Plakatbreite (Auftrag)
TEST_WORKERS = 6                  # Prozesse im Selbsttest: ein Foto braucht in der Spitze ~2-3 GB (12 MP float), mehr
                                  # Prozesse lagern auf 16 GB aus (Befund: 12 Prozesse 240 s, 280 % CPU)
ALIGN_BLUR_PX = 3.0               # align_ncc: Render und Entzerrung vor dem Vergleich so weichzeichnen (Vorschaupixel)
ALIGN_NCC_MIN = 0.8               # ... Gate fuer die Korrelation
COMPARE_FRAMES = (0, 20, 44)      # compare.png: Frame 1 (dunkel, Pastell-Stern), 21 (Papier), 45 (fast schwarz)
COMPARE_AT_FRAC = (0.42, 0.55)    # ... Ausschnitt ab dieser Stelle (Bruchteil Hoehe, Breite): Stern + Grund
COMPARE_CROP_PX = (150, 200)      # ... Ausschnitt Hoehe x Breite in Druckpixeln (12 px = 1 Zelle), gezeigt 4x
NEG_FRAMES = 8                    # Gegenproben: so viele Frames ohne Marken bzw. mit falscher Nummer


# ---------------------------------------------------------------- Config

def check(cfg):
    """[marks] pruefen, bevor gerechnet wird: Klartext statt Abbruch nach Minuten."""
    assert "marks" in cfg, "loop.toml: Abschnitt [marks] fehlt (Druckmarken, src/kickoff_loop_marks.py)"
    m = cfg["marks"]
    for k, t in {"enabled": bool, "chip_cells": int, "amp_ok": float, "tone_ok": float, "view_m": float,
                 "patch_chips": int, "search_cells": int}.items():
        assert isinstance(m.get(k), t), f"[marks].{k}: fehlt oder ist kein {t.__name__}"
    assert m["chip_cells"] >= 1, "[marks].chip_cells: mindestens 1 Zelle"
    assert m["patch_chips"] >= 8 and m["patch_chips"] % 2 == 0, "[marks].patch_chips: gerade (2x2-Bloecke), >= 8"
    assert 0 < m["amp_ok"] < JND_OK, f"[marks].amp_ok: Budget nach dem Augenfilter, zwischen 0 und JND {JND_OK}"
    assert 0 <= m["tone_ok"] < JND_OK, f"[marks].tone_ok: Tonverschiebung zwischen 0 und JND {JND_OK}"
    assert m["view_m"] > 0 and m["search_cells"] > 0, "[marks].view_m, search_cells: > 0"
    keep = cfg["qr"]["quiet_cells"] + cfg["qr"]["glow_cells"]               # QR-Platte + Gluehen bleiben frei (embed)
    return dict(m, keep_cells=keep)


# ---------------------------------------------------------------- Muster

def _blocks(rng, gh, gw):
    """gh x gw Chips aus zufaellig gewaehlten ausgeglichenen 2x2-Bloecken."""
    b = BALANCED[rng.integers(0, len(BALANCED), (gh // 2, gw // 2))].reshape(gh // 2, gw // 2, 2, 2)
    return b.transpose(0, 2, 1, 3).reshape(gh, gw)


def pattern(m, n, grid):
    """Chips fuer Frame n (1-basiert) auf einem Zellraster grid = (Zeilen, Spalten): (sync, code), Werte +1/-1/0.
    Sync und Code liegen auf einem Schachbrett aus 2x2-Bloecken, nie auf demselben Chip. n = 0: kein Code."""
    c = m["chip_cells"]
    gh, gw = [-(-g // c) + (-(-g // c)) % 2 for g in grid]   # Chips, aufgerundet auf gerade
    board = (np.add.outer(np.arange(gh) // 2, np.arange(gw) // 2) % 2).astype(bool)
    sync = np.where(board, _blocks(np.random.default_rng(SYNC_SEED), gh, gw), 0).astype(np.int8)
    code = np.where(~board, _blocks(np.random.default_rng([CODE_SEED, n]), gh, gw), 0).astype(np.int8) if n else \
        np.zeros_like(sync)
    return sync, code


def chip_image(chips, m, px, shape):
    """Chips → Pixel (px pro Zelle), auf shape zugeschnitten."""
    k = m["chip_cells"] * px
    return np.repeat(np.repeat(chips, k, 0), k, 1)[:shape[0], :shape[1]]


# ---------------------------------------------------------------- Auge

def cells_per_deg(view_m, cell_mm=A3_CELL_MM):
    return view_m * 1000 * np.tan(np.radians(1)) / cell_mm


def eye(lab, cpd):
    """Was das Auge aus Abstand sieht: S-CIELAB-Filter je Kanal auf ein OKLab-Bild mit einem Wert pro Zelle
    (cpd Zellen pro Grad). Gaussfilter von scipy sind auf Summe 1 normiert, wie in scielab.m."""
    out = np.empty_like(lab)
    for k, terms in enumerate(SCIELAB):
        out[..., k] = sum(w * gaussian_filter(lab[..., k], s * cpd / np.sqrt(2), mode="nearest") for s, w in terms)
    return out


@lru_cache(maxsize=4)
def eye_gain(chip_cells, view_m):
    """Wie viel vom Chip-Muster das Auge je Kanal (L, a, b) noch sieht: RMS nach / vor dem Filter, am echten Muster."""
    m = dict(chip_cells=chip_cells)
    sync, code = pattern(m, 1, (413, 292))
    p = chip_image((sync + code).astype(np.float64), m, 1, (413, 292))
    f = eye(np.repeat(p[..., None], 3, 2), cells_per_deg(view_m))
    return np.sqrt((f ** 2).mean((0, 1))) / np.sqrt((p ** 2).mean())


# ---------------------------------------------------------------- Farben verschieben

def _to_lin(cols):
    a = np.asarray(cols, np.float64) / 255
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _from_lin(lin):
    lin = np.clip(lin, 0, 1)
    return np.round(np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055) * 255).astype(np.uint8)


def _oklab_of_lin(lin):
    return np.cbrt(lin @ KL._M1.T) @ KL._M2.T


@lru_cache(maxsize=1)
def _directions():
    """Gleichmaessig verteilte Einheitsvektoren (Fibonacci-Kugel, ganze Kugel)."""
    k = np.arange(DIRECTIONS) + 0.5
    z = 1 - 2 * k / DIRECTIONS
    r, phi = np.sqrt(1 - z * z), np.pi * (3 - np.sqrt(5)) * k
    return np.stack([r * np.cos(phi), r * np.sin(phi), z], 1)


def printed(lin):
    """Bildschirm-Licht (linear) → Ausdruck, relativ zum Papierweiss (Auge und Kamera stellen sich auf das Papier ein):
    Buntheit auf CMYK-Mass, Tonwertzunahme, Tiefschwarz begrenzt. Danach misst die Sichtbarkeit (das Auge sieht den
    Druck, nicht den Bildschirm: im Druck ist Fast-Schwarz zusammengedrueckt) und daraus simuliert der Selbsttest."""
    y = lin @ KL.LUMA
    p = np.clip(y[..., None] + PRINT_DESAT * (lin - y[..., None]), 0, 1)
    return (PRINT_BLACK + (PRINT_PAPER - PRINT_BLACK) * p ** PRINT_GAMMA) / PRINT_PAPER


def _seen(lin):
    """OKLab, wie das Auge den Ausdruck sieht."""
    return _oklab_of_lin(printed(lin))


def _shot(lin):
    """8-bit-Werte, wie die Kamera den Ausdruck sieht (Belichtung auf Papierweiss, sRGB-Kurve)."""
    p = printed(lin)
    return 255 * np.where(p <= 0.0031308, p * 12.92, 1.055 * np.maximum(p, 1e-12) ** (1 / 2.4) - 0.055)


def _jac(f, c):
    """Ableitung von f nach dem linearen RGB an c (3 x 3), an den Grenzen einseitig."""
    cols = []
    for e in np.eye(3):
        lo, hi = np.clip(c - LIN_STEP * e, 0, 1), np.clip(c + LIN_STEP * e, 0, 1)
        cols.append((f(hi) - f(lo)) / max((hi - lo) @ e, 1e-12))
    return np.stack(cols, 1)


def shifted_colors(cols, m):
    """Je Palettenfarbe (N x 3, 0..255) die Farben fuer Chip + und - und die Basis (Mittel von + und -).
    Gesucht pro Farbe unter DIRECTIONS Richtungen e (lineares RGB) und Laengen s: groesstes Kamerasignal entlang
    CAM_AXIS, wobei (1) der Wechsel +/- nach dem Augenfilter hoechstens amp_ok sichtbar ist und (2) die Basis
    hoechstens tone_ok von der Originalfarbe abweicht. (2) ist noetig, weil die Paletten am Gamut-Rand liegen
    (070608 fast Schwarz, bdebff B = 255): Ohne Luft nach beiden Seiten geht kein symmetrischer Hub; die Basis
    wird dann so weit nach innen geschoben, wie der Hub braucht (eine gleichmaessige, unmerkliche Tonverschiebung,
    keine Marke). Symmetrisch um die Basis im linearen Licht: aus Abstand mischt das Auge + und - zur Basis.
    Eine Kamera-Achse fuer alle Farben, sonst loeschen sich zwei Farben im Dither aus (Befund Frame 57: bdebff und
    f2fbff mit entgegengesetztem Rot-Gruen-Hub, die Felder fanden falsche Gipfel)."""
    lin = _to_lin(cols)
    gain = eye_gain(m["chip_cells"], m["view_m"])
    E = _directions()
    inward = lambda c: np.where(c < 0.5, 1.0, -1.0)                       # noqa: E731
    plus, minus, base = [], [], []
    for c in lin:
        Je, Jc, Js = _jac(_seen, c), _jac(_shot, c), _jac(_oklab_of_lin, c)
        vis = np.maximum(np.linalg.norm((E @ Je.T) * gain, axis=1), np.linalg.norm((E @ Js.T) * gain, axis=1))
        s_vis = m["amp_ok"] / np.maximum(vis, 1e-12)
        cam = (E @ Jc.T) @ CAM_AXIS                                         # Kamerasignal je Einheit (mit Vorzeichen)
        room = np.minimum(c, 1 - c)

        def lift(s):                                                        # Basis-Verschiebung, die Hub s braucht
            return np.maximum(s[:, None] * np.abs(E) - room, 0) * inward(c)

        lo, hi = np.zeros(len(E)), np.ones(len(E))
        for _ in range(BISECT_STEPS):                                       # groesstes t <= 1 mit Tonverschiebung ok
            mid = (lo + hi) / 2
            sh = lift(mid * s_vis)
            ok = np.maximum(np.linalg.norm(sh @ Je.T, axis=1), np.linalg.norm(sh @ Js.T, axis=1)) <= m["tone_ok"]
            lo, hi = np.where(ok, mid, lo), np.where(ok, hi, mid)
        s = lo * s_vis
        best = np.argmax(cam * s)
        c2 = np.clip(c + lift(s)[best], 0, 1)
        a = E[best] * s[best]
        plus.append(_from_lin(c2 + a)), minus.append(_from_lin(c2 - a)), base.append(c2)
    return np.array(plus), np.array(minus), np.array(base)


def embed(img, n, m, px):
    """Druckmarken fuer Frame n in ein fertiges Plakatbild (px pro Zelle). Arbeitet auf den Palettenfarben (wenige pro
    Bild), jede wird je Chip-Vorzeichen durch ihre verschobene ersetzt. QR, Ruhezone und Gluehen ([qr] quiet_cells +
    glow_cells) bleiben frei: das Gluehen ist die Ruhezone fuer den Scanner. Befund: Marken im Gluehen liessen
    kickoff.check_qr bei Frame 1 und 6 durchfallen (3 von 4 Modulgroessen unlesbar), nur die Platte frei reichte nicht."""
    sync, code = pattern(m, n, (img.shape[0] // px, img.shape[1] // px))
    sign = chip_image(sync + code, m, px, img.shape[:2])
    (x0, y0), (x1, y1) = _qr_cells().min(0) - m["keep_cells"], _qr_cells().max(0) + m["keep_cells"]
    sign[max(round(y0 * px), 0):round(y1 * px), max(round(x0 * px), 0):round(x1 * px)] = 0   # QR bleibt unberuehrt
    flat = (img[..., 0].astype(np.uint32) << 16) | (img[..., 1].astype(np.uint32) << 8) | img[..., 2]
    vals, inv = np.unique(flat, return_inverse=True)
    plus, minus, _ = shifted_colors(np.stack([vals >> 16, (vals >> 8) & 255, vals & 255], 1), m)
    inv = inv.reshape(img.shape[:2])
    return np.where((sign > 0)[..., None], plus[inv], np.where((sign < 0)[..., None], minus[inv], img)).astype(np.uint8)


def print_image(cfg, img, i, px):
    """Hook fuer kickoff_loop.print_files: Plakat i (0-basiert) mit Marken, falls [marks].enabled."""
    m = check(cfg)
    return embed(img, i + 1, m, px) if m["enabled"] else img


# ---------------------------------------------------------------- Erkennen

@lru_cache(maxsize=1)
def _qr_cells():
    """Ecken des QR in Zellen, wie der QR-Leser sie am Render findet (in allen Frames gleich: kickoff.layout)."""
    import cv2
    cfg = KL.load()
    ok, pts = cv2.QRCodeDetector().detect(KL.frame(cfg, 0)[..., ::-1])
    assert ok, "QR im Render von Frame 1 nicht gefunden"
    return pts.reshape(4, 2) / KL.PREVIEW_CELL_PX


@lru_cache(maxsize=1)
def _qr_template():
    """QR-Platte als Graubild (Vorschau, 4 px pro Zelle) und ihre Lage in Zellen. In allen Frames gleich: Module in der
    dunkelsten, Platte in der hellsten Stufe (kickoff_loop.qr_glow), nur die Farben wechseln; ECC misst Kontrast,
    nicht Farbe."""
    import cv2
    (x0, y0), (x1, y1) = _qr_cells().min(0) - QR_TEMPLATE_CELLS, _qr_cells().max(0) + QR_TEMPLATE_CELLS
    q = KL.PREVIEW_CELL_PX
    grey = cv2.cvtColor(KL.frame(KL.load(), 0), cv2.COLOR_RGB2GRAY).astype(np.float32)
    return grey[round(y0 * q):round(y1 * q), round(x0 * q):round(x1 * q)], (x0, y0)


def _ecc(photo, H, T, origin, px):
    """H (Zellen → Foto) nachfuehren, bis das Foto auf die Vorlage T passt (Graubild, px pro Zelle, linke obere Ecke
    bei origin in Zellen): ECC (Evangelidis & Psarakis 2008, OpenCV), Homographie. ECC misst normierte Korrelation,
    also Kontrast, nicht Farbe oder Belichtung. (H, Korrelation) oder (None, 0), wenn es nicht konvergiert."""
    import cv2
    A = np.array([[1 / px, 0, 0.5 / px + origin[0]], [0, 1 / px, 0.5 / px + origin[1]], [0, 0, 1]])   # Vorlage → Zelle
    grey = cv2.cvtColor(photo, cv2.COLOR_RGB2GRAY).astype(np.float32)
    w = cv2.warpPerspective(grey, H @ A, (T.shape[1], T.shape[0]), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    try:
        cc, W = cv2.findTransformECC(T, w, np.eye(3, dtype=np.float32), cv2.MOTION_HOMOGRAPHY,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, ECC_ITER, 1e-6), None,
                                     ECC_BLUR_CELLS * px | 1)
    except cv2.error:
        return None, 0.0
    return H @ A @ W @ np.linalg.inv(A), float(cc)


def _qr_ecc(photo, H):
    """Lage des QR genau: ECC an der bekannten QR-Platte. Befund: die Hochrechnung aus den drei QR-Ecken liegt an der
    fernen Plakatecke 6-28 % daneben (affin, keine Perspektive), nach ECC 0.2-3 %. None, wenn ECC daneben liegt."""
    T, origin = _qr_template()
    H2, cc = _ecc(photo, H, T, origin, KL.PREVIEW_CELL_PX)
    return H2 if cc > ECC_MIN_CC else None


def polish(photo, H, poster):
    """Feinschliff nach der Nummer: ECC ueber das ganze Plakat gegen seinen Render (poster: Vorschau, 4 px/Zelle,
    auf POLISH_PX verkleinert). Befund: wo das Sync nur in einer Ecke des Plakats traegt (Frame 40, 44: fast
    schwarz, 18 Felder), lag die ferne Ecke bis 0.8 % daneben. Uebernommen nur, wenn ECC gut korreliert und die Ecken
    hoechstens POLISH_MAX_CELLS verschiebt (sonst passt der Render nicht zum Druck, z. B. loop.toml nach dem Druck
    geaendert: dann bleibt die Lage aus den Marken). (H, Korrelation, uebernommen)."""
    import cv2
    q = KL.PREVIEW_CELL_PX // POLISH_PX
    T = cv2.cvtColor(poster[::q, ::q] if q > 1 else poster, cv2.COLOR_RGB2GRAY).astype(np.float32)
    H2, cc = _ecc(photo, H, T, (0, 0), POLISH_PX)
    if H2 is None:
        return H, 0.0, False
    gh, gw = poster.shape[0] / KL.PREVIEW_CELL_PX, poster.shape[1] / KL.PREVIEW_CELL_PX
    c = np.array([[[0, 0], [gw, 0], [gw, gh], [0, gh]]], np.float64)
    back = cv2.perspectiveTransform(cv2.perspectiveTransform(c, H2), np.linalg.inv(H))[0]   # in Zellen von H
    ok = cc > POLISH_MIN_CC and np.abs(back - c[0]).max() <= POLISH_MAX_CELLS
    return (H2 if ok else H), cc, bool(ok)


def coarse(photo):
    """Grobe Lage Zellen → Foto aus dem QR, als Liste von Kandidaten: affin aus den drei Ecken mit Suchmuster (oben
    links, oben rechts, unten links; die vierte schaetzt der Leser nur, Befund: bis 10 px daneben), dann ECC auf der
    QR-Platte (_qr_ecc). Dekodiert der QR, ist die Drehung sicher (ein Kandidat); findet der Leser ihn nur, kommen
    alle 4 Drehungen (Befund Frame 45: detect() allein lieferte die Ecken um 90 Grad verdreht)."""
    import cv2
    grey = cv2.cvtColor(photo, cv2.COLOR_RGB2GRAY)
    found = None
    for det in (cv2.QRCodeDetector(), cv2.QRCodeDetectorAruco()):
        for k in QR_SCALES:
            small = cv2.resize(grey, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            txt, pts, _ = det.detectAndDecode(small)
            if txt == KL.K.COPY["qr_url"] and pts is not None:
                found = [pts.reshape(4, 2) / k]
                break
            ok, pts = det.detect(small)
            if found is None and ok and pts is not None and cv2.contourArea(pts.reshape(4, 2).astype(np.float32)) > 100:
                found = [np.roll(pts.reshape(4, 2) / k, r, 0) for r in range(4)]
        if found and len(found) == 1:
            break
    out = []
    for p in found or []:
        A = cv2.getAffineTransform(_qr_cells()[[0, 1, 3]].astype(np.float32), p[[0, 1, 3]].astype(np.float32))
        H = np.vstack([A, [0, 0, 1]])
        fine = _qr_ecc(photo, H)
        out.append(H if fine is None else fine)
    return out


def rectify(photo, H, grid, pad):
    """Foto → ein Wert pro Zelle (Zellmitte), pad Zellen Rand ringsum. H: Zellen → Fotopixel."""
    import cv2
    A = np.array([[1, 0, 0.5 - pad], [0, 1, 0.5 - pad], [0, 0, 1]])
    return cv2.warpPerspective(photo, H @ A, (grid[1] + 2 * pad, grid[0] + 2 * pad),
                               flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT
                               ).astype(np.float32)


def signal(cells):
    """Marke vom Plakat trennen: jede Zelle minus dem Mittel ihrer Nachbarn GLEICHER Farbe (bilateral: Nachbarn, die
    mehr als ~BIL_TAU abweichen, sind eine andere Palettenstufe und zaehlen nicht). Uebrig bleibt der Hub der Marke
    (+/-) plus Rauschen; Dither-Kanten, Verlaeufe und Flaechen fallen weg. Befund: z der Nummer 64-90 statt 17-48
    mit einem Gauss-Hochpass. Zurueck kommt die Projektion auf CAM_AXIS (ein Kanal)."""
    R = BIL_RADIUS_CELLS
    P = np.pad(cells, ((R, R), (R, R), (0, 0)), mode="reflect")
    num, den = np.zeros_like(cells), np.zeros(cells.shape[:2], np.float32)
    h, w = cells.shape[:2]
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            if dy or dx:
                nb = P[R + dy:R + dy + h, R + dx:R + dx + w]
                wt = np.exp(-((nb - cells) ** 2).sum(2) / (2 * BIL_TAU ** 2) - (dy * dy + dx * dx) / (2 * BIL_SIGMA ** 2))
                num += wt[..., None] * nb
                den += wt
    return ((cells - num / np.maximum(den, 1e-6)[..., None]) @ CAM_AXIS).astype(np.float32)


def _peak(r):
    """Gipfel einer Korrelationskarte mit Unterzelle (Parabel je Achse) und z-Wert gegen den Rest der Karte."""
    y, x = np.unravel_index(np.argmax(r), r.shape)
    if not (0 < y < r.shape[0] - 1 and 0 < x < r.shape[1] - 1):
        return None
    sub = lambda a, b, c: 0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c < 0 else 0.0   # noqa: E731
    dy, dx = sub(r[y - 1, x], r[y, x], r[y + 1, x]), sub(r[y, x - 1], r[y, x], r[y, x + 1])
    rest = np.delete(r.ravel(), np.ravel_multi_index((y, x), r.shape))
    med = np.median(rest)
    z = (r[y, x] - med) / (1.4826 * np.median(np.abs(rest - med)) + 1e-9)
    return y + dy, x + dx, z


def fields(sig, m, sync, grid, pad, search):
    """Sync feldweise suchen (Suchradius search Zellen): Liste (Feldmitte im Plakat, wo sie im entzerrten Bild liegt,
    z), in Zellen."""
    import cv2
    F = m["patch_chips"] * m["chip_cells"]
    step = round(F * FIELD_STRIDE_FRAC)
    tmpl = chip_image(sync.astype(np.float32), m, 1, grid)
    r, out = search, []
    for cy in range(0, grid[0] - F + 1, step):
        for cx in range(0, grid[1] - F + 1, step):
            ctr = np.array([cx + F / 2, cy + F / 2])
            t = tmpl[cy:cy + F, cx:cx + F]
            win = sig[cy + pad - r:cy + pad + F + r, cx + pad - r:cx + pad + F + r]
            pk = _peak(cv2.matchTemplate(np.ascontiguousarray(win), t, cv2.TM_CCOEFF_NORMED))
            if pk and pk[2] >= SYNC_Z_MIN:
                out.append((ctr, ctr + np.array([pk[1] - r, pk[0] - r]), pk[2]))
    return out


def decode(sig, m, sync, grid, pad, codes):
    """z-Wert je Code-Nummer am entzerrten Bild: Mittel je Chip, Korrelation mit jedem Code, geteilt durch das, was
    Zufall gaebe. Ohne Marken (oder an falscher Lage) ist z normalverteilt um 0."""
    k = m["chip_cells"]
    gh, gw = sync.shape
    s = sig[pad:pad + gh * k, pad:pad + gw * k]
    s = np.pad(s, ((0, gh * k - s.shape[0]), (0, gw * k - s.shape[1])))
    proj = s.reshape(gh, k, gw, k).mean((1, 3))
    z = {}
    for n in codes:
        code = pattern(m, n, grid)[1]
        sel = code != 0
        z[n] = float((proj[sel] * code[sel]).sum() / (np.sqrt((proj[sel] ** 2).sum()) + 1e-12))
    return z


def _fit(f, H):
    """Punktpaare (Plakat → entzerrt) ueber das alte H ins Foto, neue Homographie per RANSAC. (H, Anzahl passender)."""
    import cv2
    src = np.array([a for a, _, _ in f], np.float64)
    dst = cv2.perspectiveTransform(np.array([b for _, b, _ in f], np.float64)[None], H)[0]
    H2, inl = cv2.findHomography(src, dst, cv2.RANSAC, RANSAC_PX)
    return (None, 0) if H2 is None else (H2, int(inl.sum()))


def detect(photo, cfg, codes=None):
    """Foto (RGB uint8) → dict(n, H, z, z2, fields) oder dict(error=...). H: Zellen des Plakats → Fotopixel.
    Grob aus dem QR (coarse), dann das Sync-Muster in allen Feldern suchen (search_cells), neu einpassen, noch einmal
    mit kleiner Suche (FINE_SEARCH_CELLS), dann die Nummer aus dem Code, zuletzt Feinschliff am Render (polish).
    H_marks: die Lage nur aus den Marken (fuer den Bericht)."""
    m = check(cfg)
    grid = (KL.S.SIZES[KL.PREVIEW][1] // KL.PREVIEW_CELL_PX, KL.S.SIZES[KL.PREVIEW][0] // KL.PREVIEW_CELL_PX)
    codes = codes or range(1, KL.posters(cfg) + 1)
    sync, _ = pattern(m, 0, grid)
    cands = coarse(photo)
    if not cands:
        return dict(error="kein QR gefunden (grobe Lage fehlt)")
    pad = m["search_cells"] + 1
    for H in cands:                                           # mehrere nur, wenn die QR-Drehung unklar ist
        for search in (m["search_cells"], FINE_SEARCH_CELLS):
            f = fields(signal(rectify(photo, H, grid, pad)), m, sync, grid, pad, search)
            H2, inl = _fit(f, H) if len(f) >= MIN_FIELDS else (None, len(f))
            if H2 is None or inl < MIN_FIELDS:
                break
            H = H2
        if inl >= MIN_FIELDS:
            break
    if inl < MIN_FIELDS:
        return dict(error=f"nur {inl} Felder mit Sync auf einer Ebene (>= {MIN_FIELDS} noetig): keine Marken?",
                    fields=inl)
    z = decode(signal(rectify(photo, H, grid, pad)), m, sync, grid, pad, codes)
    best = sorted(z, key=z.get)[::-1]
    if z[best[0]] < CODE_Z_MIN:
        return dict(error=f"Code zu schwach (z {z[best[0]]:.1f} < {CODE_Z_MIN})", fields=inl, H=H)
    H_marks = H
    H, cc, took = polish(photo, H, KL.frame(cfg, best[0] - 1)) if inl < POLISH_BELOW_FIELDS else (H, 0.0, False)
    return dict(n=best[0], z=z[best[0]], z2=z[best[1]], H=H, H_marks=H_marks, fields=inl, polish_cc=cc, polished=took)


def load_photo(path):
    """Foto lesen, Handy-Drehung (EXIF) anwenden."""
    return np.asarray(ImageOps.exif_transpose(Image.open(path)).convert("RGB"))


def aligned(photo, H, cfg):
    """Entzerrtes Bild in Plattengroesse (kickoff_loop_video.plate_size): Plakat mittig in Vorschaugroesse (4 px pro
    Zelle), genau dort, wo photo_plate es erwartet, drumherum die Wand aus dem Foto."""
    import cv2
    import kickoff_loop_video as V
    pw, ph = KL.S.SIZES[KL.PREVIEW][:2]
    PW, PH = V.plate_size(cfg, np.zeros((ph, pw, 3), np.uint8))
    x0, y0 = (PW - pw) // 2, (PH - ph) // 2
    q = KL.PREVIEW_CELL_PX
    A = np.array([[1 / q, 0, (0.5 - x0) / q], [0, 1 / q, (0.5 - y0) / q], [0, 0, 1]])
    return cv2.warpPerspective(photo, H @ A, (PW, PH), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                               borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------- Simulation + Selbsttest

def simulate(print_img, px, rng):
    """Handyfoto eines gedruckten Plakats (print_img mit px pro Zelle) → (JPEG-Bytes, H_wahr Zellen → Fotopixel)."""
    import cv2
    gh, gw = print_img.shape[0] // px, print_img.shape[1] // px
    src = cv2.resize(print_img, (gw * SIM_SRC_PX, gh * SIM_SRC_PX), interpolation=cv2.INTER_AREA)
    src = (printed(_to_lin(src)) * PRINT_PAPER).astype(np.float32)   # Reflexion; die Kamera belichtet selbst
    W, Hh = PHOTO_WH
    yaw, pitch = np.radians(rng.uniform(-SIM_TILT_DEG, SIM_TILT_DEG, 2))
    roll = np.radians(rng.uniform(-SIM_ROLL_DEG, SIM_ROLL_DEG))
    Ry = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)], [0, np.sin(pitch), np.cos(pitch)]])
    Rz = np.array([[np.cos(roll), -np.sin(roll), 0], [np.sin(roll), np.cos(roll), 0], [0, 0, 1]])
    corners = np.array([[0, 0], [gw, 0], [gw, gh], [0, gh]], np.float64)
    plane = np.c_[corners - [gw / 2, gh / 2], np.zeros(4)] @ (Rz @ Rx @ Ry).T
    Z = PHOTO_F_PX * gh / (rng.uniform(*SIM_HEIGHT_FRAC) * Hh)
    ctr = np.array([W / 2, Hh / 2]) * (1 + rng.uniform(-SIM_SHIFT_FRAC, SIM_SHIFT_FRAC, 2) * 2)
    proj = PHOTO_F_PX * plane[:, :2] / (Z + plane[:, 2:]) + ctr
    Ht = cv2.getPerspectiveTransform(corners.astype(np.float32), proj.astype(np.float32)).astype(np.float64)
    T = np.array([[SIM_SRC_PX, 0, -0.5], [0, SIM_SRC_PX, -0.5], [0, 0, 1]])   # Zelle → Quellpixel
    scale = np.sqrt(abs(np.linalg.det(Ht[:2, :2]))) / SIM_SRC_PX            # Fotopixel pro Quellpixel (grob)
    src = cv2.GaussianBlur(src, (0, 0), max(0.4 / scale - 0.3, 0.01))       # gegen Aliasing beim Verkleinern
    low = rng.random((6, 8, 3)) * rng.uniform(0.1, 0.6)                     # Wand: weicher Farbverlauf + Aushaenge
    wall = cv2.resize(low, (W, Hh), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    for _ in range(rng.integers(3, 8)):
        x, y, w, h = rng.integers(0, W), rng.integers(0, Hh), rng.integers(150, 700), rng.integers(200, 900)
        wall[y:y + h, x:x + w] = rng.random(3) * 0.8
    img = cv2.warpPerspective(src, Ht @ np.linalg.inv(T), (W, Hh), flags=cv2.INTER_LINEAR, dst=wall,
                              borderMode=cv2.BORDER_TRANSPARENT)
    img = img * (1 + rng.uniform(-SIM_WB, SIM_WB, 3)) * rng.uniform(*SIM_EXPOSURE)
    img = cv2.GaussianBlur(img, (0, 0), rng.uniform(*SIM_BLUR_PX))
    L, ang = rng.uniform(*SIM_SHAKE_PX), rng.uniform(0, np.pi)
    if L >= 1:
        k = np.zeros((int(L) | 1, int(L) | 1), np.float32)
        c = k.shape[0] // 2
        cv2.line(k, (round(c - c * np.cos(ang)), round(c - c * np.sin(ang))),
                 (round(c + c * np.cos(ang)), round(c + c * np.sin(ang))), 1.0, 1)
        img = cv2.filter2D(img, -1, k / k.sum())
    img = _from_lin(img).astype(np.float32)
    img += rng.standard_normal(img.shape, dtype=np.float32) * np.float32(rng.uniform(*SIM_NOISE))
    ycc = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2YCrCb)
    ycc[..., 1:] = cv2.GaussianBlur(ycc[..., 1:], (0, 0), SIM_CHROMA_NR_PX)
    buf = io.BytesIO()
    Image.fromarray(cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB)).save(buf, "JPEG", quality=SIM_JPEG_Q)
    return buf.getvalue(), Ht


def corner_error(H, Ht, grid):
    """Groesster Eckabstand im Foto / Plakatbreite im Foto (Mittel aus Ober- und Unterkante)."""
    import cv2
    c = np.array([[[0, 0], [grid[1], 0], [grid[1], grid[0]], [0, grid[0]]]], np.float64)
    a, b = cv2.perspectiveTransform(c, H)[0], cv2.perspectiveTransform(c, Ht)[0]
    width = (np.linalg.norm(b[1] - b[0]) + np.linalg.norm(b[2] - b[3])) / 2
    return float(np.linalg.norm(a - b, axis=1).max() / width)


def visibility(plain, marked, px, view_m, seen=True):
    """Abweichung nach dem Augenfilter (deltaE OK) je Zelle: (Mittel, 99.9 %, Maximum) ueber das ganze Plakat.
    seen: wie der Ausdruck aussieht (printed), sonst Bildschirm-Farben."""
    o = px // 2
    f = (lambda x: _seen(_to_lin(x))) if seen else KL.to_oklab
    a, b = f(plain[o::px, o::px]), f(marked[o::px, o::px])
    d = np.linalg.norm(eye(b, cells_per_deg(view_m)) - eye(a, cells_per_deg(view_m)), axis=2)
    return float(d.mean()), float(np.percentile(d, 99.9)), float(d.max())


def _test_job(args):
    """Ein Frame: Druckbild (+ Marken mit Nummer code, 0 = ohne) → simuliertes Foto → Erkennung (+ align beim
    richtigen Code: entzerrtes Plakat gegen den Render)."""
    cfg, i, code = args
    m = check(cfg)
    plain = KL.frame(cfg, i, KL.PRINT)
    img = embed(plain, code, m, KL.PRINT_CELL_PX) if code else plain
    jpg, Ht = simulate(img, KL.PRINT_CELL_PX, np.random.default_rng([i, code]))
    photo = np.asarray(Image.open(io.BytesIO(jpg)).convert("RGB"))
    t = time.time()
    r = detect(photo, cfg)
    r["s"] = time.time() - t
    grid = (plain.shape[0] // KL.PRINT_CELL_PX, plain.shape[1] // KL.PRINT_CELL_PX)
    H = r.pop("H", None)
    r["err"] = np.inf if H is None else corner_error(H, Ht, grid)
    r["err_marks"] = corner_error(r.pop("H_marks"), Ht, grid) if "H_marks" in r else np.inf
    if code == i + 1:
        r["vis"] = [visibility(plain, img, KL.PRINT_CELL_PX, d, seen) for d in (m["view_m"], CLOSE_M)
                    for seen in (True, False)]
        r["qr"] = bool(KL.K.check_qr(img, KL.PRINT_CELL_PX))
        r["ncc"] = align_ncc(photo, H, cfg, KL.frame(cfg, i)) if H is not None else 0.0
        if i == 0:
            os.makedirs(OUT, exist_ok=True)
            open(os.path.join(OUT, "photo_01.jpg"), "wb").write(jpg)
            if H is not None:
                Image.fromarray(aligned(photo, H, cfg)).save(os.path.join(OUT, "aligned_01.png"))
    return i, code, r


def align_ncc(photo, H, cfg, poster):
    """Pruefung von aligned(): das entzerrte Plakat (Mitte der Platte) gegen den Vorschau-Render, normierte
    Korrelation der Graubilder nach ALIGN_BLUR_PX (Foto-Unschaerfe). Ein halbes Pixel Versatz im Koordinatensystem
    kostet hier sichtbar (Befund: 0.5 Zellen → < 0.8)."""
    import cv2
    out = aligned(photo, H, cfg)
    ph, pw = poster.shape[:2]
    y0, x0 = (out.shape[0] - ph) // 2, (out.shape[1] - pw) // 2
    g = [cv2.GaussianBlur(cv2.cvtColor(x, cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), ALIGN_BLUR_PX)
         for x in (out[y0:y0 + ph, x0:x0 + pw], poster)]
    a, b = (x - x.mean() for x in g)
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))


def compare(cfg, frames, out):
    """Vergleichsbild je Frame eine Zeile: Plakat ohne | mit Marken (1/6), Ausschnitt 400 % ohne | mit | Differenz x10
    (Druckpixel, 1 Zelle = 12 px; ein Chip = 24 px, im Ausschnitt 96 px)."""
    m = check(cfg)
    rows = []
    for i in frames:
        a = KL.frame(cfg, i, KL.PRINT)
        b = embed(a, i + 1, m, KL.PRINT_CELL_PX)
        d = np.clip(128 + (b.astype(np.int16) - a.astype(np.int16)) * 10, 0, 255).astype(np.uint8)
        y, x = (np.array(a.shape[:2]) * COMPARE_AT_FRAC).astype(int)
        h, w = COMPARE_CROP_PX
        thumbs = [Image.fromarray(v).resize((v.shape[1] // 6, v.shape[0] // 6), Image.BOX) for v in (a, b)]
        crops = [Image.fromarray(v[y:y + h, x:x + w]).resize((w * 4, h * 4), Image.NEAREST) for v in (a, b, d)]
        rows.append(thumbs + crops)
    W = sum(t.width for t in rows[0]) + 20 * len(rows[0])
    Hh = max(t.height for t in rows[0]) + 20
    canvas = Image.new("RGB", (W, Hh * len(rows)), (40, 40, 40))
    for k, row in enumerate(rows):
        x = 0
        for t in row:
            canvas.paste(t, (x, k * Hh))
            x += t.width + 20
    canvas.save(out)
    return out


def selftest(cfg, frames=None):
    """Alle Frames: Druckbild mit Marken → simuliertes Handyfoto → detect/align. Gates: 100 % richtige Nummer,
    Eckfehler < 0.5 % der Plakatbreite, Sichtbarkeit nach dem Augenfilter aus view_m unter JND (auf dem Ausdruck und
    am Bildschirm), QR im markierten Druck lesbar, align legt das Plakat auf den Render. Gegenproben: ohne Marken muss
    die Erkennung scheitern, mit falscher Nummer muss das Nummern-Gate anschlagen."""
    from multiprocessing import Pool
    m = check(cfg)
    n = KL.posters(cfg)
    frames = frames or list(range(n))
    neg = frames[::max(1, len(frames) // NEG_FRAMES)][:NEG_FRAMES]
    jobs = [(cfg, i, i + 1) for i in frames] + [(cfg, i, 0) for i in neg] + [(cfg, i, (i + 7) % n + 1) for i in neg]
    t0 = time.time()
    with Pool(min(TEST_WORKERS, os.cpu_count()), initializer=KL._worker_init) as pool:
        res = pool.map(_test_job, jobs, chunksize=1)
    pos = [(i, r) for i, c, r in res if c == i + 1]
    none = [r for i, c, r in res if c == 0]
    wrong = [(i, c, r) for i, c, r in res if c and c != i + 1]
    right = [r.get("n") == i + 1 for i, r in pos]
    errs = np.array([r["err"] for _, r in pos])
    errs_m = np.array([r["err_marks"] for _, r in pos])
    vis = np.array([r["vis"] for _, r in pos])            # Frame x (1 m Druck, 1 m Schirm, nah Druck, nah Schirm) x 3
    caught = sum(r.get("n") != i + 1 for i, c, r in wrong)
    gates = {
        "Nummer richtig": (all(right), f"{sum(right)}/{len(right)}"),
        "Eckfehler < 0.5 % der Plakatbreite": (errs.max() < CORNER_GATE_FRAC,
                                               f"max {100 * errs.max():.3f} %, Mittel {100 * errs.mean():.3f} %"),
        f"Sichtbarkeit aus {m['view_m']} m < JND {JND_OK} (deltaE OK)": (
            vis[:, :2, 2].max() < JND_OK, f"Ausdruck Mittel {vis[:, 0, 0].mean():.4f} max {vis[:, 0, 2].max():.4f}, "
                                          f"Bildschirm Mittel {vis[:, 1, 0].mean():.4f} max {vis[:, 1, 2].max():.4f}"),
        "QR lesbar im Druck mit Marken": (all(r["qr"] for _, r in pos), f"{sum(r['qr'] for _, r in pos)}/{len(pos)}"),
        f"align legt das Plakat auf den Render (Korrelation >= {ALIGN_NCC_MIN})": (
            min(r["ncc"] for _, r in pos) >= ALIGN_NCC_MIN, f"min {min(r['ncc'] for _, r in pos):.3f}"),
        "Gegenprobe ohne Marken scheitert": (all("n" not in r for r in none),
                                             f"{sum('n' not in r for r in none)}/{len(none)} abgelehnt"),
        "Gegenprobe falsche Nummer faellt auf": (caught == len(wrong), f"Nummern-Gate schlaegt {caught}/{len(wrong)} an "
                                                 f"({sum(r.get('n') == c for i, c, r in wrong)} lesen die falsche Nummer)"),
    }
    g1, g2 = eye_gain(m["chip_cells"], m["view_m"]), eye_gain(m["chip_cells"], CLOSE_M)
    lines = [f"Druckmarken Selbsttest: {len(frames)} Frames + {2 * len(neg)} Gegenproben, {time.time() - t0:.0f} s",
             f"[marks] {m}",
             f"Augenfilter laesst vom Muster durch (L, a, b): {m['view_m']} m {np.round(g1, 2).tolist()}, "
             f"{CLOSE_M} m {np.round(g2, 2).tolist()}", ""]
    lines += [f"{'ok  ' if g else 'NEIN'} {k}: {v}" for k, (g, v) in gates.items()]
    lines += ["",
              f"Info aus {CLOSE_M} m (kein Gate): Ausdruck Mittel {vis[:, 2, 0].mean():.4f} max {vis[:, 2, 2].max():.4f}, "
              f"Bildschirm Mittel {vis[:, 3, 0].mean():.4f} max {vis[:, 3, 2].max():.4f}",
              f"Info: z der Nummer min {min(r.get('z', 0) for _, r in pos):.1f} (Gate {CODE_Z_MIN}), naechster Code "
              f"max {max(r.get('z2', 0) for _, r in pos):.1f}; Felder min {min(r.get('fields', 0) for _, r in pos)}; "
              f"Erkennung {np.mean([r['s'] for _, r in pos]):.1f} s/Foto",
              f"Info: Eckfehler nur aus den Marken (ohne polish): max {100 * errs_m.max():.3f} %, Mittel "
              f"{100 * errs_m.mean():.3f} %; polish uebernommen {sum(r.get('polished', 0) for _, r in pos)}/{len(pos)}",
              f"Info ohne Marken: {sorted(set(r['error'].split(':')[0] for r in none if 'error' in r))}", "",
              "Frame Nummer     z  Felder  Eckfehler% (Marken)  Sicht 1 m Druck/Schirm  align  QR"]
    for i, r in pos:
        lines.append(f"{i + 1:5d} {str(r.get('n', '-')):>6} {r.get('z', 0):5.1f} {r.get('fields', 0):7d} "
                     f"{100 * r['err']:11.3f} ({100 * r['err_marks']:6.3f})  "
                     f"{r['vis'][0][2]:.4f}/{r['vis'][1][2]:.4f}         {r['ncc']:.3f}  "
                     f"{'ja' if r['qr'] else 'NEIN'}" + ("" if r.get("n") == i + 1 else f"  ! {r.get('error')}"))
    os.makedirs(OUT, exist_ok=True)
    rep = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "report.txt"), "w").write(rep)
    compare(cfg, [i for i in COMPARE_FRAMES if i < n], os.path.join(OUT, "compare.png"))
    bad = [k for k, (g, _) in gates.items() if not g]
    return rep + (f"\nNICHT bestanden: {bad}" if bad else "\nSelbsttest Druckmarken ok") + \
        f"\n→ {OUT}/report.txt, compare.png, photo_01.jpg, aligned_01.png", not bad


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    cfg = KL.load()
    check(cfg)
    if cmd == "test":
        rep, ok = selftest(cfg, [int(a) - 1 for a in args[1:]] or None)
        print(rep)
        sys.exit(0 if ok else 1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
