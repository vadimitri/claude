#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""F13 = Ende nach Vadims Feedback zu F12 (8.10.), Foto-Phase MC3, ein Ablauf:

1. Geburt (Beat birth_beat → words_beat): der Masken-Spark kommt aus der Mitte des dunklen Sparks (MC3-Video) und
   laeuft dann die echte Loop-Bahn (KL.orbit, Tempo des Karussells) bis F1 (Mitte, riesig), Groesse = Loop-Stern.
   Er ist nur Maske: darin die Wortwand ueber den ganzen Bildschirm (Loop laeuft in den Buchstaben), sonst Schwarz.
2. Wortwaende je Beat (words), ohne SPARK-Titel (Vadim: "die Begriffe fuellen den gesamten Bildschirm").
3. Wegziehen (pull_beat → erste Stufe): der Spark fliegt weiter nach links raus, die Wand haengt an ihm → Schwarz.
4. Tonleiter (steps, gemessene Bass-Einsaetze C2 / D2 / D#2): je Stufe ein Begriff der Karte, roter Spark hinter dem
   Slash mit Halo, das auf jeder Stufe aufleuchtet; nach der letzten schrumpft und dunkelt das Halo in fade_beats und
   nimmt die Schrift mit (Bayer-Zerfall) → Schwarz bis zum Schluss.

Stellschrauben: kickoff_loop/previz/review/F13/F13.toml. Licht wie das F10-Ende (kickoff_loop_end.flare_layer).
  uv run src/kickoff_loop_f13.py video|sheet|test <F13.toml>     still <F13.toml> <beat> [...]
"""
import hashlib
import json
import math
import os
import subprocess
import sys
import tomllib

import numpy as np
from PIL import Image, ImageDraw

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
COVER = 1.02           # Spark deckt das Bild: weitestes Pixel x so viel (Rand im Korn)
EVENT_RATIO = 2.0      # test: ein Schnitt setzt auf seinem Bild ein: doppelt so stark wie das Bild davor und der Median davor
EVENT_MIN = 0.003      # ... und mindestens so viel mittlere Aenderung (Encoder-Rauschen im Standbild ~0.0002)
BLACK_LUM = 0.03       # Silhouette = Zellen ueber Schwarz
OLD_SHIFT = 3          # Gegenprobe: dieselben Schnitte 3 Bilder spaeter


# ---------------------------------------------------------------- Konfiguration und Raster

def main_root():
    """Hauptcheckout (Vorschau, Songs und Cache liegen nur dort, gitignored), auch aus einem Worktree."""
    git = subprocess.run(["git", "-C", KL.ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True).stdout.strip()
    return os.path.dirname(git) if git else KL.ROOT


def load(path):
    f = tomllib.load(open(path, "rb"))["f13"]
    f["code"], f["toml"] = os.path.splitext(os.path.basename(path))[0], os.path.abspath(path)
    cfg = KL.load(os.path.join(KL.ROOT, f["base_toml"]))
    g = json.load(open(os.path.join(KL.ROOT, f["grid"])))
    f["bar1"], f["beat"] = g["in_s"] - f["song_start_s"], g["beat_s"]   # Taktstrich 1 auf der Timeline, Beatlaenge
    root = main_root()
    f["base_video"], f["song"] = (os.path.join(root, f[k]) for k in ("base_video", "song"))
    assert len(f["words"]) == f["pull_beat"] - f["words_beat"], "je Beat zwischen words_beat und pull_beat ein Begriff"
    assert len(f["steps"]) == len(f["step_items"]) and f["steps"][0] > f["pull_beat"], "steps / step_items"
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


def zoom_dt(cfg, n):
    """Sekunden nach dem Karussell-Ende (Zeitachse des F10-Endes, KE.orbit_state)."""
    return (n - round(cfg["music"]["grid"]["burst_s"] * FPS)) / FPS


def base_until(cfg):
    """Erstes Bild, in dem das MC3-Video den blauen Slogan (F9/F10) zeigt: ab da ist ausserhalb des Sparks Schwarz."""
    return round(cfg["music"]["grid"]["burst_s"] * FPS + cfg["ending"]["orbit_pre_at_beats"] * KE.beat(cfg) * FPS)


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- Bahn des Masken-Sparks (Bildanteile, r = Anteil Bildbreite)

def dark_star(cfg, n):
    """Der dunkle Spark des MC3-Videos in Bild n (Bildanteile)."""
    W, H = S.SIZES[FMT][:2]
    x, y, R, rot = KE.orbit_state(cfg, zoom_dt(cfg, n))["loop"]["digital"]["star"]
    return x / W, y / H, R / W, rot


def loop_star(cfg, phase):
    """Loop-Stern bei Bahnphase phase (Frames, gebrochen) im 9:16-Bild, umgerechnet wie KE.poster_digital."""
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


def lerp_deg(a, b, w):
    d = (b - a + KE.STAR_SYM_DEG / 2) % KE.STAR_SYM_DEG - KE.STAR_SYM_DEG / 2     # kuerzester Weg (6 Zacken)
    return a + d * w


def birth(cfg, f, n):
    """Geburt: Bahnphase laeuft im Karussell-Tempo auf F1 (= Phase 0) zu, am letzten Bild vor words_beat steht sie dort.
    Mitte und Drehung gehen von der Mitte des dunklen Sparks in die Loop-Bahn ueber (smoothstep), der Radius waechst
    von birth_scale x Loop-Stern auf den Loop-Stern (und, falls F1 das 9:16-Bild nicht deckt, auf cover_r)."""
    n0, n1 = frame_at(f, f["birth_beat"]), frame_at(f, f["words_beat"]) - 1
    u = (n - n0) / (n1 - n0)
    rate = cfg["loop"]["changes_per_bar"] / 4 / f["beat"]              # Plakate pro Sekunde (T16)
    lx, ly, lr, lrot = loop_star(cfg, -rate * (n1 - n) / FPS % KL.count(cfg))
    dx, dy, _, drot = dark_star(cfg, n)
    w = smooth(u)
    fx, fy, fr, frot = loop_star(cfg, 0.0)
    k = max(1.0, cover_r(fx, fy, frot) / fr) ** u                      # F1 deckt sonst die Ecken nicht
    return dx + (lx - dx) * w, dy + (ly - dy) * w, lr * f["birth_scale"] ** (1 - u) * k, lerp_deg(drot, lrot, w)


def full(cfg, f):
    """Lage am Ende der Geburt (F1, deckt das Bild): Ausgangspunkt der Wortwand und des Wegziehens."""
    return birth(cfg, f, frame_at(f, f["words_beat"]) - 1)


def pull(cfg, f, tb):
    """Wegziehen: Spark fliegt mit u^pull_pow (zieht an) von F1 nach pull_to und schrumpft auf pull_r x Radius."""
    x0, y0, r0, rot = full(cfg, f)
    u = min((tb - f["pull_beat"]) / (f["pull_end"] - f["pull_beat"]), 1.0) ** f["pull_pow"]
    (x1, y1), r1 = f["pull_to"], r0 * f["pull_r"]
    return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, r0 + (r1 - r0) * u, rot + f["pull_spin_deg"] * u


# ---------------------------------------------------------------- Szenen (Stil-Dicts, gecacht wie der Digitalteil)

def st_black(cfg, f):
    """Grundstil der schwarzen Szenen: Satz und Palette wie das F10-Ende, ohne Stern."""
    st = KE.orbit_state(cfg, zoom_dt(cfg, frame_at(f, f["words_beat"])))
    dg = st["loop"]["digital"]
    st = {k: v for k, v in st.items() if k != "P_spark"}
    st.update(S=KL.S_CODES["S2"], spark_fn=spark_none, type_fn=f13_type, star=(OFF[0] / 1080, OFF[1] / 1920, 0.001))
    st["loop"] = {**st["loop"], "digital": dict(u=dg["u"], offset=list(dg["offset"]), star=list(OFF), show=None)}
    return st


def white(cfg, f):
    return S.PALS[st_black(cfg, f)["P"]]


def world(cfg, f, n):
    """Plakat in den Buchstaben: der Loop laeuft digital weiter, ein Plakat je world_step_frames Bilder."""
    i = (f["world_start"] + (n - frame_at(f, f["birth_beat"])) // f["world_step_frames"]) % KL.posters(cfg)
    st = KE.poster_digital(cfg, i)
    st["type_fn"] = f13_type
    return st


def scene(cfg, f, st, **kw):
    """Was f13_type zeichnet: black (Maske), title (Region oder None), light, items (sichtbare Kartenteile), gone
    (Bayer-Zerfall der Schrift 0..1)."""
    sc = dict(black="all", title=None, light=None, items=0, gone=0.0, pal=white(cfg, f),
              scale=cfg["ending"]["orbit_date_center"])
    sc.update(kw)
    return dict(st, f13=sc, f13_src=SRC)


def spark(sp):
    x, y, r, rot = sp
    return {"spark": [round(x, 5), round(y, 5), round(r, 5), round(rot % KE.STAR_SYM_DEG, 3)]}


def wall(f, word, at=None, to=None):
    """Wortwand (Maske): Begriff in Zeilen ueber den ganzen Bildschirm. at/to = (x, y, r): die Wand haengt am Spark,
    der von at nach to fliegt (verschoben + skaliert wie er)."""
    p = dict(word=word, margin_cells=f["wall_margin_cells"], lead_frac=f["wall_lead_frac"])
    if at:
        p.update(at=[round(v, 5) for v in at[:3]], to=[round(v, 5) for v in to[:3]])
    return {"wall": p}


def card(cfg, f, tb):
    """Tonleiter: k Stufen vorbei → step_items[k-1] Kartenteile (SPARK, KICK-OFF, Datum, Ort), Licht mit Aufleuchten
    je Stufe (step_glow, klingt in step_decay_beats ab); nach der letzten Stufe + fade_hold_beats schrumpft und dunkelt
    das Halo in fade_beats, die Schrift zerfaellt mit (q)."""
    e = cfg["ending"]
    k = sum(tb >= s for s in f["steps"])
    s = f["steps"][k - 1]
    q = min(max((tb - f["steps"][-1] - f["fade_hold_beats"]) / f["fade_beats"], 0.0), 1.0)
    if q >= 1:
        return scene(cfg, f, st_black(cfg, f))
    g = math.log(e["orbit_flare_max_scale"]) + math.log(f["step_glow"]) * math.exp(-(tb - s) / f["step_decay_beats"])
    lt = dict(xy=list(e["orbit_flare_xy"]), r=round(e["orbit_flare_r_frac"] * (1 - q), 5),
              rot=round(tb * e["orbit_flare_spin_deg_per_beat"] % KE.STAR_SYM_DEG, 3), glow=round(g * (1 - q), 4),
              gain=round((1 - q) ** 2, 4), peak=e["orbit_flare_peak"], colors=list(e["orbit_flare_colors"]))
    return scene(cfg, f, st_black(cfg, f), light=lt, items=f["step_items"][k - 1], gone=round(q, 4))


def plan(cfg, f, n):
    """("base", n) aus dem MC3-Video | ("birth", st, spark, base?) Masken-Spark ueber dem dunklen | ("render", st)."""
    if n < frame_at(f, f["birth_beat"]):
        return ("base", n)
    tb = tb_of(f, n)
    if tb < f["words_beat"]:
        sp = birth(cfg, f, n)
        st = scene(cfg, f, world(cfg, f, n), black={"not": {"and": [spark(sp), wall(f, f["words"][0])]}},
                   title={"not": spark(sp)})
        return ("birth", st, sp, n < base_until(cfg))
    if tb < f["pull_beat"]:
        return ("render", scene(cfg, f, world(cfg, f, n), black={"not": wall(f, f["words"][int(tb) - f["words_beat"]])}))
    if tb < f["pull_end"]:
        sp = pull(cfg, f, tb)
        keep = {"and": [spark(sp), wall(f, f["words"][-1], full(cfg, f), sp)]}
        return ("render", scene(cfg, f, world(cfg, f, n), black={"not": keep}))
    if tb < f["steps"][0]:
        return ("render", scene(cfg, f, st_black(cfg, f)))
    return ("render", card(cfg, f, tb))


# ---------------------------------------------------------------- Zeichnen (Hooks fuer styles.render)

def spark_none(c):
    c.star_m = np.zeros((c.gh, c.gw), bool)


def wall_mask(c, p):
    """Begriff in Zeilen auf voller Satzbreite von margin bis H - margin; haengt die Wand am Spark (at → to), wird sie
    um dessen Mitte skaliert und verschoben (naechste Zelle)."""
    measure = c.W - 2 * c.L["x0"]
    cap = math.floor(measure / S.width_per_cap(p["word"]) / c.px) * c.px
    lead = round(cap * p["lead_frac"] / c.px) * c.px
    top, bottom = p["margin_cells"] * c.px, c.H - p["margin_cells"] * c.px
    rows = max(1, int((bottom - top - cap) // lead) + 1)
    y0 = top + (bottom - top - (cap + (rows - 1) * lead)) / 2
    m = KE.word_mask(c, [p["word"]] * rows, cap, lead, c.W / 2, y0)[0]
    if "at" not in p:
        return m
    (ax, ay, ar), (tx, ty, tr) = p["at"], p["to"]
    z = tr / ar
    sy = np.round(ay * c.gh - 0.5 + (c.yy - (ty * c.gh - 0.5)) / z).astype(int)
    sx = np.round(ax * c.gw - 0.5 + (c.xx - (tx * c.gw - 0.5)) / z).astype(int)
    ok = (sy >= 0) & (sy < c.gh) & (sx >= 0) & (sx < c.gw)
    out = np.zeros_like(m)
    out[ok] = m[sy[ok], sx[ok]]
    return out


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
    if op == "spark":
        x, y, r, rot = a
        return S.star_d(c, x * c.W, y * c.H, r * c.W, rot)[0] < 1
    raise ValueError(f"Maske {spec}")


def card_masks(c, sc):
    """(Titel, Zeilen der Karte) bis items Teile (1 = SPARK, 2 = + KICK-OFF, ...), Satz wie F10 (date_cap, mittig auf
    dem Spark hinter dem Slash), jede Zeile an ihrer Stelle im ganzen Block."""
    title = np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))
    ls = list(c.L["sub"])
    cap, lead = KE.date_cap(c, sc["scale"], ls)
    top = c.H / 2 - (cap + (len(ls) - 1) * lead) / 2
    lines = np.zeros((c.gh, c.gw), bool)
    for j in range(max(sc["items"] - 1, 0)):
        lines |= KE.word_mask(c, [ls[j]], cap, lead, c.W / 2, top + j * lead)[0]
    return (title if sc["items"] >= 1 else np.zeros_like(title)), lines


def light_layer(c, lt, src_mask):
    """Licht wie KE.flare_layer (Schrift + Spark GLOW_SAMPLES-mal um den Spark vergroessert, Gewicht faellt nach
    aussen, eigene Rampe), Helligkeit x gain (Ausklingen)."""
    X, Y = lt["xy"][0] * c.W, lt["xy"][1] * c.H
    centre = (Y / c.px - 0.5, X / c.px - 0.5)
    star = S.star_d(c, X, Y, max(lt["r"], 1e-6) * c.W, lt["rot"])[0] < 1
    src = np.maximum(src_mask * lt["peak"], star * 1.0).astype(np.float32)
    g = src.copy()
    for j in range(1, KE.GLOW_SAMPLES + 1):
        s = math.exp(lt["glow"] * j / KE.GLOW_SAMPLES)
        sy = np.round(centre[0] + (c.yy - centre[0]) / s).astype(int)
        sx = np.round(centre[1] + (c.xx - centre[1]) / s).astype(int)
        ok = (sy >= 0) & (sy < c.gh) & (sx >= 0) & (sx < c.gw)
        hit = np.zeros_like(g)
        hit[ok] = src[sy[ok], sx[ok]]
        g = np.maximum(g, hit * (1 - j / (KE.GLOW_SAMPLES + 1)))
    g = g * lt["gain"]
    c.layer_pal["light"] = KE.ramp(c, lt["colors"])
    c.add("light", g > KE.GLOW_MIN, g)


def f13_type(c):
    """Zeichnet die Szene st["f13"]."""
    sc = c.st["f13"]
    if sc["black"]:
        c.layer_pal["dim"] = np.zeros_like(c.pal)
        c.add("dim", mask(c, sc["black"]), 0.0)
    title, lines = card_masks(c, sc)
    stay = S.tile(S.bayer(4).T, (c.gh, c.gw)) >= sc["gone"]            # Schrift zerfaellt mit dem Halo
    if sc["light"]:
        light_layer(c, sc["light"], (title | lines) & stay)
    pal = S.hexpal_list(sc["pal"])
    c.layer_pal["type"] = pal
    hi = c.lvl(int((pal @ KL.LUMA).argmax()))
    if sc["title"] is not None:                                        # Geburt: SPARK steht, bis der Spark ihn deckt
        c.add("type", np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))
              & mask(c, sc["title"]), hi)
    c.add("type", (title | lines) & stay, hi)


# ---------------------------------------------------------------- Rendern

def _job(args):
    cfg, f, n = args
    p = plan(cfg, f, n)
    if p[0] == "base":
        return n, None
    img = KL.render_cached(p[1], FMT, "f13")
    return n, np.ascontiguousarray(img[::CELL, ::CELL])


def spark_cells(sp):
    """Maske des Sparks auf dem Zellraster (dieselbe Formel wie mask "spark", Zellmitten wie styles.Canvas)."""
    W, H = S.SIZES[FMT][:2]
    x, y, r, rot = sp
    gy, gx = np.mgrid[0:H // CELL, 0:W // CELL].astype(np.float32)
    dx, dy = (gx + 0.5) * CELL - x * W, (gy + 0.5) * CELL - y * H
    return np.hypot(dx, dy) < star_r(dx, dy, rot % KE.STAR_SYM_DEG) * r * W


def frames(cfg, f, ns):
    """Bilder ns (aufsteigend) als (n, RGB voll). MC3-Bilder aus einem Decoder, gerenderte aus dem KL-Pool; in der
    Geburt liegt der Spark ueber dem MC3-Bild, solange es den dunklen Spark zeigt (base_until)."""
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
        p = ps[n]
        if p[0] == "base":
            img = base(n)
        else:
            m, small = next(it)
            assert m == n
            img = S.up(small, CELL)
            if p[0] == "birth" and p[3]:
                img = np.where(S.up(spark_cells(p[2]), CELL)[..., None], img, base(n))
        yield n, img
    if dec:
        dec.kill()


def out_dir(f):
    d = os.path.dirname(f["toml"])
    os.makedirs(d, exist_ok=True)
    return d


def video(cfg, f):
    path = os.path.join(out_dir(f), "preview_draft.mp4")
    W, H = S.SIZES[FMT][:2]
    enc = V.ffmpeg_writer(path, (W, H), FPS, audio=f["song"], enc=V.PREVIEW_ENCODER)
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
    """Geplante Schnitte: jede Wand nach der ersten (die erste deckt der Spark auf), jede Stufe. (Bild, Name)."""
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


def report(cfg, f, path):
    a = gray(path)
    sil = (a > BLACK_LUM).astype(np.float32)
    diffs = [np.r_[0, np.abs(np.diff(a, axis=0)).mean((1, 2))], np.r_[0, np.abs(np.diff(sil, axis=0)).mean((1, 2))]]
    rows, old = on_beat(diffs, events(f)), on_beat(diffs, events(f), OLD_SHIFT)
    n_full = frame_at(f, f["words_beat"]) - 1                          # Spark deckt das Bild genau ab hier (Geometrie)
    hole = float(1 - spark_cells(birth(cfg, f, n_full)).mean())
    hole_pre = float(1 - spark_cells(birth(cfg, f, n_full - 1)).mean())
    gap = float(sil[frame_at(f, f["steps"][0]) - 1].mean())            # vor Stufe 1: Wand ist weggezogen
    tail = float(sil[round(t_beat(f, f["steps"][-1] + f["fade_hold_beats"] + f["fade_beats"]) * FPS) + 1:].mean())
    lines = [f"{f['code']}, {path}",
             f"Geburt: ungedeckt im letzten Bild vor Beat {f['words_beat']} {hole * 100:.2f} % (muss 0), ein Bild davor "
             f"{hole_pre * 100:.1f} % (muss > 0)",
             f"Weggezogen: Helles im Bild vor Stufe 1 {gap * 100:.1f} % (muss ~0)",
             f"Schluss: Helles nach dem Ausklingen {tail * 100:.2f} % (muss ~0)",
             f"Schnitte auf dem Beat (> {EVENT_RATIO:g}x Vorlauf, Helligkeit oder Silhouette):"]
    lines += [f"  {'ok ' if ok else 'NEIN'} {name:<12} Bild {n} = {n / FPS:.3f} s  x{r}" for name, n, ok, r in rows]
    lines.append(f"Gegenprobe +{OLD_SHIFT} Bilder: {sum(ok for *_, ok, _ in old)}/{len(old)} ok (muss weniger sein)")
    open(os.path.join(out_dir(f), "report_draft.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    ok = all(r[2] for r in rows) and sum(r[2] for r in old) < len(old) and hole == 0 and hole_pre > 0 and gap < 0.005 and tail < 0.001
    return ok


def test(cfg, f):
    ok = report(cfg, f, os.path.join(out_dir(f), "preview_draft.mp4"))
    print(f"{f['code']}: {'OK' if ok else 'FEHLER'}")
    return ok


# ---------------------------------------------------------------- Bogen

SHEET_BEATS = (4.2, 4.5, 4.8, 4.95, 5.05, 6.1, 7.1, 8.15, 8.3, 8.45, 8.55, 9.0, 9.55, 10.0, 10.3, 10.6, 10.8, 11.2)


def sheet(cfg, f):
    tw, th = 216, 384
    ns = [min(frame_at(f, b), n_end(f) - 1) for b in SHEET_BEATS]
    got = dict(frames(cfg, f, sorted(set(ns))))
    cols = 9
    img = Image.new("RGB", (cols * tw, 2 * (th + 16)), (18, 18, 18))
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
