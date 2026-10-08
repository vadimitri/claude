#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""F11 (Vadim 8.10. zu F10 + Songschnitt M4a: "super antiklimatisch; visuell faszinierender, auf den Beat, keine
Beat-Groessenwechsel, subtil oder Schnitte; Begriffe als Platzhalter, dann das Ende, wie es steht"). Sieben Ideen als
Entwurf: bis zur Eins von Takt 2 laeuft F10a (Vorschau/F10a_draft.mp4), ab dort rendert dieses Skript neu. Jedes
Ereignis liegt auf IGORs Raster (igor_beats.json, ueber song_start_s auf die Timeline gelegt).

Befund, der F11 ausloeste (8.10., F10a gegen M4a): ab 8 s aendert sich das Bild nur noch zu ~2 % des Karussells,
waehrend der Ton 4 dB lauter wird; das F10-Ende zaehlte Beats ab dem synkopierten Drum-Boom (~3 Bilder hinter dem Beat).

Gemeinsame Stellschrauben: kickoff_loop/previz/review/F11/F11.toml, je Idee F11x/F11x.toml ([f11] idea + Abweichungen).
Satz, Licht, Farben und Welle kommen aus der F10a-Konfiguration (base_toml), gezeichnet mit denselben Funktionen
(kickoff_loop_end.flare_layer, word_mask, date_cap): die Endkarte sieht aus wie in F10.

  uv run src/kickoff_loop_f11.py video <F11x.toml> [...]   → previz/review/F11x/preview_draft.mp4 + Vorschau/F11x_draft.mp4
  uv run src/kickoff_loop_f11.py sheet <F11x.toml> [...]   Standbilder auf den Beats → previz/review/F11/F11_sheet.png
  uv run src/kickoff_loop_f11.py test <F11x.toml> [...]    Selbsttest am fertigen Video: Schnitte liegen auf dem Beat
  uv run src/kickoff_loop_f11.py song <F11x.toml>           Songschnitt mit [f11.cut] (F11g2: M4d = M4a bis zur B-Eins)
