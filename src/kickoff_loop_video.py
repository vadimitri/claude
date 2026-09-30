"""Video-Teil des Kick-off-Loops: Plakat-Frames → Fotos (bis dahin Simulation) → Loop + Zoom → digitaler Teil → Vorschau.

Aufgerufen ueber `uv run src/kickoff_loop.py preview`.
Alle Werte aus kickoff_loop/loop.toml ([video], [endcard], [music], [simulation], [checks]).

Zeitachse in Timeline-Frames (video.timeline_fps), alles auf dem Taktraster von loop.bpm (class Timeline):
  | Karussell nach dem Musik-Raster, Kamera zoomt vom ersten Frame an gleichmaessig | Digitalteil ab burst_s |
Das Karussell endet immer auf dem letzten Frame des Loops (Titel steht dann im Standardsatz); der Startframe folgt daraus.

Plattenraum: pro Plakat ein Bild ("Platte"), in dem das Plakat immer an derselben Stelle liegt, genau so gross wie der
Vorschau-Render (1168 x 1652 px, 4 px pro Zelle). Echte Fotos werden spaeter auf diese Lage entzerrt
(kickoff_loop/photos/aligned/), bis dahin baut simulated_plate() erfundene Waende. Die Kamera schneidet aus der Platte
aus: am Anfang ist das Plakat start_poster_frac der Bildhoehe, am Ende ist eine Zelle end_cell_px Ausgabepixel gross.
"""
import bisect
import colorsys
import os
import shutil
import subprocess
import time
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

import kickoff as K
import kickoff_loop as KL
import styles as S

BOIL_SEED = 26                       # Boil: fester Zufall, damit jede Vorschau gleich zittert
VALLEY_UP_DEG = 30                   # Sternprofil: Spitzen bei 30° + 60°k, bei Drehung 30 (mod 60) zeigt ein Tal nach oben
FLASH_ANALYSIS_PX = (68, 120)        # Blitz-Check auf 1/16: ein Block = 16 px = eine Bayer-Periode am Zoom-Ende (kein Moire)


# ---------------------------------------------------------------- Zeitachse und Kamera

class Timeline:
    """Die Zeitachse in Timeline-Frames, aus dem Musik-Raster ([music].grid, kickoff_loop_music.py).

    Video-Sekunde 0 = Anfang der Musik. Plakatwechsel liegen auf 16teln/Achteln des Karussell-Tempos (carousel_bars);
    ein 16tel ist bei 120 BPM 3 Timeline-Frames, bei 81.6 BPM 4.41, gerundet wird jeder Wechsel fuer sich (kein Wegdriften).
    hit       Timeline-Frame des Impacts (Maker-Night-Drop)
    zoom_end  Ende des Karussells = Beginn des Ausbruchs (burst_s, die Luft vor dem Drop)
    changes   Plakatwechsel als (Frame, Plakat-Index); der letzte zeigt immer das letzte Plakat des Loops
    punches   Frames der Hits im Karussell (Kamera-Stoss)
    bars      Frames aller Taktstriche bis zum Ende (Marker fuer Resolve)
    total     Ende (end_s, Taktstrich)"""

    def __init__(self, cfg):
        v, g, n = cfg["video"], cfg["music"]["grid"], KL.count(cfg)
        fps = v["timeline_fps"]
        bar = 16 * g["sixteenth_s"]
        times, t = [], 0.0
        for per, bars in g["carousel_bars"]:
            for _ in range(per * bars):
                times.append(t)
                t += bar / per
        times = [x for x in times if x < g["burst_s"] - 1e-6]
        first = -len(times) % n
        self.changes = [(round(x * fps), (first + j) % n) for j, x in enumerate(times)]
        self.hit = round(g["impact_s"] * fps)
        self.zoom_end = round(g["burst_s"] * fps)
        self.total = round(g["end_s"] * fps)
        self.punches = [round(h * fps) for h in g["hits_s"] if h < g["burst_s"]]
        self.bars = [round(d * fps) for d in g["downbeats_s"] if d * fps <= self.total]
        self._starts = [f for f, _ in self.changes]

    def poster_at(self, t):
        """Welches Plakat im Frame t zu sehen ist (im Digitalteil: das letzte)."""
        return self.changes[bisect.bisect_right(self._starts, min(t, self.zoom_end - 1)) - 1][1]

    def change_before(self, t):
        return self._starts[bisect.bisect_right(self._starts, t) - 1]


def scales(cfg, poster_h):
    """Kamera-Endpunkte als Massstab Plattenpixel → Ausgabepixel: (Anfang, Ende)."""
    v = cfg["video"]
    start = v["start_poster_frac"] * v["size_px"][1] / poster_h
    end = v["end_cell_px"] / KL.PREVIEW_CELL_PX
    return start, end


