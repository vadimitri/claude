#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""SPARK Kick-off Loop: die Plakatserie ist ein Stop-Motion-Loop. Jedes Plakat = ein Frame.

Alle Gestaltungswerte stehen kommentiert in kickoff_loop/loop.toml, hier steht nur Logik.
Handbuch (Vision, Begriffe, Entscheidungen, Status, offene Fragen): kickoff_loop/CLAUDE.md.

  uv run src/kickoff_loop.py preview        Vorschau-Video + Kontaktbogen + Checks  → kickoff_loop/previz/vNNN/
  uv run src/kickoff_loop.py variants [N..] Detailvarianten der Frames N nebeneinander → kickoff_loop/previz/variants/
  uv run src/kickoff_loop.py frames         nur die Plakat-Frames rendern (fuellt den Cache)
  uv run src/kickoff_loop.py test           Selbsttest am fertigen Bild
  uv run src/kickoff_loop.py print          Druckdateien A3 300 dpi (PDF, verlustfrei) → kickoff_loop/print/
  uv run src/kickoff_loop.py resolve        Bausteine fuer den Schnitt (Platten, Digitalteil, Song, Zeitachse) → resolve/

Aufbau dieser Datei (von oben nach unten):
  Konfiguration   load()                    loop.toml lesen und pruefen
  Farbe           palette()                 Farbreise: Frame-Nummer → gemischte Palette (OKLab)
  Geometrie       star_at()                 Frame-Nummer → Lage des Sterns auf der Bumerang-Bahn
  Plakatsatz      layout(), type_layers()   Satz des Loop-Plakats, QR als Caption-Box (ersetzt kickoff.type_layers)
  Rendern         frame(), frames()         ein Plakat / alle Plakate als Bild, mit Cache und QR-Check
  Varianten       variants()                Details zum Abstimmen nebeneinander
Video, Endkarte, Musik (Song-Ausschnitt), Blitz-Check stehen in kickoff_loop_video.py.
"""
import colorsys
import glob
import hashlib
import json
import os
import sys
import tomllib
from multiprocessing import Pool
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, generate_binary_structure, label

import kickoff as K
import styles as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "kickoff_loop")
CONFIG = os.path.join(PROJECT, "loop.toml")
CACHE = os.path.join(PROJECT, "_cache")

# Vorschaugroesse aus kickoff.py: dasselbe Zellraster wie der A3-Druck (292 x 413 Zellen), aber 4 statt 12 px pro Zelle.
# Ein Vorschau-Plakat ist also pixelgenau der Druck, nur kleiner.
PREVIEW = "prev"
PREVIEW_CELL_PX = S.SIZES[PREVIEW][2] * S.BASE["R"]     # 1 * 4 = 4 px pro Zelle
POSTER_ASPECT = S.SIZES[PREVIEW][0] / S.SIZES[PREVIEW][1]  # Breite / Hoehe (A3 = 1/sqrt 2)
MODULE_CELLS = 2                                        # ein QR-Modul = 2 Zellen (so setzt es kickoff.layout)
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)   # Rec. 709: Anteil von R, G, B an der Helligkeit

P_CODES = {code: val for code, val, _ in K.PAL}         # "P17" → "signal" (nur Kick-off-Colorways, kein Lila)
S_CODES = dict(K.SPARKS)                                # "S7" → "nest", Labor-Sterne "S13" → "lab:S13"

EASE = {"linear": lambda t: t,
        "ease_in": lambda t: t * t,
        "ease_out": lambda t: 1 - (1 - t) ** 2,
        "ease_in_out": lambda t: t * t * (3 - 2 * t)}


# ---------------------------------------------------------------- Konfiguration

def load(path=CONFIG):
    """loop.toml lesen und die Fehler abfangen, die sonst erst nach Minuten Rendern auffallen."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    n, col = cfg["loop"]["frames"], cfg["color"]
    bad = [p for p in col["stations"] if p not in P_CODES]
    assert not bad, f"[color].stations: unbekannte oder lila Codes {bad}. Erlaubt: {sorted(P_CODES)}"
    bad = [s for s in cfg["styles"]["cycle"] if s not in S_CODES]
    assert not bad, f"[styles].cycle: unbekannte Codes {bad}. Erlaubt: {sorted(S_CODES)}"
    assert n % len(col["stations"]) == 0, "[loop].frames muss durch die Anzahl [color].stations teilbar sein"
    assert (n // len(col["stations"])) % cfg["loop"]["key_every"] == 0, \
        "[color].stations: jede Station soll auf einem Aushang liegen (Abstand = Vielfaches von key_every)"
    lilac = [i + 1 for i in range(n) if is_lilac(palette_hex(cfg, i))]
    assert not lilac, f"[color].stations: Mischung wird lila auf Frame {lilac} (Rot direkt neben Blau?), Reihenfolge aendern"
    assert cfg["spark"]["spin_deg"] % 60 == 0, "[spark].spin_deg: Vielfaches von 60 (6-zackiger Stern), sonst ruckt der Loop"
    q = cfg["qr"]
    for key, ok in (("label", ("inside", "sticker")), ("label_fill", ("light", "dark")),
                    ("outline", ("solid", "checker")), ("shadow", ("solid", "checker"))):
        assert q[key] in ok, f"[qr].{key}: {' | '.join(ok)}"
    assert q["shadow_step"] in range(col["steps"]), f"[qr].shadow_step: Palettenstufe 0..{col['steps'] - 1}"
    cells = [q[k] for k in ("label_cap_cells", "label_pad_cells", "outline_cells", "corner_cells")]
    assert all(type(v) is int for v in cells + q["shadow_cells"] + q["sticker_offset_cells"]), \
        "[qr]: alle *_cells in ganzen Zellen, die Box liegt exakt auf dem Pixelraster"
    sp = cfg["spark"]
    assert sp["source"] in ("orbit", "resolve"), "[spark].source: orbit | resolve"
    if sp["source"] == "resolve":
        path = os.path.join(PROJECT, "star_path.json")
        assert os.path.exists(path), "[spark].source = resolve, aber star_path.json fehlt: uv run src/kickoff_loop_resolve.py pull"
        got = json.load(open(path))
        assert got["frames"] == n, f"star_path.json hat {got['frames']} Frames, [loop].frames = {n}: angleichen"
        sp["path"] = got["path"]
    m = cfg["music"]
    grid = os.path.join(PROJECT, m["grid"])
    assert os.path.exists(os.path.join(PROJECT, m["file"])) and os.path.exists(grid), \
        f"[music]: {m['file']} oder {m['grid']} fehlt (Song-Ausschnitt und Raster, siehe CLAUDE.md)"
    m["grid"] = json.load(open(grid))
    cfg["loop"]["bpm"] = m["grid"]["bpm"]
    bars = sum(b for _, b in cfg["video"]["cadence"])
    assert bars == m["switch_bar"], f"[video].cadence: {bars} Takte, [music].switch_bar will {m['switch_bar']}"
    assert m["switch_bar"] + cfg["endcard"]["bars"] < len(m["grid"]["downbeats_s"]), "[endcard].bars: Song zu kurz"
    bad = [per for per, _ in cfg["video"]["cadence"] if 16 % per]
    assert not bad, f"[video].cadence: {bad} Wechsel pro Takt gehen nicht in 16tel auf (1, 2, 4, 8, 16)"
    return cfg


def count(cfg):
    return cfg["loop"]["frames"]


def is_key(cfg, i):
    """Aushang (haengt auf dem Campus) oder Zwischenframe (nur fuers Video). Frame 1 ist immer ein Aushang."""
    return i % cfg["loop"]["key_every"] == 0


# ---------------------------------------------------------------- Farbe

_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])       # OKLab (Bjoern Ottosson 2020)


