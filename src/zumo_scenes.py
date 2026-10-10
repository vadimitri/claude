#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "scikit-image"]
# ///
"""Zumo-Szenen, Maskottchen, Emoji: kleine 8-Bit-Loops fuer die drei Maker-Night-Challenges, gebaut aus den Zumo-Sprites.

Alle Werte stehen kommentiert in zumo_sprites/scenes.toml, die Sprites kommen aus src/zumo_sprites.py (Z4/Z7).
Handbuch (Entscheidungen, Stand): zumo_sprites/CLAUDE.md.

  uv run src/zumo_scenes.py sheet     Kontaktbogen: je Szene 4 Keyframes, Maskottchen, Emoji -> previz/scenes/sheet.png
  uv run src/zumo_scenes.py scenes    spumo, spormula, capture -> previz/scenes/<name>/ (GIF transparent + auf Grund,
                                      MP4 1080x1080 + 1080x1920, ProRes 4444 mit Alpha in Palette value)
  uv run src/zumo_scenes.py mascot    T-Shirt -> previz/mascot/ (SVG + PNG 300 dpi, Vollton + Siebdruck 1c)
  uv run src/zumo_scenes.py emoji     Slack 128 px GIF + Telegram 512 px PNG -> previz/emoji/
  uv run src/zumo_scenes.py test      Selbsttest an den fertigen Dateien (Loop, Palette, ganze Pixel, Groesse, SVG)
  uv run src/zumo_scenes.py all       scenes + mascot + emoji + sheet + test

Echte Pixel-Art wie die Sumo-Demo v3 (Vadim 7.10. zur ersten Demo: "zu High Fidelity", "zu fake"): jede Szene ist eine
reine Funktion Tick -> Index-Bild im Wertraum (0 frei, 1..6 = Stufe 0..5, ab 10 LED-Akzente, ab 20 Teamfarben). Alles
wechselt nur auf 12-fps-Ticks, Positionen in ganzen Pixeln, Keys linear, Funken und Sterne sind Stempel; Farbe kommt erst
beim Schreiben ueber die Palette. Loops sind nahtlos, weil der Zustand nach dem letzten Tick wieder der erste ist (nicht
weil modulo gerechnet wird): der Selbsttest rechnet Tick `ticks` weiter und vergleicht mit Tick 0.
"""
import hashlib
import math
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")   # ein Pool-Prozess pro Kern (wie zumo_sprites.py)
os.environ.setdefault("OMP_NUM_THREADS", "1")
import re
import subprocess
import sys
import time
import tomllib
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw

import zumo_sprites as Z
import zumo_sprites_demo as D                      # Ring, Ellipse, paste, linear, stepped aus der abgenommenen Demo

CONFIG = os.path.join(Z.PROJECT, "scenes.toml")
PREVIZ = os.path.join(Z.PROJECT, "previz")
SCENES = ("spumo", "spormula", "capture")
TEAM0 = 20                  # Index der Teamfarben: TEAM0 + 2 * Team = Land, + 1 = Spur (hinter den LED-Akzenten ab 10)
VIEWS = ("top", "tq", "side", "front")
SERIAL_MAX = 24             # bis hierhin ohne Pool: ein Sprite ~0.15 s, ein Pool-Prozess kostet ~1 s Start (numpy, scipy)


def rnd(v):
    """Auf ganze Pixel, halbe immer aufwaerts (round() rundet 2.5 auf 2: ungleiche Treppen)."""
    return int(math.floor(v + 0.5))


# ---------------------------------------------------------------- Konfiguration

def load(path=CONFIG):
    """scenes.toml lesen und pruefen; sagt in Klartext, was falsch ist, bevor gerechnet wird."""
    with open(path, "rb") as f:
        sc = tomllib.load(f)
    o = sc["output"]
    assert o["video_fps"] % o["tick_fps"] == 0, "[output]: video_fps muss ein Vielfaches von tick_fps sein (Tick = n Frames)"
    cfg = Z.load()
    for p in [o["palette"], o["alpha_palette"], *o["extra_gif_palettes"], *sc["mascot"]["palettes"],
              *sc["emoji"]["palettes"], *sc["sheet"]["palettes"]]:
        try:
            Z.palette(cfg, p)
        except (KeyError, IndexError):
            raise AssertionError(f"Palette {p!r} gibt es weder in [palettes] der zumo_sprites.toml noch als P-Code")
    for tm in sc["teams"]:
        for part in ("land", "trail"):
            assert 0 <= tm[part]["step"] <= 5, f"[[teams]] {tm['name']}.{part}.step: Stufe 0..5"
    stamps = sc["stamps"]
    for name, frames in stamps.items():
        for fr in frames:
            assert len({len(r) for r in fr}) == 1, f"[stamps].{name}: Zeilen ungleich lang"
            bad = set("".join(fr)) - set("012345#." + Z.ACCENTS)
            assert not bad, f"[stamps].{name}: unbekannte Zeichen {bad} (0..5, #, ., {Z.ACCENTS})"
    for name in SCENES:
        d = sc[name]
        vc = Z.load(variant=d["variant"])
        n = vc["anims"]["drive"]["frames"]
        assert d["ticks"] % n == 0, f"[{name}].ticks {d['ticks']}: Vielfaches der {n} Sprite-Frames, sonst springt der Loop"
        W, H = d["size_px"]
        assert o["tall_px"][0] == W and o["tall_px"][1] >= H, f"[output].tall_px: gleiche Breite wie [{name}], hoeher"
        for k in ("keys_a", "keys_b", "fall_b", "anims_a", "anims_b", "show_b", "overtaker_keys"):
            if k in d:
                ts = [e[0] for e in d[k]]
                assert ts == sorted(ts) and ts[0] == 0, f"[{name}].{k}: Ticks aufsteigend, erster Key bei 0"
        for k in ("anims_a", "anims_b"):
            for _, a in d.get(k, []):
                assert a in vc["anims"], f"[{name}].{k}: Animation {a!r} fehlt in zumo_sprites.toml [anims]"
    assert sc["spormula"]["overtaker_anim"] in Z.load()["anims"], "[spormula].overtaker_anim unbekannt"
    for b in sc["spormula"]["burst"]:
        assert b[0] in stamps and len(b) == 5, "[spormula].burst: [Stempel aus [stamps], x, y, dx, dy]"
    for x, a in sc["spormula"]["pack"]:
        assert a in Z.load()["anims"], f"[spormula].pack: Animation {a!r} unbekannt"
    c = sc["capture"]
    assert sum(leg[-1] for leg in c["legs"]) == c["ticks"], \
        f"[capture].legs dauern {sum(leg[-1] for leg in c['legs'])} Ticks, ticks = {c['ticks']}"
    for leg in c["legs"]:
        assert leg[0] in ("drive", "turn", "win"), f"[capture].legs: {leg[0]!r} (drive, turn, win)"
    assert c["legs"][c["follow_leg"]][0] == "drive", "[capture].follow_leg: muss ein drive-Abschnitt sein"
    shift = sum(leg[1] for leg in c["legs"] if leg[0] == "drive")
    assert shift % c["grid_px"] == 0, f"[capture].grid_px {c['grid_px']} teilt die Schleifenbreite {shift} nicht"
    assert sum(leg[2] for leg in c["legs"] if leg[0] == "drive") == 0, "[capture].legs: Schleife endet nicht auf der Startzeile"
    assert 0 <= c["team"] < len(sc["teams"]), "[capture].team: Index in [[teams]]"
    for it_name, it in sc["emoji"]["items"].items():
        vc = Z.load(variant=sc["emoji"]["variant"])
        assert it["view"] in vc["views"] and it["anim"] in vc["anims"], f"[emoji.items.{it_name}]: view/anim unbekannt"
        n = vc["anims"][it["anim"]]["frames"]
        assert it["frames"] % n == 0, f"[emoji.items.{it_name}].frames: Vielfaches von {n}, sonst springt der Loop"
        assert 0 <= it["still"] < it["frames"], f"[emoji.items.{it_name}].still: Frame 0..frames-1"
        for p in it.get("particles", []):
            assert p[0] in stamps, f"[emoji.items.{it_name}].particles: Stempel {p[0]!r} fehlt in [stamps]"
    m = sc["mascot"]
    assert m["view"] in VIEWS and m["anim"] in Z.load()["anims"], "[mascot]: view/anim unbekannt"
    for s in m["stamps"]:
        assert s[0] in stamps, f"[mascot].stamps: {s[0]!r} fehlt in [stamps]"
    return sc


