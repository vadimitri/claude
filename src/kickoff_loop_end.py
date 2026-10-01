#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""Kick-off Loop, Ausstiege (Vadim 2.10.): wie das Karussell endet und was danach kommt.

Stellschrauben: Abschnitt [ending] der Varianten-TOML (previz/review/<Code>/<Code>.toml). Eingehaengt in
kickoff_loop_video (Timeline, camera, digital_style) und kickoff_loop.load (Zeitachse statt Mashup-Raster).

Zeitachse: IGOR ungeschnitten ab dem Einstieg (igor_beats.json in_s = 22.435 s Songzeit), kein Mashup. Vadim 2.10.: der
M3-Schnitt "klingt nicht smooth", die Musik schneidet er spaeter selbst. Ereignisse ab Videoanfang: Takt 5 = 11.76 s
Bass-Boom (Phrase 2), 19.85 s IGORs Stopp (1 Beat Stille), 20.59 s staerkster Hit, 23.53 s B-Teil.

  Auslauf   runout_bars > 0: der letzte Umlauf bremst ab wie ein Gluecksrad und landet auf end_frame. Anfangstempo =
            T16, deshalb folgt die Steilheit aus der Laenge (runout_pow). Die Kamera bremst mit derselben Kurve, der Zoom
            danach startet aus dem Stand: kein Tempo-Sprung.
  Begriffe  end_mode = "words": der Stern faehrt in den Fluchtpunkt, aus ihm fliegen Begriffswaende frontal heran
            (HARDWARE x n untereinander). Massstab als Sigmoid (smoothstep im Logarithmus), je words_term_beats ein Begriff,
            der alte stuerzt an der Kamera vorbei. Wo sich beide decken, kippt die Schrift in den Grund (XOR wie SPARK).
            Jeder Begriff landet in der naechsten Colorway der Farbreise (harter Schnitt auf dem Beat).
  Endkarte  card_on: SPARK / KICK-OFF / Datum / Info, QR gross in der Mitte. Jedes Element setzt mit Ease-out-back ein
            (Lage, Massstab, Einblendung im Bayer-Korn), alles auf dem Zellraster. Nach Begriffen fliegt die Karte als
            Ganzes heran wie ein weiterer Begriff, im Zoom dimmt der Hintergrund im Korn ab.

  uv run src/kickoff_loop_end.py test <toml>   Selbsttest (Auslauf, Kamera, Warp), schlaegt am alten Fehler an
