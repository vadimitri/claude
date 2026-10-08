#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""Echte Fotos der gedruckten Plakate → kickoff_loop/photos/aligned/NN.png, die Platten der Foto-Phase im Video
(kickoff_loop_video.photo_plate nimmt sie statt der Simulation, sobald es sie gibt).

  uv run src/kickoff_loop_photos.py [foto...]     Standard: kickoff_loop/photos/raw/*.JPG
  uv run src/kickoff_loop_photos.py test          Selbsttest Farbausgleich (synthetisch, ~2 s)

Schritte (Stellschrauben in loop.toml [photos], Befund in kickoff_loop/CLAUDE.md "Campus-Fotos"):
  Erkennen  Nummer + Lage je Foto aus den Druckmarken (kickoff_loop_marks.detect). Ohne Marken-Treffer (dunkles Plakat,
            gewoelbt an der Litfasssaeule): Lage grob aus dem QR, Nummer = der Render, der am besten korreliert, Lage
            fein per ECC am Render (identify). Ergebnis je Datei gemerkt in photos/detect.json.
  Auswahl   je Plakat das Foto mit der besten Passung am Render (NCC: Schaerfe, Spiegelungen, Verdecktes), abzueglich
            der Flaeche der Platte, die das Foto nicht abdeckt. [photos].pick uebersteuert je Plakat.
  Farbe     Plakat soll im Foto aussehen wie digital: im linearen Licht render ~ (foto^g) @ A + b, gemessen am Inneren
            des Plakats (ohne Druckrand-Welle), robust (Spiegelungen zaehlen kaum). Die Matrix kennt nur Plakatfarben,
            auf die Wand hochgerechnet kippt sie (Befund: Holztuer → knallrot, Wand → gruen). Die Umgebung bekommt
            deshalb nur, was die Matrix auf der Grauachse tut (Weissabgleich, Schwarzpunkt, Belichtung je Kanal),
            weicher Uebergang am Plakatrand, Lichter mit Schulter, dann nur abgedunkelt auf surround_luma.
  Ausgabe   aligned/NN.png (Platte, Plakat mittig in Vorschaugroesse), photos/plates.png (alle 64 Platten: Foto oder
            Simulation), photos/colors.png (Plakat im Foto | digital), photos/report.txt.
"""
import glob
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

import kickoff_loop as KL

DIR = os.path.join(KL.PROJECT, "photos")
CACHE = os.path.join(DIR, "detect.json")
FIT_STEP_PX = 8                   # Farbausgleich: ein Messpunkt alle 8 Plattenpixel (2 Zellen), ~25000 Punkte je Plakat
IRLS_ITER = 6                     # robuste Anpassung: so oft neu gewichten (Cauchy), danach aendert sich nichts mehr
WORKERS = 6                       # ein 24-MP-Foto braucht in der Spitze ~0.8 GB
STRIP = 256                       # Zeilen je Streifen beim Umrechnen der Platte (~40 MB float statt ~500 MB)
ID_BLUR_CELLS = 1.0               # identify: Graubilder in 1 px/Zelle vor dem Vergleich so weichzeichnen (Bayer-Korn)
ID_MIN_NCC = 0.5                  # ... beste Korrelation muss darueber liegen (Befund: getroffen 0.7-0.9, Rest < 0.4)
ID_MIN_GAP = 0.1                  # ... und so weit vor der zweitbesten (sonst ist die Nummer geraten)
EXPO_STEP_PX = 8                  # Belichtung der Wand: auf jedem 8. Pixel gemessen (Mittelwert reicht)
EXPO_BISECT = 20                  # Halbierungen fuer den Wand-Faktor
PRINT_TO_PLATE = 3                # Montage: print/NN.png (3504 x 4956) = 3 x Plakat in der Platte (1168 x 1652)
MONTAGE_BLUR_PX = (0, 0.5, 1, 1.5, 2, 3, 4)   # Montage: Schaerfe des echten Plakats aus diesen Gauss-Sigmas (Plattenpixel)
MONTAGE_LIGHT_CELLS = 30          # Montage: Lichtverlauf = Foto / Modell, so weich (~1/9 Plakatbreite: Verlauf, keine Details)
SHEET_MAX_CELLS = 12              # Papierkante: Druckerrand hoechstens so breit (A3 ~4-6 mm = 4-6 Zellen, A4 verkleinert mehr)
SHEET_MIN_STEP = 0.04             # ... schwaecherer Sprung (dE OK) = keine Kante sichtbar (Rahmen, Rand verdeckt): Kante am Plakat
THUMB = 12                        # Kandidaten-Vorschau: Platte 2446 x 4348 / 12 = 204 x 362 (Auswahl-Bogen, Wandvergleich)
WALL_BLUR_PX = 12                 # Wandvergleich auf der Vorschau weichzeichnen (~36 Zellen): Parallaxe derselben Wand (Plakat in
                                  # der Hand, Hintergrund wandert) zaehlt nicht, Licht + Farbe der Umgebung schon


def lin(u8):
    x = np.asarray(u8, np.float32) / 255
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def srgb(l):
    l = np.clip(l, 0, 1)
    return np.round(np.where(l <= 0.0031308, l * 12.92, 1.055 * l ** (1 / 2.4) - 0.055) * 255).astype(np.uint8)


def oklab(l):
    return np.cbrt(np.clip(l, 0, None) @ KL._M1.T) @ KL._M2.T


def check(cfg):
    ph = cfg.get("photos")
    assert ph, "loop.toml: Abschnitt [photos] fehlt"
    need = ["fit_edge_cells", "fit_blur_cells", "fit_gammas", "fit_robust_de", "blend_cells", "wall_feather_cells",
            "wall_knee", "wall_min_gain", "wall_wb_max", "wall_black_max", "pick_cover_weight", "pick", "prefer_from",
            "variant_de", "number", "poster_match_frac", "wall_edit", "composite", "corners", "aligned_dir",
            "poster_mode", "poster_light_frac", "poster_tint_frac", "poster_fade_cells", "shot_wb_frac",
            "shot_expo_frac", "shot_paper_luma", "shot_chroma", "shot_contrast"]
    miss = [k for k in need if k not in ph]
    assert not miss, f"loop.toml [photos]: es fehlt {miss}"
    assert ph["poster_mode"] in ("rgb", "light"), "[photos].poster_mode: rgb (F4/F5) | light (MC: Licht aus dem Foto)"
    bad = [k for k in ph["corners"] if k not in ph["number"]]
    assert not bad, f"[photos].corners {bad}: braucht auch eine Nummer in [photos].number"
    assert 0 < ph["wall_knee"] < 1, "[photos].wall_knee: Knie der Lichter-Schulter, zwischen 0 und 1 (lineares Licht)"
    return ph


# ---------------------------------------------------------------- Erkennen

def _key(p, cfg):
    """Cache-Schluessel je Foto: Datei + erzwungene Nummer ([photos].number), eine neue Zuordnung erkennt neu."""
    st = os.stat(p)
    name = os.path.splitext(os.path.basename(p))[0]
    n, c = cfg["photos"]["number"].get(name), cfg["photos"]["corners"].get(name)
    return f"{os.path.basename(p)}:{st.st_size}:{int(st.st_mtime)}" + (f":n{n}" if n else "") + (f":c{c}" if c else "")


def _poster_cells(photo, H, grid):
    """Plakat aus dem Foto in 1 px pro Zelle (H: Zellen → Fotopixel), Graubild."""
    import cv2
    A = np.array([[1, 0, 0.5], [0, 1, 0.5], [0, 0, 1]])             # Pixel → Zellmitte
    g = cv2.cvtColor(photo, cv2.COLOR_RGB2GRAY).astype(np.float32)
    return cv2.warpPerspective(g, H @ A, (grid[1], grid[0]), flags=cv2.INTER_AREA | cv2.WARP_INVERSE_MAP)


def _ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-9))


def identify(photo, cfg, n=None):
    """Fallback ohne Marken: grobe Lage aus dem QR (kickoff_loop_marks.coarse), Nummer = bester Render im Vergleich
    bei 1 px pro Zelle, Lage fein per ECC am ganzen Render (marks.polish). dict wie marks.detect oder dict(error=).
    n: Nummer steht fest ([photos].number), nur die Lage wird gesucht, ohne Schwellen."""
    import cv2
    import kickoff_loop_marks as M
    q = KL.PREVIEW_CELL_PX
    renders = [KL.frame(cfg, i) for i in range(KL.posters(cfg))]
    grid = (renders[0].shape[0] // q, renders[0].shape[1] // q)
    small = [gaussian_filter(cv2.resize(cv2.cvtColor(r, cv2.COLOR_RGB2GRAY), grid[::-1], interpolation=cv2.INTER_AREA)
                             .astype(np.float32), ID_BLUR_CELLS) for r in renders]
    best = None
    for H in M.coarse(photo):
        seen = gaussian_filter(_poster_cells(photo, H, grid), ID_BLUR_CELLS)
        z = sorted(((_ncc(seen, s), i) for i, s in enumerate(small) if n is None or i == n - 1), reverse=True)
        z.append((-1.0, -1))                                  # n fest: kein zweitbester
        if best is None or z[0][0] > best[0]:
            best = (z[0][0], z[1][0], z[0][1], H)
    if best is None:
        return dict(error="kein QR gefunden (grobe Lage fehlt)")
    cc, cc2, i, H = best
    if n is None and (cc < ID_MIN_NCC or cc - cc2 < ID_MIN_GAP):    # n fest: Vadim weiss es (19 gewoelbt: NCC klein)
        return dict(error=f"ohne Marken keine sichere Nummer (Render {i + 1}: {cc:.2f}, naechster {cc2:.2f})")
    H, pcc, took = M.polish(photo, H, renders[i])
    return dict(n=i + 1, z=0.0, z2=0.0, H=H, fields=0, polish_cc=pcc, polished=took, by="number" if n else "render",
                ncc_id=cc, ncc_id2=cc2)


def _detect(p):
    import kickoff_loop_marks as M
    cfg = KL.load()
    name = os.path.splitext(os.path.basename(p))[0]
    n, corners = cfg["photos"]["number"].get(name), cfg["photos"]["corners"].get(name)
    try:
        if corners:                                           # Lage von Hand: Ecken der Druckflaeche (19, gewoelbt)
            import cv2
            gw, gh = (d // KL.PREVIEW_CELL_PX for d in KL.S.SIZES[KL.PREVIEW][:2])
            H = cv2.getPerspectiveTransform(np.float32([[0, 0], [gw, 0], [gw, gh], [0, gh]]), np.float32(corners))
            return _key(p, cfg), dict(n=n, H=H.tolist(), by="corners")
        photo = M.load_photo(p)
        r = identify(photo, cfg, n) if n else M.detect(photo, cfg)
        if "error" in r and not n:
            r2 = identify(photo, cfg)
            r = r2 if "n" in r2 else dict(error=f"{r['error']}; {r2['error']}")
    except Exception as e:                                    # ein kaputtes Foto haelt den Lauf nicht an
        r = dict(error=repr(e))
    return _key(p, cfg), {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items() if k != "H_marks"}


def detect_all(paths, cfg):
    """Nummer + Lage je Foto, gemerkt in photos/detect.json (neue Fotos ~4 s, bekannte nichts)."""
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [p for p in paths if _key(p, cfg) not in cache]
    if todo:
        print(f"erkenne {len(todo)} Fotos ...", flush=True)
        with Pool(WORKERS) as pool:
            for k, r in pool.imap_unordered(_detect, todo):
                cache[k] = r
        os.makedirs(DIR, exist_ok=True)
        json.dump(cache, open(CACHE, "w"), indent=0)
    return {p: cache[_key(p, cfg)] for p in paths}


# ---------------------------------------------------------------- Farbe

def inner_mask(shape, cfg):
    """Inneres des Plakats fuer die Farbmessung: ohne den Druckrand (Welle bis edge_cells x (1 + amp))."""
    ph, pw = shape[:2]
    e = round(cfg["photos"]["fit_edge_cells"] * KL.PREVIEW_CELL_PX)
    m = np.zeros((ph, pw), bool)
    m[e:ph - e, e:pw - e] = True
    return m


def fit_color(plate_poster, render, cfg):
    """Farbausgleich Foto → digital am Plakat. Beide weichgezeichnet (Bayer-Korn, Marken, Restversatz weg), im
    linearen Licht: render ~ (foto^g) @ A + b. g aus einem Raster, A und b robust (Cauchy-IRLS: Spiegelungen,
    Blendlicht, Verdecktes zaehlen kaum). Zurueck: dict(g, A, b, de_before, de_after) mit dE OK (Median, p90)."""
    ph = cfg["photos"]
    s = ph["fit_blur_cells"] * KL.PREVIEW_CELL_PX
    P = np.stack([gaussian_filter(c, s) for c in lin(plate_poster).transpose(2, 0, 1)], -1)
    R = np.stack([gaussian_filter(c, s) for c in lin(render).transpose(2, 0, 1)], -1)
    m = inner_mask(render.shape, cfg)[::FIT_STEP_PX, ::FIT_STEP_PX]
    P, R = P[::FIT_STEP_PX, ::FIT_STEP_PX][m], R[::FIT_STEP_PX, ::FIT_STEP_PX][m]
    Rl = oklab(R)
    best = None
    for g in ph["fit_gammas"]:
        X = np.c_[P ** g, np.ones(len(P))]
        w = np.ones(len(P))
        for _ in range(IRLS_ITER):
            W = X * w[:, None]
            coef = np.linalg.lstsq(W.T @ X, W.T @ R, rcond=None)[0]
            de = np.linalg.norm(oklab(X @ coef) - Rl, axis=1)
            w = 1 / (1 + (de / ph["fit_robust_de"]) ** 2)
        if best is None or np.median(de) < best["de_after"][0]:
            best = dict(g=g, A=coef[:3], b=coef[3], de_after=(float(np.median(de)), float(np.percentile(de, 90))))
    d0 = np.linalg.norm(oklab(P) - Rl, axis=1)
    best["de_before"] = (float(np.median(d0)), float(np.percentile(d0, 90)))
    return best


def gray_axis(f, wb_max=None, black_max=None):
    """Was die Plakat-Matrix auf der Grauachse tut, als Kanal-fuer-Kanal-Abbildung (Weissabgleich, Schwarzpunkt,
    Belichtung): Fotofarben, die die Matrix auf Grau g abbildet, liegen auf x^g = g * u + v (u = 1 A^-1, v = -b A^-1).
    Die Wand bekommt wall_c = (x_c^g - v_c) / u_c: auf Grau exakt wie das Plakat, aber keine Buntheit dazu.
    wb_max/black_max begrenzen Weissabgleich und Schwarzpunkt (sonst kippt die Wand, wo das Plakat kaum Grau hat)."""
    Ai = np.linalg.inv(f["A"])
    u, v = np.ones(3) @ Ai, -np.asarray(f["b"]) @ Ai
    if (u <= 0).any():                                        # Matrix dreht die Grauachse um: nur Belichtung
        u, v = np.full(3, u.mean() if u.mean() > 0 else 1.0), np.zeros(3)
    if wb_max:                                                # Plakat fast ohne Grau (35: nur Rot/Weiss): die Grauachse
        m = np.exp(np.log(u).mean())                          # ist schlecht bestimmt, die Wand kippte magenta/blau.
        u = m * np.clip(u / m, 1 / wb_max, wb_max)            # Kanalfaktoren hoechstens wb_max auseinander
        v = np.clip(v, -black_max, black_max)
    return u, v


def shoulder(x, k):
    """Lichter weich in [k, 1) statt hart bei 1 (C1-stetig am Knie k, lineares Licht)."""
    return np.where(x <= k, x, k + (1 - k) * (1 - np.exp(-(np.maximum(x, k) - k) / (1 - k))))


def _ring(shape, rect, px):
    """1 im Plakat (rect = x0, y0, w, h), faellt ausserhalb mit smoothstep ueber px Pixel auf 0."""
    H, W = shape
    x0, y0, w, h = rect
    ys, xs = np.arange(H, dtype=np.float32), np.arange(W, dtype=np.float32)
    dy = np.maximum(np.maximum(y0 - ys, ys - (y0 + h - 1)), 0)[:, None]
    dx = np.maximum(np.maximum(x0 - xs, xs - (x0 + w - 1)), 0)[None, :]
    t = np.clip(1 - np.sqrt(dx * dx + dy * dy) / max(px, 1), 0, 1)
    return t * t * (3 - 2 * t)


def grade(plate, f, rect, cfg, q=KL.PREVIEW_CELL_PX):
    """Platte (uint8) → fertige Platte: im Plakat die volle Korrektur, aussen nur die Grauachse (gray_axis) mit
    Lichter-Schulter; weicher Uebergang ueber blend_cells. Die Wand wird danach mit einem Faktor s <= 1 auf
    surround_luma abgedunkelt (wie kickoff_loop_video.grade, nur nie heller, nie unter wall_min_gain und nie das
    Plakat: s laeuft ueber wall_feather_cells von 1 am Plakat auf s). Zurueck: (Platte, s).
    poster_match_frac mischt die volle Korrektur im Plakat ein (1 = wie digital, 0 = das ganze Foto bekommt nur die
    Grauachse: ein Weissabgleich + Belichtung fuer alles, wie eine normale Fotokorrektur; Vadim 7.10.: "sieht aus
    wie digital", "der Hintergrund ist immer so veraendert"). q: Pixel je Zelle (Vorschau: / THUMB)."""
    ph = cfg["photos"]
    if ph["poster_mode"] == "light":
        return grade_light(plate, f, rect, ph, q), 1.0
    if not ph["wall_edit"]:
        return grade_poster_only(plate, f, rect, ph["poster_match_frac"], q), 1.0
    mc = ph["poster_match_frac"] * _ring(plate.shape[:2], rect, ph["blend_cells"] * q)
    u, v = gray_axis(f, ph["wall_wb_max"], ph["wall_black_max"])
    me = _ring(plate.shape[:2], rect, ph["wall_feather_cells"] * q)
    hole = np.ones(plate.shape[:2], bool)
    x0, y0, w, h = rect
    hole[y0:y0 + h, x0:x0 + w] = False

    def wall(x):
        return (lin(x) ** f["g"] - v) / u

    # Faktor s: Mittel der kodierten Helligkeit ausserhalb des Plakats (wie video.grade) = surround_luma, s <= 1
    sub = (slice(None, None, EXPO_STEP_PX),) * 2
    w_s, me_s, mc_s, keep = wall(plate[sub]), me[sub][..., None], mc[sub][..., None], hole[sub]

    def luma(s):
        e = s + (1 - s) * me_s
        out = mc_s * (lin(plate[sub]) ** f["g"] @ f["A"] + f["b"]) + (1 - mc_s) * shoulder(e * w_s, ph["wall_knee"])
        return float((srgb(out)[keep].astype(np.float32) / 255 @ KL.LUMA).mean())

    target, s = cfg["video"]["surround_luma"], 1.0
    if luma(1.0) > target:
        lo, hi = ph["wall_min_gain"], 1.0
        for _ in range(EXPO_BISECT):
            s = (lo + hi) / 2
            lo, hi = (lo, s) if luma(s) > target else (s, hi)  # zu hell → kleiner; unerreichbar → wall_min_gain
    out = np.empty_like(plate)
    for y in range(0, plate.shape[0], STRIP):
        sl = slice(y, y + STRIP)
        x = lin(plate[sl]) ** f["g"]
        e = (s + (1 - s) * me[sl])[..., None]
        out[sl] = srgb(mc[sl][..., None] * (x @ f["A"] + f["b"])
                       + (1 - mc[sl][..., None]) * shoulder(e * (x - v) / u, ph["wall_knee"]))
    return out, s


def sheet(plate, rect, q=KL.PREVIEW_CELL_PX):
    """Papierbogen um das Plakat (x0, y0, w, h): der Druckerrand ist dasselbe Blatt, seine Kante eine echte Kante im
    Foto. Je Seite: Profil nach aussen (Median ueber die mittleren 80 % der Seite, OKLab), Kante = staerkster Sprung
    bis SHEET_MAX_CELLS. Seite ohne sichtbare Kante (schwaecher als SHEET_MIN_STEP: Papier so hell wie die Wand) bekommt
    die Breite der Gegenseite (der Druck liegt mittig auf dem Blatt), sonst den Median der gefundenen, sonst 0 (Rahmen).
    Befund 7.10.: 21 oben Papier = Wand (Sprung 0.012), Kante am Plakat gab eine harte Stufe rohes / korrigiertes Papier."""
    x0, y0, w, h = rect
    n, k = max(int(SHEET_MAX_CELLS * q), 3), max(int(round(q / 2)), 1)    # Suchweite, halbe Sprungbreite (Pixel)
    sides = (plate[y0 - n:y0, x0 + w // 10:x0 + w - w // 10][::-1],                # oben, nach aussen geordnet
             plate[y0 + h:y0 + h + n, x0 + w // 10:x0 + w - w // 10],              # unten
             plate[y0 + h // 10:y0 + h - h // 10, x0 - n:x0][:, ::-1].transpose(1, 0, 2),   # links
             plate[y0 + h // 10:y0 + h - h // 10, x0 + w:x0 + w + n].transpose(1, 0, 2))    # rechts
    out = []
    for strip in sides:
        prof = np.median(oklab(lin(strip)), axis=1)                           # je Abstand eine Farbe
        step = np.linalg.norm(prof[2 * k:] - prof[:-2 * k], axis=1)           # Sprung zwischen d - k und d + k
        top = np.flatnonzero(step >= step.max() - 1e-6) if len(step) else []   # scharfe Kante: Plateau, dessen Mitte
        out.append(int((top[0] + top[-1]) / 2 + k + 0.5) if len(step) and step.max() >= SHEET_MIN_STEP else None)
    seen = [d for d in out if d is not None]
    t, b, l, r = (d if d is not None else out[i ^ 1] if out[i ^ 1] is not None else int(np.median(seen)) if seen else 0
                  for i, d in enumerate(out))                             # Reihenfolge oben, unten, links, rechts: i ^ 1 = Gegenseite
    return x0 - l, y0 - t, w + l + r, h + t + b


def grade_poster_only(plate, f, rect, frac, q=KL.PREVIEW_CELL_PX):
    """[photos].wall_edit = false (F4, Vadim 7.10.: "die Edits auf dem Plakat, den Rest des Fotos natuerlich, ohne dass
    man eine Maske sieht", "super erkennbar, Saturation stimmt, aber natuerlicher"): Wand bleibt das Kamera-JPG, der
    ganze Papierbogen (Plakat + Druckerrand, sheet) bekommt die Plakat-Matrix zu frac. Die Maskenkante liegt auf der
    Papierkante, einer echten Kante im Foto (1 Zelle weich, nach innen), deshalb sieht man keine Maske.
    Befund 7.10.: Korrektur relativ zum Foto-Weiss (Matrix, dann zurueck durch ihre Grauachse) kippt bunte Plakate
    (16 schwarz, 35 gelbgruen, 59 rot: Grauachse schlecht bestimmt), aufs gemessene Papierweiss skaliert wird es trueb."""
    x0, y0, w, h = sheet(plate, rect, q)
    e = max(int(round(q)), 1)
    mc = frac * _ring(plate.shape[:2], (x0 + e, y0 + e, w - 2 * e, h - 2 * e), e)
    out = np.empty_like(plate)
    for y in range(0, plate.shape[0], STRIP):
        sl = slice(y, y + STRIP)
        x, m = lin(plate[sl]), mc[sl][..., None]
        out[sl] = srgb(m * np.clip(x ** f["g"] @ f["A"] + f["b"], 0, None) + (1 - m) * x)
    return out


_M2I, _M1I = np.linalg.inv(KL._M2), np.linalg.inv(KL._M1)
LOOK_PIVOT_L = 0.6                # S-Kurve dreht um Mittelgrau: sRGB 128 = linear 0.216 = OKLab L 0.6


def unlab(lab):
    """OKLab → linear (Umkehrung von oklab)."""
    return np.clip(lab @ _M2I.T, 0, None) ** 3 @ _M1I.T


def _inset(shape, rect, px):
    """0 auf dem Plakatrand und ausserhalb, steigt nach innen mit smoothstep ueber px Pixel auf 1."""
    x0, y0, w, h = rect
    ys, xs = np.arange(shape[0], dtype=np.float32), np.arange(shape[1], dtype=np.float32)
    dy = np.minimum(ys - y0, y0 + h - 1 - ys)[:, None]
    dx = np.minimum(xs - x0, x0 + w - 1 - xs)[None, :]
    t = np.clip(np.minimum(dx, dy) / max(px, 1), 0, 1)
    return t * t * (3 - 2 * t)


def paper_white(plate, rect, f, ph, q=KL.PREVIEW_CELL_PX):
    """Papierweiss im Foto (linear): Median des unbedruckten Druckerrands zwischen Bogenkante (sheet) und Druck, die
    Graukarte in jedem Foto. Ohne sichtbaren Rand (Rahmen): was die Plakat-Matrix auf Weiss abbildet (gray_axis).
    Befund 8.10.: das Papier ist im Foto nie neutral (06 im Schatten blaeulich, 01 hinter Glas beige, 20 lila, 44
    ausgefressen weiss): die Kamera hat die Szene abgeglichen, nicht das Papier."""
    sx, sy, sw, sh = sheet(plate, rect, q)
    x0, y0, w, h = rect
    e = max(int(round(q)), 1)
    m = np.zeros(plate.shape[:2], bool)
    m[sy + e:sy + sh - e, sx + e:sx + sw - e] = True
    m[y0:y0 + h, x0:x0 + w] = False
    if m.any():
        return np.median(lin(plate[m]), 0)
    u, v = gray_axis(f, ph["wall_wb_max"], ph["wall_black_max"])
    return np.clip(u + v, 1e-3, 1) ** (1 / f["g"])


def grade_light(plate, f, rect, ph, q=KL.PREVIEW_CELL_PX):
    """[photos].poster_mode = "light" (MC, Vadim 8.10.: die Match Cuts sehen aus wie "digital reingecutted").
    Befund am Bogen: rgb (F4/F5) uebernimmt Weiss und Schwarz vom Render, das Plakat ist heller und kontrastreicher
    als alles andere im Foto (Leuchtkasten), und der mitkorrigierte Papierrand kippt (20 rosa). Hier:
    1. Plakat: Farbton + Buntheit Richtung digital (poster_match_frac), die Helligkeit bleibt die des Fotos
       (poster_light_frac 0: Licht, Schatten, Spiegelung, Papierkontrast echt; 1: wie digital). Die digitale Farbe
       bekommt den Farbstich des Lichts im Foto (Papierweiss, poster_tint_frac). Laeuft vom Plakatrand ueber
       poster_fade_cells nach innen ein (dort druckt der Lichtabfall ohnehin ins Papier), der Papierrand bleibt roh.
    2. Ganzes Foto ohne Maske (alles im Bild bekommt dasselbe, wie ein Grade je Einstellung): Weissabgleich und
       Belichtung am Papierweiss (shot_wb_frac, shot_expo_frac → shot_paper_luma: die Plakate sind ueber die Schnitte
       gleich hell), Buntheit shot_chroma, S-Kurve shot_contrast."""
    pw = paper_white(plate, rect, f, ph, q)
    y = float(pw @ KL.LUMA)
    tint = (pw / y) ** ph["poster_tint_frac"]
    gain = (y / pw) ** ph["shot_wb_frac"] * (ph["shot_paper_luma"] / y) ** ph["shot_expo_frac"]
    m = _inset(plate.shape[:2], rect, ph["poster_fade_cells"] * q)
    out = np.empty_like(plate)
    for r in range(0, plate.shape[0], STRIP):
        sl = slice(r, r + STRIP)
        x = lin(plate[sl])
        mm = m[sl][..., None]
        lift = (lambda v: shoulder(v, ph["wall_knee"])) if (gain > 1).any() else (lambda v: v)   # aufhellen ohne
        lb = oklab(lift(x * gain))                                         # Ausfressen (Befund 8.10.: 31 Himmel weiss)
        lt = oklab(lift(np.clip(x ** f["g"] @ f["A"] + f["b"], 0, None) * tint * gain))
        L = lb[..., :1] + mm * ph["poster_light_frac"] * (lt[..., :1] - lb[..., :1])
        ab = lb[..., 1:] + mm * ph["poster_match_frac"] * (lt[..., 1:] * L / np.maximum(lt[..., :1], 1e-4) - lb[..., 1:])
        L = np.clip(L, 0, 1)
        L = L + ph["shot_contrast"] * (L - LOOK_PIVOT_L) * 4 * L * (1 - L)   # Enden 0 und 1 bleiben stehen
        out[sl] = srgb(unlab(np.concatenate([L, ab * ph["shot_chroma"]], -1)))
    return out


def montage(plate, rect, host, n, cfg):
    """Plakat n in das Foto von Plakat host gesetzt (Vadim 7.10.: 45 nicht nachfotografieren, "Hintergrund, der schon
    benutzt ist, realistisch reinschneiden"): der Druck von n (print/NN.png, mit Druckrand, 3 x Plattengroesse) durch die
    am Foto gemessene Druck- + Kamera-Abbildung (fit_color von host, umgekehrt), dazu Lichtverlauf und Schaerfe des
    echten Plakats im Foto. Wand und Papierrand bleiben das Foto. Rauschen nicht nachgebaut (JPG der R8 ist entrauscht)."""
    x0, y0, pw, ph_ = rect
    crop = plate[y0:y0 + ph_, x0:x0 + pw]
    f = fit_color(crop, KL.frame(cfg, host - 1), cfg)
    Ai = np.linalg.inv(f["A"])

    def shot(k):                                              # Druck von k, wie dieses Foto ihn zeigen wuerde (linear)
        im = Image.open(os.path.join(KL.PROJECT, "print", f"{k:02d}.png")).convert("RGB").reduce(PRINT_TO_PLATE)
        return np.clip((lin(im) - f["b"]) @ Ai, 0, None) ** (1 / f["g"])
    seen, pred = lin(crop) @ KL.LUMA, shot(host) @ KL.LUMA
    m = inner_mask(crop.shape, cfg)
    sig = max(MONTAGE_BLUR_PX, key=lambda s: _ncc(seen[m], gaussian_filter(pred, s)[m]))
    big = MONTAGE_LIGHT_CELLS * KL.PREVIEW_CELL_PX
    light = np.clip(gaussian_filter(seen, big) / np.maximum(gaussian_filter(pred, big), 1e-4), 0.5, 2.0)
    new = np.stack([gaussian_filter(c, sig) if sig else c for c in shot(n).transpose(2, 0, 1)], -1) * light[..., None]
    out = plate.copy()
    out[y0:y0 + ph_, x0:x0 + pw] = srgb(new)
    return out


# ---------------------------------------------------------------- Kandidaten, Auswahl, Ausgabe

def _plate(photo, H, cfg):
    """Entzerrte Platte wie marks.aligned, aber Rand gespiegelt statt wiederholt (wiederholte Randpixel = Streifen).
    Zurueck: (Platte, Anteil des Startausschnitts, der im Foto liegt, Plakat-Rechteck x0, y0, w, h)."""
    import cv2
    import kickoff_loop_video as V
    pw, ph = KL.S.SIZES[KL.PREVIEW][:2]
    PW, PH = V.plate_size(cfg, np.zeros((ph, pw, 3), np.uint8))
    x0, y0 = (PW - pw) // 2, (PH - ph) // 2
    q = KL.PREVIEW_CELL_PX
    A = np.array([[1 / q, 0, (0.5 - x0) / q], [0, 1 / q, (0.5 - y0) / q], [0, 0, 1]])
    T = np.asarray(H) @ A
    plate = cv2.warpPerspective(photo, T, (PW, PH), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                                borderMode=cv2.BORDER_REFLECT_101)
    inside = cv2.warpPerspective(np.ones(photo.shape[:2], np.uint8), T, (PW, PH),
                                 flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP, borderValue=0)
    W, H_ = (int(np.ceil(d / V.scales(cfg, ph)[0])) for d in cfg["video"]["size_px"])   # Startausschnitt, ungedreht:
    cx, cy = (PW - W) // 2, (PH - H_) // 2                    # Abdeckung wie vor dem Drehungsrand der Platte (7.10.),
    return plate, float(inside[cy:cy + H_, cx:cx + W].mean()), (x0, y0, pw, ph)   # sonst kippt die abgenommene Wahl


def _candidate(args):
    """Ein erkanntes Foto → Kennzahlen (Passung, Abdeckung, Farbausgleich), ohne die Platte zu behalten."""
    import kickoff_loop_marks as M
    p, n, H, host = args
    cfg = KL.load()
    plate, cover, (x0, y0, pw, ph_) = _plate(M.load_photo(p), H, cfg)
    if host:
        plate = montage(plate, (x0, y0, pw, ph_), host, n, cfg)
    poster = KL.frame(cfg, n - 1)
    crop = plate[y0:y0 + ph_, x0:x0 + pw]
    m = inner_mask(poster.shape, cfg)
    g = [gaussian_filter(x.astype(np.float32) @ KL.LUMA, M.ALIGN_BLUR_PX) for x in (crop, poster)]
    clip = float(((crop.max(-1) >= 250) & (poster.max(-1) < 240) & m).sum() / m.sum())
    fit = fit_color(crop, poster, cfg)
    thumb, _ = grade(np.asarray(Image.fromarray(plate).reduce(THUMB)), fit, (x0 // THUMB, y0 // THUMB, pw // THUMB,
                     ph_ // THUMB), cfg, KL.PREVIEW_CELL_PX / THUMB)          # Vorschau so gegradet wie im Video
    return dict(path=p, n=n, H=H, host=host, ncc=_ncc(*g), cover=cover, clip=clip, fit=fit, thumb=thumb,
                rect=(x0 // THUMB, y0 // THUMB, pw // THUMB, ph_ // THUMB))


def _name(c):
    return os.path.splitext(os.path.basename(c["path"]))[0]


def pick(cands, cfg):
    """Je Plakat ein Foto: [photos].pick (Dateiname ohne Endung) oder das beste nach NCC - Gewicht x Luecke. Hat ein
    Plakat Fotos ab [photos].prefer_from, zaehlen nur diese (Vadim 7.10.: die A3-Runde hat die besseren Fotos)."""
    ph, best = cfg["photos"], {}
    forced = {int(k): v for k, v in ph["pick"].items()}
    for c in cands:
        c["score"] = c["ncc"] - ph["pick_cover_weight"] * (1 - c["cover"])
        c["rank"] = (_name(c) >= ph["prefer_from"], c["score"])   # ponytail: Namensvergleich, bricht erst beim Ueberlauf IMG_9999
        if c["n"] in forced:
            if _name(c) == forced[c["n"]]:
                best[c["n"]] = c
        elif c["rank"] > best.get(c["n"], {"rank": (False, -9)})["rank"]:
            best[c["n"]] = c
    return best


def _wall(c):
    """Wand der Kandidaten-Vorschau (ohne Plakat), weichgezeichnet, in OKLab, flach (n x 3)."""
    x0, y0, w, h = c["rect"]
    keep = np.ones(c["thumb"].shape[:2], bool)
    keep[y0:y0 + h, x0:x0 + w] = False
    return oklab(np.stack([gaussian_filter(ch, WALL_BLUR_PX) for ch in lin(c["thumb"]).transpose(2, 0, 1)], -1))[keep]


def _wall_de(a, b):
    return float(np.median(np.linalg.norm(a - b, axis=1)))


def variants(cands, chosen, cfg):
    """Je Plakat die deutlich verschiedenen Fotos (andere Wand, anderes Licht, anderer Ausschnitt): Gruppen nach
    Wand-Abstand (Median dE OK > [photos].variant_de zum Besten jeder Gruppe = neue Gruppe), je Gruppe das beste.
    Befund 7.10.: Grau-Korrelation trennt nicht (Serienbild 0.33-0.68, andere Szene 0-0.69), der Farbabstand schon
    (Serienbild 0.005-0.05, andere Szene 0.07-0.14). Nur aus der Charge, aus der gewaehlt wird (prefer_from), nicht
    fuer Plakate mit [photos].pick. Zurueck {n: [Vertreter, bestes zuerst]}, nur Plakate mit >= 2 Gruppen."""
    ph, out = cfg["photos"], {}
    forced = {int(k) for k in ph["pick"]}
    for n, best in chosen.items():
        if n in forced:
            continue
        pool = sorted((c for c in cands if c["n"] == n and c["rank"][0] == best["rank"][0]), key=lambda c: -c["score"])
        reps = []
        for c in pool:
            w = _wall(c)
            if all(_wall_de(w, r) > ph["variant_de"] for _, r in reps):
                reps.append((c, w))
        if len(reps) > 1:
            out[n] = [c for c, _ in reps]
    return out


def choice_sheet(groups, out_dir):
    """auswahl.png: je Plakat mit deutlich verschiedenen Fotos eine Zeile, je Gruppe das beste Foto (gegradet wie im
    Video), das automatisch gewaehlte (erstes) rot umrandet. Andere Wahl: [photos].pick = {NN = "IMG_...."}."""
    path = os.path.join(out_dir, "auswahl.png")
    if not groups:
        if os.path.exists(path):
            os.remove(path)
        return
    th, tw = next(iter(groups.values()))[0]["thumb"].shape[:2]
    lab, gap = 26, 12
    font = ImageFont.load_default(18)
    bw, bh, per = max(len(g) for g in groups.values()) * (tw + gap) + 3 * gap, th + lab + gap, 3   # 3 Plakate je Zeile
    sheet = Image.new("RGB", (per * bw, -(-len(groups) // per) * bh + gap), "white")
    d = ImageDraw.Draw(sheet)
    for b, n in enumerate(sorted(groups)):
        for i, c in enumerate(groups[n]):
            x, y = gap + (b % per) * bw + i * (tw + gap), gap + (b // per) * bh
            sheet.paste(Image.fromarray(c["thumb"]), (x, y + lab))
            d.text((x, y + 2), f"{n:02d}  {_name(c)}{'  auto' if i == 0 else ''}", fill="black", font=font)
            if i == 0:
                d.rectangle([x - 5, y + lab - 5, x + tw + 4, y + lab + th + 4], outline=(220, 0, 0), width=4)
    sheet.save(path)


def reprint(cfg, chosen):
    """print/nachdruck.pdf: alle Plakate ohne Foto, nur Vorderseite (aus print/NN.png wie kickoff_loop.pdf_files,
    PNG unveraendert). Vadim 7.10.: fehlende Plakate neu drucken und fotografieren. Zurueck: die Nummern."""
    import img2pdf
    miss = [k for k in range(1, KL.posters(cfg) + 1) if k not in chosen]
    path = os.path.join(KL.PROJECT, "print", "nachdruck.pdf")
    if os.path.exists(path):
        os.remove(path)
    if miss:
        lay = img2pdf.get_fixed_dpi_layout_fun((KL.PRINT_DPI, KL.PRINT_DPI))
        with open(path, "wb") as fh:
            fh.write(img2pdf.convert([os.path.join(KL.PROJECT, "print", f"{k:02d}.png") for k in miss], layout_fun=lay))
    return miss


def _build(args):
    """Gewaehltes Foto → <aligned_dir>/NN.png + Vorschaubilder fuer die Boegen. args = (Kandidat, Config-Pfad)."""
    import kickoff_loop_marks as M
    import kickoff_loop_video as V
    c, cfg_path = args
    cfg = KL.load(cfg_path)
    plate, _, rect = _plate(M.load_photo(c["path"]), c["H"], cfg)
    if c["host"]:
        plate = montage(plate, rect, c["host"], c["n"], cfg)
    out, s = grade(plate, c["fit"], rect, cfg)
    path = V.aligned_photo(cfg, c["n"] - 1)
    Image.fromarray(out).save(path)
    x0, y0, pw, ph = rect
    crop = out[y0:y0 + ph, x0:x0 + pw]
    poster = KL.frame(cfg, c["n"] - 1)
    m = inner_mask(poster.shape, cfg)
    sig = cfg["photos"]["fit_blur_cells"] * KL.PREVIEW_CELL_PX
    a, b = (oklab(np.stack([gaussian_filter(ch, sig) for ch in lin(x).transpose(2, 0, 1)], -1)[m][::64])
            for x in (crop, poster))
    de = np.linalg.norm(a - b, axis=1)
    burnt = float(((crop.max(-1) >= 254) & (poster.max(-1) < 245) & m).sum() / m.sum())
    return dict(n=c["n"], s=s, de=(float(np.median(de)), float(np.percentile(de, 90))), burnt=burnt,
                thumb=np.asarray(Image.fromarray(out).reduce(8)), pair=np.hstack([crop, poster])[::4, ::4])


def _sim(k):
    import kickoff_loop_video as V
    cfg = KL.load()
    return k, np.asarray(V.photo_plate(cfg, KL.frame(cfg, k), k).reduce(8))


def sheets(cfg, built, out_dir):
    """plates.png: alle Platten in Reihenfolge (Foto bzw. Simulation, so wie das Video sie zeigt), colors.png: je
    Foto Plakat im Foto | digital."""
    n = KL.posters(cfg)
    with Pool(WORKERS) as pool:
        sims = dict(pool.map(_sim, [k for k in range(n) if k + 1 not in built]))
    tiles = [(built[k + 1]["thumb"], f"{k + 1:02d} Foto") if k + 1 in built else (sims[k], f"{k + 1:02d} Simulation")
             for k in range(n)]
    th, tw = tiles[0][0].shape[:2]
    th, tw = th // 2, tw // 2
    cols = 8
    sheet = Image.new("RGB", (cols * tw, -(-n // cols) * (th + 16)), "white")
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + 16)
        sheet.paste(Image.fromarray(im).reduce(2), (x, y))
        d.text((x + 3, y + th + 2), label, fill="black" if "Foto" in label else "grey")
    sheet.save(os.path.join(out_dir, "plates.png"))
    pairs = [built[k] for k in sorted(built)]
    ph, pw = pairs[0]["pair"].shape[:2]
    cols = 6
    sheet = Image.new("RGB", (cols * (pw + 8), -(-len(pairs) // cols) * (ph + 16)), "white")
    d = ImageDraw.Draw(sheet)
    for i, b in enumerate(pairs):
        x, y = (i % cols) * (pw + 8), (i // cols) * (ph + 16)
        sheet.paste(Image.fromarray(b["pair"]), (x, y))
        d.text((x + 3, y + ph + 2), f"{b['n']:02d} Foto | digital  dE {b['de'][0]:.3f}", fill="black")
    sheet.save(os.path.join(out_dir, "colors.png"))


def report(det, cands, chosen, built, cfg, groups, miss):
    n = KL.posters(cfg)
    L = [f"Campus-Fotos: {len(det)} Fotos, {sum('n' in r for r in det.values())} erkannt "
         f"({sum(r.get('by') == 'render' for r in det.values())} ohne Marken, am Render), "
         f"{len(chosen)}/{n} Plakate mit Foto, Rest Simulation.",
         "Farbe: dE OK am Plakat-Inneren (Median / p90) gegen den Render, Foto roh → fertig. Gut < 0.02 (JND), "
         "ausgefressen = Anteil Pixel, die im Foto weiss sind, digital aber nicht.", "",
         "Nr  Foto      NCC   Abdeckung  dE roh        dE fertig     ausgefressen  Wand x  (Kandidaten)"]
    per = {}
    for c in cands:
        per.setdefault(c["n"], []).append(c)
    for k in sorted(chosen):
        c, b = chosen[k], built[k]
        L.append(f"{k:2d}  {os.path.basename(c['path'])[:8]}  {c['ncc']:.2f}  {c['cover']:.2f}       "
                 f"{c['fit']['de_before'][0]:.3f}/{c['fit']['de_before'][1]:.3f}   {b['de'][0]:.3f}/{b['de'][1]:.3f}   "
                 f"{b['burnt'] * 100:5.2f} %       {b['s']:.2f}   ({len(per[k])})")
    new = sum(c["rank"][0] for c in chosen.values())
    L += ["", f"Aus der Charge ab {cfg['photos']['prefer_from']}: {new}/{len(chosen)}",
          "Montage (Druck ins Foto eines anderen Plakats): " + (", ".join(
              f"{k} in {_name(c)} (zeigt {c['host']})" for k, c in sorted(chosen.items()) if c["host"]) or "keine"),
          "Ohne Foto (print/nachdruck.pdf): " + (" ".join(f"{k}" for k in miss) or "keins"),
          "Deutlich verschiedene Fotos (photos/auswahl.png, auto = erstes): "
          + ("; ".join(f"{k}: " + " ".join(_name(c) for c in g) for k, g in sorted(groups.items())) or "keine"), "",
          "Nicht zugeordnet:"]
    L += [f"  {os.path.basename(p)}: {r['error']}" for p, r in sorted(det.items()) if "error" in r]
    return "\n".join(L)


def choose(paths, cfg):
    """Erkennen, Kandidaten bewerten, je Plakat ein Foto. Zurueck: (Erkennung, Kandidaten, Wahl)."""
    det = detect_all(paths, cfg)
    with Pool(WORKERS) as pool:
        todo = [(p, r["n"], r["H"], None) for p, r in det.items() if "n" in r]
        for n, name in cfg["photos"]["composite"].items():   # Montage: Plakat n ins Foto name (zeigt Plakat host)
            hit = [(p, r) for p, r in det.items() if os.path.basename(p) == name + ".JPG" and "n" in r]
            assert hit, f"[photos].composite {n} = {name}: Foto fehlt oder ist keinem Plakat zugeordnet"
            todo.append((hit[0][0], int(n), hit[0][1]["H"], hit[0][1]["n"]))
        cands = pool.map(_candidate, todo, chunksize=1)
    return det, cands, pick(cands, cfg)


def build(chosen, cfg):
    """Gewaehlte Fotos → photos/<aligned_dir>/NN.png (vorher leeren: nur die gewaehlten bleiben, Rest = Simulation)."""
    out = os.path.join(DIR, cfg["photos"]["aligned_dir"])
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*.png")):
        os.remove(f)
    with Pool(WORKERS) as pool:
        return {b["n"]: b for b in pool.map(_build, [(c, cfg["_src"]) for c in chosen.values()], chunksize=1)}


def grade_variants(paths, cfg, tomls):
    """Match-Cut-Varianten (MC, 8.10.): dieselbe Wahl wie loop.toml, je Review-TOML ein eigener Grade nach
    photos/<aligned_dir>/ (+ plates.png, colors.png dort), die abgenommenen photos/aligned/ bleiben unberuehrt.
    Wahl und Farbmessung haengen nur an loop.toml ([photos] pick/fit_*), deshalb einmal fuer alle."""
    _, _, chosen = choose(paths, cfg)
    for t in tomls:
        vc = KL.load(t)
        check(vc)
        assert vc["photos"]["aligned_dir"] != cfg["photos"]["aligned_dir"], \
            f"{t}: [photos].aligned_dir muss ein eigener Ordner sein (sonst ueberschreibt die Variante photos/aligned/)"
        built = build(chosen, vc)
        out = os.path.join(DIR, vc["photos"]["aligned_dir"])
        sheets(vc, built, out)
        print(f"{t}: {len(built)} Platten → {out}")


def main():
    args = sys.argv[1:]
    if args[:1] == ["test"]:
        sys.exit(selftest())
    tomls = [a for a in args if a.endswith(".toml")]          # Varianten: Erkennen + Auswahl einmal, Grade je Variante
    args = [a for a in args if not a.endswith(".toml")]
    paths = [p for a in args for p in sorted(glob.glob(a)) or [a]] or sorted(glob.glob(os.path.join(DIR, "raw", "*.JPG")))
    cfg = KL.load()
    check(cfg)
    if tomls:
        return grade_variants(paths, cfg, tomls)
    det, cands, chosen = choose(paths, cfg)
    built = build(chosen, cfg)
    sheets(cfg, built, DIR)
    groups = variants(cands, chosen, cfg)
    choice_sheet(groups, DIR)
    rep = report(det, cands, chosen, built, cfg, groups, reprint(cfg, chosen))
    open(os.path.join(DIR, "report.txt"), "w").write(rep + "\n")
    print(rep)


# ---------------------------------------------------------------- Selbsttest

def selftest():
    """Am fertigen Bild: ein synthetisches 'Foto' (Render durch bekannte Druck- + Kamerafehler: Schwarz 3 %, Papier
    88 %, Buntheit 85 %, Farbstich, Belichtung, Tonkurve) an heller Wand muss nach fit_color + grade im Plakat wieder
    wie der Render aussehen (dE < 0.02; Gegenprobe: das rohe Foto liegt weit daneben), die Wand auf surround_luma."""
    cfg = KL.load()
    check(cfg)
    cfg = dict(cfg, photos=dict(cfg["photos"], poster_match_frac=1.0, wall_min_gain=0.5, wall_edit=True))  # wie F2
    poster = KL.frame(cfg, 20)
    L = lin(poster)
    pr = 0.03 + 0.85 * (0.85 * L + 0.15 * (L @ KL.LUMA)[..., None])
    shot = srgb(np.clip(pr * np.array([1.1, 1.0, 0.8]) * 0.9, 0, 1) ** 1.1)
    f = fit_color(shot, poster, cfg)
    pad, (h, w) = 1024, poster.shape[:2]
    m = inner_mask(poster.shape, cfg)
    hole = np.ones((h + 2 * pad, w + 2 * pad), bool)
    hole[pad:pad + h, pad:pad + w] = False
    de = lambda img: float(np.median(np.linalg.norm(oklab(lin(img))[m] - oklab(L)[m], axis=1)))
    res, ok = [], de(shot) > 0.05                                          # Gegenprobe: roh liegt weit daneben
    for grey, want in ((70, "Ziel"), (230, "Untergrenze")):              # erreichbar / zu hell fuer wall_min_gain
        plate = np.full((h + 2 * pad, w + 2 * pad, 3), grey, np.uint8)
        plate[pad:pad + h, pad:pad + w] = shot
        out, s = grade(plate, f, (pad, pad, w, h), cfg)
        wall = float((out[hole].astype(np.float32) / 255 @ KL.LUMA).mean())
        d = de(out[pad:pad + h, pad:pad + w])
        hit = abs(wall - cfg["video"]["surround_luma"]) < 0.01 if want == "Ziel" else (
            abs(s - cfg["photos"]["wall_min_gain"]) < 1e-3 and wall > cfg["video"]["surround_luma"])
        ok &= d < 0.02 and hit
        res.append(f"Wand {grey}: Plakat dE {d:.3f}, Wand {wall:.3f} x{s:.2f} ({want} {'ok' if hit else 'FEHLER'})")
    # Wenig Bearbeitung (poster_match_frac 0, keine Abdunklung): ein Weissabgleich fuer das ganze Foto, eine graue
    # Platte bleibt einheitlich (kein Plakat-Fleck, kein Ring). Gegenprobe volle Korrektur: nicht einheitlich
    lite = dict(cfg, photos=dict(cfg["photos"], poster_match_frac=0.0, wall_min_gain=1.0))
    grey = np.full((h + 2 * pad, w + 2 * pad, 3), 120, np.uint8)
    spread = [int(np.ptp(grade(grey, f, (pad, pad, w, h), c)[0].reshape(-1, 3), axis=0).max()) for c in (lite, cfg)]
    flat = spread[0] == 0 and spread[1] > 0
    ok &= flat
    res.append(f"wenig Bearbeitung {'ok' if flat else 'FEHLER'} (Spanne {spread[0]}, voll {spread[1]})")
    # Nur das Plakat (wall_edit false, F4): Papierkante gefunden (Rand 6 Zellen hell um das Plakat auf dunkler Wand;
    # Gegenprobe ohne Rand: Kante am Plakat), Wand ausserhalb des Bogens bitgleich, Plakat wie bei voller Korrektur
    mw = 6 * KL.PREVIEW_CELL_PX
    plate = np.full((h + 2 * pad, w + 2 * pad, 3), 60, np.uint8)
    plate[pad - mw:pad + h + mw, pad - mw:pad + w + mw] = 235
    plate[pad:pad + h, pad:pad + w] = shot
    same = plate.copy()
    same[:pad - mw] = 235                                                 # oben Wand = Papier: Kante unsichtbar
    found, none = sheet(plate, (pad, pad, w, h)), sheet(np.where(plate == 235, 60, plate).astype(np.uint8), (pad, pad, w, h))
    hidden = sheet(same, (pad, pad, w, h))
    o4 = grade(plate, f, (pad, pad, w, h), dict(cfg, photos=dict(cfg["photos"], wall_edit=False, poster_match_frac=1.0)))[0]
    wall = np.ones(plate.shape[:2], bool)
    wall[pad - mw:pad + h + mw, pad - mw:pad + w + mw] = False
    want = (pad - mw, pad - mw, w + 2 * mw, h + 2 * mw)
    edges = lambda r: (r[0], r[1], r[0] + r[2], r[1] + r[3])
    p4 = (max(abs(a - b) for r in (found, hidden) for a, b in zip(edges(r), edges(want))) <= 2 and none == (pad, pad, w, h)
          and (o4[wall] == plate[wall]).all() and de(o4[pad:pad + h, pad:pad + w]) < 0.02)
    ok &= p4
    res.append(f"nur Plakat {'ok' if p4 else 'FEHLER'} (Bogen {found}, Kante oben unsichtbar {hidden}, Soll {want}, "
               f"ohne Rand {none})")
    # Fotolicht (poster_mode light, MC 8.10.): Helligkeit im Plakat bleibt die des Fotos, Farbe wie digital bei der
    # Helligkeit des Fotos, Papierrand + Wand bitgleich; ohne Korrektur (MC1) ganzes Bild bitgleich (±1 Rundung).
    # Gegenprobe rgb (F5): Helligkeit wie digital = der Leuchtkasten
    lc = dict(cfg, photos=dict(cfg["photos"], poster_mode="light", poster_match_frac=1.0, poster_light_frac=0.0,
                               poster_tint_frac=1.0, shot_wb_frac=0.0, shot_expo_frac=0.0, shot_chroma=1.0,
                               shot_contrast=0.0))
    ol = grade(plate, f, (pad, pad, w, h), lc)[0]
    raw0 = grade(plate, f, (pad, pad, w, h), dict(lc, photos=dict(lc["photos"], poster_match_frac=0.0)))[0]
    lab_in, lab_l, lab_r = (oklab(lin(x[pad:pad + h, pad:pad + w]))[m] for x in (plate, ol, o4))
    want_ab = oklab(L)[m][:, 1:] * lab_in[:, :1] / np.maximum(oklab(L)[m][:, :1], 1e-4)
    dl, dr = float(np.median(np.abs(lab_l[:, 0] - lab_in[:, 0]))), float(np.median(np.abs(lab_r[:, 0] - lab_in[:, 0])))
    dab = float(np.median(np.linalg.norm(lab_l[:, 1:] - want_ab, axis=1)))
    pl = (dl < 0.005 and dab < 0.01 and dr > 0.03 and (ol[wall] == plate[wall]).all()
          and int(np.abs(raw0.astype(int) - plate).max()) <= 1)
    ok &= pl
    res.append(f"Fotolicht {'ok' if pl else 'FEHLER'} (Helligkeit dL {dl:.3f}, Farbe dab {dab:.3f}, "
               f"Gegenprobe rgb dL {dr:.3f})")
    # Auswahl: neue Charge schlaegt die alte (auch mit schlechterem NCC), gleiche Wand = eine Gruppe, andere = zweite
    wa, wb = np.full((90, 60, 3), 60, np.uint8), np.full((90, 60, 3), (200, 170, 120), np.uint8)
    mk = lambda name, wall, ncc: dict(path=f"{name}.JPG", n=1, ncc=ncc, cover=1.0, thumb=wall, rect=(15, 20, 30, 50))
    pc = dict(cfg, photos=dict(cfg["photos"], pick={}, prefer_from="IMG_0500"))
    cs = [mk("IMG_0100", wa, 0.99), mk("IMG_0600", wa, 0.80), mk("IMG_0601", wa, 0.79), mk("IMG_0602", wb, 0.70)]
    ch = pick(cs, pc)
    g, g0 = variants(cs, ch, pc), variants(cs[:3], pick(cs[:3], pc), pc)          # Gegenprobe: nur eine Wand
    sel = _name(ch[1]) == "IMG_0600" and [_name(c) for c in g.get(1, [])] == ["IMG_0600", "IMG_0602"] and not g0
    ok &= sel
    res.append(f"Auswahl {'ok' if sel else 'FEHLER'}")
    print(f"Plakat roh dE {de(shot):.3f} · " + " · ".join(res) + f" · {'OK' if ok else 'FEHLER'}")
    return 0 if ok else 1


if __name__ == "__main__":
    main()