def camera(cfg, tl, t, poster_h):
    """Kamera im Timeline-Frame t (nur Foto-Phase): (Massstab, Rollwinkel in Grad).

    Grundfahrt exponentiell ohne Kurve (jeder Frame vergroessert um denselben Faktor, Vadim 30.9.: "kontinuierlich"),
    der letzte Karussell-Frame erreicht genau den Endmassstab. Dazu, damit das Bild lebt (Vadim 30.9.: "zu wenig
    Bewegung"): ein gleichmaessiges Rollen (roll_deg, endet waagerecht, der Wechsel ins Digitale bleibt pixelgenau) und
    auf jedem Schlag aus tl.punches ein kurzer Stoss nach vorn, der mit punch_decay_beats abklingt."""
    v = cfg["video"]
    s0, s1 = scales(cfg, poster_h)
    tz = tl.change_before(t) if v["zoom_stepped"] else t      # Kamera springt nur, wenn das Plakat wechselt
    u = np.clip(tz / max(tl.zoom_end - 1, 1), 0, 1)
    fps, b = v["timeline_fps"], beat_s(cfg)
    kick = sum(np.exp(-(t - p) / fps / (v["punch_decay_beats"] * b)) for p in tl.punches if p <= t < tl.zoom_end - 1)
    return s0 * (s1 / s0) ** u * (1 + v["punch_frac"] * kick), v["roll_deg"] * (1 - u)


# ---------------------------------------------------------------- Platten (Fotos bzw. Simulation)

def plate_size(cfg, poster):
    """Die Platte muss den ganzen Anfangsausschnitt abdecken, plus Luft fuer den Versatz."""
    W, H = cfg["video"]["size_px"]
    s0, _ = scales(cfg, poster.shape[0])
    margin = 4 * cfg["simulation"]["jitter_px"]
    return int(np.ceil(W / s0)) + margin, int(np.ceil(H / s0)) + margin


