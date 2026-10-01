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
RED_SAT_FRAC = 0.8                   # WCAG 2.2 / ISO 9241-391: Zustand "gesaettigtes Rot" ab R/(R+G+B) >= 0.8 (linear)
RED_MIN_UV = 0.2                     # ... und ein Rot-Uebergang braucht mehr als 0.2 Abstand in der CIE-1976-Farbtafel
SRGB_XYZ = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], np.float32)  # D65
WHITE_UV = (0.1978, 0.4683)          # u', v' von D65: Schwarz hat keine Farbart, gilt als unbunt


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
        v, g, n = cfg["video"], cfg["music"]["grid"], KL.posters(cfg)   # alle Welten, nicht nur ein Umlauf
        fps = v["timeline_fps"]
        bar = 16 * g["sixteenth_s"]
        times, t = [], 0.0
        for per, bars in v["cadence"]:                    # aus load(): Raster oder [loop].changes_per_bar (T16)
            for _ in range(per * bars):
                times.append(t)
                t += bar / per
        times = [x for x in times if x < g["burst_s"] - 1e-6]
        if cfg.get("ending", {}).get("runout_bars"):           # Auslauf: ein Umlauf bremst bis zum Landetakt ab
            import kickoff_loop_end as KE
            times = [x for x in times if x < KE.runout_times(cfg)[0] - 1e-6] + KE.runout_times(cfg)
        first = (end_index(cfg) + 1 - len(times)) % n         # letzter Wechsel = [endcard].end_frame
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
    if cfg.get("ending", {}).get("runout_bars"):              # Auslauf: Kamera bremst mit dem Rad (kickoff_loop_end)
        import kickoff_loop_end as KE
        u = KE.camera_u(cfg, tl, tz)
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


def end_index(cfg):
    """Index des Frames, auf dem das Karussell endet ([endcard].end_frame, 1-basiert; ohne Angabe der letzte des Loops).
    B20c: F1 = Stern frontal, riesig, genau mittig (x 0.50, y 0.50, Radius 1.76), Einstieg in den Infinite Zoom."""
    n = KL.count(cfg)
    return (cfg["endcard"].get("end_frame", n) - 1) % n


def digital_phase(cfg, dt):
    """Abschnitt des Digitalteils dt Sekunden nach dem Wechsel: ("burst" | "impact" | "card" | "zoom", Zeit im
    Abschnitt). Ausbruch und Impact sind schaltbar (burst_on, impact_on), danach end_mode (card = Nest-Tunnel-Platzhalter,
    zoom = Infinite Zoom in den Stern, Z1-Z3)."""
    e, b = cfg["endcard"], beat_s(cfg)
    fly = e["burst_beats"] * b                                   # die Luft vor dem Drop, auch ohne Ausbruch: Impact = Drop
    hit = e["impact_frames"] / cfg["video"]["timeline_fps"]
    mode, burst, impact = e.get("end_mode", "card"), e.get("burst_on", True), e.get("impact_on", True)
    if mode == "words":                                          # Begriffe (kickoff_loop_end), ab dem Karussell-Ende
        return "words", dt
    if burst and dt < fly:
        return "burst", dt
    if impact and fly <= dt < fly + hit:
        return "impact", dt - fly
    start = zoom_times(cfg)[0] if mode == "zoom" else fly + hit  # Zoom ohne Ausbruch laeuft vom Karussell-Ende an
    return mode, dt - start


def last_star(cfg):
    """Frame, von dem der Digitalteil ausgeht: der Endframe des Karussells, falls er einen Stern hat, sonst der letzte
    davor mit Stern (leere Frames haben keinen Ausbruch, 1/Radius waere durch null)."""
    n, end = KL.count(cfg), end_index(cfg)
    return next((end - k) % n for k in range(n) if KL.star_at(cfg, (end - k) % n)[2] > 0)


ZOOM_KEYS = ("end_frame", "burst_on", "impact_on", "zoom_dolls", "zoom_ease", "zoom_ease_pow", "zoom_spin_deg_per_s",
             "zoom_center", "core_shrink", "type_out_beats", "fade_beats", "info", "info_at_beats", "info_in_beats",
             "info_cap_cells", "info_lead_frac", "info_y_frac")


def check_zoom(cfg):
    """[endcard] fuer end_mode = "zoom" pruefen, bevor gerendert wird (load() in kickoff_loop.py kennt die Schluessel nicht)."""
    e = cfg["endcard"]
    miss = [k for k in ZOOM_KEYS if k not in e]
    assert not miss, f"[endcard] end_mode = zoom braucht noch: {', '.join(miss)}"
    assert e["zoom_ease"] in ("ease_in", "ease_out", "linear"), "[endcard].zoom_ease: ease_in | ease_out | linear"
    assert e["zoom_dolls"] > 0 and e["zoom_ease_pow"] >= 1, "[endcard]: zoom_dolls > 0, zoom_ease_pow >= 1"
    assert 1 <= e["end_frame"] <= KL.count(cfg), f"[endcard].end_frame: 1..{KL.count(cfg)}"
    assert KL.star_at(cfg, e["end_frame"] - 1)[2] > 0, f"[endcard].end_frame F{e['end_frame']} ist leer (kein Stern)"
    assert KL.style_code(cfg, e["end_frame"] - 1) == "S33", \
        f"[endcard].end_frame F{e['end_frame']}: Zoom braucht S33 (Matrjoschka), dort steht {KL.style_code(cfg, e['end_frame'] - 1)}"


