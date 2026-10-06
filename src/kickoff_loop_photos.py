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
from PIL import Image, ImageDraw
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
            "wall_knee", "wall_min_gain", "wall_wb_max", "wall_black_max", "pick_cover_weight", "pick"]
    miss = [k for k in need if k not in ph]
    assert not miss, f"loop.toml [photos]: es fehlt {miss}"
    assert 0 < ph["wall_knee"] < 1, "[photos].wall_knee: Knie der Lichter-Schulter, zwischen 0 und 1 (lineares Licht)"
    return ph


# ---------------------------------------------------------------- Erkennen

def _key(p):
    st = os.stat(p)
    return f"{os.path.basename(p)}:{st.st_size}:{int(st.st_mtime)}"


def _poster_cells(photo, H, grid):
    """Plakat aus dem Foto in 1 px pro Zelle (H: Zellen → Fotopixel), Graubild."""
    import cv2
    A = np.array([[1, 0, 0.5], [0, 1, 0.5], [0, 0, 1]])             # Pixel → Zellmitte
    g = cv2.cvtColor(photo, cv2.COLOR_RGB2GRAY).astype(np.float32)
    return cv2.warpPerspective(g, H @ A, (grid[1], grid[0]), flags=cv2.INTER_AREA | cv2.WARP_INVERSE_MAP)


def _ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-9))


def identify(photo, cfg):
    """Fallback ohne Marken: grobe Lage aus dem QR (kickoff_loop_marks.coarse), Nummer = bester Render im Vergleich
    bei 1 px pro Zelle, Lage fein per ECC am ganzen Render (marks.polish). dict wie marks.detect oder dict(error=)."""
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
        z = sorted(((_ncc(seen, s), i) for i, s in enumerate(small)), reverse=True)
        if best is None or z[0][0] > best[0]:
            best = (z[0][0], z[1][0], z[0][1], H)
    if best is None:
        return dict(error="kein QR gefunden (grobe Lage fehlt)")
    cc, cc2, i, H = best
    if cc < ID_MIN_NCC or cc - cc2 < ID_MIN_GAP:
        return dict(error=f"ohne Marken keine sichere Nummer (Render {i + 1}: {cc:.2f}, naechster {cc2:.2f})")
    H, pcc, took = M.polish(photo, H, renders[i])
    return dict(n=i + 1, z=0.0, z2=0.0, H=H, fields=0, polish_cc=pcc, polished=took, by="render", ncc_id=cc, ncc_id2=cc2)


def _detect(p):
    import kickoff_loop_marks as M
    cfg = KL.load()
    try:
        photo = M.load_photo(p)
        r = M.detect(photo, cfg)
        if "error" in r:
            r2 = identify(photo, cfg)
            r = r2 if "n" in r2 else dict(error=f"{r['error']}; {r2['error']}")
    except Exception as e:                                    # ein kaputtes Foto haelt den Lauf nicht an
        r = dict(error=repr(e))
    return _key(p), {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items() if k != "H_marks"}


def detect_all(paths):
    """Nummer + Lage je Foto, gemerkt in photos/detect.json (neue Fotos ~4 s, bekannte nichts)."""
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [p for p in paths if _key(p) not in cache]
    if todo:
        print(f"erkenne {len(todo)} Fotos ...", flush=True)
        with Pool(WORKERS) as pool:
            for k, r in pool.imap_unordered(_detect, todo):
                cache[k] = r
        os.makedirs(DIR, exist_ok=True)
        json.dump(cache, open(CACHE, "w"), indent=0)
    return {p: cache[_key(p)] for p in paths}


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


def grade(plate, f, rect, cfg):
    """Platte (uint8) → fertige Platte: im Plakat die volle Korrektur, aussen nur die Grauachse (gray_axis) mit
    Lichter-Schulter; weicher Uebergang ueber blend_cells. Die Wand wird danach mit einem Faktor s <= 1 auf
    surround_luma abgedunkelt (wie kickoff_loop_video.grade, nur nie heller, nie unter wall_min_gain und nie das
    Plakat: s laeuft ueber wall_feather_cells von 1 am Plakat auf s). Zurueck: (Platte, s)."""
    ph, q = cfg["photos"], KL.PREVIEW_CELL_PX
    u, v = gray_axis(f, ph["wall_wb_max"], ph["wall_black_max"])
    mc = _ring(plate.shape[:2], rect, ph["blend_cells"] * q)
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


# ---------------------------------------------------------------- Kandidaten, Auswahl, Ausgabe

