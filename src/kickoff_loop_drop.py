#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""Kick-off Loop, Drop-Konzepte E1: was nach dem Drop kommt, damit sich der Wechsel lohnt (Vadim 2.10.).

Jeder Clip: 1 Takt Loop auf IGOR (3 Beats Karussell T16, dann IGORs eigener Stopp-Beat: Plakat steht, Kamera drueckt)
→ Sprung im Song auf den Downbeat mit Gesang (~48.9 s) → 8 Beats Auszahlung mit den Infos. Alles auf dem Zellraster
(1 Zelle = cell_px), Farben nur aus Paletten (Index-Felder), Bayer-Korn aus den Renders von kickoff_loop.
  E1a Pixel-Explosion   die hellen Zellen des Plakats fliegen auseinander und rasten auf den Beats als Endkarte ein
  E1b Dimensionssprung  jeder Beat eine neue Colorway, der Stern stempelt hinein, die Infos kommen Beat fuer Beat
  E1c Wand              Kamera reisst auf alle 32 Plakate zurueck, Lauflicht, dann klappen sie zur Endkarte um
Stellschrauben: [drop] in kickoff_loop/previz/review/E1.toml (Rest = Kopie von loop.toml).

  uv run src/kickoff_loop_drop.py sheet  [toml]   Kontaktbogen je Konzept → previz/review/E1_sheet.png
  uv run src/kickoff_loop_drop.py video  [toml]   Clips mit Ton → previz/review/E1a.mp4 …