def zoom_times(cfg):
    """(Zoom-Beginn nach dem Wechsel ins Digitale, Zoom-Dauer, Fade-Beginn ab Zoom-Beginn) in Sekunden. Ende = end_s des
    Rasters; Fade to Black ab fade_s des Rasters, falls der Musik-Agent eins schreibt, sonst fade_beats vor dem Ende."""
    e, g, b = cfg["endcard"], cfg["music"]["grid"], beat_s(cfg)
    start = 0.0                                                # ohne Ausbruch: ab dem letzten Plakat, Impact = Negativ
    if e.get("burst_on", True):                                # des Zoombilds auf dem Drop; mit Ausbruch: danach
        start = e["burst_beats"] * b + (e["impact_frames"] / cfg["video"]["timeline_fps"] if e.get("impact_on", True) else 0)
    dur = g["end_s"] - g["burst_s"] - start
    fade = dur - e["fade_beats"] * b                           # Schwarz in den letzten fade_beats vor end_s, aber nie
    if "fade_from_s" in g:                                     # vor dem Ausklang der Musik (M3: fade_from_s..end_s)
        fade = max(fade, g["fade_from_s"] - g["burst_s"] - start)
    return start, dur, fade


def zoom_state(cfg, t):
    """Zoom t Sekunden nach seinem Beginn: dict(dolls, u) mit u = Anteil der Zoomdauer, dolls = getauchte Puppen."""
    import kickoff_loop_digital as KD
    e = cfg["endcard"]
    _, dur, _ = zoom_times(cfg)
    u = min(max(t / dur, 0.0), 1.0)
    return dict(u=u, dolls=e["zoom_dolls"] * KD.ease(e["zoom_ease"], e["zoom_ease_pow"], u))


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
    if e.get("end_mode") == "words":
        import kickoff_loop_end as KE
        return KE.words_state(cfg, dt)
    W, H = cfg["video"]["size_px"]
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = digital_offset(cfg)
    last = last_star(cfg)
    x, y, r, rot = KL.star_at(cfg, last)
    per_s = cfg["video"]["cadence"][-1][0] / (4 * beat_s(cfg))                     # Plakatwechsel/s am Karussell-Ende
    spin = cfg["spark"]["spin_deg"] / n * per_s                                    # Grad pro Sekunde wie im Karussell
    phase, t = digital_phase(cfg, dt)
    st = KL.poster_style(cfg, last)
    if phase == "impact" and e.get("end_mode") == "zoom" and not e.get("burst_on", True):
        phase, t = "zoom", dt - zoom_times(cfg)[0]                                # Negativ des Zoombilds (_digital_job)
    if phase in ("burst", "impact"):
        fly = e["burst_beats"] * beat_s(cfg)
        u = min(t / fly, 1) if phase == "burst" else 1.0
        x0, y0, r0 = ox + x * pw, oy + y * ph, r * pw
        x1, y1, r1 = e["burst_star"][0] * W, e["burst_star"][1] * H, e["burst_star"][2] * W
        R = 1 / (1 / r0 + u * (1 / r1 - 1 / r0))                                  # gleichmaessige Annaeherung
        f = (R - r0) / (r1 - r0)
        star = (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, R, rot + spin * min(dt, fly))
        st["loop"] = {**st["loop"], "digital": dict(u=0.0, offset=(ox, oy), star=star, show=None)}
    elif phase == "zoom":                                                          # Infinite Zoom (Z1-Z3)
        import kickoff_loop_digital as KD
        b, zs = beat_s(cfg), zoom_state(cfg, t)
        _, dur, fade_at = zoom_times(cfg)
        last = dur - 1 / cfg["video"]["timeline_fps"]                             # letztes Bild = ganz schwarz (Zoom-Check
        pre = dt - t                                                              # Ausbruch + Impact davor (0 = aus)
        if e.get("burst_on", True):                                                # Zoom startet, wo der Ausbruch endet
            x0, y0, r0 = e["burst_star"][0] * W, e["burst_star"][1] * H, e["burst_star"][2] * W
        else:                                                                      # ... sonst genau im letzten Plakat
            x0, y0, r0 = ox + x * pw, oy + y * ph, r * pw
        k = zs["dolls"] / e["zoom_dolls"]                                          # Mitte wandert mit dem Zoom
        cx, cy = x0 + (e["zoom_center"][0] * W - x0) * k, y0 + (e["zoom_center"][1] * H - y0) * k
        star = (cx, cy, r0 / KD.DOLL_RATIO ** zs["dolls"],
                rot + spin * min(pre, e["burst_beats"] * b) + e["zoom_spin_deg_per_s"] * t)
        clip = lambda v: float(min(max(v, 0.0), 1.0))                              # noqa: E731
        zoom = dict(dolls=round(zs["dolls"], 6), core_shrink=e["core_shrink"],
                    type_out=clip(t / (e["type_out_beats"] * b)) if e["type_out_beats"] else 1.0,
                    info=list(e["info"]), info_in=clip((t - e["info_at_beats"] * b) / (e["info_in_beats"] * b)),
                    info_cap_cells=e["info_cap_cells"], info_lead_frac=e["info_lead_frac"], info_y_frac=e["info_y_frac"])
        card = None
        if cfg.get("ending", {}).get("card_on"):                                  # Endkarte im Zoom (Z5)
            import kickoff_loop_end as KE
            card = KE.card_state(cfg, dt)
        st.update(spark_fn=KD.zoom_spark, type_fn=zoom_card_type)
        st["loop"] = {**st["loop"], "digital": dict(u=0.0, offset=(ox, oy), star=star, show=None, zoom=zoom, card=card,
                                                    black=0.0 if card else clip((t - fade_at) / max(last - fade_at, 1e-6)))}
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