def _plate(photo, H, cfg):
    """Entzerrte Platte wie marks.aligned, aber Rand gespiegelt statt wiederholt (wiederholte Randpixel = Streifen).
    Zurueck: (Platte, Anteil der Platte, der im Foto liegt, Plakat-Rechteck x0, y0, w, h)."""
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
    return plate, float(inside.mean()), (x0, y0, pw, ph)


def _candidate(args):
    """Ein erkanntes Foto → Kennzahlen (Passung, Abdeckung, Farbausgleich), ohne die Platte zu behalten."""
    import kickoff_loop_marks as M
    p, n, H = args
    cfg = KL.load()
    plate, cover, (x0, y0, pw, ph) = _plate(M.load_photo(p), H, cfg)
    poster = KL.frame(cfg, n - 1)
    crop = plate[y0:y0 + ph, x0:x0 + pw]
    m = inner_mask(poster.shape, cfg)
    g = [gaussian_filter(x.astype(np.float32) @ KL.LUMA, M.ALIGN_BLUR_PX) for x in (crop, poster)]
    clip = float(((crop.max(-1) >= 250) & (poster.max(-1) < 240) & m).sum() / m.sum())
    return dict(path=p, n=n, H=H, ncc=_ncc(*g), cover=cover, clip=clip, fit=fit_color(crop, poster, cfg))


def pick(cands, cfg):
    """Je Plakat ein Foto: [photos].pick (Dateiname ohne Endung) oder das beste nach NCC - Gewicht x Luecke."""
    ph, best = cfg["photos"], {}
    forced = {int(k): v for k, v in ph["pick"].items()}
    for c in cands:
        name = os.path.splitext(os.path.basename(c["path"]))[0]
        c["score"] = c["ncc"] - ph["pick_cover_weight"] * (1 - c["cover"])
        if c["n"] in forced:
            if name == forced[c["n"]]:
                best[c["n"]] = c
        elif c["score"] > best.get(c["n"], {"score": -9})["score"]:
            best[c["n"]] = c
    return best


def _build(args):
    """Gewaehltes Foto → aligned/NN.png + Vorschaubilder fuer die Boegen."""
    import kickoff_loop_marks as M
    import kickoff_loop_video as V
    c = args
    cfg = KL.load()
    plate, _, rect = _plate(M.load_photo(c["path"]), c["H"], cfg)
    out, s = grade(plate, c["fit"], rect, cfg)
    path = V.aligned_photo(c["n"] - 1)
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


def report(det, cands, chosen, built, cfg):
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
    L += ["", "Ohne Foto: " + " ".join(f"{k}" for k in range(1, n + 1) if k not in chosen), "",
          "Nicht zugeordnet:"]
    L += [f"  {os.path.basename(p)}: {r['error']}" for p, r in sorted(det.items()) if "error" in r]
    return "\n".join(L)


def main():
    args = sys.argv[1:]
    if args[:1] == ["test"]:
        sys.exit(selftest())
    paths = [p for a in args for p in sorted(glob.glob(a)) or [a]] or sorted(glob.glob(os.path.join(DIR, "raw", "*.JPG")))
    cfg = KL.load()
    check(cfg)
    det = detect_all(paths)
    with Pool(WORKERS) as pool:
        cands = pool.map(_candidate, [(p, r["n"], r["H"]) for p, r in det.items() if "n" in r], chunksize=1)
    chosen = pick(cands, cfg)
    out = os.path.join(DIR, "aligned")
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*.png")):               # nur die gewaehlten bleiben (Rest = Simulation)
        os.remove(f)
    with Pool(WORKERS) as pool:
        built = {b["n"]: b for b in pool.map(_build, list(chosen.values()), chunksize=1)}
    sheets(cfg, built, DIR)
    rep = report(det, cands, chosen, built, cfg)
    open(os.path.join(DIR, "report.txt"), "w").write(rep + "\n")
    print(rep)


# ---------------------------------------------------------------- Selbsttest

def selftest():
    """Am fertigen Bild: ein synthetisches 'Foto' (Render durch bekannte Druck- + Kamerafehler: Schwarz 3 %, Papier
    88 %, Buntheit 85 %, Farbstich, Belichtung, Tonkurve) an heller Wand muss nach fit_color + grade im Plakat wieder
    wie der Render aussehen (dE < 0.02; Gegenprobe: das rohe Foto liegt weit daneben), die Wand auf surround_luma."""
    cfg = KL.load()
    check(cfg)
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
    print(f"Plakat roh dE {de(shot):.3f} · " + " · ".join(res) + f" · {'OK' if ok else 'FEHLER'}")
    return 0 if ok else 1


if __name__ == "__main__":
    main()
