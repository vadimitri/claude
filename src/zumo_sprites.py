#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "scikit-image"]
# ///
"""Zumo 2040 als 8-Bit-Sprites, gerendert aus dem echten Pololu-CAD (nicht nachgezeichnet).

Alle Gestaltungswerte stehen kommentiert in zumo_sprites/zumo_sprites.toml, hier steht nur Logik.
Handbuch (Vision, Entscheidungen, Stand): zumo_sprites/CLAUDE.md.

  uv run --with trimesh src/zumo_sprites.py mesh   einmalig: glb -> zumo_sprites/ref/zumo_mesh.npz (Materialien, Ritzel)
  uv run src/zumo_sprites.py sheet                  Kontaktbogen + GIFs (~20 s) -> zumo_sprites/previz/now/, oeffnet ihn
  uv run src/zumo_sprites.py test                   Selbsttest am fertigen Sprite

Warum so: Ein 3D-Render, einfach verkleinert, sieht nach "vorgerendert" aus (Rauschen aus hundert SMD-Teilen). Hier
entscheidet pro Pixel eine Mehrheitswahl ueber das Material, Licht wird in drei Baender gestuft, Kontur und Innenlinien
kommen aus Silhouette und Tiefenspruengen, und was ein Pixel-Artist von Hand setzen wuerde (Augen auf dem OLED, LEDs),
wird als Stempel gesetzt statt gerendert. Gerechnet wird im Wertraum 0..5 des Systems, Farbe kommt erst ueber die Palette.
"""
import json
import math
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")   # ein Pool-Prozess pro Kern; BLAS-Threads je Prozess ueberbuchen sonst
os.environ.setdefault("OMP_NUM_THREADS", "1")        # (gemessen 7.10.: Export 6 min statt ~40 s, Systemzeit > Nutzerzeit)
import subprocess
import sys
import tomllib
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_fill_holes, distance_transform_edt, label

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "zumo_sprites")
CONFIG = os.path.join(PROJECT, "zumo_sprites.toml")
MESH = os.path.join(PROJECT, "ref", "zumo_mesh.npz")

MATS = ["none", "track", "sprocket", "plastic", "pcb", "part", "screw", "cap", "usb", "bolt", "steel", "screen", "oled",
        "sensor", "lens", "motor", "slot"]
MAT = {m: i for i, m in enumerate(MATS)}
# Bauteil (Reihenfolge der Knoten im glb von zumo_wire.py) -> Material. Zugeordnet per Falschfarben-Render (7.10.).
# Die Knotennamen tragen zufaellige Suffixe, die Reihenfolge und Dreieckszahlen sind stabil (mesh() prueft sie).
PART_MAT = (["sensor"] * 8                                        # 0-7 vordere Sensorleiste (unten hinter dem Schild)
            + ["part"] * 5 + ["usb", "part", "cap", "part", "pcb"]  # 8-17 Bauteile, USB-C, Elkos, Hauptplatine (17)
            + ["part"] * 4 + ["usb"] * 2 + ["part"] * 7           # 18-30 Bauteile, USB-C-Gehaeuse
            + ["screw"] * 6 + ["part", "part"]                    # 31-38 Abstandshalter/Muttern am OLED, Stecker
            + ["oled"] * 3 + ["part", "screen", "screen", "part", "part"]   # 39-46 OLED-Modul, Glas, aktive Flaeche
            + ["screw"] * 10                                      # 47-56 Schrauben, Muttern, Abstandshalter
            + ["plastic", "lens", "plastic", "lens"]              # 57-60 IR-LED-Halter + Front-IR-LEDs
            + ["steel", "sensor", "plastic", "plastic"]           # 61 Schild, 62 Frontplatine, 63 Batteriedeckel, 64 Chassis
            + ["motor"] * 7 + ["bolt", "track"])                  # 65-71 Getriebemotoren, 72 Achsbolzen, 73 Ketten
SHAFT_Z = 44.0              # Motor-Teile weiter aussen = Wellenende in der Ritzelmitte -> "bolt" (silberne Nabe)
PART_TRIS = {17: 13282, 44: 2, 61: 5708, 63: 4052, 64: 102624, 73: 2720}   # Stichproben gegen ein anderes glb
CHASSIS = 64
# Kettenschleife aus dem CAD (Teil 73): Stadion um zwei Achsen, Aussenradius 19.5 mm, Kette bei |z| 34.9..49.5 mm
AXLE_X = (-17.8, 30.2)      # hinten (Umlenkrolle), vorne (Antrieb)
AXLE_Y = 19.5
TRACK_R = 19.5
TRACK_Z = (34.9, 49.5)
TRACK_TOL = 0.3             # mm ausserhalb der Kettenkontur, die noch als Kette zaehlen (Tesselierung der Rundung)
SPROCKET_R = 18.6           # Ritzel samt Zaehnen bleibt innerhalb der Kette
SPROCKET_Z = 36.5           # ab hier nach aussen ist Teil 64 Ritzel, innen Chassis
SPROCKET_FOLD_DEG = 60      # die Ritzel haben 6 Speichen: nach 60 Grad sieht das Bild gleich aus (nahtloser Loop)
PIVOT = (10.8, 0.0, 0.0)    # Drehpunkt = Mitte der Grundflaeche (x -37.3..58.9 inkl. Schild), am Boden
ACCENT0 = 10                # Index im Sprite: 0 frei, 1..6 = Stufe 0..5, ab 10 Akzentfarben (LEDs)
ACCENTS = "rgbymcw"


# ---------------------------------------------------------------- Konfiguration