def zoom_card_type(c):
    """Satz im Zoom (kickoff_loop_digital.zoom_type), darueber die Endkarte, falls [ending].card_on."""
    import kickoff_loop_digital as KD
    KD.zoom_type(c)
    if c.st["loop"]["digital"].get("card"):
        import kickoff_loop_end as KE
        KE.card_layers(c, c.st["loop"]["digital"]["card"])


ZOOM_JUMP_FACTOR = 3.0   # Zoom-Check: ein Bildwechsel gilt als Sprung, wenn er mehr als 3x so viel aendert wie der Median


def zoom_check(cfg, tl, digital, last_poster):
    """Befund am fertigen Bild: (1) stetig = kein Bildwechsel im Zoom aendert mehr als ZOOM_JUMP_FACTOR x den Median
    (mittlere Helligkeitsaenderung, auf FLASH_ANALYSIS_PX), Impact-Bilder (gewollt) ausgenommen, der Wechsel letztes
    Plakat → erstes Zoombild zaehlt mit (nahtlos); (2) das letzte Bild ist wirklich #000. Gegenprobe (schlaegt der
    Test an?): ein Zoombild mit einer halben Puppe Versatz muss als Sprung auffallen."""
    fps = cfg["video"]["timeline_fps"]
    phases = [digital_phase(cfg, k / fps)[0] for k in range(len(digital))]
    lum = [luminance(Image.fromarray(np.asarray(last_poster)))] + [luminance(im) for im in digital]
    ok_idx = [k for k in range(len(digital)) if phases[k] != "impact" and (k == 0 or phases[k - 1] != "impact")]
    steps = np.array([float(np.abs(lum[k + 1] - lum[k]).mean()) for k in ok_idx])
    med = float(np.median(steps))
    worst = int(steps.argmax())
    black = int(np.asarray(digital[-1]).max())
    # Gegenprobe: dasselbe Bild mit +0.5 Puppen (halbe Schale Versatz) gegen das echte Nachbarbild
    k = len(digital) // 2
    st = digital_style(cfg, k / fps)
    zm = st["loop"]["digital"]["zoom"]
    bad = {**st, "loop": {**st["loop"], "digital": {**st["loop"]["digital"], "black": 0.0, "zoom": {**zm, "dolls": zm["dolls"] + 0.5}}}}
    x, y, R, rot = bad["loop"]["digital"]["star"]
    import kickoff_loop_digital as KD
    bad["loop"]["digital"]["star"] = (x, y, R / KD.DOLL_RATIO ** 0.5, rot)
    good = KL.render_cached({**st, "loop": {**st["loop"], "digital": {**st["loop"]["digital"], "black": 0.0}}}, "9x16", "end")
    jump = float(np.abs(luminance(Image.fromarray(KL.render_cached(bad, "9x16", "end"))) - luminance(Image.fromarray(good))).mean())
    bites = jump > ZOOM_JUMP_FACTOR * med
    card = bool(cfg.get("ending", {}).get("card_on"))                  # mit Endkarte endet es nicht schwarz
    ok = steps.max() <= ZOOM_JUMP_FACTOR * med and (black == 0 or card) and bites
    return (f"Zoom-Check {'ok' if ok else 'FEHLER'}: Bildwechsel im Zoom median {med:.4f}, max {steps.max():.4f} "
            f"(x{steps.max() / max(med, 1e-9):.1f}, Grenze x{ZOOM_JUMP_FACTOR:.0f}) bei Zoombild {ok_idx[worst]}"
            f"{' = Plakat → Zoom' if ok_idx[worst] == 0 else ''}, Plakat → erstes Zoombild {steps[0]:.4f}; "
            f"letztes Bild {'Endkarte' if card else f'max. Wert {black} (' + ('schwarz' if black == 0 else 'NICHT schwarz') + ')'}; "
            f"Gegenprobe halbe Puppe Versatz {jump:.4f} = x{jump / max(med, 1e-9):.1f} ({'schlaegt an' if bites else 'TEST BLIND'})")