def to_oklab(rgb):
    a = np.asarray(rgb, np.float64) / 255
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return np.cbrt(lin @ _M1.T) @ _M2.T


def from_oklab(lab):
    lin = np.clip((lab @ np.linalg.inv(_M2).T) ** 3 @ np.linalg.inv(_M1).T, 0, 1)
    return np.round(np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055) * 255)


def station(p, steps):
    """Palette einer Station auf `steps` Stufen: kuerzere Paletten (CGA, 4 Stufen) werden gedoppelt, nicht gemischt,
    damit die reine Station genau so aussieht wie ihr Original."""
    pal = S.hexpal(P_CODES[p])
    return pal[np.round(np.arange(steps) * (len(pal) - 1) / (steps - 1)).astype(int)]


def palette_hex(cfg, i):
    """Palette von Frame i als Hex-Liste (dunkel → hell): zwischen zwei Stationen Stufe fuer Stufe linear in OKLab
    gemischt. OKLab statt RGB, weil gleiche Schritte dort gleich gross aussehen (kein Grau-Loch in der Mitte)."""
    col = cfg["color"]
    st = col["stations"]
    per = count(cfg) // len(st)
    k, t = divmod(i, per)
    a = to_oklab(station(st[k], col["steps"]))
    b = to_oklab(station(st[(k + 1) % len(st)], col["steps"]))
    rgb = from_oklab(a + (b - a) * t / per)
    return ["#%02X%02X%02X" % tuple(int(v) for v in c) for c in rgb]


def is_lilac(hexes):
    """Strenger als styles.lila (250-300°, s > 0.3): Mischungen streifen sonst Flieder (240-320°, s > 0.2), das liest
    sich auch als Lila. Lila gehoert der Maker Night."""
    for h in hexes:
        hh, s, v = colorsys.rgb_to_hsv(*[int(h[j:j + 2], 16) / 255 for j in (1, 3, 5)])
        if 240 <= hh * 360 < 320 and s > 0.2 and v > 0.2:
            return True
    return False


def palette(cfg, i):
    """Name der Palette von Frame i in styles.PALS. Wird in jedem Prozess neu eingetragen (macOS spawnt Worker)."""
    hexes = palette_hex(cfg, i)
    name = "loop:" + "".join(h[1:] for h in hexes)
    S.PALS[name] = hexes
    return name


def station_label(cfg, i):
    """Fuer Bogen und Report: "P11" auf einer Station, "P11>P13 50%" dazwischen."""
    st = cfg["color"]["stations"]
    per = count(cfg) // len(st)
    k, t = divmod(i, per)
    return st[k] if t == 0 else f"{st[k]}>{st[(k + 1) % len(st)]} {round(100 * t / per)}%"


