#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""F12 = F11b (Schrift als Fenster, Vadims Wahl 8.10.) mit zwei neuen Uebergaengen, Foto-Phase MC3:

1. Geburt (Vadim: "den schwarzen Spark haben, und da waechst ein neuer Spark vom Loop versetzt in klein raus, der
   fuellt, und ab dem Moment ist die Maske da, auch wenn es laenger dauert und wir ein Wort weniger haben"): ab Beat
   birth_beat laeuft das MC3-Video weiter (der dunkle Spark waechst ueber das letzte Plakat), in ihm waechst ein neuer
   Spark, um eine halbe Zackenteilung versetzt, als Fenster in den weiterlaufenden Loop. Auf dem letzten Bild vor
   words_beat deckt er genau das Bild, auf dem Beat steht die Maske (erster Begriff).
2. Ende (Vadim: "Uebergang von den maskierten Woertern zum Kick-off besser, soll kicken, passt zu dem Ding: das
   aufloesen und dann kommt nochmal ein Spark"): sieben Varianten F12a-g (je F12x/F12x.toml [f12] end), alle auf der
   Eins von Takt 3 (card_beat).

Jedes Ereignis liegt auf IGORs Raster (igor_beats.json ueber song_start_s). Gemeinsame Stellschrauben:
kickoff_loop/previz/review/F12/F12.toml. Licht, Welle und Satz des Endes wie F10 (kickoff_loop_end).

  uv run src/kickoff_loop_f12.py video <F12x.toml> [...]   → previz/review/F12x/preview_draft.mp4 + Vorschau/F12x_draft.mp4
  uv run src/kickoff_loop_f12.py sheet <F12x.toml> [...]   Standbilder auf den Beats → previz/review/F12/F12_sheet.png
  uv run src/kickoff_loop_f12.py test <F12x.toml> [...]    Selbsttest am fertigen Video: Schnitte liegen auf dem Beat
  uv run src/kickoff_loop_f12.py still <F12x.toml> <beat> [...]
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
SHARED = os.path.join(KL.PROJECT, "previz/review/F12/F12.toml")
SRC = hashlib.sha1(open(__file__, "rb").read()).hexdigest()[:12]   # im Cache-Schluessel: Aenderungen hier rendern neu
EPS = 1e-6
OFF = (-3240.0, -5760.0, 1.0, 0.0)                    # Stern weit ausserhalb (schwarze Szenen zeichnen keinen Plakatstern)
ENDS = ("sog", "implode", "rebirth", "dissolve", "hole", "black", "title")
COVER = 1.02           # Spark deckt das Bild: weitestes Pixel x so viel (Rand im Korn)
EVENT_RATIO = 2.0      # test: ein Schnitt setzt auf seinem Bild ein: doppelt so stark wie das Bild davor und der Median davor
EVENT_MIN = 0.003      # ... und mindestens so viel mittlere Aenderung (Encoder-Rauschen im Standbild ~0.0002)
BLACK_LUM = 0.03       # Silhouette = Zellen ueber Schwarz (die Welt im Fenster wechselt alle 2 Bilder, die Maske je Beat)
OLD_SHIFT = 3          # Gegenprobe: dieselben Schnitte 3 Bilder spaeter (so weit lag das F10-Ende hinter dem Beat)


# ---------------------------------------------------------------- Konfiguration und Raster

def main_root():
    """Hauptcheckout (Vorschau, Songs und Cache liegen nur dort, gitignored), auch aus einem Worktree."""
    git = subprocess.run(["git", "-C", KL.ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True).stdout.strip()
    return os.path.dirname(git) if git else KL.ROOT


def load(path):
    """F12.toml + Variante, dazu die MC3-Konfiguration. Prueft am Anfang, was spaeter erst nach Minuten bricht."""
    f = {**tomllib.load(open(SHARED, "rb"))["f12"], **tomllib.load(open(path, "rb"))["f12"]}
    f["code"], f["toml"] = os.path.splitext(os.path.basename(path))[0], os.path.abspath(path)
    cfg = KL.load(os.path.join(KL.ROOT, f["base_toml"]))
    g = json.load(open(os.path.join(KL.ROOT, f["grid"])))
    f["bar1"], f["beat"] = g["in_s"] - f["song_start_s"], g["beat_s"]   # Taktstrich 1 auf der Timeline, Beatlaenge
    root = main_root()
    f["base_video"], f["song"] = (os.path.join(root, f[k]) for k in ("base_video", "song"))
    assert f["end"] in ENDS, f"{path}: end = {f['end']!r}, erlaubt {ENDS}"
    assert len(f["words"]) == f["card_beat"] - f["words_beat"], "je Beat zwischen words_beat und card_beat ein Begriff"
    assert os.path.exists(f["song"]), f"{f['song']} fehlt"
    assert os.path.exists(f["base_video"]), f"{f['base_video']} fehlt (preview {f['base_toml']} --draft)"
    x, y, R, rot = dark_star(cfg, f, frame_at(f, f["birth_beat"]))
    W, H = S.SIZES[FMT][:2]
    dx, dy = f["birth_xy"][0] * W - x, f["birth_xy"][1] * H - y
    assert math.hypot(dx, dy) < 0.8 * star_r(np.float32(dx), np.float32(dy), rot) * R, \
        f"birth_xy {f['birth_xy']} liegt nicht im dunklen Spark (Bild {frame_at(f, f['birth_beat'])})"
    return cfg, f


def t_beat(f, b):
    return f["bar1"] + b * f["beat"]


def frame_at(f, b):
    """Bild, in dem Beat b liegt (es beginnt hoechstens 1/24 s vorher: das Auge sieht den Schnitt, wenn das Ohr ihn hoert)."""
    return math.floor(t_beat(f, b) * FPS - EPS)


def tb_of(f, n):
    """Beat-Position am Ende von Bild n: das Bild, in dem ein Beat liegt, zeigt schon den neuen Zustand (frame_at)."""
    return ((n + 1) / FPS - f["bar1"]) / f["beat"]


def n_end(f):
    return round(f["end_s"] * FPS)


def zoom_dt(cfg, n):
    """Sekunden nach dem Karussell-Ende (Zeitachse des F10-Endes, KE.orbit_state)."""
    return (n - round(cfg["music"]["grid"]["burst_s"] * FPS)) / FPS


def dark_star(cfg, f, n):
    """Der dunkle Spark des MC3-Videos in Bild n: (x, y, R in Pixeln, Drehung)."""
    return tuple(KE.orbit_state(cfg, zoom_dt(cfg, n))["loop"]["digital"]["star"])


def base_until(cfg):
    """Erstes Bild, in dem das MC3-Video den blauen Slogan (F9/F10) zeigt: ab da ist ausserhalb des neuen Sparks Schwarz."""
    e = cfg["ending"]
    return round(cfg["music"]["grid"]["burst_s"] * FPS + e["orbit_pre_at_beats"] * KE.beat(cfg) * FPS)


# ---------------------------------------------------------------- Stil-Dicts (je Bild eins, gecacht wie der Digitalteil)

def st_black(cfg, f):
    """Grundstil der schwarzen Szenen: Satz und Palette wie das F10-Ende an der Eins von Takt 2 (orbit_state), ohne
    Stern und Zoom."""
    st = KE.orbit_state(cfg, zoom_dt(cfg, frame_at(f, f["words_beat"])))
    dg = st["loop"]["digital"]
    st = {k: v for k, v in st.items() if k != "P_spark"}
    st.update(S=KL.S_CODES["S2"], spark_fn=spark_none, type_fn=f12_type, star=(OFF[0] / 1080, OFF[1] / 1920, 0.001))
    st["loop"] = {**st["loop"], "digital": dict(u=dg["u"], offset=list(dg["offset"]), star=list(OFF), show=None)}
    return st


def white(cfg, f):
    """Palette der schwarzen Szenen (hellste Stufe = Schrift im F10-Ende): fuer SPARK ueber wechselnden Welten."""
    return S.PALS[st_black(cfg, f)["P"]]


def world(cfg, f, n):
    """Plakat im Fenster: der Loop laeuft digital weiter, ein Plakat je world_step_frames Bilder ab der Geburt."""
    i = (f["world_start"] + (n - frame_at(f, f["birth_beat"])) // f["world_step_frames"]) % KL.posters(cfg)
    st = KE.poster_digital(cfg, i)
    st["type_fn"] = f12_type
    return st


def scene(cfg, f, st, **kw):
    """Was f12_type zeichnet, in dieser Reihenfolge: black (alles ausser keep), lights, rings, titles, blocks.
    Regionen sind kleine Masken-Beschreibungen (mask), damit das Stil-Dict JSON bleibt (Cache-Schluessel)."""
    sc = dict(black=None, lights=[], rings=[], titles=[dict(value="hi", pal=white(cfg, f))], blocks=[],
              scale=cfg["ending"]["orbit_date_center"])                # KICK-OFF/Datum/Ort wie F9/F10 (date_cap)
    sc.update(kw)
    return dict(st, f12=sc, f12_src=SRC)


def glow(cfg, f, tb, t0=None):
    """Schweif des Lichts (ln-Massstab): F10 (ln 1.6, waechst um creep je Beat ab der Karte); ab t0 der Kick: kick_glow
    mehr, klingt in kick_decay_beats exponentiell ab."""
    e = cfg["ending"]
    g = math.log(e["orbit_flare_max_scale"]) + e["orbit_flare_creep_per_beat"] * max(tb - f["card_beat"], 0)
    if t0 is not None and tb >= t0:
        g += math.log(f["kick_glow"]) * math.exp(-(tb - t0) / f["kick_decay_beats"])
    return round(g, 4)


def light(cfg, f, tb, g, region=None):
    """Ein Licht wie das F10-Ende (flare_state): roter Spark hinter dem Slash, Schweif g, dreht 12 Grad je Beat, Quelle
    = SPARK + KICK-OFF/Datum/Ort + Spark."""
    e = cfg["ending"]
    return dict(xy=list(e["orbit_flare_xy"]), r=e["orbit_flare_r_frac"],
                rot=round(tb * e["orbit_flare_spin_deg_per_beat"] % KE.STAR_SYM_DEG, 3), glow=g,
                peak=e["orbit_flare_peak"], colors=list(e["orbit_flare_colors"]), region=region)


def wave(cfg, f, emit, tb, beats, pw):
    """Welle wie F10 (Sternfront ab dem Spark, Front jedes Bild): None vor dem Start, sonst dict fuer mask/ring.
    pw < 1 = schnell aus dem Spark, dann bremsend (wie motionpack._ripple), F10: 1."""
    e = cfg["ending"]
    u = (tb - emit) / beats
    if u < 0:
        return None
    x, y = e["orbit_flare_xy"]
    return dict(x=x, y=y, rot=round(emit * e["orbit_flare_spin_deg_per_beat"] % KE.STAR_SYM_DEG, 3),
                front=round(e["orbit_wave_reach"] * min(u, 1.0) ** pw, 4), band=e["orbit_wave_band"],
                amp=round(1 - KE.smooth((u - 0.75) / 0.25), 3), done=u >= 1)


def ring(cfg, w):
    e = cfg["ending"]
    return dict(w=w, colors=list(e["orbit_flare_colors"]), rings=e["orbit_wave_rings"], width=e["orbit_wave_ring_width"])


def date_block(region=None):
    return dict(region=region)


def black_end(cfg, f, tb, t0=None):
    """Das F10-Ende (rot, Spark hinter dem Slash, KICK-OFF/Datum/Ort, Kick ab t0 klingt aus); im Stopp geht das Licht
    in einem Bild aus, die Schrift steht in der Stille."""
    st = st_black(cfg, f)
    if tb >= f["stop_beat"]:
        return scene(cfg, f, st, black="all", blocks=[date_block()])
    return scene(cfg, f, st, black="all", lights=[light(cfg, f, tb, glow(cfg, f, tb, t0))], blocks=[date_block()])


def spark(x, y, r, rot):
    """Masken-Beschreibung: Spark-Silhouette, Mitte (x, y) als Bildanteile, Spitzenradius r als Anteil der Bildbreite."""
    return {"spark": [round(x, 5), round(y, 5), round(r, 5), round(rot % KE.STAR_SYM_DEG, 3)]}


def cover_r(x, y, rot):
    """Spitzenradius (Anteil Bildbreite), ab dem der Spark um (x, y) jede Zelle deckt (sternfoermig: der Rand reicht)."""
    W, H = S.SIZES[FMT][:2]
    gy, gx = np.mgrid[0:H // CELL, 0:W // CELL].astype(np.float32)
    dx, dy = (gx + 0.5) * CELL - x * W, (gy + 0.5) * CELL - y * H
    return float((np.hypot(dx, dy) / star_r(dx, dy, rot)).max()) * COVER / W


def grow(r0, r1, u, p=1.0):
    """Radius r0 → r1 mit konstanter Zoomrate (log-linear), u^p: p > 1 = zieht an (Sog), p < 1 = bremst."""
    return r0 * (r1 / r0) ** (min(max(u, 0.0), 1.0) ** p)


def window(f, word, zoom=1.0, xy=(0.5, 0.5)):
    """Begriff in Zeilen ueber die volle Satzbreite (Maske), zoom < 1 = um xy (Bildanteile) geschrumpft."""
    return {"window": dict(word=word, gap_cells=f["window_gap_cells"], margin_cells=f["window_margin_cells"],
                           lead_frac=f["window_lead_frac"], zoom=round(zoom, 5), xy=list(xy))}


# ---------------------------------------------------------------- Ablauf: Geburt, Begriffe, Ende

def birth(cfg, f, n):
    """Neuer Spark im dunklen: startet in birth_xy (im dunklen Spark) mit birth_r0, Drehung des dunklen Sparks + eine
    halbe Zackenteilung (versetzt: Zacken zwischen dessen Zacken), waechst mit konstanter Zoomrate und wandert zur
    Mitte; auf dem letzten Bild vor words_beat deckt er das Bild. → (x, y, r, rot)."""
    n0, n1 = frame_at(f, f["birth_beat"]), frame_at(f, f["words_beat"]) - 1
    u = (n - n0) / (n1 - n0)
    (x0, y0), (x1, y1) = f["birth_xy"], cfg["ending"]["orbit_flare_xy"]
    s = KE.smooth(u)
    rot = dark_star(cfg, f, n)[3] + KE.STAR_SYM_DEG / 2
    r1 = cover_r(x1, y1, dark_star(cfg, f, n1)[3] + KE.STAR_SYM_DEG / 2)
    return x0 + (x1 - x0) * s, y0 + (y1 - y0) * s, grow(f["birth_r0"], r1, u), rot


def words(cfg, f, n, tb, win=None, i=None):
    """F11b: Begriff k als Fenster, darin laeuft der Loop, sonst Schwarz. win ersetzt die Maske (Uebergaenge)."""
    k = min(int(tb) - f["words_beat"], len(f["words"]) - 1)
    return scene(cfg, f, world(cfg, f, n if i is None else i), black={"not": win or window(f, f["words"][k])})


def ignite(cfg, f, n, tb, t0, outside=None, title_window=False):
    """Zuendung auf t0: roter Spark mit Kick (Licht kick_glow mehr, klingt ab), Welle (kick_wave_beats, kick_wave_pow)
    bringt SPARK weiss + KICK-OFF/Datum/Ort. outside = Maske, in der ausserhalb der Welle die Welt weiterlaeuft (None:
    Schwarz, dann leuchtet das Licht sofort ueberall); title_window: SPARK ist bis zur Welle Fenster (F11b-Ende)."""
    w = wave(cfg, f, t0, tb, f["kick_wave_beats"], f["kick_wave_pow"])
    if w["done"] or tb >= f["stop_beat"]:
        return black_end(cfg, f, tb, t0)
    passed = {"passed": w}
    keep = {"and": [outside, {"not": passed}]} if outside else None
    lt = light(cfg, f, tb, glow(cfg, f, tb, t0), region=passed if outside else None)
    title = dict(value="hi", pal=white(cfg, f), region=passed if title_window else None)
    return scene(cfg, f, world(cfg, f, n), black={"not": keep} if keep else "all", lights=[lt], rings=[ring(cfg, w)],
                 titles=[title], blocks=[date_block(region=passed)])


def last(f):
    return window(f, f["words"][-1])


def end_sog(cfg, f, n, tb):
    """F12a Sog: in der letzten halben Beat-Laenge (collapse_beats) schneidet ein schrumpfender Spark die Woerter
    zusammen (beschleunigt, collapse_pow), auf der Eins verschwinden sie im Punkt und der rote Spark zuendet."""
    t0, x, y = f["card_beat"], *cfg["ending"]["orbit_flare_xy"]
    if tb >= t0:
        return ignite(cfg, f, n, tb, t0)
    u = (tb - (t0 - f["collapse_beats"])) / f["collapse_beats"]
    if u < 0:
        return None
    rot = tb * cfg["ending"]["orbit_flare_spin_deg_per_beat"]
    r = grow(cover_r(x, y, rot), f["collapse_r_end"], u, f["collapse_pow"])
    return words(cfg, f, n, tb, {"and": [last(f), spark(x, y, r, rot)]})


def end_implode(cfg, f, n, tb):
    """F12b Implosion: die Zeilen werden in den Spark gezogen (Maske schrumpft um den Spark, beschleunigt), Zuendung."""
    t0 = f["card_beat"]
    if tb >= t0:
        return ignite(cfg, f, n, tb, t0)
    u = (tb - (t0 - f["collapse_beats"])) / f["collapse_beats"]
    if u < 0:
        return None
    z = grow(1.0, f["collapse_r_end"], u, f["collapse_pow"])
    return words(cfg, f, n, tb, window(f, f["words"][-1], z, cfg["ending"]["orbit_flare_xy"]))


def end_rebirth(cfg, f, n, tb):
    """F12c Noch ein Spark: auf der Eins bleibt die Welt im Wort stehen (Standbild), aus dem Spark hinter dem Slash
    waechst wie bei der Geburt ein neuer Spark, darin das rote Ende; in rebirth_beats deckt er das Bild."""
    t0, (x, y) = f["card_beat"], cfg["ending"]["orbit_flare_xy"]
    if tb < t0:
        return None
    u = (tb - t0) / f["rebirth_beats"]
    if u >= 1 or tb >= f["stop_beat"]:
        return black_end(cfg, f, tb)
    rot = tb * cfg["ending"]["orbit_flare_spin_deg_per_beat"]
    inside = spark(x, y, grow(f["rebirth_r0"], cover_r(x, y, rot), u), rot)
    keep = {"and": [last(f), {"not": inside}]}
    return scene(cfg, f, world(cfg, f, frame_at(f, t0) - 1), black={"not": keep},
                 lights=[light(cfg, f, tb, glow(cfg, f, tb), region=inside)], blocks=[date_block(region=inside)])


def end_dissolve(cfg, f, n, tb):
    """F12d Zerfall: auf der Eins steht das rote Ende mit Kick-Licht sofort da, das letzte Wort liegt noch darueber
    und zerfaellt in 16teln (transponierte Bayer-Folge) ueber dissolve_beats."""
    t0 = f["card_beat"]
    if tb < t0:
        return None
    q = (int((tb - t0) * 4) + 1) / (4 * f["dissolve_beats"])
    if q >= 1 or tb >= f["stop_beat"]:
        return black_end(cfg, f, tb, t0)
    stay = {"and": [last(f), {"not": {"bayerT": round(q, 4)}}]}
    gone = {"not": stay}
    return scene(cfg, f, world(cfg, f, n), black=gone, lights=[light(cfg, f, tb, glow(cfg, f, tb, t0), region=gone)],
                 blocks=[date_block(region=gone)])


def end_hole(cfg, f, n, tb):
    """F12e Loch: auf der Eins schlaegt der rote Spark ein Loch in die Woerter (Welle schnell, bremst), darin das Ende,
    draussen laeuft das letzte Wort weiter, bis die Welle draussen ist."""
    return ignite(cfg, f, n, tb, f["card_beat"], outside=last(f)) if tb >= f["card_beat"] else None


def end_black(cfg, f, n, tb):
    """F12f Schwarzer Spark: wie am Anfang, nur umgekehrt. Ein schwarzer Spark waechst in collapse_beats aus dem Spark
    hinter dem Slash ueber die Woerter (zieht an, deckt auf der Eins das Bild), auf der Eins zuendet in ihm der rote."""
    t0, (x, y) = f["card_beat"], cfg["ending"]["orbit_flare_xy"]
    if tb >= t0:
        return ignite(cfg, f, n, tb, t0)
    u = (tb - (t0 - f["collapse_beats"])) / f["collapse_beats"]
    if u < 0:
        return None
    rot = tb * cfg["ending"]["orbit_flare_spin_deg_per_beat"]
    dark = spark(x, y, grow(f["collapse_r_end"], cover_r(x, y, rot), u, f["collapse_pow"]), rot)
    return words(cfg, f, n, tb, {"and": [last(f), {"not": dark}]})


def end_title(cfg, f, n, tb):
    """F12g = F11b-Ende mit Kick: auf der Eins wird SPARK das Fenster, der rote Spark zuendet mit Kick-Licht, die Welle
    (schneller als F11b) macht SPARK weiss und bringt das Datum."""
    return ignite(cfg, f, n, tb, f["card_beat"], outside="title", title_window=True) if tb >= f["card_beat"] else None


END_FN = dict(sog=end_sog, implode=end_implode, rebirth=end_rebirth, dissolve=end_dissolve, hole=end_hole,
              black=end_black, title=end_title)


def plan(cfg, f, n):
    """Was Bild n zeigt: ("base", n) aus dem MC3-Video, ("birth", st, spark, base?) = neuer Spark ueber dem dunklen,
    ("render", st)."""
    if n < frame_at(f, f["birth_beat"]):
        return ("base", n)
    tb = tb_of(f, n)
    if tb < f["words_beat"]:
        sp = birth(cfg, f, n)
        st = scene(cfg, f, world(cfg, f, n), black={"not": spark(*sp)})
        return ("birth", st, sp, n < base_until(cfg))
    return ("render", END_FN[f["end"]](cfg, f, n, tb) or words(cfg, f, n, tb))


# ---------------------------------------------------------------- Zeichnen (Hooks fuer styles.render)

def spark_none(c):
    c.star_m = np.zeros((c.gh, c.gw), bool)


def metric(c, w):
    """Sternfoermiger Abstand vom Spark, normiert (wie KE.wave_metric, aber je Welle eigene Drehung), je Bild gemerkt."""
    memo = c.__dict__.setdefault("_f12_m", {})
    key = (w["x"], w["y"], w["rot"])
    if key not in memo:
        m = S.star_d(c, w["x"] * c.W, w["y"] * c.H, 1.0, w["rot"])[0]
        memo[key] = (m / m.max()).astype(np.float32)
    return memo[key]


def window_mask(c, p):
    """Begriff in Zeilen uebereinander auf voller Satzbreite, zwischen SPARK (+ gap) und unterem Rand (- margin);
    zoom < 1: um xy geschrumpft (naechste Zelle)."""
    measure = c.W - 2 * c.L["x0"]
    cap = math.floor(measure / S.width_per_cap(p["word"]) / c.px) * c.px
    lead = round(cap * p["lead_frac"] / c.px) * c.px
    top, bottom = c.L["tb"][0] + p["gap_cells"] * c.px, c.H - p["margin_cells"] * c.px
    rows = max(1, int((bottom - top - cap) // lead) + 1)
    y0 = top + (bottom - top - (cap + (rows - 1) * lead)) / 2
    m = KE.word_mask(c, [p["word"]] * rows, cap, lead, c.W / 2, y0)[0]
    if p["zoom"] >= 1:
        return m
    (fx, fy), z = p["xy"], p["zoom"]
    cy, cx = fy * c.gh - 0.5, fx * c.gw - 0.5
    sy, sx = np.round(cy + (c.yy - cy) / z).astype(int), np.round(cx + (c.xx - cx) / z).astype(int)
    ok = (sy >= 0) & (sy < c.gh) & (sx >= 0) & (sx < c.gw)
    out = np.zeros_like(m)
    out[ok] = m[sy[ok], sx[ok]]
    return out


def mask(c, spec):
    """Masken-Beschreibung → Bool-Maske auf dem Zellraster."""
    full = np.ones((c.gh, c.gw), bool)
    if spec is None or spec == "all":
        return full
    if spec == "title":
        return np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))
    (op, a), = spec.items()
    thr = S.tile(S.bayer(4), (c.gh, c.gw))
    if op == "not":
        return ~mask(c, a)
    if op == "and":
        return np.logical_and.reduce([mask(c, s) for s in a])
    if op == "bayerT":                                  # transponiert (Zerfall, wie Spark Lens v5 photo fade)
        return S.tile(S.bayer(4).T, (c.gh, c.gw)) < a
    if op == "passed":                                  # hinter der Wellenfront, Kante im Korn (KE.wave_passed)
        return (a["front"] - metric(c, a)) / a["band"] > thr
    if op == "window":
        return window_mask(c, a)
    if op == "spark":
        x, y, r, rot = a
        return S.star_d(c, x * c.W, y * c.H, r * c.W, rot)[0] < 1
    raise ValueError(f"Maske {spec}")


def date_mask(c, sc):
    """KICK-OFF/Datum/Ort wie F10, mittig auf dem Spark hinter dem Slash: (Maske, Verlauf), je Bild gemerkt."""
    if "_f12_d" not in c.__dict__:
        ls = list(c.L["sub"])
        cap, lead = KE.date_cap(c, sc["scale"], ls)
        c._f12_d = KE.word_mask(c, ls, cap, lead, c.W / 2, c.H / 2 - (cap + (len(ls) - 1) * lead) / 2)
    return c._f12_d


def light_layer(c, name, lt, blk, reg):
    """Licht wie KE.flare_layer (gelobt: Schrift + Spark GLOW_SAMPLES-mal um den Spark vergroessert, Gewicht faellt
    nach aussen, eigene Rampe), aber mit dem Block an seiner echten Stelle (blk) und auf die Region reg beschnitten."""
    X, Y = lt["xy"][0] * c.W, lt["xy"][1] * c.H
    centre = (Y / c.px - 0.5, X / c.px - 0.5)
    title = np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))
    star = S.star_d(c, X, Y, lt["r"] * c.W, lt["rot"])[0] < 1
    src = np.maximum.reduce([title * lt["peak"], blk * lt["peak"], star * 1.0]).astype(np.float32)
    g = src.copy()
    for j in range(1, KE.GLOW_SAMPLES + 1):
        sc = math.exp(lt["glow"] * j / KE.GLOW_SAMPLES)
        sy = np.round(centre[0] + (c.yy - centre[0]) / sc).astype(int)
        sx = np.round(centre[1] + (c.xx - centre[1]) / sc).astype(int)
        ok = (sy >= 0) & (sy < c.gh) & (sx >= 0) & (sx < c.gw)
        hit = np.zeros_like(g)
        hit[ok] = src[sy[ok], sx[ok]]
        g = np.maximum(g, hit * (1 - j / (KE.GLOW_SAMPLES + 1)))
    c.layer_pal[name] = KE.ramp(c, lt["colors"])
    c.add(name, (g > KE.GLOW_MIN) & reg, g)


def f12_type(c):
    """Zeichnet die Szene st["f12"] (scene) mit den Bausteinen des F10-Endes."""
    sc = c.st["f12"]
    hi = c.lvl(int((c.pal @ KL.LUMA).argmax()))
    if sc["black"]:
        c.layer_pal["dim"] = np.zeros_like(c.pal)
        c.add("dim", mask(c, sc["black"]), 0.0)
    for j, lt in enumerate(sc["lights"]):
        light_layer(c, f"light{j}", lt, date_mask(c, sc)[0], mask(c, lt["region"]))
    for j, rg in enumerate(sc["rings"]):               # Ring wie KE.flare_layer (Front + Echos)
        w, m = rg["w"], metric(c, rg["w"])
        v = sum(a * np.exp(-((m - (w["front"] - k)) / rg["width"]) ** 2) for k, a in rg["rings"]) * w["amp"]
        v = np.clip(v, 0, 1).astype(np.float32)
        c.layer_pal[f"ring{j}"] = KE.ramp(c, rg["colors"])
        c.add(f"ring{j}", v > KE.GLOW_MIN, v)
    for j, t in enumerate(sc["titles"]):               # SPARK in fester Farbe, egal welche Welt darunter liegt
        mk = np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))
        name, pal = f"title{j}", S.hexpal_list(t["pal"])
        c.layer_pal[name] = pal
        c.add(name, mk & mask(c, t.get("region")), c.lvl(int((pal @ KL.LUMA).argmax())))
    for b in sc["blocks"]:
        c.add("block", date_mask(c, sc)[0] & mask(c, b.get("region")), hi)


# ---------------------------------------------------------------- Rendern

def _job(args):
    """Pool: Bild n rendern (gecacht), zurueck auf dem Zellraster (1/16 der Pixel durch die Pipe)."""
    cfg, f, n = args
    p = plan(cfg, f, n)
    if p[0] == "base":
        return n, None
    img = KL.render_cached(p[1], FMT, "f12")
    return n, np.ascontiguousarray(img[::CELL, ::CELL])


def spark_cells(sp):
    """Maske des neuen Sparks auf dem Zellraster (dieselbe Formel wie mask "spark", Zellmitten wie styles.Canvas)."""
    W, H = S.SIZES[FMT][:2]
    x, y, r, rot = sp
    gy, gx = np.mgrid[0:H // CELL, 0:W // CELL].astype(np.float32)
    dx, dy = (gx + 0.5) * CELL - x * W, (gy + 0.5) * CELL - y * H
    return np.hypot(dx, dy) < star_r(dx, dy, rot % KE.STAR_SYM_DEG) * r * W


def frames(cfg, f, ns):
    """Bilder ns (aufsteigend) als (n, RGB voll), eins nach dem anderen (ein ganzes Video waeren ~2 GB im Speicher).
    MC3-Bilder kommen aus einem Decoder, gerenderte aus dem KL-Pool (imap, in Zeitfolge); in der Geburt liegt der neue
    Spark ueber dem MC3-Bild, solange es den dunklen Spark zeigt (base_until)."""
    W, H = S.SIZES[FMT][:2]
    ps = {n: plan(cfg, f, n) for n in ns}
    it = iter(KL.pool().imap(_job, [(cfg, f, n) for n in ns if ps[n][0] != "base"], chunksize=2))
    dec, at = None, 0

    def base(n):
        nonlocal dec, at
        if dec is None:
            dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", f["base_video"], "-f", "rawvideo", "-pix_fmt",
                                    "rgb24", "-"], stdout=subprocess.PIPE)
        while True:                                                    # Decoder laeuft vorwaerts bis Bild n
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
    """Ganzes Video: MC3 bis zur Geburt, dann F12; Ton = f["song"]. Hardlink nach Vorschau/."""
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

