#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""SPARK Kick-off Loop: die Plakatserie ist ein Stop-Motion-Loop. Jedes Plakat = ein Frame.

Alle Gestaltungswerte stehen kommentiert in kickoff_loop/loop.toml, hier steht nur Logik.
Handbuch (Vision, Begriffe, Entscheidungen, Status, offene Fragen): kickoff_loop/CLAUDE.md.

  uv run src/kickoff_loop.py sheet          schnelle Runde (~15 s): Kontaktbogen + Plakat-Loop → previz/now/, oeffnet beides
  uv run src/kickoff_loop.py sheet X.toml   dasselbe fuer eine Variante (Kopie der loop.toml) → previz/review/X_*
  uv run src/kickoff_loop.py boil           Test: Digitalteil ohne | mit Boil nebeneinander → previz/now/boil.mp4
  uv run src/kickoff_loop.py preview [A|B]  Vorschau-Video + Kontaktbogen + Checks  → kickoff_loop/previz/vNNN/
  uv run src/kickoff_loop.py variants [N..] Detailvarianten der Frames N nebeneinander → kickoff_loop/previz/variants/
  uv run src/kickoff_loop.py frames         nur die Plakat-Frames rendern (fuellt den Cache)
  uv run src/kickoff_loop.py stars [S..]     Sterne-Bogen: jeder Stil an 3 Stellen der Bahn → previz/variants/stars.png
  uv run src/kickoff_loop.py test [N..]     Selbsttest am fertigen Bild (Frames N, Standard 9 13 27)
  uv run src/kickoff_loop.py print          Druckdateien A3 300 dpi (PDF, verlustfrei) → kickoff_loop/print/
  uv run src/kickoff_loop.py resolve        Bausteine fuer den Schnitt (Platten, Digitalteil, Song, Zeitachse) → resolve/

Aufbau dieser Datei (von oben nach unten):
  Konfiguration   load()                    loop.toml lesen und pruefen
  Farbe           palette()                 Farbreise: Plakat-Nummer → Welt → gemischte Palette (OKLab)
  Geometrie       star_at()                 Frame-Nummer → Lage des Sterns auf der Bumerang-Bahn
  Plakatsatz      layout(), type_layers()   Satz des Loop-Plakats, QR glueht ein (qr_glow; ersetzt kickoff.type_layers)
  Rendern         frame(), frames()         ein Plakat / alle Plakate als Bild, mit Cache und QR-Check
  Boegen          variants(), stars()       QR-Varianten / Sternstile nebeneinander zum Auswaehlen