def zoom_sheet(cfg, tl, digital, last_poster, path, n=10):
    """Kontaktbogen des Zooms: letztes Plakat + n Schluesselbilder gleichmaessig ueber den Digitalteil, beschriftet mit
    Zeit, Abschnitt und Puppen-Tiefe."""
    fps = cfg["video"]["timeline_fps"]
    idx = [round(j * (len(digital) - 1) / (n - 1)) for j in range(n)]
    W, H = digital[0].size
    tw, th, cap, gap = W // 4, H // 4, 40, 12
    font = S.font("DepartureMono-Regular.otf", 22)
    sheet = Image.new("RGB", ((n + 1) * (tw + gap), th + cap), (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    items = [(f"F{end_index(cfg) + 1} {(tl.zoom_end - 1) / fps:.2f}s", last_poster)]
    for k in idx:
        ph, t = digital_phase(cfg, k / fps)
        st = digital_style(cfg, k / fps)
        z = (st["loop"]["digital"].get("zoom") or {}).get("dolls", 0)
        items.append((f"{(tl.zoom_end + k) / fps:.2f}s {ph[:4]} z{z:.1f}", digital[k]))
    for j, (label, im) in enumerate(items):
        sheet.paste(im.resize((tw, th), Image.BOX), (j * (tw + gap), 0))
        d.text((j * (tw + gap), th + 8), label, font=font, fill=(230, 230, 230))
    sheet.save(path)
    return path


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
    if digital_phase(cfg, dt)[0] == "impact":
        return invert(img, st["P"])
    import kickoff_loop_digital as KD                                  # Fade to Black im Korn (Zoom), 0 = nichts
    return KD.blackout(img, st["loop"]["digital"].get("black", 0.0), S.BASE["R"] * S.SIZES["9x16"][2])


def digital_frames(cfg, tl):
    """Alle Bilder des Digitalteils (24 fps). Gleiche Stile (Zweier der Endkarte) nur einmal rendern."""
    fps = cfg["video"]["timeline_fps"]
    if cfg["endcard"].get("end_mode", "card") == "zoom":
        check_zoom(cfg)
    dts = [k / fps for k in range(tl.total - tl.zoom_end)]
    key = lambda d: repr([digital_style(cfg, d).get(k) for k in ("nest_phase", "dither_shift", "P")]) \
        + repr(digital_style(cfg, d)["loop"]["digital"]) + digital_phase(cfg, d)[0]                 # noqa: E731
    uniq = {}
    for d in dts:
        uniq.setdefault(key(d), d)
    with Pool() as pool:
        imgs = dict(zip(uniq, pool.map(_digital_job, [(cfg, d) for d in uniq.values()])))
    return [Image.fromarray(imgs[key(d)]) for d in dts]


# ---------------------------------------------------------------- Pruefungen

def linear_rgb(img):
    """sRGB linearisiert 0..1, verkleinert auf FLASH_ANALYSIS_PX."""
    a = np.asarray(img.resize(FLASH_ANALYSIS_PX, Image.BOX), np.float32) / 255
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def luminance(img):
    """Relative Luminanz 0..1 (sRGB linearisiert, Rec. 709), verkleinert auf FLASH_ANALYSIS_PX."""
    return linear_rgb(img) @ KL.LUMA


def chroma_state(img):
    """Fuer die Rot-Regel je Analysepixel [gesaettigt rot 0/1, u', v'] (CIE 1976 UCS), verkleinert wie luminance."""
    lin = linear_rgb(img)
    red = lin[..., 0] >= RED_SAT_FRAC * np.maximum(lin.sum(-1), 1e-6)
    X, Y, Z = np.moveaxis(lin @ SRGB_XYZ.T, -1, 0)
    den = X + 15 * Y + 3 * Z
    ok = den > 1e-6
    u = np.where(ok, 4 * X / np.where(ok, den, 1), WHITE_UV[0])
    v = np.where(ok, 9 * Y / np.where(ok, den, 1), WHITE_UV[1])
    return np.stack([red & ok, u, v], -1).astype(np.float32)


def _flashes_per_s(step, fps):
    """Spruenge je Bild und Pixel (+1, -1, 0) → Blitze pro 1-s-Fenster. Ein Blitz = ein Sprung gegen die Richtung des
    vorigen Sprungs desselben Pixels (Paar gegenlaeufiger Uebergaenge)."""
    T = len(step)
    seen = np.where(step != 0, np.arange(T, dtype=np.int32)[:, None, None], -1)
    last = np.maximum.accumulate(seen, axis=0)             # Index des letzten Sprungs bis einschliesslich t
    prev = np.concatenate([np.full((1,) + last.shape[1:], -1, np.int32), last[:-1]])
    prev_sign = np.where(prev >= 0, np.take_along_axis(step, np.maximum(prev, 0), 0), 0)
    flash = (step != 0) & (step == -prev_sign)
    acc = np.concatenate([np.zeros((1,) + flash.shape[1:], np.int32), np.cumsum(flash, 0, dtype=np.int32)])
    return acc[fps:] - acc[:-fps] if T >= fps else acc[-1:]


def red_steps(chroma):
    """Rot-Uebergaenge je Bild und Pixel: +1 ins gesaettigte Rot, -1 heraus, wenn sich die Farbart dabei um mehr als
    RED_MIN_UV aendert (WCAG 2.2 / ISO 9241-391). Beide Zustaende rot oder keiner: kein Rot-Uebergang."""
    red, uv = chroma[..., 0] > 0.5, chroma[..., 1:]
    far = np.linalg.norm(np.diff(uv, axis=0), axis=-1) > RED_MIN_UV
    return ((red[1:].astype(np.int8) - red[:-1].astype(np.int8)) * far).astype(np.int8)


def flash_check(lum, cfg, chroma=None):
    """WCAG 2.3.1, allgemeine Blitzschwelle und (mit chroma) rote Blitze, vereinfacht.

    Ein Sprung = Helligkeitsaenderung eines Pixels um mindestens flash_min_delta, wobei das dunklere Bild unter 0.8
    liegt. Ein Blitz = ein Sprung, der gegen die Richtung des vorigen Sprungs desselben Pixels geht (Paar).
    Ein Pixel faellt durch, wenn es in irgendeinem 1-s-Fenster mehr als flash_max_per_s Blitze hat. Verstoss, wenn
    durchgefallene Pixel mehr als flash_max_area_frac des Bildes bedecken.
    Rot (chroma aus chroma_state): gleiche Zaehlung ueber red_steps, unabhaengig von der Helligkeit. Ein Wechsel
    Rot <> gleich helles Grau blitzt nicht allgemein, aber rot (flash_selftest). Gemessen wird ueber das ganze Bild,
    nicht je 10°-Blickfeld."""
    ch, fps = cfg["checks"], cfg["video"]["timeline_fps"]
    d = np.diff(lum, axis=0)
    darker = np.minimum(lum[1:], lum[:-1])
    step = (np.sign(d) * ((np.abs(d) >= ch["flash_min_delta"]) & (darker < 0.8))).astype(np.int8)
    per_s = _flashes_per_s(step, fps)
    area = (per_s > ch["flash_max_per_s"]).mean((1, 2))
    worst = int(area.argmax())
    out = dict(ok=bool(area.max() <= ch["flash_max_area_frac"]), worst_area=float(area.max()),
               worst_at_s=worst / fps, max_flashes_per_s=int(per_s.max()))
    if chroma is not None:
        rper = _flashes_per_s(red_steps(chroma), fps)
        rarea = (rper > ch["flash_max_per_s"]).mean((1, 2))
        out.update(red_ok=bool(rarea.max() <= ch["flash_max_area_frac"]), red_worst_area=float(rarea.max()),
                   red_worst_at_s=int(rarea.argmax()) / fps, red_max_per_s=int(rper.max()))
        out["ok"] = out["ok"] and out["red_ok"]
    return out


def flash_text(flash, cfg):
    """Eine Zeile Befund aus flash_check fuer Reports (None: Gate aus)."""
    if flash is None:
        return "aus ([checks].flash_gate = false, Vadim 2.10.)"
    ch = cfg["checks"]
    s = (f"{'ok' if flash['ok'] else 'VERSTOSS'} · allgemein: schlimmste Sekunde bei {flash['worst_at_s']:.1f} s "
         f"{flash['worst_area'] * 100:.0f} % der Flaeche ueber {ch['flash_max_per_s']} Blitze/s (Grenze "
         f"{ch['flash_max_area_frac'] * 100:.0f} %), max. {flash['max_flashes_per_s']} Blitze/s an einer Stelle")
    if "red_ok" in flash:
        s += (f" · rot: {flash['red_worst_area'] * 100:.0f} % der Flaeche (bei {flash['red_worst_at_s']:.1f} s), "
              f"max. {flash['red_max_per_s']} rote Blitze/s an einer Stelle")
    return s


def flash_selftest(cfg):
    """Selbsttest der Rot-Regel am Bild: 2 s lang reines Rot <> gleich helles Grau im Karusselltempo (8 Wechsel/s).
    Allgemein ist das kein Blitz (gleiche Luminanz), rot ist es einer auf der ganzen Flaeche. Ohne chroma (der alte
    flash_check) faellt es nicht auf."""
    fps = cfg["video"]["timeline_fps"]
    red = Image.new("RGB", FLASH_ANALYSIS_PX, (255, 0, 0))
    grey_v = round(255 * (1.055 * float(KL.LUMA[0]) ** (1 / 2.4) - 0.055))      # sRGB-Wert mit der Luminanz von Rot
    grey = Image.new("RGB", FLASH_ANALYSIS_PX, (grey_v,) * 3)
    seq = [(red, grey)[(t * 8 // fps) % 2] for t in range(2 * fps)]
    lum, chroma = np.array([luminance(im) for im in seq]), np.array([chroma_state(im) for im in seq])
    old, new = flash_check(lum, cfg), flash_check(lum, cfg, chroma)
    assert old["ok"] and new["max_flashes_per_s"] == 0, "Rot <> Grau: allgemein darf es nicht blitzen (gleiche Luminanz)"
    assert not new["red_ok"] and new["red_worst_area"] > 0.99, f"Rot-Regel schlaegt nicht an: {new}"
    return f"Selbsttest ok (Blitz: Rot <> Grau gleicher Luminanz ist allgemein ok, rot {new['red_max_per_s']} Blitze/s)"


def world_text(cfg):
    """Farbreise(n) als Text: "P11 → … → P11" bei einer Welt, sonst je Welt "W1 P23 > P22 (4 Frames je Station)"."""
    col = cfg["color"]
    if len(col["worlds"]) == 1:
        st = col["worlds"][0]
        return " → ".join(st + st[:1])
    return " | ".join(f"W{w + 1} {' > '.join(st)} ({col['world_frames'] // len(st)} Frames je Station)"
                      for w, st in enumerate(col["worlds"]))


def carousel_flash(cfg, posters, passes=2):
    """Blitz-Check der Plakatfolge allein, Plakat bildfuellend (schlimmster Fall: Zoom-Ende), im schnellsten
    Karusselltempo (meiste Wechsel pro Takt im Musik-Raster; 120 BPM, 16tel: 8 Plakate/s) auf dem Timeline-Raster.
    Alle Plakate der Reihe nach, passes-mal, damit der Neustart mitzaehlt. Liefert (flash_check, lum, chroma je Plakat)."""
    bar_s = 16 * cfg["music"]["grid"]["sixteenth_s"]
    hold = cfg["video"]["timeline_fps"] * bar_s / max(per for per, _ in cfg["video"]["cadence"])
    ims = [Image.fromarray(p) for p in posters]
    lum, chroma = [luminance(im) for im in ims], [chroma_state(im) for im in ims]
    seq = [j for _ in range(passes) for j in range(len(posters))]
    idx = [j for k, j in enumerate(seq) for _ in range(round((k + 1) * hold) - round(k * hold))]
    return flash_check(np.array([lum[j] for j in idx]), cfg, np.array([chroma[j] for j in idx])), lum, chroma


def switch_jumps(cfg, lum, chroma):
    """Jeder Plakatwechsel k → k+1 (inkl. Neustart): (k, Weltgrenze ja/nein, mittlere Helligkeit vorher/nachher,
    Flaechenanteil mit Blitz-Sprung (|delta| >= flash_min_delta, dunkleres Bild < 0.8), Flaechenanteil mit
    Rot-Uebergang). Ein harter Weltwechsel ist ein einzelner Sprung; zum Blitz wird er erst mit dem Gegensprung."""
    n, wf = len(lum), cfg["color"]["world_frames"]
    out = []
    for k in range(n):
        a, b = lum[k], lum[(k + 1) % n]
        jump = ((np.abs(b - a) >= cfg["checks"]["flash_min_delta"]) & (np.minimum(a, b) < 0.8)).mean()
        red = (red_steps(np.array([chroma[k], chroma[(k + 1) % n]]))[0] != 0).mean()
        out.append((k, (k + 1) % wf == 0 and len(cfg["color"]["worlds"]) > 1, float(a.mean()), float(b.mean()),
                    float(jump), float(red)))
    return out


def cta_legibility(cfg, i, img):
    """Lesbarkeit von JOIN US (kickoff.legible, gleiche Messung wie Titel/Datum) auf Plakat i."""
    st = KL.poster_style(cfg, i)
    c = S.Ctx(st, KL.PREVIEW)
    K._EXTRA["title"] = K._EXTRA["date"] = KL.qr_glow(c, st["loop"]["qr"])[-1][1]
    return K.legible(img, KL.PREVIEW_CELL_PX)


def sheet_report(cfg, posters, qr_ok, legib, name=""):
    """Befund zu einem Bogen: Plakate, Welten, QR, Lesbarkeit (Titel+Datum, JOIN US), Lila, Blitz im Karusselltempo
    und jeder harte Weltwechsel einzeln."""
    n = len(posters)
    keys = sum(KL.is_key(cfg, i) for i in range(n))
    cta = [cta_legibility(cfg, i, p) for i, p in enumerate(posters)]
    paper = [i for i in range(n) if KL.is_paper(KL.color_pos(cfg, i)[1][0])]
    flash, lum, chroma = carousel_flash(cfg, posters)
    if not cfg["checks"]["flash_gate"]:
        flash = None
    jumps = switch_jumps(cfg, lum, chroma)
    inner = max((j for j in jumps if not j[1]), key=lambda j: j[4])
    below = [f"{i + 1:02d} ({x:.2f})" for i, x in enumerate(legib) if x < K.TIER[0]]
    lines = [f"{name} · {n} Plakate = {keys} Aushaenge + {n - keys} Fotoframes · {len(cfg['color']['worlds'])} Welt(en) a "
             f"{cfg['color']['world_frames']} Frames · Bahn und Stile alle {KL.count(cfg)} Frames",
             f"Welten: {world_text(cfg)}",
             f"QR lesbar: {sum(qr_ok)}/{n}" + ("" if all(qr_ok) else "  ! nicht: " + " ".join(
                 f"{i + 1:02d}" for i, ok in enumerate(qr_ok) if not ok)),
             f"Lesbarkeit Titel+Datum: min {min(legib):.2f}, {sum(x >= K.TIER[0] for x in legib)}/{n} in Stufe A"
             + (f"  ! unter A: {' '.join(below)}" if below else ""),
             f"Lesbarkeit JOIN US: min {min(cta):.2f} (dunkel {min((x for i, x in enumerate(cta) if i not in paper), default=1):.2f}"
             f", Papier {min((cta[i] for i in paper), default=float('nan')):.2f})",
             "Lila: ok (load prueft jedes Plakat, sonst gaebe es keinen Bogen)",
             f"Blitz, Plakat bildfuellend, {loop_fps(cfg):.2f} Plakate/s, 2 Durchgaenge: {flash_text(flash, cfg)}",
             f"Loop-Video: {loop_fps(cfg):.2f} Plakate/s, {cfg['music']['loop_passes']} Durchgaenge = "
             f"{n * cfg['music']['loop_passes'] / loop_fps(cfg):.2f} s, Ton {cfg['music']['loop_file']}",
             "Harte Weltwechsel (Helligkeit vorher → nachher, Flaeche mit Blitz-Sprung, Flaeche mit Rot-Uebergang):"]
    for k, world, a, b, jump, red in jumps:
        if world:
            w0, w1 = KL.color_pos(cfg, k)[0], KL.color_pos(cfg, (k + 1) % n)[0]
            lines.append(f"  W{w0 + 1} > W{w1 + 1}  Plakat {k + 1:02d} > {(k + 1) % n + 1:02d}  {a:.2f} → {b:.2f}  "
                         f"Sprung {jump * 100:3.0f} %  Rot {red * 100:3.0f} %")
    k, _, a, b, jump, red = inner
    lines.append(f"  zum Vergleich, groesster Wechsel innerhalb einer Welt: Plakat {k + 1:02d} > {(k + 1) % n + 1:02d}  "
                 f"{a:.2f} → {b:.2f}  Sprung {jump * 100:.0f} %  Rot {red * 100:.0f} %")
    return "\n".join(lines) + "\n"


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
    off = m["grid"].get("file_offset_s", 0.0)                   # [ending]: IGOR ungeschnitten ab dem Einstieg
    x = KM.decode(os.path.join(KL.PROJECT, m["file"]))[round(off * KM.SR):round((off + dur) * KM.SR)]
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


def sheet(cfg, posters, qr_ok, legib, out, tag=""):
    """Schnelle Runde (~15 s statt ~2 min): nur Kontaktbogen + Plakat-Loop im Karusselltempo + report.txt (Befund aus
    sheet_report) → previz/now/. Fuer Standbild-Entscheidungen; das Video erst mit preview, wenn die Standbilder stehen."""
    os.makedirs(out, exist_ok=True)
    contact_sheet(cfg, posters, qr_ok, legib, [], os.path.join(out, tag + "contact.png"))
    with open(os.path.join(out, tag + "report.txt"), "w", encoding="utf-8") as f:
        f.write(sheet_report(cfg, posters, qr_ok, legib, tag.rstrip("_") or "loop.toml"))
    loop_video(cfg, posters, os.path.join(out, tag + "loop.mp4"))
    return out


def loop_fps(cfg):
    """Plakatwechsel pro Sekunde im Loop-Video: schnellstes Karusselltempo auf dem Takt von [music].loop_grid."""
    return max(per for per, _ in cfg["video"]["cadence"]) / (16 * cfg["music"]["loop_grid"]["sixteenth_s"])


def loop_video(cfg, posters, path):
    """Plakat-Loop allein, halbe Groesse, loop_passes Durchgaenge im schnellsten Karusselltempo, mit Ton:
    [music].loop_file ab dem Einstieg in_s seines Rasters (Taktstrich), genau so lang wie das Bild. Weil die Bildrate
    aus demselben Raster kommt, liegt jeder Plakatwechsel auf dem Song-Raster (T16: auf jeder 32tel-Triole)."""
    import kickoff_loop_music as KM
    m, fps = cfg["music"], loop_fps(cfg)
    frames_n = len(posters) * m["loop_passes"]
    start = m["loop_grid"]["in_s"]
    x = KM.decode(os.path.join(KL.PROJECT, m["loop_file"]))[round(start * KM.SR):round((start + frames_n / fps) * KM.SR)]
    x = x * 10 ** ((m["loudness_lufs"] - KM.lufs(x)) / 20)
    k = round(m["fade_out_s"] * KM.SR)
    x[-k:] *= np.linspace(1, 0, k)[:, None]
    wav = os.path.splitext(path)[0] + ".wav"
    KM.write_wav(wav, x)
    h, w = posters[0].shape[:2]
    ff = ffmpeg_writer(path, (w // 2, h // 2), fps, wav)
    for img in posters * m["loop_passes"]:
        ff.stdin.write(np.asarray(Image.fromarray(img).resize((w // 2, h // 2), Image.BOX)).tobytes())
    ff.stdin.close()
    ff.wait()
    os.remove(wav)
    return path


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
    out = KL.out_dir(cfg) or next_version()                   # Variante: ihr eigener Ordner, sonst neue Version vNNN
    if os.path.abspath(cfg["_src"]) != os.path.abspath(os.path.join(out, os.path.basename(cfg["_src"]))):
        shutil.copy(cfg["_src"], out)                         # die Config, aus der dieses Video gerechnet ist
    n = len(posters)
    tl = Timeline(cfg)
    size = tuple(cfg["video"]["size_px"])
    tfps, bpm = cfg["video"]["timeline_fps"], cfg["loop"]["bpm"]
    bar_s = 16 * cfg["music"]["grid"]["sixteenth_s"]

    # 1. Plakat-Loop allein im schnellsten Karusselltempo, mit Ton (man soll den Neustart sehen)
    h, w = posters[0].shape[:2]
    top_fps = max(per for per, _ in cfg["video"]["cadence"]) / bar_s
    loop_video(cfg, posters, os.path.join(out, "loop.mp4"))

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
    stills, lum, chroma = [], [], []
    for t in range(tl.total):
        if t < tl.zoom_end:
            sc, roll = camera(cfg, tl, t, h)
            img = shoot(plates[tl.poster_at(t)], sc, size, roll)
        else:
            img = digital[t - tl.zoom_end]
        ff.stdin.write(np.asarray(img).tobytes())
        if t == tl.zoom_end - 1:
            last_img = img                                     # letztes Karussellbild (Zoom-Check: nahtlos?)
        lum.append(luminance(img))
        chroma.append(chroma_state(img))
        if t in marks:
            stills.append((f"{marks[t]} {t / tfps:.2f}s", img))
    ff.stdin.close()
    ff.wait()
    os.remove(wav)                                             # steckt im Video

    # 3. Pruefungen, Kontaktbogen, Report
    flash = flash_check(np.array(lum), cfg, np.array(chroma)) if cfg["checks"]["flash_gate"] else None
    end_leg = KL.legibility(digital_style(cfg, (tl.total - tl.zoom_end - 1) / tfps), np.asarray(digital[-1]), "9x16")
    contact_sheet(cfg, posters, qr_ok, legib, stills, os.path.join(out, "contact.png"))
    mode = cfg["endcard"].get("end_mode")
    if mode in ("zoom", "words"):
        zoom_sheet(cfg, tl, digital, last_img, os.path.join(out, f"{mode}.png"))
    ground = [float(KL.LUMA @ (np.array([int(c[j:j + 2], 16) for j in (1, 3, 5)]) / 255))
              for c in (KL.palette_hex(cfg, i)[0] for i in range(n))]
    real = sum(os.path.exists(aligned_photo(k)) for k in range(n))
    keys = [i for i in range(n) if KL.is_key(cfg, i)]

    def tier(x):                                  # Lesbarkeitsstufe wie bei den Einzelplakaten
        return "A" if x >= K.TIER[0] else "B" if x >= K.TIER[1] else "C"

    ending = [f"Endkarte: Lesbarkeit Titel+Datum {end_leg:.2f} {tier(end_leg)}"]
    if "ending" in cfg:                                       # Ausstiege (kickoff_loop_end): Zeitachse, Auslauf, Endkarte
        import kickoff_loop_end as KE
        e = cfg["ending"]
        ending = KE.report(cfg, tl)
        if mode == "words":
            ending.append(f"Ende: Begriffe {' / '.join(e['words'])}, je {e['words_term_beats']} Beat, Bogen words.png")
        if e["card_on"]:
            qr, leg = KE.card_check(digital_style(cfg, (len(digital) - 1) / tfps), np.asarray(digital[-1]))
            run = 0.0                                          # wie lange vor Schluss der QR schon lesbar ist (1/4 s)
            for k in range(len(digital) - 1, -1, -(tfps // 4)):
                if not KE.card_check(digital_style(cfg, k / tfps), np.asarray(digital[k]))[0]:
                    break
                run = (len(digital) - k) / tfps
            ending.append(f"Endkarte: QR {'lesbar' if qr else 'NICHT lesbar'}, scanbar die letzten {run:.2f} s, "
                          f"Lesbarkeit SPARK + KICK-OFF/Datum {leg:.2f} {tier(leg)}")

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
             f"Farbreise: {world_text(cfg)} (OKLab, keine Mischung lila: geprueft in load)",
             f"QR lesbar: {sum(qr_ok)}/{n}" + ("" if all(qr_ok) else "  ! nicht lesbar: "
                                                + " ".join(f"{i + 1:02d}" for i, ok in enumerate(qr_ok) if not ok)),
             f"Lesbarkeit Titel+Datum: {sum(x >= K.TIER[0] for x in legib)}/{n} in Stufe A (>= {K.TIER[0]})"
             + ("" if min(legib) >= K.TIER[0] else "  ! unter A: " + " ".join(
                 f"{i + 1:02d}" for i, x in enumerate(legib) if x < K.TIER[0])),
             *ending,
             f"Blitz-Check (WCAG 2.3.1, vereinfacht): {flash_text(flash, cfg)}",
             *([f"Ende: Infinite Zoom ({cfg['endcard']['zoom_ease']}, {cfg['endcard']['zoom_dolls']} Puppen, Ausbruch "
                f"{'an' if cfg['endcard']['burst_on'] else 'aus'}, Impact {'an' if cfg['endcard']['impact_on'] else 'aus'}), "
                f"Karussell endet auf F{end_index(cfg) + 1}, Bogen zoom.png",
                zoom_check(cfg, tl, digital, last_img)] if cfg["endcard"].get("end_mode") == "zoom" else []),
             f"Ton: preview.mp4 {cfg['music']['file']}, loop.mp4 {cfg['music']['loop_file']} "
             f"({cfg['music']['loop_passes']} Durchgaenge, {loop_fps(cfg):.2f} Plakate/s)",
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
