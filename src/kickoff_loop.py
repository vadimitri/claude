#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless"]
# ///
"""SPARK Kick-off Loop: die Plakatserie ist ein Stop-Motion-Loop. Jedes Plakat = ein Frame.

Alle Gestaltungswerte stehen kommentiert in kickoff_loop/loop.toml, hier steht nur Logik.
Handbuch (Vision, Entscheidungen, Status, offene Fragen): kickoff_loop/CLAUDE.md.

  uv run src/kickoff_loop.py preview        Vorschau-Video + Kontaktbogen + Checks  → kickoff_loop/previz/vNNN/
  uv run src/kickoff_loop.py variants [N]   Detailvarianten von Plakat N nebeneinander → kickoff_loop/previz/variants/
  uv run src/kickoff_loop.py frames         nur die Plakat-Frames rendern (fuellt den Cache)

Aufbau dieser Datei (von oben nach unten):
  Konfiguration   load()                    loop.toml lesen und pruefen
  Geometrie       star_at()                 Frame-Nummer → Lage des Sterns (Silhouette, fuer alle Stile gleich)
  Plakatsatz      type_layers(), qr_card()  Schrift und QR des Loop-Plakats (ersetzt kickoff.type_layers)
  Rendern         frame(), frames()         ein Plakat / alle Plakate als Bild, mit Cache und QR-Check
  Varianten       variants()                Details zum Abstimmen nebeneinander
Video, Simulation, Blitz-Check und Temp-Ton stehen in kickoff_loop_video.py.
"""
import glob
import hashlib
import json
import os
import sys
import tomllib
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import label

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
    frames = cfg["posters"]["frames"]
    bad = [f"{p} {s}" for p, s in frames if p not in P_CODES or s not in S_CODES]
    assert not bad, f"[posters].frames: unbekannte Codes {bad}. P (ohne Lila): {sorted(P_CODES)}, S: {sorted(S_CODES)}"
    assert cfg["spark"]["growth"] in [*EASE, "pulse"], f"[spark].growth: {[*EASE, 'pulse']}"
    assert cfg["video"]["zoom_curve"] in EASE, f"[video].zoom_curve: {list(EASE)}"
    assert cfg["qr"]["style"] in ("card", "band"), "[qr].style: card | band"
    bar = frames_per_bar(cfg)
    assert bar == int(bar), "[loop].bpm und [video].timeline_fps: ein Takt muss ganze Timeline-Frames lang sein"
    bad = [per for per, _ in cfg["video"]["cadence"] if int(bar) % per]
    assert not bad, f"[video].cadence: {bad} Wechsel pro Takt passen nicht auf {int(bar)} Timeline-Frames pro Takt"
    assert cfg["video"]["hold_bars"] < sum(b for _, b in cfg["video"]["cadence"]), "[video].hold_bars laenger als cadence"
    return cfg


def frames_per_bar(cfg):
    """Timeline-Frames pro 4/4-Takt (bei 120 BPM und 24 fps: 48)."""
    return cfg["video"]["timeline_fps"] * 60 / cfg["loop"]["bpm"] * 4


def count(cfg):
    return len(cfg["posters"]["frames"])


# ---------------------------------------------------------------- Geometrie

def star_at(cfg, i):
    """Lage des Sterns in Frame i: (x, y, Radius, Drehung) in Plakateinheiten (siehe Kopf von loop.toml).

    Drehung laeuft ueber i/n: Frame n waere Frame 0 um turn_deg weiter, bei 72° deckungsgleich → nahtlos.
    Wachstum laeuft ueber i/(n-1): der letzte Frame erreicht genau size_end, danach springt der Stern zurueck.
    pulse waechst bis zur Loop-Mitte und schrumpft wieder (Kosinus), dann gibt es keinen Sprung."""
    sp, n = cfg["spark"], count(cfg)
    if sp["growth"] == "pulse":
        g = 0.5 - 0.5 * np.cos(2 * np.pi * i / n)
    else:
        g = EASE[sp["growth"]](i / max(n - 1, 1))
    radius = sp["size_start"] + (sp["size_end"] - sp["size_start"]) * g
    rot = sp["rot_start_deg"] + sp["turn_deg"] * i / n
    x, y = sp["center"]
    return float(x), float(y), float(radius), float(rot)


def poster_style(cfg, i):
    """Stil-Dict fuer styles.render: Colorway + Stern aus der Liste, Lage aus star_at, Satz aus diesem Modul."""
    p, s = cfg["posters"]["frames"][i]
    x, y, radius, rot = star_at(cfg, i)
    st = K.st_code(p, s, "K1", star=(x, y, radius), rot=rot, seed=cfg["posters"]["seed"])   # star ersetzt die K-Lage
    st.update(type_fn=type_layers, loop=dict(i=i, n=count(cfg), type=cfg["type"], qr=cfg["qr"]))
    return st


