#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""F16 = Ende nach Vadims Feedback zu F15 (8.10.), Foto-Phase MC3, ein Ablauf:

1. Maske (mask_beat → pull_beat): der echte dunkle Spark des MC3-Videos. Je MC3-Bild (Digitalteil auf Zweiern) sind
   die Zellen in seinem Sternkoerper Maske, die im MC3-Bild dunkel sind (mask_dark_luma), dazu der Titel dort; hellere
   gerasterte Baender des Sparks und alles ausserhalb bleiben MC3 (Vadim zu F15: "warum ein neuer Spark statt der
   echten? Mismatch, Posterization fehlt"). In der Maske die Wortwand, in den Buchstaben der Loop: solange der dunkle
   Spark auf der Bahn ist, genau sein Plakat mit hellem Spark an seiner Stelle (deckungsgleich), danach im
   Karussell-Tempo weiter, so dass im letzten Wandbild F1 steht. Ab base_until (MC3 zeigt den alten Slogan) deckt er.
2. Vorhang (pull_beat → erste Stufe): die Woerter stehen, das Loch ist der Plakat-Spark auf F1 (Silhouette im Stil des
   Plakats dahinter) und zieht mit der Geschwindigkeit der Loop-Bahn an F1 geradeaus weiter, wie die Sparks hinter den
   Woertern, bis er draussen ist (F15 war x5 so schnell).
3. Tonleiter (steps, gemessene Bass-Einsaetze C2 / D2 / D#2): je Stufe neue Kartenzeilen, roter Spark hinter dem Slash.
   Eine neue Zeile leuchtet ein (Rampe glimmend rot → weiss, intro_beats), ihr Halo waechst von klein auf
   (ease-in-out), jede spaetere Stufe gibt allen aelteren glow_bump_frac dazu, alle kriechen stetig weiter: kein Halo
   wird kleiner (F15 atmete). Nach der letzten Stufe + fade_hold_beats schrumpft und dunkelt alles Licht in fade_beats,
   die Schrift zerfaellt mit → Schwarz.

Stellschrauben: kickoff_loop/previz/review/F16/F16.toml. Licht wie das F10-Ende (kickoff_loop_end.flare_layer).
  uv run src/kickoff_loop_f16.py video|sheet|test <F16.toml>     still <F16.toml> <beat> [...]
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
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
EVENT_RATIO = 2.0      # test: ein Schnitt setzt auf seinem Bild ein: doppelt so stark wie das Bild davor und der Median davor
EVENT_MIN = 0.003      # ... und mindestens so viel mittlere Aenderung (Encoder-Rauschen im Standbild ~0.0002)
BLACK_LUM = 0.03       # Silhouette = Zellen ueber Schwarz
LIT_LUM = 0.10         # test "Woerter stehen": sicher hell (Encoder-Saum an Buchstabenkanten liegt darunter)
OLD_SHIFT = 3          # Gegenprobe: dieselben Schnitte 3 Bilder spaeter
GROW_PROBE_BEATS = 0.6 # test "Halo waechst": Lichtflaeche so lange nach der Stufe gegen das Bild der Stufe (vor der naechsten)
INTRO_RATIO = 0.6      # test "leuchtet ein": neue Zeile auf ihrer Stufe hoechstens so hell wie nach intro_beats
SAME_MC3 = 0.02        # test "Maske": ausserhalb mittlere Abweichung vom MC3-Bild hoechstens (Encoder), innen mindestens 0.05
NEVER_LESS = 0.003     # test "Halo nie kleiner": Lichtflaeche faellt von Bild zu Bild hoechstens so viel (Encoder, Korn)


# ---------------------------------------------------------------- Konfiguration und Raster

def main_root():
    """Hauptcheckout (Vorschau, Songs und Cache liegen nur dort, gitignored), auch aus einem Worktree."""
    git = subprocess.run(["git", "-C", KL.ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True).stdout.strip()
    return os.path.dirname(git) if git else KL.ROOT


def load(path, master=False):
    """master: Basisvideo ohne _draft (preview --master, Digitalteil auf Einern), x264, Ausgabe preview.mp4."""
    f = tomllib.load(open(path, "rb"))["f16"]
    f["master"] = master
    f["code"], f["toml"] = os.path.splitext(os.path.basename(path))[0], os.path.abspath(path)
    cfg = KL.load(os.path.join(KL.ROOT, f["base_toml"]))
    g = json.load(open(os.path.join(KL.ROOT, f["grid"])))
    f["bar1"], f["beat"] = g["in_s"] - f["song_start_s"], g["beat_s"]   # Taktstrich 1 auf der Timeline, Beatlaenge
    root = main_root()
    f["base_video"], f["song"] = (os.path.join(root, f[k]) for k in ("base_video", "song"))
    if master:
        f["base_video"] = f["base_video"].replace("_draft.mp4", ".mp4")
        cfg["f16_base_step"] = 1
    ch = f["words_change"]
    assert len(ch) == len(f["words"]) - 1 and ch == sorted(ch), "words_change: je Begriff nach dem ersten ein Beat, steigend"
    assert f["mask_beat"] < ch[0] and ch[-1] < f["pull_beat"] < f["steps"][0], "mask_beat < words_change < pull_beat < steps"
    assert len(f["steps"]) == len(f["step_items"]), "steps / step_items"
    assert not f.get("wall_colorways") or len(f["wall_colorways"]) == len(f["words"]), "wall_colorways: eine je Begriff"
    assert f.get("wall_hold_frames", 1) >= 1 and 0 < f.get("wall_width_frac", 1) <= 1, "wall_hold_frames / wall_width_frac"
    assert not f.get("wall_style") or f["wall_style"] in KL.S_CODES, f"wall_style {f.get('wall_style')} unbekannt"
    assert 0 <= f["intro_level"] < 1 and f["intro_beats"] > 0 and f["glow_grow_beats"] > 0, "intro_* / glow_grow_beats"
    assert os.path.exists(f["song"]) and os.path.exists(f["base_video"]), "Song oder MC3-Video fehlt"
    n0, n2, n3 = marks(f)
    assert n0 < switch_frame(cfg, f) < n2, "der dunkle Spark verlaesst die Bahn nicht zwischen mask_beat und pull_beat"
    need = curtain_frames(cfg, f)
    assert need <= n3 - n2, (f"Vorhang braucht {need} Bilder im Loop-Tempo, hat {n3 - n2}: pull_beat <= "
                             f"{tb_of(f, n3 - need) - 1 / (f['beat'] * FPS):.2f}")
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
    """Eckbilder: erstes mit Maske, letztes der Wortwand (F1), letztes des Vorhangs (Loch draussen, schwarz)."""
    return frame_at(f, f["mask_beat"]), frame_at(f, f["pull_beat"]) - 1, frame_at(f, f["steps"][0]) - 1


def zoom_end(cfg):
    return round(cfg["music"]["grid"]["burst_s"] * FPS)


def base_step(cfg):
    """Digitalteil des Basisvideos: Entwurf auf Zweiern (V.DRAFT_STEP), Master auf Einern (load setzt es)."""
    return cfg.get("f16_base_step", V.DRAFT_STEP)


def mc3_dt(cfg, n):
    """Zeit des Digitalteils, die MC3-Bild n zeigt (kickoff_loop_video.digital_frames, auf base_step)."""
    k = n - zoom_end(cfg)
    return (k - k % base_step(cfg)) / FPS


def mc3_pair(cfg, n):
    """Erstes Bild des Zweiers von n (beide zeigen denselben Render; die Maske kommt aus diesem, sonst flackert sie mit
    dem Encoder-Rauschen)."""
    k = n - zoom_end(cfg)
    return zoom_end(cfg) + k - k % base_step(cfg)


def base_until(cfg):
    """Erstes Bild, in dem das MC3-Video den blauen Slogan (F9/F10) zeigt: ab da ist ausserhalb des Sparks Schwarz."""
    return round(cfg["music"]["grid"]["burst_s"] * FPS + cfg["ending"]["orbit_pre_at_beats"] * KE.beat(cfg) * FPS)


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- Bahn: dunkler Spark, Loop in den Buchstaben, Vorhang

def loop_star(cfg, phase):
    """Loop-Stern bei Bahnphase phase (Frames) im 9:16-Bild, umgerechnet wie KE.poster_digital."""
    W, H = S.SIZES[FMT][:2]
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = V.digital_offset(cfg)
    x, y, r, rot = KL.orbit(cfg, phase)
    return (ox + x * pw) / W, (oy + y * ph) / H, r * pw / W, rot


def dark(cfg, n):
    """Der dunkle Spark in MC3-Bild n (Bildanteile)."""
    W, H = S.SIZES[FMT][:2]
    x, y, R, rot = KE.orbit_state(cfg, mc3_dt(cfg, n))["loop"]["digital"]["star"]
    return x / W, y / H, R / W, rot


def core_cells(pose):
    """Sternkoerper auf dem Zellraster (Formel wie styles.star_d, Zellmitten wie styles.Ctx)."""
    W, H = S.SIZES[FMT][:2]
    x, y, r, rot = pose
    gy, gx = np.mgrid[0:H // CELL, 0:W // CELL].astype(np.float32)
    dx, dy = (gx + 0.5) * CELL - x * W, (gy + 0.5) * CELL - y * H
    return np.hypot(dx, dy) < star_r(dx, dy, rot % KE.STAR_SYM_DEG) * r * W


def switch_frame(cfg, f):
    """Erstes Bild ab mask_beat, in dem der dunkle Spark die Bahn verlaesst (MC3 taucht in ihn ein)."""
    n = marks(f)[0]
    while KE.orbit_star(cfg, mc3_dt(cfg, n))["loop"]:
        n += 1
    return n


def inner(cfg, f):
    """(Bild, Phase, Tempo) des Loops in den Buchstaben ab dem Verlassen der Bahn: startet auf der Phase des dunklen
    Sparks, Tempo ~Karussell, so dass im letzten Wandbild F1 steht (naechstes Vielfaches des Umlaufs)."""
    ns, n2 = switch_frame(cfg, f), marks(f)[1]
    p0 = KE.orbit_phase(cfg, mc3_dt(cfg, ns))
    rate = cfg["loop"]["changes_per_bar"] / 4 / f["beat"] / FPS          # Plakate pro Bild (T16)
    N = KL.count(cfg)
    target = round((p0 + rate * (n2 - ns)) / N) * N
    return ns, p0, (target - p0) / (n2 - ns)


def phase(cfg, f, n):
    """Phase des Loops in den Buchstaben ab dem Verlassen der Bahn (davor zeigt er das Plakat des dunklen Sparks). F18
    (Vadim 9.10.: "etwas mehr posterised"): steht je wall_hold_frames Bilder, die Stufen sind am letzten Wandbild
    verankert (dort steht F1, der Vorhang setzt daran an)."""
    ns, p0, rate = inner(cfg, f)
    n = max(ns, n - (n - marks(f)[1]) % f.get("wall_hold_frames", 1))
    return p0 + rate * (n - ns)


def curtain_motion(cfg, f):
    """Vorhang: Start = Plakat-Spark auf F1, je Plakat des Loops in den Buchstaben ein Schritt mit Weg + Drehung der
    Loop-Bahn an F1 (7.5 Grad). F17 (Vadim 8.10. zu F16: "nicht aligned, dreht sich mehr als der Loop"): das Loch fuhr
    jedes Bild stufenlos, der Loop dahinter springt je Plakat auf seiner gekruemmten Bahn; jetzt springen beide zusammen."""
    x0, y0, r0, rot0 = loop_star(cfg, 0)
    xa, ya, _, ra = loop_star(cfg, -0.5)
    xb, yb, _, rb = loop_star(cfg, 0.5)
    return (x0, y0, r0, rot0), (xb - xa, yb - ya), rb - ra


def curtain(cfg, f, n):
    (x0, y0, r0, rot0), (vx, vy), spin = curtain_motion(cfg, f)
    m = math.floor(phase(cfg, f, n) + EPS) - math.floor(phase(cfg, f, marks(f)[1]) + EPS)   # Plakate seit F1
    return x0 + vx * m, y0 + vy * m, r0, rot0 + spin * m


def lift(P, frac):
    """Palette "loop:RRGGBB..." mit jeder Stufe um frac x (1 - Helligkeit / hellste) zum hellsten Ton gemischt: dunkle
    Stufen werden heller, die hellste bleibt. Befund F17: in Weiss/Rot/Blau ist der Stern dunkelblau, als Riesenstern
    auf F1 standen die Buchstaben dunkel auf dem schwarzen Spark."""
    hx = P.split(":")[1]
    cols = np.array([[int(hx[i + j:i + j + 2], 16) for j in (0, 2, 4)] for i in range(0, len(hx), 6)], np.float64)
    lum = cols @ LUMA
    out = cols + (cols[lum.argmax()] - cols) * (frac * (1 - lum / lum.max()))[:, None]
    hexes = ["#" + "".join(f"{round(v):02X}" for v in c) for c in out]
    name = "loop:" + "".join(h[1:] for h in hexes)
    S.PALS[name] = hexes                            # in jedem Prozess eintragen wie KL.palette (macOS spawnt Worker)
    return name


def wall_colors(cfg, f, st, word):
    """Loop in den Buchstaben, ruhig und lesbar. F17 (Vadim 8.10.: "nicht so viele Hintergrundfarben"): je Begriff eine
    feste Colorway (wall_colorways = Plakat je Begriff), angehoben um wall_lift_frac. F18 (Vadim 9.10.: "weniger Effekte,
    nicht der gesamte Canvas aendert sich, Hintergrund ein Standardgradient"): Stil wall_style fuer alle (Befund: jeder
    Labor-Stil aendert 26-89 % der Flaeche ausserhalb seines Sterns) auf linearem Grund ohne Tropfen."""
    if f.get("wall_colorways"):
        k = f["wall_colorways"][f["words"].index(word)]
        P = k if str(k).startswith("loop:") else KL.poster_style(cfg, int(str(k).lstrip("~")))["P"]   # "loop:..." = eigene
        if str(k).startswith("~"):              # "~N" = Palette von Plakat N umgedreht (F19: bunte Stufen werden der Grund)
            hx = P.split(":")[1]
            P = "loop:" + "".join(hx[i:i + 6] for i in range(len(hx) - 6, -1, -6))
        st["P"] = lift(P, f.get("wall_lift_frac", 0.0))
    if f.get("wall_style"):
        st["S"] = KL.S_CODES[f["wall_style"]]
        st["ground"] = dict(st["ground"], mode="linear", melt_cells=0)
    return st


@functools.lru_cache(maxsize=None)
def _curtain_frames(key):
    cfg, f = key.cfg, key.f
    n2 = marks(f)[1]
    wm = wall_mask(S.Ctx(world(cfg, 0), FMT), wall(f, f["words"][-1])["wall"])
    n = n2 + 1
    while True:
        x, y, r, rot = curtain(cfg, f, n)
        if not (core_cells((x, y, r * (1 + f["sil_rim"]), rot)) & wm).any():
            return n - n2
        n += 1


class _Key:
    """Haelt cfg/f fuer lru_cache (Dicts sind nicht hashbar), gleich je Config-Datei."""
    def __init__(self, cfg, f):
        self.cfg, self.f = cfg, f

    def __hash__(self):
        return hash(self.f["toml"])

    def __eq__(self, o):
        return self.f["toml"] == o.f["toml"]


def curtain_frames(cfg, f):
    """Bilder, bis Koerper + Rand des Vorhang-Lochs keinen Buchstaben mehr beruehren (die Wand hat Satzrand: am Bildrand
    gemessen war er 7 Bilder vor Schluss unsichtbar, Befund 8.10.)."""
    return _curtain_frames(_Key(cfg, f))


# ---------------------------------------------------------------- Szenen (Stil-Dicts, gecacht wie der Digitalteil)

def spark_none(c):
    c.star_m = np.zeros((c.gh, c.gw), bool)


def st_black(cfg, f):
    """Grundstil der schwarzen Szenen: Satz und Palette wie das F10-Ende, ohne Stern."""
    st = KE.orbit_state(cfg, (frame_at(f, f["pull_beat"]) - zoom_end(cfg)) / FPS)
    dg = st["loop"]["digital"]
    st = {k: v for k, v in st.items() if k != "P_spark"}
    st.update(S=KL.S_CODES["S2"], spark_fn=spark_none, type_fn=f16_type, star=(OFF[0] / 1080, OFF[1] / 1920, 0.001))
    st["loop"] = {**st["loop"], "digital": dict(u=dg["u"], offset=list(dg["offset"]), star=list(OFF), show=None)}
    return st


def white(cfg, f):
    return S.PALS[st_black(cfg, f)["P"]]


def world(cfg, k, pose=None):
    """Plakat k in den Buchstaben (KE.poster_digital: so saehe es aus, wenn das Karussell digital weiterliefe). pose:
    sein Spark sitzt dort (Bildanteile), sonst auf seinem Bahnframe."""
    st = KE.poster_digital(cfg, k)
    if pose:
        W, H = S.SIZES[FMT][:2]
        x, y, r, rot = pose
        st["loop"] = {**st["loop"], "digital": dict(st["loop"]["digital"], star=(x * W, y * H, r * W, rot))}
        st["star"], st["rot"] = (x, y, r), rot
    st["type_fn"] = f16_type
    return st


def inner_world(cfg, f, n):
    """Plakat in den Buchstaben in Bild n: auf der Bahn das des dunklen Sparks mit hellem Spark genau an seiner Stelle,
    danach der Loop (inner)."""
    if n < switch_frame(cfg, f):
        return world(cfg, KE.orbit_poster(cfg, mc3_dt(cfg, n)), dark(cfg, n))
    return world(cfg, math.floor(phase(cfg, f, n) + EPS))


def scene(cfg, f, st, **kw):
    """Was f16_type zeichnet: black (Maske), light, items (sichtbare Kartenteile), gone (Bayer-Zerfall der Schrift 0..1)."""
    sc = dict(black="all", light=None, items=0, gone=0.0, pal=white(cfg, f), scale=cfg["ending"]["orbit_date_center"],
              drop=f.get("card_drop_chars", ""))
    sc.update(kw)
    return dict(st, f16=sc, f16_src=SRC)


def hole_spec(f, pose):
    x, y, r, rot = pose
    return {"hole": dict(pose=[round(x, 5), round(y, 5), round(r, 5), round(rot % KE.STAR_SYM_DEG, 3)],
                         reach=f["sil_reach"], rim=f["sil_rim"])}


def wall(f, word):
    """Wortwand (Maske): Begriff in Zeilen ueber den ganzen Bildschirm, steht fest."""
    return {"wall": dict(word=word, margin_cells=f["wall_margin_cells"], lead_frac=f["wall_lead_frac"],
                         width_frac=f.get("wall_width_frac", 1.0))}


def card(cfg, f, tb):
    """Tonleiter: k Stufen vorbei → step_items[k-1] Kartenteile (SPARK, KICK-OFF, Datum, Ort). Je Stufe j eine Gruppe
    [erste, letzte Zeile, Halo-Laenge, Textstufe]: die Zeilen leuchten von intro_level (Rampe: glimmend rot) nach Weiss
    ein, das Halo waechst von glow_start_frac auf voll (ease-in-out), jede spaetere Stufe gibt glow_bump_frac dazu, alle
    kriechen mit glow_creep_per_beat weiter (nur wachsen). Nach der letzten Stufe + fade_hold_beats schrumpft und dunkelt
    alles in fade_beats, die Schrift zerfaellt mit (q)."""
    e = cfg["ending"]
    k = sum(tb >= s for s in f["steps"])
    q = min(max((tb - f["steps"][-1] - f["fade_hold_beats"]) / f["fade_beats"], 0.0), 1.0)
    if q >= 1:
        return scene(cfg, f, st_black(cfg, f))
    full = math.log(e["orbit_flare_max_scale"])
    grown = [smooth((tb - f["steps"][j]) / f["glow_grow_beats"]) for j in range(k)]
    groups = []
    for j in range(k):
        size = (f["glow_start_frac"] + (1 - f["glow_start_frac"]) * grown[j] + f["glow_bump_frac"] * sum(grown[j + 1:])
                + f["glow_creep_per_beat"] * (min(tb, f["steps"][-1] + f["fade_hold_beats"]) - f["steps"][j]))
        level = f["intro_level"] + (1 - f["intro_level"]) * smooth((tb - f["steps"][j]) / f["intro_beats"])
        groups.append([f["step_items"][j - 1] if j else 0, f["step_items"][j], round(full * size * (1 - q), 4),
                       round(level, 4)])
    lt = dict(xy=list(e["orbit_flare_xy"]), r=round(e["orbit_flare_r_frac"] * (1 - q), 5),
              rot=round(tb * e["orbit_flare_spin_deg_per_beat"] % KE.STAR_SYM_DEG, 3), groups=groups,
              gain=round((1 - q) ** 2, 4), peak=e["orbit_flare_peak"], colors=list(e["orbit_flare_colors"]))
    return scene(cfg, f, st_black(cfg, f), light=lt, items=f["step_items"][k - 1], gone=round(q, 4))


def plan(cfg, f, n):
    """("base", n) aus dem MC3-Video | ("render", st, mc3): mc3 = ausserhalb der Maske des dunklen Sparks liegt MC3."""
    n0, n2, n3 = marks(f)
    if n < n0:
        return ("base", n)
    if n <= n2:                                                        # dunkler Spark = Maske, darin die Wortwand
        word = f["words"][sum(tb_of(f, n) >= b for b in f["words_change"])]
        st = wall_colors(cfg, f, inner_world(cfg, f, n), word)
        return ("render", scene(cfg, f, st, black={"not": wall(f, word)}), n < base_until(cfg))
    if n == n3:                                                        # Vorhang draussen (Auslaeufer auch)
        return ("render", scene(cfg, f, st_black(cfg, f)), False)
    if n < n3:                                                         # Vorhang: Loch zieht ueber die stehende Wand
        pose = curtain(cfg, f, n)                                      # Spark des Plakats sitzt genau im Loch
        keep = {"and": [hole_spec(f, pose), wall(f, f["words"][-1])]}
        st = wall_colors(cfg, f, world(cfg, math.floor(phase(cfg, f, n) + EPS), pose), f["words"][-1])
        return ("render", scene(cfg, f, st, black={"not": keep}), False)
    return ("render", card(cfg, f, tb_of(f, n) + f.get("step_lead_beats", 0.0)), False)


# ---------------------------------------------------------------- Zeichnen (Hooks fuer styles.render)

def wall_mask(c, p):
    """Begriff in Zeilen auf voller Satzbreite von margin bis H - margin."""
    measure = (c.W - 2 * c.L["x0"]) * p.get("width_frac", 1.0)          # F18: schmaler = kleiner, mehr Luft
    cap = math.floor(measure / S.width_per_cap(p["word"]) / c.px) * c.px
    lead = round(cap * p["lead_frac"] / c.px) * c.px
    top, bottom = p["margin_cells"] * c.px, c.H - p["margin_cells"] * c.px
    rows = max(1, int((bottom - top - cap) // lead) + 1)
    y0 = top + (bottom - top - (cap + (rows - 1) * lead)) / 2
    return KE.word_mask(c, [p["word"]] * rows, cap, lead, c.W / 2, y0)[0]


def hole_mask(c, p):
    """Silhouette des Vorhang-Lochs an p["pose"]: Sternkoerper mit posterisiertem Rand (Bayer-Band bis rim x Radius) plus
    die Auslaeufer des Plakat-Stils (c.st["S"]): helle Zellen seines Renders (Spritzer, Scherben, Schein) bis reach x
    Radius. Der Render allein taugt nicht: viele Stile sind innen dunkel (S33 Ringe, S23/S47 Kern), S31 leuchtet ein
    Rechteck aus (Befund 8.10. an allen 20 Stilen)."""
    x, y, r, rot = p["pose"]
    X, Y, R = x * c.W, y * c.H, r * c.W
    d = S.star_d(c, X, Y, R, rot)[0]
    m = d < 1 + p["rim"] * (1 - S.tile(S.bayer(4), (c.gh, c.gw)))
    sub = copy.copy(c)
    sub.st, sub.L, sub.layers, sub.layer_pal = dict(c.st, rot=rot), dict(c.L, star=(X, Y, R, rot)), [], {}
    K.spark(sub)
    K._EXTRA["extra"] = []                                              # Zweitlicht der Labor-Sterne nicht ins Schwarz
    return m | (sub.star_m & (d < p["reach"]))


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


@functools.lru_cache(maxsize=1)
def _title_cells(key):
    c = S.Ctx(world(key.cfg, 0), FMT)
    return np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))


def dark_mask(cfg, f, n, img):
    """Maske des echten dunklen Sparks in Bild n aus dem MC3-Bild img (erstes Bild seines Zweiers): Zellen in seinem
    Sternkoerper, die dunkler als mask_dark_luma sind, dazu der Titel dort (er kippt ueber dem Spark hell)."""
    W, H = S.SIZES[FMT][:2]
    lum = (img.astype(np.float32) @ LUMA / 255).reshape(H // CELL, CELL, W // CELL, CELL).mean((1, 3))
    title = _title_cells(_Key(cfg, f))
    if f.get("mask_title_glow_cells"):         # F19 (Vadim 9.10.: "blaues Ghost-Halo am ersten Masken-Spark"): das Gluehen
        title = binary_dilation(title, iterations=f["mask_title_glow_cells"])   # um den MC3-Titel geht mit in die Maske
    return core_cells(dark(cfg, n)) & ((lum < f["mask_dark_luma"]) | title)


def item_masks(c, sc):
    """Kartenteile 1..items als Masken (SPARK, KICK-OFF, Datum, Ort), Satz wie F10 (date_cap, mittig auf dem Spark
    hinter dem Slash), jede Zeile an ihrer Stelle im ganzen Block."""
    out = [np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))]
    ls = list(c.L["sub"])
    if S.SOCIAL:                                   # Social-Fassung: Ort im Endbild HPI (die Fotos zeigen D-SCHOOL)
        ls[-1] = S.SOCIAL_END_WHERE
    cap, lead = KE.date_cap(c, sc["scale"], ls)
    top = c.H / 2 - (cap + (len(ls) - 1) * lead) / 2
    out += [KE.word_mask(c, [s], cap, lead, c.W / 2, top + j * lead)[0] & ~drop_cells(c, s, cap, top + j * lead,
                                                                                       sc.get("drop", ""))
            for j, s in enumerate(ls)]
    return out[:sc["items"]]


def drop_cells(c, line, cap, top, chars):
    """Zellen der Zeichen aus chars in der Zeile, gesetzt wie KE.word_mask (mittig, an der Tinte nachgesetzt): Zeile bis
    einschliesslich Zeichen minus Zeile davor, beide an derselben Stelle. F18 (Vadim 9.10.: "Slash weg, 14.10. und
    17 Uhr am gleichen Punkt"): der Rest bleibt, wo er stand."""
    out = np.zeros((c.gh, c.gw), bool)
    if not any(ch in chars for ch in line):
        return out
    cx, base = c.W / 2, round((top + cap) / c.px) * c.px
    x = cx - S.width_per_cap(line) * cap / 2
    m = S.line_mask(line, "clash", cap, base, x, c.px, (c.gh, c.gw))
    xs = np.nonzero(m.any(0))[0]
    if len(xs) and xs[0] > 0 and xs[-1] < c.gw - 1:
        x += cx - (xs[0] + xs[-1] + 1) / 2 * c.px
    for i, ch in enumerate(line):
        if ch in chars:
            out |= (S.line_mask(line[:i + 1], "clash", cap, base, x, c.px, (c.gh, c.gw))
                    & ~S.line_mask(line[:i], "clash", cap, base, x, c.px, (c.gh, c.gw)))
    return out


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
    """Licht je Stufe: ihre Zeilen (auf Stufe 1 dazu der Spark) als Quelle in Textstufe, eigener Schweif, Maximum ueber
    die Stufen; Zeilen, die noch einleuchten, stehen selbst in der Rampe (glimmend rot → weiss), alles x gain."""
    X, Y = lt["xy"][0] * c.W, lt["xy"][1] * c.H
    centre = (Y / c.px - 0.5, X / c.px - 0.5)
    star = (S.star_d(c, X, Y, max(lt["r"], 1e-6) * c.W, lt["rot"])[0] < 1).astype(np.float32)
    g = np.zeros((c.gh, c.gw), np.float32)
    for j, (a, b, glow, level) in enumerate(lt["groups"]):
        text = np.logical_or.reduce(items[a:b]).astype(np.float32)
        src = text * lt["peak"] * level
        if j == 0:
            src = np.maximum(src, star)
        g = np.maximum(np.maximum(g, streak(c, src, centre, glow)), text * level)
    g = g * lt["gain"]
    c.layer_pal["light"] = KE.ramp(c, lt["colors"])
    c.add("light", g > KE.GLOW_MIN, g)


def f16_type(c):
    """Zeichnet die Szene st["f16"]."""
    sc = c.st["f16"]
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
    done = [items[a:b] for a, b, _, level in (sc["light"] or {}).get("groups", []) if level >= 1 - EPS]
    if done:                                                           # eingeleuchtete Zeilen: Weiss der Schrift
        c.add("type", np.logical_or.reduce(sum(done, [])), hi)


# ---------------------------------------------------------------- Rendern

def _job(args):
    cfg, f, n = args
    p = plan(cfg, f, n)
    if p[0] == "base":
        return n, None
    return n, np.ascontiguousarray(KL.render_cached(p[1], FMT, "f16")[::CELL, ::CELL])


class MC3:
    """MC3-Bilder in aufsteigender Folge aus einem Decoder, die letzten zwei gemerkt (Zweier: die Maske braucht das erste)."""
    def __init__(self, path):
        self.path, self.dec, self.at, self.keep = path, None, 0, {}

    def __call__(self, n):
        W, H = S.SIZES[FMT][:2]
        if self.dec is None:
            self.dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", self.path, "-f", "rawvideo", "-pix_fmt", "rgb24",
                                         "-"], stdout=subprocess.PIPE)
        while self.at <= n:
            self.keep = {k: v for k, v in self.keep.items() if k >= self.at - 2}
            self.keep[self.at] = np.frombuffer(self.dec.stdout.read(W * H * 3), np.uint8).reshape(H, W, 3)
            self.at += 1
        return self.keep[n]

    def close(self):
        if self.dec:
            self.dec.kill()


def frames(cfg, f, ns):
    """Bilder ns (aufsteigend) als (n, RGB voll): MC3 vor der Maske, gerenderte aus dem KL-Pool; solange MC3 den dunklen
    Spark zeigt, liegt die Wortwand nur in seiner Maske (dark_mask), ausserhalb MC3."""
    ps = {n: plan(cfg, f, n) for n in ns}
    it = iter(KL.pool().imap(_job, [(cfg, f, n) for n in ns if ps[n][0] != "base"], chunksize=2))
    mc3 = MC3(f["base_video"])
    for n in ns:
        if ps[n][0] == "base":
            img = mc3(n)
        else:
            m, small = next(it)
            assert m == n
            img = S.up(small, CELL)
            if ps[n][2]:
                base, pair = mc3(n), mc3(mc3_pair(cfg, n))
                img = np.where(S.up(dark_mask(cfg, f, n, pair), CELL)[..., None], img, base)
        yield n, img
    mc3.close()


def out_dir(f):
    d = os.path.dirname(f["toml"])
    os.makedirs(d, exist_ok=True)
    return d


SR = 48000      # Audio-Abtastrate der Vorschau (ffmpeg dekodiert/kodiert darauf)
DUCK_S = 0.3    # Huellkurve fuers Ducking des Nachhalls: RMS ueber so viele Sekunden (~ein Achtel bei IGOR)


def song_pad(f):
    """Song bis end_s (der Writer schneidet mit -shortest auf die kuerzere Spur). F17 (Vadim 8.10.: "hoert sich am Ende
    so leer an, ganz subtil laenger"): Nachhall aus Rauschen mit exponentiellem Abfall (tail_rt60_s, tiefpass
    tail_lowpass_hz, Stereo dekorreliert), tail_wet_db unter den ganzen Song gemischt; der letzte Ton klingt aus statt
    abzureissen. Ohne tail_rt60_s nur Stille wie F16."""
    import scipy.signal as sig
    path = os.path.join(out_dir(f), "song_pad.wav")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f["song"], "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    x = np.pad(x, ((0, max(0, round(f["end_s"] * SR) - len(x))), (0, 0)))
    if f.get("tail_rt60_s"):
        t = np.arange(round(f["tail_rt60_s"] * SR)) / SR
        ir = np.random.default_rng(1).normal(size=(len(t), 2)) * np.exp(-6.91 * t / f["tail_rt60_s"])[:, None]
        ir = sig.sosfilt(sig.butter(2, f["tail_lowpass_hz"], fs=SR, output="sos"), ir, axis=0)
        ir /= np.sqrt((ir ** 2).sum(0))                                 # Energie 1: Hall so laut wie der Song, dann wet_db
        wet = sig.fftconvolve(x, ir, axes=0)[:len(x)]
        # Ducking: Hall nur, wo der Song leise wird (Huellkurve DUCK_S), sonst bliebe kein Platz bis 0 dBFS (F17 erst:
        # ganzer Song 3 dB leiser gerechnet)
        env = np.sqrt(sig.fftconvolve(x.mean(1) ** 2, np.ones(round(DUCK_S * SR)) / round(DUCK_S * SR), mode="same").clip(0))
        duck = (1 - env / env.max()) ** 2
        x = x + wet * 10 ** (f["tail_wet_db"] / 20) * duck[:, None]
        x /= max(1.0, np.abs(x).max() / 0.999)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-i", "-", path],
                   input=x.astype(np.float32).tobytes(), check=True)
    return path