"""
import json, math, os, sys
from functools import lru_cache

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kickoff as K            # noqa: E402
import styles as S             # noqa: E402

KEYS = ("carousel_bars", "runout_bars", "length_bars", "card_on")
WORD_KEYS = ("words", "words_term_beats", "words_far_scale", "words_vanish_beats", "words_width_frac", "words_lead_frac",
             "words_lines")
CARD_KEYS = ("card_moves", "card_in_beats", "card_overshoot", "card_dim_frac", "card_title_w_frac", "card_top_frac",
             "card_sub_frac", "card_gap_frac", "card_qr_module_cells", "card_qr_quiet_cells", "card_qr_y_frac",
             "card_glow_cells", "card_cta_cells", "card_cta_gap_cells", "card_info", "card_info_frac")
CARD_PARTS = ("title", "what", "when", "cta", "qr", "info")
EXIT_MAX_SCALE = 30.0   # Begriff an der Kamera vorbei: ab diesem Massstab ist er durch (nur noch Flaechen, nicht mehr gezeichnet)
GLOW_E = 4              # Gluehen wie kickoff_loop.qr_glow "light": exp(-4) = 2 % am Ende von card_glow_cells
GLOW_MIN = 0.02         # ... darunter unsichtbar im Korn (wie kickoff_loop.GLOW_MIN)


# ---------------------------------------------------------------- Konfiguration, Zeitachse

def grid(cfg):
    """Zeitachse (dieselben Schluessel wie ein Mashup-Raster, kickoff_loop.GRID_KEYS) aus IGORs Raster und [ending].
    Setzt [music].file auf IGOR (loop_file), song() liest ab file_offset_s. Prueft [ending] vorher."""
    e, m = cfg["ending"], cfg["music"]
    words = cfg["endcard"].get("end_mode") == "words"
    need = KEYS + (WORD_KEYS if words else ()) + (CARD_KEYS if e.get("card_on") else ())
    miss = [k for k in need if k not in e]
    assert not miss, f"[ending] fehlt: {', '.join(miss)}"
    assert e["carousel_bars"] > 0 and e["runout_bars"] >= 0, "[ending]: carousel_bars > 0, runout_bars >= 0"
    assert not e["runout_bars"] or runout_pow(cfg) >= 1, \
        f"[ending].runout_bars: mindestens {cfg['loop']['frames'] / cfg['loop']['changes_per_bar']:.2f} Takte (sonst schneller als T16)"
    assert not words or e["words_lines"] % 2 == 1, "[ending].words_lines ungerade (eine Zeile steht in der Mitte)"
    assert not e["card_on"] or all(len(mv) == 5 and mv[0] in CARD_PARTS for mv in e["card_moves"]), \
        f"[ending].card_moves: [Teil, Beat, dx, dy, Massstab], Teil aus {CARD_PARTS}"
    ig = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kickoff_loop",
                                     m["loop_grid"])))
    bar, beat = 16 * ig["sixteenth_s"], ig["beat_s"]
    land = (e["carousel_bars"] + e["runout_bars"]) * bar
    end = e["length_bars"] * bar
    assert end > land, f"[ending].length_bars {e['length_bars']}: Video endet vor dem Karussell (Takt {land / bar:.2f})"
    m["file"] = m["loop_file"]
    return dict(bpm_carousel=ig["bpm"], bpm_end=ig["bpm"], sixteenth_s=ig["sixteenth_s"],
                carousel_bars=[[cfg["loop"]["changes_per_bar"] or 48, e["carousel_bars"]]],
                hits_s=[h for h in ig["hits_s"] if h <= end], downbeats_s=ig["downbeats_s"],
                burst_s=land, impact_s=land + cfg["endcard"]["burst_beats"] * beat, end_s=end,
                file_offset_s=ig["in_s"])


def runout_pow(cfg):
    """Steilheit des Auslaufs: Position = n (1 - (1 - u)^p). Anfangstempo n p / Dauer muss das Karussell-Tempo
    (changes_per_bar pro Takt) sein, also p = runout_bars * changes_per_bar / n. 2 Takte, 48, 32 Frames → p = 3."""
    return cfg["ending"]["runout_bars"] * cfg["loop"]["changes_per_bar"] / cfg["loop"]["frames"]


def runout_times(cfg, p=None):
    """Wechselzeiten (s) des Auslaufs: n + 1 Wechsel (Neustart auf dem Taktstrich, dann ein Umlauf), auf das
    32tel-Triolen-Raster gerundet. Der letzte liegt genau auf dem Landetakt (burst_s) und zeigt end_frame."""
    g, n = cfg["music"]["grid"], cfg["loop"]["frames"]
    bar = 16 * g["sixteenth_s"]
    slot = bar / 48                                         # kickoff_loop.SUBDIV_PER_BAR
    t0, R = cfg["ending"]["carousel_bars"] * bar, cfg["ending"]["runout_bars"] * bar
    p = p or runout_pow(cfg)
    out = []
    for k in range(n + 1):
        s = round(R * (1 - (1 - k / n) ** (1 / p)) / slot)
        out.append(max(s, out[-1] + 1) if out else s)       # nie zwei Wechsel auf einem Slot
    return [t0 + s * slot for s in out]


def camera_u(cfg, tl, t):
    """Kamerafahrt 0..1 (Anteil der Log-Zoomstrecke) mit Auslauf: gleichmaessig bis zum Auslauf, dann bremst sie mit
    derselben Kurve wie das Rad (Ease-out mit runout_pow) und steht auf dem Landetakt. Steigung am Uebergang gleich."""
    fps = cfg["video"]["timeline_fps"]
    bar = 16 * cfg["music"]["grid"]["sixteenth_s"]
    t0, R, p = cfg["ending"]["carousel_bars"] * bar * fps, cfg["ending"]["runout_bars"] * bar * fps, runout_pow(cfg)
    a = 1 / (t0 + R / p)
    if t <= t0:
        return a * t
    tau = min((t - t0) / R, 1.0)
    return a * t0 + a * R / p * (1 - (1 - tau) ** p)


def beat(cfg):
    return 60 / cfg["loop"]["bpm"]


# ---------------------------------------------------------------- Kurven

def smooth(u):
    """Sigmoid (smoothstep): steht am Anfang und am Ende."""
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def back(u, c1):
    """Ease-out-back: schiesst um c1-abhaengig ueber das Ziel und setzt sich (c1 = 1.70158 → 10 % Ueberschwinger)."""
    u = min(max(u, 0.0), 1.0) - 1
    return 1 + (c1 + 1) * u ** 3 + c1 * u ** 2


# ---------------------------------------------------------------- Raster-Helfer

def bayer(c):
    return S.tile(S.bayer(4), (c.gh, c.gw))


def warp(c, m, s, dx=0.0, dy=0.0, ax=None, ay=None):
    """Maske m (Zellen) um (ax, ay) auf s skaliert und um (dx, dy) Zellen verschoben. s >= 1: naechster Nachbar
    (Zellen werden zu Bloecken, wie die Kamera ins Pixelraster). s < 1: Flaechenmittel, dann im Bayer-Korn
    geschwellt (kleine Schrift zerfaellt in Korn statt in Luecken). s = 1 ohne Versatz gibt m exakt zurueck."""
    ax = c.gw / 2 if ax is None else ax
    ay = c.gh / 2 if ay is None else ay
    if s <= 1e-3 or not m.any():
        return np.zeros_like(m)
    if s >= 1:
        sy = np.floor(ay + (c.yy + 0.5 - ay - dy) / s).astype(int)
        sx = np.floor(ax + (c.xx + 0.5 - ax - dx) / s).astype(int)
        ok = (sy >= 0) & (sy < m.shape[0]) & (sx >= 0) & (sx < m.shape[1])
        out = np.zeros(c.yy.shape, bool)
        out[ok] = m[sy[ok], sx[ok]]
        return out
    h, w = max(1, round(m.shape[0] * s)), max(1, round(m.shape[1] * s))
    cov = cv2.resize(m.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
    top, left = round(ay + dy - ay * s), round(ax + dx - ax * s)
    full = np.zeros(c.yy.shape, np.float32)
    y0, x0, y1, x1 = max(top, 0), max(left, 0), min(top + h, c.gh), min(left + w, c.gw)
    if y0 < y1 and x0 < x1:
        full[y0:y1, x0:x1] = cov[y0 - top:y1 - top, x0 - left:x1 - left]
    return full > bayer(c)


def centered_line(c, text, cap, base, cx=None):
    """Zeile (Clash) mit Versalhoehe cap und Grundlinie base (Zellen), waagerecht auf cx zentriert (Zellen)."""
    cx = c.gw / 2 if cx is None else cx
    w = S.width_per_cap(text) * cap
    return S.line_mask(text, "clash", cap * c.px, base * c.px, (cx - w / 2) * c.px, c.px, (c.gh, c.gw))


# ---------------------------------------------------------------- Begriffe

@lru_cache(maxsize=64)
def _wall_ref(text, gw, gh, width_frac, lead_frac, lines):
    """Begriffswand im Landemassstab (s = 1), mittig in einer eigenen Flaeche: lines Zeilen untereinander, jede so
    breit wie width_frac der Bildbreite. Gecacht (pro Prozess), weil jedes Bild der Annaeherung sie verkleinert."""
    cap = width_frac * gw / S.width_per_cap(text)
    lead = cap * lead_frac
    H = int(math.ceil(lines * lead + cap)) + 2
    c = _cells(gw, H)
    m = np.zeros((H, gw), bool)
    for k in range(-(lines // 2), lines // 2 + 1):
        m |= centered_line(c, text, cap, H / 2 + k * lead + cap / 2)
    return m


def _cells(gw, gh):
    """Minimaler Ctx-Ersatz fuer centered_line/warp in einer eigenen Flaeche (Zellen = Pixel, px 1)."""
    yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
    return type("Cells", (), dict(gw=gw, gh=gh, px=1, yy=yy, xx=xx))()


def wall(c, w, text, s, cx, cy):
    """Begriffswand im Bild: Massstab s um (cx, cy) Zellen. s <= 1 aus der Referenz verkleinert (Korn), s > 1 jede
    sichtbare Zeile neu gesetzt (scharf, Clash als Vektorschrift)."""
    if s > EXIT_MAX_SCALE:
        return np.zeros((c.gh, c.gw), bool)
    if s <= 1:
        ref = _wall_ref(text, c.gw, c.gh, w["width_frac"], w["lead_frac"], w["lines"])
        return warp(c, ref, s, cx - c.gw / 2, cy - ref.shape[0] / 2, ax=c.gw / 2, ay=ref.shape[0] / 2)
    cap0 = w["width_frac"] * c.gw / S.width_per_cap(text)
    cap, lead = cap0 * s, cap0 * w["lead_frac"] * s
    m = np.zeros((c.gh, c.gw), bool)
    for k in range(-(w["lines"] // 2), w["lines"] // 2 + 1):
        y = cy + k * lead
        if y + cap / 2 < 0 or y - cap / 2 > c.gh:
            continue
        m |= centered_line(c, text, cap, y + cap / 2, cx)
    return m


def words_state(cfg, dt):
    """Stil-Dict des Begriffe-Teils dt Sekunden nach dem Karussell-Ende (Ablauf: Moduldoc). Alles, was das Bild
    bestimmt, steht gerundet in st["loop"]["digital"] (Cache-Schluessel, gleiche Bilder nur einmal rendern)."""
    import kickoff_loop as KL
    import kickoff_loop_video as V
    e, n, b = cfg["ending"], KL.count(cfg), beat(cfg)
    W, H = cfg["video"]["size_px"]
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = V.digital_offset(cfg)
    last = V.last_star(cfg)
    x, y, r, rot = KL.star_at(cfg, last)
    px = S.BASE["R"] * S.SIZES["9x16"][2]
    T = e["words_term_beats"] * b
    terms = list(e["words"])
    card = e["card_on"]

    # Stern faehrt in den Fluchtpunkt (beschleunigt), der erste Begriff kommt von dort
    k = min(dt / (e["words_vanish_beats"] * b), 1.0) ** 2
    vx, vy = ox + cfg["spark"]["vanish"][0] * pw, oy + cfg["spark"]["vanish"][1] * ph
    x0, y0 = ox + x * pw, oy + y * ph
    star = (x0 + (vx - x0) * k, y0 + (vy - y0) * k, r * pw * (1 - k), rot)
    landed = sum(dt >= (j + 1) * T for j in range(len(terms) + card))
    st = KL.poster_style(cfg, (last + landed) % n)                 # Colorway: je gelandetem Begriff eine weiter
    sl = KL.poster_style(cfg, last)
    st.update(S=sl["S"], seed=sl["seed"])                          # Stern-Stil bleibt der des letzten Plakats
    if star[2] < px:                                               # kleiner als eine Zelle: weg (Labor-Stile messen am Stern)
        star, st["S"] = (-3.0 * W, -3.0 * H, 1.0, rot), KL.S_CODES["S2"]

    walls = []
    for j, text in enumerate(terms + (["<card>"] if card else [])):
        a0, a1 = j * T, (j + 1) * T
        if dt < a0:
            break
        if dt < a1:
            s = e["words_far_scale"] ** (1 - smooth((dt - a0) / T))   # Sigmoid im Logarithmus des Massstabs
        elif j == len(terms) + card - 1 or text == "<card>":
            s = 1.0                                                     # der letzte bleibt stehen
        elif dt < a1 + T:
            s = 1 / max(1 - ((dt - a1) / T) ** 2, 1e-6)                # stuerzt beschleunigt an der Kamera vorbei
        else:
            continue
        f = smooth((dt - a0) / T) if j == 0 else 1.0                    # erster Begriff: vom Fluchtpunkt zur Mitte
        cx, cy = (vx + (W / 2 - vx) * f) / px, (vy + (H / 2 - vy) * f) / px
        walls.append([text, round(s, 5), round(cx, 2), round(cy, 2)])

    fps = cfg["video"]["timeline_fps"]
    dur = cfg["music"]["grid"]["end_s"] - cfg["music"]["grid"]["burst_s"]
    fade_at, last_t = dur - cfg["endcard"]["fade_beats"] * b, dur - 1 / fps
    black = 0.0 if card else min(max((dt - fade_at) / max(last_t - fade_at, 1e-6), 0.0), 1.0)
    cs = None
    if card:
        g = next((w[1] for w in walls if w[0] == "<card>"), 0.0)
        cs = card_state(cfg, dt, g)
        walls = [w for w in walls if w[0] != "<card>"]
    tout = min(dt / (cfg["endcard"]["type_out_beats"] * b), 1.0)
    st.update(type_fn=words_type)
    st["loop"] = {**st["loop"], "digital": dict(
        u=0.0, offset=(ox, oy), star=star, show=None, black=round(black, 4),
        zoom=dict(type_out=round(tout, 4), info=[], info_in=0.0),
        words=dict(walls=walls, width_frac=e["words_width_frac"], lead_frac=e["words_lead_frac"], lines=e["words_lines"]),
        card=cs)}
    st["star"] = (star[0] / W, star[1] / H, star[2] / W)
    return st


def words_type(c):
    """Satz im Begriffe-Teil: Titelblock + QR des letzten Plakats zerfallen im Korn (wie im Zoom), dann die Waende,
    juengste zuletzt. Wo sich zwei Waende oder Wand und Stern decken: Grund (XOR). Danach ggf. die Endkarte."""
    import kickoff_loop_digital as KD
    dg = c.st["loop"]["digital"]
    KD.zoom_type(c)
    w = dg["words"]
    acc = np.zeros((c.gh, c.gw), bool)
    v = np.full((c.gh, c.gw), np.nan, np.float32)
    for text, s, cx, cy in w["walls"]:                               # aelteste (groesste) zuerst
        m = wall(c, w, text, s, cx, cy)
        v = np.where(m, np.where(acc | c.star_m, c.lvl(0), c.lvl(c.N)), v)
        acc |= m
    if acc.any():
        c.add("words", acc, v)
    if dg.get("card"):
        card_layers(c, dg["card"])


# ---------------------------------------------------------------- Endkarte

def card_state(cfg, dt, group=1.0):
    """Animationsstand der Endkarte dt Sekunden nach dem Karussell-Ende: je Teil (Name, Einblendung 0..1, Massstab,
    dx, dy in Zellen) aus card_moves [Teil, Einsatz in Beats, dx/dy als Bruchteil der Bildbreite/-hoehe, Startmassstab].
    Lage und Massstab mit Ease-out-back (ueberschwingen, setzen), Einblendung in der ersten Haelfte. group = Massstab
    der ganzen Karte (fliegt nach Begriffen heran). Gerundet: steht alles, ist das Bild gleich (Cache)."""
    e, b = cfg["ending"], beat(cfg)
    W, H = cfg["video"]["size_px"]
    px = S.BASE["R"] * S.SIZES["9x16"][2]
    gw, gh = W // px, H // px
    parts = []
    for name, at, dx, dy, s0 in e["card_moves"]:
        u = (dt - at * b) / (e["card_in_beats"] * b)
        if u <= 0:
            continue
        k = back(u, e["card_overshoot"])
        parts.append([name, round(min(2 * u, 1.0), 3), round(s0 + (1 - s0) * k, 4),
                      round(dx * gw * (1 - k), 2), round(dy * gh * (1 - k), 2)])
    first = min(at for _, at, *_ in e["card_moves"])
    dim = e["card_dim_frac"] * min(max((dt - first * b) / (e["card_in_beats"] * b), 0.0), 1.0)
    lay = {k[5:]: e[k] for k in CARD_KEYS if k not in ("card_moves", "card_in_beats", "card_overshoot", "card_dim_frac")}
    return dict(group=round(group, 5), parts=parts, dim=round(dim, 3), layout=lay)


def card_masks(c, lay):
    """Endkarte im Endzustand (Zellen): {Teil: Maske} plus QR-Platte und -Module. Senkrecht gestapelt, alles mittig:
    SPARK (title_w_frac der Bildbreite) ab top_frac, KICK-OFF und Datum (sub_frac der Titelhoehe), JOIN US ueber dem QR,
    QR (qr_module_cells pro Modul) mit der Mitte auf qr_y_frac, Info darunter."""
    W, H = c.gw, c.gh
    cap = lay["title_w_frac"] * W / S.width_per_cap(K.COPY["title"])
    sub, gap = cap * lay["sub_frac"], cap * lay["gap_frac"]
    tb = lay["top_frac"] * H + cap
    wb = tb + gap + sub
    db = wb + gap * 0.6 + sub
    out = dict(title=centered_line(c, K.COPY["title"], cap, tb), what=centered_line(c, K.COPY["what"], sub, wb),
               when=centered_line(c, K.COPY["when"], sub, db))
    q = S.qr_matrix()
    mc, quiet = lay["qr_module_cells"], lay["qr_quiet_cells"]
    n = len(q) * mc + 2 * quiet
    top, left = round(lay["qr_y_frac"] * H - n / 2), round((W - n) / 2)
    plate = np.zeros((H, W), bool)
    plate[top:top + n, left:left + n] = True
    mods = np.zeros((H, W), bool)
    mods[top + quiet:top + n - quiet, left + quiet:left + n - quiet] = S.up(q, mc)
    out.update(qr=plate, qr_mods=mods,
               cta=centered_line(c, K.COPY["cta"], lay["cta_cells"], top - lay["cta_gap_cells"]))
    info = [s for s in ([K.COPY["where"]] if K.COPY["where"] else []) + list(lay["info"]) if s]
    m = np.zeros((H, W), bool)
    ic = cap * lay["info_frac"]
    for j, s in enumerate(info):
        m |= centered_line(c, s, ic, top + n + gap + ic + j * ic * 1.4)
    out["info"] = m
    return out


def card_layers(c, cs):
    """Endkarte als Ebenen: Hintergrund im Korn abdimmen (dim = Anteil Zellen auf Grund), dann je Teil die Maske im
    Animationsstand (warp um die eigene Mitte, dann um die Bildmitte mit group), Einblendung im Bayer-Korn. QR: Platte
    in der hellsten Stufe, Module in der dunkelsten, Gluehen aus dem Abstand zur (bewegten) Platte. Alle Schrift in der
    Tintenstufe. Kein Kippen pro Buchstabe wie auf dem Plakat (flip_glyphs): im Zoom zaehlen die abgedimmten Schalen
    dort als hell, JOIN US und Info verloren ganze Buchstaben (Vorschau 2.10.)."""
    import kickoff_loop as KL
    thr = bayer(c)
    if cs["dim"] > 0:
        c.add("dim", thr < cs["dim"], c.lvl(0))
    if not cs["parts"]:
        return
    base = card_masks(c, cs["layout"])
    lum = c.pal @ KL.LUMA
    hi, lo = c.lvl(int(lum.argmax())), c.lvl(int(lum.argmin()))

    def place(m, a, s, dx, dy):
        ys, xs = np.nonzero(m)
        if not len(ys):
            return m
        out = warp(c, m, s, dx, dy, (xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2)
        out = warp(c, out, cs["group"]) if cs["group"] != 1 else out
        return out & (thr < a) if a < 1 else out

    for name, a, s, dx, dy in cs["parts"]:
        if name == "qr":
            ys, xs = np.nonzero(base["qr"])
            ax, ay = (xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2
            plate = warp(c, base["qr"], s, dx, dy, ax, ay)
            mods = warp(c, base["qr_mods"], s, dx, dy, ax, ay)
            if cs["group"] != 1:
                plate, mods = warp(c, plate, cs["group"]), warp(c, mods, cs["group"])
            if not plate.any():
                continue
            g = np.exp(-GLOW_E * distance_transform_edt(~plate) / (cs["layout"]["glow_cells"] * s * cs["group"]))
            glow = (g > GLOW_MIN) & ~plate & (thr < a)
            u = KL.under(c)
            c.add("qr", glow, u + (hi - u) * g)
            c.add("qr", plate & (thr < a), hi)
            c.add("qr", mods & plate & (thr < a), lo)
            continue
        m = place(base[name], a, s, dx, dy)
        if m.any():
            c.add(name, m, c.lvl(c.N))     # Tinte, ohne Kippen: der Grund ist abgedimmt, die Schalen darunter zaehlen nicht


def card_check(st, img):
    """Befund am letzten Bild der Endkarte: QR dekodiert? Lesbarkeit von SPARK und KICK-OFF/Datum (kickoff.legible,
    Stufen kickoff.TIER), Masken aus card_masks."""
    c = S.Ctx(st, "9x16")
    m = card_masks(c, st["loop"]["digital"]["card"]["layout"])
    K._EXTRA["title"], K._EXTRA["date"] = m["title"], m["what"] | m["when"]
    px = S.BASE["R"] * S.SIZES["9x16"][2]
    return K.check_qr(img, px), K.legible(img, px)


# ---------------------------------------------------------------- Befund, Selbsttest

def report(cfg, tl):
    """Zeilen fuer report.txt: Zeitachse auf IGOR, Auslauf gemessen."""
    e, g = cfg["ending"], cfg["music"]["grid"]
    bar = 16 * g["sixteenth_s"]
    out = [f"Zeitachse: IGOR ungeschnitten ab Songzeit {g['file_offset_s']:.3f} s, Karussell {e['carousel_bars']} Takte "
           f"T16, Auslauf {e['runout_bars']} Takte, Karussell-Ende {g['burst_s']:.2f} s (Takt {g['burst_s'] / bar + 1:.2f}), "
           f"Ende {g['end_s']:.2f} s"]
    if e["runout_bars"]:
        ts = runout_times(cfg)
        d = np.diff(ts)
        out.append(f"Auslauf: {len(ts)} Wechsel, Abstand {d[0]:.3f} s (= T16 {bar / 48:.3f} s) → {d[-1]:.2f} s, "
                   f"Potenz {runout_pow(cfg):.2f}, landet auf F{tl.changes[-1][1] + 1} bei {ts[-1]:.2f} s")
    return out


def selftest(cfg):
    """(1) Auslauf: erster Abstand = T16-Raster, Abstaende wachsen, letzter Wechsel auf dem Landetakt mit end_frame.
    Gegenprobe: linear (p = 1, das alte "bleibt prompt stehen") muss als "bremst nicht ab" auffallen.
    (2) Kamera: Tempo am Auslauf-Beginn stetig (Sprung < 2 %), am Ende ~0. (3) warp: s = 1 ist die Identitaet,
    s = 0.5 behaelt ~1/4 der Flaeche (Korn)."""
    import kickoff_loop_video as V
    lines, ok = [], True
    bar = 16 * cfg["music"]["grid"]["sixteenth_s"]
    if cfg["ending"]["runout_bars"]:
        def brakes(ts):
            d = np.diff(ts)
            return d[0] < bar / 48 + 1e-6 and (d[1:] >= d[:-1] - bar / 48 - 1e-9).all() and d[-1] > 8 * d[0]   # 1 Slot Rundung
        ts, tl = runout_times(cfg), V.Timeline(cfg)
        good = brakes(ts) and abs(ts[-1] - cfg["music"]["grid"]["burst_s"]) < 1e-6 and tl.changes[-1][1] == V.end_index(cfg)
        bites = not brakes(runout_times(cfg, p=1))
        lines.append(f"Auslauf: {'ok' if good else 'FEHLER'} (bremst ab, landet auf F{tl.changes[-1][1] + 1}); "
                     f"Gegenprobe linear: {'schlaegt an' if bites else 'TEST BLIND'}")
        ok &= good and bites
        fps = cfg["video"]["timeline_fps"]
        t0 = cfg["ending"]["carousel_bars"] * bar * fps
        v0, v1 = camera_u(cfg, tl, t0) - camera_u(cfg, tl, t0 - 1), camera_u(cfg, tl, t0 + 1) - camera_u(cfg, tl, t0)
        end = tl.zoom_end - 1
        vend = camera_u(cfg, tl, end) - camera_u(cfg, tl, end - 1)
        cam = abs(v1 - v0) / v0 < 0.02 and vend < 0.01 * v0 and abs(camera_u(cfg, tl, (cfg['ending']['carousel_bars'] + cfg['ending']['runout_bars']) * bar * fps) - 1) < 1e-9
        lines.append(f"Kamera: Tempo vor/nach Auslauf-Beginn {v0:.5f}/{v1:.5f}, am Ende {vend:.6f}: {'ok' if cam else 'FEHLER'}")
        ok &= cam
    c = _cells(270, 480)
    m = np.zeros((480, 270), bool)
    m[100:300, 50:200] = True
    same = (warp(c, m, 1.0) == m).all()
    q = warp(c, m, 0.5).sum() / m.sum()
    good = same and 0.2 < q < 0.3
    lines.append(f"warp: Identitaet {'ok' if same else 'FEHLER'}, s 0.5 → Flaeche x{q:.3f} (~0.25): {'ok' if good else 'FEHLER'}")
    return ok and good, lines


if __name__ == "__main__":
    import kickoff_loop as KL
    if len(sys.argv) < 3 or sys.argv[1] != "test":
        sys.exit(__doc__)
    ok, lines = selftest(KL.load(sys.argv[2]))
    print("\n".join(lines))
    sys.exit(0 if ok else 1)
