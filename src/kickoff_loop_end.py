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
  Bahn      end_mode = "orbit" (Vadim 2.10.: "digitaler Loop, der anders loopt"): nach dem Karussell laeuft der Loop
            digital weiter (24 fps, KL.orbit mit gebrochener Phase, Farbe/Stern je ganzer Phase wie im Karussell, an ganzen
            Phasen bitgleich zum Plakat), dann wechselt der Stern die Bahn (orbit_path):
              throw  Wurf in die Tiefe: gerade Linie zum Fluchtpunkt, Bildtempo x orbit_throw_speedup pro Beat (O6)
              dive   Wurf auf die Kamera: im Anflug taucht die Kamera ein, Zoomrate = Wachstum der Bahn, nur schneller,
                     ab F1 (S33) Infinite Zoom mit mitwachsendem Korn und Bewegungsunschaerfe (O7)
            Drehung zieht in beiden mit orbit_spin_speedup an. Verworfen 3.10.: O4/O5 (bremsten im Bild, Wachstum x8
            am Wechsel, Mitte bremste hart), zoom (O1, bremsen in F17 + Zoom aus dem
            Stand), O2/O3 (Schleuder seitlich, zur Kamera). Vadim 3.10. (zu v1 mit 2-3 Umlaeufen): "ab dem Moment, wo es
            digital ist, einmal das noch und dann zack", also orbit_loops Umlaeufe (1), dann der Wechsel; end_frame und
            der Zeitpunkt folgen daraus.

  uv run src/kickoff_loop_end.py test <toml>   Selbsttest (Auslauf, Kamera, Warp, Bahn), schlaegt am alten Fehler an