# ---------------------------------------------------------------- Sprites (gesammelt, parallel, auf Platte gecacht)

def _render(key):
    variant, view, d, anim, frame = key
    return key, Z.sprite(Z.load(variant=variant), view, d, anim, frame)


class Sprites:
    """Sprite nach (Variante, Ansicht, Richtung, Animation, Frame). Szenen laufen zweimal: erst sammelt `dry` die
    gebrauchten Schluessel (Platzhalter in Leinwandgroesse), `fill` rechnet die fehlenden im Pool, dann das echte Bild.
    Cache auf Platte nach Inhalt (Hash aus zumo_sprites.toml + zumo_sprites.py): aendert sich der Sprite, rechnet er neu."""

    def __init__(self):
        h = hashlib.sha1()
        for p in (Z.CONFIG, Z.__file__):
            with open(p, "rb") as f:
                h.update(f.read())
        self.path = os.path.join(PREVIZ, "scenes", "_cache", f"sprites_{h.hexdigest()[:12]}.npz")
        self.have, self.want, self.cfgs, self.dry = {}, set(), {}, False
        if os.path.exists(self.path):
            with np.load(self.path) as f:
                for k in f.files:
                    v, view, d, a, fr = k.split("|")
                    self.have[(v, view, float(d), a, int(fr))] = f[k]

    def cfg(self, variant):
        if variant not in self.cfgs:
            self.cfgs[variant] = Z.load(variant=variant)
        return self.cfgs[variant]

    def pivot(self, variant, view):
        c = self.cfg(variant)
        return Z.view_canvas(c, c["views"][view]["pitch_deg"])[2]

    def __call__(self, variant, view, d, anim, frame):
        c = self.cfg(variant)
        key = (variant, view, float(d) % 360, anim, frame % c["anims"][anim]["frames"])   # Frame n = Frame 0 (Loop)
        if key in self.have:
            return self.have[key]
        if self.dry:
            self.want.add(key)
            W, H, _ = Z.view_canvas(c, c["views"][view]["pitch_deg"])
            return np.zeros((H, W), np.uint8)
        self.have[key] = _render(key)[1]
        return self.have[key]

    def fill(self):
        todo = sorted(self.want - set(self.have))
        self.want.clear()
        if not todo:
            return
        t0 = time.time()
        if len(todo) < SERIAL_MAX:
            self.have.update(map(_render, todo))
        else:
            with Pool(min(os.cpu_count(), len(todo) // SERIAL_MAX * 4)) as pool:
                self.have.update(pool.map(_render, todo, chunksize=4))
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        np.savez_compressed(self.path, **{"|".join(map(str, k)): v for k, v in self.have.items()})
        print(f"{len(todo)} Sprites gerechnet ({time.time() - t0:.1f} s), Cache {os.path.basename(self.path)}")

    def run(self, fn):
        """fn() zweimal: sammeln, rechnen, Ergebnis."""
        self.dry = True
        fn()
        self.dry = False
        self.fill()
        return fn()


# ---------------------------------------------------------------- Bausteine

def iso(keys, t):
    """[x, y] zum Tick t aus [[tick, x, y], ...], linear. Auf 2:1-Diagonalen in ganzen Iso-Schritten (2 px x, 1 px y),
    sonst gerundet: getrennt gerundet springt die Treppe um 1 px aus der Diagonale."""
    for k0, k1 in zip(keys, keys[1:]):
        if k0[0] <= t <= k1[0]:
            f = (t - k0[0]) / max(k1[0] - k0[0], 1)
            (x0, y0), (x1, y1) = k0[1:], k1[1:]
            dx, dy = x1 - x0, y1 - y0
            if dy and abs(dx) == 2 * abs(dy):
                n = rnd(abs(dy) * f)
                return [x0 + 2 * n * (1 if dx > 0 else -1), y0 + n * (1 if dy > 0 else -1)]
            return [rnd(x0 + dx * f), rnd(y0 + dy * f)]
    return list(keys[-1][1:])


def lin(keys, t):
    """Einzelwert zum Tick t aus [[tick, wert], ...], linear, ganze Pixel."""
    return iso([[k, v, 0] for k, v in keys], t)[0]


def code(ch):
    """Stempelzeichen -> Index: '0'..'5' Stufe, '#' Stufe 5, Buchstabe LED-Akzent, '.' frei (0 = nichts setzen)."""
    if ch == ".":
        return 0
    if ch == "#":
        return 6
    if ch.isdigit():
        return 1 + int(ch)
    return Z.ACCENT0 + Z.ACCENTS.index(ch)


def stamp(idx, rows, x, y):
    """Stempel mittig auf (x, y), pixelgenau; '.' laesst den Grund stehen."""
    a = np.array([[code(c) for c in r] for r in rows], np.uint8)
    h, w = a.shape
    ys, xs = np.nonzero(a)
    ty, tx = ys + y - h // 2, xs + x - w // 2
    ok = (ty >= 0) & (ty < idx.shape[0]) & (tx >= 0) & (tx < idx.shape[1])
    idx[ty[ok], tx[ok]] = a[ys[ok], xs[ok]]


def ring4(mask):
    """1-px-Ring um eine Maske (4er-Nachbarschaft, wie die Sprite-Kontur)."""
    p = np.pad(mask, 1)
    near = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return near & ~mask


def scene_lut(sc, cfg, pal):
    """Palette als RGBA-Tabelle ueber alle Indizes: Stufen, LED-Akzente, Teamfarben (eigene Farbe der Palette oder Stufe)."""
    hx = lambda c: tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    steps, acc = Z.palette(cfg, pal)
    L = np.zeros((256, 4), np.uint8)
    for i, c in enumerate(steps):
        L[1 + i] = (*c, 255)
    for i, c in enumerate(acc):
        L[Z.ACCENT0 + i] = (*c, 255)
    for i, tm in enumerate(sc["teams"]):
        for j, part in enumerate(("land", "trail")):
            p = tm[part]
            L[TEAM0 + 2 * i + j] = (*(hx(p[pal]) if pal in p else steps[p["step"]]), 255)
    return L


# ---------------------------------------------------------------- Szene: Spumo (Iso)

def spumo(sc, sp, t):
    """Sumo im Dohyo, Choreografie der Demo v3 plus Reset: B verpufft und faellt am Start vom Himmel, A setzt zurueck."""
    d = sc["spumo"]
    v = d["variant"]
    S = sc["stamps"]
    W, H = d["size_px"]
    cx, cy = d["ring_center_px"]
    base = D.ring(d)
    k = t % sp.cfg(v)["anims"]["drive"]["frames"]
    pivot = sp.pivot(v, "tq")
    jit = (1 if t % 2 else -1) if d["jitter"][0] <= t < d["jitter"][1] else 0
    (ax, ay), (bx, by) = iso(d["keys_a"], t), iso(d["keys_b"], t)
    ax, bx = ax + jit, bx + jit
    fall = lin(d["fall_b"], t)
    bots = [(ay, ax, ay, 0, sp(v, "tq", d["dir_a"], D.stepped(d["anims_a"], t), k))]
    if D.stepped(d["show_b"], t):
        bots.append((by, bx, by, fall, sp(v, "tq", d["dir_b"], D.stepped(d["anims_b"], t), k)))
    idx = base.copy()
    for _, x, y, f, _ in bots:
        if D.on_ring(d, x, y) and f <= 0:                          # Schatten auf dem Ring, auch unter dem fallenden B
            idx[D.ellipse(W, H, cx + x, cy + y, *d["shadow_px"]) & (base == 1 + d["ring_values"][0])] = 1
    for _, x, y, f, s in sorted(bots, key=lambda b: b[0]):         # weiter hinten zuerst (Boden-y, nicht Fallhoehe)
        D.paste(idx, s, cx + x, cy + y + f, pivot)
    t_imp = d["impact_tick"]
    spark = sp.cfg(v)["demo"]["spark"]
    if t_imp <= t < t_imp + len(spark):
        stamp(idx, spark[t - t_imp], cx + (ax + bx) // 2, cy + (ay + by) // 2 + d["spark_y_px"])
    st = d["stars"]
    if st["from"] <= t < st["to"]:                                 # KO-Sterne kreisen ueber B
        for j in range(st["n"]):
            a = 2 * math.pi * (t / st["period"] + j / st["n"])
            stamp(idx, S["star"][0], cx + bx + rnd(st["rx_px"] * math.cos(a)),
                  cy + by + fall + st["y_px"] + rnd(st["ry_px"] * math.sin(a)))
    p = d["poof"]
    if p["tick"] <= t < p["tick"] + len(S["poof"]):
        stamp(idx, S["poof"][t - p["tick"]], cx + bx, cy + by + fall + p["y_px"])
    du = d["dust"]
    if du["tick"] <= t < du["tick"] + len(S["dust"]):
        for sgn in (-1, 1):
            stamp(idx, S["dust"][t - du["tick"]], cx + bx + sgn * du["dx_px"], cy + by + du["y_px"])
    if t_imp <= t < t_imp + len(d["shake_px"]):
        dx, dy = d["shake_px"][t - t_imp]
        idx = np.roll(idx, (dy, dx), (0, 1))
    return idx


def spumo_gates(sc, sp):
    """Kontakt am Boden (Abstand der Drehpunkte = Schildspitze + halbe Breite, wie Demo v3)."""
    d = sc["spumo"]
    cfg = sp.cfg(d["variant"])
    V = Z.get_mesh(cfg)[0] - Z.PIVOT
    reach = (V[:, 0].max() + np.abs(V[:, 2]).max()) / cfg["render"]["mm_per_px"]
    t = d["impact_tick"]
    (ax, ay), (bx, by) = iso(d["keys_a"], t), iso(d["keys_b"], t)
    dist = math.hypot(bx - ax, (by - ay) / d["ring_ry_frac"])
    line = f"spumo: Kontakt Tick {t}: Abstand {dist:.1f} px, Schild + halbe Breite {reach:.1f} px (Gate +-1.5)"
    return line, abs(dist - reach) <= 1.5


# ---------------------------------------------------------------- Szene: Spormula E (Draufsicht, Kamera faehrt mit)

def spormula_world(d, t):
    """Bild-x aller Ziellinien und Codes zum Tick t (Welt wiederholt sich alle ticks * scroll_px)."""
    P = d["scroll_px"] * d["ticks"]
    cam = d["scroll_px"] * t
    W = d["size_px"][0]

    def xs(X, w):
        s = (X - cam) % P
        return [s + n * P for n in (-1, 0, 1) if -w <= s + n * P < W + w]
    return xs


def spormula_crossings(d):
    """Ticks, in denen der Ueberholer (Spur A) als Erster eine Ziellinie kreuzt (davor ist es nur eine Runde), und wann
    der Fuehrende auf Spur B sie kreuzt."""
    T = d["ticks"]
    fin = lambda t: spormula_world(d, t)(d["finish_x_px"], 400)
    out, lead = [], []
    lead_x = max(x for x, _ in d["pack"])
    for t in range(1, T + 1):
        ox0, ox1 = lin(d["overtaker_keys"], t - 1), lin(d["overtaker_keys"], t)
        for f0 in fin(t - 1):
            f1 = f0 - d["scroll_px"]
            if ox0 < f0 and ox1 >= f1 and ox1 > lead_x:
                out.append((t, f1))
            if lead_x < f0 and lead_x >= f1:
                lead.append(t)
    return out, lead


def spormula(sc, sp, t):
    """Linienrennen: zwei Zumos auf Spur B (Kamera faehrt mit), der dritte ueberholt auf Spur A, Ziel mit Flagge."""
    d = sc["spormula"]
    v = d["variant"]
    S = sc["stamps"]
    W, H = d["size_px"]
    idx = np.zeros((H, W), np.uint8)
    b0, b1 = d["board_y_px"]
    idx[b0 - 1] = idx[b1 + 1] = 1 + d["outline_value"]
    idx[b0:b1 + 1] = 1 + d["board_value"]
    idx[b0:b0 + 2] = idx[b1 - 1:b1 + 1] = 1 + d["edge_value"]       # Kante oben und unten
    lw = d["line_px"]
    for ly in d["lanes_y_px"]:
        idx[ly - lw // 2:ly - lw // 2 + lw] = 1 + d["line_value"]
    xs = spormula_world(d, t)
    bw, bl = d["bar_px"]
    for X, n in d["codes"]:                                        # Querbalken quer ueber jede Spur
        for sx in xs(X, n * (bw + d["bar_gap_px"])):
            for i in range(n):
                x0 = sx + i * (bw + d["bar_gap_px"])
                for ly in d["lanes_y_px"]:
                    idx[ly - bl // 2:ly - bl // 2 + bl, max(x0, 0):max(x0 + bw, 0)] = 1 + d["line_value"]
    c, nc = d["checker_px"], d["checker_cols"]
    yy, xx = np.mgrid[b0 + 2:b1 - 1, 0:W]
    for sx in xs(d["finish_x_px"], c * nc + 20):                   # Ziellinie: Schachbrett ueber die ganze Flaeche
        sel = (xx >= sx) & (xx < sx + c * nc)
        chk = (((xx - sx) // c + (yy - b0 - 2) // c) % 2 == 0)
        idx[b0 + 2:b1 - 1][sel & chk] = 1 + d["line_value"]
        idx[b0 + 2:b1 - 1][sel & ~chk] = 1 + d["board_value"]
        fl = d["flag"]
        stamp(idx, S["flag"][(t // fl["ticks"]) % len(S["flag"])], sx + fl["dx_px"], b0 + fl["dy_px"])
    pivot = sp.pivot(v, "top")
    k = t % sp.cfg(v)["anims"]["drive"]["frames"]
    D.paste(idx, sp(v, "top", 0, d["overtaker_anim"], k), lin(d["overtaker_keys"], t), d["lanes_y_px"][0], pivot)
    for x, a in d["pack"]:
        D.paste(idx, sp(v, "top", 0, a, k), x, d["lanes_y_px"][1], pivot)
    for tc, _ in spormula_crossings(d)[0]:                         # Sterne aus der Flagge, fahren mit der Ziellinie
        if tc <= t < tc + d["burst_ticks"]:
            age = t - tc
            for sx in xs(d["finish_x_px"], 60):
                for name, x, y, dx, dy in d["burst"]:
                    stamp(idx, S[name][0], sx + x + dx * age, b0 + y + dy * age)
    return idx


def spormula_gates(sc):
    d = sc["spormula"]
    out, lead = spormula_crossings(d)
    W = d["size_px"][0]
    ok = bool(out) and bool(lead) and out[0][0] < min(lead)
    lines = [f"spormula: Ueberholer kreuzt die Ziellinie bei Tick {[t for t, _ in out]}, Fuehrender bei {lead} "
             f"(Gate: Ueberholer zuerst)"]
    edge = [lin(d["overtaker_keys"], t) for t in (0, d["ticks"])]
    off = all(x + 20 < 0 or x - 20 >= W for x in edge)               # Zumo von oben ~40 px breit
    lines.append(f"spormula: Ueberholer bei Tick 0 / {d['ticks']} auf x {edge} (Gate: ausserhalb des Bildes)")
    return lines, ok and off


# ---------------------------------------------------------------- Szene: Area Capture (Draufsicht)

def capture_path(d):
    """Zustand des Zumo zu Beginn jedes Ticks (Welt): x, y, Richtung, Animation, Kamera-x. Plus Endzustand."""
    x, y = d["start_px"]
    dr, cam, states = 0.0, 0, []
    for li, leg in enumerate(d["legs"]):
        if leg[0] == "drive":
            _, dx, dy, n = leg
            dr = math.degrees(math.atan2(-dy, dx)) % 360
            for i in range(n):
                f = i / n
                states.append((x + rnd(dx * f), y + rnd(dy * f), dr, "drive",
                               cam + (rnd(dx * f) if li == d["follow_leg"] else 0)))
            x, y = x + dx, y + dy
            cam += dx if li == d["follow_leg"] else 0
        elif leg[0] == "turn":
            _, deg, n = leg
            for i in range(n):
                states.append((x, y, (dr + deg * i / n) % 360, "turn_left" if deg > 0 else "turn_right", cam))
            dr = (dr + deg) % 360
        else:
            for i in range(leg[1]):
                states.append((x, y, dr, "win", cam))
    return states, (x, y, dr, "drive", cam)


def capture(sc, sp, t):
    """Schleife aus dem Land, Spur in Teamfarbe, zurueck im Land fuellt sich die Flaeche, dann an die neue Kante."""
    d = sc["capture"]
    v = d["variant"]
    W, H = d["size_px"]
    states, end = capture_path(d)
    x, y, dr, anim, cam = states[t] if t < len(states) else end
    E, y1 = d["start_px"]
    hw = d["trail_px"] // 2
    shift = sum(leg[1] for leg in d["legs"] if leg[0] == "drive")
    top, bot = y1 - hw, y1 + d["band_h_px"] + hw                  # Land-Streifen (Zeilen, inklusive)
    # Rueckkehr ins Land: erster Tick nach dem Verlassen mit Drehpunkt wieder auf/hinter der Kante
    out = [i for i, s in enumerate(states) if s[0] > E + hw]
    t_in = next(i for i in range(out[0], len(states)) if states[i][0] <= E + hw)
    idx = np.zeros((H, W), np.uint8)
    f0, f1 = d["field_y_px"]
    idx[f0 - 1] = idx[f1 + 1] = 1 + d["outline_value"]
    idx[f0:f1 + 1] = 1 + d["field_value"]
    idx[f0:f0 + 2] = idx[f1 - 1:f1 + 1] = 1 + d["edge_value"]
    g = d["grid_px"]
    gx = np.arange((cam // g) * g, cam + W + g, g) - cam           # Punktraster faehrt mit der Welt
    for gy in range(f0 + g // 2, f1 - 1, g):
        for sx in gx[(gx >= 0) & (gx < W)]:
            idx[gy, sx] = 1 + d["grid_value"]
    land, trail = TEAM0 + 2 * d["team"], TEAM0 + 2 * d["team"] + 1
    idx[top:bot + 1, :max(0, min(W, E + hw + 1 - cam))] = land
    pts = [(s[0], s[1]) for s in states[:min(t, t_in) + 1]]        # Spur bis zum aktuellen Drehpunkt
    if t < len(states):
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            xa, xb, ya, yb = min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)
            ys, ye = max(ya - hw, 0), min(yb + hw + 1, H)
            xs_, xe = max(xa - hw - cam, 0), min(xb + hw + 1 - cam, W)
            if xs_ < xe and ys < ye:
                idx[ys:ye, xs_:xe] = trail
    if t >= t_in:                                                  # Flaeche fuellt sich in Zeilenbaendern von oben
        j = t - t_in
        rows = bot + 1 - top if j >= d["fill_ticks"] else rnd((bot + 1 - top) * (j + 1) / d["fill_ticks"])
        idx[top:top + rows, max(0, E + hw + 1 - cam):max(0, min(W, E + shift + hw + 1 - cam))] = land
    k = t % sp.cfg(v)["anims"]["drive"]["frames"]
    D.paste(idx, sp(v, "top", dr, anim, k), x - cam, y, sp.pivot(v, "top"))
    spark = sp.cfg(v)["demo"]["spark"]
    if t_in <= t < t_in + len(spark):
        stamp(idx, spark[t - t_in], E + shift // 2 - cam, (top + bot) // 2)
    return idx


def capture_gates(sc):
    d = sc["capture"]
    states, end = capture_path(d)
    shift = sum(leg[1] for leg in d["legs"] if leg[0] == "drive")
    x0, y0 = d["start_px"]
    ok = (end[0] - end[4], end[1], end[2]) == (x0, y0, 0.0) and end[4] == shift
    return [f"capture: Ende x {end[0]} (Kamera {end[4]}), y {end[1]}, Richtung {end[2]:g}; Start x {x0}, y {y0} "
            f"(Gate: Bild nach dem letzten Tick = Start)"], ok


SCENE_FN = {"spumo": spumo, "spormula": spormula, "capture": capture}


def scene_frames(sc, sp, name, ticks=None):
    d = sc[name]
    ticks = range(d["ticks"]) if ticks is None else ticks
    return sp.run(lambda: [SCENE_FN[name](sc, sp, t) for t in ticks])


# ---------------------------------------------------------------- Schreiben (GIF, MP4, ProRes, PNG, SVG)

def big(a, k):
    return a.repeat(k, 0).repeat(k, 1) if k > 1 else a


def gif_durations(n, fps):
    """GIF zaehlt in 1/100 s: 1000/12 ms gibt es nicht. 8, 9, 8 ... Hundertstel ergeben genau 12 fps im Mittel."""
    cs = [rnd(i * 100 / fps) for i in range(n + 1)]
    return [10 * (b - a) for a, b in zip(cs, cs[1:])]


def save_gif(path, frames, L, k, fps, ground=None):
    """P-Mode-GIF, Index = Palette (wie im Sprite). ground=None: Index 0 transparent (1 Bit), sonst Grund-Index."""
    pal = L[:, :3].reshape(-1).tolist()
    ims = []
    for fr in frames:
        a = fr if ground is None else np.where(fr == 0, ground, fr).astype(np.uint8)
        im = Image.fromarray(big(a, k), "P")
        im.putpalette(pal)
        ims.append(im)
    kw = dict(transparency=0, disposal=2) if ground is None else {}
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=gif_durations(len(frames), fps), loop=0,
                optimize=False, **kw)


def save_video(path, frames, L, k, o, size, alpha=False, loops=1):
    """MP4 (Grund) oder ProRes 4444 mit Alpha. size = logische Leinwand (W, H); die Szene sitzt mittig."""
    W, H = size
    h0, w0 = frames[0].shape
    oy, ox = (H - h0) // 2, (W - w0) // 2
    hold = o["video_fps"] // o["tick_fps"]
    if alpha:
        args = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0"]
    else:
        args = ["-vf", "scale=out_color_matrix=bt709:out_range=tv", "-colorspace", "bt709", "-color_primaries", "bt709",
                "-color_trc", "bt709", "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"]
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba" if alpha else "rgb24",
                          "-s", f"{W * k}x{H * k}", "-r", str(o["video_fps"]), "-i", "-", *args, path],
                         stdin=subprocess.PIPE)
    ground = 1 + o["ground_value"]
    for _ in range(loops):
        for fr in frames:
            cv = np.zeros((H, W), np.uint8) if alpha else np.full((H, W), ground, np.uint8)
            cv[oy:oy + h0, ox:ox + w0] = fr if alpha else np.where(fr == 0, ground, fr)
            img = big(L[cv] if alpha else L[cv][..., :3], k)
            for _ in range(hold):
                p.stdin.write(img.tobytes())
    p.stdin.close()
    assert p.wait() == 0, f"ffmpeg: {path}"


def save_png(path, idx, L, k, dpi=None):
    im = Image.fromarray(big(L[idx], k), "RGBA")
    if dpi:
        im.save(path, dpi=(dpi, dpi))
    else:
        im.save(path)


def runs(row):
    e = np.flatnonzero(np.diff(np.r_[0, row.astype(np.int8), 0]))
    return list(zip(e[::2], e[1::2]))


def rects(mask):
    """Maske -> Rechtecke: waagrechte Laeufe, gleiche Laeufe in Folgezeilen zu einem Rechteck zusammengefasst."""
    out, open_ = [], {}
    H = mask.shape[0]
    for y in range(H + 1):
        rr = set(runs(mask[y])) if y < H else set()
        for r in [r for r in open_ if r not in rr]:
            out.append((int(r[0]), open_[r], int(r[1] - r[0]), y - open_[r]))
            del open_[r]
        for r in rr:
            open_.setdefault(r, y)
    return out


def save_svg(path, layers, w, h, width_mm):
    """layers = [(Farbe #RRGGBB, Maske)]: je Farbe ein Pfad aus Pixel-Rechtecken, Ursprung oben links, 1 Einheit = 1 Pixel.
    Gleiche Farben werden vorher vereint (in P-Paletten leuchten LEDs in der hellsten Stufe: Index 6 und 10 = eine Farbe)."""
    merged = {}
    for col, m in layers:
        merged[col] = merged.get(col, False) | m
    paths = []
    for col, m in merged.items():
        d = "".join(f"M{x} {y}h{rw}v{rh}h-{rw}z" for x, y, rw, rh in rects(m))
        if d:
            paths.append(f'<path fill="{col}" d="{d}"/>')
    with open(path, "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:g}mm" height="{width_mm * h / w:.2f}mm" '
                f'viewBox="0 0 {w} {h}" shape-rendering="crispEdges">\n' + "\n".join(paths) + "\n</svg>\n")


def read_svg(path, w, h):
    """SVG zurueck in Masken je Farbe (fuer den Selbsttest: Flaeche = Pixel)."""
    txt = open(path).read()
    out = {}
    for col, d in re.findall(r'<path fill="(#[0-9A-Fa-f]{6})" d="([^"]*)"', txt):
        m = np.zeros((h, w), np.int32)
        for x, y, rw, rh, rw2 in re.findall(r"M(\d+) (\d+)h(\d+)v(\d+)h-(\d+)z", d):
            x, y, rw, rh = int(x), int(y), int(rw), int(rh)
            m[y:y + rh, x:x + rw] += 1
        out[col] = m
    return out


def hexrgb(c):
    return "#%02X%02X%02X" % tuple(int(v) for v in c[:3])


# ---------------------------------------------------------------- Befehle: Szenen

def scenes(sc, sp, names=SCENES):
    o = sc["output"]
    cfg = sp.cfg(sc[names[0]]["variant"])
    report = []
    for name in names:
        d = sc[name]
        frames = scene_frames(sc, sp, name)
        dst = os.path.join(PREVIZ, "scenes", name)
        os.makedirs(dst, exist_ok=True)
        for i, pal in enumerate([o["palette"], *o["extra_gif_palettes"]]):
            L = scene_lut(sc, cfg, pal)
            sfx = "" if i == 0 else f"_{pal}"
            save_gif(os.path.join(dst, f"{name}{sfx}.gif"), frames, L, o["gif_px"], o["tick_fps"])
            save_gif(os.path.join(dst, f"{name}{sfx}_ground.gif"), frames, L, o["gif_px"], o["tick_fps"],
                     ground=1 + o["ground_value"])
        L = scene_lut(sc, cfg, o["palette"])
        k = o["video_px"]
        W, H = d["size_px"]
        save_video(os.path.join(dst, f"{name}_{W * k}x{H * k}.mp4"), frames, L, k, o, (W, H), loops=o["mp4_loops"])
        tw, th = o["tall_px"]
        save_video(os.path.join(dst, f"{name}_{tw * k}x{th * k}.mp4"), frames, L, k, o, (tw, th), loops=o["mp4_loops"])
        save_video(os.path.join(dst, f"{name}_alpha_{o['alpha_palette']}.mov"), frames,
                   scene_lut(sc, cfg, o["alpha_palette"]), k, o, (W, H), alpha=True)
        report.append(f"{name}: {len(frames)} Ticks ({len(frames) / o['tick_fps']:g} s) -> {dst}")
        print(report[-1])
    return report


def gates(sc, sp):
    lines, ok = [], True
    line, g = spumo_gates(sc, sp)
    lines.append(line)
    ok &= g
    for ls, g in (spormula_gates(sc), capture_gates(sc)):
        lines += ls
        ok &= g
    return lines, ok


# ---------------------------------------------------------------- Befehle: Maskottchen

def mascot_index(sc, sp):
    """Maskottchen als Index-Bild, auf die Silhouette (plus Stempel) beschnitten."""
    m = sc["mascot"]
    v = m["variant"]
    C = 160
    px0, py0 = C // 2, C // 2 + 20
    idx = np.zeros((C, C), np.uint8)
    D.paste(idx, sp(v, m["view"], m["dir_deg"], m["anim"], m["frame"]), px0, py0, sp.pivot(v, m["view"]))
    for name, x, y in m["stamps"]:
        stamp(idx, sc["stamps"][name][0], px0 + x, py0 + y)
    ys, xs = np.nonzero(idx)
    return idx[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(ys) else idx   # leer nur im Sammellauf


def mascot_scale(sc, w):
    m = sc["mascot"]
    return max(1, rnd(m["width_cm"] / 2.54 * m["dpi"] / w))


def mascot_ink(sc, idx):
    """Siebdruck 1c: Farbe, wo die Stufe in ink_values liegt (Kontur, Innenlinien, OLED); Augen, LEDs, Flaechen = Shirt."""
    vals = [1 + v for v in sc["mascot"]["ink_values"]]
    return np.isin(idx, vals)


def mascot(sc, sp):
    m = sc["mascot"]
    idx = sp.run(lambda: mascot_index(sc, sp))
    h, w = idx.shape
    k = mascot_scale(sc, w)
    dst = os.path.join(PREVIZ, "mascot")
    os.makedirs(dst, exist_ok=True)
    cfg = sp.cfg(m["variant"])
    report = []
    for pal in m["palettes"]:
        L = scene_lut(sc, cfg, pal)
        cols = [c for c in np.unique(idx) if c]
        save_svg(os.path.join(dst, f"mascot_{pal}.svg"), [(hexrgb(L[c]), idx == c) for c in cols], w, h, m["width_cm"] * 10)
        save_png(os.path.join(dst, f"mascot_{pal}.png"), idx, L, k, m["dpi"])
        report.append(f"mascot {pal}: {len({hexrgb(L[c]) for c in cols})} Volltonfarben")
    ink = mascot_ink(sc, idx)
    save_svg(os.path.join(dst, "mascot_1c.svg"), [(m["ink_color"].upper(), ink)], w, h, m["width_cm"] * 10)
    L1 = np.zeros((256, 4), np.uint8)
    L1[1] = (*[int(m["ink_color"][i:i + 2], 16) for i in (1, 3, 5)], 255)
    save_png(os.path.join(dst, "mascot_1c.png"), ink.astype(np.uint8), L1, k, m["dpi"])
    report.append(f"mascot: {w} x {h} px, x{k} = {w * k} x {h * k} px = {w * k / m['dpi'] * 2.54:.1f} x "
                  f"{h * k / m['dpi'] * 2.54:.1f} cm bei {m['dpi']} dpi -> {dst}")
    print(*report, sep="\n")
    return report


# ---------------------------------------------------------------- Befehle: Emoji

def emoji_frames(sc, sp, it, only=None):
    """Ein Emoji als Liste von Index-Bildern (Arbeitsleinwand, Drehpunkt fest): Zumo, Sticker-Ring, Partikel.
    Frames 0..n (Frame n nur fuer den Loop-Test), oder nur die in `only`."""
    e = sc["emoji"]
    v = e["variant"]
    S = sc["stamps"]
    C = 128
    px0, py0 = C // 2, C // 2 + 16
    pivot = sp.pivot(v, it["view"])
    dirs = it["dir_deg"] if isinstance(it["dir_deg"], list) else [it["dir_deg"]]
    n = it["frames"]
    out = []
    for f in range(n + 1) if only is None else only:
        idx = np.zeros((C, C), np.uint8)
        D.paste(idx, sp(v, it["view"], dirs[f % len(dirs)], it["anim"], f), px0, py0, pivot)
        idx[ring4(idx > 0)] = 1 + e["sticker_value"]
        for name, x, y, dx, dy, start, life in it.get("particles", []):
            age = (f - start) % n
            if age < life:
                stamp(idx, S[name][0], px0 + x + dx * age, py0 + y + dy * age)
        ob = it.get("orbit")
        if ob:
            for j in range(ob["n"]):
                a = 2 * math.pi * (f / ob["period"] + j / ob["n"])
                stamp(idx, S[ob["stamp"]][0], px0 + rnd(ob["rx_px"] * math.cos(a)), py0 + ob["y_px"] + rnd(ob["ry_px"] * math.sin(a)))
        out.append(idx)
    return out


def emoji_set(sc, sp):
    """Alle Emoji, auf einen gemeinsamen Massstab gebracht: {name: (Frames inkl. Frame n, k_slack, k_telegram)}."""
    items = sc["emoji"]["items"]
    raw = sp.run(lambda: {name: emoji_frames(sc, sp, it) for name, it in items.items()})
    e = sc["emoji"]
    boxes = {}
    for name, frs in raw.items():
        m = np.any(np.stack(frs) > 0, 0)
        ys, xs = np.nonzero(m)
        boxes[name] = (ys.min(), ys.max() + 1, xs.min(), xs.max() + 1)
    big_side = max(max(b[1] - b[0], b[3] - b[2]) for b in boxes.values())
    ks = (e["size_px"] - 2 * e["pad_px"]) // big_side
    kt = (e["telegram_px"] - 2 * e["pad_px"]) // big_side
    out = {}
    for name, frs in raw.items():
        y0, y1, x0, x1 = boxes[name]
        out[name] = [f[y0:y1, x0:x1] for f in frs]
    return out, ks, kt


def place(a, k, size):
    """Ganzzahlig vergroessern und mittig auf eine quadratische Leinwand setzen (Index 0 = transparent)."""
    b = big(a, k)
    cv = np.zeros((size, size), np.uint8)
    oy, ox = (size - b.shape[0]) // 2, (size - b.shape[1]) // 2
    cv[oy:oy + b.shape[0], ox:ox + b.shape[1]] = b
    return cv


def emoji(sc, sp):
    e = sc["emoji"]
    o = sc["output"]
    sets, ks, kt = emoji_set(sc, sp)
    cfg = sp.cfg(e["variant"])
    report = [f"emoji: Massstab x{ks} (Slack {e['size_px']} px), x{kt} (Telegram {e['telegram_px']} px)"]
    for i, pal in enumerate(e["palettes"]):
        L = scene_lut(sc, cfg, pal)
        dst = os.path.join(PREVIZ, "emoji", *([] if i == 0 else [pal]))
        os.makedirs(os.path.join(dst, "telegram"), exist_ok=True)
        for name, frs in sets.items():
            it = e["items"][name]
            p = os.path.join(dst, f"zumo-{name}.gif")
            save_gif(p, [place(f, ks, e["size_px"]) for f in frs[:it["frames"]]], L, 1, o["tick_fps"])
            save_png(os.path.join(dst, "telegram", f"zumo-{name}.png"), place(frs[it["still"]], kt, e["telegram_px"]), L, 1)
            if i == 0:
                report.append(f"zumo-{name}.gif: {it['frames']} Frames, {os.path.getsize(p) / 1024:.1f} KB")
    print(*report, sep="\n")
    return report


# ---------------------------------------------------------------- Kontaktbogen

def label(img, text, xy, size=22, fill=(150, 145, 170)):
    ImageDraw.Draw(img).text(xy, text, fill=fill, font_size=size)


def sheet(sc, sp):
    """Kontaktbogen: je Szene 4 Keyframes (P1 + natural auf Grund), Maskottchen (Vollton, 1c), Emoji (Frame 0)."""
    o = sc["output"]
    sh = sc["sheet"]
    z = sh["zoom"]
    cfg = sp.cfg("Z4")

    def collect():
        frames = {n: [SCENE_FN[n](sc, sp, t) for t in sc[n]["sheet_ticks"]] for n in SCENES}
        return frames, mascot_index(sc, sp), {name: emoji_frames(sc, sp, it, [it["still"]])[0]
                                              for name, it in sc["emoji"]["items"].items()}
    frames, mi, em = sp.run(collect)
    bgc = (20, 18, 28)
    rows = []
    for n in SCENES:
        for pal in sh["palettes"]:
            L = scene_lut(sc, cfg, pal)
            g = 1 + o["ground_value"]
            tiles = [Image.fromarray(big(L[np.where(f == 0, g, f)], z), "RGBA") for f in frames[n]]
            row = Image.new("RGB", (260 + sum(t.width + 12 for t in tiles), tiles[0].height + 16), bgc)
            label(row, n, (14, 12), 34)
            label(row, pal, (14, 56))
            x = 260
            for t, tk in zip(tiles, sc[n]["sheet_ticks"]):
                row.paste(t, (x, 8))
                label(row, f"t {tk}", (x + 6, 12), 16, (120, 115, 140))
                x += t.width + 12
            rows.append(row)
    # Maskottchen: Vollton je Palette auf dunklem + hellem Shirt, 1c
    mk = 6
    tiles = []
    for pal in sc["mascot"]["palettes"]:
        L = scene_lut(sc, cfg, pal)
        for shirt in ((14, 12, 20), (236, 233, 242)):
            t = Image.new("RGB", (mi.shape[1] * mk + 40, mi.shape[0] * mk + 40), shirt)
            im = Image.fromarray(big(L[mi], mk), "RGBA")
            t.paste(im, (20, 20), im)
            tiles.append(t)
    ink = mascot_ink(sc, mi)
    for shirt, col in (((236, 233, 242), (0, 0, 0)), ((14, 12, 20), (240, 236, 250))):
        t = Image.new("RGB", (mi.shape[1] * mk + 40, mi.shape[0] * mk + 40), shirt)
        a = np.zeros((*mi.shape, 4), np.uint8)
        a[ink] = (*col, 255)
        im = Image.fromarray(big(a, mk), "RGBA")
        t.paste(im, (20, 20), im)
        tiles.append(t)
    row = Image.new("RGB", (260 + sum(t.width + 12 for t in tiles), max(t.height for t in tiles) + 16), bgc)
    label(row, "mascot", (14, 12), 34)
    label(row, " ".join(sc["mascot"]["palettes"]) + " 1c", (14, 56))
    x = 260
    for t in tiles:
        row.paste(t, (x, 8))
        x += t.width + 12
    rows.append(row)
    # Emoji: Frame `still`, x3, auf hell und dunkel
    L = scene_lut(sc, cfg, sc["emoji"]["palettes"][0])
    for bg in ((236, 233, 242), (26, 29, 33)):
        tiles = []
        for name, f in em.items():
            ys, xs = np.nonzero(f)
            f = f[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            t = Image.new("RGB", (190, 170), bg)
            im = Image.fromarray(big(L[f], 3), "RGBA")
            t.paste(im, ((190 - im.width) // 2, (150 - im.height) // 2), im)
            label(t, name, (6, 148), 15, (120, 115, 140))
            tiles.append(t)
        row = Image.new("RGB", (260 + sum(t.width + 8 for t in tiles), 186), bgc)
        label(row, "emoji", (14, 12), 34)
        x = 260
        for t in tiles:
            row.paste(t, (x, 8))
            x += t.width + 8
        rows.append(row)
    S = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows)), bgc)
    y = 0
    for r in rows:
        S.paste(r, (0, y))
        y += r.height
    dst = os.path.join(PREVIZ, "scenes")
    os.makedirs(dst, exist_ok=True)
    p = os.path.join(dst, "sheet.png")
    S.save(p)
    print(p)
    return p


# ---------------------------------------------------------------- Selbsttest

def gif_ticks(path, fps):
    """GIF -> Liste RGBA-Bilder, eines pro Tick (doppelte Frames fasst Pillow zusammen, die Dauer bleibt)."""
    im = Image.open(path)
    out = []
    cs = 0
    for i in range(im.n_frames):
        im.seek(i)
        fr = np.array(im.convert("RGBA"))
        cs += im.info["duration"] // 10
        while rnd(len(out) * 100 / fps) < cs:
            out.append(fr)
    return out


def blocks_ok(a, k):
    """Ganze Pixel: jedes k x k-Feld einfarbig (nearest, ganzzahlig, kein Subpixel)."""
    H, W = a.shape[:2]
    if k < 1 or H % k or W % k:
        return False
    b = a.reshape(H // k, k, W // k, k, -1)
    return bool((b == b[:, :1, :, :1]).all())


def even_steps(seq):
    """Lineare Bewegung: Schrittweite pro Tick schwankt hoechstens um 1 px (Rundung). Smoothstep beschleunigt/bremst."""
    d = np.abs(np.diff(np.asarray(seq), axis=0))
    return bool(len(d) < 2 or (d.max(0) - d.min(0)).max() <= 1)


def colors_ok(a, L):
    """Nur Farben der Palette (RGBA, Alpha 0 oder 255)."""
    allowed = {tuple(c) for c in L[1:] if c[3]} | {(0, 0, 0, 0)}
    px = a.reshape(-1, 4)
    px = np.where(px[:, 3:4] == 0, 0, px)                          # transparent = transparent, Farbe egal
    got = {tuple(c) for c in np.unique(px, axis=0)}
    return got <= allowed, got - allowed


def composite(fr, L, k, ground=None):
    a = fr if ground is None else np.where(fr == 0, ground, fr)
    return big(L[a], k)


def selftest(sc, sp):
    """Misst an den fertigen Dateien. Gegenproben (absichtlich kaputte Eingaben) muessen anschlagen, sonst ist der Test
    blind: Loop einen Tick zu kurz, weich statt nearest skaliert, ein SVG-Rechteck weniger."""
    o = sc["output"]
    fails, notes = [], []
    cfg = sp.cfg("Z4")
    lines, ok = gates(sc, sp)
    notes += lines
    if not ok:
        fails.append("Gate verletzt (siehe oben)")
    # 0 Keys linear (Vadim 7.10.: "zu fake"): in jedem Abschnitt pro Tick gleich weit, Rundung +-1. Gegenprobe Smoothstep.
    for n, key in (("spumo", "keys_a"), ("spumo", "keys_b"), ("spumo", "fall_b"), ("spormula", "overtaker_keys")):
        keys = sc[n][key]
        for k0, k1 in zip(keys, keys[1:]):
            seq = [iso(keys, t) if len(k0) == 3 else [lin(keys, t), 0] for t in range(k0[0], k1[0] + 1)]
            if len(k0) == 3 and k1[2] != k0[2] and abs(k1[1] - k0[1]) == 2 * abs(k1[2] - k0[2]):
                seq = [[p[1], 0] for p in seq]                      # Iso-Diagonale: in Schritten (1 px y) zaehlen
            if not even_steps(seq):
                fails.append(f"[{n}].{key} Tick {k0[0]}..{k1[0]}: ungleiche Schritte {np.diff(seq, axis=0).tolist()}")
    smooth = [[rnd(64 * (3 * f * f - 2 * f ** 3)), 0] for f in np.linspace(0, 1, 7)]
    if even_steps(smooth):
        fails.append("Gegenprobe linear: Smoothstep-Bewegung faellt nicht auf")
    # 1 Loops am Zustand: Tick `ticks` weitergerechnet = Tick 0. Gegenprobe: ein Loop, der einen Sprite-Zyklus (8 Ticks)
    #   zu frueh endet, laege mitten in der Bewegung und muss auffallen (Sprite-Frame gleich, nur der Zustand nicht).
    for n in SCENES:
        T = sc[n]["ticks"]
        cyc = sp.cfg(sc[n]["variant"])["anims"]["drive"]["frames"]
        f0, fT, fS = scene_frames(sc, sp, n, [0, T, T - cyc])
        diff = int((f0 != fT).sum())
        notes.append(f"Loop {n}: Tick {T} vs 0: {diff} px verschieden (Gegenprobe Tick {T - cyc}: {int((f0 != fS).sum())} px)")
        if diff:
            fails.append(f"Loop {n}: Bild nach dem letzten Tick weicht in {diff} px vom ersten ab")
        if (f0 == fS).all():
            fails.append(f"Gegenprobe Loop {n}: Tick {T - cyc} = Tick 0, ein zu kurzer Loop fiele nicht auf")
    # 2 Szenen-Dateien
    for n in SCENES:
        d = sc[n]
        dst = os.path.join(PREVIZ, "scenes", n)
        frames = None
        for i, pal in enumerate([o["palette"], *o["extra_gif_palettes"]]):
            L = scene_lut(sc, cfg, pal)
            for gr in (None, 1 + o["ground_value"]):
                p = os.path.join(dst, f"{n}{'' if i == 0 else '_' + pal}{'' if gr is None else '_ground'}.gif")
                if not os.path.exists(p):
                    fails.append(f"fehlt: {p} (erst `scenes`)")
                    continue
                tk = gif_ticks(p, o["tick_fps"])
                if len(tk) != d["ticks"]:
                    fails.append(f"{os.path.basename(p)}: {len(tk)} Ticks statt {d['ticks']}")
                bad = [j for j, a in enumerate(tk) if not blocks_ok(a, o["gif_px"])]
                if bad:
                    fails.append(f"{os.path.basename(p)}: keine ganzen Pixel in Tick {bad[:5]}")
                cols = [colors_ok(a, L) for a in tk[::4]]
                if not all(c[0] for c in cols):
                    fails.append(f"{os.path.basename(p)}: Farben ausserhalb der Palette {set().union(*[c[1] for c in cols])}")
                if frames is None:
                    frames = scene_frames(sc, sp, n, [0, d["ticks"] - 1])
                if tk and not (tk[0] == composite(frames[0], L, o["gif_px"], gr)).all():
                    fails.append(f"{os.path.basename(p)}: erstes Bild != Szene Tick 0")
                if tk and not (tk[-1] == composite(frames[1], L, o["gif_px"], gr)).all():
                    fails.append(f"{os.path.basename(p)}: letztes Bild != Szene Tick {d['ticks'] - 1}")
        k = o["video_px"]
        W, H = d["size_px"]
        tw, th = o["tall_px"]
        for name, (w, h), nf in ((f"{n}_{W * k}x{H * k}.mp4", (W * k, H * k), d["ticks"] * o["mp4_loops"]),
                                 (f"{n}_{tw * k}x{th * k}.mp4", (tw * k, th * k), d["ticks"] * o["mp4_loops"]),
                                 (f"{n}_alpha_{o['alpha_palette']}.mov", (W * k, H * k), d["ticks"])):
            p = os.path.join(dst, name)
            if not os.path.exists(p):
                fails.append(f"fehlt: {p}")
                continue
            q = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height,nb_read_frames", "-of", "csv=p=0", p], capture_output=True, text=True)
            got = tuple(int(x) for x in q.stdout.strip().split(",")[:3])
            want = (w, h, nf * (o["video_fps"] // o["tick_fps"]))
            if got != want:
                fails.append(f"{name}: {got} statt {want} (Breite, Hoehe, Frames)")
        p = os.path.join(dst, f"{n}_alpha_{o['alpha_palette']}.mov")
        if os.path.exists(p):                                      # ProRes: exakte Graustufen k/5 und 1-Bit-Alpha
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba",
                                  "-"], capture_output=True).stdout
            a = np.frombuffer(raw, np.uint8).reshape(H * k, W * k, 4).astype(int)
            vis = a[..., 3] > 127
            dev = np.abs(a[..., :3][vis] - np.round(a[..., :3][vis] / 51) * 51).max(initial=0)
            gray = np.abs(a[..., 0] - a[..., 2])[vis].max(initial=0)
            amid = ((a[..., 3] > 2) & (a[..., 3] < 253)).sum()
            notes.append(f"{n} ProRes: Abweichung von k/5 max {dev}, Buntheit max {gray}, Halbtransparenz {amid} px")
            if dev > 3 or gray > 3 or amid:
                fails.append(f"{n} ProRes value: nicht exakt k/5 grau oder Alpha nicht 1 Bit")
    # 3 Maskottchen: SVG-Flaeche = PNG-Pixel, 300 dpi, Breite
    m = sc["mascot"]
    mi = sp.run(lambda: mascot_index(sc, sp))
    h, w = mi.shape
    k = mascot_scale(sc, w)
    for pal in m["palettes"] + ["1c"]:
        svg, png = (os.path.join(PREVIZ, "mascot", f"mascot_{pal}.{x}") for x in ("svg", "png"))
        if not (os.path.exists(svg) and os.path.exists(png)):
            fails.append(f"fehlt: {svg} / .png (erst `mascot`)")
            continue
        masks = read_svg(svg, w, h)
        im = Image.open(png)
        a = np.array(im.convert("RGBA"))
        if not blocks_ok(a, k):
            fails.append(f"mascot_{pal}.png: keine ganzen Pixel (x{k})")
        dpi = im.info.get("dpi", (0, 0))
        cm = a.shape[1] / dpi[0] * 2.54 if dpi[0] else 0
        if abs(dpi[0] - m["dpi"]) > 0.5 or abs(cm - m["width_cm"]) > 0.5:
            fails.append(f"mascot_{pal}.png: {dpi[0]:.0f} dpi, {cm:.1f} cm breit (soll {m['dpi']} dpi, {m['width_cm']} cm)")
        small = a[::k, ::k]
        for col, mm in masks.items():
            if mm.max() > 1:
                fails.append(f"mascot_{pal}.svg: Rechtecke ueberlappen ({col})")
            rgb = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5))
            px = (small[..., 3] > 0) & (small[..., :3] == rgb).all(-1)
            if not (px == (mm > 0)).all():
                fails.append(f"mascot_{pal}: SVG {col} {int((mm > 0).sum())} px, PNG {int(px.sum())} px")
        if sum(int((mm > 0).sum()) for mm in masks.values()) != int((small[..., 3] > 0).sum()):
            fails.append(f"mascot_{pal}: SVG-Flaeche != deckende PNG-Pixel")
        if pal == "1c" and len(masks) != 1:
            fails.append(f"mascot_1c.svg: {len(masks)} Farben statt 1")
    notes.append(f"mascot: {w} x {h} px, x{k} -> {w * k / m['dpi'] * 2.54:.2f} cm bei {m['dpi']} dpi")
    svg = os.path.join(PREVIZ, "mascot", "mascot_1c.svg")       # Gegenprobe: ein Rechteck weniger muss auffallen
    if os.path.exists(svg):
        broken = re.sub(r"M\d+ \d+h\d+v\d+h-\d+z", "", open(svg).read(), count=1)
        tmp = os.path.join(PREVIZ, "mascot", "_gegenprobe.svg")
        with open(tmp, "w") as f:
            f.write(broken)
        got = sum(int((mm > 0).sum()) for mm in read_svg(tmp, w, h).values())
        os.remove(tmp)
        if got == int(mascot_ink(sc, mi).sum()):
            fails.append("Gegenprobe SVG: ein fehlendes Rechteck faellt nicht auf")
    # 4 Emoji: Groesse, Masse, Palette, ganze Pixel, Loop am Zustand
    e = sc["emoji"]
    sets, ks, kt = emoji_set(sc, sp)
    for i, pal in enumerate(e["palettes"]):
        L = scene_lut(sc, cfg, pal)
        dst = os.path.join(PREVIZ, "emoji", *([] if i == 0 else [pal]))
        for name, frs in sets.items():
            it = e["items"][name]
            if (frs[it["frames"]] != frs[0]).any():
                fails.append(f"zumo-{name}: Frame {it['frames']} (nach dem letzten) != Frame 0")
            p = os.path.join(dst, f"zumo-{name}.gif")
            if not os.path.exists(p):
                fails.append(f"fehlt: {p} (erst `emoji`)")
                continue
            kb = os.path.getsize(p) / 1024
            if kb > e["max_kb"]:
                fails.append(f"zumo-{name}.gif: {kb:.0f} KB > {e['max_kb']} KB")
            tk = gif_ticks(p, o["tick_fps"])
            if tk[0].shape[:2] != (e["size_px"],) * 2 or len(tk) != it["frames"]:
                fails.append(f"zumo-{name}.gif: {tk[0].shape[:2]}, {len(tk)} Frames")
            if not tk[0][0, 0, 3] == 0:
                fails.append(f"zumo-{name}.gif: Ecke nicht transparent")
            for a in tk:
                ok, extra = colors_ok(a, L)
                if not ok:
                    fails.append(f"zumo-{name}.gif: Farben ausserhalb der Palette {extra}")
                    break
            ref = place(frs[0], ks, e["size_px"])
            pad = (e["size_px"] - frs[0].shape[0] * ks) // 2, (e["size_px"] - frs[0].shape[1] * ks) // 2
            if not (tk[0] == L[ref]).all():
                fails.append(f"zumo-{name}.gif: erstes Bild != Emoji Frame 0")
            crop = tk[0][pad[0]:pad[0] + frs[0].shape[0] * ks, pad[1]:pad[1] + frs[0].shape[1] * ks]
            if not blocks_ok(crop, ks):
                fails.append(f"zumo-{name}.gif: keine ganzen Pixel (x{ks})")
            tp = os.path.join(dst, "telegram", f"zumo-{name}.png")
            a = np.array(Image.open(tp).convert("RGBA"))
            if a.shape[:2] != (e["telegram_px"],) * 2 or a[0, 0, 3] != 0 or not colors_ok(a, L)[0]:
                fails.append(f"telegram zumo-{name}.png: {a.shape[:2]}, Ecke Alpha {a[0, 0, 3]}, Palette {colors_ok(a, L)[0]}")
            if i == 0:
                notes.append(f"zumo-{name}.gif: {kb:.1f} KB, {len(tk)} Frames, x{ks}")
    # 5 Gegenprobe Pixel: weich und nicht ganzzahlig skaliert muss an Palette und Bloecken scheitern
    p = os.path.join(PREVIZ, "scenes", "spumo", "spumo.gif")
    if os.path.exists(p):
        a = gif_ticks(p, o["tick_fps"])[10]
        soft = np.array(Image.fromarray(a).resize((a.shape[1] * 9 // 8, a.shape[0] * 9 // 8), Image.BILINEAR))
        L = scene_lut(sc, cfg, o["palette"])
        if colors_ok(soft, L)[0] or blocks_ok(soft, o["gif_px"]):
            fails.append("Gegenprobe Pixel: weich skaliertes Bild besteht Palette oder ganze Pixel")
    print("\n".join(notes))
    print("\n".join(fails) or "selftest ok (Szenen, Maskottchen, Emoji; Gegenproben schlagen an)")
    with open(os.path.join(PREVIZ, "scenes", "report.txt"), "w") as f:
        f.write("\n".join(notes + (fails or ["selftest ok"])) + "\n")
    return not fails


# ---------------------------------------------------------------- Einstieg

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sheet"
    sc = load()
    sp = Sprites()
    if cmd == "sheet":
        print(*gates(sc, sp)[0], sep="\n")
        p = sheet(sc, sp)
        if "--no-open" not in sys.argv:
            subprocess.run(["open", p])
    elif cmd == "scenes":
        lines, ok = gates(sc, sp)
        print(*lines, sep="\n")
        assert ok, "Gate verletzt"
        names = [a for a in sys.argv[2:] if a in SCENES] or list(SCENES)
        scenes(sc, sp, names)
    elif cmd == "mascot":
        mascot(sc, sp)
    elif cmd == "emoji":
        emoji(sc, sp)
    elif cmd == "test":
        sys.exit(0 if selftest(sc, sp) else 1)
    elif cmd == "all":
        scenes(sc, sp)
        mascot(sc, sp)
        emoji(sc, sp)
        sheet(sc, sp)
        sys.exit(0 if selftest(sc, sp) else 1)
    else:
        sys.exit(__doc__)