Video, Endkarte, Musik (Song-Ausschnitt), Blitz-Check stehen in kickoff_loop_video.py.
"""
import colorsys
import glob
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from multiprocessing import Pool
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, label

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
SUBDIV_PER_BAR = 48   # kleinstes gemeinsames Raster pro 4/4-Takt: 16tel (16) und 32tel-Triolen (48, T16)
GRID_KEYS = ("bpm_carousel", "bpm_end", "sixteenth_s", "carousel_bars", "hits_s", "downbeats_s", "burst_s", "impact_s",
             "end_s")   # was die Zeitachse aus dem Musik-Raster braucht (kickoff_loop_music.py schreibt es)
STAR_CLEAR = 1.6    # Selbsttest: ab diesem Vielfachen des Sternradius liegt kein Stern und kaum Schein mehr (background)
GLOW_LIGHT_E = 4    # QR-Gluehen "light": exp(-4) = 2 % am Ende von glow_cells, gleich wie gauss dort
GLOW_SIDE_TOL = 0.6  # Selbsttest: gleicher Abstand, andere Seite der Platte, hoechstens so viele Stufen Unterschied
                    # (Hintergrundverlauf ueber die Plattenhoehe ~0.2 Stufen, Bayer-Rest pro Ring ~0.2)
ELLIPSE_SAMPLES = 4001  # Stuetzstellen der Bahn fuer Zeit → Ort (Fehler < 0.1 % eines Frames bei 32 Frames)
OFF_STAR = (-3.0, -3.0, 0.002)  # leerer Frame: Stern (x, y, Radius) so weit draussen, dass auch kein Schein hereinreicht
BEHIND_Z = 0.02    # Bahn: Abstand (Bahnradius = 1), ab dem der Stern hinter/neben dem Kopf ist (Projektion 1/z explodiert)
GLOW_MIN = 0.02     # QR-Gluehen: darunter unsichtbar im 6-stufigen Bayer-Korn (1/5 Stufe Abstand, 16 Schwellen: ~0.01)

P_CODES = {code: val for code, val, _ in K.PAL}         # "P17" → "signal" (nur Kick-off-Colorways, kein Lila)
S_CODES = dict(K.SPARKS)                                # "S7" → "nest", Labor-Sterne "S13" → "lab:S13"

EASE = {"linear": lambda t: t,
        "ease_in": lambda t: t * t,
        "ease_out": lambda t: 1 - (1 - t) ** 2,
        "ease_in_out": lambda t: t * t * (3 - 2 * t)}


# ---------------------------------------------------------------- Konfiguration

def load(path=CONFIG, music=None):
    """loop.toml lesen und die Fehler abfangen, die sonst erst nach Minuten Rendern auffallen.
    music = "A" | "B": Mashup-Variante statt der in [music] eingetragenen (zum Vergleichen, ohne die toml zu aendern)."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    if os.path.abspath(path) != os.path.abspath(CONFIG):    # Review-TOML: fehlende Schluessel aus loop.toml (aeltere Kopien)
        with open(CONFIG, "rb") as f:
            for sec, vals in tomllib.load(f).items():
                for k, v in vals.items():
                    cfg.setdefault(sec, {}).setdefault(k, v)
    if music:
        cfg["music"].update(file=f"ref/audio/mashup_{music}.wav", grid=f"ref/audio/mashup_{music}.json")
    n, col = cfg["loop"]["frames"], cfg["color"]
    assert ("stations" in col) != ("worlds" in col), "[color]: entweder stations (eine Welt) oder worlds, nicht beides"
    if "stations" in col:                                  # eine Welt ueber den ganzen Loop (Stand bis 1.10.)
        col.update(worlds=[col["stations"]], world_frames=n)
    assert "world_frames" in col, "[color].worlds braucht world_frames (Frames pro Welt)"
    col.setdefault("mix", "oklab")                         # ohne Angabe: wie bis 1.10. (gerade Linie in OKLab)
    col.setdefault("chroma_boost_frac", 0.0)
    col.setdefault("split_level", None)
    assert col["mix"] in ("oklab", "rainbow", "cut"), "[color].mix: oklab | rainbow | cut (harte Spruenge, kein Mischen)"
    cut = col["mix"] == "cut"
    if col["mix"] == "rainbow":
        lo, hi = col.get("rainbow_avoid_hue_deg", (None, None))
        assert lo is not None and 0 <= lo < hi <= 360, \
            "[color].mix = rainbow braucht rainbow_avoid_hue_deg = [von, bis] (OKLCh-Farbton, den der Weg nicht kreuzt)"
    assert col["chroma_boost_frac"] >= 0, "[color].chroma_boost_frac: 0 = aus, 0.3 = Mitte der Mischung 30 % bunter"
    split = any("/" in p for st in col["worlds"] for p in st)
    assert not split or (type(col["split_level"]) is int and 0 < col["split_level"] < col["steps"]), \
        f"[color]: Split-Stationen (\"P11/P18\") brauchen split_level, ganze Stufe 1..{col['steps'] - 1}"
    wf, key = col["world_frames"], cfg["loop"]["key_every"]
    for w, st in enumerate(col["worlds"]):
        where = f"[color] Welt {w + 1} {st}"
        bad = [p for p in st if len(p.split("/")) > 2 or any(q.removeprefix("~") not in P_CODES for q in p.split("/"))]
        assert st and not bad, (f"{where}: unbekannte oder lila Codes {bad}. Erlaubt: {sorted(P_CODES)}, "
                                "Split-Tone als \"Grund/Licht\", z. B. \"P11/P18\", Negativ als \"~P11\"")
        bad = [p for p in st if len({is_paper(q) for q in p.split("/")}) > 1]
        assert not bad, f"{where}: Split {bad} kreuzt Papier mit Dunkel (Licht und Grund waeren gleich hell)"
        assert wf % len(st) == 0, f"{where}: {wf} Frames pro Welt nicht durch {len(st)} Stationen teilbar"
        assert cut or (wf // len(st)) % key == 0, (f"{where}: jede Station soll auf einem Aushang liegen, Abstand {wf // len(st)}"
                                            f" Frames ist kein Vielfaches von key_every {key}")
        mixed = {is_paper(p) for p in st}
        assert cut or len(mixed) == 1, (f"{where}: Papier ({[p for p in st if is_paper(p)]}) und dunkle Gruende in einer Welt "
                                 "werden auf dem Weg grau (Grund und Tinte gleich hell). Papier in eine eigene Welt")
    assert posters(cfg) % n == 0, (f"[color]: {len(col['worlds'])} Welten x {wf} Frames = {posters(cfg)} Plakate, kein "
                                   f"Vielfaches von [loop].frames {n}: Bahn und Stile sprangen am Neustart")
    seam = slice(col["split_level"] - 1, col["split_level"]) if split else slice(0, 0)   # Naht Grund | Licht
    lilac = [f"{i + 1} ({station_label(cfg, i)})" for i in range(posters(cfg))
             if is_lilac(palette_hex(cfg, i)) or is_lilac(dither_mids(palette_hex(cfg, i))[seam])]
    assert not lilac, (f"[color]: lila auf Plakat {', '.join(lilac)} (Palette oder Korn zwischen zwei Stufen). Mischung: "
                       "Rot direkt neben Blau? Reihenfolge aendern. Split: blauer Grund unter rotem Licht wird im Korn "
                       "lila. Reine Station P6: Grund dithert Schwarz + #FF55FF zu Lila, nicht verwendbar")
    bad = [s for s in cfg["styles"]["cycle"] if s not in S_CODES]
    assert not bad, f"[styles].cycle: unbekannte Codes {bad}. Erlaubt: {sorted(S_CODES)}"
    sp = cfg["spark"]
    # < 1: Betrachter auf der Bahn (B19, leere Frames hinter dem Kopf); > 1: Bahn ganz vor ihm (B20, Nahpunkt = ahead - 1)
    assert sp["ahead"] >= 0 and abs(sp["ahead"] - 1) > BEHIND_Z, \
        "[spark].ahead: 0..1 (Betrachter in der Bahn) oder > 1 (Bahn vor ihm), nicht ~1 (Stern durchfliegt den Kopf)"
    assert 0 <= sp["kepler_frac"] <= 1 and sp["width"] > 0, "[spark]: kepler_frac 0..1, width > 0"
    a, b, f = sp.get("front_dwell_frac", 0), sp.get("ends_dwell_frac", 0), sp.get("screen_frac", 0)
    assert abs(a) + b < 1 and b >= 0, "[spark]: |front_dwell_frac| + ends_dwell_frac < 1 (sonst laeuft der Stern rueckwaerts)"
    assert 0 <= f <= 1 and (f == 0 or sp["ahead"] > 1), "[spark].screen_frac: 0..1, nur mit ahead > 1 (Bahn vor dem Betrachter)"
    assert cfg["spark"]["spin_deg"] % 60 == 0, "[spark].spin_deg: Vielfaches von 60 (6-zackiger Stern), sonst ruckt der Loop"
    q = cfg["qr"]
    for key, ok in (("glow_shape", ("round", "square")), ("glow_profile", ("gauss", "light", "linear", "steps"))):
        assert q[key] in ok, f"[qr].{key}: {' | '.join(ok)}"
    assert all(type(q[k]) is int for k in ("quiet_cells", "glow_cells", "label_cap_cells", "label_gap_cells")), \
        "[qr]: alle *_cells in ganzen Zellen (Pixelraster)"
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
        f"[music]: {m['file']} oder {m['grid']} fehlt: uv run src/kickoff_loop_music.py"
    g = m["grid"] = json.load(open(grid))
    miss = [k for k in GRID_KEYS if k not in g]
    assert not miss, f"[music].grid: {m['grid']} ohne {miss} (altes Songraster? Mashup-Raster aus kickoff_loop_music.py)"
    cad = g["carousel_bars"]
    per_bar = cfg["loop"]["changes_per_bar"]
    if per_bar:                                          # festes Tempo (T16) ueber alle Karussell-Takte des Rasters
        cad = [[per_bar, sum(bars for _, bars in cad)]]
    cfg["loop"]["bpm"], cfg["video"]["cadence"] = g["bpm_carousel"], cad
    bad = [per for per, _ in cad if SUBDIV_PER_BAR % per]
    assert not bad, (f"Karussell: {bad} Wechsel pro Takt gehen nicht im Raster auf (Teiler von {SUBDIV_PER_BAR}: 16tel "
                     "und 32tel-Triolen, z. B. 8 16 24 48)")
    lm = cfg["music"]
    for k in ("loop_file", "loop_grid"):
        assert os.path.exists(os.path.join(PROJECT, lm[k])), f"[music].{k}: {lm[k]} fehlt"
    lm["loop_grid"] = json.load(open(os.path.join(PROJECT, lm["loop_grid"])))
    assert {"in_s", "sixteenth_s"} <= set(lm["loop_grid"]), "[music].loop_grid braucht in_s und sixteenth_s"
    assert abs(g["impact_s"] - g["burst_s"] - cfg["endcard"]["burst_beats"] * 60 / g["bpm_carousel"]) < 2e-3, \
        "[endcard].burst_beats passt nicht zur Luft im Mashup: uv run src/kickoff_loop_music.py neu bauen"
    assert len(cfg["styles"]["cycle"]) * cfg["styles"]["hold_frames"] == n, \
        f"[styles]: {len(cfg['styles']['cycle'])} Stile x hold {cfg['styles']['hold_frames']} != {n} Frames (Stile fielen weg)"
    return cfg