# ---------------------------------------------------------------- Geometrie

def orbit(cfg, phase):
    """Stern auf der Bumerang-Bahn bei `phase` (Frames, darf gebrochen sein): (x, y, Radius, Drehung).

    Kreisbahn um den Betrachter, im Raum gerechnet: Winkel th laeuft ueber den sichtbaren Bogen (sweep_deg) gleichmaessig,
    Abstand z = near + depth*cos(th), Zentralprojektion auf das Plakat (x ~ sin(th)/z, Groesse ~ 1/z). Nahe am Betrachter
    ist er gross, tief und schnell, fern klein und nahe am Fluchtpunkt. Die Frame-Mitten liegen bei (i + 0.5)/n, damit
    der Schritt ueber den Neustart (hinter dem Kopf) so gross ist wie jeder andere. Der Stern bleibt immer frontal
    (Vadim 30.9.: keine Kippung), er dreht sich nur in der Bildebene (spin_deg)."""
    sp, n = cfg["spark"], count(cfg)
    a, b = sp["sweep_deg"]
    f = (phase + 0.5) / n
    w = sp["far_rush_frac"]                                   # fern schneller, nah verweilen (0 = gleichmaessiger Winkel)
    th = np.radians(a + (b - a) * (f - w * np.sin(2 * np.pi * f) / (2 * np.pi)))
    z = sp["near"] + sp["depth"] * np.cos(th)
    x = sp["vanish"][0] + sp["lens"] * np.sin(th) / z
    y = sp["vanish"][1] + sp["lens"] * POSTER_ASPECT * sp["height"] / z
    return float(x), float(y), float(sp["lens"] * sp["size"] / z), float(sp["rot_start_deg"] + sp["spin_deg"] * phase / n)


def star_at(cfg, i):
    """Lage des Sterns in Frame i: (x, y, Radius, Drehung). [spark].source = "resolve": von Vadim in Resolve
    gekeyframed (kickoff_loop_resolve.py pull → star_path.json), sonst die gerechnete Bahn (orbit)."""
    sp = cfg["spark"]
    return tuple(sp["path"][i]) if sp["source"] == "resolve" else orbit(cfg, i)