"""
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import tomllib
from functools import lru_cache

import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image, ImageDraw, ImageOps

import kickoff as K
import kickoff_loop as KL
import kickoff_loop_end as KE
import kickoff_loop_video as V
import styles as S

FPS = 24
FMT = "9x16"
CELL = S.BASE["R"] * S.SIZES[FMT][2]                  # 4 Ausgabepixel pro Zelle
SHARED = os.path.join(KL.PROJECT, "previz/review/F11/F11.toml")
SRC = hashlib.sha1(open(__file__, "rb").read()).hexdigest()[:12]   # im Cache-Schluessel: Aenderungen hier rendern neu
EPS = 1e-6
OFF = (-3240.0, -5760.0, 1.0, 0.0)                    # Stern weit ausserhalb (schwarze Ideen zeichnen keinen Plakatstern)
IDEAS = ("sequencer", "window", "worlds", "photos", "pulse", "lights")
STOPS = ("freeze", "light_off", "black", "hit")
EVENT_RATIO = 2.0      # test: ein Schnitt setzt auf seinem Bild ein: doppelt so stark wie das Bild davor und der Median davor
EVENT_MIN = 0.003      # ... und mindestens so viel mittlere Aenderung (Encoder-Rauschen im Standbild ~0.0002)
BLACK_LUM = 0.03       # Silhouette = Zellen ueber Schwarz (F11b: die Welt im Fenster wechselt alle 2 Bilder, die Maske je Beat)
OLD_SHIFT = 3          # Gegenprobe: dieselben Schnitte 3 Bilder spaeter (so weit lag das F10-Ende hinter dem Beat)


# ---------------------------------------------------------------- Konfiguration und Raster

def main_root():
    """Hauptcheckout (Vorschau, Songs und Cache liegen nur dort, gitignored), auch aus einem Worktree."""
    git = subprocess.run(["git", "-C", KL.ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True).stdout.strip()
    return os.path.dirname(git) if git else KL.ROOT


def load(path):
    """F11.toml + Variante, dazu die F10a-Konfiguration. Prueft am Anfang, was spaeter erst nach Minuten bricht."""
    f = {**tomllib.load(open(SHARED, "rb"))["f11"], **tomllib.load(open(path, "rb"))["f11"]}
    f["code"], f["toml"] = os.path.splitext(os.path.basename(path))[0], os.path.abspath(path)
    cfg = KL.load(os.path.join(KL.ROOT, f["base_toml"]))
    g = json.load(open(os.path.join(KL.ROOT, f["grid"])))
    f["bar1"], f["beat"] = g["in_s"] - f["song_start_s"], g["beat_s"]   # Taktstrich 1 auf der Timeline, Beatlaenge
    root = main_root()
    f["base_video"], f["song"] = (os.path.join(root, f[k]) for k in ("base_video", "song"))
    assert f["idea"] in IDEAS, f"{path}: idea = {f['idea']!r}, erlaubt {IDEAS}"
    assert f["stop"] in STOPS, f"{path}: stop = {f['stop']!r}, erlaubt {STOPS}"
    assert len(f["words"]) == f["card_beat"] - f["words_beat"], "je Beat zwischen words_beat und card_beat ein Begriff"
    for k in ("ramps", "world_posters", "light_from", "light_drift", "photos"):
        if k in f:
            assert len(f[k]) == len(f["words"]), f"{path}: {k} braucht {len(f['words'])} Eintraege (einen je Begriff)"
    for r in f.get("ramps", []):
        assert not KL.is_lilac(r), f"{path}: Rampe {r} streift Lila (gehoert der Maker Night)"
    if not os.path.exists(f["song"]):
        sys.exit(f"{f['song']} fehlt. F11g2: erst `uv run src/kickoff_loop_f11.py song {path}`")
    assert os.path.exists(f["base_video"]), f"{f['base_video']} fehlt (preview {f['base_toml']} --draft)"
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


# ---------------------------------------------------------------- Stil-Dicts (je Bild eins, gecacht wie der Digitalteil)

def pal_code(hexes):
    """Eigene Palette (Licht-Rampe) als Code wie KL.palette, im Prozess registriert (Pool-Worker bauen den Stil selbst)."""
    name = "loop:" + "".join(h[1:].upper() for h in hexes)
    S.PALS[name] = list(hexes)
    return name


def st_black(cfg, f):
    """Grundstil der schwarzen Szenen: Satz und Palette wie das F10-Ende an der Eins von Takt 2 (orbit_state), ohne
    Stern und Zoom; schwarz macht erst die Szene (black)."""
    zoom_end = round(cfg["music"]["grid"]["burst_s"] * FPS)
    st = KE.orbit_state(cfg, (frame_at(f, f["words_beat"]) - zoom_end) / FPS)
    dg = st["loop"]["digital"]
    st = {k: v for k, v in st.items() if k != "P_spark"}
    st.update(S=KL.S_CODES["S2"], spark_fn=spark_none, type_fn=f11_type, star=(OFF[0] / 1080, OFF[1] / 1920, 0.001))
    st["loop"] = {**st["loop"], "digital": dict(u=dg["u"], offset=list(dg["offset"]), star=list(OFF), show=None)}
    return st


def white(cfg, f):
    """Palette der schwarzen Szenen (hellste Stufe = Schrift im F10-Ende): fuer SPARK ueber wechselnden Welten."""
    return S.PALS[st_black(cfg, f)["P"]]


def st_world(cfg, i, star=None, P=None, S2=False):
    """Plakat i im Digitalteil (KE.poster_digital), eigener Satz; star = (x, y, r als Bildanteile, Drehung) setzt den
    Stern fest (F11c), P eine andere Palette, S2 den vollen Stern (Uebergang ins rote Ende)."""
    st = KE.poster_digital(cfg, i)
    if star is not None:
        W, H = S.SIZES[FMT][:2]
        x, y, r, rot = star
        st["loop"] = {**st["loop"], "digital": {**st["loop"]["digital"], "star": (x * W, y * H, r * W, rot)}}
        st.update(star=(x, y, r), rot=rot)
    if P:
        st["P"] = P
    if S2:
        st.update(S=KL.S_CODES["S2"], spark_fn=K.spark)
    st["type_fn"] = f11_type
    return st


def scene(cfg, f, st, **kw):
    """Was f11_type zeichnet, in dieser Reihenfolge: photo, black (alles ausser keep), lights, rings, titles, blocks.
    Regionen sind kleine Masken-Beschreibungen (mask), damit das Stil-Dict JSON bleibt (Cache-Schluessel)."""
    sc = dict(photo=None, black=None, lights=[], rings=[], titles=[dict(value="hi")], blocks=[],
              scale=cfg["ending"]["orbit_date_center"],                # KICK-OFF/Datum/Ort wie F9/F10 (date_cap)
              words=list(f["words"]), word_scale_max=f["word_scale_max"], word_y=f["word_y"])
    sc.update(kw)
    st = dict(st, f11=sc, f11_src=SRC)
    return st


def light(cfg, f, colors, lines, text, tb, r=None, xy=None, glow=None, region=None):
    """Ein Licht wie das F10-Ende (flare_state): Spark am Ort xy, Schweif ln-Massstab glow (F10: ln 1.6, waechst um
    creep je Beat), dreht 12 Grad je Beat. lines = Block (None = KICK-OFF/Datum/Ort), text = Anteil seines Schweifs."""
    e = cfg["ending"]
    g = math.log(e["orbit_flare_max_scale"]) + e["orbit_flare_creep_per_beat"] * max(tb - f["words_beat"], 0)
    return dict(xy=list(xy or e["orbit_flare_xy"]), r=round(e["orbit_flare_r_frac"] if r is None else r, 4),
                rot=round(tb * e["orbit_flare_spin_deg_per_beat"] % KE.STAR_SYM_DEG, 3),
                glow=round(g if glow is None else glow, 4), peak=e["orbit_flare_peak"], colors=list(colors),
                lines=lines, text=round(text, 4), region=region)


def wave(cfg, f, emit, tb, beats, pw=None):
    """Welle wie F10 (Sternfront ab dem Spark, Front jedes Bild): None vor dem Start, sonst dict fuer mask/ring.
    pw < 1 = schnell aus dem Spark, dann bremsend (wie motionpack._ripple), F10: 1."""
    e = cfg["ending"]
    u = (tb - emit) / beats
    if u < 0:
        return None
    x, y = e["orbit_flare_xy"]
    return dict(x=x, y=y, rot=round(emit * e["orbit_flare_spin_deg_per_beat"] % KE.STAR_SYM_DEG, 3),
                front=round(e["orbit_wave_reach"] * min(u, 1.0) ** (pw or e["orbit_wave_pow"]), 4), band=e["orbit_wave_band"],
                amp=round(1 - KE.smooth((u - 0.75) / 0.25), 3), done=u >= 1)


def ring(cfg, w, colors):
    e = cfg["ending"]
    return dict(w=w, colors=list(colors), rings=e["orbit_wave_rings"], width=e["orbit_wave_ring_width"])


def date_block(value="hi", region=None, reveal=None):
    return dict(lines=None, value=value, region=region, reveal=reveal)


def black_end(cfg, f, tb, st=None):
    """Das F10-Ende (rot, Spark hinter dem Slash, KICK-OFF/Datum/Ort) und der Stopp nach f["stop"]."""
    e = cfg["ending"]
    st = st or st_black(cfg, f)
    if tb >= f["stop_beat"] and f["stop"] in ("light_off", "black", "hit"):
        return scene(cfg, f, st, black="all", blocks=[date_block()])            # Licht in einem Bild aus, Schrift bleibt
    lt = light(cfg, f, e["orbit_flare_colors"], None, 1.0, min(tb, f["stop_beat"] - EPS))
    return scene(cfg, f, st, black="all", lights=[lt], blocks=[date_block()])


# ---------------------------------------------------------------- Die Ideen: Zustand je Bild (tb = Beat-Position)

def idea_sequencer(cfg, f, n, tb):
    """F11a Bayer-Sequencer: Bayer 4x4 hat 16 Schwellen, ein Takt 16 Sechzehntel. Jeder Begriff setzt in seinem Beat in
    steps_per_beat Bayer-Stufen ein (eine je 16tel), das Licht waechst mit; ab der Eins von Takt 3 setzt der
    Datumsblock in 16teln ein (1/16 je 16tel), die fehlenden Stufen fallen alle in den Stopp: das Bild steht in der
    Stille fertig da (keine Bewegung mehr). Das Licht (seq_glow_scale, laenger als F10) setzt mit ein: das Bild wird
    in Durchgaengen gedruckt."""
    e = cfg["ending"]
    tq = min(tb, f["stop_beat"] - EPS)
    if tb < f["card_beat"]:
        k = int(tb) - f["words_beat"]
        q = (int((tb % 1) * f["steps_per_beat"]) + 1) / f["steps_per_beat"]
        lines, colors = [f["words"][k]], e["orbit_pre_colors"]
    else:
        q = 1.0 if tb >= f["stop_beat"] else (int((tb - f["card_beat"]) * 4) + 1) / 16
        lines, colors = None, e["orbit_flare_colors"]
    reveal = {"bayer": round(q, 4)}                                    # Schrift und Licht setzen gemeinsam im Korn ein
    lt = light(cfg, f, colors, lines, 1.0, tq, glow=math.log(f["seq_glow_scale"]), region=reveal)
    return scene(cfg, f, st_black(cfg, f), black="all", lights=[lt], blocks=[dict(lines=lines, value="hi", region=reveal)])


def idea_window(cfg, f, n, tb):
    """F11b Schrift als Fenster: der Begriff steht in Zeilen uebereinander ueber die volle Satzbreite (HARDWARE
    HARDWARE HARDWARE ...), in den Buchstaben laeuft das Karussell digital weiter (Plakat je world_step_frames Bilder),
    sonst Schwarz. Je Beat schneidet nur die Maske, die Welt darin laeuft durch. Ab der Eins von Takt 3 ist SPARK das
    Fenster, die rote Welle (F10, ueber wave_beats) macht dahinter SPARK weiss und bringt Licht und Datum."""
    e = cfg["ending"]
    i = (f["world_start"] + (n - frame_at(f, f["words_beat"])) // f["world_step_frames"]) % KL.posters(cfg)
    if tb < f["card_beat"]:
        win = {"window": dict(word=f["words"][int(tb) - f["words_beat"]], gap_cells=f["window_gap_cells"],
                              margin_cells=f["window_margin_cells"], lead_frac=f["window_lead_frac"])}
        return scene(cfg, f, st_world(cfg, i), black={"not": win}, titles=[dict(value="hi", pal=white(cfg, f))])
    w = wave(cfg, f, f["card_beat"], tb, f["wave_beats"])
    if w["done"] or tb >= f["stop_beat"]:
        return black_end(cfg, f, tb)
    passed = {"passed": w}
    lt = light(cfg, f, e["orbit_flare_colors"], None, 1.0, tb, region=passed)
    return scene(cfg, f, st_world(cfg, i), black={"not": {"and": ["title", {"not": passed}]}}, lights=[lt],
                 rings=[ring(cfg, w, e["orbit_flare_colors"])], titles=[dict(value="hi", region=passed, pal=white(cfg, f))],
                 blocks=[date_block(region=passed)])


def idea_worlds(cfg, f, n, tb):
    """F11c Ein Stern, viele Welten: ein grosser Stern steht fest (Lage, Groesse, dreht stetig), je Beat schneidet seine
    Welt (Stil + Colorway eines anderen Plakats): Match-Cut auf die Silhouette. Begriff mittig, kippt als Ganzes wie
    JOIN US, SPARK als Differenz wie auf den Plakaten. Ab der Eins von Takt 3: voller Stern (S2) in Rot, zieht sich in
    shrink_beats auf den Spark hinter dem Slash zusammen (ease-in), dann das F10-Ende."""
    e = cfg["ending"]
    x, y, r = f["world_star"]
    rot = f["world_rot_deg"] + f["world_spin_deg_per_beat"] * (tb - f["words_beat"])
    if tb < f["card_beat"]:
        k = int(tb) - f["words_beat"]
        st = st_world(cfg, f["world_posters"][k], star=(x, y, r, round(rot % 360, 3)))
        return scene(cfg, f, st, titles=[dict(value="xor")], blocks=[dict(lines=[f["words"][k]], value="flip")])
    u = (tb - f["card_beat"]) / f["shrink_beats"]
    if u >= 1:
        return black_end(cfg, f, tb)
    a = u ** 2                                                         # ease-in: zieht an, verschwindet im Spark
    sx, sy = e["orbit_flare_xy"]
    star = (x + (sx - x) * a, y + (sy - y) * a, r + (e["orbit_flare_r_frac"] - r) * a, round(rot % 360, 3))
    st = st_world(cfg, f["world_posters"][-1], star=star, P=pal_code(e["orbit_flare_colors"]), S2=True)
    return scene(cfg, f, st, black={"not": "star"}, titles=[dict(value="xor")])


def idea_photos(cfg, f, n, tb):
    """F11d Werkstatt-Inserts: je Beat ein Foto aus dem Club, durch den Spark-Look (Zellraster, Bayer, Colorway eines
    Plakats), langsam naeher (zoom_per_beat, stetig, kein Beat-Stoss). Begriff mittig, kippt als Ganzes, SPARK als
    Differenz. Ab der Eins von Takt 3 zerfaellt das letzte Foto in dissolve_beats im Korn (transponierte Bayer-Folge,
    auf 16teln) zu Schwarz, dahinter das rote F10-Ende."""
    e = cfg["ending"]
    k = min(int(tb) - f["words_beat"], len(f["photos"]) - 1)
    ph = f["photos"][k]
    photo = dict(path=ph["path"], focus=ph["focus"], gamma=ph.get("gamma", 1.0), blur=f["photo_blur_cells"],
                 zoom=round(ph.get("zoom", 1.0) * (1 + f["zoom_per_beat"] * (tb - f["words_beat"] - k)), 4))
    st = dict(st_black(cfg, f), P=pal_code(f["ramps"][k]))         # Duoton: Schwarz → Farbe → Weiss je Foto
    if tb < f["card_beat"]:
        return scene(cfg, f, st, photo=photo, titles=[dict(value="flip")], blocks=[dict(lines=[f["words"][k]], value="flip")])
    q = (int((tb - f["card_beat"]) * 4) + 1) / (4 * f["dissolve_beats"])   # eine Stufe je 16tel
    if q >= 1:
        return black_end(cfg, f, tb)
    gone = {"bayerT": round(q, 4)}
    lt = light(cfg, f, e["orbit_flare_colors"], None, 1.0, tb, region=gone)
    return scene(cfg, f, st, photo=photo, black=gone, lights=[lt], titles=[dict(value="flip", region={"not": gone}),
                                                                 dict(value="hi", region=gone)],
                 blocks=[date_block(region=gone)])


def idea_pulse(cfg, f, n, tb):
    """F11e Puls aus dem Spark: der Spark hinter dem Slash schickt je Beat eine Sternwelle (F10-Front), hinter ihr
    stehen der naechste Begriff und das naechste Licht (ramps), die fuenfte Welle auf der Eins von Takt 3 bringt Rot
    und KICK-OFF/Datum/Ort. Jede Welle startet wave_lead_16ths vor ihrem Beat, damit die Front auf dem Beat am Wort ist
    (das Wort liegt um den Spark). Stopp: siehe black_end (F11g1 schwarz, F11g2 Standbild + Hit)."""
    e = cfg["ending"]
    if tb >= f["stop_beat"]:
        return pulse_hit(cfg, f, tb) if f["stop"] == "hit" else black_end(cfg, f, tb)
    ramps = [*f["ramps"], e["orbit_flare_colors"]]                     # je Begriff eine (F11.toml), Takt 3 = Rot
    lines = [[w] for w in f["words"]] + [None]
    lead = f["wave_lead_16ths"] / 4
    emits = [f["words_beat"] + k - lead for k in range(len(f["words"]))] + [f["card_beat"] - lead]
    ws = [wave(cfg, f, a, tb, f["pulse_wave_beats"], f["pulse_wave_pow"]) for a in emits]
    live = [k for k, w in enumerate(ws) if w]
    lights, rings, blocks = [], [], []
    top = live[-1]
    for k in live:
        nxt = ws[k + 1] if k + 1 < len(ws) else None
        if nxt and nxt["done"]:
            continue                                                   # ganz von der naechsten Welle ueberrollt
        region = {"passed": ws[k]} if not nxt else {"and": [{"passed": ws[k]}, {"not": {"passed": nxt}}]}
        lights.append(light(cfg, f, ramps[k], lines[k], 1.0, tb, r=None if k == top else 0.0, region=region))
        blocks.append(dict(lines=lines[k], value="hi", region=region))
        if not ws[k]["done"]:
            rings.append(ring(cfg, ws[k], ramps[k]))
    return scene(cfg, f, st_black(cfg, f), black="all", lights=lights, rings=rings, blocks=blocks)


def pulse_hit(cfg, f, tb):
    """F11g2 auf den Hit nach dem Stopp: rote Endkarte mit vollem Licht (hit_glow_scale), letzte Welle, das Licht klingt
    ueber hit_decay_beats exponentiell aus (Standbild davor: video_frames, freeze)."""
    e = cfg["ending"]
    x = tb - f["hit_beat"]
    g = math.log(f["hit_glow_scale"]) * math.exp(-x / f["hit_decay_beats"])
    w = wave(cfg, f, f["hit_beat"], tb, f["pulse_wave_beats"], f["pulse_wave_pow"])
    return scene(cfg, f, st_black(cfg, f), black="all", lights=[light(cfg, f, e["orbit_flare_colors"], None, 1.0, tb, glow=g)],
                 rings=[] if w["done"] else [ring(cfg, w, e["orbit_flare_colors"])], blocks=[date_block()])


def idea_lights(cfg, f, n, tb):
    """F11f Lichtregie: Satz steht, nur das Licht schneidet. Je Beat kommt der Lichtschweif (dasselbe Verfahren wie das
    F10-Leuchten) von einer anderen Stelle ausserhalb des Bilds (light_from, Kick unten, Snare oben) und wandert im Beat
    stetig ein Stueck (light_drift). Ab der Eins von Takt 3 der rote Spark hinter dem Slash wie F10, im Stopp aus."""
    e = cfg["ending"]
    if tb >= f["card_beat"]:
        return black_end(cfg, f, tb)
    k = int(tb) - f["words_beat"]
    p = tb % 1
    xy = [f["light_from"][k][j] + f["light_drift"][k][j] * p for j in (0, 1)]
    lt = light(cfg, f, e["orbit_pre_colors"], [f["words"][k]], 1.0, tb, r=0.0, xy=[round(v, 4) for v in xy],
               glow=math.log(f["light_scale"]))
    return scene(cfg, f, st_black(cfg, f), black="all", lights=[lt], blocks=[dict(lines=[f["words"][k]], value="hi")])


IDEA_FN = dict(sequencer=idea_sequencer, window=idea_window, worlds=idea_worlds, photos=idea_photos,
               pulse=idea_pulse, lights=idea_lights)


def plan(cfg, f, n):
    """Was Bild n zeigt: ("base", n) aus F10a, ("render", st), ("black",) oder ("freeze", m) = Bild m in 2 Stufen."""
    if n < frame_at(f, f["words_beat"]):
        return ("base", n)
    tb = tb_of(f, n)
    if f["stop"] == "black" and tb >= f["stop_beat"]:
        return ("black",)
    if f["stop"] == "hit" and f["stop_beat"] <= tb < f["hit_beat"]:
        return ("freeze", frame_at(f, f["stop_beat"]) - 1)
    return ("render", IDEA_FN[f["idea"]](cfg, f, n, tb))


# ---------------------------------------------------------------- Zeichnen (Hooks fuer styles.render)

def spark_none(c):
    c.star_m = np.zeros((c.gh, c.gw), bool)


def metric(c, w):
    """Sternfoermiger Abstand vom Spark, normiert (wie KE.wave_metric, aber je Welle eigene Drehung), je Bild gemerkt."""
    memo = c.__dict__.setdefault("_f11_m", {})
    key = (w["x"], w["y"], w["rot"])
    if key not in memo:
        m = S.star_d(c, w["x"] * c.W, w["y"] * c.H, 1.0, w["rot"])[0]
        memo[key] = (m / m.max()).astype(np.float32)
    return memo[key]


def window_mask(c, p):
    """Begriff in Zeilen uebereinander auf voller Satzbreite, zwischen SPARK (+ gap) und unterem Rand (- margin)."""
    measure = c.W - 2 * c.L["x0"]
    cap = math.floor(measure / S.width_per_cap(p["word"]) / c.px) * c.px
    lead = round(cap * p["lead_frac"] / c.px) * c.px
    top, bottom = c.L["tb"][0] + p["gap_cells"] * c.px, c.H - p["margin_cells"] * c.px
    rows = max(1, int((bottom - top - cap) // lead) + 1)
    y0 = top + (bottom - top - (cap + (rows - 1) * lead)) / 2
    return KE.word_mask(c, [p["word"]] * rows, cap, lead, c.W / 2, y0)[0]


def mask(c, spec):
    """Masken-Beschreibung → Bool-Maske auf dem Zellraster."""
    full = np.ones((c.gh, c.gw), bool)
    if spec is None or spec == "all":
        return full
    if spec == "title":
        return np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))
    if spec == "star":
        return c.star_m.copy()
    (op, a), = spec.items()
    thr = S.tile(S.bayer(4), (c.gh, c.gw))
    if op == "not":
        return ~mask(c, a)
    if op == "and":
        return np.logical_and.reduce([mask(c, s) for s in a])
    if op == "bayer":                                   # Bayer-Reihenfolge (Einsetzen im Korn)
        return thr < a
    if op == "bayerT":                                  # transponiert (Zerfall, wie Spark Lens v5 photo fade)
        return S.tile(S.bayer(4).T, (c.gh, c.gw)) < a
    if op == "passed":                                  # hinter der Wellenfront, Kante im Korn (KE.wave_passed)
        return (a["front"] - metric(c, a)) / a["band"] > thr
    if op == "window":
        return window_mask(c, a)
    raise ValueError(f"Maske {spec}")


@lru_cache(maxsize=8)
def photo_lum(path):
    """Helligkeit des Fotos (0..1, auf 2400 px), Weiss-/Schwarzpunkt aus dem ganzen Foto (1 %/99 %): fest je Foto,
    damit der Ausschnitt beim Naeherkommen nicht pumpt."""
    im = ImageOps.exif_transpose(Image.open(os.path.expanduser(path))).convert("L")
    im.thumbnail((2400, 2400))
    a = np.asarray(im, np.float32) / 255
    lo, hi = np.percentile(a, (1, 99))
    return np.clip((a - lo) / max(hi - lo, 1e-3), 0, 1).astype(np.float32)   # float32: PIL "F" liest sonst Muell


def photo_field(c, ph):
    """9:16-Ausschnitt um focus (Bildanteile), zoom > 1 = naeher, < 1 = weiter (Rand mit der Bildkante aufgefuellt:
    Produktfoto auf Weiss), flaechengemittelt auf das Zellraster."""
    a = photo_lum(ph["path"])
    h, w = a.shape
    ch = min(h, w * 16 / 9) / ph["zoom"]
    cw = ch * 9 / 16
    pad = int(math.ceil(max(cw - w, ch - h, 0) / 2)) + 1 if ph["zoom"] < 1 else 0
    if pad:
        a, h, w = np.pad(a, pad, mode="edge"), h + 2 * pad, w + 2 * pad
    x0 = min(max(pad + ph["focus"][0] * (w - 2 * pad) - cw / 2, 0), w - cw)
    y0 = min(max(pad + ph["focus"][1] * (h - 2 * pad) - ch / 2, 0), h - ch)
    im = Image.fromarray(a, "F").resize((c.gw, c.gh), Image.BOX, box=(x0, y0, x0 + cw, y0 + ch))
    v = gaussian_filter(np.asarray(im, np.float32), ph["blur"]) if ph["blur"] else np.asarray(im, np.float32)
    return np.clip(v, 0, 1) ** ph["gamma"]


def block(c, sc, lines, wscale):
    """Maske + Verlauf eines Blocks: Begriff (lines) gleich gross fuer alle Begriffe, Mitte auf word_y (ueber dem
    Spark: so faechert sein Licht nach oben auf, mittig auf dem Spark las es sich als Balken); None = KICK-OFF/Datum/Ort
    wie F10, mittig auf dem Spark hinter dem Slash."""
    memo = c.__dict__.setdefault("_f11_b", {})
    key = tuple(lines or ())
    if key not in memo:
        ls = lines or list(c.L["sub"])
        cap, lead = KE.date_cap(c, wscale if lines else sc["scale"], ls)
        y = (sc["word_y"] if lines else 0.5) * c.H
        memo[key] = KE.word_mask(c, ls, cap, lead, c.W / 2, y - (cap + (len(ls) - 1) * lead) / 2)
    return memo[key]


def light_layer(c, name, lt, blk, reg):
    """Licht wie KE.flare_layer (gelobt: Schrift + Spark GLOW_SAMPLES-mal um den Spark vergroessert, Gewicht faellt
    nach aussen, eigene Rampe), aber mit dem Block an seiner echten Stelle (blk) und auf die Region reg beschnitten."""
    X, Y = lt["xy"][0] * c.W, lt["xy"][1] * c.H
    centre = (Y / c.px - 0.5, X / c.px - 0.5)
    title = np.logical_or.reduce(KL.line_masks(c, KL.text_lines(c)["title"], centered=True))
    star = S.star_d(c, X, Y, lt["r"] * c.W, lt["rot"])[0] < 1 if lt["r"] > 0 else np.zeros((c.gh, c.gw), bool)
    src = np.maximum.reduce([title * lt["peak"], blk * lt["peak"] * lt["text"], star * 1.0]).astype(np.float32)
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


def f11_type(c):
    """Zeichnet die Szene st["f11"] (scene) mit den Bausteinen des F10-Endes."""
    sc = c.st["f11"]
    hi = c.lvl(int((c.pal @ KL.LUMA).argmax()))
    if sc["photo"]:
        c.add("photo", np.ones((c.gh, c.gw), bool), photo_field(c, sc["photo"]))
    if sc["black"]:
        c.layer_pal["dim"] = np.zeros_like(c.pal)
        c.add("dim", mask(c, sc["black"]), 0.0)
    wscale = min(sc["word_scale_max"], (c.W - 2 * c.L["x0"]) / (c.L["capd"] * max(map(S.width_per_cap, sc["words"]))))
    for j, lt in enumerate(sc["lights"]):
        light_layer(c, f"light{j}", lt, block(c, sc, lt["lines"], wscale)[0], mask(c, lt["region"]))
    for j, rg in enumerate(sc["rings"]):               # Ring wie KE.flare_layer (Front + Echos)
        w, m = rg["w"], metric(c, rg["w"])
        v = sum(a * np.exp(-((m - (w["front"] - k)) / rg["width"]) ** 2) for k, a in rg["rings"]) * w["amp"]
        v = np.clip(v, 0, 1).astype(np.float32)
        c.layer_pal[f"ring{j}"] = KE.ramp(c, rg["colors"])
        c.add(f"ring{j}", v > KE.GLOW_MIN, v)
    steps = c.st["loop"]["type"]["text_gradient_steps"]
    for j, t in enumerate(sc["titles"]):
        lines = KL.text_lines(c)["title"]
        ms = KL.line_masks(c, lines, centered=True)
        mk, v = np.logical_or.reduce(ms), np.zeros((c.gh, c.gw), np.float32)
        for (s, b, cap), m in zip(lines, ms):
            v = np.where(m, KL.line_gradient(c, b, cap, steps), v)
        name, val = "title", {"xor": lambda: KL.title_value(c, v), "flip": lambda: KL.flip_word(c, mk, v)}.get(
            t["value"], lambda: hi)()                                  # flip: Fotos (weisses Produktfoto: SPARK dunkel)
        if t.get("pal"):                                               # feste Farbe, egal welche Welt darunter liegt
            name, pal = f"title{j}", S.hexpal_list(t["pal"])
            c.layer_pal[name], val = pal, c.lvl(int((pal @ KL.LUMA).argmax()))
        c.add(name, mk & mask(c, t.get("region")), val)
    for b in sc["blocks"]:
        mk, v = block(c, sc, b["lines"], wscale)
        val = KL.flip_word(c, mk, v) if b["value"] == "flip" else hi
        c.add("block", mk & mask(c, b.get("region")), val)


# ---------------------------------------------------------------- Rendern

def _job(args):
    """Pool: Bild n rendern (gecacht), zurueck auf dem Zellraster (1/16 der Pixel durch die Pipe)."""
    cfg, f, n = args
    p = plan(cfg, f, n)
    if p[0] != "render":
        return n, None
    img = KL.render_cached(p[1], FMT, "f11")
    return n, np.ascontiguousarray(img[::CELL, ::CELL])


def two_tone(img):
    """Standbild im Stopp (Impact, Spider-Verse): das Bild auf zwei Stufen, Schwarz und Weiss, an der Bildhelligkeit."""
    lum = img.astype(np.float32) @ KL.LUMA
    return np.repeat(np.where(lum > 127, 255, 0).astype(np.uint8)[..., None], 3, -1)


def frames(cfg, f, ns):
    """Bilder ns (aufsteigend) als (n, RGB voll), eins nach dem anderen (ein ganzes Video waeren ~2 GB im Speicher).
    F10a-Bilder kommen aus einem Decoder, gerenderte aus dem KL-Pool (imap, in Zeitfolge)."""
    W, H = S.SIZES[FMT][:2]
    ps = {n: plan(cfg, f, n) for n in ns}
    keep = {p[1] for p in ps.values() if p[0] == "freeze"}           # Quelle des Standbilds merken
    need = sorted({n for n in ns if ps[n][0] == "render"} | keep)
    it = iter(KL.pool().imap(_job, [(cfg, f, n) for n in need], chunksize=2))
    dec, at, kept = None, 0, {}

    def pull(target):                                                  # Pool bis zu diesem Bild abholen
        while target not in kept:
            m, small = next(it)
            kept[m] = S.up(small, CELL)
        return kept[target] if target in keep else kept.pop(target)

    for n in ns:
        p = ps[n]
        if p[0] == "base":
            if dec is None:
                dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", f["base_video"], "-f", "rawvideo", "-pix_fmt",
                                        "rgb24", "-"], stdout=subprocess.PIPE)
            while True:                                                # Decoder laeuft vorwaerts bis Bild n
                img = np.frombuffer(dec.stdout.read(W * H * 3), np.uint8).reshape(H, W, 3)
                at += 1
                if at > n:
                    break
        elif p[0] == "black":
            img = np.zeros((H, W, 3), np.uint8)
        elif p[0] == "freeze":
            img = two_tone(pull(p[1]))
        else:
            img = pull(n)
        yield n, img
    if dec:
        dec.kill()


def out_dir(f):
    d = os.path.dirname(f["toml"])
    os.makedirs(d, exist_ok=True)
    return d


def video(cfg, f):
    """Ganzes Video: F10a bis zur Eins von Takt 2, dann F11; Ton = f["song"]. Hardlink nach Vorschau/."""
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
    """Geplante Schnitte: jeder Begriff, die Eins von Takt 3, der Stopp (ausser freeze: dort steht das Bild nur
    still), bei hit auch der Hit. (Bild, Name). Der Puls hat keine Schnitte, seine Wellen laufen stetig (die Front
    erreicht das Wort auf dem Beat): dort zaehlen nur Stopp und Hit."""
    ev = [] if f["idea"] == "pulse" else [(frame_at(f, f["words_beat"] + k), w) for k, w in enumerate(f["words"])]
    ev += [] if f["idea"] == "pulse" else [(frame_at(f, f["card_beat"]), "Takt 3")]
    if f["stop"] != "freeze":
        ev.append((frame_at(f, f["stop_beat"]), "Stopp"))
    if f["stop"] == "hit":
        ev.append((frame_at(f, f["hit_beat"]), "Hit"))
    return ev


def onset(d, n):
    """Setzt die Aenderung auf Bild n ein? -> (ok, Staerke / Vorlauf). Vorlauf = max(Bild davor, Median der 8 davor):
    nach einem Schnitt darf es weiterlaufen (Ring nach dem Hit), davor nicht."""
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


def report(cfg, f, path):
    diffs = frame_diff(path)
    d = diffs[0]
    rows = on_beat(diffs, events(f))
    old = on_beat(diffs, events(f), OLD_SHIFT)
    lines = [f"{f['code']} ({f['idea']}, Stopp {f['stop']}), {path}", f"Raster: Taktstrich 1 = {f['bar1']:.3f} s, Beat "
             f"{f['beat']:.4f} s; Begriffe ab Beat {f['words_beat']} = {t_beat(f, f['words_beat']):.3f} s, Karte "
             f"{t_beat(f, f['card_beat']):.3f} s, Stopp {t_beat(f, f['stop_beat']):.3f} s",
             f"Schnitte auf dem Beat (setzt auf dem Bild ein: > {EVENT_RATIO:g}x Vorlauf, Helligkeit oder Silhouette):"]
    lines += [f"  {'ok ' if ok else 'NEIN'} {name:<12} Bild {n} = {n / FPS:.3f} s  x{r}" for name, n, ok, r in rows]
    lines.append(f"Gegenprobe +{OLD_SHIFT} Bilder (wie F10): {sum(ok for *_, ok, _ in old)}/{len(old)} ok "
                 f"(muss weniger sein)")
    lines.append("Bildaenderung je Sekunde (x100, Befund F10a: 0-5 s ~17, 8-9 s 0.35, 11-12 s 0.10):")
    lines.append("  " + "  ".join(f"{s}:{d[s * FPS:(s + 1) * FPS].mean() * 100:.2f}" for s in range(len(d) // FPS)))
    open(os.path.join(out_dir(f), "report_draft.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return rows, old


def test(cfg, f):
    """Selbsttest am fertigen Video: alle Schnitte auf ihrem Beat-Bild, die Gegenprobe (3 Bilder spaeter, der
    F10-Versatz) schlaegt an."""
    path = os.path.join(out_dir(f), "preview_draft.mp4")
    rows, old = report(cfg, f, path)
    ok = all(r[2] for r in rows) and sum(r[2] for r in old) < len(old)
    print(f"{f['code']}: {'OK' if ok else 'FEHLER'}")
    return ok


# ---------------------------------------------------------------- Bogen und Songschnitt

SHEET_BEATS = (4.1, 5.1, 6.1, 7.1, 7.9, 8.1, 9.0, 10.0, 11.05, 11.6)   # Beats ab Taktstrich 1 (11 = Stopp)


def sheet(variants, path):
    """Standbilder je Variante auf den Beats (Zeilen = Varianten), beschriftet."""
    tw, th = 216, 384
    cols = max(len(SHEET_BEATS) + (2 if f["stop"] == "hit" else 0) for _, f in variants)
    img = Image.new("RGB", (90 + cols * tw, len(variants) * (th + 18) + 18), (18, 18, 18))
    dr = ImageDraw.Draw(img)
    for r, (cfg, f) in enumerate(variants):
        beats = list(SHEET_BEATS) + ([12.1, 14.0] if f["stop"] == "hit" else [])
        ns = [min(frame_at(f, b), n_end(f) - 1) for b in beats]
        got = dict(frames(cfg, f, sorted(set(ns))))
        y = 18 + r * (th + 18)
        dr.text((6, y + th // 2), f["code"], fill=(255, 220, 0))
        for j, (b, n) in enumerate(zip(beats, ns)):
            img.paste(Image.fromarray(got[n]).resize((tw, th), Image.BOX), (90 + j * tw, y))
            if r == 0 or f["stop"] == "hit":
                dr.text((90 + j * tw + 4, y - 14), f"Beat {b:g} = {n / FPS:.2f} s", fill=(220, 220, 220))
    img.save(path)
    return path


def song(f):
    """Songschnitt wie M4a (resolve/schnitt/songcut/songcut.py, dieselbe Naht), Quelle aber bis cut.length_s, dann
    fade_ms Ausblende ans Ende (kein Knacken auf der B-Eins). → f["song"]."""
    root = main_root()
    cut = f["cut"]
    tool = os.path.join(root, "kickoff_loop/resolve/schnitt/songcut/songcut.py")
    code = os.path.splitext(os.path.basename(f["song"]))[0]
    with tempfile.TemporaryDirectory() as tmp:
        toml = os.path.join(tmp, "cut.toml")
        open(toml, "w").write(
            f'source = "ref/audio/igors_theme.mp3"\ngrid = "{f["grid"].split("kickoff_loop/", 1)[1]}"\n'
            f'out_dir = "{tmp}"\nstart_song_s = {f["song_start_s"]}\nlength_s = {cut["length_s"]}\nxfade_ms = 8\n'
            f'snap_ms = 40\nfine_ms = 30\nvideo_s = {f["end_s"]}\n[cut.{code}]\nnote = "F11g2"\n'
            f'at_s = {cut["at_s"]}\nbars = {cut["bars"]}\n')
        subprocess.run(["uv", "run", "-q", tool, toml], check=True)
        d = cut["fade_ms"] / 1000
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(tmp, f"{code}.wav"), "-t", str(f["end_s"]),
                        "-af", f"afade=t=out:st={f['end_s'] - d}:d={d}", "-c:a", "pcm_s24le", f["song"]], check=True)
    print(f["song"])


def main():
    cmd, paths = sys.argv[1], sys.argv[2:]
    if cmd == "song":
        f = {**tomllib.load(open(SHARED, "rb"))["f11"], **tomllib.load(open(paths[0], "rb"))["f11"]}
        f["song"] = os.path.join(main_root(), f["song"])
        song(f)
        return
    variants = [load(p) for p in paths] if cmd != "still" else []
    if cmd == "video":
        for cfg, f in variants:
            print(video(cfg, f))
    elif cmd == "sheet":
        print(sheet(variants, os.path.join(os.path.dirname(SHARED), "F11_sheet.png")))
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