def frame_diff(path):
    """Je Bild: mittlere Helligkeitsaenderung und Aenderung der Silhouette (Anteil Zellen, die zwischen Schwarz und
    Nicht-Schwarz kippen), Graustufen 135 x 240, Bild 0 = 0."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "scale=135:240", "-f", "rawvideo", "-pix_fmt",
                          "gray", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 240, 135).astype(np.float32) / 255
    sil = (a > BLACK_LUM).astype(np.float32)
    return np.r_[0, np.abs(np.diff(a, axis=0)).mean((1, 2))], np.r_[0, np.abs(np.diff(sil, axis=0)).mean((1, 2))]


def events(f):
    """Geplante Schnitte: jeder Begriff (der erste = Maske nach der Geburt), die Eins von Takt 3 (ausser card_cut
    false: dort waechst der neue Spark erst aus einem Punkt), der Stopp. (Bild, Name)."""
    ev = [(frame_at(f, f["words_beat"] + k), w) for k, w in enumerate(f["words"])]
    ev += [(frame_at(f, f["card_beat"]), "Takt 3")] if f.get("card_cut", True) else []
    return ev + [(frame_at(f, f["stop_beat"]), "Stopp")]


def onset(d, n):
    """Setzt die Aenderung auf Bild n ein? -> (ok, Staerke / Vorlauf). Vorlauf = max(Bild davor, Median der 8 davor)."""
    pre = max(float(d[n - 1]), float(np.median(d[max(n - 8, 1):n]))) + 1e-6
    return bool(d[n] >= EVENT_MIN and d[n] > EVENT_RATIO * pre), round(float(d[n] / pre), 1)


def on_beat(diffs, ev, shift=0):
    """Je Schnitt: setzt er genau auf seinem Bild ein (Helligkeit oder Silhouette)? [(Name, Bild, ok, Staerke)]."""
    out = []
    for n, name in ev:
        n += shift
        res = [onset(d, n) for d in diffs]
        out.append((name, n, any(ok for ok, _ in res), max(r for _, r in res)))
    return out


def covered(path, f):
    """Geburt: Anteil schwarzer Zellen im letzten Bild vor der Maske (der neue Spark muss das Bild decken)."""
    n = frame_at(f, f["words_beat"]) - 1
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"select=eq(n\\,{n}),scale=135:240", "-frames:v",
                          "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(240, 135, 3)
    return float((a.max(-1) < 8).mean())


def report(cfg, f, path):
    diffs = frame_diff(path)
    d = diffs[0]
    rows = on_beat(diffs, events(f))
    old = on_beat(diffs, events(f), OLD_SHIFT)
    hole = covered(path, f)
    lines = [f"{f['code']} (Ende {f['end']}), {path}", f"Raster: Taktstrich 1 = {f['bar1']:.3f} s, Beat {f['beat']:.4f} s; "
             f"Geburt ab Beat {f['birth_beat']} = {t_beat(f, f['birth_beat']):.3f} s, Begriffe ab {t_beat(f, f['words_beat']):.3f} s, "
             f"Karte {t_beat(f, f['card_beat']):.3f} s, Stopp {t_beat(f, f['stop_beat']):.3f} s",
             f"Geburt: schwarze Flaeche im letzten Bild vor der Maske {hole * 100:.1f} % (muss ~0 sein)",
             f"Schnitte auf dem Beat (setzt auf dem Bild ein: > {EVENT_RATIO:g}x Vorlauf, Helligkeit oder Silhouette):"]
    lines += [f"  {'ok ' if ok else 'NEIN'} {name:<12} Bild {n} = {n / FPS:.3f} s  x{r}" for name, n, ok, r in rows]
    lines.append(f"Gegenprobe +{OLD_SHIFT} Bilder: {sum(ok for *_, ok, _ in old)}/{len(old)} ok (muss weniger sein)")
    lines.append("Bildaenderung je Sekunde (x100, Befund F10a: 0-5 s ~17, 8-9 s 0.35, 11-12 s 0.10):")
    lines.append("  " + "  ".join(f"{s}:{d[s * FPS:(s + 1) * FPS].mean() * 100:.2f}" for s in range(len(d) // FPS)))
    open(os.path.join(out_dir(f), "report_draft.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return rows, old, hole


def test(cfg, f):
    """Selbsttest am fertigen Video: alle Schnitte auf ihrem Beat-Bild, Gegenprobe (3 Bilder spaeter) schlaegt an, die
    Geburt deckt das Bild vor der Maske (< 0.5 % Schwarz)."""
    rows, old, hole = report(cfg, f, os.path.join(out_dir(f), "preview_draft.mp4"))
    ok = all(r[2] for r in rows) and sum(r[2] for r in old) < len(old) and hole < 0.005
    print(f"{f['code']}: {'OK' if ok else 'FEHLER'}")
    return ok


# ---------------------------------------------------------------- Bogen

SHEET_BEATS = (4.3, 4.6, 4.9, 5.05, 6.1, 7.1, 7.6, 7.85, 8.05, 8.3, 8.7, 9.5, 11.05)   # Beats ab Taktstrich 1


def sheet(variants, path):
    """Standbilder je Variante auf den Beats (Zeilen = Varianten), beschriftet."""
    tw, th = 216, 384
    img = Image.new("RGB", (90 + len(SHEET_BEATS) * tw, len(variants) * (th + 18) + 18), (18, 18, 18))
    dr = ImageDraw.Draw(img)
    for r, (cfg, f) in enumerate(variants):
        ns = [min(frame_at(f, b), n_end(f) - 1) for b in SHEET_BEATS]
        got = dict(frames(cfg, f, sorted(set(ns))))
        y = 18 + r * (th + 18)
        dr.text((6, y + th // 2), f["code"], fill=(255, 220, 0))
        for j, (b, n) in enumerate(zip(SHEET_BEATS, ns)):
            img.paste(Image.fromarray(got[n]).resize((tw, th), Image.BOX), (90 + j * tw, y))
            if r == 0:
                dr.text((90 + j * tw + 4, y - 14), f"Beat {b:g} = {n / FPS:.2f} s", fill=(220, 220, 220))
    img.save(path)
    return path


def main():
    cmd, paths = sys.argv[1], sys.argv[2:]
    variants = [load(p) for p in paths] if cmd != "still" else []
    if cmd == "video":
        for cfg, f in variants:
            print(video(cfg, f))
    elif cmd == "sheet":
        print(sheet(variants, os.path.join(os.path.dirname(SHARED), "F12_sheet.png")))
    elif cmd == "still":                                               # still <toml> <beat> [...]: Standbilder voll
        cfg, f = load(paths[0])
        ns = sorted({min(frame_at(f, float(b)), n_end(f) - 1) for b in paths[1:]})
        for n, img in frames(cfg, f, ns):
            out = os.path.join(out_dir(f), f"still_{n:03d}.png")
            Image.fromarray(img).save(out)
            print(out)
    elif cmd == "test":
        sys.exit(0 if all([test(cfg, f) for cfg, f in variants]) else 1)


if __name__ == "__main__":
    main()