# ---------------------------------------------------------------- Plakatsatz

def rect(shape, y0, x0, y1, x1):
    """Rechteck-Maske in Zellen, [y0, y1) x [x0, x1)."""
    m = np.zeros(shape, bool)
    m[max(y0, 0):y1, max(x0, 0):x1] = True
    return m


def line_gradient(c, base, cap, steps):
    """Wertfeld fuer eine Schriftzeile: unterste Pixelreihe = hellste Stufe minus `steps`, oberste = hellste Stufe.

    Gemessen wird an Grundlinie und Versalhoehe dieser einen Zeile, nicht ueber Zeilengrenzen hinweg (der alte
    Verlauf lief 1.4 Versalhoehen hoch und fing in der Zeile darueber unten wieder hell an). Die Mitten der ersten und
    letzten Pixelreihe liegen genau auf den Endstufen, deshalb sind beide Enden flaechig."""
    rel = np.clip((base - c.px / 2 - c.cy) / (cap - c.px), 0, 1)      # 0 = unterste Pixelreihe, 1 = oberste
    return 1 - steps / c.N * (1 - rel)


def flip_glyphs(c, mk, v):
    """Kleine Schrift kippt pro Buchstabe in die Grundfarbe (Mehrheit seiner Pixel liegt auf Hellem), nicht pro Pixel.
    So bleibt sie auch in Strahlen und Sternkanten lesbar. Gleiche Regel wie in kickoff.py."""
    base = S.background(c)
    for _, _, lv, _, _ in c.layers:
        base = np.where(np.isnan(lv), base, lv)
    bright = c.star_m | (base > 0.5)
    lab, n = label(mk)
    share = np.bincount(lab.ravel(), bright.ravel(), n + 1) / np.maximum(np.bincount(lab.ravel(), minlength=n + 1), 1)
    return np.where(share[lab] > 0.5, c.lvl(0), v)


def qr_card(c, q):
    """JOIN US + QR als ein Element, harte Kanten, keine Dither-Kante, kein Halo.

    card: Karte flaechig in der hellsten Stufe, Schrift und Module in der dunkelsten.
    band: QR-Platte hell, darueber ein Band in Plattenbreite in der dunkelsten Stufe, Schrift hell.
    Die Ruhezone des QR (3 Module rundum) bleibt in beiden Faellen frei. Ein schmaler Rand in Grundfarbe trennt das
    Element vom Stern; auf dem Grund selbst ist er unsichtbar."""
    L, px = c.L, c.px
    shape = (c.gh, c.gw)
    lum = c.pal @ LUMA
    hi, lo = c.lvl(int(lum.argmax())), c.lvl(int(lum.argmin()))
    n = L["qs"] // px                                             # Plattenkante in Zellen, inkl. Ruhezone
    top, left = round((L["qbot"] - L["qs"]) / px), round(L["m"] / px)
    pad, kl = q["label_pad_cells"], q["keyline_cells"]

    text = S.line_mask(K.COPY["cta"], "clash", L["capj"], top * px, left * px, px, shape)
    ys, xs = np.nonzero(text)
    dy = (top - pad - 1) - ys.max()                               # Unterkante der Schrift: pad Zellen ueber der Platte
    dx = left + (n - (xs.max() - xs.min() + 1)) // 2 - xs.min()   # waagerecht mittig ueber der Platte
    text = np.roll(text, (dy, dx), (0, 1))
    head = ys.min() + dy - pad                                    # Oberkante des Elements

    element = rect(shape, head, left, top + n, left + n)
    plate = rect(shape, top, left, top + n, left + n)
    c.add("qr", rect(shape, head - kl, left - kl, top + n + kl, left + n + kl) & ~element, c.lvl(0))
    if q["style"] == "card":
        c.add("qr", element, hi)
        ink = lo
    else:
        c.add("qr", element & ~plate, lo)
        c.add("qr", plate, hi)
        ink = hi
    quiet = (n - len(L["q"]) * MODULE_CELLS) // 2                 # Ruhezone in Zellen
    mods = np.zeros(shape, bool)
    mods[top + quiet:top + n - quiet, left + quiet:left + n - quiet] = S.up(L["q"], MODULE_CELLS)
    c.add("qr", mods, lo)
    c.add("cta", text, ink)