"""
import json, math, os, sys
from functools import lru_cache

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kickoff as K            # noqa: E402
import styles as S             # noqa: E402

KEYS = ("carousel_bars", "runout_bars", "runout_hold_beats", "length_bars", "card_on")
WORD_KEYS = ("words", "words_term_beats", "words_far_scale", "words_vanish_beats", "words_width_frac", "words_lead_frac",
             "words_lines")
CARD_KEYS = ("card_reveal", "card_diff", "card_moves", "card_in_beats", "card_overshoot", "card_dim_frac", "card_title_w_frac", "card_top_frac",
             "card_sub_frac", "card_gap_frac", "card_qr_module_cells", "card_qr_quiet_cells", "card_qr_y_frac",
             "card_glow_cells", "card_cta_cells", "card_cta_gap_cells", "card_info", "card_info_frac")
CARD_PARTS = ("title", "what", "when", "cta", "qr", "info")
EXIT_MAX_SCALE = 30.0   # Begriff an der Kamera vorbei: ab diesem Massstab ist er durch (nur noch Flaechen, nicht mehr gezeichnet)
GLOW_E = 4              # Gluehen wie kickoff_loop.qr_glow "light": exp(-4) = 2 % am Ende von card_glow_cells
GLOW_MIN = 0.02         # ... darunter unsichtbar im Korn (wie kickoff_loop.GLOW_MIN)
REVEALS = ("bayer", "blocks", "noise")
REVEAL_BLOCKS = (8, 4, 2)   # card_reveal "blocks": Blockgroesse (Zellen) im ersten, zweiten, dritten Drittel des Einsatzes
REVEAL_SEED = 41           # card_reveal "noise": fester Zufall, gleiche Datei = gleiches Bild
ORBIT_KEYS = ("orbit_path", "orbit_frame", "orbit_loops", "orbit_cycle_beats", "orbit_type_out_at_beats",
              "orbit_type_out_beats", "orbit_spin_speedup")
ORBIT_PATH_KEYS = {"throw": ("orbit_throw_speedup",),
                   "dive": ("orbit_throw_speedup", "orbit_dive_lead_beats", "orbit_dive_core_shrink",
                            "orbit_dive_shutter_frac", "orbit_dive_drift_pow")}
PHASE_EPS = 1e-6     # Bahn: so nah an einer ganzen Phase = ganze Phase (Float-Rest aus Tempo x Zeit, sonst nie bitgleich)
TANGENT_H = 1e-3     # Schleuder: Schrittweite (Bahnframes) der zentralen Differenz fuer die Tangente beim Loslassen
RELEASE_JUMP = 1.5   # Selbsttest Bahn: Schritt beim Bahnwechsel hoechstens 1.5 x der groessere Nachbarschritt (sonst Sprung)
ZOOM_SMOOTH_PX = 6.0  # Zoom am Bild: Glaettung vor der Messung (Bayer-Korn 4 Zellen, steht im Bild fest)
ZOOM_LP_R, ZOOM_LP_A = 512, 360   # ... log-polares Raster (Radius, Winkel; Winkel durch 6 teilbar)
ZOOM_LP_INNER = 0.03              # ... innerster Radius als Bruchteil des aeussersten (darunter wenige Pixel je Ring)
STROBE_MAX = 0.3                  # ... ab 1 Puppe pro Bild hoechstens so viel Ringkontrast wie ohne Unschaerfe
RINGS_MIN = 0.5                   # ... unter 1/2 Puppe pro Bild mindestens so viel (die Matrjoschka bleibt erkennbar)
KINK_DEG = 10.0      # Selbsttest Bahn: Richtung der Mitte am Wechsel dreht hoechstens so viel (Uebergabe 3.10.: "kein Knick")
SLOW_EPS = 1e-6      # ... "nie langsamer": kleiner um mehr als Float-Rauschen
MOVE_PX = 0.5        # ... Umkehr zaehlt nur, wenn sich die Mitte in beiden Schritten sichtbar bewegt (halbes Pixel)
PROBE_FRAMES = 4     # ... Bilder vor und nach dem Bahnwechsel, an denen die Sternlage gemessen wird
THROW_SAMPLES = 256  # dive: Stuetzstellen fuer den Weg der Mitte (Integral von exp(-ln-Zuwachs), keine geschlossene Form)
DIGITAL_LOOPS_MAX = 1.0   # Vadim 3.10.: ab dem Wechsel ins Digitale hoechstens ein Umlauf bis zum Bahnwechsel ("zu teasing")
PROBE_FIT = 0.25     # ... Messstern hoechstens so gross (Bruchteil der Bildbreite): ein bildfuellender Stern (O5, F1 = 1.9 x
                     # Bildbreite) hat keine messbare Flaeche, die Gegenprobe war blind (x0.74). Massstab fest im Fenster
GONE_R_PX = 0.01     # Stern in der Ferne verschwunden: Radius so klein, dass keine Zellmitte mehr im Stern liegt


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
    assert not e["card_on"] or e["card_reveal"] in REVEALS, f"[ending].card_reveal: {' | '.join(REVEALS)}"
    assert not e["card_on"] or all(len(mv) == 5 and mv[0] in CARD_PARTS for mv in e["card_moves"]), \
        f"[ending].card_moves: [Teil, Beat, dx, dy, Massstab], Teil aus {CARD_PARTS}"
    ig = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kickoff_loop",
                                     m["loop_grid"])))
    bar, beat = 16 * ig["sixteenth_s"], ig["beat_s"]
    land = (e["carousel_bars"] + e["runout_bars"]) * bar
    end = e["length_bars"] * bar
    assert end > land, f"[ending].length_bars {e['length_bars']}: Video endet vor dem Karussell (Takt {land / bar:.2f})"
    if cfg["endcard"].get("end_mode") == "orbit":
        check_orbit(cfg, (end - land) / beat)
    m["file"] = m["loop_file"]
    return dict(bpm_carousel=ig["bpm"], bpm_end=ig["bpm"], sixteenth_s=ig["sixteenth_s"],
                carousel_bars=[[cfg["loop"]["changes_per_bar"] or 48, e["carousel_bars"]]],
                hits_s=[h for h in ig["hits_s"] if h <= end], downbeats_s=ig["downbeats_s"],
                burst_s=land, impact_s=land + cfg["endcard"]["burst_beats"] * beat, end_s=end,
                file_offset_s=ig["in_s"])


def runout_bars(cfg):
    """Takte, in denen das Rad bremst: runout_bars minus der Halt auf dem Landeframe (runout_hold_beats). Vorschau Z4
    vom 2.10.: ohne Halt fiel die Landung auf den Beginn des Digitalteils, F1 war nie als Plakat zu sehen, das Rad
    stand 1.8 s auf F32 und es schnitt hart in den Zoom (Zoom-Check: Sprung x5.8)."""
    e = cfg["ending"]
    return e["runout_bars"] - e["runout_hold_beats"] / 4


def runout_pow(cfg):
    """Steilheit des Auslaufs: Position = n (1 - (1 - u)^p). Anfangstempo n p / Dauer muss das Karussell-Tempo
    (changes_per_bar pro Takt) sein, also p = Bremstakte * changes_per_bar / n. 1.5 Takte, 48, 32 Frames → p = 2.25."""
    return runout_bars(cfg) * cfg["loop"]["changes_per_bar"] / cfg["loop"]["frames"]


def runout_times(cfg, p=None):
    """Wechselzeiten (s) des Auslaufs: n + 1 Wechsel (Neustart auf dem Taktstrich, dann ein Umlauf), auf das
    32tel-Triolen-Raster gerundet. Der letzte zeigt end_frame und steht dann runout_hold_beats bis zum Zoom (burst_s)."""
    g, n = cfg["music"]["grid"], cfg["loop"]["frames"]
    bar = 16 * g["sixteenth_s"]
    slot = bar / 48                                         # kickoff_loop.SUBDIV_PER_BAR
    t0, R = cfg["ending"]["carousel_bars"] * bar, runout_bars(cfg) * bar
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
    t0, R, p = cfg["ending"]["carousel_bars"] * bar * fps, runout_bars(cfg) * bar * fps, runout_pow(cfg)
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


# ---------------------------------------------------------------- Bahn: digitaler Loop, dann eine neue Bahn

def check_orbit(cfg, beats_left):
    """[ending] fuer end_mode = "orbit" pruefen und daraus [endcard].end_frame und [ending].orbit_at_beats setzen. Der
    digitale Loop setzt das Karussell im selben Tempo fort (changes_per_bar / 4 Bahnframes pro Beat), laeuft orbit_loops
    Umlaeufe und wechselt dann auf orbit_frame die Bahn. Daraus folgt, auf welchem Frame das Karussell endet und wann
    (Beats nach dem Karussell-Ende) der Wechsel ist (orbit_at_beats, abgeleitet)."""
    import kickoff_loop as KL
    e, n = cfg["ending"], cfg["loop"]["frames"]
    miss = [k for k in ORBIT_KEYS if k not in e]
    assert not miss, f"[ending] end_mode = orbit braucht noch: {', '.join(miss)}"
    path = e["orbit_path"]
    assert path in ORBIT_PATH_KEYS, f"[ending].orbit_path: {' | '.join(ORBIT_PATH_KEYS)}"
    miss = [k for k in ORBIT_PATH_KEYS[path] if k not in e]
    assert not miss, f"[ending] orbit_path = {path} braucht noch: {', '.join(miss)}"
    per_beat = cfg["loop"]["changes_per_bar"] / 4
    assert per_beat > 0, "[loop].changes_per_bar > 0: der digitale Loop laeuft im Karusselltempo weiter"
    f = e["orbit_frame"]
    assert type(f) is int and 1 <= f <= n, f"[ending].orbit_frame: ganzer Bahnframe 1..{n}"
    assert "orbit_at_beats" not in e or e.get("_orbit_derived"), \
        "[ending].orbit_at_beats: folgt aus orbit_loops (Umlaeufe digital bis zum Bahnwechsel), Zeile streichen"
    assert e["orbit_throw_speedup"] >= 1, "[ending]: orbit_throw_speedup >= 1 (Tempo-Faktor pro Beat, 1 = gleichmaessig)"
    if path == "dive":
        assert e["orbit_dive_lead_beats"] >= 0 and e["orbit_dive_core_shrink"] >= 0 and e["orbit_dive_drift_pow"] > 0 and \
            0 <= e["orbit_dive_shutter_frac"] <= 1, \
            "[ending]: orbit_dive_lead_beats >= 0, orbit_dive_core_shrink >= 0, orbit_dive_drift_pow > 0, orbit_dive_shutter_frac 0..1"
        bad = [KL.style_code(cfg, i) for i in range(f - 1, KL.posters(cfg), n) if KL.style_code(cfg, i) != "S33"]
        assert not bad, f"[ending].orbit_frame F{f}: dive taucht in die Matrjoschka, dort steht {bad[0]} statt S33"
    steps = e["orbit_loops"] * n                                          # Bahnframes digital bis zum Wechsel
    assert e["orbit_loops"] > 0 and abs(steps - round(steps)) < PHASE_EPS, \
        f"[ending].orbit_loops > 0, x {n} Frames ganzzahlig (sonst wechselt die Bahn zwischen zwei Frames)"
    end = (f - 2 - round(steps)) % n + 1                                  # Karussell endet davor, Loop startet danach
    given = cfg["endcard"].get("end_frame")
    assert given in (None, end), (f"[endcard].end_frame {given}: folgt bei end_mode = orbit aus orbit_frame/orbit_loops "
                                   f"(= {end}), Zeile streichen")
    cfg["endcard"]["end_frame"] = end
    e.update(orbit_at_beats=steps / per_beat, _orbit_derived=True)        # Bahnwechsel auf orbit_frame
    assert e["orbit_at_beats"] < beats_left, f"[ending]: Bahnwechsel nach {e['orbit_at_beats']:g} Beats, Video endet vorher"
    assert e["orbit_spin_speedup"] >= 1 and e["orbit_type_out_beats"] > 0 and e["orbit_cycle_beats"] >= 0, \
        "[ending]: orbit_spin_speedup >= 1, orbit_type_out_beats > 0, orbit_cycle_beats >= 0"
    lead = e["orbit_dive_lead_beats"] * per_beat if path == "dive" else 0.0   # Bahnframes Vorlauf (Kamera taucht ein)
    assert lead < steps, "[ending].orbit_dive_lead_beats: Eintauchen muss nach dem Karussell-Ende liegen"
    phi_s = f - 1 - lead
    dr = KL.orbit(cfg, (phi_s + TANGENT_H) % n)[2] - KL.orbit(cfg, (phi_s - TANGENT_H) % n)[2]
    assert (dr < 0) if path == "throw" else (dr > 0), (
        f"[ending]: {path} ab Bahnphase F{phi_s % n + 1:.2f}: dort {'waechst' if dr >= 0 else 'schrumpft'} der Stern. "
        f"throw braucht einen Frame, auf dem er schrumpft (F2..F16), dive einen Vorlauf im Anflug (F18..F32)")


def _snap(p):
    """Gebrochene Phase, die nur durch Float-Rest neben einer ganzen liegt, auf die ganze ziehen (bitgleich zum Plakat)."""
    r = round(p)
    return float(r) if abs(p - r) < PHASE_EPS else float(p)


def orbit_clock(cfg):
    """(Phase beim Karussell-Ende, Bahnframes pro Sekunde, Beat s). Das letzte Plakat (end_frame) steht bis zum
    Karussell-Ende, dann kommt auf dem Taktstrich end_frame + 1, weiter im Karusselltempo (T16: 16.32/s, 12 pro Beat)."""
    import kickoff_loop_video as V
    b = beat(cfg)
    return V.end_index(cfg) + 1, cfg["loop"]["changes_per_bar"] / 4 / b, b


def orbit_release(cfg):
    """(Zeit s nach dem Karussell-Ende, Bahnphase) des Bahnwechsels. orbit_at_beats setzt check_orbit (orbit_loops)."""
    phi0, per_s, b = orbit_clock(cfg)
    t = cfg["ending"]["orbit_at_beats"] * b
    return t, _snap(phi0 + per_s * t)


def orbit_px(cfg, phase):
    """Bahn bei gebrochener phase im 9:16-Bild: (x, y, R px, Drehung)."""
    import kickoff_loop as KL
    import kickoff_loop_video as V
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = V.digital_offset(cfg)
    x, y, r, rot = KL.orbit(cfg, phase % KL.count(cfg))
    return float(ox + x * pw), float(oy + y * ph), float(r * pw), rot


def orbit_kin(cfg, phase):
    """Zustand der Bahn im Bild bei phase: Lage (x, y, R px) und Tempo (vx, vy, vR in px/s), zentrale Differenz."""
    _, per_s, _ = orbit_clock(cfg)
    a, m, c = (orbit_px(cfg, phase + d)[:3] for d in (-TANGENT_H, 0.0, TANGENT_H))
    return m, tuple((cc - aa) / (2 * TANGENT_H) * per_s for aa, cc in zip(a, c))


def orbit_switch(cfg):
    """(Zeit s nach dem Karussell-Ende, Bahnphase), ab der der Stern die Ellipse verlaesst: throw beim Loslassen
    (orbit_frame), dive schon orbit_dive_lead_beats davor (die Kamera taucht im Anflug ein)."""
    phi0, per_s, b = orbit_clock(cfg)
    t_r, _ = orbit_release(cfg)
    e = cfg["ending"]
    t = t_r - (e["orbit_dive_lead_beats"] * b if e["orbit_path"] == "dive" else 0.0)
    return t, _snap(phi0 + per_s * t)


def _ramp(tau, b, k):
    """Integral von k^(s/b) ueber 0..tau (Tempo-Faktor k pro Beat, k = 1: gleichmaessig)."""
    return tau if abs(k - 1) < 1e-12 else b / math.log(k) * (k ** (tau / b) - 1)


def orbit_star(cfg, dt, jump=0.0):
    """Stern im 9:16-Bild dt s nach dem Karussell-Ende: dict(star = (x, y, R px, Drehung) oder None (weg), dolls =
    getauchte Puppen, blur = Breite der Dreiecksblende in Puppen (2 x Verschluss x Puppen je Bild: bei
    Verschluss 0.5 verschwinden die Ringe genau ab 1 Puppe pro Bild), loop = als Plakat zeichnen (Stil des Plakats, nur Lage/Groesse
    gegeben)). jump: nur Selbsttest (Gegenprobe), die neue Bahn startet so viele Bahnframes versetzt.
    Vadim 3.10. zu O4/O5: "ergeben logisch und physisch keinen Sinn, zu wenig Schwung, disconnected zum Loop".
    Befund 1.10.: O4 wurde im Bild langsamer (46 -> 3 px/Bild), O5 sprang im Wachstum x8 und bremste die Mitte hart.
    Beide Fortsetzungen starten jetzt am Zustand der Bahn im Bild (orbit_kin) und werden nur schneller:
      throw  (O6) gerade Linie in die Tiefe, perspektivisch exakt: fuer eine Gerade sind Radius und Abstand zum
             Fluchtpunkt beide ~ 1/Z. Gesteuert wird 1/Z selbst: R = R0 + R0' F, Mitte = c0 + v0 F, F = Integral von
             k^(t/b) (k = orbit_throw_speedup pro Beat). Bildtempo und Schrumpfen wachsen, bis er im Fluchtpunkt ist
             (endliche Zeit, "zack"). Braucht einen Frame, auf dem er schrumpft.
      dive   (O7) die Kamera taucht schon im Anflug ein (orbit_dive_lead_beats vor orbit_frame): Wachstumsrate
             g = g0 k^(t/b) ab der Rate der Bahn (nie langsamer, kein Sprung), die Mitte faehrt in ihrer Richtung
             weiter und laeuft mit dem Zoom aus (Tempo v0 (R0 / R)^orbit_dive_drift_pow: keine Umkehr, kein Ziel).
             Ab orbit_frame (S33, Schnitt wie im Loop) Infinite Zoom (KD.zoom_spark), Puppen = ln-Zuwachs seitdem.
    Drehung ab dem Loslassen: Bahntempo, das in jedem Beat um (orbit_spin_speedup - 1) x zulegt.
    ghost: ist er weg, wo er waere (Grund V3 legt die Tasche um c.L["star"], sonst springt sie in die Ecke)."""
    import kickoff_loop as KL
    import kickoff_loop_digital as KD
    e, n, sp = cfg["ending"], KL.count(cfg), cfg["spark"]
    W, H = cfg["video"]["size_px"]
    cell = S.BASE["R"] * S.SIZES["9x16"][2]
    phi0, per_s, b = orbit_clock(cfg)
    t_r, phi_r = orbit_release(cfg)
    t_s, phi_s = orbit_switch(cfg)
    k = e["orbit_throw_speedup"]
    w0 = sp["spin_deg"] / n * per_s                                          # Grad pro Sekunde auf der Bahn
    if dt <= t_r:
        rot = orbit_px(cfg, _snap(phi0 + per_s * dt))[3]
    else:
        tau = dt - t_r
        rot = orbit_px(cfg, phi_r + jump)[3] + w0 * (tau + 0.5 * (e["orbit_spin_speedup"] - 1) * tau * tau / b)
    if dt <= t_s:
        x, y, R, _ = orbit_px(cfg, _snap(phi0 + per_s * dt))
        return dict(star=(x, y, R, rot) if R > 0 else None, dolls=0.0, blur=0.0, loop=True)
    tau = dt - t_s
    (x0, y0, R0), (vx, vy, vR) = orbit_kin(cfg, phi_s + jump)
    if e["orbit_path"] == "dive":
        g0 = vR / R0
        G = lambda t: g0 * _ramp(t, b, k)                                   # noqa: E731  ln(R / R0)
        s = np.linspace(0.0, tau, THROW_SAMPLES)
        f = np.exp(-e["orbit_dive_drift_pow"] * G(s))
        drift = float(np.sum((f[1:] + f[:-1]) / 2 * np.diff(s)))           # Weg der Mitte / v0
        dolls = max(G(tau) - G(t_r - t_s), 0.0) / math.log(1 / KD.DOLL_RATIO)
        blur = 2 * e["orbit_dive_shutter_frac"] * g0 * k ** (tau / b) / math.log(1 / KD.DOLL_RATIO) / cfg["video"]["timeline_fps"]
        return dict(star=(x0 + vx * drift, y0 + vy * drift, R0 * math.exp(G(tau)), rot), dolls=dolls,
                    blur=blur if dt > t_r else 0.0, loop=dt <= t_r)
    F = _ramp(tau, b, k)
    cx, cy, R = x0 + vx * F, y0 + vy * F, R0 + vR * F
    clear = KL.STAR_CLEAR * max(R, 0.0)
    out = cx + clear < 0 or cx - clear > W or cy + clear < 0 or cy - clear > H
    if R < cell or out:
        return dict(star=None, ghost=(cx, cy, max(R, 0.0) if out else GONE_R_PX, rot), dolls=0.0, blur=0.0, loop=False)
    return dict(star=(cx, cy, R, rot), dolls=0.0, blur=0.0, loop=False)


def orbit_poster(cfg, dt):
    """Plakat (Index ueber alle Welten), dessen Farbe und Stern dt s nach dem Karussell-Ende gilt: laeuft im
    Karusselltempo weiter bis orbit_cycle_beats, dann steht es (Farbe der Endkarte)."""
    import kickoff_loop as KL
    phi0, per_s, b = orbit_clock(cfg)
    return int(math.floor(_snap(phi0 + per_s * min(dt, cfg["ending"]["orbit_cycle_beats"] * b)))) % KL.posters(cfg)


def orbit_state(cfg, dt, jump=0.0):
    """Stil-Dict des Bahn-Endes dt s nach dem Karussell-Ende (Ablauf: orbit_star). Im Loop-Teil exakt das Dict, das
    ein Plakat im Digitalteil hat (poster_digital), nur mit der Sternlage der gebrochenen Phase: an ganzen Phasen
    bitgleich. Danach: Titelblock zerfaellt im Korn (orbit_type_out_*), Endkarte (card_on). Deckt die Karte alles
    (card_dim_frac 1), steht der Stern still: gleiche Bilder rendern nur einmal."""
    import kickoff_loop as KL
    import kickoff_loop_video as V
    import kickoff_loop_digital as KD
    e = cfg["ending"]
    W, H = cfg["video"]["size_px"]
    ox, oy = V.digital_offset(cfg)
    b = beat(cfg)
    card = card_state(cfg, dt) if e["card_on"] else None
    card = card if card and (card["parts"] or card["dim"] > 0) else None
    t_star = dt                               # steht die Karte (erster Einsatz fertig), steht der Stern bzw. sein Grund:
    if e["card_on"]:                          # gleiche Bilder rendern nur einmal
        t_star = min(dt, (min(mv[1] for mv in e["card_moves"]) + e["card_in_beats"]) * b)
    os_ = orbit_star(cfg, t_star, jump)
    idx = orbit_poster(cfg, dt)
    st = KL.poster_style(cfg, idx)
    star = os_["star"]
    if not os_["loop"] and e["orbit_path"] == "dive":                      # Infinite Zoom in die Matrjoschka
        st.update(S=KL.S_CODES["S33"], spark_fn=KD.zoom_spark,
                  fx_behind_title="S33" in cfg["type"].get("effects_behind_title", []))
    if star is None:                          # weg: S2 (Labor-Stile messen am Stern, manche fuellen die Seite), unsichtbar
        star = os_.get("ghost") or (-3.0 * W, -3.0 * H, 1.0, 0.0)          # dort, wo er waere (Grund), sonst weit draussen
        st["S"], st["spark_fn"] = KL.S_CODES["S2"], K.spark
    tout = min(max((dt - e["orbit_type_out_at_beats"] * b) / (e["orbit_type_out_beats"] * b), 0.0), 1.0)
    dg = dict(u=0.0, offset=(ox, oy), star=star, show=None)
    if not os_["loop"] or tout > 0 or card:                                # sonst exakt das Plakat-Dict (bitgleich)
        dg.update(poster=idx, card=card, zoom=dict(dolls=round(os_["dolls"], 6), type_out=round(tout, 4), info=[],
                                                   info_in=0.0, core_shrink=e.get("orbit_dive_core_shrink", 0.0),
                                                   blur=round(os_.get("blur", 0.0), 4)))   # 0: throw, ohne Zoom
        st["type_fn"] = KD.zoom_card_type
    st["rot"] = star[3]                                                    # Labor-Sterne drehen nach st["rot"]
    st["loop"] = {**st["loop"], "digital": dg}
    st["star"] = (star[0] / W, star[1] / H, star[2] / W)
    return st


def poster_digital(cfg, i):
    """Plakat i im Digitalteil (9:16, Satz wie im letzten Foto, u = 0), Stern von KL.star_at: so saehe Plakat i aus,
    wenn das Karussell digital weiterliefe. Referenz fuer den Selbsttest (unabhaengig von orbit_state gebaut)."""
    import kickoff_loop as KL
    import kickoff_loop_video as V
    W, H = cfg["video"]["size_px"]
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = V.digital_offset(cfg)
    x, y, r, rot = KL.star_at(cfg, i % KL.count(cfg))
    st = KL.poster_style(cfg, i % KL.posters(cfg))
    star = (ox + x * pw, oy + y * ph, r * pw, rot)
    st["loop"] = {**st["loop"], "digital": dict(u=0.0, offset=(ox, oy), star=star, show=None)}
    st["star"] = (star[0] / W, star[1] / H, star[2] / W)
    return st


def _rel_step(a, c):
    """Sichtbarer Weg zwischen zwei Sternlagen relativ zur Sterngroesse: Mittenweg / Radius + |Delta ln Radius|. So
    zaehlt ein Stern in der Ferne, der sich wenig bewegt, so viel wie ein naher, der weit faehrt (wie das Auge)."""
    return math.hypot(c[0] - a[0], c[1] - a[1]) / max(a[2], 1e-9) + abs(math.log(c[2] / a[2]))


def orbit_measure(cfg, jump=0.0):
    """Befund "clean" (Uebergabe 3.10.) an der Bahn, je Videobild (24 fps) ab PROBE_FRAMES Bildern vor dem Verlassen der
    Ellipse bis der Stern weg ist, die Karte alles deckt oder 2 Beats um sind. Schritt = (dx, dy px, d ln R, Drehung).
    dict(kink = Winkel Grad zwischen dem Schritt davor und dem ersten danach, jump = |v| danach / davor, gjump = |d ln R|
    danach / davor, slow = Schritte danach, in denen eine Groesse kleiner wird (throw: |v| und |d ln R|; dive: d ln R und
    Sehfluss |v| + d ln R x rms-Bildradius; beide: Drehung), turn = Richtungsumkehren der Mitte (Skalarprodukt < 0), track = Schritte
    danach, gone_s = s nach dem Karussell-Ende, ab der der Stern weg ist (None: bleibt), on = Mitte am Ende im Bild).
    Am alten O4 (1.10.): |v| fiel 24 von 25 Schritten; alter O5: d ln R sprang x8.1, Sehfluss fiel 7x."""
    e = cfg["ending"]
    fps = cfg["video"]["timeline_fps"]
    W, H = cfg["video"]["size_px"]
    b = beat(cfg)
    t_s, _ = orbit_switch(cfg)
    k0 = math.floor(t_s * fps) + 1                                         # erstes Bild nach dem Verlassen
    end = t_s + 2 * b
    if e["card_on"] and e["card_dim_frac"] >= 1:
        end = min(end, (min(mv[1] for mv in e["card_moves"]) + e["card_in_beats"]) * b)
    seq, gone = [], None
    for kk in range(k0 - PROBE_FRAMES, max(math.floor(end * fps) + 1, k0 + 2)):
        st = orbit_star(cfg, kk / fps, jump)["star"]
        if st is None:
            gone = kk / fps
            break
        seq.append(st)
    steps = [(c[0] - a[0], c[1] - a[1], math.log(c[2] / a[2]), abs((c[3] - a[3] + 30) % 60 - 30)) for a, c in zip(seq, seq[1:])]
    j = PROBE_FRAMES - 1                                                   # vom letzten Bild davor zum ersten danach
    u, v = steps[j - 1], steps[j]
    nu, nv = math.hypot(*u[:2]), math.hypot(*v[:2])
    kink = math.degrees(math.acos(max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / max(nu * nv, 1e-12)))))
    after = steps[j:]
    sizes = [math.hypot(*x[:2]) for x in after]
    rates = [abs(x[2]) for x in after]
    spins = [x[3] for x in after]
    r_rms = math.sqrt((W * W + H * H) / 12)                                # mittlerer Abstand der Bildpunkte zur Mitte (rms)
    flow = [sz + r * r_rms for sz, r in zip(sizes, rates)]

    def falls(xs):
        return sum(1 for a, c in zip(xs, xs[1:]) if c < a * (1 - SLOW_EPS))
    slow = falls(rates) + falls(spins) + (falls(flow) if e["orbit_path"] == "dive" else falls(sizes))
    turn = sum(1 for a, c in zip(after, after[1:])
               if math.hypot(*a[:2]) > MOVE_PX and math.hypot(*c[:2]) > MOVE_PX and a[0] * c[0] + a[1] * c[1] < 0)
    x, y = seq[-1][:2]
    return dict(kink=kink, jump=nv / max(nu, 1e-12), gjump=abs(v[2]) / max(abs(u[2]), 1e-12), slow=slow, turn=turn,
                track=len(after), gone_s=gone, on=0 <= x <= W and 0 <= y <= H,
                v=sizes, g=rates)


def orbit_clean(m):
    """Gates fuer orbit_measure: kein Knick (Winkel <= KINK_DEG, Tempo und Rate x1/RELEASE_JUMP..RELEASE_JUMP),
    danach nie langsamer, keine Umkehr, die Mitte bleibt im Bild oder er ist weg."""
    lo = 1 / RELEASE_JUMP
    return (m["kink"] <= KINK_DEG and lo <= m["jump"] <= RELEASE_JUMP and lo <= m["gjump"] <= RELEASE_JUMP
            and m["slow"] == 0 and m["turn"] == 0 and (m["on"] or m["gone_s"] is not None))


def orbit_report(cfg):
    """Zeilen fuer report.txt (Bahn-Ende): Ablauf mit Zeiten ab Videoanfang, Bahn-Check (orbit_measure)."""
    import kickoff_loop as KL
    e, g = cfg["ending"], cfg["music"]["grid"]
    phi0, per_s, b = orbit_clock(cfg)
    t_r, phi_r = orbit_release(cfg)
    t_s, phi_s = orbit_switch(cfg)
    m = orbit_measure(cfg)
    at, n = g["burst_s"], KL.count(cfg)
    land = orbit_poster(cfg, 1e9)
    what = (f"Kamera taucht ab F{phi_s % n + 1:.2f} bei {at + t_s:.2f} s ein (Zoomrate = Wachstum der Bahn, x"
            f"{e['orbit_throw_speedup']:g} pro Beat), Mitte laeuft mit dem Zoom aus, Infinite Zoom ab F{phi_r % n + 1:.0f} "
            f"bei {at + t_r:.2f} s, Verschluss {e['orbit_dive_shutter_frac']:g}"
            if e["orbit_path"] == "dive" else
            f"Wurf in die Tiefe ab F{phi_r % n + 1:.0f} bei {at + t_r:.2f} s (gerade Linie zum Fluchtpunkt, Bildtempo x"
            f"{e['orbit_throw_speedup']:g} pro Beat)")
    return [f"Ende Bahn: digitaler Loop ab F{phi0 % n + 1} auf dem Karussell-Ende {at:.2f} s "
            f"({t_r * per_s / n:.2f} Umlaeufe, 24 fps), dann {what}, Drehung x{e['orbit_spin_speedup']:g} pro Beat. "
            f"Farbe/Stern wechseln bis {at + e['orbit_cycle_beats'] * b:.2f} s, Endfarbe Plakat {land + 1} "
            f"({KL.station_label(cfg, land)})",
            f"Bahn-Check {'ok' if orbit_clean(m) else 'FEHLER'}: Knick {m['kink']:.1f} Grad (Grenze {KINK_DEG}), Tempo "
            f"x{m['jump']:.2f}, Rate x{m['gjump']:.2f} am Wechsel (x{1 / RELEASE_JUMP:.2f}-x{RELEASE_JUMP}), ueber "
            f"{m['track']} Bilder {m['slow']}x langsamer, {m['turn']}x Umkehr, Stern "
            + (f"weg ab {at + m['gone_s']:.2f} s" if m["gone_s"] is not None else
               ("Mitte im Bild" if m["on"] else "MITTE AUS DEM BILD"))]


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
    lay = {k[5:]: e[k] for k in CARD_KEYS if k not in ("card_reveal", "card_diff", "card_moves", "card_in_beats",
                                                       "card_overshoot", "card_dim_frac")}
    return dict(group=round(group, 5), parts=parts, dim=round(dim, 3), layout=lay, reveal=e["card_reveal"],
                diff=bool(e["card_diff"]))


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


def reveal(c, m, a, mode):
    """Einsatz im Dither statt Blende (Vadim 2.10.: "mit so einem Dither-Effekt auftauchen, kein langer Fade"), a 0..1:
    bayer  Zellen kippen in Bayer-Reihenfolge     noise  Zellen ploppen in fester Zufallsreihenfolge
    blocks erst grobe Bloecke (REVEAL_BLOCKS), dann feiner, je im Bayer-Raster der Blockgroesse.
    a >= 1 gibt m exakt zurueck."""
    if a >= 1:
        return m
    if mode == "noise":
        return m & (np.random.default_rng(REVEAL_SEED).random(m.shape) < a)
    if mode == "blocks":
        B = REVEAL_BLOCKS[min(int(a * len(REVEAL_BLOCKS)), len(REVEAL_BLOCKS) - 1)]
        h, w = -(-m.shape[0] // B), -(-m.shape[1] // B)
        pad = np.zeros((h * B, w * B), bool)
        pad[:m.shape[0], :m.shape[1]] = m
        blk = pad.reshape(h, B, w, B).any((1, 3)) & (S.tile(S.bayer(4), (h, w)) < a)
        return S.up(blk, B)[:m.shape[0], :m.shape[1]]
    return m & (bayer(c) < a)


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
        return reveal(c, out, a, cs["reveal"])

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
            glow = reveal(c, (g > GLOW_MIN) & ~plate, a, cs["reveal"])
            u = KL.under(c)
            c.add("qr", glow, u + (hi - u) * g)
            c.add("qr", reveal(c, plate, a, cs["reveal"]), hi)
            c.add("qr", reveal(c, mods & plate, a, cs["reveal"]), lo)
            continue
        m = place(base[name], a, s, dx, dy)
        if m.any():
            ink = np.full((c.gh, c.gw), c.lvl(c.N), np.float32)
            c.add(name, m, KL.title_value(c, ink) if cs["diff"] else ink)   # diff: wie SPARK auf dem Plakat, Effekte
                                                                            # laufen invertiert durch (Difference-Ebene)


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
                   f"Potenz {runout_pow(cfg):.2f}, landet auf F{tl.changes[-1][1] + 1} bei {ts[-1]:.2f} s, steht bis {g['burst_s']:.2f} s")
    if cfg["endcard"].get("end_mode") == "orbit":
        out += orbit_report(cfg)
    return out


def orbit_selftest(cfg):
    """Bahn-Ende, am fertigen Bild wo es um Bilder geht:
    (1) Loop bitgleich: an ganzen Phasen vor dem Verlassen der Ellipse ist das Bild = poster_digital (Plakat i im
        Digitalteil, Stern aus KL.star_at). Gegenprobe: eine halbe Phase spaeter muss es abweichen.
    (2) Bahn stetig am Bild: Stern als S2 auf fester Palette, je Bild einmal mit und einmal ohne Stern gerendert; die
        Differenz ist die Sternflaeche, gemessen Schwerpunkt + Wurzel der Flaeche um den Wechsel. Schritt beim Wechsel
        hoechstens RELEASE_JUMP x Nachbarschritt. Gegenprobe: neue Bahn 1 Bahnframe versetzt (jump) muss anschlagen.
    (3) clean (orbit_clean): kein Knick, nie langsamer, keine Umkehr. Gegenproben: throw mit Tempo-Faktor 0.5 pro Beat
        (wird langsamer wie der alte O4), dive ohne Vorlauf aus dem Nahpunkt F1 (Zoom aus dem Stand wie der alte O5).
    (4) dive: Stroboskop am Bild (zoom_rate_check): schnelle Ringe verwischt, langsame sichtbar.
    (5) Hoechstens DIGITAL_LOOPS_MAX Umlaeufe digital bis zum Wurf. Gegenprobe: die Laenge von v1 (2.5) muss anschlagen."""
    import copy
    import kickoff_loop as KL
    lines, ok = [], True
    n, W, H = KL.count(cfg), *cfg["video"]["size_px"]

    def img(st):
        return KL.render_cached(st, "9x16", "end")
    phi0, per_s, b = orbit_clock(cfg)
    t_s, _ = orbit_switch(cfg)
    js = [j for j in (0, 5, 11) if j / per_s < t_s]
    same = [np.array_equal(img(orbit_state(cfg, j / per_s)), img(poster_digital(cfg, phi0 + j))) for j in js]
    bites = not np.array_equal(img(orbit_state(cfg, (js[-1] + 0.5) / per_s)), img(poster_digital(cfg, phi0 + js[-1])))
    lines.append(f"Loop bitgleich zum Plakat an ganzen Phasen (Plakate {', '.join(str(phi0 + j + 1) for j in js)}): "
                 f"{'ok' if all(same) else 'FEHLER'}; Gegenprobe halbe Phase: {'schlaegt an' if bites else 'TEST BLIND'}")
    ok &= all(same) and bites

    fps = cfg["video"]["timeline_fps"]
    k0 = math.floor(t_s * fps) + 1
    ks = range(k0 - PROBE_FRAMES, k0 + PROBE_FRAMES)
    P0 = orbit_state(cfg, ks[0] / fps)["P"]

    def probe(jump):
        """Sternlage am Bild je Bild ks: (Schwerpunkt x, y, Wurzel der Flaeche) in Bildpixeln. Radius im ganzen Fenster
        mit demselben Faktor verkleinert (PROBE_FIT), Lage unveraendert: Spruenge in Lage und Massstab bleiben sichtbar."""
        out = []
        fit = min(1.0, PROBE_FIT * W / max(orbit_star(cfg, k / fps, jump)["star"][2] for k in ks))
        for k in ks:
            st = orbit_state(cfg, k / fps, jump)
            dg = st["loop"]["digital"]
            x, y, R, rot = dg["star"]
            dg = {**dg, "star": (x, y, R * fit, rot)}
            st.update(S=KL.S_CODES["S2"], P=P0, spark_fn=K.spark, type_fn=KL.type_layers)
            st.pop("ground", None)                                         # Grund um den Stern (V3) aendert sonst alles
            on = {**st, "loop": {**st["loop"], "digital": dict(u=0.0, offset=dg["offset"], star=dg["star"], show=None)}}
            off = {**st, "loop": {**st["loop"], "digital": dict(u=0.0, offset=dg["offset"], star=(-3.0 * W, -3.0 * H, 1.0, 0.0),
                                                                show=None)}}
            m = (img(on) != img(off)).any(-1)
            ys, xs = np.nonzero(m)
            out.append((xs.mean(), ys.mean(), math.sqrt(m.sum())))
        st = [math.hypot(c[0] - a[0], c[1] - a[1]) + abs(c[2] - a[2]) for a, c in zip(out, out[1:])]
        j = PROBE_FRAMES - 1                                               # Schritt vom letzten Bild davor zum ersten danach
        return st[j] / max(st[j - 1], st[j + 1], 1e-9)
    good, bad = probe(0.0), probe(1.0)
    lines.append(f"Bahn stetig am Bild (Sternflaeche S2): Schritt beim Wechsel x{good:.2f} des groesseren Nachbarn "
                 f"(Grenze x{RELEASE_JUMP}): {'ok' if good <= RELEASE_JUMP else 'FEHLER'}; Gegenprobe 1 Bahnframe versetzt "
                 f"x{bad:.2f}: {'schlaegt an' if bad > RELEASE_JUMP else 'TEST BLIND'}")
    ok &= good <= RELEASE_JUMP < bad

    m = orbit_measure(cfg)
    probe_cfg = copy.deepcopy(cfg)                                         # ohne check_orbit: bewusst falsche Werte
    if cfg["ending"]["orbit_path"] == "dive":
        probe_cfg["ending"]["orbit_dive_lead_beats"] = 0.0
        what = "ohne Vorlauf aus F1 (Zoom aus dem Stand, alter O5)"
    else:
        probe_cfg["ending"]["orbit_throw_speedup"] = 0.5
        what = "Tempo x0.5 pro Beat (wird langsamer, alter O4)"
    m2 = orbit_measure(probe_cfg)
    lines.append(f"Bahn clean: Knick {m['kink']:.1f} Grad, Tempo x{m['jump']:.2f}, Rate x{m['gjump']:.2f}, "
                 f"{m['slow']}x langsamer, {m['turn']}x Umkehr ueber {m['track']} Bilder: "
                 f"{'ok' if orbit_clean(m) else 'FEHLER'}; Gegenprobe {what}: "
                 f"{'schlaegt an' if not orbit_clean(m2) else 'TEST BLIND'} ({m2['slow']}x langsamer, Rate x{m2['gjump']:.2f})")
    ok &= orbit_clean(m) and not orbit_clean(m2)

    if cfg["ending"]["orbit_path"] == "dive":
        good, more = zoom_rate_check(cfg)
        lines += more
        ok &= good

    def loops(c):                                                          # Bahnframes vom Karussell-Ende bis zum Wurf
        return orbit_release(c)[0] * orbit_clock(c)[1] / n
    old = copy.deepcopy(cfg)
    old["ending"]["orbit_loops"] = 2.5
    del old["endcard"]["end_frame"]
    check_orbit(old, 1e9)
    got, bad = loops(cfg), loops(old)
    lines.append(f"Digital bis zum Wurf: {got:.2f} Umlaeufe (hoechstens {DIGITAL_LOOPS_MAX:g}): "
                 f"{'ok' if got <= DIGITAL_LOOPS_MAX + PHASE_EPS else 'FEHLER'}; Gegenprobe v1-Laenge {bad:.2f}: "
                 f"{'schlaegt an' if bad > DIGITAL_LOOPS_MAX + PHASE_EPS else 'TEST BLIND'}")
    ok &= got <= DIGITAL_LOOPS_MAX + PHASE_EPS < bad
    return ok, lines


def _ring_contrast(im, centre, rmax, per_doll):
    """Kontrast der Puppenringe im Bild: Graustufen geglaettet (das Bayer-Korn steht fest), log-polar abgewickelt
    (eigenes Raster, cv2.warpPolar lieferte im Log-Modus nan), die 6 Zacken uebereinander, Strahl mit den schaerfsten
    Ringen, davon der Anteil unterhalb einer Puppe (Hochpass): Standardabweichung."""
    from scipy.ndimage import gaussian_filter1d
    r = np.exp(np.linspace(math.log(rmax * ZOOM_LP_INNER), math.log(rmax), ZOOM_LP_R))
    ang = np.linspace(0, 2 * np.pi, ZOOM_LP_A, endpoint=False)[:, None]
    mx = (centre[0] + r[None] * np.cos(ang)).astype(np.float32)
    my = (centre[1] + r[None] * np.sin(ang)).astype(np.float32)
    g = cv2.GaussianBlur(im.mean(-1).astype(np.float32), (0, 0), ZOOM_SMOOTH_PX)
    six = cv2.remap(g, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).reshape(6, ZOOM_LP_A // 6, -1).mean(0)
    p = six[int(np.argmax(six.std(1)))]
    steps = per_doll * (ZOOM_LP_R - 1) / -math.log(ZOOM_LP_INNER)          # Raster-Schritte pro Puppe
    return float((p - gaussian_filter1d(p, steps)).std())


def zoom_rate_check(cfg):
    """dive: Stroboskop am fertigen Bild. Der Zoom uebernimmt das Tempo der Bahn (O7: ab 0.37 Puppen pro Bild, nah an der
    Grenze 1/2, ab der periodische Ringe rueckwaerts zu laufen scheinen) und zieht an. Gemessen: Ringkontrast
    (_ring_contrast um die Sternmitte, nur der Stern) mit Bewegungsunschaerfe / ohne, je Bild ab 1 Puppe pro Bild.
    Ok, wenn er dort hoechstens STROBE_MAX ist (Ringe verwischt), und unter 1/2 Puppe pro Bild mindestens RINGS_MIN (die
    Puppen bleiben sichtbar, solange nichts flackert)."""
    import copy
    import kickoff_loop as KL
    import kickoff_loop_digital as KD
    fps = cfg["video"]["timeline_fps"]
    W, H = cfg["video"]["size_px"]
    b = beat(cfg)
    t_r, _ = orbit_release(cfg)
    e = cfg["ending"]
    end = (min(mv[1] for mv in e["card_moves"])) * b if e["card_on"] else t_r + 2 * b
    doll = math.log(1 / KD.DOLL_RATIO)
    sharp = copy.deepcopy(cfg)
    sharp["ending"]["orbit_dive_shutter_frac"] = 0.0
    fast, slow = [], []
    for k in range(math.floor(t_r * fps) + 1, math.floor(end * fps), 2):
        pair = []
        for c in (cfg, sharp):
            st = orbit_state(c, k / fps)
            dg = st["loop"]["digital"]
            st["loop"] = {**st["loop"], "digital": {**dg, "card": None, "zoom": {**dg["zoom"], "type_out": 1.0}}}
            x, y = dg["star"][:2]
            centre = (min(max(x, 1.0), W - 2.0), min(max(y, 1.0), H - 2.0))
            pair.append(_ring_contrast(np.asarray(KL.render_cached(st, "9x16", "end")), centre, min(W, H) / 2, doll))
        rate = math.log(orbit_star(cfg, k / fps)["star"][2] / orbit_star(cfg, (k - 1) / fps)["star"][2]) / doll
        (fast if rate >= 1 else slow if rate < 0.5 else []).append(pair[0] / max(pair[1], 1e-9))
    good = bool(fast) and max(fast) <= STROBE_MAX and (not slow or min(slow) >= RINGS_MIN)
    return good, [f"Stroboskop am Bild: Ringkontrast mit/ohne Unschaerfe ab 1 Puppe pro Bild {max(fast, default=0):.2f} "
                  f"({len(fast)} Bilder, hoechstens {STROBE_MAX}), unter 1/2 Puppe {min(slow, default=1):.2f} "
                  f"({len(slow)} Bilder, mind. {RINGS_MIN}): {'ok' if good else 'FEHLER'}"]


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
        land = (cfg["ending"]["carousel_bars"] + runout_bars(cfg)) * bar             # sichtbar gelandet, vor dem Zoom
        good = brakes(ts) and abs(ts[-1] - land) < 1e-6 and ts[-1] < cfg["music"]["grid"]["burst_s"] \
            and tl.changes[-1][1] == V.end_index(cfg)
        bites = not brakes(runout_times(cfg, p=1))
        lines.append(f"Auslauf: {'ok' if good else 'FEHLER'} (bremst ab, landet auf F{tl.changes[-1][1] + 1}); "
                     f"Gegenprobe linear: {'schlaegt an' if bites else 'TEST BLIND'}")
        ok &= good and bites
        fps = cfg["video"]["timeline_fps"]
        t0 = cfg["ending"]["carousel_bars"] * bar * fps
        v0, v1 = camera_u(cfg, tl, t0) - camera_u(cfg, tl, t0 - 1), camera_u(cfg, tl, t0 + 1) - camera_u(cfg, tl, t0)
        end = tl.zoom_end - 1
        vend = camera_u(cfg, tl, end) - camera_u(cfg, tl, end - 1)
        cam = abs(v1 - v0) / v0 < 0.02 and vend < 0.01 * v0 and abs(camera_u(cfg, tl, land * fps) - 1) < 1e-9
        lines.append(f"Kamera: Tempo vor/nach Auslauf-Beginn {v0:.5f}/{v1:.5f}, am Ende {vend:.6f}: {'ok' if cam else 'FEHLER'}")
        ok &= cam
    c = _cells(270, 480)
    m = np.zeros((480, 270), bool)
    m[100:300, 50:200] = True
    same = (warp(c, m, 1.0) == m).all()
    q = warp(c, m, 0.5).sum() / m.sum()
    good = same and 0.2 < q < 0.3
    lines.append(f"warp: Identitaet {'ok' if same else 'FEHLER'}, s 0.5 → Flaeche x{q:.3f} (~0.25): {'ok' if good else 'FEHLER'}")
    if cfg["endcard"].get("end_mode") == "orbit":
        ob, more = orbit_selftest(cfg)
        lines += more
        good &= ob
    return ok and good, lines


if __name__ == "__main__":
    import kickoff_loop as KL
    if len(sys.argv) < 3 or sys.argv[1] != "test":
        sys.exit(__doc__)
    ok, lines = selftest(KL.load(sys.argv[2]))
    print("\n".join(lines))
    sys.exit(0 if ok else 1)