def preview_path(f):
    return os.path.join(out_dir(f), "preview.mp4" if f["master"] else "preview_draft.mp4")


def video(cfg, f):
    path = preview_path(f)
    if os.path.exists(path):                       # Hardlink loesen: ffmpeg -y schreibt sonst in Vorschau/<alte Version>
        os.remove(path)
    W, H = S.SIZES[FMT][:2]
    enc = V.ffmpeg_writer(path, (W, H), FPS, audio=song_pad(f), enc=V.MASTER_ENCODER if f["master"] else V.PREVIEW_ENCODER)
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
    lead = f.get("step_lead_beats", 0.0)                 # Stufen setzen so viel frueher an (F17), fruehestens nach dem Vorhang
    return ev + [(max(frame_at(f, s - lead), marks(f)[2] + 1), f"Stufe {j + 1}") for j, s in enumerate(f["steps"])]


def onset(d, n):
    pre = max(float(d[n - 1]), float(np.median(d[max(n - 8, 1):n]))) + 1e-6
    return bool(d[n] >= EVENT_MIN and d[n] > EVENT_RATIO * pre), round(float(d[n] / pre), 1)


def on_beat(diffs, sil, ev, shift=0):
    """Je Schnitt: setzt er auf seinem Bild ein? Aus Schwarz heraus (Stufe 1 leuchtet sanft ein) zaehlt: Bild davor
    schwarz, dieses nicht."""
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
    # Maske: Zweier (gleiche Maske je Paar), im ersten Bild ausserhalb = MC3, in der Maske die Woerter
    mc3 = MC3(f["base_video"])
    probe = [n for n in range(n0, base_until(cfg)) if mc3_pair(cfg, n) == n]
    d_out, d_in, pairs = [], [], 0
    g3 = gray(f["base_video"])
    for n in probe:
        m = dark_mask(cfg, f, n, mc3(n))
        pairs += bool(np.array_equal(m, dark_mask(cfg, f, n + 1, mc3(mc3_pair(cfg, n + 1)))))
        inside, outside = down(m, shape, "all"), ~binary_dilation(down(m, shape, "any"), iterations=2)
        d_out.append(float(np.abs(a[n] - g3[n])[outside].mean()))
        if inside.any():
            d_in.append(float(np.abs(a[n] - g3[n])[inside].mean()))
    mc3.close()
    # Vorhang: Woerter stehen (Helles nur in der Wand), Sichtbares nur im Loch (Koerper x sil_reach); die Flaeche selbst
    # schwankt mit der Helligkeit der Plakate in den Buchstaben (Befund 8.10.: 52 → 55 %), daher kein "faellt"
    wm = binary_dilation(down(wall_mask(S.Ctx(world(cfg, 0), FMT), wall(f, f["words"][-1])["wall"]), shape, "any"))
    lit = a > LIT_LUM
    stray = max(float((lit[n] & ~wm).mean()) for n in range(n2 + 1, n3))
    area = [float(sil[n].mean()) for n in range(n2, n3 + 1)]
    outside = 0.0
    for n in range(n2 + 1, n3):
        x, y, r, rot = curtain(cfg, f, n)
        hole = binary_dilation(down(core_cells((x, y, r * f["sil_reach"], rot)), shape, "any"), iterations=2)
        outside = max(outside, float(((sil[n] > 0) & ~hole).mean()))
    gap = float(sil[n3].mean())
    # Tonleiter: neue Zeilen leuchten ein, Halo waechst, wird nie kleiner
    c = S.Ctx(st_black(cfg, f), FMT)
    its = [down(m, shape, "all") for m in item_masks(c, dict(items=4, scale=cfg["ending"]["orbit_date_center"]))]
    intro, grow = [], []
    for j, s in enumerate(f["steps"]):
        reg = np.logical_or.reduce(its[(f["step_items"][j - 1] if j else 0):f["step_items"][j]])
        ns, ni, ng = frame_at(f, s), frame_at(f, s + f["intro_beats"]), frame_at(f, s + GROW_PROBE_BEATS)
        intro.append((ns, ni, float(a[ns][reg].mean()), float(a[ni][reg].mean())))
        grow.append((ns, ng, float(sil[ns].mean()), float(sil[ng].mean())))
    fade0 = frame_at(f, f["steps"][-1] + f["fade_hold_beats"] - f.get("step_lead_beats", 0.0))
    halo = [float(sil[n].mean()) for n in range(frame_at(f, f["steps"][0]), fade0)]
    drop = max(p - q for p, q in zip(halo, halo[1:]))
    tail = float(sil[round(t_beat(f, f["steps"][-1] + f["fade_hold_beats"] + f["fade_beats"]) * FPS) + 1:].mean())
    lines = [f"{f['code']}, {path}",
             f"Maske ab Bild {n0} (echter dunkler Spark, Basis auf {'Einern' if base_step(cfg) == 1 else 'Zweiern'}, Paare gleich nur bei Zweiern): "
             f"Paare gleich {pairs}/{len(probe)}, ausserhalb "
             f"= MC3 (Abweichung max {max(d_out):.3f}, muss < {SAME_MC3}), in der Maske Woerter (min {min(d_in):.3f}, "
             f"muss > 0.05); Loop in den Buchstaben ab Bild {switch_frame(cfg, f)} Phase {inner(cfg, f)[1]:.2f}, "
             f"{inner(cfg, f)[2]:.3f} Plakate/Bild",
             f"Vorhang ab Bild {n2 + 1}: {curtain_frames(cfg, f)} Bilder bis draussen ({n3 - n2} da), Tempo der Loop-Bahn "
             f"an F1; Helles ausserhalb der stehenden Wand max {stray * 100:.2f} % (muss < 0.5), Sichtbares ausserhalb des "
             f"Lochs max {outside * 100:.2f} % (muss < 0.5); Flaeche " + " ".join(f"{p * 100:.0f}" for p in area) + " %",
             f"Weggezogen: Helles im Bild vor Stufe 1 {gap * 100:.1f} % (muss ~0)",
             "Zeilen leuchten ein (Helligkeit der neuen Zeilen auf der Stufe → +" + f"{f['intro_beats']:g} Beat): "
             + ", ".join(f"Bild {ns} {p:.2f} → {ni} {q:.2f}" for ns, ni, p, q in intro) + f" (muss < {INTRO_RATIO:g}x)",
             "Halo waechst (Lichtflaeche auf der Stufe → +" + f"{GROW_PROBE_BEATS:g} Beat): "
             + ", ".join(f"Bild {ns} {p * 100:.1f} % → {ng} {q * 100:.1f} %" for ns, ng, p, q in grow) + " (muss steigen)",
             f"Halo nie kleiner bis zum Ausklingen: groesster Rueckgang je Bild {drop * 100:.2f} % (muss < {NEVER_LESS * 100:g})",
             f"Schluss: Helles nach dem Ausklingen {tail * 100:.2f} % (muss ~0)",
             f"Schnitte auf dem Beat (> {EVENT_RATIO:g}x Vorlauf, Helligkeit oder Silhouette):"]
    lines += [f"  {'ok ' if ok else 'NEIN'} {name:<12} Bild {n} = {n / FPS:.3f} s  x{r}" for name, n, ok, r in rows]
    lines.append(f"Gegenprobe +{OLD_SHIFT} Bilder: {sum(ok for *_, ok, _ in old)}/{len(old)} ok (muss weniger sein)")
    open(os.path.join(out_dir(f), "report.txt" if f["master"] else "report_draft.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return (all(r[2] for r in rows) and sum(r[2] for r in old) < len(old) and (pairs == len(probe) or base_step(cfg) == 1)
            and max(d_out) < SAME_MC3 and min(d_in) > 0.05 and stray < 0.005 and outside < 0.005 and gap < 0.005
            and tail < 0.001 and drop < NEVER_LESS and all(p < INTRO_RATIO * q for *_, p, q in intro)
            and all(q > p for *_, p, q in grow))


def test(cfg, f):
    ok = report(cfg, f, preview_path(f))
    print(f"{f['code']}: {'OK' if ok else 'FEHLER'}")
    return ok


# ---------------------------------------------------------------- Bogen

SHEET_BEATS = (3.5, 3.6, 3.7, 3.8, 3.9, 4.0, 4.15, 4.3, 4.6, 5.2, 6.4,
               7.0, 7.2, 7.35, 7.5, 7.65, 7.8, 7.95, 8.1, 8.25, 8.4, 8.52,
               8.7, 9.0, 9.52, 9.8, 10.27, 10.6, 11.2, 11.8, 12.1, 12.3)


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
    master = "--master" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--master"]
    cmd, path = args[0], args[1]
    cfg, f = load(path, master)
    if cmd == "video":
        print(video(cfg, f))
    elif cmd == "sheet":
        print(sheet(cfg, f))
    elif cmd == "still":
        ns = sorted({min(frame_at(f, float(b)), n_end(f) - 1) for b in args[2:]})
        for n, img in frames(cfg, f, ns):
            out = os.path.join(out_dir(f), f"still_{n:03d}.png")
            Image.fromarray(img).save(out)
            print(out)
    elif cmd == "test":
        sys.exit(0 if test(cfg, f) else 1)


if __name__ == "__main__":
    main()