def count(cfg):
    """Frames eines Umlaufs: Periode von Bahn und Stilen ([loop].frames)."""
    return cfg["loop"]["frames"]


def posters(cfg):
    """Anzahl Plakate: Welten x Frames pro Welt. Eine Welt (stations): so viele wie count(cfg)."""
    return len(cfg["color"]["worlds"]) * cfg["color"]["world_frames"]


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


RAINBOW_GREY_CHROMA = 0.03   # OKLab-Buntheit, unter der eine Stufe keinen verlaesslichen Farbton hat (Weiss, Schwarz):
                             # sie nimmt den der Gegenseite (sonst dreht Weiss > Gelb einmal um den Kreis)
RAINBOW_SAMPLES = 36         # Stuetzstellen, an denen ein Farbton-Weg auf das Lila-Band geprueft wird (10° Abstand)


def is_paper(p):
    """Papier-Colorway: der Grund (Stufe 0) ist heller als die Tinte (letzte Stufe), z. B. P16 P21-P24.
    Split-Station "P23/P16": zaehlt der Grund."""
    pal = station(p.split("/")[0], 2) @ LUMA
    return bool(pal[0] > pal[-1])


def station(p, steps, split_level=None):
    """Palette einer Station auf `steps` Stufen: kuerzere Paletten (CGA, 4 Stufen) werden gedoppelt, nicht gemischt,
    damit die reine Station genau so aussieht wie ihr Original.
    Split-Tone "P11/P18" (Vadim 1.10.: "interdimensional"): Stufen unter split_level aus P11 (Grund, Schatten), ab
    split_level aus P18 (Licht, Tinte). Das Korn zwischen den beiden Haelften mischt die Welten im Bild.
    Negativ "~P11" (Vadim 2.10.: "extremer"): Stufen umgedreht, aus einer dunklen Colorway wird Papier (heller Grund,
    dunkle Tinte), aus Papier eine dunkle. Geht auch als Haelfte eines Splits: "~P11/P23", "P20/~P22"."""
    if "/" in p:
        ground, light = p.split("/")
        return np.concatenate([station(ground, steps)[:split_level], station(light, steps)[split_level:]])
    if p.startswith("~"):
        return station(p[1:], steps)[::-1]
    pal = S.hexpal(P_CODES[p])
    return pal[np.round(np.arange(steps) * (len(pal) - 1) / (steps - 1)).astype(int)]


def rainbow(a, b, f, avoid):
    """Mischung in OKLCh statt OKLab, je Stufe: Helligkeit und Buntheit linear, der Farbton dreht um den Farbkreis, in
    die Richtung, die das Band avoid (OKLCh-Grad, Maker-Night-Lila) nicht kreuzt; kreuzen beide oder keine, die kuerzere.
    Blau > Rot laeuft so ueber Tuerkis, Gruen, Gelb (Regenbogen) statt durch Lila oder Grau."""
    lch = lambda x: (x[:, 0], np.hypot(x[:, 1], x[:, 2]), np.degrees(np.arctan2(x[:, 2], x[:, 1])) % 360)  # noqa: E731
    (La, Ca, ha), (Lb, Cb, hb) = lch(a), lch(b)
    ha, hb = np.where(Ca < RAINBOW_GREY_CHROMA, hb, ha), np.where(Cb < RAINBOW_GREY_CHROMA, ha, hb)
    up = (hb - ha) % 360                                           # Weg mit wachsendem Winkel, 0..360
    s = np.linspace(0, 1, RAINBOW_SAMPLES + 1)[:, None]
    cross = lambda d: ((((ha + d * s) % 360) >= avoid[0]) & (((ha + d * s) % 360) <= avoid[1])).any(0)  # noqa: E731
    cu, cd = cross(up), cross(up - 360)
    d = np.where(cu == cd, np.where(up <= 180, up, up - 360), np.where(cu, up - 360, up))
    h, C, L = np.radians(ha + d * f), Ca + (Cb - Ca) * f, La + (Lb - La) * f
    return np.stack([L, C * np.cos(h), C * np.sin(h)], -1)