def text_lines(c):
    """Die grossen Schriftzeilen aus kickoff.layout: {"title": [(text, grundlinie, versalhoehe)], "date": [...]}.
    date = KICK-OFF und die Datumszeile (kickoff.COPY what/when/where)."""
    L = c.L
    return {"title": [(s, b, L["cap"]) for s, b in zip(L["title"], L["tb"])],
            "date": [(s, b, L["capd"]) for s, b in zip(L["sub"], L["sb"])]}


def line_masks(c, lines):
    return [S.line_mask(s, "clash", cap, b, c.L["m"], c.px, (c.gh, c.gw)) for s, b, cap in lines]


def type_layers(c):
    """Satz des Loop-Plakats. Raster und Groessen kommen aus kickoff.layout (identisch zu den Einzelplakaten);
    neu gegenueber kickoff.type_layers: Verlauf pro Zeile, Frame-Nummer statt Hex-Raetsel, QR als Karte."""
    L, px, lp = c.L, c.px, c.st["loop"]
    shape = (c.gh, c.gw)
    n0 = len(c.layers)
    qr_card(c, lp["qr"])

    steps = lp["type"]["text_gradient_steps"]
    for name, lines in text_lines(c).items():
        mk = np.zeros(shape, bool)
        v = np.zeros(shape, np.float32)
        for (s, b, cap), m in zip(lines, line_masks(c, lines)):
            v = np.where(m, line_gradient(c, b, cap, steps), v)
            mk |= m
        # Titel kippt pro Pixel (XOR mit dem Stern), die kleineren Zeilen pro Buchstabe
        c.add(name, mk, np.where(c.star_m, c.lvl(0), v) if name == "title" else flip_glyphs(c, mk, v))
        K._EXTRA[name] = mk

    def small(s, x, right=False):                 # Kleintext der Kopfzeile, DepartureMono
        return S.line_mask(s, "departure", L["sc"], L["meta"], x, px, shape, right)

    left = lp["type"]["meta_left"].format(i=lp["i"] + 1, n=lp["n"])
    mk = small(S.CODENAME[c.st["P"]], c.W - L["m"], True)
    if left:
        mk |= small(left, L["m"])
    c.add("meta", mk, flip_glyphs(c, mk, c.ink))
    K._EXTRA["type"] = np.maximum.reduce([a for _, a, *_ in c.layers[n0:]]) > 0   # fuer das Zweitlicht in kickoff.frame_of


# ---------------------------------------------------------------- Rendern

def _source_hash():
    """Aendert sich irgendein Quelltext in src/, sind alle gecachten Plakate ungueltig."""
    h = hashlib.sha1()
    for p in sorted(glob.glob(os.path.join(ROOT, "src", "*.py"))):
        h.update(open(p, "rb").read())
    return h.hexdigest()


def frame(cfg, i, fmt=PREVIEW, style=None):
    """Plakat i als RGB-Array. Cache-Schluessel = alles, was das Bild bestimmt: Stil, Lage, Satzwerte, Quelltext."""
    st = style or poster_style(cfg, i)
    lp = st["loop"]
    satz = f'{st["type_fn"].__module__}.{st["type_fn"].__qualname__}'        # alter oder neuer Plakatsatz
    key = json.dumps([fmt, st["P"], st["S"], st["star"], st["rot"], st["seed"], lp, satz, _source_hash()],
                     sort_keys=True, default=str)
    path = os.path.join(CACHE, f"{i + 1:02d}_{hashlib.sha1(key.encode()).hexdigest()[:12]}.png")
    if os.path.exists(path):
        return np.asarray(Image.open(path).convert("RGB"))
    img = K.frame_of(st, fmt)
    S.save(img, path)
    return img


def legibility(st, img):
    """Lesbarkeit von Titel und Datum, 0..1, gemessen mit kickoff.legible: wie sauber trennt eine Helligkeitsschwelle
    die Schrift von ihrer Umgebung (0.5 = Zufall → 0). Stufen wie bei den Einzelplakaten: kickoff.TIER."""
    c = S.Ctx(st, PREVIEW)
    for name, lines in text_lines(c).items():
        K._EXTRA[name] = np.logical_or.reduce(line_masks(c, lines))
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
    if over == "old":                                   # die Einzelplakate von heute: kickoff.type_layers
        st["type_fn"] = K.type_layers
    else:
        for path, val in over.items():                  # "qr.style" → st["loop"]["qr"]["style"]
            sec, key = path.split(".")
            st["loop"][sec] = {**st["loop"][sec], key: val}
    return name, frame(cfg, i, style=st)


VARIANTS = [
    ("heute", "old"),
    ("Karte · Verlauf 1.0", {"qr.style": "card", "type.text_gradient_steps": 1.0}),
    ("Karte · Verlauf 1.4", {"qr.style": "card", "type.text_gradient_steps": 1.4}),
    ("Band · Verlauf 1.0", {"qr.style": "band", "type.text_gradient_steps": 1.0}),
]


