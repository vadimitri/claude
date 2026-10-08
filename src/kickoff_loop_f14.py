#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""F14 = Ende nach Vadims Feedback zu F13 (8.10.), Foto-Phase MC3, ein Ablauf:

1. Geburt (Beat birth_beat → words_beat): das Loch ist der Spark des Plakats darunter. Die Bahnphase laeuft im
   Karussell-Tempo von F21 (hinten rechts, klein) auf F1 (Mitte, riesig) zu, je Bild das Plakat floor(Phase) mit
   seinem Spark genau im Loch (Vadim: "dass das Plakat genau an der Stelle der Maske ist"), Silhouette = die des Stils
   dieses Plakats (posterisiert, wechselt mit jedem Plakat). F1 deckt 9:16 nicht ganz: in den letzten cover_frames
   Bildern loest sich das Loch vom Plakat und waechst weiter, bis es deckt ("kann irgendwann detached sein").
2. Wortwaende je Beat (words), ganzer Bildschirm, der Loop laeuft in den Buchstaben einen Umlauf bis F1.
3. Vorhang (pull_beat → erste Stufe): die Woerter stehen, ein Spark-Loch (innen bunt, aussen schwarz) laeuft von F1
   auf der Bahn weiter (links, kleiner, nach hinten), wie die Sparks auf den Plakaten hinter den Woertern, und
   verschwindet in der Tiefe. Erst fehlt kaum etwas, dann zieht es alles weg.