def style_code(cfg, i):
    sy = cfg["styles"]
    return sy["cycle"][(i // sy["hold_frames"]) % len(sy["cycle"])]


def poster_style(cfg, i):
    """Stil-Dict fuer styles.render: Palette aus der Farbreise, Stern-Stil aus dem Zyklus, Lage von der Bahn,
    Satz aus diesem Modul."""
    x, y, radius, rot = star_at(cfg, i)
    st = K.style(palette(cfg, i), S_CODES[style_code(cfg, i)], "riese", star=(x, y, radius), rot=rot,
                 seed=cfg["styles"]["seed"])
    st.update(layout=layout, type_fn=type_layers,
              loop=dict(i=i, n=count(cfg), type=cfg["type"], qr=cfg["qr"], digital=None))
    return st


# ---------------------------------------------------------------- Plakatsatz

def layout(c):
    """kickoff.layout plus x0 (linke Satzkante). Im Digitalteil (st["loop"]["digital"]) liegt das Plakat im 9:16-Bild:
    der Satz wird zwischen "Plakat, wie es im letzten Foto im Bild liegt" (u = 0) und "eigener 9:16-Satz" (u = 1)
    gemischt, Stern kommt fertig in Bildpixeln mit."""
    dg = c.st["loop"]["digital"]
    if not dg:
        L = K.layout(c)
        return dict(L, x0=L["m"])
    W, H = S.SIZES[PREVIEW][:2]
    poster = K.layout(SimpleNamespace(W=W, H=H, px=c.px, st=c.st))
    native = K.layout(c)
    ox, oy, u = dg["offset"][0], dg["offset"][1], dg["u"]
    snap = lambda v: round(v / c.px) * c.px                                   # noqa: E731
    mix = lambda a, b: snap(a + (b - a) * u)                                  # noqa: E731
    y = lambda k: mix(poster[k] + oy, native[k])                              # noqa: E731
    L = dict(native, x0=mix(poster["m"] + ox, native["m"]), meta=y("meta"), cap=mix(poster["cap"], native["cap"]),
             capd=mix(poster["capd"], native["capd"]), capj=mix(poster["capj"], native["capj"]), qbot=y("qbot"))
    L["tb"] = [mix(poster["tb"][0] + oy, native["tb"][0])]
    L["sb"] = [mix(a + oy, b) for a, b in zip(poster["sb"], native["sb"])]
    L["db"] = L["sb"][-1]
    L["star"] = dg["star"]
    return L


def rect(c, y0, x0, y1, x1, r=0):
    """Rechteck-Maske in Zellen, [y0, y1) x [x0, x1). r > 0: Ecken als Pixeltreppe (eine Zelle gehoert dazu, wenn ihre
    Mitte im Viertelkreis mit Radius r liegt). Nur ganze Zellen, keine Kantenglaettung."""
    cy, cx = c.yy + 0.5, c.xx + 0.5
    dy = np.maximum(np.maximum(y0 + r - cy, cy - (y1 - r)), 0)
    dx = np.maximum(np.maximum(x0 + r - cx, cx - (x1 - r)), 0)
    return (cy > y0) & (cy < y1) & (cx > x0) & (cx < x1) & (np.hypot(dx, dy) <= r)


def line_gradient(c, base, cap, steps):
    """Wertfeld fuer eine Schriftzeile: unterste Pixelreihe = hellste Stufe minus `steps`, oberste = hellste Stufe.

    Gemessen wird an Grundlinie und Versalhoehe dieser einen Zeile, nicht ueber Zeilengrenzen hinweg (der alte
    Verlauf lief 1.4 Versalhoehen hoch und fing in der Zeile darueber unten wieder hell an). Die Mitten der ersten und
    letzten Pixelreihe liegen genau auf den Endstufen, deshalb sind beide Enden flaechig."""
    rel = np.clip((base - c.px / 2 - c.cy) / (cap - c.px), 0, 1)      # 0 = unterste Pixelreihe, 1 = oberste
    return 1 - steps / c.N * (1 - rel)


def under(c):
    """Was bisher unter jeder Zelle liegt (Grund + alle Ebenen), Wertraum 0..1."""
    base = S.background(c)
    for _, _, lv, _, _ in c.layers:
        base = np.where(np.isnan(lv), base, lv)
    return base


def flip_glyphs(c, mk, v):
    """Kleine Schrift kippt pro Buchstabe in die Grundfarbe (Mehrheit seiner Pixel liegt auf Hellem), nicht pro Pixel.
    So bleibt sie auch in Strahlen und Sternkanten lesbar. Gleiche Regel wie in kickoff.py."""
    bright = c.star_m | (under(c) > 0.5)
    lab, n = label(mk)
    share = np.bincount(lab.ravel(), bright.ravel(), n + 1) / np.maximum(np.bincount(lab.ravel(), minlength=n + 1), 1)
    return np.where(share[lab] > 0.5, c.lvl(0), v)


def qr_box(c, q):
    """JOIN US + QR als Comic-Caption-Box (Into the Spider-Verse): Ebenen [(name, Maske, Wert)] in Malreihenfolge, alles
    in ganzen Zellen und exakten Palettenstufen (kein Verlauf, kein Weichzeichnen, kein Dither-Auslauf).

    Karte in der hellsten Stufe, Rand (outline) und harter Schlagschatten (shadow) in der dunkelsten; auf dunklem Grund
    traegt die helle Flaeche, auf dem Stern trennt der dunkle Rand sie vom Stern. Die Karte umschliesst immer die ganze
    QR-Platte (Module + 3 Module Ruhezone aus kickoff.layout), Rand und Schatten liegen also nie in der Ruhezone.
    JOIN US hat eine feste Groesse in Zellen und waechst nicht mit dem Titel: eine harte Kante, die von Frame zu Frame
    um eine Zelle springt, saehe nach Fehler aus.
      inside   JOIN US in der Karte ueber dem QR, Abstand zu den Modulen = Ruhezone, darueber label_pad_cells
      sticker  JOIN US auf eigener Karte (label_fill hell oder dunkel), versetzt ueber der oberen Kante; sie endet samt
               Rand und Schatten ueber der Ruhezone"""
    L, px = c.L, c.px
    lum = c.pal @ LUMA
    hi, lo = c.lvl(int(lum.argmax())), c.lvl(int(lum.argmin()))
    n = L["qs"] // px                                             # Plattenkante in Zellen, inkl. Ruhezone
    quiet = (n - len(L["q"]) * MODULE_CELLS) // 2                 # Ruhezone in Zellen
    top, left = round((L["qbot"] - L["qs"]) / px), round(L["x0"] / px)
    mods = np.zeros((c.gh, c.gw), bool)
    mods[top + quiet:top + n - quiet, left + quiet:left + n - quiet] = S.up(L["q"], MODULE_CELLS)

    text = S.line_mask(K.COPY["cta"], "clash", q["label_cap_cells"] * px, top * px, left * px, px, (c.gh, c.gw))
    ys, xs = np.nonzero(text)
    th, tw = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
    pad, r, ink = q["label_pad_cells"], q["corner_cells"], lo
    if q["label"] == "inside":                                    # Schrift sitzt direkt auf der Platte (Ruhezone darunter)
        ty, tx = top - th, left + (n - tw) // 2
        cards = [(rect(c, ty - pad, left, top + n, left + n, r), hi)]
    else:
        ox, oy = q["sticker_offset_cells"]
        clear = q["outline_cells"] + max(q["shadow_cells"][1], 0)  # Rand + Schatten des Etiketts enden ueber der Platte
        ty, tx = top - clear - pad - th, left + ox + pad
        dark = q["label_fill"] == "dark"
        ink = hi if dark else lo
        cards = [(rect(c, ty - pad - oy, left, top + n, left + n, r), hi),
                 (rect(c, ty - pad, tx - pad, ty + th + pad, tx + tw + pad, r), lo if dark else hi)]
    text = np.roll(text, (ty - ys.min(), tx - xs.min()), (0, 1))

    grow = np.ones((3, 3), bool) if r == 0 else generate_binary_structure(2, 1)  # Treppe: Rand folgt diagonal, 1 Zelle
    checker = (c.yy + c.xx) % 2 == 0                              # 1-Bit-Grau: jede zweite Zelle
    out = []
    for card, fill in cards:
        rim = binary_dilation(card, grow, q["outline_cells"]) & ~card if q["outline_cells"] else card & False
        body = card | rim
        shadow = np.roll(body, q["shadow_cells"][::-1], (0, 1)) & ~body
        out += [("qr", shadow & (checker | (q["shadow"] == "solid")), c.lvl(q["shadow_step"])),
                ("qr", rim, np.where(checker | (q["outline"] == "solid"), lo, hi)),
                ("qr", card, fill)]
    return out + [("qr", mods, lo), ("cta", text, ink)]


def qr_embed(c, q):
    """JOIN US + QR auf das Plakat legen (Geometrie und Stufen: qr_box)."""
    for name, mask, v in qr_box(c, q):
        c.add(name, mask, v)


def text_lines(c):
    """Die grossen Schriftzeilen aus kickoff.layout: {"title": [(text, grundlinie, versalhoehe)], "date": [...]}.
    date = KICK-OFF und die Datumszeile (kickoff.COPY what/when/where)."""
    L = c.L
    return {"title": [(s, b, L["cap"]) for s, b in zip(L["title"], L["tb"])],
            "date": [(s, b, L["capd"]) for s, b in zip(L["sub"], L["sb"])]}


def line_masks(c, lines, centered=False):
    """Masken der Zeilen, linksbuendig an x0; centered: waagerecht auf die Bildmitte (Plakat- bzw. 9:16-Mitte, im
    Digitalteil liegt das Plakat mittig im Bild, die Mitte wandert also nicht)."""
    out = []
    for s, b, cap in lines:
        m = S.line_mask(s, "clash", cap, b, c.L["x0"], c.px, (c.gh, c.gw))
        if centered and m.any():
            xs = np.nonzero(m.any(0))[0]
            m = np.roll(m, round(c.gw / 2 - (xs[0] + xs[-1] + 1) / 2), 1)
        out.append(m)
    return out


def type_layers(c):
    """Satz des Loop-Plakats. Raster und Groessen aus kickoff.layout;
    neu gegenueber kickoff.type_layers: Verlauf pro Zeile, SPARK waagerecht zentriert, keine Kopfzeile, QR als Caption-Box."""
    L, px, lp = c.L, c.px, c.st["loop"]
    shape = (c.gh, c.gw)
    n0 = len(c.layers)
    show = (lp["digital"] or {}).get("show")                       # Endkarte: Elemente setzen nacheinander ein
    if show is None or "qr" in show:
        qr_embed(c, lp["qr"])

    steps = lp["type"]["text_gradient_steps"]
    for name, lines in text_lines(c).items():
        if show is not None and name not in show:
            continue
        mk = np.zeros(shape, bool)
        v = np.zeros(shape, np.float32)
        for (s, b, cap), m in zip(lines, line_masks(c, lines, centered=name == "title")):
            v = np.where(m, line_gradient(c, b, cap, steps), v)
            mk |= m
        # Titel kippt pro Pixel (XOR mit dem Stern), die kleineren Zeilen pro Buchstabe
        c.add(name, mk, np.where(c.star_m, c.lvl(0), v) if name == "title" else flip_glyphs(c, mk, v))
        K._EXTRA[name] = mk

    K._EXTRA["type"] = (np.maximum.reduce([a for _, a, *_ in c.layers[n0:]]) > 0 if len(c.layers) > n0
                        else np.zeros((c.H, c.W), bool))            # fuer das Zweitlicht in kickoff.frame_of


# ---------------------------------------------------------------- Rendern

def _source_hash():
    """Aendert sich irgendein Quelltext in src/, sind alle gecachten Plakate ungueltig."""
    h = hashlib.sha1()
    for p in sorted(glob.glob(os.path.join(ROOT, "src", "*.py"))):
        h.update(open(p, "rb").read())
    return h.hexdigest()


def render_cached(st, fmt, tag):
    """Bild zu einem Stil-Dict, gecacht nach allem, was es bestimmt (Stil, Lage, Satzwerte, Palette, Quelltext)."""
    key = json.dumps([fmt, st["P"], S.PALS[st["P"]], st["S"], st["star"], st["rot"], st.get("nest_phase"), st["seed"],
                      st["loop"], _source_hash()], sort_keys=True, default=str)
    path = os.path.join(CACHE, f"{tag}_{hashlib.sha1(key.encode()).hexdigest()[:12]}.png")
    if os.path.exists(path):
        return np.asarray(Image.open(path).convert("RGB"))
    img = K.frame_of(st, fmt)
    S.save(img, path)
    return img


def frame(cfg, i, fmt=PREVIEW, style=None):
    """Plakat i als RGB-Array."""
    return render_cached(style or poster_style(cfg, i), fmt, f"{i + 1:02d}")


def legibility(st, img, fmt=PREVIEW):
    """Lesbarkeit von Titel und Datum, 0..1, gemessen mit kickoff.legible: wie sauber trennt eine Helligkeitsschwelle
    die Schrift von ihrer Umgebung (0.5 = Zufall → 0). Stufen wie bei den Einzelplakaten: kickoff.TIER."""
    c = S.Ctx(st, fmt)
    for name, lines in text_lines(c).items():
        K._EXTRA[name] = np.logical_or.reduce(line_masks(c, lines, centered=name == "title"))
    return K.legible(img, PREVIEW_CELL_PX)


def _frame_job(args):
    cfg, i = args
    img = frame(cfg, i)
    return img, K.check_qr(img, PREVIEW_CELL_PX), legibility(poster_style(cfg, i), img)


def frames(cfg):
    """Alle Plakate (Vorschaugroesse), je Plakat QR lesbar ja/nein und Lesbarkeit 0..1. Parallel, gecacht in _cache/."""
    with Pool() as pool:
        out = pool.map(_frame_job, [(cfg, i) for i in range(count(cfg))])
    return [list(x) for x in zip(*out)]


# ---------------------------------------------------------------- Varianten zum Abstimmen

def _variant_job(args):
    cfg, i, name, over = args
    st = poster_style(cfg, i)
    for path, val in over.items():                      # "qr.label" → st["loop"]["qr"]["label"]
        sec, key = path.split(".")
        st["loop"][sec] = {**st["loop"][sec], key: val}
    img = frame(cfg, i, style=st)
    return name, img, K.check_qr(img, PREVIEW_CELL_PX)


# Box um JOIN US + QR (qr_box). Jede Variante nennt alle Box-Schluessel, damit sie unabhaengig vom Stand der loop.toml
# gleich aussieht; die Variante, die loop.toml gerade setzt, ist auf den Boegen markiert.
_CAPTION = {"qr.label": "inside", "qr.label_fill": "light", "qr.label_cap_cells": 9, "qr.label_pad_cells": 6,
            "qr.sticker_offset_cells": [-5, -6], "qr.outline_cells": 1, "qr.outline": "solid", "qr.shadow_cells": [2, 2],
            "qr.shadow": "solid", "qr.shadow_step": 0, "qr.corner_cells": 0}
VARIANTS = [
    ("A Caption", _CAPTION),
    ("B Pixeltreppe", {**_CAPTION, "qr.corner_cells": 5, "qr.outline_cells": 0, "qr.shadow_cells": [0, 0]}),
    ("C Rasterrand", {**_CAPTION, "qr.outline_cells": 2, "qr.outline": "checker", "qr.shadow_cells": [0, 0]}),
    ("D Sticker", {**_CAPTION, "qr.label": "sticker", "qr.label_pad_cells": 3, "qr.sticker_offset_cells": [-4, -8]}),
    ("D2 Etikett dunkel", {**_CAPTION, "qr.label": "sticker", "qr.label_fill": "dark", "qr.label_pad_cells": 3,
                           "qr.sticker_offset_cells": [3, -8]}),
    ("E1 Halbton-Schatten", {**_CAPTION, "qr.shadow_cells": [3, 3], "qr.shadow": "checker"}),
    ("E2 Farbversatz", {**_CAPTION, "qr.shadow_cells": [3, 3], "qr.shadow_step": 3}),
]


def _sheet(cols, path):
    """Spalten [(Ueberschrift, [(Beschriftung, Bild)])] nebeneinander auf dunklem Grund speichern."""
    gap, label_h = 24, 56
    font = S.font("DepartureMono-Regular.otf", 36)
    cw = max(im.width for _, parts in cols for _, im in parts)
    sheet_h = label_h + max(sum(im.height + gap + (label_h if cap else 0) for cap, im in parts) for _, parts in cols)
    sheet = Image.new("RGB", (len(cols) * (cw + gap), sheet_h), (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    for k, (name, parts) in enumerate(cols):
        x, y = k * (cw + gap), label_h
        d.text((x, 8), name, font=font, fill=(230, 230, 230))
        for cap, im in parts:
            if cap:
                d.text((x, y + 8), cap, font=font, fill=(150, 150, 160))
                y += label_h
            sheet.paste(im, (x, y))
            y += im.height + gap
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)
    return path


def variants(cfg, idx):
    """Frames idx in allen VARIANTS. Pro Frame ein Bogen previz/variants/frameNN.png: oben ganz (halbe Groesse), darunter
    der Titelblock in Vorschaugroesse (1 Zelle = 4 px) und das untere linke Viertel mit dem QR doppelt (1 Zelle = 8 px),
    damit man Kanten zaehlen kann. Dazu qr_box_sheet.png: JOIN US + QR aller Varianten (Spalten) auf allen Frames
    (Zeilen), doppelt, mit QR-Befund, zum Auswaehlen auf einen Blick."""
    with Pool() as pool:
        res = pool.map(_variant_job, [(cfg, i, n, o) for i in idx for n, o in VARIANTS])
    h, w = res[0][1].shape[:2]
    title_box = (0, round(0.02 * h), w, round(0.34 * h))      # Kopfzeile bis Datum (Anteile der Plakatflaeche)
    card_box = (0, round(0.70 * h), w // 2, h)                # unteres linkes Viertel mit dem QR
    qr_crop = (0, round(0.68 * h), round(0.36 * w), h)        # JOIN US + QR mit etwas Umgebung
    x2 = lambda im: im.resize((im.width * 2, im.height * 2), Image.NEAREST)  # noqa: E731
    mark = lambda name, over: name + (" = loop.toml" if all(                  # noqa: E731
        cfg[p.split(".")[0]][p.split(".")[1]] == v for p, v in over.items()) else "")
    names = [mark(n, o) for n, o in VARIANTS]
    out, grid = [], {n: [] for n in names}
    for k, i in enumerate(idx):
        cols = []
        for name, (_, img, ok) in zip(names, res[k * len(VARIANTS):(k + 1) * len(VARIANTS)]):
            im = Image.fromarray(img)
            cols.append((name + ("" if ok else "  QR!"), [(None, im.resize((w // 2, h // 2), Image.NEAREST)),
                                                         (None, im.crop(title_box)), (None, x2(im.crop(card_box)))]))
            grid[name].append((f"Frame {i + 1} {station_label(cfg, i)} {style_code(cfg, i)}  QR {'ok' if ok else 'NICHT lesbar'}",
                               x2(im.crop(qr_crop))))
        out.append(_sheet(cols, os.path.join(PROJECT, "previz", "variants", f"frame{i + 1:02d}.png")))
    out.append(_sheet(list(grid.items()), os.path.join(PROJECT, "previz", "variants", "qr_box_sheet.png")))
    return "\n".join(out)


# ---------------------------------------------------------------- Selbsttest

def selftest(cfg, i=8):
    """Prueft am fertigen Bild (nicht am Code), was schiefgehen kann:
    Verlauf pro Zeile = oberste Pixelreihe nur hellste Stufe, unterste nur die Stufe darunter, dazwischen wird es von
    unten nach oben nie dunkler; Schrift auf dem Stern (gekippt) ist ausgenommen. QR lesbar. Titelblock steht in jedem Frame gleich.
    Farbreise: keine Lila-Mischung, jede Station exakt ihre Original-Palette. SPARK waagerecht zentriert.
    QR-Box hart: jede Zelle, die qr_box belegt, hat im Bild genau ihre Palettenstufe und ist innen einfarbig (Raster,
    kein Auslauf, kein Dither; der alte weiche Hof faellt hier durch), rundum >= 3 Module hellste Stufe als Ruhezone."""
    cfg = {**cfg, "type": {**cfg["type"], "text_gradient_steps": 1.0}}
    st = poster_style(cfg, i)
    img = frame(cfg, i, style=st)
    c = S.Ctx(st, PREVIEW)
    cells = img[PREVIEW_CELL_PX // 2::PREVIEW_CELL_PX, PREVIEW_CELL_PX // 2::PREVIEW_CELL_PX].astype(int)
    level = np.argmin(((cells[..., None, :] - c.pal.astype(int)[None, None]) ** 2).sum(-1), -1)
    top_level = c.N
    groups = text_lines(c)
    lines = [ln for group in groups.values() for ln in group]
    masks = [m for name, group in groups.items() for m in line_masks(c, group, centered=name == "title")]
    title = masks[0]
    xs = np.nonzero(title.any(0))[0]
    assert abs((xs[0] + xs[-1] + 1) / 2 - c.gw / 2) <= 0.5, "SPARK nicht waagerecht zentriert"
    for (s, _, _), m in zip(lines, masks):
        m &= level != 0                                 # ohne gekippte Pixel
        rows = np.array([np.mean(level[y][m[y]]) for y in np.nonzero(m.any(1))[0]])
        assert rows[0] == top_level and rows[-1] == top_level - 1, f"{s}: Enden nicht flaechig {rows[0]:.2f} {rows[-1]:.2f}"
        period = len(S.bayer(4))                        # Bayer 4x4 fuellt Nachbarreihen verschieden: ueber 4 Reihen mitteln
        smooth = np.convolve(rows, np.ones(period) / period, "valid")
        assert np.all(np.diff(smooth) <= 0.05), f"{s}: Verlauf wird nach unten wieder heller {np.round(smooth, 2)}"
    assert K.check_qr(img, PREVIEW_CELL_PX), "QR nicht lesbar"
    box = qr_box(c, st["loop"]["qr"])
    want = np.full(level.shape, -1)
    for _, m, v in box:
        want[m] = np.rint(np.broadcast_to(v, m.shape)[m] * c.N)
    got = want >= 0
    bad = np.count_nonzero(level[got] != want[got])
    assert not bad, f"QR-Box: {bad} Zellen nicht in ihrer Stufe (weicher Rand, Dither oder falsche Farbe)"
    p = PREVIEW_CELL_PX
    blocks = img[:c.gh * p, :c.gw * p].reshape(c.gh, p, c.gw, p, 3)
    assert (blocks == blocks[:, :1, :, :1]).all((1, 3, 4))[got].all(), "QR-Box: Zellen nicht einfarbig (nicht auf dem Raster)"
    ys, xs = np.nonzero(box[-2][1])                     # Module
    q = 3 * MODULE_CELLS
    zone = level[ys.min() - q:ys.max() + q + 1, xs.min() - q:xs.max() + q + 1].copy()
    zone[q:-q, q:-q] = c.hi
    assert (zone == c.hi).all(), "QR-Ruhezone: weniger als 3 Module hellste Stufe um die Module"
    last = S.Ctx(poster_style(cfg, count(cfg) - 1), PREVIEW)
    same = [np.array_equal(a, b) for a, b in zip(masks, (m for name, group in text_lines(last).items()
                                                       for m in line_masks(last, group, centered=name == "title")))]
    assert all(same), "Titel/Datum stehen nicht in jedem Frame an derselben Stelle"
    per = count(cfg) // len(cfg["color"]["stations"])
    for k, p in enumerate(cfg["color"]["stations"]):
        got = np.array([[int(h[j:j + 2], 16) for j in (1, 3, 5)] for h in palette_hex(cfg, k * per)])
        assert np.abs(got - station(p, cfg["color"]["steps"])).max() <= 1, f"Station {p} weicht vom Original ab"
    assert is_lilac(["#A877A6"]) and not is_lilac(palette_hex(cfg, 0)), "Lila-Test erkennt Flieder nicht"
    return f"Selbsttest ok (Frame {i + 1}: Verlauf pro Zeile, QR, QR-Box + Ruhezone; Titel fix, Stationen, Lila-Test)"


# ---------------------------------------------------------------- Befehle

# ---------------------------------------------------------------- Druck

PRINT = "a3"
PRINT_CELL_PX = S.SIZES[PRINT][2] * S.BASE["R"]                 # 3 * 4 = 12 px pro Zelle = 1 mm bei 300 dpi
PRINT_DPI = 300                                                 # 3504 x 4956 px = 296.7 x 419.6 mm (A3: 297 x 420)
BACK_LINES = ("BITTE NICHT", "ABHÄNGEN")                     # Rueckseite jedes Aushangs (Vadim 30.9.)
BACK_WIDTH_FRAC = 0.8                                           # laengste Zeile / Seitenbreite


def _print_job(args):
    cfg, i = args
    img = frame(cfg, i, PRINT)
    return img, K.check_qr(img, PRINT_CELL_PX)


def back_page():
    """Rueckseite: schwarze Schrift auf Weiss (spart Toner, scheint nicht durch), zwei Zeilen mittig."""
    W, H = S.SIZES[PRINT][:2]
    name, var = S.FONTSPEC["clash"][:2]
    f0 = S.font(name, 100, var)
    wide = max(f0.getlength(t) for t in BACK_LINES)
    f = S.font(name, round(100 * BACK_WIDTH_FRAC * W / wide), var)
    im = Image.new("L", (W, H), 255)
    ImageDraw.Draw(im).multiline_text((W / 2, H / 2), "\n".join(BACK_LINES), font=f, fill=0, anchor="mm", align="center",
                                     spacing=round(0.3 * f.size))       # Luft fuer die Umlaut-Punkte
    return im


def print_files(cfg):
    """Druckdateien A3 hoch, 300 dpi, 12 px pro Zelle → kickoff_loop/print/. Aushaenge als aushang_NN.pdf mit
    Rueckseite (Duplex), Zwischenframes als foto_NN.pdf (einseitig, nur fuers Video). PDF per img2pdf: das PNG geht
    unveraendert hinein (kein JPEG, das Bayer-Korn bleibt exakt). Jeder QR wird in Druckaufloesung dekodiert."""
    import img2pdf
    out = os.path.join(PROJECT, "print")
    os.makedirs(out, exist_ok=True)
    n = count(cfg)
    with Pool() as pool:
        res = pool.map(_print_job, [(cfg, i) for i in range(n)])
    bad = [i + 1 for i, (_, ok) in enumerate(res) if not ok]
    back = os.path.join(out, "_rueckseite.png")
    back_page().save(back, dpi=(PRINT_DPI, PRINT_DPI))
    for i, (img, _) in enumerate(res):
        png = os.path.join(out, f"{i + 1:02d}.png")
        S.save(img, png, PRINT_DPI)
        pages = [png, back] if is_key(cfg, i) else [png]
        name = f"{'aushang' if is_key(cfg, i) else 'foto'}_{i + 1:02d}.pdf"
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(img2pdf.convert(pages, layout_fun=img2pdf.get_fixed_dpi_layout_fun((PRINT_DPI, PRINT_DPI))))
    keys = sum(is_key(cfg, i) for i in range(n))
    return (f"{n} Druckdateien in {out}: {keys} Aushaenge (mit Rueckseite), {n - keys} Fotoframes; "
            f"QR lesbar {n - len(bad)}/{n}" + (f"  ! NICHT lesbar: {bad}" if bad else ""))


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "preview"
    cfg = load()
    if cmd == "frames":
        _, ok, leg = frames(cfg)
        print(f"{len(ok)} Plakate, QR lesbar: {sum(ok)}/{len(ok)}, Lesbarkeit: {' '.join(f'{x:.2f}' for x in leg)}")
    elif cmd == "test":
        print(selftest(cfg))
    elif cmd == "print":
        print(print_files(cfg))
    elif cmd == "variants":
        print(variants(cfg, [int(a) - 1 for a in args[1:]] or [8]))
    elif cmd == "preview":
        import kickoff_loop_video as V
        print(V.preview(cfg, *frames(cfg)))
    elif cmd == "resolve":                              # Bausteine fuer Resolve → kickoff_loop/resolve/
        import kickoff_loop_video as V
        print(V.export(cfg, frames(cfg)[0]))
    elif cmd == "gallery":                              # index.html neu, z. B. nach dem Loeschen einer Version
        import kickoff_loop_video as V
        V.gallery()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