def variants(cfg, i):
    """Plakat i in allen VARIANTS nebeneinander: oben ganz (halbe Groesse), darunter der Titelblock in Vorschaugroesse
    (1 Zelle = 4 px) und die QR-Karte doppelt (1 Zelle = 8 px), damit man Verlauf und Kanten zaehlen kann."""
    with Pool() as pool:
        res = pool.map(_variant_job, [(cfg, i, n, o) for n, o in VARIANTS])
    h, w = res[0][1].shape[:2]
    title_box = (0, round(0.02 * h), w, round(0.34 * h))      # Kopfzeile bis Datum (Anteile der Plakatflaeche)
    card_box = (0, round(0.70 * h), w // 2, h)                # unteres linkes Viertel mit der QR-Karte
    gap, label_h = 24, 40
    font = S.font("DepartureMono-Regular.otf", 22)
    cols = []
    for name, img in res:
        im = Image.fromarray(img)
        card = im.crop(card_box)
        cols.append((name, [im.resize((w // 2, h // 2), Image.NEAREST), im.crop(title_box),
                            card.resize((card.width * 2, card.height * 2), Image.NEAREST)]))
    sheet_h = label_h + sum(p.height + gap for p in cols[0][1])
    sheet = Image.new("RGB", (len(cols) * (w + gap), sheet_h), (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    for k, (name, parts) in enumerate(cols):
        x, y = k * (w + gap), label_h
        d.text((x, 8), name, font=font, fill=(230, 230, 230))
        for part in parts:
            sheet.paste(part, (x, y))
            y += part.height + gap
    out = os.path.join(PROJECT, "previz", "variants", f"frame{i + 1:02d}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    return out


# ---------------------------------------------------------------- Selbsttest

def selftest(cfg, i=8):
    """Prueft am fertigen Bild (nicht am Code), was bei den alten Plakaten schiefging:
    Verlauf pro Zeile = oberste Pixelreihe nur hellste Stufe, unterste nur die Stufe darunter, dazwischen wird es von
    unten nach oben nie dunkler; Schrift auf dem Stern (gekippt) ist ausgenommen. Dazu: QR lesbar."""
    cfg = {**cfg, "type": {**cfg["type"], "text_gradient_steps": 1.0}}
    st = poster_style(cfg, i)
    img = frame(cfg, i, style=st)
    c = S.Ctx(st, PREVIEW)
    cells = img[PREVIEW_CELL_PX // 2::PREVIEW_CELL_PX, PREVIEW_CELL_PX // 2::PREVIEW_CELL_PX].astype(int)
    level = np.argmin(((cells[..., None, :] - c.pal.astype(int)[None, None]) ** 2).sum(-1), -1)
    top_level = c.N
    lines = [ln for group in text_lines(c).values() for ln in group]
    for (s, _, _), m in zip(lines, line_masks(c, lines)):
        m &= level != 0                                 # ohne gekippte Pixel
        rows = np.array([np.mean(level[y][m[y]]) for y in np.nonzero(m.any(1))[0]])
        assert rows[0] == top_level and rows[-1] == top_level - 1, f"{s}: Enden nicht flaechig {rows[0]:.2f} {rows[-1]:.2f}"
        period = len(S.bayer(4))                        # Bayer 4x4 fuellt Nachbarreihen verschieden: ueber 4 Reihen mitteln
        smooth = np.convolve(rows, np.ones(period) / period, "valid")
        assert np.all(np.diff(smooth) <= 0.05), f"{s}: Verlauf wird nach unten wieder heller {np.round(smooth, 2)}"
    assert K.check_qr(img, PREVIEW_CELL_PX), "QR nicht lesbar"
    return f"Selbsttest ok (Plakat {i + 1}: Verlauf pro Zeile, QR)"


# ---------------------------------------------------------------- Befehle

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "preview"
    cfg = load()
    if cmd == "frames":
        _, ok, leg = frames(cfg)
        print(f"{len(ok)} Plakate, QR lesbar: {sum(ok)}/{len(ok)}, Lesbarkeit: {' '.join(f'{x:.2f}' for x in leg)}")
    elif cmd == "test":
        print(selftest(cfg))
    elif cmd == "variants":
        print(variants(cfg, int(args[1]) - 1 if len(args) > 1 else 8))
    elif cmd == "preview":
        import kickoff_loop_video as V
        print(V.preview(cfg, *frames(cfg)))
    elif cmd == "gallery":                              # index.html neu, z. B. nach dem Loeschen einer Version
        import kickoff_loop_video as V
        V.gallery()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