def mix_lab(a, b, t, per, col):
    """Zwei Stationspaletten (OKLab, je Stufe) bei Schritt t von per mischen.
      mix = oklab    gerade Linie in OKLab (Stand 30.9.)  |  rainbow  um den Farbkreis (rainbow)
      chroma_boost_frac  Buntheit in der Mitte der Mischung hoeher (sin-Buckel: 0 an den Stationen, die bleiben exakt)."""
    if col["mix"] == "oklab" and not col["chroma_boost_frac"]:
        return a + (b - a) * t / per                               # genau wie bisher (bitgleich)
    f = t / per
    m = a + (b - a) * f if col["mix"] == "oklab" else rainbow(a, b, f, col["rainbow_avoid_hue_deg"])
    m[:, 1:] *= 1 + col["chroma_boost_frac"] * np.sin(np.pi * f)
    return m


def dither_mids(hexes):
    """Was das Bayer-Korn zwischen zwei benachbarten Stufen zeigt: ihr Mittel in linearem Licht (das Auge mittelt
    Licht). Blau neben Rot ist einzeln nicht lila, im Korn schon. load prueft damit nur die Naht einer Split-Station:
    innerhalb einer Colorway ist das Korn gewollt (P17 Blau | Orange, P16 Pink | Blau schlagen hier an)."""
    rgb = np.array([[int(h[j:j + 2], 16) for j in (1, 3, 5)] for h in hexes]) / 255
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    mid = (lin[1:] + lin[:-1]) / 2
    srgb = np.where(mid <= 0.0031308, mid * 12.92, 1.055 * mid ** (1 / 2.4) - 0.055)
    return ["#%02X%02X%02X" % tuple(int(round(v * 255)) for v in c) for c in srgb]


def color_pos(cfg, i):
    """Wo Plakat i in der Farbreise liegt: (Welt w, ihre Stationen, Station k, Schritt t, Schritte pro Station per).
    t = 0: reine Station k, sonst Mischung von k nach k+1 zu t/per.

    Welten (Spider-Verse, Uebergabe 2): die Plakate laufen Welt fuer Welt durch, je world_frames Frames. Jede Welt ist
    eine in sich geschlossene Farbreise (die letzte Station mischt zurueck in die erste), zwischen den Welten wird hart
    gewechselt. Deshalb darf eine Welt Papier sein und die naechste dunkel: gemischt wuerde das grau."""
    col = cfg["color"]
    w, j = divmod(i, col["world_frames"])
    st = col["worlds"][w]
    per = col["world_frames"] // len(st)
    k, t = divmod(j, per)
    return w, st, k, t, per


def palette_hex(cfg, i):
    """Palette von Plakat i als Hex-Liste (Stufe 0 = Grund): zwischen zwei Stationen seiner Welt Stufe fuer Stufe linear
    in OKLab gemischt. OKLab statt RGB, weil gleiche Schritte dort gleich gross aussehen (kein Grau-Loch in der Mitte)."""
    col = cfg["color"]
    _, st, k, t, per = color_pos(cfg, i)
    if col["mix"] == "cut":                                         # harte Spruenge: die Station haelt, kein Mischen
        return ["#%02X%02X%02X" % tuple(int(v) for v in c) for c in station(st[k], col["steps"], col["split_level"])]
    a = to_oklab(station(st[k], col["steps"], col["split_level"]))
    b = to_oklab(station(st[(k + 1) % len(st)], col["steps"], col["split_level"]))
    rgb = from_oklab(mix_lab(a, b, t, per, col))
    return ["#%02X%02X%02X" % tuple(int(v) for v in c) for c in rgb]


def is_lilac(hexes):
    """Strenger als styles.lila (250-300°, s > 0.3): Mischungen streifen sonst Flieder (240-320°, s > 0.2), das liest
    sich auch als Lila. Lila gehoert der Maker Night. load prueft damit jedes Plakat, auch reine Stationen: P6 (CGA,
    #FF55FF bei 300°) laesst styles.lila durch, im Loop dithert sein Grund aber Schwarz + Magenta zu Lila (Bogen C3,
    1.10.). Hier faellt es heraus."""
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
    """Fuer Bogen und Report: "P11" auf einer Station, "P11>P13 50%" dazwischen. Bei mehreren Welten davor die Welt:
    "W2 P11>P13 50%"."""
    w, st, k, t, per = color_pos(cfg, i)
    world = f"W{w + 1} " if len(cfg["color"]["worlds"]) > 1 else ""
    nxt = st[(k + 1) % len(st)]
    hold = t == 0 or nxt == st[k] or cfg["color"]["mix"] == "cut"
    return world + (st[k] if hold else f"{st[k]}>{nxt} {round(100 * t / per)}%")


# ---------------------------------------------------------------- Geometrie

