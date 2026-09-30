"""Video-Teil des Kick-off-Loops: Plakat-Frames → Fotos (bis dahin Simulation) → Loop + Zoom + Endkarte → Vorschau.

Aufgerufen ueber `uv run src/kickoff_loop.py preview`.
Alle Werte aus kickoff_loop/loop.toml ([video], [simulation], [checks]).

Zeitachse in Timeline-Frames (video.timeline_fps), alles auf dem Taktraster von loop.bpm (class Timeline):
  | hold_bars Takte stehend | Rest der cadence: Zoom, Karussell bremst | endcard_s Sekunden Endkarte (digital) |

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
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

import kickoff as K
import kickoff_loop as KL
import styles as S

AUDIO_RATE = 48000
FLASH_ANALYSIS_PX = (68, 120)        # Blitz-Check auf 1/16: ein Block = 16 px = eine Bayer-Periode am Zoom-Ende (kein Moire)


# ---------------------------------------------------------------- Zeitachse und Kamera

class Timeline:
    """Die Zeitachse in Timeline-Frames, aus [video].cadence und [loop].bpm.

    changes   Plakatwechsel als (Frame, Plakat-Index), Plakate laufen reihum weiter (auch ueber Loop-Grenzen)
    hold_end  Ende des Abschnitts ohne Zoom
    zoom_end  Ende des Karussells = Ende des Zooms = Wechsel ins Digitale
    total     Ende der Endkarte"""

    def __init__(self, cfg):
        v, n = cfg["video"], KL.count(cfg)
        self.bar = int(KL.frames_per_bar(cfg))
        self.changes, t, k = [], 0, 0
        for per_bar, bars in v["cadence"]:
            for _ in range(per_bar * bars):
                self.changes.append((t, k % n))
                t += self.bar // per_bar
                k += 1
        self.hold_end = v["hold_bars"] * self.bar
        self.zoom_end = t
        self.total = t + round(v["endcard_s"] * v["timeline_fps"])
        self._starts = [f for f, _ in self.changes]

    def poster_at(self, t):
        """Welches Plakat im Frame t zu sehen ist (in der Endkarte: das, auf dem das Karussell stehen blieb)."""
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
    """Massstab im Timeline-Frame t (nur fuer die Foto-Phase). Exponentiell interpoliert: jeder Frame vergroessert um
    denselben Faktor, so wirkt ein Zoom gleichmaessig. zoom_curve formt darauf Anfahren und Abbremsen.
    Der letzte Karussell-Frame erreicht genau den Endmassstab."""
    s0, s1 = scales(cfg, poster_h)
    if cfg["video"]["zoom_stepped"]:
        t = tl.change_before(t)                           # Kamera springt nur, wenn das Plakat wechselt
    u = np.clip((t - tl.hold_end) / max(tl.zoom_end - 1 - tl.hold_end, 1), 0, 1)
    return s0 * (s1 / s0) ** KL.EASE[cfg["video"]["zoom_curve"]](u)


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
    img = Image.fromarray(np.clip(np.asarray(img, np.float32) + grain, 0, 255).astype(np.uint8))

    s = Image.fromarray(poster).convert("RGBA").rotate(rng.normal(0, sim["jitter_rot_deg"]), Image.BICUBIC, expand=True)
    jx, jy = rng.normal(0, sim["jitter_px"], 2)
    x0 = round((PW - s.width) / 2 + jx)
    y0 = round((PH - s.height) / 2 + jy)
    shadow = Image.new("L", (PW, PH), 0)
    shadow.paste(s.getchannel("A").point(lambda v: v * 0.55), (x0 + 10, y0 + 16))
    img.paste((0, 0, 0), (0, 0), shadow.filter(ImageFilter.GaussianBlur(14)))
    img.paste(s, (x0, y0), s)
    return img


def aligned_photo(k):
    return os.path.join(KL.PROJECT, "photos", "aligned", f"{k + 1:02d}.png")


def photo_plate(cfg, poster, k):
    """Echtes, entzerrtes Foto, falls vorhanden (kickoff_loop/photos/aligned/NN.png), sonst Simulation."""
    path = aligned_photo(k)
    if os.path.exists(path):
        return Image.open(path).convert("RGB")
    return simulated_plate(cfg, poster, k)


def shoot(plate, s, size):
    """Kameraausschnitt: Plattenmitte, Massstab s (Plattenpixel → Ausgabepixel), auf size skaliert.
    Bei s = 1 und ganzzahliger Lage ist das eine 1:1-Kopie, deshalb ist das Zoom-Ende pixelgenau."""
    W, H = size
    cx, cy = plate.width / 2, plate.height / 2
    box = (cx - W / 2 / s, cy - H / 2 / s, cx + W / 2 / s, cy + H / 2 / s)
    return plate.resize(size, Image.LANCZOS, box=box)


def endcard(cfg, poster, k):
    """v0-Platzhalter: das digitale Plakat im Endmassstab, Rest des Bildes in der Grundfarbe seiner Colorway.
    Hier entsteht spaeter die eigentliche Endkarte (Ort, Zeit, mehr Info, im selben Stop-Motion-Stil)."""
    W, H = cfg["video"]["size_px"]
    p = S.hexpal(KL.P_CODES[cfg["posters"]["frames"][k][0]])[0].astype(int)
    canvas = Image.new("RGB", (W, H), tuple(p))
    im = Image.fromarray(poster)
    s = cfg["video"]["end_cell_px"] / KL.PREVIEW_CELL_PX
    if s != 1:
        im = im.resize((round(im.width * s), round(im.height * s)), Image.NEAREST)
    canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    return canvas


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


# ---------------------------------------------------------------- Temp-Ton

def temp_audio(cfg, tl, path):
    """Timing-Spur (ersetzt spaeter die Musik): Klick pro Plakatwechsel, Akzent auf Plakat 01 (Loop-Anfang),
    tiefer Schlag beim Wechsel ins Digitale. Nur zum Beurteilen des Rhythmus, kein Sounddesign."""
    tfps, total = cfg["video"]["timeline_fps"], tl.total
    out = np.zeros(round(total / tfps * AUDIO_RATE) + AUDIO_RATE, np.float32)
    rng = np.random.default_rng(0)
    tick_t = np.arange(round(0.012 * AUDIO_RATE)) / AUDIO_RATE
    tick = np.diff(rng.standard_normal(len(tick_t) + 1)).astype(np.float32) * np.exp(-tick_t / 0.002)
    blip_t = np.arange(round(0.05 * AUDIO_RATE)) / AUDIO_RATE
    blip = np.sin(2 * np.pi * 1760 * blip_t) * np.exp(-blip_t / 0.012)
    for f, k in tl.changes:
        i = round(f / tfps * AUDIO_RATE)
        out[i:i + len(tick)] += 0.25 * tick
        if k == 0:
            out[i:i + len(blip)] += 0.35 * blip
    boom_t = np.arange(round(0.6 * AUDIO_RATE)) / AUDIO_RATE
    boom = np.sin(2 * np.pi * np.cumsum(40 + 60 * np.exp(-boom_t / 0.05)) / AUDIO_RATE) * np.exp(-boom_t / 0.2)
    i = round(tl.zoom_end / tfps * AUDIO_RATE)
    out[i:i + len(boom)] += 0.8 * boom
    out = out[:round(total / tfps * AUDIO_RATE)]
    pcm = (np.clip(out / max(np.abs(out).max(), 1e-9) * 0.8, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(AUDIO_RATE)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- Vorschau

def next_version():
    base = os.path.join(KL.PROJECT, "previz")
    os.makedirs(base, exist_ok=True)
    nums = [int(d[1:]) for d in os.listdir(base) if d[0] == "v" and d[1:].isdigit()]
    path = os.path.join(base, f"v{max(nums, default=0) + 1:03d}")
    os.makedirs(path)
    return path


def ffmpeg_writer(path, size, fps, audio=None):
    W, H = size
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
           "-i", "-"] + (["-i", audio] if audio else []) + \
          ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart"] + \
          (["-c:a", "aac", "-b:a", "192k", "-shortest"] if audio else []) + [path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def contact_sheet(cfg, posters, qr_ok, legib, stills, path):
    """Oben alle Plakate in Loop-Reihenfolge (Nummer, Codes, QR, Lesbarkeit, Codename), unten Momente des Videos."""
    font = S.font("DepartureMono-Regular.otf", 22)
    n, cols = len(posters), 8
    pw, ph = posters[0].shape[1] // 4, posters[0].shape[0] // 4
    gap, cap = 16, 56
    vw, vh = stills[0][1].width // 4, stills[0][1].height // 4
    rows = -(-n // cols)
    sheet = Image.new("RGB", (max(cols * (pw + gap), len(stills) * (vw + gap)), rows * (ph + cap) + vh + cap + gap),
                      (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    for i, img in enumerate(posters):
        x, y = (i % cols) * (pw + gap), (i // cols) * (ph + cap)
        sheet.paste(Image.fromarray(img).resize((pw, ph), Image.BOX), (x, y))
        p, s = cfg["posters"]["frames"][i]
        warn = ("" if qr_ok[i] else " QR!") + ("" if legib[i] >= K.TIER[0] else f" L{legib[i]:.2f}")
        d.text((x, y + ph + 4), f"{i + 1:02d} {p} {s}{warn}", font=font,
               fill=(230, 230, 230) if not warn else (255, 120, 90))
        d.text((x, y + ph + 28), S.CODENAME[KL.P_CODES[p]], font=font, fill=(140, 140, 150))
    y = rows * (ph + cap) + gap
    for k, (label, im) in enumerate(stills):
        x = k * (vw + gap)
        sheet.paste(im.resize((vw, vh), Image.BOX), (x, y))
        d.text((x, y + vh + 4), label, font=font, fill=(230, 230, 230))
    sheet.save(path)


def preview(cfg, posters, qr_ok, legib):
    """Ganze Vorschau in eine neue Version: Video mit Temp-Ton, Plakat-Loop allein, Kontaktbogen, Report, Config-Kopie."""
    t0 = time.time()
    out = next_version()
    shutil.copy(KL.CONFIG, os.path.join(out, "loop.toml"))
    n = len(posters)
    tl = Timeline(cfg)
    size = tuple(cfg["video"]["size_px"])
    tfps, bpm = cfg["video"]["timeline_fps"], cfg["loop"]["bpm"]
    bar_s = tl.bar / tfps

    # 1. Plakat-Loop allein im schnellsten Karusselltempo, 3 Durchlaeufe (man soll den Neustart sehen)
    h, w = posters[0].shape[:2]
    top_fps = max(per for per, _ in cfg["video"]["cadence"]) / bar_s
    ff = ffmpeg_writer(os.path.join(out, "loop.mp4"), (w // 2, h // 2), top_fps)
    for img in posters * 3:
        ff.stdin.write(np.asarray(Image.fromarray(img).resize((w // 2, h // 2), Image.BOX)).tobytes())
    ff.stdin.close()
    ff.wait()

    # 2. Das Video: Platten → Kamera → Endkarte
    plates = [photo_plate(cfg, img, k) for k, img in enumerate(posters)]
    wav = os.path.join(out, "temp_click.wav")
    temp_audio(cfg, tl, wav)
    ff = ffmpeg_writer(os.path.join(out, "preview.mp4"), size, tfps, wav)
    marks = {0: "Start", tl.hold_end: "Zoom an", (tl.hold_end + tl.zoom_end) // 2: "Zoom Mitte",
             tl.zoom_end - 1: "Zoom Ende", tl.zoom_end: "Endkarte"}
    stills, lum = [], []
    for t in range(tl.total):
        k = tl.poster_at(t)
        img = shoot(plates[k], camera(cfg, tl, t, h), size) if t < tl.zoom_end else endcard(cfg, posters[k], k)
        ff.stdin.write(np.asarray(img).tobytes())
        lum.append(luminance(img))
        if t in marks:
            stills.append((f"{marks[t]} {t / tfps:.2f}s", img))
    ff.stdin.close()
    ff.wait()

    # 3. Pruefungen, Kontaktbogen, Report
    flash = flash_check(np.array(lum), cfg)
    contact_sheet(cfg, posters, qr_ok, legib, stills, os.path.join(out, "contact.png"))
    ground = [float(KL.LUMA @ (S.hexpal(KL.P_CODES[p])[0] / 255)) for p, _ in cfg["posters"]["frames"]]
    real = sum(os.path.exists(aligned_photo(k)) for k in range(n))

    def tier(x):                                  # Lesbarkeitsstufe wie bei den Einzelplakaten
        return "A" if x >= K.TIER[0] else "B" if x >= K.TIER[1] else "C"

    cad = " → ".join(f"{bars}x{per}tel" for per, bars in cfg["video"]["cadence"])
    lines = [f"Version {os.path.basename(out)} · {time.strftime('%Y-%m-%d %H:%M')} · {time.time() - t0:.0f} s Renderzeit",
             f"Karussell: {n} Plakate, {cad} (Takte x Wechsel) bei {bpm} BPM, Loop im schnellsten Tempo "
             f"{n / top_fps:.2f} s = {n / top_fps * bpm / 60:g} Schlaege",
             f"Video: {tl.total / tfps:.2f} s ({tl.hold_end / tfps:.1f} stehend, "
             f"{(tl.zoom_end - tl.hold_end) / tfps:.1f} Zoom, {(tl.total - tl.zoom_end) / tfps:.1f} Endkarte),"
             f" {size[0]}x{size[1]} @ {tfps} fps, bleibt stehen auf Plakat {tl.poster_at(tl.zoom_end) + 1:02d},"
             f" echte Fotos: {real}/{n} (Rest simuliert)",
             f"QR lesbar: {sum(qr_ok)}/{n}" + ("" if all(qr_ok) else "  ! nicht lesbar: "
                                                + " ".join(f"{i + 1:02d}" for i, ok in enumerate(qr_ok) if not ok)),
             f"Lesbarkeit Titel+Datum: {sum(x >= K.TIER[0] for x in legib)}/{n} in Stufe A (>= {K.TIER[0]})"
             + ("" if min(legib) >= K.TIER[0] else "  ! unter A: " + " ".join(
                 f"{i + 1:02d}" for i, x in enumerate(legib) if x < K.TIER[0])),
             f"Blitz-Check (WCAG 2.3.1, vereinfacht): {'ok' if flash['ok'] else 'VERSTOSS'} · schlimmste Sekunde bei "
             f"{flash['worst_at_s']:.1f} s: {flash['worst_area'] * 100:.0f} % der Flaeche ueber "
             f"{cfg['checks']['flash_max_per_s']} Blitze/s (Grenze {cfg['checks']['flash_max_area_frac'] * 100:.0f} %),"
             f" max. {flash['max_flashes_per_s']} Blitze/s an einer Stelle",
             "", "Plakat  P    S     Codename          Grund  Lesbarkeit"]
    lines += [f"{i + 1:02d}      {p:<4} {s:<5} {S.CODENAME[KL.P_CODES[p]]:<17} {g:.2f}   {x:.2f} {tier(x)}"
              for i, ((p, s), g, x) in enumerate(zip(cfg["posters"]["frames"], ground, legib))]
    report = "\n".join(lines) + "\n"
    open(os.path.join(out, "report.txt"), "w", encoding="utf-8").write(report)
    gallery()
    return report + out


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
Links das Video (mit Temp-Klick), Mitte der Plakat-Loop allein. Detailvarianten: <a href="variants/">variants/</a>.</p>
{"".join(parts)}</main></html>"""
    open(os.path.join(base, "index.html"), "w", encoding="utf-8").write(page)