def load(path=CONFIG, variant=None, style=None):
    """TOML lesen und pruefen. variant = Code aus [variants] (Z1 ...): ueberschreibt einzelne Werte aus [render]/[toy].
    style = Augenregel aus [eye_styles] (E1 ...), sonst [eyes].style."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    variant = variant or cfg["render"].get("variant")
    if variant:
        assert variant in cfg["variants"], f"Variante {variant} fehlt in [variants]"
        for k, v in cfg["variants"][variant].items():
            if k == "label":
                continue
            sec = next((s for s in ("render", "toy", "eyes") if k in cfg[s]), None)
            assert sec, f"[variants.{variant}].{k}: kein Schluessel in [render], [toy] oder [eyes]"
            cfg[sec][k] = v
        cfg["_variant"] = variant
    style = cfg["eyes"]["style"] = style or cfg["eyes"]["style"]  # Augenregel in 3/4 (E-Code), nach der Variante
    assert style in cfg["eye_styles"], f"[eyes].style {style!r} fehlt in [eye_styles]"
    for k, v in cfg["eye_styles"][style].items():
        if k != "label":
            assert k in cfg["eyes"], f"[eye_styles.{style}].{k}: kein Schluessel in [eyes]"
            cfg["eyes"][k] = v
    r = cfg["render"]
    assert r["mm_per_px"] > 0 and r["supersample"] >= 2, "[render]: mm_per_px > 0, supersample >= 2"
    for m, ramp in cfg["materials"].items():
        assert m in MAT and len(ramp) == 3 and all(0 <= v <= 5 for v in ramp), f"[materials].{m}: [Schatten, Mitte, Licht] 0..5"
    for name, a in cfg["anims"].items():
        assert len(a["tread"]) == 2, f"[anims.{name}].tread = [links, rechts]"
        for f in a["faces"]:
            assert f in cfg["faces"], f"[anims.{name}]: Gesicht {f!r} fehlt in [faces]"
        assert all(-r["margin_px"] < b <= 0 for b in a["bob_px"]), f"[anims.{name}].bob_px: 0 .. -{r['margin_px'] - 1}"
        for row in a["leds"]:
            assert len(row) == len(cfg["leds"]["pos_mm"]) and set(row) <= set(ACCENTS + "."), \
                f"[anims.{name}].leds: je Frame {len(cfg['leds']['pos_mm'])} Zeichen aus {ACCENTS}."
    return cfg


# ---------------------------------------------------------------- Mesh (einmalig aus dem glb)

def mesh(cfg):
    """glb -> npz: Vertices (mm), Dreiecke, Material pro Dreieck, Ritzel-Nummer pro Vertex (zum Drehen)."""
    import trimesh
    s = trimesh.load(os.path.expanduser(cfg["source"]["glb"]))
    nodes = list(s.graph.nodes_geometry)
    assert len(nodes) == len(PART_MAT), f"glb hat {len(nodes)} Bauteile, PART_MAT kennt {len(PART_MAT)}"
    V, F, M = [], [], []
    off = 0
    for k, node in enumerate(nodes):
        T, g = s.graph[node]
        m = s.geometry[g]
        assert PART_TRIS.get(k, len(m.faces)) == len(m.faces), f"Bauteil {k}: {len(m.faces)} Dreiecke, erwartet {PART_TRIS[k]}"
        V.append(trimesh.transform_points(m.vertices, T) * 1000)       # glb in Metern
        F.append(m.faces + off)
        M.append(np.full(len(m.faces), MAT[PART_MAT[k]], np.uint8))
        off += len(m.vertices)
    V, F, M = np.concatenate(V), np.concatenate(F), np.concatenate(M)
    # Ritzel aus dem Chassis-Teil schneiden: aussen (|z| > SPROCKET_Z) und im Radius einer Achse
    ch = np.repeat(np.arange(len(nodes)), [len(s.geometry[s.graph[n][1]].faces) for n in nodes]) == CHASSIS
    c = V[F].mean(1)
    d = np.stack([np.hypot(c[:, 0] - ax, c[:, 1] - AXLE_Y) for ax in AXLE_X], 1)
    spr = ch & (np.abs(c[:, 2]) > SPROCKET_Z) & (d.min(1) < SPROCKET_R)
    M[spr] = MAT["sprocket"]
    M[(M == MAT["motor"]) & (np.abs(c[:, 2]) > SHAFT_Z)] = MAT["bolt"]
    sid = np.where(spr, d.argmin(1) * 2 + (c[:, 2] > 0), -1)          # 0/1 = hinten links/rechts, 2/3 = vorne
    # Ritzel-Dreiecke bekommen eigene Vertices, damit Drehen nichts anderes mitzieht
    idx = np.nonzero(spr)[0]
    newv = V[F[idx]].reshape(-1, 3)
    F[idx] = len(V) + np.arange(len(newv)).reshape(-1, 3)
    V = np.concatenate([V, newv])
    SPR = np.full(len(V), -1, np.int8)
    SPR[F[idx].ravel()] = np.repeat(sid[idx], 3)
    os.makedirs(os.path.dirname(MESH), exist_ok=True)
    np.savez_compressed(MESH, V=V.astype(np.float32), F=F.astype(np.int32), M=M, SPR=SPR)
    print(f"{MESH}: {len(V)} Vertices, {len(F)} Dreiecke, {spr.sum()} davon Ritzel")


_MESH = {}


def get_mesh(cfg):
    """Modell nach [render].model: "cad" = echtes STEP-Mesh, "toy" = vereinfachtes Modell mit den Massen aus dem STEP."""
    model = cfg["render"]["model"]
    key = model if model == "cad" else (model, repr(sorted(cfg["toy"].items())))
    if key not in _MESH:
        if model == "cad":
            d = np.load(MESH)
            _MESH[key] = d["V"].astype(np.float64), d["F"], d["M"], d["SPR"]
        else:
            _MESH[key] = toy_mesh(cfg["toy"])
    return _MESH[key]


# ---------------------------------------------------------------- Spielzeug-Modell
# Masse aus dem STEP (mm, x vorne, y oben, z rechts), gemessen per Bounding-Box der Bauteile am 7.10.
PCB = (-37.3, 45.6, 24.5, 26.1, 34.5)        # x0 x1 y0 y1, halbe Breite zwischen den Ketten
CHASSIS_BOX = (-31.0, 34.0, 4.5, 24.5, 35.0)  # Batteriekasten zwischen den Ketten
OLED_BOARD = (-14.3, 19.2, 32.9, 34.5, 17.7)
OLED_GLASS = (-9.5, 14.5, 34.5, 35.6, 16.6)
SENSOR_BAR = (46.1, 47.4, 28.7, 37.2, 25.0)
EAR = (41.5, 45.6, 27.2, 37.2, 24.7, 32.0)    # IR-LED-Halter vorne links/rechts (x0 x1 y0 y1 |z|0 |z|1)
LENS = (45.6, 52.5, 33.0, 2.4, 28.0)         # Front-IR-LED: x0 x1, Hoehe, Radius, |z|
BLADE = ((58.4, 0.5), (49.6, 37.3), 1.0, 49.5)   # Schild als Keil: Unterkante vorne, Oberkante am Roboter (x, y), Dicke,
                                                 # halbe Breite. CAD: Unterkante x 57.8..58.9 (Vadim 7.10.: war vertauscht).
                                                 # Breite = Kettenbreite (CAD 98 vs 99 mm): sonst 1 px Kette nur links
USB = (-37.6, -29.4, 26.1, 29.3, 2.5, 11.5)
SPROCKET_FACE_Z = (44.0, 47.1)               # Ritzel-Aussenscheibe (|z|), dahinter Chassis-Seitenwand bei |z| 35


def _box(x0, x1, y0, y1, z0, z1):
    V = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], float)
    F = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                  [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    return V, F


def _ring(outer, inner, z0, z1):
    """Band zwischen zwei geschlossenen Konturen (x, y) gleicher Laenge, extrudiert von z0 bis z1."""
    n = len(outer)
    V = np.concatenate([np.c_[c, np.full(n, z)] for c in (outer, inner) for z in (z0, z1)])
    o0, o1, i0, i1 = (np.arange(n) + k * n for k in range(4))
    j = np.roll(np.arange(n), -1)
    F = []
    for a, b in ((o0, o1), (i0, i1), (o0, i0), (o1, i1)):          # Aussen, Innen, Stirnseiten
        F += [np.c_[a, a[j], b], np.c_[b, a[j], b[j]]]
    return V, np.concatenate(F)


def _prism(contour, z0, z1):
    """Konvexe Kontur (x, y) als Prisma von z0 bis z1 (Deckel als Faecher)."""
    n = len(contour)
    V = np.concatenate([np.c_[contour, np.full(n, z0)], np.c_[contour, np.full(n, z1)]])
    j = np.roll(np.arange(n), -1)
    i = np.arange(n)
    F = [np.c_[i, j, i + n], np.c_[i + n, j, j + n]]
    F += [np.c_[np.zeros(n - 2, int), i[1:-1], i[2:]], np.c_[np.full(n - 2, n), i[2:] + n, i[1:-1] + n]]
    return V, np.concatenate(F)


def _circle(cx, cy, r, n=24):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.c_[cx + r * np.cos(a), cy + r * np.sin(a)]


def _stadium(r, n=48):
    """Kettenkontur um beide Achsen, Radius r, im Uhrzeigersinn egal (geschlossen)."""
    a1 = np.linspace(-math.pi / 2, math.pi / 2, n)                # vorne: unten -> oben
    a2 = np.linspace(math.pi / 2, 3 * math.pi / 2, n)             # hinten: oben -> unten
    return np.concatenate([np.c_[AXLE_X[1] + r * np.cos(a1), AXLE_Y + r * np.sin(a1)],
                           np.c_[AXLE_X[0] + r * np.cos(a2), AXLE_Y + r * np.sin(a2)]])


def toy_mesh(t):
    """Vereinfachter Zumo aus Grundkoerpern: jede Form ist bei 2-3 mm/px noch eine Form (kein Rauschen).
    t = [toy]-Tabelle (Kopfgroesse, Kettenstaerke, Elkos ...). Gibt (V, F, M, SPR) wie das CAD-Mesh."""
    parts = []                                                     # (V, F, Material, Ritzel-ID)

    def add(vf, mat, sid=-1):
        parts.append((vf[0], vf[1], mat, sid))

    band = t["track_band_mm"]
    for sgn in (-1, 1):
        z0, z1 = sorted((sgn * TRACK_Z[0], sgn * TRACK_Z[1]))
        add(_ring(_stadium(TRACK_R), _stadium(TRACK_R - band), z0, z1), "track")
        for k, ax in enumerate(AXLE_X):
            sid = k * 2 + (sgn > 0)
            fz = sorted((sgn * SPROCKET_FACE_Z[0], sgn * SPROCKET_FACE_Z[1]))
            r_out = TRACK_R - band
            # Segmentzahlen durch 6 teilbar: nach 60 Grad Drehung deckungsgleich (nahtloser Loop)
            add(_ring(_circle(ax, AXLE_Y, r_out, 36), _circle(ax, AXLE_Y, r_out - t["rim_mm"], 36), *fz), "sprocket", sid)
            add(_prism(_circle(ax, AXLE_Y, t["hub_mm"], 18), *fz), "sprocket", sid)
            for s in range(6):                                     # Speichen
                a = math.radians(s * 60 + 30)
                w = t["spoke_mm"] / 2
                r0, r1 = t["hub_mm"] * 0.8, r_out - t["rim_mm"] * 0.5
                c = np.array([[r0, -w], [r1, -w], [r1, w], [r0, w]])
                rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
                add(_prism(c @ rot.T + (ax, AXLE_Y), *fz), "sprocket", sid)
            bz = sorted((sgn * SPROCKET_FACE_Z[1], sgn * (SPROCKET_FACE_Z[1] + 0.8)))
            add(_prism(_circle(ax, AXLE_Y, t["bolt_mm"], 12), *bz), "bolt")
        # Rueckscheibe hinter jedem Ritzel: durch die Speichenluecken sieht man dunkles Chassis, nicht durch den Roboter
        for ax in AXLE_X:
            add(_prism(_circle(ax, AXLE_Y, TRACK_R - band, 24), *sorted((sgn * 37.0, sgn * 38.0))), "plastic")
        add(_box(AXLE_X[0], AXLE_X[1], AXLE_Y - 12, AXLE_Y + 6, *sorted((sgn * 35.0, sgn * 37.0))), "plastic")
    x0, x1, y0, y1, hz = CHASSIS_BOX
    add(_box(x0, x1, y0, y1, -hz, hz), "plastic")
    x0, x1, y0, y1, hz = PCB
    add(_box(x0, x1, y0, y1, -hz, hz), "pcb")
    # OLED = Kopf: optional groesser und angehoben (Chibi), um seine Mitte skaliert
    hs, lift = t["head_scale"], t["head_lift_mm"]
    cx, cy = (OLED_BOARD[0] + OLED_BOARD[1]) / 2, OLED_BOARD[2]
    head = lambda x, y: (cx + (x - cx) * hs, cy + lift + (y - cy) * hs)
    for (bx0, bx1, by0, by1, bz), mat in ((OLED_BOARD, "oled"), (OLED_GLASS, "screen")):
        (hx0, hy0), (hx1, hy1) = head(bx0, by0), head(bx1, by1)
        add(_box(hx0, hx1, hy0, hy1, -bz * hs, bz * hs), mat)
    # Hals: dunkler Block unter dem Kopf (echt: Stiftleiste + Stecker unter dem OLED). Ohne ihn schwebt der angehobene
    # Kopf, und die Seitenansicht hat Durchsicht-Loecher.
    (nx0, ny), (nx1, _) = head(OLED_BOARD[0] + t["neck_inset_mm"], OLED_BOARD[2]), head(OLED_BOARD[1] - t["neck_inset_mm"], 0)
    add(_box(nx0, nx1, PCB[3], ny, -OLED_BOARD[4] * hs + t["neck_inset_mm"], OLED_BOARD[4] * hs - t["neck_inset_mm"]),
        "plastic")
    x0, x1, y0, y1, hz = SENSOR_BAR
    add(_box(x0, x1, y0, y1, -hz, hz), "sensor")
    for sgn in (-1, 1):
        x0, x1, y0, y1, a, b = EAR
        add(_box(x0, x1, y0, y1, *sorted((sgn * a, sgn * b))), "plastic")
        lx0, lx1, ly, lr, lz = LENS
        lens = _prism(_circle(ly, sgn * lz, lr, 10), lx0, lx1)     # Zylinder entlang x
        add((lens[0][:, [2, 0, 1]], lens[1]), "lens")
    (bx0, by0), (bx1, by1), th, hz = BLADE
    ln = math.hypot(bx1 - bx0, by1 - by0)
    u = np.array([bx1 - bx0, by1 - by0]) / ln                      # entlang des Schilds
    nrm = np.array([u[1], -u[0]])                                  # nach vorne
    quad = np.array([[bx0, by0], [bx1, by1], [bx1, by1] + nrm * th, [bx0, by0] + nrm * th])
    add(_prism(quad, -hz, hz), "steel")
    n, sw, sy0, sy1 = t["slots"], t["slot_w_mm"], t["slot_y_mm"][0], t["slot_y_mm"][1]
    for i in range(n):                                             # Schlitzreihe unten im Schild
        zc = (i - (n - 1) / 2) * t["slot_pitch_mm"]
        p0 = np.array([bx0, by0]) + u * (sy0 - by0) / u[1] + nrm * (th + 0.05)
        p1 = np.array([bx0, by0]) + u * (sy1 - by0) / u[1] + nrm * (th + 0.05)
        q = np.array([p0, p1, p1 + nrm * 0.1, p0 + nrm * 0.1])
        add(_prism(q, zc - sw / 2, zc + sw / 2), "slot")
    x0, x1, y0, y1, z0, z1 = USB
    add(_box(x0, x1, y0, y1, z0, z1), "usb")
    for x, z in t["caps_xz_mm"]:
        cap = _prism(_circle(x, z, 3.2, 12), PCB[3], PCB[3] + 5.5)
        add((cap[0][:, [0, 2, 1]], cap[1]), "cap")
    V, F, M, S = [], [], [], []
    off = 0
    for v, f, mat, sid in parts:
        V.append(v)
        F.append(f + off)
        M.append(np.full(len(f), MAT[mat], np.uint8))
        S.append(np.full(len(v), sid, np.int8))
        off += len(v)
    return np.concatenate(V), np.concatenate(F), np.concatenate(M), np.concatenate(S)


# ---------------------------------------------------------------- Kamera + Rasterizer

def camera(dir_deg, pitch_deg):
    """Matrix Roboter-lokal (x vorne, y oben, z rechts) -> Bild (rechts, oben, zur Kamera).
    dir = Fahrtrichtung auf dem Boden im Bild (0 = rechts, 90 = weg), pitch = Blick von oben."""
    t, p = math.radians(dir_deg), math.radians(pitch_deg)
    ground = np.array([[math.cos(t), 0, math.sin(t)],          # Boden rechts
                       [math.sin(t), 0, -math.cos(t)],         # Boden weg von der Kamera
                       [0, 1, 0]])                             # Hoehe
    tilt = np.array([[1, 0, 0],
                     [0, math.sin(p), math.cos(p)],            # Bild oben = Hoehe * cos + weg * sin
                     [0, -math.cos(p), math.sin(p)]])          # zur Kamera
    return tilt @ ground


def raster(S, F, W, H, K=4):
    """Z-Buffer, vektorisiert nach Dreiecksgroesse. S = Bildkoordinaten in Pixeln (x, y nach unten, Tiefe: klein = nah).
    Gibt pro Pixel die Dreiecks-ID (-1 = leer) und die Tiefe zurueck."""
    tri = S[F]
    x0 = np.floor(tri[:, :, 0].min(1) - 0.5).astype(int) + 1
    x1 = np.floor(tri[:, :, 0].max(1) - 0.5).astype(int)
    y0 = np.floor(tri[:, :, 1].min(1) - 0.5).astype(int) + 1
    y1 = np.floor(tri[:, :, 1].max(1) - 0.5).astype(int)
    ok = (x1 >= x0) & (y1 >= y0) & (x1 >= 0) & (y1 >= 0) & (x0 < W) & (y0 < H)
    bw = np.maximum(x1 - x0 + 1, y1 - y0 + 1)
    zb = np.full(W * H, np.inf)
    ib = np.full(W * H, -1)
    for lo, hi in ((0, K), (K, 4 * K), (4 * K, 16 * K), (16 * K, 10 ** 6)):
        idx = np.nonzero(ok & (bw > lo) & (bw <= hi))[0]
        if not len(idx):
            continue
        n = min(hi, int(bw[idx].max()))
        step = max(1, 2_000_000 // (n * n))
        gx, gy = (a.ravel()[None] for a in np.meshgrid(np.arange(n), np.arange(n)))
        for c in range(0, len(idx), step):
            ii = idx[c:c + step]
            px, py = x0[ii, None] + gx, y0[ii, None] + gy
            t = tri[ii]
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = ([t[:, j, i, None] for i in range(3)] for j in range(3))
            qx, qy = px + 0.5, py + 0.5
            area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            w0 = (bx - qx) * (cy - qy) - (by - qy) * (cx - qx)
            w1 = (cx - qx) * (ay - qy) - (cy - qy) * (ax - qx)
            w2 = (ax - qx) * (by - qy) - (ay - qy) * (bx - qx)
            sg = np.sign(area)
            inside = (w0 * sg >= 0) & (w1 * sg >= 0) & (w2 * sg >= 0) & (np.abs(area) > 1e-12)
            inside &= (px <= x1[ii, None]) & (py <= y1[ii, None]) & (px >= 0) & (py >= 0) & (px < W) & (py < H)
            if not inside.any():
                continue
            a = np.where(np.abs(area) > 1e-12, area, 1)
            z = (w0 * az + w1 * bz + w2 * cz) / a
            pi, zz = (py * W + px)[inside], z[inside]
            ti = np.broadcast_to(ii[:, None], px.shape)[inside]
            o = np.lexsort((zz, pi))
            pi, zz, ti = pi[o], zz[o], ti[o]
            first = np.r_[True, pi[1:] != pi[:-1]]
            pi, zz, ti = pi[first], zz[first], ti[first]
            better = zz < zb[pi]
            zb[pi[better]], ib[pi[better]] = zz[better], ti[better]
    return ib.reshape(H, W), zb.reshape(H, W)


# ---------------------------------------------------------------- Geometrie der Kette

def track_s(x, y):
    """Bogenlaenge (mm) auf der Kettenschleife, im Uhrzeigersinn von der Seite rechts gesehen (oben laeuft nach vorne)."""
    xr, xf, r = AXLE_X[0], AXLE_X[1], TRACK_R
    L = xf - xr
    s = np.where(y >= AXLE_Y, np.clip(x, xr, xf) - xr, L + math.pi * r + (xf - np.clip(x, xr, xf)))
    a = np.arctan2(y - AXLE_Y, x - xf)                            # vorderer Bogen: von oben (90 Grad) im Uhrzeigersinn
    s = np.where(x > xf, L + r * (math.pi / 2 - a), s)
    b = np.arctan2(y - AXLE_Y, x - xr)                            # hinterer Bogen: von unten (-90 Grad) im Uhrzeigersinn
    s = np.where(x < xr, 2 * L + math.pi * r + r * np.mod(-math.pi / 2 - b, 2 * math.pi), s)
    return s


def track_depth(x, y):
    """Abstand (mm) nach innen vom Aussenrand der Kettenschleife (negativ = ausserhalb)."""
    cx = np.clip(x, AXLE_X[0], AXLE_X[1])
    return TRACK_R - np.hypot(x - cx, y - AXLE_Y)


# ---------------------------------------------------------------- Sprite

def anim_frame(cfg, anim, frame):
    a = cfg["anims"][anim]
    pick = lambda lst: lst[frame % len(lst)]
    return a["tread"], pick(a["faces"]), pick(a["leds"]), a["frames"], pick(a["bob_px"])


def view_canvas(cfg, pitch):
    """Leinwand pro Ansicht: gross genug fuer jede Richtung, Drehpunkt fest (Sprites einer Ansicht liegen deckungsgleich)."""
    r = cfg["render"]
    V = get_mesh(cfg)[0] - PIVOT
    ext = np.abs(V[:, [0, 2]]).max(0)
    rad = math.hypot(*ext)                                         # Radius um den Drehpunkt am Boden
    hgt = V[:, 1].max()
    p = math.radians(pitch)
    up = rad * math.sin(p) + hgt * math.cos(p)                     # wie weit der Roboter ueber den Drehpunkt ragt
    down = rad * math.sin(p)
    m = r["margin_px"]
    W = 2 * math.ceil(rad / r["mm_per_px"]) + 2 * m
    H = math.ceil(up / r["mm_per_px"]) + math.ceil(down / r["mm_per_px"]) + 2 * m
    return W, H, (W / 2, m + math.ceil(up / r["mm_per_px"]))       # Drehpunkt in Pixeln (x, y)


def gbuffer(cfg, dir_deg, pitch, tread, frame, nframes):
    """Abtastungen in Supersample-Aufloesung: Material, Normale (Bild), Tiefe, lokale Position."""
    r = cfg["render"]
    V, F, M, SPR = get_mesh(cfg)
    keep = ~np.isin(M, [MAT[m] for m in r["hide"]])                # Kleinkram, den ein Pixel-Artist weglaesst
    F, M = F[keep], M[keep]
    V = V.copy()
    # Ritzel drehen: links = Ritzel 0, 2; rechts = 1, 3. Vorwaerts dreht von rechts gesehen im Uhrzeigersinn.
    for sid in range(4):
        sign = tread[sid % 2]
        if not sign:
            continue
        sel = SPR == sid
        ang = -sign * math.radians(SPROCKET_FOLD_DEG) * frame / nframes
        cx, cy = AXLE_X[sid // 2], AXLE_Y
        x, y = V[sel, 0] - cx, V[sel, 1] - cy
        V[sel, 0], V[sel, 1] = cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang)
    R = camera(dir_deg, pitch)
    W, H, (ox, oy) = view_canvas(cfg, pitch)
    ss = r["supersample"]
    mm = r["mm_per_px"] / ss
    C = (V - PIVOT) @ R.T
    S = np.stack([C[:, 0] / mm + ox * ss, -C[:, 1] / mm + oy * ss, -C[:, 2]], 1)
    ib, zb = raster(S, F, W * ss, H * ss)
    hit = ib >= 0
    tri = np.where(hit, ib, 0)
    mat = np.where(hit, M[tri], 0)
    e1, e2 = V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]
    nl = np.cross(e1, e2)
    nl /= np.maximum(np.linalg.norm(nl, axis=1, keepdims=True), 1e-12)
    n = (nl @ R.T)[tri]
    n *= np.where(n[..., 2:3] < 0, -1, 1)                          # CAD-Wicklung ist nicht verlaesslich: zur Kamera drehen
    # lokale Position jeder Abtastung (Bild -> Roboter), fuer Kettenmuster und Ketten-Band
    yy, xx = np.mgrid[0:H * ss, 0:W * ss]
    cam = np.stack([(xx + 0.5 - ox * ss) * mm, -(yy + 0.5 - oy * ss) * mm, -np.where(hit, zb, 0)], -1)
    loc = cam @ R + PIVOT
    td = track_depth(loc[..., 0], loc[..., 1])
    band = hit & (np.abs(loc[..., 2]) >= TRACK_Z[0]) & (np.abs(loc[..., 2]) <= TRACK_Z[1]) \
        & (td >= -TRACK_TOL) & (td <= r["track_band_mm"])          # nur in der Schleife (Vadim 7.10.: Schild war Kette)
    mat = np.where(band, MAT["track"], mat)
    return dict(mat=mat, n=n, z=np.where(hit, zb, np.inf), loc=loc, W=W, H=H, ss=ss, R=R, origin=(ox, oy))


def sprite(cfg, view, dir_deg, anim="drive", frame=0):
    """Ein Sprite als Index-Bild: 0 frei, 1..6 = Stufe 0..5, ACCENT0+i = Akzent i (LED-Farbe)."""
    r = cfg["render"]
    pitch = cfg["views"][view]["pitch_deg"]
    tread, face, leds, nframes, bob = anim_frame(cfg, anim, frame)
    g = gbuffer(cfg, dir_deg, pitch, tread, frame, nframes)
    W, H, ss = g["W"], g["H"], g["ss"]
    blk = lambda a: a.reshape(H, ss, W, ss, *a.shape[2:]).swapaxes(1, 2).reshape(H, W, ss * ss, *a.shape[2:])
    mat, n, z, loc = blk(g["mat"]), blk(g["n"]), blk(g["z"]), blk(g["loc"])
    # Mehrheitswahl Material (gewichtet), Deckung
    hitc = (mat > 0).mean(-1)
    w = np.array([0] + [cfg["vote"].get(m, 1.0) for m in MATS[1:]])
    votes = np.stack([(mat == k).sum(-1) * w[k] for k in range(len(MATS))], -1)
    win = votes.argmax(-1)
    opaque = hitc >= r["coverage_frac"]
    for m, frac in r["thin"].items():                              # duennes Blech (Schild von der Seite) bleibt 1 px Linie
        thin = (mat == MAT[m]).mean(-1) >= frac
        win = np.where(thin & ~opaque, MAT[m], win)
        opaque |= thin
    win = np.where(opaque, win, 0)
    sel = (mat == win[..., None]) & opaque[..., None]
    cnt = np.maximum(sel.sum(-1), 1)
    L = np.array(r["light"], float)
    L /= np.linalg.norm(L)
    ndl = ((n @ L) * sel).sum(-1) / cnt
    depth = np.where(sel, z, 0).sum(-1) / cnt
    band = np.digitize(ndl, r["bands"])                            # 0 Schatten, 1 Mitte, 2 Licht
    ramp = np.zeros((len(MATS), 3), int)
    for m, v in cfg["materials"].items():
        ramp[MAT[m]] = v
    if r["min_island_px"]:
        win = clean_islands(win, opaque, r["min_island_px"], [MAT[m] for m in r["island_keep"]])
    val = ramp[win, band]
    for m, (lo, hi) in cfg["dither"].items():                     # Verlauf ueber die Hoehe, Bayer 4x4 (D3 des Systems)
        k = MAT[m]
        msel = sel & (mat == k)
        y = (loc[..., 1] * msel).sum(-1) / np.maximum(msel.sum(-1), 1)
        ys = loc[..., 1][mat == k]
        h = np.clip((y - ys.min()) / max(np.ptp(ys), 1e-6), 0, 1) if len(ys) else y * 0
        v = lo + (hi - lo) * h + (band - 1)
        thr = np.tile(bayer4(), (H // 4 + 1, W // 4 + 1))[:H, :W]
        val = np.where(win == k, np.clip(np.floor(v + thr), 0, 5).astype(int), val)
    # Kettenmuster: Stollen laufen mit der Kette (Bogenlaenge s), Rille = eine Stufe dunkler
    tr = cfg["tread"]
    mmpx = r["mm_per_px"]
    side = np.where(loc[..., 2] > 0, 1, 0)
    shift = np.where(side == 1, tread[1], tread[0]) * frame * tr["step_px"] * mmpx
    s = track_s(loc[..., 0], loc[..., 1]) - shift
    groove = np.mod(s, tr["pitch_px"] * mmpx) < tr["groove_px"] * mmpx
    gsel = sel & (mat == MAT["track"])
    gfrac = (groove & gsel).sum(-1) / np.maximum(gsel.sum(-1), 1)
    val = np.where((win == MAT["track"]) & (gfrac > 0.5), np.maximum(val - 1, 0), val)
    # Pixel-Art-Nacharbeit: Vertiefungen dunkler, Lichtkante oben links, Innenlinien hinter Tiefenspruengen
    dz = np.where(opaque, depth, np.inf)
    if r["cavity_mm"]:
        rec = cavity(dz, r["cavity_px"], r["cavity_mm"])
        RECESS[:] = [rec & (win == MAT["steel"])]                  # fuer den Selbsttest: Schild ist eben
        val = np.where(rec, np.maximum(val - 1, 0), val)
    nb = lambda a, dy, dx, fill: np.pad(a, 1, constant_values=fill)[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
    if r["rim"]:
        rim = np.zeros_like(opaque)
        for dy, dx in ((-1, 0), (0, -1)):                         # Nachbar zum Licht hin (oben, links) liegt tiefer/frei
            rim |= nb(dz, dy, dx, np.inf) > dz + r["line_mm"]
        rim &= opaque & (win != MAT["screen"])
        val = np.where(rim, np.minimum(val + 1, 5), val)
    if r["line_mm"]:
        closer = np.zeros_like(opaque)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            closer |= nb(dz, dy, dx, np.inf) < dz - r["line_mm"]
        val = np.where(opaque & closer, 0, val)
    if r["despeckle"]:
        val = despeckle(val, opaque)
    if r["value_island_px"]:                                       # Splitter aus Licht/Linie/Vertiefung: ein Pixel-Artist
        keep = np.isin(win, [MAT[m] for m in r["island_keep"]])    # setzt keine 1-2-px-Inseln (Vadim 8.10.: "nur pixelized")
        val = np.where(keep, val, clean_islands(np.where(keep, -1, val), opaque & ~keep, r["value_island_px"], []))
    out = np.where(opaque, val + 1, 0).astype(np.uint8)
    EYES.clear()
    if cfg["eyes"]["show"]:
        out = stamp_eyes(cfg, out, win, g, view, dir_deg, face)
    out = stamp_leds(cfg, out, depth, g, leds)
    if r["outline"]:
        o = out > 0
        ring = np.zeros_like(o)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ring |= np.roll(np.roll(o, dy, 0), dx, 1)
        out = np.where(ring & ~o, 1 + r["outline_value"], out).astype(np.uint8)
    return np.roll(out, bob, 0)                                    # Hopser: Rand ist frei (margin_px > Hopser)


def cavity(dz, k, mm):
    """Vertiefung = konkav: tiefer als die Mitte zweier gegenueberliegender Nachbarn (Abstand k, waagrecht, senkrecht,
    diagonal). Eine schraege Ebene ist das nie. Vorher: tiefer als das Minimum im Umkreis -> in 3/4 wurden Schild und
    Kettenflanken (steile Ebenen, > 2 mm Tiefe pro Pixel) fleckig dunkel, "sieht nur verpixelt aus" (Vadim 8.10.)."""
    H, W = dz.shape
    p = np.pad(dz, k, constant_values=np.inf)
    at = lambda dy, dx: p[k + dy:k + dy + H, k + dx:k + dx + W]
    out = np.zeros(dz.shape, bool)
    with np.errstate(invalid="ignore"):                            # inf ausserhalb der Silhouette zaehlt nicht
        for dy, dx in ((0, k), (k, 0), (k, k), (k, -k)):
            out |= dz - (at(dy, dx) + at(-dy, -dx)) / 2 > mm
    return out & np.isfinite(dz)


def bayer4():
    """Bayer 4x4 aus dem System (styles.bayer, D3), Schwellen in (0, 1)."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import styles as S
    return S.bayer(4)