def orbit(cfg, phase):
    """Stern auf der Bumerang-Bahn bei `phase` (Frames, darf gebrochen sein): (x, y, Radius, Drehung).

    Ellipse um den Betrachter (Vadim 1.10.: "wie ein Boomerang nach hinten und wieder vorne, elliptisch"): Tiefe 1,
    Breite `width`, Mitte `ahead` vor dem Betrachter. Er sitzt nahe dem hinteren Ende, also ist der Weg hinter dem Kopf
    kurz. Der Stern kommt links riesig herein, fliegt in die Tiefe (klein), kommt rechts riesig zurueck und ist hinter
    dem Kopf weg. Die Zeit ist echt (Vadim: "man fuehlt, wenn der Spark nicht genug Zeit hatte"): gleichmaessiges
    Tempo auf der Bahn (kepler_frac 0) oder Flaechensatz um den Betrachter (1, hinten schnell), dazwischen gemischt.
    Der Stern ist groesser als der Abstand, in dem er vorbeifliegt (Comic, Spider-Verse): nur so ist er an den Seiten
    mehrere Frames lang riesig. Er verlaesst das Plakat hinter dem Kopf, dort ist der Frame leer (Radius 0). Frontal,
    dreht sich nur in der Bildebene (spin_deg). Zentralprojektion aufs Plakat (x ~ X/Z, Groesse ~ 1/Z)."""
    sp, n = cfg["spark"], count(cfg)
    t = (phase + 0.5 + sp["phase_shift_frames"]) / n
    t -= sp.get("front_dwell_frac", 0) * np.sin(2 * np.pi * t) / (2 * np.pi)   # Tempo 1 - a cos: am Nahpunkt (t=0) langsam
    t -= sp.get("ends_dwell_frac", 0) * np.sin(4 * np.pi * t) / (4 * np.pi)    # 1 - b cos 2x: nah UND fern langsam
    X, Z = _ellipse(sp, t)
    rot = float(sp["rot_start_deg"] + sp["spin_deg"] * phase / n)
    if Z <= BEHIND_Z:                                         # hinter/neben dem Kopf: kein Stern auf dem Plakat
        return 0.5, 0.5, 0.0, rot
    x, y, r = _project(sp, X, Z)
    dx, dy = max(-x, 0, x - 1), max(-y, 0, y - 1) / POSTER_ASPECT   # Abstand der Mitte zum Plakat (Einheit kurze Seite)
    if dx * dx + dy * dy >= r * r:                            # ganz neben dem Plakat: leer, auch kein Schein
        return 0.5, 0.5, 0.0, rot
    return float(x), float(y), float(r), rot


def _project(sp, X, Z):
    """Bahnpunkt(e) (X seitlich, Z vorn) → Plakat (x, y, Radius), Zentralprojektion (x ~ X/Z, Groesse ~ 1/Z)."""
    ro = np.radians(sp["plane_roll_deg"])                   # Bahnebene um die Blickachse gedreht (0 = waagerecht)
    u, v = X * np.cos(ro) - sp["height"] * np.sin(ro), X * np.sin(ro) + sp["height"] * np.cos(ro)
    return (sp["vanish"][0] + sp["lens"] * u / Z, sp["vanish"][1] + sp["lens"] * POSTER_ASPECT * v / Z,
            sp["lens"] * sp["size"] / Z)


def _ellipse(sp, t):
    """Punkt (X seitlich, Z vorn) der Bahnellipse zur Zeit t (0..1 = ein Umlauf, 0 = hinter dem Kopf bzw. Nahpunkt,
    0.5 = fern). Zeit = Mischung aus Bogenlaenge (gleiches Tempo im Raum), ueberstrichener Flaeche um den Betrachter
    (Flaechensatz, kepler_frac) und sichtbarem Weg der Sternspitzen auf dem Plakat (screen_frac: gleiches Tempo im
    Bild, Mitte + Radius). Vadim 2.10. zu B20c: "wo der Spark ist und wie lange er wo braucht, fuehlt sich komisch an"
    (Befund: hinter dem Titel kriecht er 0.08/Frame, an den Seiten hetzt er 0.26). Numerisch invertiert auf
    ELLIPSE_SAMPLES Stuetzstellen."""
    w, ahead, k = sp["width"], sp["ahead"], sp["kepler_frac"]
    ph = np.linspace(-np.pi, np.pi, ELLIPSE_SAMPLES)          # -pi = hinter dem Kopf, 0 = fern
    X, Z = w * np.sin(ph), ahead + np.cos(ph)                 # links herum nach vorn (wie bisher)
    arc = np.r_[0, np.cumsum(np.hypot(np.diff(X), np.diff(Z)))]
    area = np.r_[0, np.cumsum(0.5 * np.abs(X[:-1] * Z[1:] - X[1:] * Z[:-1]))]
    T = (1 - k) * arc / arc[-1] + k * area / area[-1]
    f = sp.get("screen_frac", 0)
    if f:                                                     # nur Bahnen ganz vor dem Betrachter (load prueft ahead > 1)
        x, y, r = _project(sp, X, Z)
        seen = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y) / POSTER_ASPECT) + np.abs(np.diff(r)))]
        T = (1 - f) * T + f * seen / seen[-1]
    p = np.interp(t % 1, T, ph)
    return float(w * np.sin(p)), float(ahead + np.cos(p))


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
    Satz aus diesem Modul. Plakat i (ueber alle Welten) liegt auf Bahnframe i mod [loop].frames: jede Welt ist ein
    ganzer Umlauf bzw. ein Stueck davon."""
    x, y, radius, rot = star_at(cfg, i % count(cfg))
    code = style_code(cfg, i)
    if radius == 0:                                           # leerer Frame: winziger S2-Stern weit neben dem Plakat, so
        (x, y, radius), code = OFF_STAR, "S2"                 # bleibt jede Stern-/Satzebene definiert (Maske leer). S2,
                                                              # weil Labor-Stile (S31g) am Stern messen und leer abbrechen
    st = K.style(palette(cfg, i), S_CODES[code], "riese", star=(x, y, radius), rot=rot,
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


def qr_glow(c, q):
    """JOIN US + QR, die Platte glueht ins Plakat ein (Vadim zu v005: keine harte Box, "reingeglueht" wie v003, aber
    sauber). Ebenen [(name, Maske, Wert)] in Malreihenfolge.

    Die QR-Platte (Module + quiet_cells Ruhezone) steht flaechig in der hellsten Stufe, die Module in der dunkelsten.
    Unten links an Rand und Satzkante wie in kickoff.layout; weniger Ruhezone = kleinere Platte, gleiche Ecke. Um die Platte laeuft die hellste Stufe ueber den Untergrund aus, rein geometrisch aus dem Abstand zur
    Platte (kein Rauschen: der verbeulte v003-Hof kam aus halo_warp_cells), im Bayer-Korn des Plakats auf dem Zellraster.
      glow_shape    round = Abstand zum Rechteck, die Ecken runden sich nach aussen | square = bleibt eckig (Chebyshev)
      glow_profile  gauss = weich | light = Lichtabfall (exponentiell) | linear = gleichmaessig |
                    steps = linear, auf Palettenstufen gerundet: Ringe ohne Korn
    JOIN US steht frei ueber der Platte, ohne Kasten/Rand/Hof, und kippt pro Buchstabe hell/dunkel je nach Untergrund
    (flip_glyphs, Regel wie beim Datum). Es hat eine feste Groesse in Zellen und waechst nicht mit dem Titel."""
    L, px = c.L, c.px
    lum = c.pal @ LUMA
    hi, lo = c.lvl(int(lum.argmax())), c.lvl(int(lum.argmin()))
    quiet = q["quiet_cells"]                                      # Ruhezone in Zellen (kickoff.layout: 3 Module = 6)
    n = len(L["q"]) * MODULE_CELLS + 2 * quiet                    # Plattenkante in Zellen, inkl. Ruhezone
    top, left = round(L["qbot"] / px) - n, round(L["x0"] / px)   # Platte unten links an Rand und Satzkante
    plate = rect(c, top, left, top + n, left + n)
    mods = np.zeros((c.gh, c.gw), bool)
    mods[top + quiet:top + n - quiet, left + quiet:left + n - quiet] = S.up(L["q"], MODULE_CELLS)

    dy = np.maximum(np.maximum(top - (c.yy + 0.5), c.yy + 0.5 - (top + n)), 0)     # Abstand Zellmitte → Platte
    dx = np.maximum(np.maximum(left - (c.xx + 0.5), c.xx + 0.5 - (left + n)), 0)
    d = np.hypot(dx, dy) if q["glow_shape"] == "round" else np.maximum(dx, dy)
    w = q["glow_cells"]
    g = {"gauss": lambda: np.exp(-(2 * d / w) ** 2),               # flache Kuppe, dann Abriss
         "light": lambda: np.exp(-GLOW_LIGHT_E * d / w),            # Lichtabfall: steil an der Platte, langer Schweif
         }.get(q["glow_profile"], lambda: np.clip(1 - d / w, 0, 1))()
    base = under(c)
    v = base + (hi - base) * g
    if q["glow_profile"] == "steps":
        v = np.round(v * c.N) / c.N
    glow = (g > GLOW_MIN) & ~plate

    text = S.line_mask(K.COPY["cta"], "clash", q["label_cap_cells"] * px, top * px, left * px, px, (c.gh, c.gw))
    ys, xs = np.nonzero(text)
    ty = top - q["label_gap_cells"] - (ys.max() - ys.min() + 1)  # Oberkante: label_gap_cells ueber der Platte
    tx = left + (n - (xs.max() - xs.min() + 1)) // 2              # waagerecht mittig ueber der Platte
    text = np.roll(text, (ty - ys.min(), tx - xs.min()), (0, 1))
    return [("qr", glow, v), ("qr", plate, hi), ("qr", mods, lo), ("cta", text, None)]


def qr_embed(c, q):
    """JOIN US + QR auf das Plakat legen (Geometrie und Stufen: qr_glow). JOIN US zuletzt, damit flip_glyphs das
    Gluehen als Untergrund sieht. JOIN US steht in der Tintenstufe (letzte Stufe: auf dunklem Grund die hellste, auf
    Papier die dunkelste) und kippt auf Hohem in den Grund. Frueher stand hier die hellste Stufe: auf Papier ist das
    der Grund selbst, JOIN US verschwand im Gluehen (das dort ebenfalls zum Grund hin laeuft)."""
    for name, mask, v in qr_glow(c, q):
        c.add(name, mask, flip_glyphs(c, mask, c.lvl(c.N)) if v is None else v)


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
    neu gegenueber kickoff.type_layers: Verlauf pro Zeile, SPARK waagerecht zentriert, keine Kopfzeile, QR glueht (qr_glow)."""
    lp = c.st["loop"]
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
                      st.get("dither_shift"),
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
        out = pool.map(_frame_job, [(cfg, i) for i in range(posters(cfg))])
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