"""
import glob
import hashlib
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kickoff_loop as KL  # noqa: E402
import kickoff_loop_video as V  # noqa: E402
import styles as S  # noqa: E402

DEF_TOML = os.path.join(KL.PROJECT, "previz", "review", "E1.toml")
OUT = os.path.join(KL.PROJECT, "previz", "review")
AUDIO = "ref/audio/igors_theme.mp3"
SR = 48000
FADE_S = 0.005          # Entknacken an den Schnitten (5 ms hoert man nicht als Blende)
PEAK = 0.89             # -1 dBFS, feste Verstaerkung (kein Regler, der Drop bleibt so laut wie im Song)


def _source_hash():
    """Wie KL._source_hash, aber ohne diese Datei: sonst rendert jede Aenderung hier alle 32 Plakate neu."""
    h = hashlib.sha1()
    for p in sorted(glob.glob(os.path.join(KL.ROOT, "src", "*.py"))):
        if not p.endswith("kickoff_loop_drop.py"):
            h.update(open(p, "rb").read())
    return h.hexdigest()


KL._source_hash = _source_hash   # gilt auch in den Pool-Arbeitern (macOS spawnt, importiert dieses Modul neu)


def load(path):
    cfg = KL.load(path)
    d = cfg.get("drop")
    assert d, f"{path}: Abschnitt [drop] fehlt"
    W, H = d["size_px"]
    assert W % d["cell_px"] == 0 and H % d["cell_px"] == 0, "[drop].size_px nicht durch cell_px teilbar"
    assert d["src_from_s"] < d["src_to_s"], "[drop]: src_from_s < src_to_s"
    bad = [p for p in d["worlds"] if p not in KL.P_CODES or KL.is_lilac(KL.palette_hex({**cfg, "color": {
        **cfg["color"], "worlds": [[p]], "world_frames": KL.count(cfg)}}, 0))]
    assert not bad, f"[drop].worlds: unbekannt oder lila {bad}"
    assert d["card_style"] in KL.S_CODES, f"[drop].card_style: {d['card_style']} unbekannt"
    return cfg


# ---------------------------------------------------------------- Zeit

class T:
    def __init__(self, cfg):
        d = cfg["drop"]
        self.fps, self.beat = d["fps"], 60 / cfg["music"]["loop_grid"]["bpm"]
        self.drop_s = d["src_to_s"] - d["src_from_s"]                    # 1 Takt
        self.drop = round(self.drop_s * self.fps)
        self.total = self.drop + round(d["payoff_beats"] * self.beat * self.fps)
        self.loop_end = round(d["loop_beats"] * self.beat * self.fps)
        self.per_s = cfg["loop"]["changes_per_bar"] / (4 * self.beat)    # T16: 16.32 Plakate/s

    def payoff(self, f):
        """Zeit nach dem Drop in Beats."""
        return (f - self.drop) / self.fps / self.beat


# ---------------------------------------------------------------- Bilder als Index-Felder

def to_idx(img, pal, px):
    """RGB-Render → Palettenindex je Zelle (Zellmitte, naechste Palettenfarbe)."""
    cells = img[px // 2::px, px // 2::px].astype(np.int32)
    return ((cells[..., None, :] - np.asarray(pal, np.int32)[None, None]) ** 2).sum(-1).argmin(-1).astype(np.int8)


def hex_arr(hexes):
    return np.array([[int(h[j:j + 2], 16) for j in (1, 3, 5)] for h in hexes], np.uint8)


def card_style(cfg, show, scale=1.0, rot_add=0.0):
    """Endkarte 9:16 (kickoff_loop.layout im Digitalteil, u = 1): Stern + Satz, show = welche Elemente."""
    d = cfg["drop"]
    last = V.last_star(cfg)
    W, H = S.SIZES["9x16"][:2]
    st = KL.poster_style(cfg, last)
    st["S"] = KL.S_CODES[d["card_style"]]
    cx, cy, cr = d["card_star"]
    star = (cx * W, cy * H, cr * W * scale, KL.star_at(cfg, last)[3] + rot_add)
    st["loop"] = {**st["loop"], "digital": dict(u=1.0, offset=V.digital_offset(cfg), star=star, show=list(show))}
    st["star"] = (star[0] / W, star[1] / H, star[2] / W)
    return st


def _card_job(args):
    cfg, show, scale, rot = args
    st = card_style(cfg, show, scale, rot)
    img = KL.render_cached(st, "9x16", "e1card")
    return to_idx(img, S.hexpal(st["P"]), KL.PREVIEW_CELL_PX), S.PALS[st["P"]]


def cards(cfg, jobs):
    with Pool() as pool:
        return pool.map(_card_job, [(cfg, *j) for j in jobs])


SHOWS = [(), ("title",), ("title", "date"), ("title", "date", "qr")]


# ---------------------------------------------------------------- Vor dem Drop (fuer alle Konzepte gleich)

def poster_screen(cfg, img, push=1.0):
    """Plakat (4 px/Zelle) aufs 9:16-Bild bei cell_px pro Zelle, mittig, um push vergroessert (Zellen bleiben Quadrate
    ganzer Pixel: nearest)."""
    d = cfg["drop"]
    W, H = d["size_px"]
    cells = img[2::4, 2::4]
    gh, gw = cells.shape[:2]
    k = d["cell_px"] * push
    yy, xx = np.mgrid[0:H, 0:W]
    sy, sx = ((yy - H / 2) / k + gh / 2).astype(int), ((xx - W / 2) / k + gw / 2).astype(int)
    ok = (sy >= 0) & (sy < gh) & (sx >= 0) & (sx < gw)
    out = np.full((H, W, 3), 10, np.uint8)
    out[ok] = cells[sy[ok], sx[ok]]
    return out


def pre_frame(cfg, tm, posters, f):
    """Karussell T16, endet auf dem letzten Frame mit Stern; im Stopp-Beat steht es, die Kamera drueckt nach vorn."""
    last = V.last_star(cfg)
    n = KL.count(cfg)
    if f < tm.loop_end:
        k = int(f / tm.fps * tm.per_s)
        kend = int((tm.loop_end - 1) / tm.fps * tm.per_s)
        return poster_screen(cfg, posters[(last - (kend - k)) % n])
    u = (f - tm.loop_end) / max(tm.drop - tm.loop_end, 1)
    return poster_screen(cfg, posters[last], 1 + cfg["drop"]["push_frac"] * u ** 2)


def up(idx_rgb, px):
    return np.repeat(np.repeat(idx_rgb, px, 0), px, 1)


# ---------------------------------------------------------------- E1a Pixel-Explosion

class Explode:
    """Helle Zellen (>= lit_level) des letzten Plakats sind Teilchen. Auf dem Drop fliegen sie radial vom Stern weg
    (gebremst), auf land_beats rasten sie gruppenweise (Stern, SPARK, Datum, QR) als Endkarte ein, mit Ueberschwingen.
    Jede Zelle bleibt eine Zelle auf dem Raster (Lage gerundet), Farbe = Palettenstufe."""

    def __init__(self, cfg, posters, cardset):
        d = cfg["drop"]
        self.cfg, self.d = cfg, d
        W, H = d["size_px"]
        self.gw, self.gh = W // d["cell_px"], H // d["cell_px"]
        last = V.last_star(cfg)
        pal_src = hex_arr(KL.palette_hex(cfg, last))
        src = to_idx(posters[last], pal_src, KL.PREVIEW_CELL_PX)
        sh, sw = src.shape
        oy, ox = (self.gh - sh) // 2, (self.gw - sw) // 2
        ys, xs = np.nonzero(src >= d["lit_level"])
        self.src_pos = np.stack([ys + oy, xs + ox], 1).astype(np.float32)
        self.src_lvl = src[ys, xs]
        x, y, r, _ = KL.star_at(cfg, last)
        center = np.array([y * sh + oy, x * sw + ox], np.float32)
        idxs = [c[0] for c in cardset]                                   # Karten: leer, +Titel, +Datum, +QR
        self.pal = hex_arr(cardset[-1][1])
        full = idxs[-1]
        self.base = np.where(full >= d["lit_level"], 1, full)            # Grund der Endkarte ohne Teilchen (Stufe 1)
        group = np.full(full.shape, -1)
        group[idxs[0] >= d["lit_level"]] = 0                             # Stern
        for g in range(1, 4):
            group[(idxs[g] != idxs[g - 1]) & (full >= d["lit_level"])] = g
        group[(group < 0) & (full >= d["lit_level"])] = 0
        ty, tx = np.nonzero(group >= 0)
        self.tgt = np.stack([ty, tx], 1).astype(np.float32)
        self.tgt_lvl, self.tgt_grp = full[ty, tx], group[ty, tx]
        rng = np.random.default_rng(14)
        pick = rng.integers(0, len(self.src_pos), len(self.tgt))           # jede Zielzelle bekommt ein Teilchen
        self.p0, self.l0 = self.src_pos[pick], self.src_lvl[pick]
        dirv = self.p0 - center
        dirv /= np.maximum(np.linalg.norm(dirv, axis=1, keepdims=True), 1e-3)
        ang = rng.normal(0, 0.35, len(dirv))                               # etwas Streuung
        c, s = np.cos(ang), np.sin(ang)
        dirv = np.stack([dirv[:, 0] * c - dirv[:, 1] * s, dirv[:, 0] * s + dirv[:, 1] * c], 1)
        lo, hi = d["explode_speed_cells_s"]
        self.v = dirv * rng.uniform(lo, hi, (len(dirv), 1)) * (0.4 + 0.6 * rng.random((len(dirv), 1)))
        self.order = rng.permutation(len(self.tgt))
        self.pal_src = pal_src

    def frame(self, tm, f):
        d = self.d
        t = (f - tm.drop) / tm.fps
        tau = d["explode_tau_s"]
        pos = self.p0 + self.v * tau * (1 - np.exp(-t / tau))
        s = np.zeros(len(pos), np.float32)
        for g, b in enumerate(d["land_beats"]):
            m = self.tgt_grp == g
            s[m] = np.clip((t - b * tm.beat) / d["land_s"], 0, 1)
        k = 1.70158                                                         # easeOutBack: schiesst 10 % ueber
        e = 1 + (k + 1) * (s - 1) ** 3 + k * (s - 1) ** 2
        pos = pos + (self.tgt - pos) * e[:, None]
        lvl = np.where(s >= 1, self.tgt_lvl, self.l0)
        idx = self.base.copy()
        p = np.round(pos[self.order]).astype(int)
        ok = (p[:, 0] >= 0) & (p[:, 0] < self.gh) & (p[:, 1] >= 0) & (p[:, 1] < self.gw)
        idx[p[ok, 0], p[ok, 1]] = lvl[self.order][ok]
        rgb = self.pal[idx]
        if f - tm.drop < d["impact_frames"]:
            rgb = self.pal[len(self.pal) - 1 - idx]
        return up(rgb, d["cell_px"])


# ---------------------------------------------------------------- E1b Dimensionssprung

def dimension_jobs(cfg, tm):
    """Welche Karten-Renders gebraucht werden: (show, Massstab, Drehung) je Bild."""
    d = cfg["drop"]
    out = []
    for f in range(tm.drop, tm.total):
        b = tm.payoff(f)
        k = int(b)
        show = SHOWS[sum(b >= x for x in d["reveal_beats"][1:])]
        j = int((b - k) * tm.beat * tm.fps)
        sc = d["punch"][j] if j < len(d["punch"]) else 1.0
        out.append((tuple(show), sc, d["stamp_rot_deg"] * k))
    return out


def dimension_frame(cfg, tm, f, rendered, jobs):
    """Jeder Beat eine neue Welt (Colorway aus [drop].worlds, gleiche Stufen-Indizes), der Stern stempelt hinein
    (gross → Endgroesse in drei Bildern), die Infos kommen auf reveal_beats dazu."""
    d = cfg["drop"]
    idx, _ = rendered[jobs[f - tm.drop]]
    k = min(int(tm.payoff(f)), len(d["worlds"]) - 1)
    pal = np.asarray(KL.station(d["worlds"][k], cfg["color"]["steps"]), np.uint8)
    if f - tm.drop < d["impact_frames"]:
        idx = len(pal) - 1 - idx
    return up(pal[idx], d["cell_px"])


# ---------------------------------------------------------------- E1c Wand

class Wall:
    """Alle 32 Plakate als Wand (4 x 8), jedes auf seine Kachel verkleinert und neu im Bayer-Korn gedithert (eigene
    Palette, Raster der Ausgabe). Lauflicht im Karusselltempo, dann klappen die Kacheln in einer Welle um (waagerecht
    gestaucht, nearest, auf dem Raster), ihre Rueckseiten sind die Teile der Endkarte."""

    def __init__(self, cfg, posters, card):
        d = self.d = cfg["drop"]
        W, H = d["size_px"]
        self.gw, self.gh = W // d["cell_px"], H // d["cell_px"]
        n = KL.count(cfg)
        cols, rows = d["wall_cols"], d["wall_rows"]
        self.xe = np.round(np.linspace(0, self.gw, cols + 1)).astype(int)
        self.ye = np.round(np.linspace(0, self.gh, rows + 1)).astype(int)
        self.idx = np.zeros((self.gh, self.gw), np.int8)
        self.tile = np.full((self.gh, self.gw), -1)
        self.pals = np.zeros((n + 1, cfg["color"]["steps"], 3), np.uint8)
        self.boxes = []
        th = self.ye[1] - self.ye[0] - 2                                   # 1 Zelle Luft oben/unten
        tw = round(th * KL.POSTER_ASPECT)
        for i in range(n):
            r, c = divmod(i, cols)
            pal = hex_arr(KL.palette_hex(cfg, i))
            self.pals[i] = pal
            lv = to_idx(posters[i], pal, KL.PREVIEW_CELL_PX).astype(np.float32) / (len(pal) - 1)
            small = np.asarray(Image.fromarray(lv).resize((tw, th), Image.BOX))
            y0 = self.ye[r] + 1
            x0 = (self.xe[c] + self.xe[c + 1] - tw) // 2
            self.idx[y0:y0 + th, x0:x0 + tw] = S.dither(small, len(pal) - 1, "bayer4", 1)
            self.tile[y0:y0 + th, x0:x0 + tw] = i
            self.boxes.append((self.ye[r], self.xe[c], self.ye[r + 1], self.xe[c + 1], y0, x0, th, tw))
        self.card_idx, self.card_pal = card[0], hex_arr(card[1])
        self.pals[n] = self.card_pal
        self.last = V.last_star(cfg)
        self.n = n

    def wall_rgb(self, active=None):
        idx = self.idx.copy()
        if active is not None:
            idx = np.where((self.tile >= 0) & (self.tile != active), np.maximum(idx - 2, 0), idx)
        out = np.full((self.gh, self.gw, 3), 8, np.uint8)
        m = self.tile >= 0
        out[m] = self.pals[self.tile[m], idx[m]]
        return out

    def frame(self, cfg, tm, f, posters):
        d = self.d
        t = (f - tm.drop) / tm.fps
        b = tm.payoff(f)
        c0, c1 = d["chase_beats"]
        active = None
        if c0 <= b < c1:
            active = (self.last + 1 + int((t - c0 * tm.beat) * tm.per_s)) % self.n
        img = self.wall_rgb(active)
        if t < d["wall_zoom_s"]:                                           # Rueckzug: vom vollen Plakat auf die Wand
            Y0, X0, Y1, X1, y0, x0, th, tw = self.boxes[self.last]
            u = 1 - (1 - t / d["wall_zoom_s"]) ** 3
            z0 = self.gh / th * 0.98
            z = z0 * (1 / z0) ** u
            cy = (y0 + th / 2) * (1 - u) + self.gh / 2 * u
            cx = (x0 + tw / 2) * (1 - u) + self.gw / 2 * u
            yy, xx = np.mgrid[0:self.gh, 0:self.gw]
            sy = np.clip(((yy - self.gh / 2) / z + cy).astype(int), 0, self.gh - 1)
            sx = np.clip(((xx - self.gw / 2) / z + cx).astype(int), 0, self.gw - 1)
            img = img[sy, sx]
        flip0 = d["flip_start_beats"]
        if b >= flip0:
            card = self.card_pal[self.card_idx]
            for i, (Y0, X0, Y1, X1, *_) in enumerate(self.boxes):
                r, c = divmod(i, d["wall_cols"])
                order = r + c                                              # Welle diagonal von oben links
                ft = (b - flip0 - order * d["flip_per_tile_beats"]) * tm.beat * tm.fps
                if ft < 0:
                    continue
                k = d["flip_frames"]
                if ft >= k:
                    img[Y0:Y1, X0:X1] = card[Y0:Y1, X0:X1]
                    continue
                w = abs(1 - 2 * ft / k)                                    # 1 → 0 → 1: Kante voraus, dann Rueckseite
                face = img[Y0:Y1, X0:X1].copy() if ft < k / 2 else card[Y0:Y1, X0:X1]
                xc = (X1 - X0) / 2
                xs = np.arange(X1 - X0)
                sx = ((xs - xc) / max(w, 1e-3) + xc).astype(int)
                ok = (sx >= 0) & (sx < X1 - X0)
                tile = np.full_like(face, 8)
                tile[:, ok] = face[:, sx[ok]]
                img[Y0:Y1, X0:X1] = tile
        if f - tm.drop < d["impact_frames"]:
            img = 255 - img                                                # Negativ (Wand hat 32 Paletten)
        return up(img, d["cell_px"])


# ---------------------------------------------------------------- Zusammenbau

CONCEPTS = [("E1a", "Pixel-Explosion"), ("E1b", "Dimensionssprung"), ("E1c", "Wand")]


def build(cfg):
    tm = T(cfg)
    posters, _, _ = KL.frames(cfg)
    base = cards(cfg, [(s, 1.0, 0.0) for s in SHOWS])
    jobs = dimension_jobs(cfg, tm)
    uniq = sorted(set(jobs))
    rendered = dict(zip(uniq, cards(cfg, uniq)))
    ex, wall = Explode(cfg, posters, base), Wall(cfg, posters, base[-1])

    def frame(code, f):
        if f < tm.drop:
            return pre_frame(cfg, tm, posters, f)
        if code == "E1a":
            return ex.frame(tm, f)
        if code == "E1b":
            return dimension_frame(cfg, tm, f, rendered, jobs)
        return wall.frame(cfg, tm, f, posters)
    return tm, frame


def audio(cfg, tm, path):
    """IGOR src_from_s..src_to_s (Drums + Stopp), dann Sprung auf jump_to_s (Downbeat mit Gesang), genau so lang wie
    das Bild. 5 ms Entknacken an den Kanten, feste Verstaerkung auf -1 dBFS Spitze."""
    import kickoff_loop_music as KM
    d = cfg["drop"]
    x = KM.decode(os.path.join(KL.PROJECT, AUDIO))
    a = x[round(d["src_from_s"] * SR):round(d["src_to_s"] * SR)]
    n = round(tm.total / tm.fps * SR) - len(a)
    b = x[round(d["jump_to_s"] * SR):round(d["jump_to_s"] * SR) + n].copy()
    k = round(FADE_S * SR)
    a[-k:] *= np.linspace(1, 0, k)[:, None]
    b[:k] *= np.linspace(0, 1, k)[:, None]
    y = np.concatenate([a, b])
    y[-k * 4:] *= np.linspace(1, 0, k * 4)[:, None]
    y *= PEAK / np.abs(y).max()
    KM.write_wav(path, y)
    return path


def label(im, text):
    im = Image.fromarray(im)
    ImageDraw.Draw(im).text((8, 8), text, fill=(255, 255, 255), font=S.font("DepartureMono-Regular.otf", 22))
    return im


def sheet(cfg):
    tm, frame = build(cfg)
    beats = [None, -0.5, 0.05, 0.5, 1.2, 2.5, 4.2, 5.5, 7.9]
    cols = []
    for code, name in CONCEPTS:
        row = []
        for b in beats:
            f = round(tm.loop_end * 0.5) if b is None else min(tm.drop + round(b * tm.beat * tm.fps), tm.total - 1)
            row.append(label(frame(code, f), f"{code} {f / tm.fps:.2f}s" + ("" if b is None else f" Beat {b:+.1f}")))
        cols.append((f"{code} {name}", row))
    W, H = cfg["drop"]["size_px"]
    s = 2
    out = Image.new("RGB", (len(beats) * (W // s + 8), len(cols) * (H // s + 40)), (14, 14, 18))
    d = ImageDraw.Draw(out)
    for r, (name, row) in enumerate(cols):
        y = r * (H // s + 40)
        d.text((4, y + 6), name, fill=(230, 230, 230), font=S.font("DepartureMono-Regular.otf", 26))
        for c, im in enumerate(row):
            out.paste(im.resize((W // s, H // s), Image.NEAREST), (c * (W // s + 8), y + 36))
    path = os.path.join(OUT, "E1_sheet.png")
    out.save(path)
    return path


def video(cfg, only=None):
    tm, frame = build(cfg)
    wav = audio(cfg, tm, os.path.join(OUT, "E1_audio.wav"))
    W, H = cfg["drop"]["size_px"]
    out = []
    for code, _ in CONCEPTS:
        if only and code not in only:
            continue
        path = os.path.join(OUT, f"{code}.mp4")
        ff = V.ffmpeg_writer(path, (W, H), tm.fps, wav)
        for f in range(tm.total):
            ff.stdin.write(np.ascontiguousarray(frame(code, f)).tobytes())
        ff.stdin.close()
        ff.wait()
        out.append(path)
    rep = os.path.join(OUT, "E1_report.txt")
    d = cfg["drop"]
    with open(rep, "w", encoding="utf-8") as fh:
        fh.write(f"E1 Drop-Konzepte · {W}x{H} @ {tm.fps} fps · {tm.total / tm.fps:.2f} s, Drop bei {tm.drop / tm.fps:.3f} s "
                 f"(Bild {tm.drop})\nTon: IGOR {d['src_from_s']:.3f}-{d['src_to_s']:.3f} s (3 Beats Drums + Stopp-Beat), "
                 f"Sprung auf {d['jump_to_s']:.3f} s (Downbeat Takt 10, Raster 48.904) bis "
                 f"{d['jump_to_s'] + (tm.total - tm.drop) / tm.fps:.3f} s\nKarussell {tm.per_s:.2f} Plakate/s, endet auf "
                 f"Frame {V.last_star(cfg) + 1}\n")
    return out + [rep]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sheet"
    path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].endswith(".toml") else DEF_TOML
    cfg = load(path)
    if cmd == "sheet":
        p = sheet(cfg)
        print(p)
        subprocess.run(["open", p]) if sys.stdout.isatty() else None
    elif cmd == "video":
        print("\n".join(video(cfg, [a for a in sys.argv[2:] if not a.endswith(".toml")] or None)))
    else:
        sys.exit(__doc__)