def clean_islands(win, opaque, min_px, keep):
    """Material-Inseln kleiner als min_px (8er-Nachbarschaft) gehen im umgebenden Material auf. keep = nie anfassen."""
    out = win.copy()
    gone = np.zeros_like(opaque)
    for k in np.unique(win[opaque]):
        if k in keep:
            continue
        lab, n = label(win == k, structure=np.ones((3, 3)))
        sizes = np.bincount(lab.ravel())
        small = (sizes < min_px)
        small[0] = False
        gone |= small[lab]
    if gone.any():
        idx = distance_transform_edt(gone | ~opaque, return_distances=False, return_indices=True)
        fill = win[idx[0], idx[1]]
        out = np.where(gone, fill, out)
    return out


def despeckle(val, opaque):
    """Ein Pixel, dessen Wert keinem seiner 8 Nachbarn gleicht, nimmt den haeufigsten Nachbarwert an (Pixel-Art: keine
    Waisen). Nur im Inneren, die Silhouette bleibt."""
    H, W = val.shape
    pad = np.pad(np.where(opaque, val, -1), 1, constant_values=-1)
    nb = np.stack([pad[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx], -1)
    same = (nb == val[..., None]).any(-1)
    counts = np.stack([(nb == k).sum(-1) for k in range(6)], -1)
    inner = opaque & (nb >= 0).all(-1)
    return np.where(inner & ~same, counts.argmax(-1), val)


def to_px(cfg, g, p):
    """Lokaler Punkt (mm) -> Sprite-Pixel (x, y) und Tiefe (wie im Z-Buffer, klein = nah)."""
    c = (np.asarray(p, float) - PIVOT) @ g["R"].T
    mm = cfg["render"]["mm_per_px"]
    ox, oy = g["origin"]
    return c[0] / mm + ox, -c[1] / mm + oy, -c[2]


EYES = []                   # gestempelte Augenpixel des letzten Sprites (fuer den Selbsttest)
RECESS = []                 # Vertiefung auf dem Schild im letzten Sprite (fuer den Selbsttest)


def stamp_eyes(cfg, out, win, g, view, dir_deg, face):
    """Augen als Stempel aufs OLED, pixelgenau und auf den Bildschirm beschnitten. Draufsicht: Lage aus dem 3D, das
    Gesicht dreht mit dem Roboter. Sonst Zeichner-Logik: beide Augen auf einer Zeile, Mindestabstand, in Fahrtrichtung
    verschoben (physikalisch stuenden sie bei Fahrt nach rechts uebereinander, als Figur liest sich das nicht)."""
    e = cfg["eyes"]
    EYES.clear()
    scr = win == MAT["screen"]
    V, F, M, _ = get_mesh(cfg)
    sv = V[np.unique(F[M == MAT["screen"]])]
    lo, hi = sv.min(0), sv.max(0)
    x0, y = (lo[0] + hi[0]) / 2 + e["offset_x_frac"] * (hi[0] - lo[0]), hi[1]
    gap = e["spacing_frac"] * (hi[2] - lo[2])
    cx, cy, _ = to_px(cfg, g, (x0, y, 0.0))
    ix, iy = int(math.floor(cx)), int(math.floor(cy))
    if not (0 <= iy < scr.shape[0] and 0 <= ix < scr.shape[1]) or not scr[iy, ix]:
        return out                                                 # Bildschirm nicht sichtbar (Seite, verdeckt)
    st = np.array([[c == "#" for c in row] for row in
                   cfg["faces"][face]["tall" if scr[:, ix].sum() >= e["min_rows_tall"] else "flat"]])
    side = [to_px(cfg, g, (x0, y, sgn * gap / 2))[:2] for sgn in (-1, 1)]   # linkes, rechtes Auge des Roboters
    if view == "top":
        k = int(round((dir_deg - 90) / 90)) % 4
        eyes = [(side[0], np.rot90(st, k)), (side[1], np.rot90(st[:, ::-1], k))]
    else:
        t = math.radians(dir_deg)
        if math.sin(t) > e["away_sin"] and not e["show_away"]:
            return out                                             # Hinterkopf: das OLED schaut nach hinten, ein Gesicht
                                                                   # von hinten liest sich als Front (Vadim 8.10.: "andersrum")
        sep = max(abs(side[0][0] - side[1][0]), st.shape[1] + e["min_gap_px"])
        look = e["look_px"] * math.cos(t)
        diag = abs(math.cos(t)) > 0.3 and math.sin(t) < -0.3       # schraeg zur Kamera (225, 315)
        if diag and e["diag_forward_frac"]:                        # Blick dorthin, wohin er faehrt (Seite: sonst am Rand)
            fx = x0 + e["diag_forward_frac"] * (hi[0] - lo[0])
            cx, cy, _ = to_px(cfg, g, (fx, y, 0.0))
            side = [to_px(cfg, g, (fx, y, sgn * gap / 2))[:2] for sgn in (-1, 1)]
        (_, ly), (_, ry) = sorted(side)                            # Augen im Bild links, rechts
        tilt = round((ry - ly) / 2) if e["plane"] and diag else 0  # Paar liegt auf der Bildschirmebene (Iso-Treppe)
        left, right = st, st[:, ::-1]
        n = e["far_narrow_px"] if diag and st.shape[1] > 1 else 0
        w = st.shape[1]
        keep = (w - n - 1) // 2 - (w - 1) // 2                     # Stempel wird mittig gesetzt: Rest bleibt, wo er war
        dl = dr = 0
        if n and math.cos(t) > 0:                                  # 3/4-Gesicht: das Auge auf der Fahrtseite ist das ferne,
            right, dr = right[:, :w - n], keep                     # schmaler, Innenkante bleibt
        elif n:
            left, dl = left[:, n:], n + keep
        eyes = [((cx + look - sep / 2 + dl, cy - tilt), left), ((cx + look + sep / 2 + dr, cy + tilt), right)]
    for (px, py), stp in eyes:
        h, w = stp.shape
        ys, xs = np.nonzero(stp)
        ys, xs = ys + int(math.floor(py)) - (h - 1) // 2, xs + int(math.floor(px)) - (w - 1) // 2
        ok = (ys >= 0) & (ys < out.shape[0]) & (xs >= 0) & (xs < out.shape[1])
        ys, xs = ys[ok], xs[ok]
        keep = scr[ys, xs]
        out[ys[keep], xs[keep]] = 6                                # Stufe 5 = hellste
        EYES.append((ys[keep], xs[keep]))
    return out


def stamp_leds(cfg, out, depth, g, leds):
    """LEDs als einzelne Pixel in Akzentfarbe, nur wo sie nicht verdeckt sind."""
    hgt = cfg["leds"]["height_mm"]
    for (x, z), c in zip(cfg["leds"]["pos_mm"], leds):
        if c == ".":
            continue
        px, py, d = to_px(cfg, g, (x, hgt, z))
        ix, iy = int(math.floor(px)), int(math.floor(py))
        if 0 <= iy < out.shape[0] and 0 <= ix < out.shape[1] and out[iy, ix] and depth[iy, ix] > d - 2.5:
            out[iy, ix] = ACCENT0 + ACCENTS.index(c)
    return out


# ---------------------------------------------------------------- Farbe

def palette(cfg, name):
    """Name aus [palettes] oder P-Code des Systems -> (6 Stufen RGB, Akzente RGB)."""
    hx = lambda c: tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    if name in cfg["palettes"]:
        p = cfg["palettes"][name]
        return [hx(c) for c in p["steps"]], [hx(p["accents"][a]) for a in ACCENTS]
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import styles as S
    code = {c: v for c, v, *_ in S.AX["P"]}
    steps = S.PALS[code.get(name, name)]
    if len(steps) == 4:                                            # 4-stufige Paletten wie im System auf 6 verdoppeln
        steps = [steps[i] for i in (0, 1, 1, 2, 2, 3)]
    steps = [hx(c) for c in steps]
    return steps, [steps[5]] * len(ACCENTS)                       # Akzente leuchten in der hellsten Stufe


def colorize(cfg, idx, pal):
    steps, acc = palette(cfg, pal)
    lut = np.zeros((256, 4), np.uint8)
    for i, c in enumerate(steps):
        lut[1 + i] = (*c, 255)
    for i, c in enumerate(acc):
        lut[ACCENT0 + i] = (*c, 255)
    return lut[idx]


# ---------------------------------------------------------------- Boegen

def _job(a):
    cfg, view, d, anim, fr = a
    return sprite(cfg, view, d, anim, fr)


def sheet(cfg):
    out = os.path.join(PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    sh = cfg["sheet"]
    z = sh["zoom"]
    jobs = [(cfg, v, d, "drive", 0) for v, vv in cfg["views"].items() for d in vv["dirs_deg"]]
    with Pool() as pool:
        imgs = pool.map(_job, jobs)
    rows = {}
    for (_, v, d, _, _), im in zip(jobs, imgs):
        rows.setdefault(v, []).append((d, im))
    # ein Block pro Palette x Grund
    blocks = []
    for pal in sh["palettes"]:
        for gr in sh["grounds"]:
            bg = tuple(int(gr[i:i + 2], 16) for i in (1, 3, 5))
            lines = []
            for v, items in rows.items():
                tiles = [Image.fromarray(colorize(cfg, im, pal)).resize((im.shape[1] * z, im.shape[0] * z), Image.NEAREST)
                         for _, im in items]
                w = sum(t.width for t in tiles) + 8 * (len(tiles) - 1)
                h = max(t.height for t in tiles)
                line = Image.new("RGB", (w, h + 18), bg)
                x = 0
                for (d, _), t in zip(items, tiles):
                    line.paste(t, (x, 0), t)
                    ImageDraw.Draw(line).text((x + 2, h + 4), f"{v} {d:g}", fill=(128, 128, 140))
                    x += t.width + 8
                lines.append(line)
            W = max(l.width for l in lines)
            blk = Image.new("RGB", (W + 24, sum(l.height + 12 for l in lines) + 30), bg)
            ImageDraw.Draw(blk).text((12, 8), f"{pal} auf {gr}", fill=(128, 128, 140))
            y = 26
            for l in lines:
                blk.paste(l, (12, y))
                y += l.height + 12
            blocks.append(blk)
    W = max(b.width for b in blocks)
    S = Image.new("RGB", (W, sum(b.height for b in blocks)), (20, 20, 24))
    y = 0
    for b in blocks:
        S.paste(b, (0, y))
        y += b.height
    p = os.path.join(out, "sheet.png")
    S.save(p)
    print(p)
    return p


def _vjob(a):
    code, view, d = a
    return sprite(load(variant=code), view, d)


def variants(cfg):
    """Variantenbogen: pro Z-Code eine Zeile mit den wichtigsten Ansichten, Echtfarben auf hell + dunkel, dazu P1."""
    out = os.path.join(PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    z = cfg["sheet"]["zoom"]
    cols = [tuple(c) for c in cfg["sheet"]["variant_views"]]
    codes = list(cfg["variants"])
    jobs = [(c, v, d) for c in codes for v, d in cols]
    with Pool() as pool:
        imgs = pool.map(_vjob, jobs)
    lines = []
    for ci, code in enumerate(codes):
        vc = load(variant=code)
        row = imgs[ci * len(cols):(ci + 1) * len(cols)]
        for pal, gr in cfg["sheet"]["variant_looks"]:
            bg = tuple(int(gr[i:i + 2], 16) for i in (1, 3, 5))
            tiles = [Image.fromarray(colorize(vc, im, pal)).resize((im.shape[1] * z, im.shape[0] * z), Image.NEAREST)
                     for im in row]
            h = max(t.height for t in tiles)
            line = Image.new("RGB", (220 + sum(t.width + 16 for t in tiles), h + 16), bg)
            d = ImageDraw.Draw(line)
            d.text((12, 12), code, fill=(140, 140, 155), font_size=40)
            d.text((12, 62), cfg["variants"][code].get("label", ""), fill=(140, 140, 155), font_size=15)
            d.text((12, 84), pal, fill=(140, 140, 155), font_size=15)
            x = 220
            for t in tiles:
                line.paste(t, (x, h - t.height + 8), t)
                x += t.width + 16
            lines.append(line)
    W = max(l.width for l in lines)
    S = Image.new("RGB", (W, sum(l.height for l in lines)), (20, 20, 24))
    y = 0
    for l in lines:
        S.paste(l, (0, y))
        y += l.height
    p = os.path.join(out, "variants.png")
    S.save(p)
    print(p)
    return p


def look(cfg, views=(("tq", 270), ("tq", 315), ("tq", 0), ("tq", 45), ("top", 0), ("top", 90), ("side", 0), ("front", 270)),
         looks=(("natural", "#E9E6F2"), ("P1", "#0A0711")), zoom=10):
    """Detailbogen fuer eine Variante: wenige Ansichten gross, zum Pixel-Pruefen."""
    out = os.path.join(PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    with Pool() as pool:
        imgs = pool.map(_job, [(cfg, v, d, "drive", 0) for v, d in views])
    rows = []
    for pal, gr in looks:
        bg = tuple(int(gr[i:i + 2], 16) for i in (1, 3, 5))
        tiles = [Image.fromarray(colorize(cfg, im, pal)).resize((im.shape[1] * zoom, im.shape[0] * zoom), Image.NEAREST)
                 for im in imgs]
        h = max(t.height for t in tiles)
        row = Image.new("RGB", (sum(t.width + 20 for t in tiles), h + 20), bg)
        x = 10
        for t in tiles:
            row.paste(t, (x, h - t.height + 10), t)
            x += t.width + 20
        rows.append(row)
    S = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows)))
    y = 0
    for r in rows:
        S.paste(r, (0, y))
        y += r.height
    p = os.path.join(out, f"look_{cfg.get('_variant', 'base')}.png")
    S.save(p)
    print(p)
    return p


def _ejob(a):
    code, style, view, d, anim = a
    return sprite(load(variant=code, style=style), view, d, anim, 0)


def eyes_sheet(cfg, views=(("tq", 0), ("tq", 45), ("tq", 90), ("tq", 135), ("tq", 180), ("tq", 225), ("tq", 270),
                           ("tq", 315), ("front", 90)), anims=("idle", "win"), zoom=6):
    """Augenbogen: pro E-Code eine Zeile (idle + win), alle 3/4-Richtungen. Vadim waehlt per Code."""
    out = os.path.join(PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    code = cfg.get("_variant")
    styles = list(cfg["eye_styles"])
    jobs = [(code, s, v, d, a) for s in styles for a in anims for v, d in views]
    with Pool() as pool:
        imgs = pool.map(_ejob, jobs)
    bg = tuple(int(cfg["sheet"]["grounds"][1][i:i + 2], 16) for i in (1, 3, 5))
    lines, k = [], 0
    for s in styles:
        for a in anims:
            row = imgs[k:k + len(views)]
            k += len(views)
            tiles = [Image.fromarray(colorize(cfg, im, "natural")).resize((im.shape[1] * zoom, im.shape[0] * zoom),
                                                                          Image.NEAREST) for im in row]
            h = max(t.height for t in tiles)
            line = Image.new("RGB", (240 + sum(t.width + 12 for t in tiles), h + 12), bg)
            dr = ImageDraw.Draw(line)
            dr.text((12, 10), s, fill=(60, 60, 75), font_size=40)
            dr.text((12, 60), cfg["eye_styles"][s].get("label", ""), fill=(60, 60, 75), font_size=15)
            dr.text((12, 82), a, fill=(110, 110, 125), font_size=15)
            x = 240
            for t in tiles:
                line.paste(t, (x, h - t.height + 6), t)
                x += t.width + 12
            lines.append(line)
    S = Image.new("RGB", (max(l.width for l in lines), sum(l.height for l in lines) + 30), bg)
    ImageDraw.Draw(S).text((252, 6), "   ".join(f"{v} {d:g}" for v, d in views), fill=(110, 110, 125), font_size=15)
    y = 30
    for l in lines:
        S.paste(l, (0, y))
        y += l.height
    p = os.path.join(out, f"eyes_{code or 'base'}.png")
    S.save(p)
    print(p)
    return p


def gifs(cfg, specs, pal="natural"):
    """Animierte Vorschau (vergroessert) pro (Ansicht, Richtung, Animation)."""
    out = os.path.join(PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    z = cfg["sheet"]["zoom"]
    bg = tuple(int(cfg["sheet"]["grounds"][0][i:i + 2], 16) for i in (1, 3, 5))
    jobs = [(cfg, v, d, a, f) for v, d, a in specs for f in range(cfg["anims"][a]["frames"])]
    with Pool() as pool:
        imgs = pool.map(_job, jobs)
    paths = []
    k = 0
    for v, d, a in specs:
        n = cfg["anims"][a]["frames"]
        frames = []
        for im in imgs[k:k + n]:
            rgba = Image.fromarray(colorize(cfg, im, pal)).resize((im.shape[1] * z, im.shape[0] * z), Image.NEAREST)
            f = Image.new("RGB", rgba.size, bg)
            f.paste(rgba, (0, 0), rgba)
            frames.append(f)
        k += n
        p = os.path.join(out, f"{a}_{v}_{d:g}.gif")
        frames[0].save(p, save_all=True, append_images=frames[1:], duration=1000 // 12, loop=0)
        paths.append(p)
    return paths


# ---------------------------------------------------------------- Selbsttest

def eye_rows():
    """Zeile (Mittel) jedes gestempelten Auges des letzten Sprites, von links nach rechts."""
    return [ys.mean() for ys, xs in sorted(EYES, key=lambda e: e[1].mean()) if len(ys)]


def selftest(cfg):
    """Misst am fertigen Sprite. Jeder Test schlaegt am alten Fehler an (geprueft 7.10. durch kurzes Einbauen)."""
    fails = []
    n = cfg["anims"]["drive"]["frames"]
    cad = cfg["render"]["model"] == "cad"                          # STEP-Ritzel: keine 60-Grad-Symmetrie, echte Luecken
    for v, d in () if cad else (("top", 22.5), ("tq", 315), ("side", 0)):
        a0, a1, an = (sprite(cfg, v, d, "drive", f) for f in (0, 1, n))
        if (a0 != an).sum() > 2:                                   # Loop: Frame n = Frame 0 (Stollen + 6er-Speichen)
            fails.append(f"Loop {v} {d}: Frame {n} weicht in {(a0 != an).sum()} px von Frame 0 ab")
        if (a0 != a1).sum() < 10:
            fails.append(f"Kette {v} {d}: Frame 0 -> 1 aendert nur {(a0 != a1).sum()} px")
    e = cfg["eyes"]
    for d in (0, 180, 270) if e["show"] else ():                  # alter Fehler: Augen uebereinander bei Fahrt seitwaerts
        sprite(cfg, "tq", d, "idle", 0)
        rows = eye_rows()
        if len(rows) != 2 or abs(rows[0] - rows[1]) > 0.5:
            fails.append(f"Augen tq {d}: {len(rows)} Augen, Zeilen {rows}")
    for v, d in (("tq", 45), ("tq", 90), ("tq", 135), ("front", 90)) if e["show"] and not e["show_away"] else ():
        sprite(cfg, v, d, "idle", 0)                               # alter Fehler: von hinten schaut ihn ein Gesicht an,
        if eye_rows():                                             # er wirkt "andersrum" (Vadim 8.10.)
            fails.append(f"Hinterkopf {v} {d}: {len(eye_rows())} Augen sichtbar")
    for d in (225, 315) if cfg["render"]["cavity_mm"] else ():   # alter Fehler: Vertiefung = tiefer als das Minimum im
        sprite(cfg, "tq", d, "idle", 0)                            # Umkreis -> schraege Ebenen (Schild) fleckig dunkel
        if RECESS and RECESS[0].sum():
            fails.append(f"Vertiefung tq {d}: {RECESS[0].sum()} px auf dem ebenen Schild abgedunkelt")
    if not cad:                                                    # alter Fehler: durch die Speichenluecken sieht man
        g = gbuffer(cfg, 0, 0, (0, 0), 0, n)                       # das Ritzel der anderen Seite (Pixelrauschen)
        loc, hit = g["loc"], g["mat"] > 0
        r_in = TRACK_R - cfg["toy"]["track_band_mm"] - 1
        disc = np.min([np.hypot(loc[..., 0] - ax, loc[..., 1] - AXLE_Y) for ax in AXLE_X], 0) < r_in
        deep = hit & disc & (loc[..., 2] < SPROCKET_Z)             # Kamera sieht die rechte Seite (+z)
        if deep.mean() > 0.001:
            fails.append(f"Seite: {deep.sum()} Abtastungen sehen durch die Ritzel hindurch")
    for v, d in (("front", 270), ("tq", 315), ("top", 0)):         # alter Fehler: Schildraender ausserhalb der Kettenschleife
        g = gbuffer(cfg, d, cfg["views"][v]["pitch_deg"], (0, 0), 0, n)   # wurden zu Kette (Kette von vorne sichtbar)
        loc = g["loc"][g["mat"] == MAT["track"]]
        out_ = (track_depth(loc[:, 0], loc[:, 1]) < -1.0).sum()   # feste Schwelle, unabhaengig von TRACK_TOL
        if out_:
            fails.append(f"Kette {v} {d}: {out_} Abtastungen ausserhalb der Kettenschleife als Kette markiert")
    for v, vv in cfg["views"].items():                             # gleiche Leinwand fuer alle Richtungen einer Ansicht
        shapes = {sprite(cfg, v, d).shape for d in vv["dirs_deg"][:3]}
        if len(shapes) != 1:
            fails.append(f"Leinwand {v}: {shapes}")
    print("\n".join(fails) or f"selftest ok ({cfg.get('_variant', 'base')})")
    return not fails


# ---------------------------------------------------------------- Export

def lut(cfg, pal):
    """Palette als Liste fuer P-Mode-Bilder (Index wie im Sprite: 0 frei, 1..6 Stufen, ab ACCENT0 Akzente)."""
    steps, acc = palette(cfg, pal)
    p = [(0, 0, 0)] * 256
    p[1:7] = steps
    p[ACCENT0:ACCENT0 + len(acc)] = acc
    return [c for rgb in p for c in rgb]


def indexed(idx, pal_list, scale=1):
    im = Image.fromarray(np.kron(idx, np.ones((scale, scale), np.uint8)) if scale > 1 else idx, "P")
    im.putpalette(pal_list)
    im.info["transparency"] = 0
    return im


def dirname(d):
    return f"{d:g}".replace(".", "_")


def export(cfg):
    """Alle Ansichten x Richtungen x Animationen -> Sheets (P-Mode, umfaerbbar), Sequenzen, GIFs, atlas.json, index.html.
    Sheet-Layout: eine Zeile pro Richtung (wie dirs_deg), eine Spalte pro Frame."""
    ex = cfg["export"]
    code = cfg.get("_variant", "base")
    root = os.path.join(os.path.expanduser(ex["dir"]), code)
    views, anims = cfg["views"], cfg["anims"]
    jobs = [(cfg, v, d, a, f) for v, vv in views.items() for d in vv["dirs_deg"] for a, aa in anims.items()
            for f in range(aa["frames"])]
    with Pool() as pool:
        imgs = pool.map(_job, jobs, chunksize=4)
    spr = {j[1:]: im for j, im in zip(jobs, imgs)}
    sc = ex["scale"]
    atlas = dict(variant=code, label=cfg["variants"].get(code, {}).get("label", ""), mm_per_px=cfg["render"]["mm_per_px"],
                 fps=ex["fps"], scale_hint=sc,
                 index="0 = transparent, 1..6 = value step 0..5 (ground -> ink), "
                       f"{ACCENT0}.. = LED accents {' '.join(ACCENTS)}",
                 sheet_layout="row = direction (dirs_deg order), column = frame",
                 palettes={p: {k: ["#%02X%02X%02X" % c for c in cs] for k, cs in zip(("steps", "accents"), palette(cfg, p))}
                           for p in ex["palettes"]},
                 views={}, anims={a: dict(frames=aa["frames"], tread=aa["tread"]) for a, aa in anims.items()})
    for v, vv in views.items():
        h, w = spr[(v, vv["dirs_deg"][0], "drive", 0)].shape
        W, H, (ox, oy) = view_canvas(cfg, vv["pitch_deg"])
        atlas["views"][v] = dict(pitch_deg=vv["pitch_deg"], dirs_deg=vv["dirs_deg"], frame_w=w, frame_h=h,
                                 pivot=[ox, oy], note="pivot = ground point under the robot centre, same for every frame")
    for pal in ex["palettes"]:
        pl = lut(cfg, pal)
        d0 = os.path.join(root, "sheets", pal)
        os.makedirs(d0, exist_ok=True)
        for v, vv in views.items():
            for a, aa in anims.items():
                grid = np.concatenate([np.concatenate([spr[(v, d, a, f)] for f in range(aa["frames"])], 1)
                                       for d in vv["dirs_deg"]], 0)
                indexed(grid, pl).save(os.path.join(d0, f"{v}_{a}.png"), transparency=0)
                indexed(grid, pl, sc).save(os.path.join(d0, f"{v}_{a}@{sc}x.png"), transparency=0)
    for pal in ex["seq_palettes"]:
        for v, vv in views.items():
            for d in vv["dirs_deg"]:
                for a, aa in anims.items():
                    d1 = os.path.join(root, "seq", pal, f"{v}_{dirname(d)}", a)
                    os.makedirs(d1, exist_ok=True)
                    for f in range(aa["frames"]):
                        im = colorize(cfg, np.kron(spr[(v, d, a, f)], np.ones((sc, sc), np.uint8)), pal)
                        Image.fromarray(im).save(os.path.join(d1, f"{f:04d}.png"))
    pl = lut(cfg, ex["gif_palette"])
    gifs_ = {}
    for v, vv in views.items():
        for d in vv["dirs_deg"]:
            for a, aa in anims.items():
                d2 = os.path.join(root, "gif")
                os.makedirs(d2, exist_ok=True)
                fr = [indexed(spr[(v, d, a, f)], pl, sc) for f in range(aa["frames"])]
                name = f"{v}_{dirname(d)}_{a}.gif"
                fr[0].save(os.path.join(d2, name), save_all=True, append_images=fr[1:], duration=round(1000 / ex["fps"]),
                           loop=0, transparency=0, disposal=2)
                gifs_.setdefault(v, {}).setdefault(a, []).append((d, f"gif/{name}"))
    with open(os.path.join(root, "atlas.json"), "w") as f:
        json.dump(atlas, f, indent=1)
    gallery(root, atlas, gifs_)
    print(f"{root}: {len(jobs)} Sprites, Paletten {ex['palettes']}")
    return root


def gallery(root, atlas, gifs_):
    """index.html: alle Animationen als GIF, Grund umschaltbar (hell / dunkel / Maker Night)."""
    rows = []
    for v, by_anim in gifs_.items():
        rows.append(f"<h2>{v} <small>pitch {atlas['views'][v]['pitch_deg']}&deg;</small></h2>")
        for a, items in by_anim.items():
            imgs = "".join(f'<figure><img src="{p}"><figcaption>{d:g}&deg;</figcaption></figure>' for d, p in items)
            rows.append(f'<div class="row"><h3>{a}</h3>{imgs}</div>')
    html = f"""<!doctype html><meta charset="utf-8"><title>Zumo Sprites {atlas['variant']}</title>
<style>
:root{{--bg:#2B2A36;--fg:#C9C6D6}} body{{background:var(--bg);color:var(--fg);font:14px/1.4 system-ui;margin:24px}}
body.light{{--bg:#E9E6F2;--fg:#3a3850}} body.night{{--bg:#0A0711;--fg:#AE93EE}}
img{{image-rendering:pixelated;display:block}} figure{{margin:0 10px 10px 0;display:inline-block;vertical-align:bottom}}
figcaption{{font-size:11px;opacity:.6}} .row{{display:flex;flex-wrap:wrap;align-items:flex-end;gap:4px}}
.row h3{{width:100%;margin:12px 0 4px;font-size:13px}} button{{margin-right:6px}}
</style>
<h1>Zumo Sprites {atlas['variant']} <small>{atlas['label']}, {atlas['mm_per_px']} mm/px, {atlas['fps']} fps</small></h1>
<p><button onclick="document.body.className=''">dunkel</button><button onclick="document.body.className='light'">hell</button>
<button onclick="document.body.className='night'">Maker Night</button></p>
{''.join(rows)}"""
    with open(os.path.join(root, "index.html"), "w") as f:
        f.write(html)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sheet"
    code = next((a for a in sys.argv[2:] if not a.startswith("-")), None)
    cfg = load(variant=code)
    if cmd == "mesh":
        mesh(cfg)
    elif cmd == "test":
        sys.exit(0 if selftest(cfg) else 1)
    elif cmd == "export":
        p = export(cfg)
        if "--no-open" not in sys.argv:
            subprocess.run(["open", os.path.join(p, "index.html")])
    elif cmd == "look":
        p = look(cfg)
        if "--no-open" not in sys.argv:
            subprocess.run(["open", p])
    elif cmd == "eyes":
        p = eyes_sheet(cfg)
        if "--no-open" not in sys.argv:
            subprocess.run(["open", p])
    elif cmd == "variants":
        p = variants(cfg)
        if "--no-open" not in sys.argv:
            subprocess.run(["open", p])
    elif cmd == "sheet":
        p = sheet(cfg)
        gifs(cfg, [("top", 90, "drive"), ("side", 0, "drive"), ("tq", 315, "drive"), ("tq", 270, "idle")])
        if "--no-open" not in sys.argv:
            subprocess.run(["open", p])
    else:
        sys.exit(__doc__)