# JOIN US + QR (qr_glow). Jede Variante nennt alle [qr]-Schluessel, damit sie unabhaengig vom Stand der loop.toml
# gleich aussieht; die Variante, die loop.toml gerade setzt, ist auf den Boegen markiert.
_GLOW = {"qr.quiet_cells": 6, "qr.glow_shape": "round", "qr.glow_profile": "light", "qr.glow_cells": 12,
         "qr.label_cap_cells": 9, "qr.label_gap_cells": 4}
VARIANTS = [   # Vadim zu G1-G6: "nicht so viel Padding" → Ruhezone 1 / 1.5 / 2 Module, je mit Licht (G3) und eng (G1)
    ("R2 Licht", {**_GLOW, "qr.quiet_cells": 2}),
    ("R3 Licht", {**_GLOW, "qr.quiet_cells": 3}),
    ("R4 Licht", {**_GLOW, "qr.quiet_cells": 4}),
    ("R2 eng", {**_GLOW, "qr.quiet_cells": 2, "qr.glow_profile": "gauss", "qr.glow_cells": 6}),
    ("R3 eng", {**_GLOW, "qr.quiet_cells": 3, "qr.glow_profile": "gauss", "qr.glow_cells": 6}),
    ("R6 Licht (bisher)", _GLOW),
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
    damit man Kanten zaehlen kann. Dazu qr_sheet.png: JOIN US + QR aller Varianten (Spalten) auf allen Frames
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
    out.append(_sheet(list(grid.items()), os.path.join(PROJECT, "previz", "variants", "qr_sheet.png")))
    return "\n".join(out)


def _star_job(args):
    cfg, i, code = args
    st = poster_style(cfg, i)
    st["S"] = S_CODES.get(code, "lab:" + code)
    img = frame(cfg, i, style=st)
    return code, i, img, legibility(st, img)


def stars(cfg, codes):
    """Sterne-Bogen: jeder Stil an denselben drei Stellen der Bahn (Frame 1 gross links angeschnitten, Mitte fern,
    letzter Frame gross rechts), in der Farbe des jeweiligen Frames. Beschriftet mit Code, Name, Lesbarkeit.
    Zyklus-Stile weiss, andere gelb. → previz/variants/stars.png
    Befund 1.10.: die Labor-Stile S15 S16 S17 S19 S20 S28 ignorieren die Bahn (feste Lage oder seitenfuellend), S25
    braucht eine Zweitpalette je Colorway: keine Kandidaten fuer den Loop."""
    n = count(cfg)
    at = [0, n // 2, n - 1]
    with Pool() as pool:
        res = pool.map(_star_job, [(cfg, i, c) for c in codes for i in at])
    import lab_spark
    names = {c: name for c, _, name, _ in lab_spark.CANDS} | {"S2": "Verlauf", "S7": "Nest", "S33": "Matrjoschka"}
    h, w = res[0][2].shape[:2]
    pw, ph, gap, cap, per_row = w // 4, h // 4, 12, 64, 4
    cell_w = 3 * pw + 2 * 4 + gap * 2
    rows = -(-len(codes) // per_row)
    sheet = Image.new("RGB", (per_row * cell_w, rows * (ph + cap + gap)), (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    font = S.font("DepartureMono-Regular.otf", 26)
    cycle = cfg["styles"]["cycle"]
    for k, code in enumerate(codes):
        x0, y0 = (k % per_row) * cell_w, (k // per_row) * (ph + cap + gap)
        part = [r for r in res if r[0] == code]
        worst = min(r[3] for r in part)
        tag = f"{code} {names.get(code, '')}"[:30] + ("" if worst >= K.TIER[0] else f"  L{worst:.2f}")
        d.text((x0, y0 + 6), tag, font=font, fill=(230, 230, 230) if code in cycle else (255, 214, 90))
        for j, (_, i, img, _) in enumerate(part):
            sheet.paste(Image.fromarray(img).resize((pw, ph), Image.BOX), (x0 + j * (pw + 4), y0 + cap))
    path = os.path.join(PROJECT, "previz", "variants", "stars.png")
    sheet.save(path)
    return path


# ---------------------------------------------------------------- Selbsttest

def selftest_frames(cfg):
    """Standardframes fuer `test` ohne Argumente, aus der Bahn statt fest (die alten 3/7/9 passten nur zu 16 Frames):
    die drei kleinsten Sterne. Dort ist der QR frei (ein verbeultes Gluehen faellt auf) und der Frame nicht leer.
    Nur dunkler Grund: Gluehen- und Verlaufstest setzen helles Licht auf dunklem Grund voraus; Papier-Frames (C5b,
    Grund L > 0.5) brauchen eine eigene Regel (offen)."""
    dark = lambda i: to_oklab(np.array([[int(palette_hex(cfg, i)[0][k:k + 2], 16) for k in (1, 3, 5)]], float))[0, 0] < 0.5
    r = [(star_at(cfg, i)[2], i) for i in range(count(cfg)) if dark(i)]
    return sorted(i for _, i in sorted(x for x in r if x[0] > 0)[:3])


def selftest(cfg, i=8):
    """Prueft am fertigen Bild (nicht am Code), was schiefgehen kann:
    Verlauf pro Zeile = oberste Pixelreihe nur hellste Stufe, unterste nur die Stufe darunter, dazwischen wird es von
    unten nach oben nie dunkler; Schrift auf dem Stern (gekippt) ist ausgenommen. QR lesbar. Titelblock steht in jedem Frame gleich.
    Farbreise: keine Lila-Mischung, jede Station exakt ihre Original-Palette. SPARK waagerecht zentriert.
    QR: Platte flaechig in ihrer Stufe, rundum >= quiet_cells hellste Stufe als Ruhezone. Gluehen geometrisch: pro
    Abstandsring zur Platte wird es nach aussen nie heller und ist auf allen vier Seiten gleich hell (der verbeulte
    v003-Hof mit halo_warp_cells faellt hier durch, die harte Box von v005 auch: Ring 1 war dort der dunkle Rand)."""
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
    for (s, _, _), full in zip(lines, masks):
        m = full & (level != 0)                         # ohne gekippte Pixel. Kopie: masks wird unten mit F32 verglichen
        if m.sum() < full.sum() / 2:                    # Zeile gekippt (dunkle Schrift auf Papier, C5b): kein Licht-Verlauf
            continue
        rows = np.array([np.mean(level[y][m[y]]) for y in np.nonzero(m.any(1))[0]])
        assert rows[0] == top_level and rows[-1] == top_level - 1, f"{s}: Enden nicht flaechig {rows[0]:.2f} {rows[-1]:.2f}"
        period = len(S.bayer(4))                        # Bayer 4x4 fuellt Nachbarreihen verschieden: ueber 4 Reihen mitteln
        smooth = np.convolve(rows, np.ones(period) / period, "valid")
        assert np.all(np.diff(smooth) <= 0.05), f"{s}: Verlauf wird nach unten wieder heller {np.round(smooth, 2)}"
    assert K.check_qr(img, PREVIEW_CELL_PX), "QR nicht lesbar"
    q = st["loop"]["qr"]
    (_, glow, _), (_, plate, _), (_, mods, _), _ = qr_glow(c, q)
    p = PREVIEW_CELL_PX
    blocks = img[:c.gh * p, :c.gw * p].reshape(c.gh, p, c.gw, p, 3)
    assert (blocks == blocks[:, :1, :, :1]).all((1, 3, 4))[plate | glow].all(), "QR: Zellen nicht einfarbig (nicht auf dem Raster)"
    ys, xs = np.nonzero(mods)
    k = q["quiet_cells"]
    zone = level[ys.min() - k:ys.max() + k + 1, xs.min() - k:xs.max() + k + 1].copy()
    zone[k:-k, k:-k] = c.hi
    assert (zone == c.hi).all(), f"QR-Ruhezone: weniger als {k} Zellen hellste Stufe um die Module"
    ys, xs = np.nonzero(plate)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    cx, cy, R, rot = c.L["star"]
    text = binary_dilation(qr_glow(c, q)[-1][1], iterations=2)
    free = glow & (S.star_d(c, cx, cy, R, rot)[0] > STAR_CLEAR) & ~text   # ohne Stern + Schein, ohne JOIN US
    sides = {"oben": np.s_[y0 - q["glow_cells"]:y0, x0:x1], "unten": np.s_[y1:y1 + q["glow_cells"], x0:x1],
             "links": np.s_[y0:y1, x0 - q["glow_cells"]:x0], "rechts": np.s_[y0:y1, x1:x1 + q["glow_cells"]]}
    ring = np.maximum(np.maximum(y0 - c.yy, c.yy - y1 + 1), np.maximum(x0 - c.xx, c.xx - x1 + 1)).astype(int)
    profs = {}
    for name, sl in sides.items():
        f, r, lv = free[sl], ring[sl], level[sl]
        prof = np.array([lv[f & (r == d)].mean() if (f & (r == d)).sum() >= 8 else np.nan
                         for d in range(1, q["glow_cells"] + 1)])
        if np.isnan(prof).sum() > len(prof) // 2:                      # Seite liegt am Bildrand oder im Stern
            continue
        ok = prof[~np.isnan(prof)]
        assert ok[0] >= c.hi - 1, f"QR-Gluehen {name}: direkt an der Platte nicht hell ({ok[0]:.2f}), harter Rand?"
        per = len(S.bayer(4))                                           # Bayer 4x4: ueber 4 Ringe mitteln
        smooth = np.convolve(ok, np.ones(per) / per, "valid")
        assert np.all(np.diff(smooth) <= 0.1), f"QR-Gluehen {name}: wird nach aussen wieder heller {np.round(ok, 2)}"
        profs[name] = prof
    assert len(profs) >= 2, f"QR-Gluehen: nur {list(profs)} frei von Stern/Schrift, anderen Frame testen"
    spread = np.nanmax(np.nanmax(list(profs.values()), 0) - np.nanmin(list(profs.values()), 0))
    assert spread <= GLOW_SIDE_TOL, f"QR-Gluehen: Seiten ungleich hell (bis {spread:.2f} Stufen), verbeult?"
    last = S.Ctx(poster_style(cfg, count(cfg) - 1), PREVIEW)
    same = [np.array_equal(a, b) for a, b in zip(masks, (m for name, group in text_lines(last).items()
                                                       for m in line_masks(last, group, centered=name == "title")))]
    assert all(same), "Titel/Datum stehen nicht in jedem Frame an derselben Stelle"
    for k in range(posters(cfg)):
        w, st, j, t, _ = color_pos(cfg, k)
        if t == 0:
            got = np.array([[int(h[q:q + 2], 16) for q in (1, 3, 5)] for h in palette_hex(cfg, k)])
            assert np.abs(got - station(st[j], cfg["color"]["steps"], cfg["color"]["split_level"])).max() <= 1, \
                f"Welt {w + 1}, Station {st[j]} (Plakat {k + 1}) weicht vom Original ab"
    assert is_lilac(["#A877A6"]) and not is_lilac(palette_hex(cfg, 0)), "Lila-Test erkennt Flieder nicht"
    if cfg["spark"]["source"] == "orbit":                     # Bahn: geschlossen, links rein, rechts raus (1.10.: Vorzeichen
        n = count(cfg)                                        # der Ellipse war vertauscht, der Stern kam rechts herein)
        assert np.allclose(orbit(cfg, n)[:3], orbit(cfg, 0)[:3]), "Bahn schliesst nicht: Sprung am Neustart"
        seen = [o for o in (orbit(cfg, i) for i in range(n)) if o[2] > 0]
        assert seen[0][0] < 0.5 < seen[-1][0], "Bahn: Stern soll links hereinkommen und rechts hinaus"
    return f"Selbsttest ok (Frame {i + 1}: Verlauf pro Zeile, QR, Ruhezone, Gluehen geometrisch; Titel fix, Stationen, Lila-Test)"


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
    n = posters(cfg)
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
    arg = args[1] if len(args) > 1 else None
    var = arg if cmd in ("sheet", "preview") and arg and arg.endswith(".toml") else None   # <variante.toml> neben loop.toml
    cfg = load(var or CONFIG, music=arg if cmd == "preview" and arg and not var else None)
    if cmd == "frames":
        _, ok, leg = frames(cfg)
        print(f"{len(ok)} Plakate, QR lesbar: {sum(ok)}/{len(ok)}, Lesbarkeit: {' '.join(f'{x:.2f}' for x in leg)}")
    elif cmd == "test":
        for i in [int(a) - 1 for a in args[1:]] or selftest_frames(cfg):
            print(selftest(cfg, i))
        if cfg["checks"]["flash_gate"]:
            import kickoff_loop_video as V
            print(V.flash_selftest(cfg))
    elif cmd == "print":
        print(print_files(cfg))
    elif cmd == "stars":                                # Sterne aussuchen: Zyklus oder die genannten Codes
        print(stars(cfg, args[1:] or cfg["styles"]["cycle"]))
    elif cmd == "variants":
        print(variants(cfg, [int(a) - 1 for a in args[1:]] or [8]))
    elif cmd == "sheet":                                # schnelle Runde: Kontaktbogen + Plakat-Loop, kein Video
        import kickoff_loop_video as V
        posters, ok, leg = frames(cfg)
        tag = os.path.splitext(os.path.basename(var))[0] + "_" if var else ""   # B1.toml → review/B1_contact.png
        out = V.sheet(cfg, posters, ok, leg, os.path.join(PROJECT, "previz", "review" if var else "now"), tag)
        print(f"{out}/{tag}contact.png  QR {sum(ok)}/{len(ok)}, Lesbarkeit min {min(leg):.2f}")
        subprocess.run(["open", os.path.join(out, tag + "contact.png"), os.path.join(out, tag + "loop.mp4")]) if sys.stdout.isatty() else None
    elif cmd == "boil":                                 # Test: Digitalteil ohne | mit Boil nebeneinander
        import kickoff_loop_video as V
        out = V.boil_test(cfg)
        print(out)
        subprocess.run(["open", out])
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