4. Tonleiter (steps, gemessene Bass-Einsaetze C2 / D2 / D#2): je Stufe ein Kartenteil, roter Spark hinter dem Slash;
   das Halo jeder neuen Zeile waechst klein → gross, aeltere bleiben; nach der letzten Stufe + fade_hold_beats
   schrumpft und dunkelt alles Licht in fade_beats und nimmt die Schrift mit (Bayer-Zerfall) → Schwarz.

Stellschrauben: kickoff_loop/previz/review/F14/F14.toml. Licht wie das F10-Ende (kickoff_loop_end.flare_layer).
  uv run src/kickoff_loop_f14.py video|sheet|test <F14.toml>     still <F14.toml> <beat> [...]
"""
import copy
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
EVENT_RATIO = 2.0      # test: ein Schnitt setzt auf seinem Bild ein: doppelt so stark wie das Bild davor und der Median davor
EVENT_MIN = 0.003      # ... und mindestens so viel mittlere Aenderung (Encoder-Rauschen im Standbild ~0.0002)
BLACK_LUM = 0.03       # Silhouette = Zellen ueber Schwarz
LIT_LUM = 0.10         # test "Woerter stehen": sicher hell (Encoder-Saum an Buchstabenkanten liegt darunter)
OLD_SHIFT = 3          # Gegenprobe: dieselben Schnitte 3 Bilder spaeter
GROW_PROBE_BEATS = 0.6 # test "Halo waechst": Lichtflaeche so lange nach der Stufe gegen das Bild der Stufe (vor der naechsten)


# ---------------------------------------------------------------- Konfiguration und Raster

def main_root():
    """Hauptcheckout (Vorschau, Songs und Cache liegen nur dort, gitignored), auch aus einem Worktree."""
    git = subprocess.run(["git", "-C", KL.ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True).stdout.strip()
    return os.path.dirname(git) if git else KL.ROOT


def load(path):
    f = tomllib.load(open(path, "rb"))["f14"]
    f["code"], f["toml"] = os.path.splitext(os.path.basename(path))[0], os.path.abspath(path)
    cfg = KL.load(os.path.join(KL.ROOT, f["base_toml"]))
    g = json.load(open(os.path.join(KL.ROOT, f["grid"])))
    f["bar1"], f["beat"] = g["in_s"] - f["song_start_s"], g["beat_s"]   # Taktstrich 1 auf der Timeline, Beatlaenge
    root = main_root()
    f["base_video"], f["song"] = (os.path.join(root, f[k]) for k in ("base_video", "song"))
    assert len(f["words"]) == f["pull_beat"] - f["words_beat"], "je Beat zwischen words_beat und pull_beat ein Begriff"
    assert len(f["steps"]) == len(f["step_items"]) and f["steps"][0] > f["pull_beat"], "steps / step_items"
    assert f["birth_grow_frames"] >= 1 and f["cover_frames"] >= 1, "birth_grow_frames / cover_frames >= 1"
    assert 0 < f["pull_vanish_frac"] < 1 and f["pull_pow"] > 0, "pull_vanish_frac in (0, 1), pull_pow > 0"
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
    """Eckbilder: erstes der Geburt, letztes der Geburt (F1, deckt), letztes der Wortwand (wieder F1), letztes des
    Vorhangs (Loch zu, schwarz)."""
    return (frame_at(f, f["birth_beat"]), frame_at(f, f["words_beat"]) - 1, frame_at(f, f["pull_beat"]) - 1,
            frame_at(f, f["steps"][0]) - 1)


def zoom_dt(cfg, n):
    """Sekunden nach dem Karussell-Ende (Zeitachse des F10-Endes, KE.orbit_state)."""
    return (n - round(cfg["music"]["grid"]["burst_s"] * FPS)) / FPS


def base_until(cfg):
    """Erstes Bild, in dem das MC3-Video den blauen Slogan (F9/F10) zeigt: ab da ist ausserhalb des Sparks Schwarz."""
    return round(cfg["music"]["grid"]["burst_s"] * FPS + cfg["ending"]["orbit_pre_at_beats"] * KE.beat(cfg) * FPS)


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- Bahn des Lochs (Bildanteile, r = Anteil Bildbreite)

def loop_star(cfg, phase):
    """Loop-Stern bei Bahnphase phase (Frames) im 9:16-Bild, umgerechnet wie KE.poster_digital."""
    W, H = S.SIZES[FMT][:2]
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = V.digital_offset(cfg)
    x, y, r, rot = KL.orbit(cfg, phase)
    return (ox + x * pw) / W, (oy + y * ph) / H, r * pw / W, rot


def cover_r(x, y, rot):
    """Spitzenradius (Anteil Bildbreite), ab dem der Spark um (x, y) jede Zelle deckt (sternfoermig: der Rand reicht)."""
    W, H = S.SIZES[FMT][:2]
    gy, gx = np.mgrid[0:H // CELL, 0:W // CELL].astype(np.float32)
    dx, dy = (gx + 0.5) * CELL - x * W, (gy + 0.5) * CELL - y * H
    return float((np.hypot(dx, dy) / star_r(dx, dy, rot)).max()) * COVER / W


def cover_gain(cfg):
    """So viel groesser als der Plakat-Spark auf F1 muss das Loch sein, damit es das 9:16-Bild deckt."""
    x, y, r, rot = loop_star(cfg, 0)
    return max(1.0, cover_r(x, y, rot) / r)


def phase(cfg, f, n):
    """Bahnphase (Bahnframes, absolut: Plakat = floor) in Bild n. Geburt im Karussell-Tempo auf F1 (= count) zu, Wortwand
    ein Umlauf bis F1 (= 2 count, ~0.6 Plakate/Bild statt 0.68), Vorhang pull_frames weiter mit u^pull_pow."""
    n0, n1, n2, n3 = marks(f)
    N = KL.count(cfg)
    if n <= n1:
        rate = cfg["loop"]["changes_per_bar"] / 4 / f["beat"] / FPS     # Plakate pro Bild (T16)
        return N - rate * (n1 - n)
    if n <= n2:
        return N + N * (n - n1) / (n2 - n1)
    return 2 * N + f["pull_frames"] * pull_u(f, n) ** f["pull_pow"]


def pull_u(f, n):
    _, _, n2, n3 = marks(f)
    return min(max((n - n2) / (n3 - n2), 0.0), 1.0)


def gain(cfg, f, n):
    """Lochgroesse relativ zum Plakat-Spark: < 1 waechst aus dem Punkt bzw. verschwindet in der Tiefe, 1 = deckungsgleich,
    > 1 = vom Plakat geloest, bis es das Bild deckt (cover_gain, auf F1)."""
    n0, n1, n2, n3 = marks(f)
    gc = cover_gain(cfg)
    if n <= n1:
        grow = smooth((n - n0 + 1) / f["birth_grow_frames"])
        return grow * gc ** smooth((n - (n1 - f["cover_frames"])) / f["cover_frames"])
    if n <= n2:
        return gc
    u, v = pull_u(f, n), f["pull_vanish_frac"]
    return gc ** (1 - smooth(u / f["pull_release_frac"])) * (1 - smooth((u - (1 - v)) / v))


def hole(cfg, f, n):
    """(Plakat k, Lage des Lochs) in Bild n: Plakat floor(Phase) (Stop-Motion wie der Loop), Lage seines Bahnframes,
    Spitzenradius x gain."""
    k = math.floor(phase(cfg, f, n) + EPS)
    x, y, r, rot = loop_star(cfg, k % KL.count(cfg))
    return k, (x, y, r * gain(cfg, f, n), rot)


# ---------------------------------------------------------------- Szenen (Stil-Dicts, gecacht wie der Digitalteil)

def spark_none(c):
    c.star_m = np.zeros((c.gh, c.gw), bool)


def st_black(cfg, f):
    """Grundstil der schwarzen Szenen: Satz und Palette wie das F10-Ende, ohne Stern."""
    st = KE.orbit_state(cfg, zoom_dt(cfg, frame_at(f, f["words_beat"])))
    dg = st["loop"]["digital"]
    st = {k: v for k, v in st.items() if k != "P_spark"}
    st.update(S=KL.S_CODES["S2"], spark_fn=spark_none, type_fn=f14_type, star=(OFF[0] / 1080, OFF[1] / 1920, 0.001))
    st["loop"] = {**st["loop"], "digital": dict(u=dg["u"], offset=list(dg["offset"]), star=list(OFF), show=None)}
    return st


def white(cfg, f):
    return S.PALS[st_black(cfg, f)["P"]]


def world(cfg, k, pose=None):
    """Plakat k in den Buchstaben (KE.poster_digital: so saehe es aus, wenn das Karussell digital weiterliefe). pose:
    sein Spark sitzt genau im Loch (Bildanteile), sonst auf seinem Bahnframe."""
    st = KE.poster_digital(cfg, k)
    if pose:
        W, H = S.SIZES[FMT][:2]
        x, y, r, rot = pose
        st["loop"] = {**st["loop"], "digital": dict(st["loop"]["digital"], star=(x * W, y * H, r * W, rot))}
        st["star"] = (x, y, r)
    st["type_fn"] = f14_type
    return st


def scene(cfg, f, st, **kw):
    """Was f14_type zeichnet: black (Maske), title (Region oder None), light, items (sichtbare Kartenteile), gone
    (Bayer-Zerfall der Schrift 0..1)."""
    sc = dict(black="all", title=None, light=None, items=0, gone=0.0, pal=white(cfg, f),
              scale=cfg["ending"]["orbit_date_center"])
    sc.update(kw)
    return dict(st, f14=sc, f14_src=SRC)


def hole_spec(f, pose):
    x, y, r, rot = pose
    return {"hole": dict(pose=[round(x, 5), round(y, 5), round(r, 5), round(rot % KE.STAR_SYM_DEG, 3)],
                         reach=f["sil_reach"], rim=f["sil_rim"])}


def wall(f, word):
    """Wortwand (Maske): Begriff in Zeilen ueber den ganzen Bildschirm, steht fest."""
    return {"wall": dict(word=word, margin_cells=f["wall_margin_cells"], lead_frac=f["wall_lead_frac"])}


def card(cfg, f, tb):
    """Tonleiter: k Stufen vorbei → step_items[k-1] Kartenteile (SPARK, KICK-OFF, Datum, Ort). Das Halo jeder Stufe
    (ihre neuen Zeilen, auf Stufe 1 dazu der Spark) waechst ab ihrem Einsatz von glow_start_frac auf seine volle Laenge
    (ease-out, glow_grow_beats), aeltere bleiben stehen. Nach der letzten Stufe + fade_hold_beats schrumpft und dunkelt
    alles Licht in fade_beats, die Schrift zerfaellt mit (q)."""
    e = cfg["ending"]
    k = sum(tb >= s for s in f["steps"])
    q = min(max((tb - f["steps"][-1] - f["fade_hold_beats"]) / f["fade_beats"], 0.0), 1.0)
    if q >= 1:
        return scene(cfg, f, st_black(cfg, f))
    full = math.log(e["orbit_flare_max_scale"])
    groups = []
    for j in range(k):
        u = min((tb - f["steps"][j]) / f["glow_grow_beats"], 1.0)
        grow = f["glow_start_frac"] + (1 - f["glow_start_frac"]) * (1 - (1 - u) ** 2)
        groups.append([f["step_items"][j - 1] if j else 0, f["step_items"][j], round(full * grow * (1 - q), 4)])
    lt = dict(xy=list(e["orbit_flare_xy"]), r=round(e["orbit_flare_r_frac"] * (1 - q), 5),
              rot=round(tb * e["orbit_flare_spin_deg_per_beat"] % KE.STAR_SYM_DEG, 3), groups=groups,
              gain=round((1 - q) ** 2, 4), peak=e["orbit_flare_peak"], colors=list(e["orbit_flare_colors"]))
    return scene(cfg, f, st_black(cfg, f), light=lt, items=f["step_items"][k - 1], gone=round(q, 4))


def plan(cfg, f, n):
    """("base", n) aus dem MC3-Video | ("render", st, base?): base = ausserhalb des Lochs liegt noch das MC3-Bild."""
    n0, n1, n2, n3 = marks(f)
    if n < n0:
        return ("base", n)
    if n <= n1:                                                        # Geburt
        k, pose = hole(cfg, f, n)
        sync = gain(cfg, f, n) <= 1
        hs = hole_spec(f, pose)
        st = scene(cfg, f, world(cfg, k, pose if sync else None), black={"not": {"and": [hs, wall(f, f["words"][0])]}},
                   title={"not": hs})
        return ("render", st, n < base_until(cfg))
    if n <= n2:                                                        # Waende, Loop laeuft in den Buchstaben
        k = math.floor(phase(cfg, f, n) + EPS)
        word = f["words"][min(int(tb_of(f, n)) - f["words_beat"], len(f["words"]) - 1)]
        return ("render", scene(cfg, f, world(cfg, k), black={"not": wall(f, word)}), False)
    if n <= n3:                                                        # Vorhang: Loch zieht ueber die stehende Wand
        k, pose = hole(cfg, f, n)
        sync = gain(cfg, f, n) <= 1
        if pose[2] <= EPS:
            return ("render", scene(cfg, f, st_black(cfg, f)), False)
        keep = {"and": [hole_spec(f, pose), wall(f, f["words"][-1])]}
        return ("render", scene(cfg, f, world(cfg, k, pose if sync else None), black={"not": keep}), False)
    return ("render", card(cfg, f, tb_of(f, n)), False)


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
    """Silhouette des Lochs = Spark im Stil des Plakats (c.st["S"]) an p["pose"]: Koerper (Sternform) mit posterisiertem
    Rand (Bayer-Band bis rim x Radius nach aussen) plus die Auslaeufer des Stils (helle Zellen seines Renders: Spritzer,
    Scherben, Schein) bis reach x Radius. Der Render allein taugt nicht: viele Stile sind innen dunkel (S33 Ringe,
    S23/S47 Kern) und S31 leuchtet ein Rechteck aus (Befund 8.10. an allen 20 Stilen)."""
    x, y, r, rot = p["pose"]
    X, Y, R = x * c.W, y * c.H, r * c.W
    d = S.star_d(c, X, Y, R, rot)[0]
    body = d < 1 + p["rim"] * (1 - S.tile(S.bayer(4), (c.gh, c.gw)))
    sub = copy.copy(c)
    sub.st, sub.L, sub.layers, sub.layer_pal = dict(c.st, rot=rot), dict(c.L, star=(X, Y, R, rot)), [], {}
    K.spark(sub)
    K._EXTRA["extra"] = []                                              # Zweitlicht der Labor-Sterne nicht ins Schwarz
    return body | (sub.star_m & (d < p["reach"]))


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
    """Licht je Stufe: ihre Zeilen (auf Stufe 1 dazu der Spark) mit eigener Schweiflaenge, Maximum ueber die Stufen,
    eigene Rampe, Helligkeit x gain (Ausklingen)."""
    X, Y = lt["xy"][0] * c.W, lt["xy"][1] * c.H
    centre = (Y / c.px - 0.5, X / c.px - 0.5)
    star = S.star_d(c, X, Y, max(lt["r"], 1e-6) * c.W, lt["rot"])[0] < 1
    g = np.zeros((c.gh, c.gw), np.float32)
    for j, (a, b, glow) in enumerate(lt["groups"]):
        src = np.logical_or.reduce(items[a:b]).astype(np.float32) * lt["peak"]
        if j == 0:
            src = np.maximum(src, star.astype(np.float32))
        g = np.maximum(g, streak(c, src, centre, glow))
    g = g * lt["gain"]
    c.layer_pal["light"] = KE.ramp(c, lt["colors"])
    c.add("light", g > KE.GLOW_MIN, g)


def f14_type(c):
    """Zeichnet die Szene st["f14"]."""
    sc = c.st["f14"]
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
    if sc["title"] is not None:                                        # Geburt: SPARK steht, bis das Loch ihn deckt
        c.add("type", np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))
              & mask(c, sc["title"]), hi)
    if items:
        c.add("type", np.logical_or.reduce(items), hi)


# ---------------------------------------------------------------- Rendern

def _job(args):
    """Bild n auf dem Zellraster; bei base zusaetzlich die Lochmaske (MC3 liegt ausserhalb)."""
    cfg, f, n = args
    p = plan(cfg, f, n)
    if p[0] == "base":
        return n, None, None
    img = KL.render_cached(p[1], FMT, "f14")
    m = None
    if p[2]:
        c = S.Ctx(p[1], FMT)
        m = hole_mask(c, p[1]["f14"]["title"]["not"]["hole"])
    return n, np.ascontiguousarray(img[::CELL, ::CELL]), m


def frames(cfg, f, ns):
    """Bilder ns (aufsteigend) als (n, RGB voll). MC3-Bilder aus einem Decoder, gerenderte aus dem KL-Pool; in der
    Geburt liegt das Loch ueber dem MC3-Bild, solange es den dunklen Spark zeigt (base_until)."""
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
    """Geplante Schnitte: jede Wand nach der ersten (die erste deckt das Loch auf), jede Stufe. (Bild, Name)."""
    ev = [(frame_at(f, f["words_beat"] + k), w) for k, w in enumerate(f["words"]) if k]
    return ev + [(frame_at(f, s), f"Stufe {j + 1}") for j, s in enumerate(f["steps"])]


def onset(d, n):
    pre = max(float(d[n - 1]), float(np.median(d[max(n - 8, 1):n]))) + 1e-6
    return bool(d[n] >= EVENT_MIN and d[n] > EVENT_RATIO * pre), round(float(d[n] / pre), 1)


def on_beat(diffs, ev, shift=0):
    out = []
    for n, name in ev:
        n += shift
        res = [onset(d, n) for d in diffs]
        out.append((name, n, any(ok for ok, _ in res), max(r for _, r in res)))
    return out


def core_cells(pose):
    """Sternkoerper des Lochs auf dem Zellraster (Formel wie styles.star_d, Zellmitten wie styles.Ctx)."""
    W, H = S.SIZES[FMT][:2]
    x, y, r, rot = pose
    gy, gx = np.mgrid[0:H // CELL, 0:W // CELL].astype(np.float32)
    dx, dy = (gx + 0.5) * CELL - x * W, (gy + 0.5) * CELL - y * H
    return np.hypot(dx, dy) < star_r(dx, dy, rot % KE.STAR_SYM_DEG) * r * W


def wall_cells(cfg, f, word, shape):
    """Wortwand auf dem Raster des Befunds (shape), 1 Zelle dilatiert (Encoder-Saum)."""
    c = S.Ctx(world(cfg, 0), FMT)
    m = wall_mask(c, wall(f, word)["wall"])
    sy, sx = m.shape[0] // shape[0], m.shape[1] // shape[1]
    m = m[:shape[0] * sy, :shape[1] * sx].reshape(shape[0], sy, shape[1], sx).any((1, 3))
    return binary_dilation(m)


def report(cfg, f, path):
    a = gray(path)
    sil = (a > BLACK_LUM).astype(np.float32)
    diffs = [np.r_[0, np.abs(np.diff(a, axis=0)).mean((1, 2))], np.r_[0, np.abs(np.diff(sil, axis=0)).mean((1, 2))]]
    rows, old = on_beat(diffs, events(f)), on_beat(diffs, events(f), OLD_SHIFT)
    n0, n1, n2, n3 = marks(f)
    hole_n1 = float(1 - core_cells(hole(cfg, f, n1)[1]).mean())         # Loch deckt das Bild genau ab hier (Geometrie)
    hole_pre = float(1 - core_cells(hole(cfg, f, n1 - 1)[1]).mean())
    sync = [n for n in range(n0, n1 + 1) if gain(cfg, f, n) <= 1]
    gap = float(sil[n3].mean())                                         # vor Stufe 1: Loch ist zu
    tail = float(sil[round(t_beat(f, f["steps"][-1] + f["fade_hold_beats"] + f["fade_beats"]) * FPS) + 1:].mean())
    wm = wall_cells(cfg, f, f["words"][-1], a.shape[1:])                # Woerter stehen: Helles im Vorhang nur in der Wand
    stray = max(float(((a[n] > LIT_LUM) & ~wm).mean()) for n in range(n2 + 1, n3))
    lit = (a > BLACK_LUM)
    grow = []
    for s in f["steps"]:                                                # Halo waechst nach jeder Stufe
        ns, ng = frame_at(f, s), frame_at(f, s + GROW_PROBE_BEATS)
        grow.append((ns, ng, float(lit[ns].mean()), float(lit[ng].mean())))
    lines = [f"{f['code']}, {path}",
             f"Geburt: ungedeckt im letzten Bild vor Beat {f['words_beat']} {hole_n1 * 100:.2f} % (muss 0), ein Bild davor "
             f"{hole_pre * 100:.1f} % (muss > 0); Plakat-Spark = Loch in Bild {sync[0]}-{sync[-1]}, danach geloest",
             f"Vorhang: Helles ausserhalb der stehenden Wand max {stray * 100:.2f} % (muss < 0.5; F13 zog die Wand mit)",
             f"Weggezogen: Helles im Bild vor Stufe 1 {gap * 100:.1f} % (muss ~0)",
             f"Schluss: Helles nach dem Ausklingen {tail * 100:.2f} % (muss ~0)",
             "Halo waechst (Lichtflaeche auf der Stufe → +" + f"{GROW_PROBE_BEATS:g} Beat): " +
             ", ".join(f"Bild {ns} {p * 100:.1f} % → {ng} {q * 100:.1f} %" for ns, ng, p, q in grow) + " (muss steigen)",
             f"Schnitte auf dem Beat (> {EVENT_RATIO:g}x Vorlauf, Helligkeit oder Silhouette):"]
    lines += [f"  {'ok ' if ok else 'NEIN'} {name:<12} Bild {n} = {n / FPS:.3f} s  x{r}" for name, n, ok, r in rows]
    lines.append(f"Gegenprobe +{OLD_SHIFT} Bilder: {sum(ok for *_, ok, _ in old)}/{len(old)} ok (muss weniger sein)")
    open(os.path.join(out_dir(f), "report_draft.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return (all(r[2] for r in rows) and sum(r[2] for r in old) < len(old) and hole_n1 == 0 and hole_pre > 0
            and gap < 0.005 and tail < 0.001 and stray < 0.005 and all(q > p for *_, p, q in grow))


def test(cfg, f):
    ok = report(cfg, f, os.path.join(out_dir(f), "preview_draft.mp4"))
    print(f"{f['code']}: {'OK' if ok else 'FEHLER'}")
    return ok


# ---------------------------------------------------------------- Bogen

SHEET_BEATS = (4.1, 4.3, 4.5, 4.7, 4.85, 4.95, 5.05, 6.1, 7.1,
               8.1, 8.2, 8.3, 8.4, 8.6, 9.2, 9.6, 10.3, 11.0, 11.6, 12.1, 12.3, 12.6)


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