def simulated_plate(cfg, poster, k):
    """Platzhalter-Foto: das Plakat haengt an einer erfundenen Wand, jede Karte in einer anderen Welt.
    Wand = zwei Farbtoene + weiche Flecken + ein paar andere Aushaenge + Filmkorn; Plakat mit Schatten und Restversatz.
    Ersetzt durch echte, entzerrte Fotos, sobald es sie gibt."""
    sim = cfg["simulation"]
    rng = np.random.default_rng(1000 + k)
    PW, PH = plate_size(cfg, poster)
    low = (PH // 32, PW // 32)                             # Wand klein erzeugen, weich hochskalieren (Fotolook)
    hue = rng.random()
    a = np.array(colorsys.hsv_to_rgb(hue, rng.uniform(0.15, 0.45), rng.uniform(0.25, 0.65)))
    b = np.array(colorsys.hsv_to_rgb((hue + rng.uniform(-0.08, 0.08)) % 1, rng.uniform(0.1, 0.35), rng.uniform(0.15, 0.5)))
    blot = gaussian_filter(rng.standard_normal(low), 3)
    blot = (blot - blot.min()) / np.ptp(blot)
    ramp = np.linspace(0, 1, low[0])[:, None] * rng.uniform(0.3, 0.8)
    wall = a * (1 - np.clip(blot * 0.7 + ramp, 0, 1))[..., None] + b * np.clip(blot * 0.7 + ramp, 0, 1)[..., None]
    for _ in range(rng.integers(3, 7)):                    # andere Aushaenge an der Wand
        h, w = rng.integers(low[0] // 8, low[0] // 3), rng.integers(low[1] // 8, low[1] // 3)
        y, x = rng.integers(0, low[0] - h), rng.integers(0, low[1] - w)
        wall[y:y + h, x:x + w] = colorsys.hsv_to_rgb(rng.random(), rng.uniform(0, 0.6), rng.uniform(0.3, 0.95))
    img = Image.fromarray((np.clip(wall, 0, 1) * 255).astype(np.uint8)).resize((PW, PH), Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(6))
    grain = rng.normal(0, 6, (PH, PW, 1))
    img = grade(Image.fromarray(np.clip(np.asarray(img, np.float32) + grain, 0, 255).astype(np.uint8)), cfg)

    s = Image.fromarray(poster).convert("RGBA").rotate(rng.normal(0, sim["jitter_rot_deg"]), Image.BICUBIC, expand=True)
    jx, jy = rng.normal(0, sim["jitter_px"], 2)
    x0 = round((PW - s.width) / 2 + jx)
    y0 = round((PH - s.height) / 2 + jy)
    shadow = Image.new("L", (PW, PH), 0)
    shadow.paste(s.getchannel("A").point(lambda v: v * 0.55), (x0 + 10, y0 + 16))
    img.paste((0, 0, 0), (0, 0), shadow.filter(ImageFilter.GaussianBlur(14)))
    img.paste(s, (x0, y0), s)
    return img


def grade(img, cfg, hole=None):
    """Belichtung angleichen: ganzes Bild mit einem Faktor so hell/dunkel, dass die Umgebung (alles ausser `hole`,
    dem Plakat) im Mittel surround_luma hat. Ohne das blitzt bei 8 fps jeder Ortswechsel ueber das ganze Bild
    (v003 ohne Angleichen: 45 % der Flaeche, Grenze 25 %). Gilt fuer echte Fotos genauso wie fuer die Simulation."""
    a = np.asarray(img, np.float32) / 255
    lum = a @ KL.LUMA
    m = np.ones(lum.shape, bool)
    if hole:
        x0, y0, x1, y1 = hole
        m[y0:y1, x0:x1] = False
    gain = cfg["video"]["surround_luma"] / max(float(lum[m].mean()), 1e-3)
    return Image.fromarray((np.clip(a * gain, 0, 1) * 255).astype(np.uint8))


def aligned_photo(k):
    return os.path.join(KL.PROJECT, "photos", "aligned", f"{k + 1:02d}.png")


def photo_plate(cfg, poster, k):
    """Echtes, entzerrtes Foto, falls vorhanden (kickoff_loop/photos/aligned/NN.png), sonst Simulation."""
    path = aligned_photo(k)
    if os.path.exists(path):
        im = Image.open(path).convert("RGB")
        ph, pw = poster.shape[:2]
        x0, y0 = (im.width - pw) // 2, (im.height - ph) // 2
        return grade(im, cfg, (x0, y0, x0 + pw, y0 + ph))
    return simulated_plate(cfg, poster, k)


def shoot(plate, s, size, roll=0.0):
    """Kameraausschnitt: Plattenmitte, Massstab s (Plattenpixel → Ausgabepixel), um roll Grad gedreht.
    Bei s = 1, roll = 0 und ganzzahliger Lage ist das eine 1:1-Kopie, deshalb ist das Zoom-Ende pixelgenau."""
    W, H = size
    if not roll:
        cx, cy = plate.width / 2, plate.height / 2
        box = (cx - W / 2 / s, cy - H / 2 / s, cx + W / 2 / s, cy + H / 2 / s)
        return plate.resize(size, Image.LANCZOS, box=box)
    a = np.radians(roll)
    c, sn = np.cos(a) / s, np.sin(a) / s                     # Ausgabepixel → Plattenpixel (Drehung um die Bildmitte)
    cx, cy = plate.width / 2, plate.height / 2
    data = (c, sn, cx - c * W / 2 - sn * H / 2, -sn, c, cy + sn * W / 2 - c * H / 2)
    return plate.transform(size, Image.AFFINE, data, Image.BICUBIC)


def digital_offset(cfg):
    """Wo das Plakat im letzten Foto-Frame liegt (linke obere Ecke in Ausgabepixeln), aufs Zellraster gerundet."""
    W, H = cfg["video"]["size_px"]
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    px = KL.PREVIEW_CELL_PX
    return round((W - pw) / 2 / px) * px, round((H - ph) / 2 / px) * px


def beat_s(cfg):
    return 60 / cfg["loop"]["bpm"]


def digital_phase(cfg, dt):
    """Abschnitt des Digitalteils dt Sekunden nach dem Wechsel: ("burst" | "impact" | "card", Zeit im Abschnitt)."""
    e, b = cfg["endcard"], beat_s(cfg)
    fly = e["burst_beats"] * b
    hit = e["impact_frames"] / cfg["video"]["timeline_fps"]
    if dt < fly:
        return "burst", dt
    if dt < fly + hit:
        return "impact", dt - fly
    return "card", dt - fly - hit


def digital_style(cfg, dt):
    """Stil-Dict des Digitalteils, dt Sekunden nach dem Wechsel ins Digitale. Drei Abschnitte (Spider-Verse-Prinzip:
    der Bildrhythmus selbst ist der Uebergang, Stop-Motion auf Achteln → Rechner auf 24 fps):

    burst   Der Stern bricht aus dem Papier: er fliegt aus seiner Lage im letzten Plakat auf die Kamera zu, bis er das
            Bild fuellt (burst_star). Perspektivisch: 1/Radius laeuft linear (gleichmaessige Annaeherung wirkt wie
            Beschleunigung), die Lage folgt dem Radius. Er dreht weiter, frontal. Der Satz
            bleibt, wo er auf dem Plakat stand, und kippt auf dem Stern in die Grundfarbe (XOR).
    impact  impact_frames Bilder: das letzte burst-Bild in Negativ (Palette umgedreht, siehe digital_frames).
    card    Endkarte im 9:16-Satz: Hypno-Loop. Der Stern wird zum XOR-Nest-Tunnel (card_style), aus der Mitte wachsen
            stetig neue Sterne nach aussen (card_zoom_stars_per_s), alles frontal, 24 fps. Titel, Datum und QR setzen
            nacheinander auf 16teln ein (card_reveal_16ths), nichts steht still."""
    e, n = cfg["endcard"], KL.count(cfg)
    W, H = cfg["video"]["size_px"]
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = digital_offset(cfg)
    x, y, r, rot = KL.star_at(cfg, n - 1)
    per_s = cfg["video"]["cadence"][-1][0] / (4 * beat_s(cfg))                     # Plakatwechsel/s am Karussell-Ende
    spin = cfg["spark"]["spin_deg"] / n * per_s                                    # Grad pro Sekunde wie im Karussell
    phase, t = digital_phase(cfg, dt)
    st = KL.poster_style(cfg, n - 1)
    if phase in ("burst", "impact"):
        fly = e["burst_beats"] * beat_s(cfg)
        u = min(t / fly, 1) if phase == "burst" else 1.0
        x0, y0, r0 = ox + x * pw, oy + y * ph, r * pw
        x1, y1, r1 = e["burst_star"][0] * W, e["burst_star"][1] * H, e["burst_star"][2] * W
        R = 1 / (1 / r0 + u * (1 / r1 - 1 / r0))                                  # gleichmaessige Annaeherung
        f = (R - r0) / (r1 - r0)
        star = (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, R, rot + spin * min(dt, fly))
        st["loop"] = {**st["loop"], "digital": dict(u=0.0, offset=(ox, oy), star=star, show=None)}
    else:
        tq = np.floor(t * e["card_fps"]) / e["card_fps"]                           # auf Zweiern
        cx, cy, cr = e["card_star"]
        star = (cx * W, cy * H, cr * W, rot + spin * e["burst_beats"] * beat_s(cfg) + e["card_spin_deg_per_s"] * tq)
        st["S"] = KL.S_CODES[e["card_style"]]
        st["nest_phase"] = e["card_zoom_stars_per_s"] * tq
        six = 60 / cfg["music"]["grid"]["bpm_end"] / 4                            # 16tel der Endmusik (Maker Night)
        show = [name for name, at in zip(("title", "date", "qr"), e["card_reveal_16ths"]) if t + 1e-6 >= at * six]
        st["loop"] = {**st["loop"], "digital": dict(u=1.0, offset=(ox, oy), star=star, show=show)}
    st["star"] = (star[0] / W, star[1] / H, star[2] / W)
    return boil(cfg, st, dt)


def boil(cfg, st, dt):
    """Boil wie in handgezeichneter Animation, aber im Pixelraster: auf boil_on-teln (Zweier = 12/s bei 24 fps) springt
    der Stern um bis zu boil_cells ganze Zellen und boil_rot_deg Drehung, und das Bayer-Korn verschiebt sich (es
    "kocht", statt stillzustehen). Titel, Datum und QR bleiben stehen (Lesbarkeit, QR). boil_cells = 0: aus.
    Zufall fest pro Zweier-Schritt (gleiche Datei = gleiches Bild), kein Weichzeichnen, keine Zwischenlagen."""
    e = cfg["endcard"]
    if not e["boil_cells"]:
        return st
    k = int(dt * cfg["video"]["timeline_fps"] + 1e-6) // e["boil_on"]
    rng = np.random.default_rng(BOIL_SEED + k)
    px = S.BASE["R"] * S.SIZES["9x16"][2]                                          # Ausgabepixel pro Zelle
    W, H = cfg["video"]["size_px"]
    dy, dx = rng.integers(-e["boil_cells"], e["boil_cells"] + 1, 2) * px
    x, y, r, rot = st["loop"]["digital"]["star"]
    star = (x + dx, y + dy, r, rot + rng.uniform(-1, 1) * e["boil_rot_deg"])
    st["loop"] = {**st["loop"], "digital": {**st["loop"]["digital"], "star": star}}
    st["star"] = (star[0] / W, star[1] / H, star[2] / W)
    st["dither_shift"] = tuple(int(v) for v in rng.integers(0, len(S.bayer(4)), 2)) if e["boil_dither"] else (0, 0)
    return st


def invert(img, P):
    """Negativ auf der Palette: jede Stufe k wird zu N - k (Impact-Frame). Farben ausserhalb der Palette (Zweitlicht)
    gehen auf die naechste Stufe."""
    pal = S.hexpal(P).astype(np.int32)
    idx = ((img[..., None, :].astype(np.int32) - pal) ** 2).sum(-1).argmin(-1)
    return pal[::-1][idx].astype(np.uint8)


def _digital_job(args):
    cfg, dt = args
    st = digital_style(cfg, dt)
    img = KL.render_cached(st, "9x16", "end")
    return invert(img, st["P"]) if digital_phase(cfg, dt)[0] == "impact" else img


def digital_frames(cfg, tl):
    """Alle Bilder des Digitalteils (24 fps). Gleiche Stile (Zweier der Endkarte) nur einmal rendern."""
    fps = cfg["video"]["timeline_fps"]
    dts = [k / fps for k in range(tl.total - tl.zoom_end)]
    key = lambda d: repr([digital_style(cfg, d).get(k) for k in ("nest_phase", "dither_shift")]) \
        + repr(digital_style(cfg, d)["loop"]["digital"]) + digital_phase(cfg, d)[0]                 # noqa: E731
    uniq = {}
    for d in dts:
        uniq.setdefault(key(d), d)
    with Pool() as pool:
        imgs = dict(zip(uniq, pool.map(_digital_job, [(cfg, d) for d in uniq.values()])))
    return [Image.fromarray(imgs[key(d)]) for d in dts]


# ---------------------------------------------------------------- Pruefungen

def luminance(img):
    """Relative Luminanz 0..1 (sRGB linearisiert, Rec. 709), verkleinert auf FLASH_ANALYSIS_PX."""
    a = np.asarray(img.resize(FLASH_ANALYSIS_PX, Image.BOX), np.float32) / 255
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return lin @ KL.LUMA


def flash_check(lum, cfg):
    """WCAG 2.3.1, allgemeine Blitzschwelle, vereinfacht.

    Ein Sprung = Helligkeitsaenderung eines Pixels um mindestens flash_min_delta, wobei das dunklere Bild unter 0.8
    liegt. Ein Blitz = ein Sprung, der gegen die Richtung des vorigen Sprungs desselben Pixels geht (Paar).
    Ein Pixel faellt durch, wenn es in irgendeinem 1-s-Fenster mehr als flash_max_per_s Blitze hat. Verstoss, wenn
    durchgefallene Pixel mehr als flash_max_area_frac des Bildes bedecken. Die Sonderregel fuer rote Blitze fehlt."""
    ch, fps = cfg["checks"], cfg["video"]["timeline_fps"]
    d = np.diff(lum, axis=0)
    darker = np.minimum(lum[1:], lum[:-1])
    step = (np.sign(d) * ((np.abs(d) >= ch["flash_min_delta"]) & (darker < 0.8))).astype(np.int8)
    T = len(step)
    seen = np.where(step != 0, np.arange(T, dtype=np.int32)[:, None, None], -1)
    last = np.maximum.accumulate(seen, axis=0)             # Index des letzten Sprungs bis einschliesslich t
    prev = np.concatenate([np.full((1,) + last.shape[1:], -1, np.int32), last[:-1]])
    prev_sign = np.where(prev >= 0, np.take_along_axis(step, np.maximum(prev, 0), 0), 0)
    flash = (step != 0) & (step == -prev_sign)
    acc = np.concatenate([np.zeros((1,) + flash.shape[1:], np.int32), np.cumsum(flash, 0, dtype=np.int32)])
    per_s = acc[fps:] - acc[:-fps] if T >= fps else acc[-1:]
    area = (per_s > ch["flash_max_per_s"]).mean((1, 2))
    worst = int(area.argmax())
    return dict(ok=bool(area.max() <= ch["flash_max_area_frac"]), worst_area=float(area.max()),
                worst_at_s=worst / fps, max_flashes_per_s=int(per_s.max()))


# ---------------------------------------------------------------- Vorschau

def next_version():
    base = os.path.join(KL.PROJECT, "previz")
    os.makedirs(base, exist_ok=True)
    nums = [int(d[1:]) for d in os.listdir(base) if d[0] == "v" and d[1:].isdigit()]
    path = os.path.join(base, f"v{max(nums, default=0) + 1:03d}")
    os.makedirs(path)
    return path


def song(cfg, tl, path):
    """Musik genau so lang wie das Video (endet auf einem Taktstrich), kurzer Fade gegen den Knack, auf
    [music].loudness_lufs gebracht als feste Verstaerkung: ein Lautheitsregler (loudnorm) wuerde den Sprung vom Aufbau
    in den Drop plattdruecken (Befund Musik-Agent 1.10., B: Drop +6 dB)."""
    import kickoff_loop_music as KM
    m = cfg["music"]
    dur = tl.total / cfg["video"]["timeline_fps"]
    x = KM.decode(os.path.join(KL.PROJECT, m["file"]))[:round(dur * KM.SR)]
    x = x * 10 ** ((m["loudness_lufs"] - KM.lufs(x)) / 20)
    k = round(m["fade_out_s"] * KM.SR)
    x[-k:] *= np.linspace(1, 0, k)[:, None]
    KM.write_wav(path, x)


def ffmpeg_writer(path, size, fps, audio=None):
    """Roh-RGB auf stdin → H.264. Mit Ton: AAC (Pegel stellt song() ein)."""
    W, H = size
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
           "-i", "-"] + (["-i", audio] if audio else []) + \
          ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart"] + \
          (["-c:a", "aac", "-b:a", "256k", "-shortest"] if audio else []) + [path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def contact_sheet(cfg, posters, qr_ok, legib, stills, path):
    """Oben alle Plakate in Loop-Reihenfolge (A = Aushang, Nummer, Stil, Farbe, Warnungen), unten Momente des Videos."""
    font = S.font("DepartureMono-Regular.otf", 22)
    n, cols = len(posters), 8
    pw, ph = posters[0].shape[1] // 4, posters[0].shape[0] // 4
    gap, cap = 16, 56
    vw, vh = (stills[0][1].width // 4, stills[0][1].height // 4) if stills else (0, -cap - gap)
    rows = -(-n // cols)
    sheet = Image.new("RGB", (max(cols * (pw + gap), len(stills) * (vw + gap)), rows * (ph + cap) + vh + cap + gap),
                      (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    for i, img in enumerate(posters):
        x, y = (i % cols) * (pw + gap), (i // cols) * (ph + cap)
        sheet.paste(Image.fromarray(img).resize((pw, ph), Image.BOX), (x, y))
        warn = ("" if qr_ok[i] else " QR!") + ("" if legib[i] >= K.TIER[0] else f" L{legib[i]:.2f}")
        d.text((x, y + ph + 4), f"{'A' if KL.is_key(cfg, i) else ' '} {i + 1:02d} {KL.style_code(cfg, i)}{warn}",
               font=font, fill=(230, 230, 230) if not warn else (255, 120, 90))
        d.text((x, y + ph + 28), KL.station_label(cfg, i), font=font, fill=(140, 140, 150))
    y = rows * (ph + cap) + gap
    for k, (label, im) in enumerate(stills):
        x = k * (vw + gap)
        sheet.paste(im.resize((vw, vh), Image.BOX), (x, y))
        d.text((x, y + vh + 4), label, font=font, fill=(230, 230, 230))
    sheet.save(path)


def sheet(cfg, posters, qr_ok, legib):
    """Schnelle Runde (~15 s statt ~2 min): nur Kontaktbogen + Plakat-Loop im Karusselltempo → previz/now/.
    Fuer Standbild-Entscheidungen; das Video erst mit preview, wenn die Standbilder stehen."""
    out = os.path.join(KL.PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    contact_sheet(cfg, posters, qr_ok, legib, [], os.path.join(out, "contact.png"))
    h, w = posters[0].shape[:2]
    bar_s = 16 * cfg["music"]["grid"]["sixteenth_s"]
    fps = max(per for per, _ in cfg["video"]["cadence"]) / bar_s
    ff = ffmpeg_writer(os.path.join(out, "loop.mp4"), (w // 2, h // 2), fps)
    for img in posters * 4:
        ff.stdin.write(np.asarray(Image.fromarray(img).resize((w // 2, h // 2), Image.BOX)).tobytes())
    ff.stdin.close()
    ff.wait()
    return out


def boil_test(cfg):
    """Boil-Test: Digitalteil (Ausbruch, Impact, Endkarte) ohne | mit Boil nebeneinander, halbe Groesse, mit Musik
    → previz/now/boil.mp4. Schnell (nur der Digitalteil, ~100 Bilder), zum Entscheiden."""
    tl = Timeline(cfg)
    off = {**cfg, "endcard": {**cfg["endcard"], "boil_cells": 0}}
    on = {**cfg, "endcard": {**cfg["endcard"], "boil_cells": cfg["endcard"]["boil_cells"] or 1}}
    a, b = digital_frames(off, tl), digital_frames(on, tl)
    out = os.path.join(KL.PROJECT, "previz", "now")
    os.makedirs(out, exist_ok=True)
    W, H = cfg["video"]["size_px"]
    fps = cfg["video"]["timeline_fps"]
    import kickoff_loop_music as KM
    wav = os.path.join(out, "boil.wav")
    song(cfg, tl, wav)
    part = KM.decode(wav)[round(tl.zoom_end / fps * KM.SR):]
    KM.write_wav(wav, np.concatenate([part, part]))                  # Digitalteil zweimal, wie das Bild
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H // 2}",
                           "-r", str(fps), "-i", "-", "-i", wav, "-c:v", "libx264", "-crf", "16",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", os.path.join(out, "boil.mp4")],
                          stdin=subprocess.PIPE)
    for x, y in zip(a * 2, b * 2):                                  # zweimal hintereinander
        pair = np.hstack([np.asarray(x.resize((W // 2, H // 2), Image.NEAREST)),
                          np.asarray(y.resize((W // 2, H // 2), Image.NEAREST))])
        ff.stdin.write(pair.tobytes())
    ff.stdin.close()
    ff.wait()
    return os.path.join(out, "boil.mp4")


def preview(cfg, posters, qr_ok, legib):
    """Ganze Vorschau in eine neue Version: Video mit Musik, Plakat-Loop allein, Kontaktbogen, Report, Config-Kopie."""
    t0 = time.time()
    out = next_version()
    shutil.copy(KL.CONFIG, os.path.join(out, "loop.toml"))
    n = len(posters)
    tl = Timeline(cfg)
    size = tuple(cfg["video"]["size_px"])
    tfps, bpm = cfg["video"]["timeline_fps"], cfg["loop"]["bpm"]
    bar_s = 16 * cfg["music"]["grid"]["sixteenth_s"]

    # 1. Plakat-Loop allein im schnellsten Karusselltempo, 3 Durchlaeufe (man soll den Neustart sehen)
    h, w = posters[0].shape[:2]
    top_fps = max(per for per, _ in cfg["video"]["cadence"]) / bar_s
    ff = ffmpeg_writer(os.path.join(out, "loop.mp4"), (w // 2, h // 2), top_fps)
    for img in posters * 3:
        ff.stdin.write(np.asarray(Image.fromarray(img).resize((w // 2, h // 2), Image.BOX)).tobytes())
    ff.stdin.close()
    ff.wait()

    # 2. Das Video: Platten → Kamera → Digitalteil, Musik
    plates = [photo_plate(cfg, img, k) for k, img in enumerate(posters)]
    digital = digital_frames(cfg, tl)
    wav = os.path.join(out, "music.wav")
    song(cfg, tl, wav)
    ff = ffmpeg_writer(os.path.join(out, "preview.mp4"), size, tfps, wav)
    fly = round(cfg["endcard"]["burst_beats"] * beat_s(cfg) * tfps)
    card = fly + cfg["endcard"]["impact_frames"]
    marks = {0: "Start", tl.zoom_end // 2: "Zoom Mitte", tl.zoom_end - 1: "Zoom Ende", tl.zoom_end + fly // 2: "Ausbruch",
             tl.zoom_end + fly: "Impact", tl.zoom_end + card + 2: "Endkarte", tl.total - 1: "Ende"}
    stills, lum = [], []
    for t in range(tl.total):
        if t < tl.zoom_end:
            sc, roll = camera(cfg, tl, t, h)
            img = shoot(plates[tl.poster_at(t)], sc, size, roll)
        else:
            img = digital[t - tl.zoom_end]
        ff.stdin.write(np.asarray(img).tobytes())
        lum.append(luminance(img))
        if t in marks:
            stills.append((f"{marks[t]} {t / tfps:.2f}s", img))
    ff.stdin.close()
    ff.wait()

    # 3. Pruefungen, Kontaktbogen, Report
    flash = flash_check(np.array(lum), cfg)
    end_leg = KL.legibility(digital_style(cfg, (tl.total - tl.zoom_end - 1) / tfps), np.asarray(digital[-1]), "9x16")
    contact_sheet(cfg, posters, qr_ok, legib, stills, os.path.join(out, "contact.png"))
    ground = [float(KL.LUMA @ (np.array([int(c[j:j + 2], 16) for j in (1, 3, 5)]) / 255))
              for c in (KL.palette_hex(cfg, i)[0] for i in range(n))]
    real = sum(os.path.exists(aligned_photo(k)) for k in range(n))
    keys = [i for i in range(n) if KL.is_key(cfg, i)]

    def tier(x):                                  # Lesbarkeitsstufe wie bei den Einzelplakaten
        return "A" if x >= K.TIER[0] else "B" if x >= K.TIER[1] else "C"

    cad = " → ".join(f"{bars}x{per}tel" for per, bars in cfg["video"]["cadence"])
    lines = [f"Version {os.path.basename(out)} · {time.strftime('%Y-%m-%d %H:%M')} · {time.time() - t0:.0f} s Renderzeit",
             f"Loop: {n} Frames = {len(keys)} Aushaenge ({' '.join(str(i + 1) for i in keys)}) + {n - len(keys)} "
             f"Zwischenframes (nur Video), {n / top_fps:.2f} s pro Umlauf im schnellsten Tempo",
             f"Musik: {cfg['music']['file']}, Impact {cfg['music']['grid']['impact_s']:.2f} s (Drop), "
             f"{len(tl.changes) / n:.1f} Durchgaenge",
             f"Karussell: {cad} (Takte x Wechsel) bei {bpm} BPM, {len(tl.changes)} Wechsel, "
             f"startet auf Frame {tl.changes[0][1] + 1}, endet auf Frame {tl.changes[-1][1] + 1}",
             f"Video: {tl.total / tfps:.2f} s ({tl.zoom_end / tfps:.1f} Zoom ab 0 s, "
             f"{(tl.total - tl.zoom_end) / tfps:.1f} digital), {size[0]}x{size[1]} @ {tfps} fps,"
             f" echte Fotos: {real}/{n} (Rest simuliert)",
             f"Farbreise: {' → '.join(cfg['color']['stations'])} → {cfg['color']['stations'][0]} "
             f"(OKLab, keine Mischung lila: geprueft in load)",
             f"QR lesbar: {sum(qr_ok)}/{n}" + ("" if all(qr_ok) else "  ! nicht lesbar: "
                                                + " ".join(f"{i + 1:02d}" for i, ok in enumerate(qr_ok) if not ok)),
             f"Lesbarkeit Titel+Datum: {sum(x >= K.TIER[0] for x in legib)}/{n} in Stufe A (>= {K.TIER[0]})"
             + ("" if min(legib) >= K.TIER[0] else "  ! unter A: " + " ".join(
                 f"{i + 1:02d}" for i, x in enumerate(legib) if x < K.TIER[0])),
             f"Endkarte: Lesbarkeit Titel+Datum {end_leg:.2f} {tier(end_leg)}",
             f"Blitz-Check (WCAG 2.3.1, vereinfacht): {'ok' if flash['ok'] else 'VERSTOSS'} · schlimmste Sekunde bei "
             f"{flash['worst_at_s']:.1f} s: {flash['worst_area'] * 100:.0f} % der Flaeche ueber "
             f"{cfg['checks']['flash_max_per_s']} Blitze/s (Grenze {cfg['checks']['flash_max_area_frac'] * 100:.0f} %),"
             f" max. {flash['max_flashes_per_s']} Blitze/s an einer Stelle",
             "", "Frame  Aushang  Farbe               S     Radius Grund  Lesbarkeit"]
    lines += [f"{i + 1:02d}     {'ja' if KL.is_key(cfg, i) else '  '}       {KL.station_label(cfg, i):<19} "
              f"{KL.style_code(cfg, i):<5} {KL.star_at(cfg, i)[2]:.2f}   {g:.2f}   {x:.2f} {tier(x)}"
              for i, (g, x) in enumerate(zip(ground, legib))]
    report = "\n".join(lines) + "\n"
    open(os.path.join(out, "report.txt"), "w", encoding="utf-8").write(report)
    gallery()
    return report + out


def export(cfg, posters):
    """Bausteine fuer den Schnitt in Resolve → kickoff_loop/resolve/ (Dateinamen bleiben gleich, Resolve verlinkt neu):

    plates/NN.png   Platte je Plakat (Foto bzw. Simulation), Plakat mittig, 4 px pro Zelle. Echte Fotos ersetzen sie.
    digital.mov     Digitalteil (Ausbruch, Impact, Endkarte), 1080x1920, 24 fps, ProRes 422 HQ, pixelgenau
    camera.mov      die ganze Foto-Phase mit Kamera, wie in der Vorschau gerechnet (Referenz / Rueckfall)
    song.wav        Song-Ausschnitt, genau so lang wie das Video
    timeline.json   Schnittpunkte (Timeline-Frames), Kamera je Frame, Marker (Takte, Hits, Wechsel)
    Die Kamera steht als Massstab relativ zu "Platte fuellt das Bild" (Fusion-Transform Size) und Rollwinkel."""
    import json
    out = os.path.join(KL.PROJECT, "resolve")
    os.makedirs(os.path.join(out, "plates"), exist_ok=True)
    tl = Timeline(cfg)
    size = tuple(cfg["video"]["size_px"])
    tfps = cfg["video"]["timeline_fps"]
    h = posters[0].shape[0]
    plates = [photo_plate(cfg, img, k) for k, img in enumerate(posters)]
    for k, pl in enumerate(plates):
        pl.save(os.path.join(out, "plates", f"{k + 1:02d}.png"))
    fit = min(size[0] / plates[0].width, size[1] / plates[0].height)       # Massstab "Platte passt ins Bild"

    def prores(path):
        return subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                                 f"{size[0]}x{size[1]}", "-r", str(tfps), "-i", "-", "-c:v", "prores_ks", "-profile:v",
                                 "3", "-pix_fmt", "yuv422p10le", path], stdin=subprocess.PIPE)
    ff = prores(os.path.join(out, "digital.mov"))
    for img in digital_frames(cfg, tl):
        ff.stdin.write(np.asarray(img).tobytes())
    ff.stdin.close()
    ff.wait()
    cam, ff = [], prores(os.path.join(out, "camera.mov"))
    for t in range(tl.zoom_end):
        sc, roll = camera(cfg, tl, t, h)
        cam.append([round(sc / fit, 5), round(float(roll), 4)])
        ff.stdin.write(np.asarray(shoot(plates[tl.poster_at(t)], sc, size, roll)).tobytes())
    ff.stdin.close()
    ff.wait()
    song(cfg, tl, os.path.join(out, "song.wav"))
    info = dict(fps=tfps, size=size, plate_size=[plates[0].width, plates[0].height], total=tl.total,
                zoom_end=tl.zoom_end, hit=tl.hit,
                changes=[dict(frame=f, dur=(tl.changes[j + 1][0] if j + 1 < len(tl.changes) else tl.zoom_end) - f,
                              plate=f"plates/{k + 1:02d}.png") for j, (f, k) in enumerate(tl.changes)],
                camera=dict(unit="Size relativ zu 'Platte passt ins Bild', Rollwinkel in Grad (positiv = Bildinhalt dreht im "
                                 "Uhrzeigersinn, also Fusion-Transform Angle = minus Wert)", per_frame=cam),
                digital=dict(file="digital.mov", start=tl.zoom_end, dur=tl.total - tl.zoom_end),
                markers=[dict(frame=f, color="Red", name=f"Takt {i + 1}") for i, f in enumerate(tl.bars)]
                + [dict(frame=f, color="Sky", name="Hit") for f in tl.punches]
                + [dict(frame=tl.zoom_end, color="Yellow", name="Ausbruch"), dict(frame=tl.hit, color="Yellow",
                                                                                  name="Impact (Bass-Boom)")],
                song=dict(file="song.wav", source=cfg["music"]["file"], bpm=cfg["loop"]["bpm"],
                          bpm_end=cfg["music"]["grid"]["bpm_end"]))
    json.dump(info, open(os.path.join(out, "timeline.json"), "w"), indent=1)
    return f"Resolve-Bausteine in {out}: {len(plates)} Platten, {len(tl.changes)} Wechsel, {tl.total} Frames"


def gallery():
    """kickoff_loop/previz/index.html: alle Versionen, neueste oben (Video, Plakat-Loop, Kontaktbogen, Report)."""
    import html
    base = os.path.join(KL.PROJECT, "previz")
    vs = sorted((d for d in os.listdir(base) if d[0] == "v" and d[1:].isdigit()), reverse=True)
    parts = []
    for v in vs:
        rep = open(os.path.join(base, v, "report.txt"), encoding="utf-8").read() if os.path.exists(
            os.path.join(base, v, "report.txt")) else ""
        parts.append(f'<h2 id="{v}">{v}</h2><div class="row"><video src="{v}/preview.mp4" controls playsinline></video>'
                     f'<video src="{v}/loop.mp4" autoplay loop muted playsinline></video><div><pre>{html.escape(rep)}</pre>'
                     f'<p><a href="{v}/contact.png">Kontaktbogen</a> · <a href="{v}/loop.toml">loop.toml dieser Version</a>'
                     f'</p></div></div>')
    page = f"""<!doctype html><html lang="de"><meta charset="utf-8"><title>Kick-off Loop · Vorschau</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{S.CSS}
.row{{display:grid;grid-template-columns:minmax(0,300px) minmax(0,260px) 1fr;gap:18px;align-items:start}}
video{{width:100%}}pre{{white-space:pre-wrap;font-size:12px;margin:0}}
@media(max-width:900px){{.row{{grid-template-columns:1fr}}}}</style><main><h1>SPARK Kick-off Loop · Vorschau</h1>
<p class="d">Jede Version = ein Lauf von <code>uv run src/kickoff_loop.py preview</code>
mit der loop.toml, die daneben liegt.
Links das Video (mit Musik v1), Mitte der Plakat-Loop allein. Detailvarianten: <a href="variants/">variants/</a>.</p>
{"".join(parts)}</main></html>"""
    open(os.path.join(base, "index.html"), "w", encoding="utf-8").write(page)
