#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""F15 = Ende nach Vadims Feedback zu F14 (8.10.), Foto-Phase MC3, ein Ablauf:

1. Maske (mask_beat → pull_beat): der dunkle Spark des MC3-Videos (KE.orbit_state, fliegt ueber die letzten Plakate auf
   die Kamera zu und macht alles schwarz) ist die Maske. Darin die Wortwand ueber den ganzen Bildschirm, in den
   Buchstaben laeuft der Loop weiter; ausserhalb das MC3-Bild, bis er es deckt. Vadim: "der ist ja schon posterized, da
   ist es nicht so schlimm, wenn er nicht verschiedene Formen annimmt; dann haben wir genug Zeit fuer die Begriffe".
   Begriffe wechseln auf words_change.
2. Vorhang (pull_beat → erste Stufe): die Woerter stehen, ein Spark-Loch in Deckgroesse auf F1 (Silhouette im Stil des
   Plakats dahinter, wechselt je Plakat) zieht geradeaus zur Seite weg, Tempo erst steigend, dann konstant, Groesse
   bleibt (F14 schrumpfte in die Tiefe und liess einen Zwerg uebrig, der in einem Bild verschwand).
3. Tonleiter (steps, gemessene Bass-Einsaetze C2 / D2 / D#2): je Stufe neue Kartenzeilen, roter Spark hinter dem Slash.
   Eine neue Zeile leuchtet ein (Rampe glimmend rot → weiss, intro_beats), ihr Halo waechst dabei von klein auf
   (ease-in-out), alle aelteren wachsen ein Stueck mit (glow_bump_frac); alle Halos atmen und flackern leicht. Nach der
   letzten Stufe + fade_hold_beats schrumpft und dunkelt alles Licht in fade_beats, die Schrift zerfaellt mit → Schwarz.

Stellschrauben: kickoff_loop/previz/review/F15/F15.toml. Licht wie das F10-Ende (kickoff_loop_end.flare_layer).
  uv run src/kickoff_loop_f15.py video|sheet|test <F15.toml>     still <F15.toml> <beat> [...]
"""
import copy
import functools
import hashlib
import json
import math
import os
import subprocess
import sys
import tomllib

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation

import kickoff as K
import kickoff_loop as KL
import kickoff_loop_end as KE
import kickoff_loop_video as V
import styles as S
from makernight_sparks import star_r

FPS = 24
FMT = "9x16"
CELL = S.BASE["R"] * S.SIZES[FMT][2]                  # 4 Ausgabepixel pro Zelle
SRC = hashlib.sha1(open(__file__, "rb").read()).hexdigest()[:12]   # im Cache-Schluessel: Aenderungen hier rendern neu
EPS = 1e-6
OFF = (-3240.0, -5760.0, 1.0, 0.0)                    # Plakatstern weit ausserhalb (schwarze Szenen)
COVER = 1.02           # Loch deckt das Bild: weitestes Pixel x so viel (Rand im Korn)
FLICKER_PER_BEAT = (2.7, 4.1)   # Flackern = zwei Sinus mit unteilbaren Frequenzen (~3.7 / 5.6 Hz): wirkt unregelmaessig
EVENT_RATIO = 2.0      # test: ein Schnitt setzt auf seinem Bild ein: doppelt so stark wie das Bild davor und der Median davor
EVENT_MIN = 0.003      # ... und mindestens so viel mittlere Aenderung (Encoder-Rauschen im Standbild ~0.0002)
BLACK_LUM = 0.03       # Silhouette = Zellen ueber Schwarz
LIT_LUM = 0.10         # test "Woerter stehen" / "kein Zwerg": sicher hell (Encoder-Saum an Buchstabenkanten liegt darunter)
OLD_SHIFT = 3          # Gegenprobe: dieselben Schnitte 3 Bilder spaeter
GROW_PROBE_BEATS = 0.6 # test "Halo waechst": Lichtflaeche so lange nach der Stufe gegen das Bild der Stufe (vor der naechsten)
INTRO_RATIO = 0.6      # test "leuchtet ein": neue Zeile auf ihrer Stufe hoechstens so hell wie nach intro_beats
SAME_MC3 = 0.02        # test "Maske": ausserhalb mittlere Abweichung vom MC3-Bild hoechstens (Encoder), innen mindestens 0.05


# ---------------------------------------------------------------- Konfiguration und Raster

def main_root():
    """Hauptcheckout (Vorschau, Songs und Cache liegen nur dort, gitignored), auch aus einem Worktree."""
    git = subprocess.run(["git", "-C", KL.ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True).stdout.strip()
    return os.path.dirname(git) if git else KL.ROOT


def load(path):
    f = tomllib.load(open(path, "rb"))["f15"]
    f["code"], f["toml"] = os.path.splitext(os.path.basename(path))[0], os.path.abspath(path)
    cfg = KL.load(os.path.join(KL.ROOT, f["base_toml"]))
    g = json.load(open(os.path.join(KL.ROOT, f["grid"])))
    f["bar1"], f["beat"] = g["in_s"] - f["song_start_s"], g["beat_s"]   # Taktstrich 1 auf der Timeline, Beatlaenge
    root = main_root()
    f["base_video"], f["song"] = (os.path.join(root, f[k]) for k in ("base_video", "song"))
    ch = f["words_change"]
    assert len(ch) == len(f["words"]) - 1 and ch == sorted(ch), "words_change: je Begriff nach dem ersten ein Beat, steigend"
    assert f["mask_beat"] < ch[0] and ch[-1] < f["pull_beat"] < f["steps"][0], "mask_beat < words_change < pull_beat < steps"
    assert len(f["steps"]) == len(f["step_items"]), "steps / step_items"
    assert 0 < f["pull_accel_frac"] <= 1 and math.hypot(*f["pull_dir"]) > 0, "pull_accel_frac in (0, 1], pull_dir != 0"
    assert 0 <= f["intro_level"] < 1 and f["intro_beats"] > 0 and f["glow_grow_beats"] > 0, "intro_* / glow_grow_beats"
    assert os.path.exists(f["song"]) and os.path.exists(f["base_video"]), "Song oder MC3-Video fehlt"
    return cfg, f


def t_beat(f, b):
    return f["bar1"] + b * f["beat"]


def frame_at(f, b):
    """Bild, in dem Beat b liegt (es zeigt schon den neuen Zustand)."""
    return math.floor(t_beat(f, b) * FPS - EPS)


def tb_of(f, n):
    """Beat-Position am Ende von Bild n."""
    return ((n + 1) / FPS - f["bar1"]) / f["beat"]


def n_end(f):
    return round(f["end_s"] * FPS)


def marks(f):
    """Eckbilder: erstes mit Maske, letztes der Wortwand (deckt ganz), letztes des Vorhangs (Loch draussen, schwarz)."""
    return frame_at(f, f["mask_beat"]), frame_at(f, f["pull_beat"]) - 1, frame_at(f, f["steps"][0]) - 1


def zoom_dt(cfg, n):
    """Sekunden nach dem Karussell-Ende (Zeitachse des F10-Endes, KE.orbit_state)."""
    return (n - round(cfg["music"]["grid"]["burst_s"] * FPS)) / FPS


def base_until(cfg):
    """Erstes Bild, in dem das MC3-Video den blauen Slogan (F9/F10) zeigt: ab da ist ausserhalb des Sparks Schwarz."""
    return round(cfg["music"]["grid"]["burst_s"] * FPS + cfg["ending"]["orbit_pre_at_beats"] * KE.beat(cfg) * FPS)


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- Lage der Loecher (Bildanteile, r = Anteil Bildbreite)

def loop_star(cfg, phase):
    """Loop-Stern bei Bahnphase phase (Frames) im 9:16-Bild, umgerechnet wie KE.poster_digital."""
    W, H = S.SIZES[FMT][:2]
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = V.digital_offset(cfg)
    x, y, r, rot = KL.orbit(cfg, phase)
    return (ox + x * pw) / W, (oy + y * ph) / H, r * pw / W, rot


def dark(cfg, n):
    """Der dunkle Spark des MC3-Videos in Bild n (Befund 8.10.: Umriss liegt auf Bild 159-190 genau auf ihm)."""
    W, H = S.SIZES[FMT][:2]
    x, y, R, rot = KE.orbit_state(cfg, zoom_dt(cfg, n))["loop"]["digital"]["star"]
    return x / W, y / H, R / W, rot


def core_cells(pose):
    """Sternkoerper auf dem Zellraster (Formel wie styles.star_d, Zellmitten wie styles.Ctx)."""
    W, H = S.SIZES[FMT][:2]
    x, y, r, rot = pose
    gy, gx = np.mgrid[0:H // CELL, 0:W // CELL].astype(np.float32)
    dx, dy = (gx + 0.5) * CELL - x * W, (gy + 0.5) * CELL - y * H
    return np.hypot(dx, dy) < star_r(dx, dy, rot % KE.STAR_SYM_DEG) * r * W


def cover_r(x, y, rot):
    """Spitzenradius (Anteil Bildbreite), ab dem der Spark um (x, y) jede Zelle deckt (sternfoermig: der Rand reicht)."""
    W, H = S.SIZES[FMT][:2]
    gy, gx = np.mgrid[0:H // CELL, 0:W // CELL].astype(np.float32)
    dx, dy = (gx + 0.5) * CELL - x * W, (gy + 0.5) * CELL - y * H
    return float((np.hypot(dx, dy) / star_r(dx, dy, rot)).max()) * COVER / W


def phase(cfg, f, n):
    """Bahnphase (Bahnframes, absolut: Plakat = floor) in Bild n: Karussell-Tempo, auf F1 (= 2 count) im letzten Bild der
    Wortwand, damit der Vorhang dort ansetzt, wo der Spark des Plakats dahinter gerade steht."""
    rate = cfg["loop"]["changes_per_bar"] / 4 / f["beat"] / FPS         # Plakate pro Bild (T16)
    return 2 * KL.count(cfg) + rate * (n - marks(f)[1])


def pull_u(f, n):
    _, n2, n3 = marks(f)
    return min(max((n - n2) / (n3 - n2), 0.0), 1.0)


@functools.lru_cache(maxsize=None)
def exit_dist(x0, y0, r, rot, dx, dy):
    """Weg (Einheiten von pull_dir), nach dem ein Stern (x0, y0, r, rot) keine Zelle mehr beruehrt (Bisektion)."""
    hi = 1.0
    while core_cells((x0 + dx * hi, y0 + dy * hi, r, rot)).any():
        hi *= 2
    lo = 0.0
    for _ in range(24):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if core_cells((x0 + dx * mid, y0 + dy * mid, r, rot)).any() else (lo, mid)
    return hi


def curtain(cfg, f, n):
    """Vorhang: Loch in Deckgroesse auf F1 zieht geradeaus nach pull_dir, Tempo steigt in pull_accel_frac linear und
    bleibt dann (Weg s(u) = u^2/2a bzw. u - a/2, normiert), im letzten Bild vor der ersten Stufe ist es samt Auslaeufern
    (sil_reach) draussen. Groesse bleibt, Drehung laeuft weiter."""
    x0, y0, r0, rot0 = loop_star(cfg, 0)
    R = r0 * max(1.0, cover_r(x0, y0, rot0) / r0)
    u, a = pull_u(f, n), f["pull_accel_frac"]
    s = (u * u / (2 * a) if u <= a else u - a / 2) / (1 - a / 2)
    dx, dy = np.array(f["pull_dir"]) / math.hypot(*f["pull_dir"])
    rot1 = rot0 + f["pull_spin_deg"]
    D = exit_dist(x0, y0, R * (1 + f["sil_rim"]), rot1 % KE.STAR_SYM_DEG, float(dx), float(dy))
    return x0 + dx * D * s, y0 + dy * D * s, R, rot0 + f["pull_spin_deg"] * u


# ---------------------------------------------------------------- Szenen (Stil-Dicts, gecacht wie der Digitalteil)

def spark_none(c):
    c.star_m = np.zeros((c.gh, c.gw), bool)


def st_black(cfg, f):
    """Grundstil der schwarzen Szenen: Satz und Palette wie das F10-Ende, ohne Stern."""
    st = KE.orbit_state(cfg, zoom_dt(cfg, frame_at(f, f["pull_beat"])))
    dg = st["loop"]["digital"]
    st = {k: v for k, v in st.items() if k != "P_spark"}
    st.update(S=KL.S_CODES["S2"], spark_fn=spark_none, type_fn=f15_type, star=(OFF[0] / 1080, OFF[1] / 1920, 0.001))
    st["loop"] = {**st["loop"], "digital": dict(u=dg["u"], offset=list(dg["offset"]), star=list(OFF), show=None)}
    return st


def white(cfg, f):
    return S.PALS[st_black(cfg, f)["P"]]


def world(cfg, k):
    """Plakat k in den Buchstaben (KE.poster_digital: so saehe es aus, wenn das Karussell digital weiterliefe)."""
    st = KE.poster_digital(cfg, k)
    st["type_fn"] = f15_type
    return st


def scene(cfg, f, st, **kw):
    """Was f15_type zeichnet: black (Maske), light, items (sichtbare Kartenteile), gone (Bayer-Zerfall der Schrift 0..1)."""
    sc = dict(black="all", light=None, items=0, gone=0.0, pal=white(cfg, f), scale=cfg["ending"]["orbit_date_center"])
    sc.update(kw)
    return dict(st, f15=sc, f15_src=SRC)


def hole_spec(f, pose, reach):
    x, y, r, rot = pose
    return {"hole": dict(pose=[round(x, 5), round(y, 5), round(r, 5), round(rot % KE.STAR_SYM_DEG, 3)],
                         reach=reach, rim=f["sil_rim"])}


def wall(f, word):
    """Wortwand (Maske): Begriff in Zeilen ueber den ganzen Bildschirm, steht fest."""
    return {"wall": dict(word=word, margin_cells=f["wall_margin_cells"], lead_frac=f["wall_lead_frac"])}


def flicker(tb, j):
    a, b = FLICKER_PER_BEAT
    return 0.6 * math.sin(2 * math.pi * a * tb + 1.3 * j) + 0.4 * math.sin(2 * math.pi * b * tb + 2.1 * j)


def card(cfg, f, tb):
    """Tonleiter: k Stufen vorbei → step_items[k-1] Kartenteile (SPARK, KICK-OFF, Datum, Ort). Je Stufe j eine Gruppe
    [erste, letzte Zeile, Halo-Laenge, Textstufe, Halo-Helligkeit]: die Zeilen leuchten von intro_level (Rampe: glimmend
    rot) nach Weiss ein, das Halo waechst von glow_start_frac auf voll (ease-in-out), jede spaetere Stufe gibt
    glow_bump_frac dazu; Laenge atmet (breathe_*), Helligkeit flackert (flicker_frac), Zeilen versetzt. Nach der letzten
    Stufe + fade_hold_beats schrumpft und dunkelt alles in fade_beats, die Schrift zerfaellt mit (q)."""
    e = cfg["ending"]
    k = sum(tb >= s for s in f["steps"])
    q = min(max((tb - f["steps"][-1] - f["fade_hold_beats"]) / f["fade_beats"], 0.0), 1.0)
    if q >= 1:
        return scene(cfg, f, st_black(cfg, f))
    full = math.log(e["orbit_flare_max_scale"])
    grown = [smooth((tb - f["steps"][j]) / f["glow_grow_beats"]) for j in range(k)]
    groups = []
    for j in range(k):
        size = f["glow_start_frac"] + (1 - f["glow_start_frac"]) * grown[j] + f["glow_bump_frac"] * sum(grown[j + 1:])
        size *= 1 + f["breathe_frac"] * math.sin(2 * math.pi * (tb / f["breathe_beats"] + j / 3))
        level = f["intro_level"] + (1 - f["intro_level"]) * smooth((tb - f["steps"][j]) / f["intro_beats"])
        groups.append([f["step_items"][j - 1] if j else 0, f["step_items"][j], round(full * size * (1 - q), 4),
                       round(level, 4), round(1 + f["flicker_frac"] * flicker(tb, j), 4)])
    lt = dict(xy=list(e["orbit_flare_xy"]), r=round(e["orbit_flare_r_frac"] * (1 - q), 5),
              rot=round(tb * e["orbit_flare_spin_deg_per_beat"] % KE.STAR_SYM_DEG, 3), groups=groups,
              gain=round((1 - q) ** 2, 4), peak=e["orbit_flare_peak"], colors=list(e["orbit_flare_colors"]))
    return scene(cfg, f, st_black(cfg, f), light=lt, items=f["step_items"][k - 1], gone=round(q, 4))


def plan(cfg, f, n):
    """("base", n) aus dem MC3-Video | ("render", st, hole): hole = ausserhalb liegt noch das MC3-Bild."""
    n0, n2, n3 = marks(f)
    if n < n0:
        return ("base", n)
    k = math.floor(phase(cfg, f, n) + EPS)
    if n <= n2:                                                        # dunkler Spark = Maske, darin die Wortwand
        word = f["words"][sum(tb_of(f, n) >= b for b in f["words_change"])]
        pose = dark(cfg, n)
        if core_cells(pose).all():
            return ("render", scene(cfg, f, world(cfg, k), black={"not": wall(f, word)}), None)
        hs = hole_spec(f, pose, 0.0)
        st = scene(cfg, f, world(cfg, k), black={"not": {"and": [hs, wall(f, word)]}})
        return ("render", st, hs if n < base_until(cfg) else None)
    if n == n3:                                                        # Vorhang draussen (Auslaeufer auch)
        return ("render", scene(cfg, f, st_black(cfg, f)), None)
    if n < n3:                                                         # Vorhang: Loch zieht ueber die stehende Wand
        keep = {"and": [hole_spec(f, curtain(cfg, f, n), f["sil_reach"]), wall(f, f["words"][-1])]}
        return ("render", scene(cfg, f, world(cfg, k), black={"not": keep}), None)
    return ("render", card(cfg, f, tb_of(f, n)), None)


# ---------------------------------------------------------------- Zeichnen (Hooks fuer styles.render)

def wall_mask(c, p):
    """Begriff in Zeilen auf voller Satzbreite von margin bis H - margin."""
    measure = c.W - 2 * c.L["x0"]
    cap = math.floor(measure / S.width_per_cap(p["word"]) / c.px) * c.px
    lead = round(cap * p["lead_frac"] / c.px) * c.px
    top, bottom = p["margin_cells"] * c.px, c.H - p["margin_cells"] * c.px
    rows = max(1, int((bottom - top - cap) // lead) + 1)
    y0 = top + (bottom - top - (cap + (rows - 1) * lead)) / 2
    return KE.word_mask(c, [p["word"]] * rows, cap, lead, c.W / 2, y0)[0]


def hole_mask(c, p):
    """Silhouette eines Lochs an p["pose"]: Sternkoerper mit posterisiertem Rand (Bayer-Band bis rim x Radius nach
    aussen); reach > 0 nimmt die Auslaeufer des Plakat-Stils (c.st["S"]) dazu: helle Zellen seines Renders (Spritzer,
    Scherben, Schein) bis reach x Radius. Der Render allein taugt nicht: viele Stile sind innen dunkel (S33 Ringe,
    S23/S47 Kern), S31 leuchtet ein Rechteck aus (Befund 8.10. an allen 20 Stilen)."""
    x, y, r, rot = p["pose"]
    X, Y, R = x * c.W, y * c.H, r * c.W
    d = S.star_d(c, X, Y, R, rot)[0]
    m = d < 1 + p["rim"] * (1 - S.tile(S.bayer(4), (c.gh, c.gw)))
    if p["reach"] > 0:
        sub = copy.copy(c)
        sub.st, sub.L, sub.layers, sub.layer_pal = dict(c.st, rot=rot), dict(c.L, star=(X, Y, R, rot)), [], {}
        K.spark(sub)
        K._EXTRA["extra"] = []                                          # Zweitlicht der Labor-Sterne nicht ins Schwarz
        m |= sub.star_m & (d < p["reach"])
    return m


def mask(c, spec):
    """Masken-Beschreibung → Bool-Maske auf dem Zellraster."""
    if spec is None or spec == "all":
        return np.ones((c.gh, c.gw), bool)
    (op, a), = spec.items()
    if op == "not":
        return ~mask(c, a)
    if op == "and":
        return np.logical_and.reduce([mask(c, s) for s in a])
    if op == "wall":
        return wall_mask(c, a)
    if op == "hole":
        return hole_mask(c, a)
    raise ValueError(f"Maske {spec}")


def item_masks(c, sc):
    """Kartenteile 1..items als Masken (SPARK, KICK-OFF, Datum, Ort), Satz wie F10 (date_cap, mittig auf dem Spark
    hinter dem Slash), jede Zeile an ihrer Stelle im ganzen Block."""
    out = [np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))]
    ls = list(c.L["sub"])
    cap, lead = KE.date_cap(c, sc["scale"], ls)
    top = c.H / 2 - (cap + (len(ls) - 1) * lead) / 2
    out += [KE.word_mask(c, [s], cap, lead, c.W / 2, top + j * lead)[0] for j, s in enumerate(ls)]
    return out[:sc["items"]]


def streak(c, src, centre, glow):
    """Schweif wie KE.flare_layer: src GLOW_SAMPLES-mal um centre vergroessert (bis exp(glow)), Gewicht faellt nach aussen."""
    g = src.copy()
    for j in range(1, KE.GLOW_SAMPLES + 1):
        s = math.exp(glow * j / KE.GLOW_SAMPLES)
        sy = np.round(centre[0] + (c.yy - centre[0]) / s).astype(int)
        sx = np.round(centre[1] + (c.xx - centre[1]) / s).astype(int)
        ok = (sy >= 0) & (sy < c.gh) & (sx >= 0) & (sx < c.gw)
        hit = np.zeros_like(g)
        hit[ok] = src[sy[ok], sx[ok]]
        g = np.maximum(g, hit * (1 - j / (KE.GLOW_SAMPLES + 1)))
    return g


def light_layer(c, lt, items):
    """Licht je Stufe: ihre Zeilen (auf Stufe 1 dazu der Spark) als Quelle in Textstufe x Helligkeit, eigener Schweif,
    Maximum ueber die Stufen; Zeilen, die noch einleuchten, stehen selbst in der Rampe (glimmend rot → weiss), eigene
    Rampe, alles x gain (Ausklingen)."""
    X, Y = lt["xy"][0] * c.W, lt["xy"][1] * c.H
    centre = (Y / c.px - 0.5, X / c.px - 0.5)
    star = (S.star_d(c, X, Y, max(lt["r"], 1e-6) * c.W, lt["rot"])[0] < 1).astype(np.float32)
    g = np.zeros((c.gh, c.gw), np.float32)
    for j, (a, b, glow, level, bright) in enumerate(lt["groups"]):
        text = np.logical_or.reduce(items[a:b]).astype(np.float32)
        src = np.minimum(text * lt["peak"] * level * bright, 1.0)
        if j == 0:
            src = np.maximum(src, star * bright)
        g = np.maximum(np.maximum(g, streak(c, src, centre, glow)), text * level)
    g = g * lt["gain"]
    c.layer_pal["light"] = KE.ramp(c, lt["colors"])
    c.add("light", g > KE.GLOW_MIN, g)


def f15_type(c):
    """Zeichnet die Szene st["f15"]."""
    sc = c.st["f15"]
    if sc["black"]:
        c.layer_pal["dim"] = np.zeros_like(c.pal)
        c.add("dim", mask(c, sc["black"]), 0.0)
        K._EXTRA["extra"] = []
    stay = S.tile(S.bayer(4).T, (c.gh, c.gw)) >= sc["gone"]            # Schrift zerfaellt mit dem Halo
    items = [m & stay for m in item_masks(c, sc)] if sc["items"] else []
    if sc["light"]:
        light_layer(c, sc["light"], items)
    pal = S.hexpal_list(sc["pal"])
    c.layer_pal["type"] = pal
    hi = c.lvl(int((pal @ KL.LUMA).argmax()))
    done = [items[a:b] for a, b, _, level, _ in (sc["light"] or {}).get("groups", []) if level >= 1 - EPS]
    if done:                                                           # eingeleuchtete Zeilen: Weiss der Schrift
        c.add("type", np.logical_or.reduce(sum(done, [])), hi)


# ---------------------------------------------------------------- Rendern

def _job(args):
    """Bild n auf dem Zellraster; mit Loch zusaetzlich dessen Maske (MC3 liegt ausserhalb)."""
    cfg, f, n = args
    p = plan(cfg, f, n)
    if p[0] == "base":
        return n, None, None
    img = KL.render_cached(p[1], FMT, "f15")
    m = hole_mask(S.Ctx(p[1], FMT), p[2]["hole"]) if p[2] else None
    return n, np.ascontiguousarray(img[::CELL, ::CELL]), m


def frames(cfg, f, ns):
    """Bilder ns (aufsteigend) als (n, RGB voll). MC3-Bilder aus einem Decoder, gerenderte aus dem KL-Pool; solange das
    MC3-Bild den dunklen Spark zeigt (base_until), liegt es ausserhalb der Maske."""
    W, H = S.SIZES[FMT][:2]
    ps = {n: plan(cfg, f, n) for n in ns}
    it = iter(KL.pool().imap(_job, [(cfg, f, n) for n in ns if ps[n][0] != "base"], chunksize=2))
    dec, at = None, 0

    def base(n):
        nonlocal dec, at
        if dec is None:
            dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", f["base_video"], "-f", "rawvideo", "-pix_fmt",
                                    "rgb24", "-"], stdout=subprocess.PIPE)
        while True:
            img = np.frombuffer(dec.stdout.read(W * H * 3), np.uint8).reshape(H, W, 3)
            at += 1
            if at > n:
                return img

    for n in ns:
        if ps[n][0] == "base":
            img = base(n)
        else:
            m, small, hm = next(it)
            assert m == n
            img = S.up(small, CELL)
            if hm is not None:
                img = np.where(S.up(hm, CELL)[..., None], img, base(n))
        yield n, img
    if dec:
        dec.kill()


def out_dir(f):
    d = os.path.dirname(f["toml"])
    os.makedirs(d, exist_ok=True)
    return d


def song_pad(f):
    """Song mit Stille bis end_s (der Writer schneidet mit -shortest auf die kuerzere Spur)."""
    path = os.path.join(out_dir(f), "song_pad.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f["song"], "-af", f"apad=whole_dur={f['end_s']}", path],
                   check=True)
    return path


def video(cfg, f):
    path = os.path.join(out_dir(f), "preview_draft.mp4")
    if os.path.exists(path):                       # Hardlink loesen: ffmpeg -y schreibt sonst in Vorschau/<alte Version>
        os.remove(path)
    W, H = S.SIZES[FMT][:2]
    enc = V.ffmpeg_writer(path, (W, H), FPS, audio=song_pad(f), enc=V.PREVIEW_ENCODER)
    for n, img in frames(cfg, f, range(n_end(f))):
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    assert enc.wait() == 0, "ffmpeg"
    report(cfg, f, path)
    return V.publish(path, f["code"])


# ---------------------------------------------------------------- Befund am fertigen Video

def gray(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "scale=135:240", "-f", "rawvideo", "-pix_fmt",
                          "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 240, 135).astype(np.float32) / 255


def events(f):
    """Geplante Schnitte: jeder Begriffswechsel, jede Stufe. (Bild, Name)."""
    ev = [(frame_at(f, b), w) for b, w in zip(f["words_change"], f["words"][1:])]
    return ev + [(frame_at(f, s), f"Stufe {j + 1}") for j, s in enumerate(f["steps"])]


def onset(d, n):
    pre = max(float(d[n - 1]), float(np.median(d[max(n - 8, 1):n]))) + 1e-6
    return bool(d[n] >= EVENT_MIN and d[n] > EVENT_RATIO * pre), round(float(d[n] / pre), 1)


def on_beat(diffs, sil, ev, shift=0):
    """Je Schnitt: setzt er auf seinem Bild ein? Aus Schwarz heraus (Stufe 1 leuchtet sanft ein, davor bewegt sich der
    Vorhang im Median) zaehlt: Bild davor schwarz, dieses nicht."""
    out = []
    for n, name in ev:
        n += shift
        res = [onset(d, n) for d in diffs]
        from_black = sil[n - 1].mean() < 0.005 and sil[n].mean() > 0.01
        out.append((name + (" (aus Schwarz)" if from_black else ""), n, from_black or any(ok for ok, _ in res),
                    max(r for _, r in res)))
    return out


def down(m, shape, how):
    """Zellmaske auf das Raster des Befunds (shape): any = beruehrt, all = ganz drin."""
    sy, sx = m.shape[0] // shape[0], m.shape[1] // shape[1]
    b = m[:shape[0] * sy, :shape[1] * sx].reshape(shape[0], sy, shape[1], sx)
    return b.any((1, 3)) if how == "any" else b.all((1, 3))


def report(cfg, f, path):
    a = gray(path)
    shape = a.shape[1:]
    sil = (a > BLACK_LUM).astype(np.float32)
    diffs = [np.r_[0, np.abs(np.diff(a, axis=0)).mean((1, 2))], np.r_[0, np.abs(np.diff(sil, axis=0)).mean((1, 2))]]
    rows, old = on_beat(diffs, sil, events(f)), on_beat(diffs, sil, events(f), OLD_SHIFT)
    n0, n2, n3 = marks(f)
    # Maske: im ersten Bild ausserhalb = MC3, innerhalb (Kern, ohne Rand) die Woerter
    mc3 = gray(f["base_video"])[n0]
    inside = down(core_cells(dark(cfg, n0)), shape, "all")
    outside = ~binary_dilation(down(core_cells(dark(cfg, n0)), shape, "any"), iterations=3)
    d_out, d_in = float(np.abs(a[n0] - mc3)[outside].mean()), float(np.abs(a[n0] - mc3)[inside].mean())
    full = next(n for n in range(n0, n2 + 1) if core_cells(dark(cfg, n)).all())
    # Vorhang: Woerter stehen, Helles wird nur weniger. "Kein Zwerg" ist am Bild nicht trennbar (der F14-Zwerg lag in
    # Bild 250 ebenfalls an der Wandkante, Befund 8.10.), die Groesse bleibt im Code (curtain)
    wm = binary_dilation(down(wall_mask(S.Ctx(world(cfg, 0), FMT), wall(f, f["words"][-1])["wall"]), shape, "any"))
    lit = a > LIT_LUM
    stray = max(float((lit[n] & ~wm).mean()) for n in range(n2 + 1, n3))
    area = [float(lit[n].mean()) for n in range(n2, n3 + 1)]
    shrink = all(q <= p + 0.002 for p, q in zip(area, area[1:]))
    gap = float(sil[n3].mean())
    # Tonleiter: neue Zeilen leuchten ein, Halo waechst
    c = S.Ctx(st_black(cfg, f), FMT)
    its = [down(m, shape, "all") for m in item_masks(c, dict(items=4, scale=cfg["ending"]["orbit_date_center"]))]
    intro, grow = [], []
    for j, s in enumerate(f["steps"]):
        reg = np.logical_or.reduce(its[(f["step_items"][j - 1] if j else 0):f["step_items"][j]])
        ns, ni, ng = frame_at(f, s), frame_at(f, s + f["intro_beats"]), frame_at(f, s + GROW_PROBE_BEATS)
        intro.append((ns, ni, float(a[ns][reg].mean()), float(a[ni][reg].mean())))
        grow.append((ns, ng, float(sil[ns].mean()), float(sil[ng].mean())))
    tail = float(sil[round(t_beat(f, f["steps"][-1] + f["fade_hold_beats"] + f["fade_beats"]) * FPS) + 1:].mean())
    lines = [f"{f['code']}, {path}",
             f"Maske ab Bild {n0}: ausserhalb = MC3 (Abweichung {d_out:.3f}, muss < {SAME_MC3}), innen Woerter "
             f"({d_in:.3f}, muss > 0.05); dunkler Spark deckt ab Bild {full} = Beat {tb_of(f, full):.2f}",
             f"Vorhang: Helles ausserhalb der stehenden Wand max {stray * 100:.2f} % (muss < 0.5); Flaeche "
             + " ".join(f"{p * 100:.0f}" for p in area) + f" % (muss fallen: {'ja' if shrink else 'NEIN'})",
             f"Weggezogen: Helles im Bild vor Stufe 1 {gap * 100:.1f} % (muss ~0)",
             "Zeilen leuchten ein (Helligkeit der neuen Zeilen auf der Stufe → +" + f"{f['intro_beats']:g} Beat): "
             + ", ".join(f"Bild {ns} {p:.2f} → {ni} {q:.2f}" for ns, ni, p, q in intro) + f" (muss < {INTRO_RATIO:g}x)",
             "Halo waechst (Lichtflaeche auf der Stufe → +" + f"{GROW_PROBE_BEATS:g} Beat): "
             + ", ".join(f"Bild {ns} {p * 100:.1f} % → {ng} {q * 100:.1f} %" for ns, ng, p, q in grow) + " (muss steigen)",
             f"Schluss: Helles nach dem Ausklingen {tail * 100:.2f} % (muss ~0)",
             f"Schnitte auf dem Beat (> {EVENT_RATIO:g}x Vorlauf, Helligkeit oder Silhouette):"]
    lines += [f"  {'ok ' if ok else 'NEIN'} {name:<12} Bild {n} = {n / FPS:.3f} s  x{r}" for name, n, ok, r in rows]
    lines.append(f"Gegenprobe +{OLD_SHIFT} Bilder: {sum(ok for *_, ok, _ in old)}/{len(old)} ok (muss weniger sein)")
    open(os.path.join(out_dir(f), "report_draft.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return (all(r[2] for r in rows) and sum(r[2] for r in old) < len(old) and d_out < SAME_MC3 and d_in > 0.05
            and stray < 0.005 and shrink and gap < 0.005 and tail < 0.001
            and all(p < INTRO_RATIO * q for *_, p, q in intro) and all(q > p for *_, p, q in grow))


def test(cfg, f):
    ok = report(cfg, f, os.path.join(out_dir(f), "preview_draft.mp4"))
    print(f"{f['code']}: {'OK' if ok else 'FEHLER'}")
    return ok


# ---------------------------------------------------------------- Bogen

SHEET_BEATS = (3.5, 3.65, 3.8, 3.95, 4.1, 4.3, 4.6, 5.2, 6.7, 7.9, 8.05,
               8.12, 8.2, 8.27, 8.35, 8.42, 8.52, 8.65, 8.9, 9.52, 9.7, 10.27,
               10.45, 10.8, 11.3, 11.9, 12.1, 12.3)


def sheet(cfg, f):
    tw, th = 216, 384
    ns = [min(frame_at(f, b), n_end(f) - 1) for b in SHEET_BEATS]
    got = dict(frames(cfg, f, sorted(set(ns))))
    cols = 11
    rows = -(-len(ns) // cols)
    img = Image.new("RGB", (cols * tw, rows * (th + 16)), (18, 18, 18))
    dr = ImageDraw.Draw(img)
    for j, (b, n) in enumerate(zip(SHEET_BEATS, ns)):
        x, y = (j % cols) * tw, (j // cols) * (th + 16)
        img.paste(Image.fromarray(got[n]).resize((tw, th), Image.BOX), (x, y + 16))
        dr.text((x + 4, y + 2), f"Beat {b:g} = {n / FPS:.2f} s", fill=(220, 220, 220))
    path = os.path.join(out_dir(f), f"{f['code']}_sheet.png")
    img.save(path)
    return path


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    cfg, f = load(path)
    if cmd == "video":
        print(video(cfg, f))
    elif cmd == "sheet":
        print(sheet(cfg, f))
    elif cmd == "still":
        ns = sorted({min(frame_at(f, float(b)), n_end(f) - 1) for b in sys.argv[3:]})
        for n, img in frames(cfg, f, ns):
            out = os.path.join(out_dir(f), f"still_{n:03d}.png")
            Image.fromarray(img).save(out)
            print(out)
    elif cmd == "test":
        sys.exit(0 if test(cfg, f) else 1)


if __name__ == "__main__":
    main()
