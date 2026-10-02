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
from scipy.ndimage import binary_dilation, distance_transform_edt

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
MORPH = {"title": ("title",), "date": ("what", "when"), "qr": ("qr",), "cta": ("cta",)}   # Plakatsatz -> Kartenteile
REVEAL_BLOCKS = (8, 4, 2)   # card_reveal "blocks": Blockgroesse (Zellen) im ersten, zweiten, dritten Drittel des Einsatzes
REVEAL_SEED = 41           # card_reveal "noise": fester Zufall, gleiche Datei = gleiches Bild
ORBIT_KEYS = ("orbit_path", "orbit_frame", "orbit_loops", "orbit_loop_speedup", "orbit_cycle_beats",
              "orbit_type_morph", "orbit_type_out_at_beats", "orbit_type_out_beats", "orbit_spin_speedup",
              "orbit_flow_at_beats", "orbit_flow_in_beats", "orbit_flow_steps", "orbit_flow_per_beat")
ORBIT_PATH_KEYS = {"throw": ("orbit_throw_speedup",),
                   "dive": ("orbit_throw_speedup", "orbit_dive_lead_frames", "orbit_dive_core_shrink",
                            "orbit_dive_shutter_frac", "orbit_dive_drift_pow", "orbit_dive_target",
                            "orbit_dive_target_ease")}
FINALE_KEYS = ("orbit_zoom_peak_beats", "orbit_zoom_decay", "orbit_spin_stop_beats", "orbit_spin_rest_deg", "orbit_glow_frames", "orbit_glow_max_scale",
               "orbit_dissolve", "orbit_dissolve_at_beats", "orbit_dissolve_beats", "orbit_dissolve_scale",
               "orbit_words", "orbit_words_at_beats", "orbit_words_beats", "orbit_words_grow_beats",
               "orbit_words_fade_beats", "orbit_words_effect", "orbit_close_at_beats", "orbit_close_beats",
               "orbit_sparks", "orbit_sparks_ratio", "orbit_sparks_spin_deg", "orbit_sparks_dim", "orbit_sparks_colors", "orbit_zoom_max_per_frame")
STAR_SYM_DEG = 60.0  # der Stern hat 6 Zacken: alle 60 Grad steht er wieder gleich (gerade)
GLOW_SAMPLES = 16    # Zoom-Gluehen: so viele vergroesserte Kopien der Schrift (darunter zerfaellt der Schweif in Stufen)
FRAG_SEED = 43       # QR-Zerfall: fester Zufall je Splitter (Tiefe, Verzoegerung), gleiche Datei = gleiches Bild
FRAG_DELAY = 0.5     # ... Splitter starten in der ersten Haelfte des Zerfalls, fliegen in der zweiten
FRAG_DEPTH = (0.35, 1.0)   # ... Anteil am vollen Wachstum orbit_dissolve_scale je Splitter (Parallaxe: nahe fliegen schneller)
WORD_SEED = 47             # Begriffe: fester Zufall je Begriff (Reihenfolge der Pixel, Funken), gleiche Datei = gleiches Bild
RIPPLE_ECHOES = ((0, 1.0), (1, 0.6), (2, 0.35), (3, 0.2))   # ripple: Ring + Nachlaeufer (Abstand, Gewicht) wie motionpack._ripple
RIPPLE_SPACING = 2.5       # ... Abstand der Nachlaeufer in Ringbreiten (motionpack: 0.09 bei Breite 0.035)
RIPPLE_POW = 0.8           # ... Front bremst wie in der Referenz (front ~ p^0.8)
WORD_MIN_CAP_CELLS = 3     # zoom: kleiner gesetzt ist ein Begriff nur Korn (Clash rastert mindestens 6 pt), also nicht zeichnen
WORD_EFFECTS = {"sparkle": ("orbit_words_flash_frac",),
                "ripple": ("orbit_words_ring_reach", "orbit_words_ring_width"),
                "zoom": ("orbit_words_zoom_from_px", "orbit_words_zoom_cap_frac", "orbit_words_zoom_gap_frac")}
PHASE_EPS = 1e-6    # Bahn: so nah an einer ganzen Phase = ganze Phase (Float-Rest aus Tempo x Zeit, sonst nie bitgleich)
TANGENT_H = 1e-3     # Schleuder: Schrittweite (Bahnframes) der zentralen Differenz fuer die Tangente beim Loslassen
RELEASE_JUMP = 1.5   # Selbsttest Bahn: Schritt beim Bahnwechsel hoechstens 1.5 x der groessere Nachbarschritt (sonst Sprung)
ZOOM_SMOOTH_PX = 6.0  # Zoom am Bild: Glaettung vor der Messung (Bayer-Korn 4 Zellen, steht im Bild fest)
ZOOM_LP_R, ZOOM_LP_A = 512, 360   # ... log-polares Raster (Radius, Winkel; Winkel durch 6 teilbar)
ZOOM_LP_INNER = 0.03              # ... innerster Radius als Bruchteil des aeussersten (darunter wenige Pixel je Ring)
STROBE_MAX = 0.3                  # ... ab 1 Puppe pro Bild hoechstens so viel Ringkontrast wie ohne Unschaerfe
SPARKS_PER_FRAME = 0.5           # O9: hoechstens eine neue Stern-Puppe je 2 Bilder
RINGS_MIN = 0.5                   # ... unter 1/2 Puppe pro Bild mindestens so viel (die Matrjoschka bleibt erkennbar)
KINK_DEG = 10.0      # Selbsttest Bahn: Richtung der Mitte am Wechsel dreht hoechstens so viel mehr/weniger als davor ("kein Knick")
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
        tg = e["orbit_dive_target"]
        assert e["orbit_dive_lead_frames"] >= 0 and e["orbit_dive_core_shrink"] >= 0 and e["orbit_dive_drift_pow"] > 0 and \
            0 <= e["orbit_dive_shutter_frac"] <= 1 and e["orbit_dive_target_ease"] > 0 and (tg == [] or (len(tg) == 2 and all(0 <= v <= 1 for v in tg))), \
            ("[ending]: orbit_dive_lead_frames >= 0, orbit_dive_core_shrink >= 0, orbit_dive_drift_pow > 0, "
             "orbit_dive_shutter_frac 0..1, orbit_dive_target_ease > 0, orbit_dive_target [] (frei) oder [x, y] als Bruchteil des Bildes")
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
    a = e["orbit_loop_speedup"]
    assert a >= 1, "[ending].orbit_loop_speedup >= 1 (Tempo des digitalen Loops x a pro Beat, 1 = T16 gleichmaessig)"
    assert e["orbit_flow_in_beats"] > 0 and e["orbit_flow_steps"] >= 0 and e["orbit_flow_per_beat"] >= 0, \
        "[ending]: orbit_flow_in_beats > 0, orbit_flow_steps >= 0, orbit_flow_per_beat >= 0"
    if any(k in e for k in FINALE_KEYS):                                  # O8: Titel bleibt, QR zerfaellt, Abschluss
        miss = [k for k in FINALE_KEYS if k not in e]
        assert not miss, f"[ending] Finale (O8) braucht noch: {', '.join(miss)}"
        assert path == "dive" and not e["card_on"], "[ending] Finale: nur mit orbit_path = dive und card_on = false"
        assert e["orbit_spin_stop_beats"] > 0 and e["orbit_glow_frames"] >= 0 and e["orbit_glow_max_scale"] >= 1 \
            and e["orbit_dissolve_beats"] > 0 and e["orbit_dissolve_scale"] >= 1 \
            and e["orbit_close_beats"] > 0 and 0 < e["orbit_zoom_decay"] <= 1, (
                                             "[ending] Finale: orbit_zoom_decay 0..1, orbit_spin_stop_beats > 0, orbit_glow_frames >= 0, "
                                             "orbit_glow_max_scale >= 1, orbit_dissolve_beats > 0, orbit_dissolve_scale >= 1, "
                                             "orbit_close_beats > 0")
        ws = e["orbit_words"]
        assert ws and all(isinstance(w, list) and w and all(isinstance(x, str) for x in w) for w in ws) \
            and e["orbit_words_beats"] > 0 and e["orbit_words_grow_beats"] > 0 and e["orbit_words_fade_beats"] >= 0 \
            and e["orbit_words_grow_beats"] + e["orbit_words_fade_beats"] <= e["orbit_words_beats"], (
                "[ending] Finale: orbit_words = [[\"ZEILE\", ...], ...] (je Begriff eine Liste Zeilen, der letzte bleibt), "
                "orbit_words_beats > 0, orbit_words_fade_beats >= 0 (0 = Pixel landen direkt in der Tinte), "
                "orbit_words_grow_beats + orbit_words_fade_beats <= orbit_words_beats")
        fx = e["orbit_words_effect"]
        assert fx in WORD_EFFECTS, f"[ending].orbit_words_effect: {' | '.join(WORD_EFFECTS)}, nicht {fx!r}"
        miss = [k for k in WORD_EFFECTS[fx] if k not in e]
        assert not miss, f"[ending] orbit_words_effect = {fx} braucht noch: {', '.join(miss)}"
        assert all(e[k] > 0 for k in WORD_EFFECTS[fx]), f"[ending]: {', '.join(WORD_EFFECTS[fx])} > 0"
        sp = e["orbit_sparks"]
        bad = [x for x in sp if x not in KL.S_CODES]
        assert sp and not bad and 0 < e["orbit_sparks_ratio"] < 1 and e["orbit_zoom_max_per_frame"] > 1 \
            and 0 < e["orbit_sparks_dim"] <= 1, (
            f"[ending]: orbit_sparks = Stern-Codes aus [styles].cycle (unbekannt: {bad}), orbit_sparks_ratio 0..1, "
            "orbit_zoom_max_per_frame > 1 (Massstab pro Bild), orbit_sparks_dim 0..1 (1 = nicht abdimmen)")
        bad = [x for x in e["orbit_sparks_colors"] if x != KL.BW and not KL.station_ok(x)]
        assert not bad, (f"[ending].orbit_sparks_colors: Stationen wie in [color].worlds (\"P11\", \"~P23/P13\") oder "
                         f"\"{KL.BW}\" (Schwarz-Weiss), nicht {bad}")
        bad = [x for x in e["orbit_dissolve"] if x not in ("qr", "cta", "title", "date")]
        assert not bad, f"[ending].orbit_dissolve: Teile des Plakatsatzes qr | cta | title | date, nicht {bad}"
        assert e["orbit_close_at_beats"] + e["orbit_close_beats"] <= beats_left, \
            f"[ending] Finale: Abschluss endet nach dem Video ({beats_left:g} Beats nach dem Karussell-Ende)"
    e.update(orbit_at_beats=_beats_to(steps / per_beat, a), _orbit_derived=True)   # Bahnwechsel auf orbit_frame
    assert e["orbit_at_beats"] < beats_left, f"[ending]: Bahnwechsel nach {e['orbit_at_beats']:g} Beats, Video endet vorher"
    assert e["orbit_spin_speedup"] >= 1 and e["orbit_type_out_beats"] > 0 and e["orbit_cycle_beats"] >= 0, \
        "[ending]: orbit_spin_speedup >= 1, orbit_type_out_beats > 0, orbit_cycle_beats >= 0"
    lead = e["orbit_dive_lead_frames"] if path == "dive" else 0.0          # Bahnframes Vorlauf (Kamera taucht ein)
    assert lead < steps, "[ending].orbit_dive_lead_frames: Eintauchen muss nach dem Karussell-Ende liegen"
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


def _beats_to(x, a):
    """Beats, bis ein Loop, dessen Tempo pro Beat um a waechst, x Beats Weg im Anfangstempo zurueckgelegt hat
    (Umkehrung von _ramp in Beats: (a^u - 1) / ln a = x)."""
    return x if abs(a - 1) < 1e-12 else math.log(1 + x * math.log(a)) / math.log(a)


def orbit_phase(cfg, dt):
    """Bahnphase dt s nach dem Karussell-Ende. Vadim 1.10.: "den letzten Loop auch noch schneller": das Tempo legt pro
    Beat um orbit_loop_speedup zu (1 = T16 gleichmaessig), Start im Karusselltempo (stetig). Nach dem Bahnwechsel
    laeuft die Uhr weiter (Farben bis orbit_cycle_beats)."""
    phi0, per_s, b = orbit_clock(cfg)
    return _snap(phi0 + per_s * _ramp(dt, b, cfg["ending"]["orbit_loop_speedup"]))


def orbit_rate(cfg, dt):
    """Bahnframes pro Sekunde dt s nach dem Karussell-Ende (Ableitung von orbit_phase)."""
    _, per_s, b = orbit_clock(cfg)
    return per_s * cfg["ending"]["orbit_loop_speedup"] ** (dt / b)


def orbit_time(cfg, j):
    """Zeit s nach dem Karussell-Ende, zu der der digitale Loop j Bahnframes gelaufen ist."""
    _, per_s, b = orbit_clock(cfg)
    return _beats_to(j / per_s / b, cfg["ending"]["orbit_loop_speedup"]) * b


def orbit_release(cfg):
    """(Zeit s nach dem Karussell-Ende, Bahnphase) des Bahnwechsels. orbit_at_beats setzt check_orbit (orbit_loops)."""
    t = cfg["ending"]["orbit_at_beats"] * beat(cfg)
    return t, orbit_phase(cfg, t)


def orbit_px(cfg, phase):
    """Bahn bei gebrochener phase im 9:16-Bild: (x, y, R px, Drehung)."""
    import kickoff_loop as KL
    import kickoff_loop_video as V
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    ox, oy = V.digital_offset(cfg)
    x, y, r, rot = KL.orbit(cfg, phase % KL.count(cfg))
    return float(ox + x * pw), float(oy + y * ph), float(r * pw), rot


def orbit_kin(cfg, phase, per_s):
    """Zustand der Bahn im Bild bei phase: Lage (x, y, R px) und Tempo (vx, vy, vR in px/s bei per_s Bahnframes pro
    Sekunde), zentrale Differenz."""
    a, m, c = (orbit_px(cfg, phase + d)[:3] for d in (-TANGENT_H, 0.0, TANGENT_H))
    return m, tuple((cc - aa) / (2 * TANGENT_H) * per_s for aa, cc in zip(a, c))


def orbit_switch(cfg):
    """(Zeit s nach dem Karussell-Ende, Bahnphase), ab der der Stern die Ellipse verlaesst: throw beim Loslassen
    (orbit_frame), dive schon orbit_dive_lead_frames Bahnframes davor (die Kamera taucht im Anflug ein)."""
    e, n = cfg["ending"], cfg["loop"]["frames"]
    if e["orbit_path"] != "dive":
        return orbit_release(cfg)
    t = orbit_time(cfg, round(e["orbit_loops"] * n) - e["orbit_dive_lead_frames"])
    return t, orbit_phase(cfg, t)


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
      dive   (O7) die Kamera taucht schon im Anflug ein (orbit_dive_lead_frames Bahnframes vor orbit_frame): Wachstumsrate
             g = g0 k^(t/b) ab der Rate der Bahn (nie langsamer, kein Sprung), die Mitte faehrt in ihrer Richtung
             weiter und laeuft mit dem Zoom aus (Tempo v0 (R0 / R)^orbit_dive_drift_pow, keine Umkehr). orbit_dive_target
             [x, y]: statt auszulaufen faehrt die Mitte auf einer Hermite-Kurve dorthin (Bruchteil des Bildes), [] = frei.
             Ab orbit_frame (S33, Schnitt wie im Loop) Infinite Zoom (KD.zoom_spark), Puppen = ln-Zuwachs seitdem.
    Drehung ab dem Loslassen: Bahntempo, das in jedem Beat um (orbit_spin_speedup - 1) x zulegt.
    ghost: ist er weg, wo er waere (Grund V3 legt die Tasche um c.L["star"], sonst springt sie in die Ecke)."""
    import kickoff_loop as KL
    import kickoff_loop_digital as KD
    e, n, sp = cfg["ending"], KL.count(cfg), cfg["spark"]
    W, H = cfg["video"]["size_px"]
    cell = S.BASE["R"] * S.SIZES["9x16"][2]
    b = beat(cfg)
    t_r, phi_r = orbit_release(cfg)
    t_s, phi_s = orbit_switch(cfg)
    k = e["orbit_throw_speedup"]
    w0 = sp["spin_deg"] / n * orbit_rate(cfg, t_r)                           # Grad pro Sekunde auf der Bahn beim Wurf
    if dt <= t_r:
        rot = orbit_px(cfg, orbit_phase(cfg, dt))[3]
    else:
        tau = dt - t_r
        rot0 = orbit_px(cfg, phi_r + jump)[3]
        if e.get("orbit_spin_stop_beats"):                                 # O8 (Vadim 2.10.: "nicht drehen, langsamer
            rot = rot0 + spin_stop(w0, rot0, e["orbit_spin_stop_beats"] * b, e["orbit_spin_rest_deg"], tau)  # werden, gerade bleiben")
        else:
            rot = rot0 + w0 * (tau + 0.5 * (e["orbit_spin_speedup"] - 1) * tau * tau / b)
    if dt <= t_s:
        x, y, R, _ = orbit_px(cfg, orbit_phase(cfg, dt))
        return dict(star=(x, y, R, rot) if R > 0 else None, dolls=0.0, blur=0.0, loop=True)
    tau = dt - t_s
    (x0, y0, R0), (vx, vy, vR) = orbit_kin(cfg, phi_s + jump, orbit_rate(cfg, t_s))
    if e["orbit_path"] == "dive":
        rate, G = zoom_rate(cfg, vR / R0, t_s)
        tp = e.get("orbit_zoom_peak_beats", math.inf) * b - t_s
        def drift(t):                                                      # Weg der Mitte / v0
            s = np.linspace(0.0, t, THROW_SAMPLES)
            f = np.exp(-e["orbit_dive_drift_pow"] * G(s))
            return float(np.sum((f[1:] + f[:-1]) / 2 * np.diff(s)))
        x, y = x0 + vx * drift(tau), y0 + vy * drift(tau)
        if e["orbit_dive_target"]:                                         # Vadim 1.10.: "Spark mittig, leicht rechts,
            W, H = cfg["video"]["size_px"]                                 # als wuerde man reinfliegen"
            x, y = target_path(x0, y0, vx, vy, e["orbit_dive_target"][0] * W, e["orbit_dive_target"][1] * H,
                               e["orbit_dive_target_ease"], tau)
        dolls = max(G(tau) - G(t_r - t_s), 0.0) / math.log(1 / KD.DOLL_RATIO)
        blur = 2 * e["orbit_dive_shutter_frac"] * rate(tau) / math.log(1 / KD.DOLL_RATIO) / cfg["video"]["timeline_fps"]
        return dict(star=(x, y, R0 * math.exp(G(tau)), rot), dolls=dolls,
                    blur=blur if dt > t_r else 0.0, loop=dt <= t_r, rate=rate(tau), rate_hold=rate(min(tau, tp)))
    F = _ramp(tau, b, k)
    cx, cy, R = x0 + vx * F, y0 + vy * F, R0 + vR * F
    clear = KL.STAR_CLEAR * max(R, 0.0)
    out = cx + clear < 0 or cx - clear > W or cy + clear < 0 or cy - clear > H
    if R < cell or out:
        return dict(star=None, ghost=(cx, cy, max(R, 0.0) if out else GONE_R_PX, rot), dolls=0.0, blur=0.0, loop=False)
    return dict(star=(cx, cy, R, rot), dolls=0.0, blur=0.0, loop=False)


def target_path(x0, y0, vx, vy, tx, ty, p, tau):
    """Mitte faehrt von (Lage, Tempo) der Bahn ins Ziel und kommt dort weich zur Ruhe. Vadim 2.10. zu O9: "Mitte rechts ->
    Bildmitte zu sichtbar, kein Ease-out, sieht komisch aus": die alte kubische Hermite-Kurve liess das Tempo linear auf 0
    fallen, am Ziel bremste sie also mit voller Kraft und stand dann (Ruck). Jetzt Tempoprofil v0 (1 - u^p)^2: startet
    mit dem Tempo der Bahn ohne Ruck (Bremsung 0), kommt mit Tempo 0 UND Bremsung 0 an. Dauer T = Abstand / (kappa v0),
    kappa = mittleres Tempo / v0 = 1 - 2/(p+1) + 1/(2p+1): groesseres p haelt das Tempo laenger und bremst spaeter (kuerzer;
    p = 3: T = 1.56 x Abstand / Tempo, die Hermite-Kurve brauchte 2). Zeigt die Bahn nicht genau aufs Ziel, gleicht
    G(u) = u (1-u)^3 (1+3u) die Querrichtung aus (G'(0) = 1, G''(0) = 0: kein Ruck am Start; am Ende G = G' = G'' = 0)."""
    kappa = 1 - 2 / (p + 1) + 1 / (2 * p + 1)
    T = math.hypot(tx - x0, ty - y0) / (kappa * max(math.hypot(vx, vy), 1e-9))
    u = min(tau / T, 1.0) if T > 0 else 1.0
    F = (u - 2 * u ** (p + 1) / (p + 1) + u ** (2 * p + 1) / (2 * p + 1)) / kappa
    G = u * (1 - u) ** 3 * (1 + 3 * u)
    return (x0 + (tx - x0) * F + (T * vx - (tx - x0) / kappa) * G,
            y0 + (ty - y0) * F + (T * vy - (ty - y0) / kappa) * G)


def zoom_rate(cfg, g0, t_s):
    """dive: Zoomrate d ln R / dt und ihr Integral ln(R / R0), t s nach dem Eintauchen (beide fuer Skalare und Arrays).
    Startet bei g0 (Wachstum der Bahn), zieht x orbit_throw_speedup pro Beat an, hoechstens orbit_zoom_max_per_frame
    (ln-Massstab pro Videobild; O9, Vadim 2.10. zu O8: "Zoom langsamer, dann direkt unscharf": O8 stieg bis 40 S33-Puppen
    pro Bild), ab orbit_zoom_peak_beats faellt sie x orbit_zoom_decay pro Beat. Geschlossen, stueckweise."""
    e, b = cfg["ending"], beat(cfg)
    k, d_ = e["orbit_throw_speedup"], e.get("orbit_zoom_decay", 1.0)
    tp = e.get("orbit_zoom_peak_beats", math.inf) * b - t_s
    cap = math.log(e.get("orbit_zoom_max_per_frame", math.inf)) * cfg["video"]["timeline_fps"]
    tc = 0.0 if cap <= g0 else math.inf if k == 1 or cap == math.inf or g0 <= 0 else b * math.log(cap / g0) / math.log(k)
    r_tp = min(g0 * k ** (tp / b), cap) if tp < math.inf else 0.0         # Rate am Gipfel

    def rate(t):
        return np.minimum(g0 * k ** (np.minimum(t, tp) / b), cap) * d_ ** (np.maximum(t - tp, 0) / b)

    def G(t):
        a = np.minimum(np.minimum(t, tp), tc)
        out = g0 * _ramp(a, b, k) if tc > 0 else 0.0 * a
        if tc < tp:                                                        # gedeckelt: gleichmaessig
            out = out + cap * np.maximum(np.minimum(t, tp) - tc, 0)
        if tp < math.inf:
            out = out + r_tp * _ramp(np.maximum(t - tp, 0), b, d_)
        return out
    return (lambda t: float(rate(t)) if np.isscalar(t) else rate(t)), G


def spin_stop(w0, rot0, T0, rest, tau):
    """Drehung tau s nach dem Wurf, wenn sie auslaeuft: Tempo faellt linear von w0 (Grad/s, stetig zur Bahn) auf 0 und
    der Stern steht gerade (rest + Vielfache von STAR_SYM_DEG). Die Dauer T wird um T0 so gewaehlt, dass er genau dort
    zur Ruhe kommt (Weg = w0 T / 2, auf die naechste gerade Lage in Drehrichtung gerundet)."""
    if abs(w0) < 1e-9:
        return 0.0
    goal = rest + STAR_SYM_DEG * round((rot0 + w0 * T0 / 2 - rest) / STAR_SYM_DEG)
    d = goal - rot0
    if d * w0 <= 0:                                                        # nie rueckwaerts: naechste Lage voraus
        d += math.copysign(STAR_SYM_DEG, w0)
    T = 2 * d / w0
    u = min(tau, T)
    return w0 * (u - u * u / (2 * T))


def orbit_poster(cfg, dt):
    """Plakat (Index ueber alle Welten), dessen Farbe und Stern dt s nach dem Karussell-Ende gilt: laeuft im
    Karusselltempo weiter bis orbit_cycle_beats, dann steht es (Farbe der Endkarte)."""
    import kickoff_loop as KL
    return int(math.floor(orbit_phase(cfg, min(dt, cfg["ending"]["orbit_cycle_beats"] * beat(cfg))))) % KL.posters(cfg)


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
    elif "orbit_close_at_beats" in e:         # Finale: nach dem Abschluss liegt alles im Grund
        t_star = min(dt, (e["orbit_close_at_beats"] + e["orbit_close_beats"]) * b)
    os_ = orbit_star(cfg, t_star, jump)
    idx = orbit_poster(cfg, dt)
    st = KL.poster_style(cfg, idx)
    star = os_["star"]
    if not os_["loop"] and e["orbit_path"] == "dive":                      # Infinite Zoom in die Matrjoschka
        st.update(S=KL.S_CODES["S33"], spark_fn=KD.zoom_sparks if e.get("orbit_sparks") else KD.zoom_spark,
                  fx_behind_title="S33" in cfg["type"].get("effects_behind_title", []))
    if star is None:                          # weg: S2 (Labor-Stile messen am Stern, manche fuellen die Seite), unsichtbar
        star = os_.get("ghost") or (-3.0 * W, -3.0 * H, 1.0, 0.0)          # dort, wo er waere (Grund), sonst weit draussen
        st["S"], st["spark_fn"] = KL.S_CODES["S2"], K.spark
    tout = min(max((dt - e["orbit_type_out_at_beats"] * b) / (e["orbit_type_out_beats"] * b), 0.0), 1.0)
    morph = None
    if e["orbit_type_morph"]:                 # Vadim 1.10.: der Text verschwindet nicht und kommt neu, er loest sich auf
        tout = 0.0                            # und dithert an der Kartenstelle ein: jedes Element des Plakatsatzes kippt
        a = {p[0]: p[1] for p in (card or {}).get("parts", [])}           # in derselben Bayer-Reihenfolge weg, in der
        morph = {k: max(a.get(v, 0.0) for v in vs) for k, vs in MORPH.items()}   # sein Gegenstueck einsetzt
        morph = morph if any(morph.values()) else None
    flow = orbit_flow(cfg, dt)
    dg = dict(u=0.0, offset=(ox, oy), star=star, show=None)
    if not os_["loop"] or tout > 0 or card or flow:                        # sonst exakt das Plakat-Dict (bitgleich)
        dg.update(poster=idx, card=card, zoom=dict(dolls=round(os_["dolls"], 6), type_out=round(tout, 4), info=[],
                                                   info_in=0.0, core_shrink=e.get("orbit_dive_core_shrink", 0.0),
                                                   blur=round(os_.get("blur", 0.0), 4), flow=flow, morph=morph,
                                                   finale=finale(cfg, dt, os_)))
        if e.get("orbit_sparks"):                                          # O9: Matrjoschka aus allen Sternen
            col = cfg["color"]                                             # O10: Colorway + Drehung je Puppe
            dg["zoom"]["sparks"] = dict(codes=list(e["orbit_sparks"]), ratio=e["orbit_sparks_ratio"],
                                        spin=e["orbit_sparks_spin_deg"], dim=e["orbit_sparks_dim"],
                                        pals=[KL.station_hex(p, col["steps"], col["split_level"])
                                              for p in e["orbit_sparks_colors"]])
        st["type_fn"] = KD.zoom_card_type
    st["rot"] = star[3]                                                    # Labor-Sterne drehen nach st["rot"]
    st["loop"] = {**st["loop"], "digital": dg}
    st["star"] = (star[0] / W, star[1] / H, star[2] / W)
    return st


def _prog(dt, at, dur, b):
    """Fortschritt 0..1 einer Phase, die at Beats nach dem Karussell-Ende beginnt und dur Beats dauert."""
    return min(max((dt - at * b) / (dur * b), 0.0), 1.0)


def finale(cfg, dt, os_):
    """O8 (Vadim 2.10.): kein neuer Titel, keine Karte. Der Plakatsatz bleibt stehen, waehrend die Kamera in die
    Matrjoschka taucht:
      glow      Zoom-Gluehen am Titelblock: ln-Massstab, um den die Kamera in orbit_glow_frames Bildern waechst
                (gedeckelt bei orbit_glow_max_scale). Je staerker der Zoom, desto laenger der Schweif.
      dissolve  0..1, orbit_dissolve-Teile (QR) zerfallen nach vorn in Splitter
      words     Begriffe (finale_words), [] vor dem ersten
      close     0..1, Abschluss: alles ausser der Schrift kippt im Korn in den Grund (frueher card_dim_frac)
    Gluehen haelt ab O9 den erreichten Hoechstwert (Vadim: "soll nicht weggehen, wird langsamer"), bis zum Abschluss.
    None ohne Finale-Schluessel."""
    e, b = cfg["ending"], beat(cfg)
    if "orbit_close_at_beats" not in e:
        return None
    close = _prog(dt, e["orbit_close_at_beats"], e["orbit_close_beats"], b)
    span = os_.get("rate_hold", 0.0) / cfg["video"]["timeline_fps"] * e["orbit_glow_frames"]
    glow = min(span, math.log(e["orbit_glow_max_scale"])) * (1 - close) if not os_["loop"] else 0.0
    return dict(glow=round(glow, 4), close=round(close, 3), parts=list(e["orbit_dissolve"]),
                dissolve=round(_prog(dt, e["orbit_dissolve_at_beats"], e["orbit_dissolve_beats"], b), 3),
                scale=e["orbit_dissolve_scale"], effect=e["orbit_words_effect"], words=finale_words(cfg, dt, os_),
                fx={k.removeprefix("orbit_words_"): e[k] for k in WORD_EFFECTS[e["orbit_words_effect"]]})


def finale_words(cfg, dt, os_):
    """Begriffe im Finale (O9, Vadim 2.10.: "pro Beat ein Begriff"): je orbit_words_beats einer aus orbit_words, der
    letzte bleibt stehen. O10 (Vadim 2.10. zu O9): mittig im Bild statt an der QR-Stelle, Pixel-Effekt statt Kristall.
    Liste von dicts (lines, seed und je nach Effekt):
      sparkle/ripple  der aktuelle Begriff, mittig: grow = Zeit seit dem Einsatz in orbit_words_grow_beats (nicht
                      gedeckelt: frisch gesetzte Pixel leuchten noch nach), fade 0..1 = danach in die Tintenstufe
      zoom            (Vadim: "kommt aus der Tiefe, sitzt in seiner Puppe, waechst mit ihr, fliegt nach unten aus dem Bild,
                      der naechste folgt") jeder bisherige Begriff k haengt an der Puppe, die bei seinem Einsatz
                      orbit_words_zoom_from_px Radius hatte: Versalhoehe cap_frac x Puppenradius, Oberkante gap_frac x
                      Puppenradius unter der Mitte (waechst also nur nach unten, nie in SPARK), mittig ueber der Mitte;
                      weg, sobald die Oberkante unter dem Bild ist. Der letzte waechst in grow_beats aus der Bildmitte
                      auf die Satzgroesse (Ease-out) und bleibt."""
    e, b = cfg["ending"], beat(cfg)
    ws, x = e["orbit_words"], (dt / b - e["orbit_words_at_beats"]) / e["orbit_words_beats"]
    if x < 0:
        return []
    j = min(int(x), len(ws) - 1)
    local = (x - j) * e["orbit_words_beats"]                               # Beats seit Begriff j
    grow = local / e["orbit_words_grow_beats"]
    fb = e["orbit_words_fade_beats"]
    fade = 1.0 if fb == 0 else min(max(local - e["orbit_words_grow_beats"], 0) / fb, 1.0)
    cur = dict(lines=list(ws[j]), seed=j, grow=round(grow, 3), fade=round(fade, 3))
    if e["orbit_words_effect"] != "zoom":
        return [cur]
    H = cfg["video"]["size_px"][1]
    cx, cy, R, _ = orbit_star(cfg, dt)["star"]                             # nicht os_: der Stern steht nach dem Abschluss,
    # die Begriffe fliegen weiter aus dem Bild (sonst bleibt der letzte fliegende im Schlussbild haengen)
    lr = math.log(e["orbit_sparks_ratio"])
    out = []
    for k in range(min(j, len(ws) - 2) + 1):
        tk = (e["orbit_words_at_beats"] + k * e["orbit_words_beats"]) * b
        jd = math.ceil(math.log(e["orbit_words_zoom_from_px"] / orbit_star(cfg, tk)["star"][2]) / lr)
        r = R * e["orbit_sparks_ratio"] ** jd                              # Puppe des Begriffs jetzt
        top = cy + e["orbit_words_zoom_gap_frac"] * r
        if top < H:
            out.append(dict(lines=list(ws[k]), seed=k, cap=round(e["orbit_words_zoom_cap_frac"] * r, 2),
                            cx=round(cx, 2), top=round(top, 2)))
    if j == len(ws) - 1:
        out.append(dict(cur, grow=round(1 - (1 - min(grow, 1.0)) ** 3, 3), fade=1.0))
    return out


def orbit_flow(cfg, dt):
    """Laufender Verlauf in der Schrift (Vadim 1.10.: "die Gradients bewegen sich darunter, dass es lively wird",
    posterisiert): ab orbit_flow_at_beats laeuft der Zeilenverlauf mit orbit_flow_per_beat Zeilenhoehen pro Beat nach
    oben (KL.line_gradient, Dreieckswelle), seine Spannweite waechst in orbit_flow_in_beats von text_gradient_steps auf
    orbit_flow_steps Palettenstufen. (Phase mod 2, Stufen) oder None (steht)."""
    e, b = cfg["ending"], beat(cfg)
    if "orbit_flow_at_beats" not in e or dt <= e["orbit_flow_at_beats"] * b or not e["orbit_flow_per_beat"]:
        return None
    x = (dt - e["orbit_flow_at_beats"] * b) / b
    s0 = cfg["type"]["text_gradient_steps"]
    u = min(x / e["orbit_flow_in_beats"], 1.0)
    return [round(e["orbit_flow_per_beat"] * x % 2, 4), round(s0 + (e["orbit_flow_steps"] - s0) * u * u * (3 - 2 * u), 3)]


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
    Ellipse bis der Stern weg ist, die Karte alles deckt, der Zoom-Gipfel erreicht ist oder 2 Beats um sind. Schritt = (dx, dy px, d ln R, Drehung).
    dict(kink = Drehung der Mitte am Wechsel minus Drehung im Schritt davor (Grad; die Bahn kruemmt sich bei x1.6 bis
    20 Grad pro Bild, das ist kein Knick, ein Abknicken dagegen schon), jump/gjump = |v| bzw. |d ln R| im ersten ganzen
    Schritt danach / im letzten davor (Sprung im Tempo bzw. in der Zoomrate), , slow = Schritte danach, in denen eine Groesse kleiner wird bzw. |d ln R| nicht waechst (throw: |v| und |d ln R|; dive: d ln R und
    Sehfluss |v| + d ln R x rms-Bildradius; beide: Drehung), turn = Richtungsumkehren der Mitte (Skalarprodukt < 0), track = Schritte
    danach, gone_s = s nach dem Karussell-Ende, ab der der Stern weg ist (None: bleibt), on = Mitte am Ende im Bild).
    Am alten O4 (1.10.): |v| fiel 24 von 25 Schritten; alter O5: d ln R sprang x8.1, Sehfluss fiel 7x."""
    e = cfg["ending"]
    fps = cfg["video"]["timeline_fps"]
    W, H = cfg["video"]["size_px"]
    b = beat(cfg)
    t_s, _ = orbit_switch(cfg)
    k0 = math.floor(t_s * fps) + 1                                         # erstes Bild nach dem Verlassen
    end = min(t_s + 2 * b, e.get("orbit_zoom_peak_beats", math.inf) * b)  # nach dem Gipfel bremst der Zoom gewollt
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

    def turn(a, c):                                                        # vorzeichenbehaftete Drehung Grad a -> c
        return math.degrees(math.atan2(a[0] * c[1] - a[1] * c[0], a[0] * c[0] + a[1] * c[1]))
    kink = abs(turn(u, v) - turn(steps[j - 2], u))                         # Drehung am Wechsel minus Drehung davor
    after = steps[j:]
    sizes = [math.hypot(*x[:2]) for x in after]
    rates = [abs(x[2]) for x in after]
    spins = [x[3] for x in after]
    r_rms = math.sqrt((W * W + H * H) / 12)                                # mittlerer Abstand der Bildpunkte zur Mitte (rms)
    flow = [sz + r * r_rms for sz, r in zip(sizes, rates)]

    def falls(xs):
        return sum(1 for a, c in zip(xs, xs[1:]) if c < a * (1 - SLOW_EPS))

    def flat(xs):                                                          # Zoom/Schrumpfen muss echt anziehen (ein
        return sum(1 for a, c in zip(xs, xs[1:]) if c <= a * (1 + SLOW_EPS))   # Zoom aus dem Stand bleibt sonst bei 0)
    spin_slow = 0 if e.get("orbit_spin_stop_beats") else falls(spins)     # Finale: Drehung laeuft gewollt aus
    cap = math.log(e.get("orbit_zoom_max_per_frame", math.inf))           # O9: am Deckel halten ist kein Bremsen
    if cap < math.inf:                        # O9: Fluss nie unter dem am Wechsel (die Mitte landet, der Zoom haelt sein Tempo)
        fslow = sum(1 for f in flow if f < flow[0] * (1 - SLOW_EPS))
    else:
        fslow = falls(flow) if e["orbit_path"] == "dive" else falls(sizes)
    slow = flat([r for r in rates if r < cap * (1 - SLOW_EPS)]) + spin_slow + fslow
    turn = sum(1 for a, c in zip(after, after[1:])
               if math.hypot(*a[:2]) > MOVE_PX and math.hypot(*c[:2]) > MOVE_PX and a[0] * c[0] + a[1] * c[1] < 0)
    x, y = seq[-1][:2]
    w = steps[j + 1]                                                       # erster ganzer Schritt danach (steps[j] ist
    nw = math.hypot(*w[:2])                                                # halb Loop, halb neue Bahn: verdeckt Spruenge)
    return dict(kink=kink, jump=nw / max(nu, 1e-12), gjump=abs(w[2]) / max(abs(u[2]), 1e-12), slow=slow, turn=turn,
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
    zoom = (f"Matrjoschka aus {len(e['orbit_sparks'])} Sternen (je x{e['orbit_sparks_ratio']:g})"
            if e.get("orbit_sparks") else f"Infinite Zoom, Verschluss {e['orbit_dive_shutter_frac']:g}")
    cap = (f", hoechstens x{e['orbit_zoom_max_per_frame']:g} pro Bild" if "orbit_zoom_max_per_frame" in e else "")
    what = (f"Kamera taucht ab F{phi_s % n + 1:.2f} bei {at + t_s:.2f} s ein (Zoomrate = Wachstum der Bahn, x"
            f"{e['orbit_throw_speedup']:g} pro Beat{cap}), Mitte laeuft mit dem Zoom aus, {zoom} ab F{phi_r % n + 1:.0f} "
            f"bei {at + t_r:.2f} s"
            if e["orbit_path"] == "dive" else
            f"Wurf in die Tiefe ab F{phi_r % n + 1:.0f} bei {at + t_r:.2f} s (gerade Linie zum Fluchtpunkt, Bildtempo x"
            f"{e['orbit_throw_speedup']:g} pro Beat)")
    return [f"Ende Bahn: digitaler Loop ab F{phi0 % n + 1} auf dem Karussell-Ende {at:.2f} s "
            f"({(phi_r - phi0) / n:.2f} Umlaeufe, Tempo x{e['orbit_loop_speedup']:g} pro Beat, 24 fps), dann {what}, Drehung x{e['orbit_spin_speedup']:g} pro Beat. "
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
                diff=bool(e["card_diff"]), flow=orbit_flow(cfg, dt) if cfg["endcard"].get("end_mode") == "orbit" else None)


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
    Tintenstufe. Kein Kippen je Zeile wie auf dem Plakat (flip_word): im Zoom zaehlen die abgedimmten Schalen
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
            if cs.get("flow"):                                             # Verlauf laeuft wie im Plakatsatz (orbit_flow)
                ys = np.nonzero(base[name].any(1))[0]
                rel = np.clip((ys.max() - np.arange(c.gh)) / max(ys.max() - ys.min(), 1), 0, 1)[:, None]
                rel = 1 - np.abs((rel - cs["flow"][0]) % 2 - 1)
                ink = np.broadcast_to(np.round((1 - cs["flow"][1] / c.N * (1 - rel)) * c.N) / c.N,
                                      (c.gh, c.gw)).astype(np.float32)
            c.add(name, m, KL.title_value(c, ink) if cs["diff"] else ink)   # diff: wie SPARK auf dem Plakat, Effekte
                                                                            # laufen invertiert durch (Difference-Ebene)


def _fly(c, mask, val, u, scale, centre):
    """Splitter fliegen nach vorn (Vadim 2.10.: "der QR-Code loest sich nach vorne auf, in Pixeln"): je QR-Modul ein
    Splitter mit eigener Tiefe (FRAG_DEPTH) und Verzoegerung (FRAG_DELAY). Er waechst perspektivisch um centre (die
    Zoom-Mitte, wie alles beim Eintauchen) bis scale^Tiefe und kippt dabei im Bayer-Korn weg. Nahe Splitter malen
    zuletzt. Zellraster, ganze Zellen."""
    import kickoff_loop as KL
    B = KL.MODULE_CELLS
    ys, xs = np.nonzero(mask)
    rng = np.random.default_rng(FRAG_SEED)
    nb = (c.gh // B + 1, c.gw // B + 1)
    depth, delay = rng.uniform(*FRAG_DEPTH, nb), rng.uniform(0, FRAG_DELAY, nb)
    w = np.clip((u - delay[ys // B, xs // B]) / (1 - FRAG_DELAY), 0, 1)
    keep = bayer(c)[ys, xs] >= w
    ys, xs, w = ys[keep], xs[keep], w[keep]
    s = scale ** (w * depth[ys // B, xs // B])
    out_m, out_v = np.zeros((c.gh, c.gw), bool), np.zeros((c.gh, c.gw), np.float32)
    cy, cx = centre
    for j in np.argsort(s, kind="stable"):
        y0, x0 = cy + (ys[j] - cy) * s[j], cx + (xs[j] - cx) * s[j]
        y1, x1 = int(round(y0 + s[j])), int(round(x0 + s[j]))
        y0, x0 = max(int(round(y0)), 0), max(int(round(x0)), 0)
        if y1 > y0 and x1 > x0:
            out_m[y0:y1, x0:x1] = True
            out_v[y0:y1, x0:x1] = val[ys[j], xs[j]]
    return out_m, out_v


def word_mask(c, lines, cap, lead, cx, top):
    """Maske + Verlauf eines Begriffs: jede Zeile waagerecht mittig auf cx (Breite aus dem Vektorfont, dann an der
    gerasterten Tinte nachgemessen; kein np.roll, das bei Zeilen breiter als das Bild umbricht), erste Oberkante bei top,
    Verlauf wie KICK-OFF/Datum (KL.line_gradient)."""
    import kickoff_loop as KL
    mk = np.zeros((c.gh, c.gw), bool)
    v = np.zeros((c.gh, c.gw), np.float32)
    steps = c.st["loop"]["type"]["text_gradient_steps"]
    for j, line in enumerate(lines):
        base = round((top + cap + j * lead) / c.px) * c.px
        x = cx - S.width_per_cap(line) * cap / 2
        m = S.line_mask(line, "clash", cap, base, x, c.px, (c.gh, c.gw))
        xs = np.nonzero(m.any(0))[0]
        if len(xs) and xs[0] > 0 and xs[-1] < c.gw - 1:                    # Breite gerastert (Schriftgrad gerundet, Tinte
            dx = cx - (xs[0] + xs[-1] + 1) / 2 * c.px                      # eine Zelle versetzt: bis 5 Zellen daneben):
            m = S.line_mask(line, "clash", cap, base, x + dx, c.px, (c.gh, c.gw))   # gemessen nachsetzen
        v = np.where(m, KL.line_gradient(c, base, cap, steps), v)
        mk |= m
    return mk, v


def word_layer(c, w, effect, fx, hi):
    """Ein Begriff (finale_words) aufs Bild. Mittig (sparkle, ripple, letzter bei zoom): Groesse und Zeilenabstand wie
    KICK-OFF/Datum, Block waagerecht und senkrecht auf der Bildmitte. Endwert = Tinte, kippt als Ganzes hell/dunkel
    (KL.flip_word wie JOIN US); davor als Difference wie SPARK (KL.title_value), fade blendet hinueber.
      sparkle  (a, Vadim 2.10.: "zufaellige Pixel im Wort leuchten einzeln nacheinander auf", Referenz pack/gif sparkle)
               jede Zelle hat einen festen Zufallszeitpunkt in der Wachstumszeit, leuchtet dann orbit_words_flash_frac
               davon in der hellsten Stufe und faellt auf ihren Wert
      ripple   (b, "Funken im Feld um das Wort, aussen verloeschen sie, im Wort bleiben sie", Referenz pack/gif ripple)
               Ring + Nachlaeufer laufen von der Wortmitte nach aussen (Abstand in halben Wortbreiten, Front ~ t^0.8 bis
               orbit_words_ring_reach); wo der Ring ist, zuenden Funken (fester Zufall je Zelle unter der Ringstaerke),
               ausserhalb verloeschen sie hinter ihm, im Wort bleibt jede Zelle, die die Front ueberstrichen hat
      zoom     ohne Effekt: der Begriff steht in seiner Puppe (cap, cx, top aus finale_words) bzw. waechst (letzter)."""
    import kickoff_loop as KL
    L = c.L
    cap = L["capd"]
    lead = L["sb"][1] - L["sb"][0] if len(L["sb"]) > 1 else 1.4 * cap
    g = w.get("grow", 1.0)
    if "cap" in w:                                                         # zoom: haengt an seiner Puppe
        if w["cap"] < WORD_MIN_CAP_CELLS * c.px:
            return
        cap, lead, cx, top = w["cap"], w["cap"] * lead / cap, w["cx"], w["top"]
    else:
        if effect == "zoom":                                               # letzter: waechst aus der Bildmitte
            if g * cap < WORD_MIN_CAP_CELLS * c.px:
                return
            cap, lead, g = g * cap, g * lead, 1.0
        cx, top = c.W / 2, c.H / 2 - (cap + (len(w["lines"]) - 1) * lead) / 2
    mk, v = word_mask(c, w["lines"], cap, lead, cx, top)
    if not mk.any():
        return
    K._EXTRA["new"] = mk
    K._EXTRA["ripple_on"] = np.zeros_like(mk)
    ink = KL.flip_word(c, mk, v)
    keep = getattr(c, "title_target", None), getattr(c, "title_fx", None)
    diff = KL.title_value(c, v)                                            # Negativ des Untergrunds wie SPARK
    c.title_target, c.title_fx = keep                                      # (Selbsttest Titel misst SPARK)
    body = diff + (ink - diff) * w.get("fade", 1.0)
    if effect == "zoom" or g >= 1 + fx.get("flash_frac", 0):             # fertig: nur noch der Wert
        c.add("new", mk, ink if effect == "zoom" else body)
        K._EXTRA["new_on"] = mk
        return
    rng = np.random.default_rng(WORD_SEED + w["seed"])
    noise = rng.random((c.gh, c.gw))
    if effect == "sparkle":
        age = (g - noise) / fx["flash_frac"]                                  # 0..1 = leuchtet gerade auf
        on = mk & (age >= 0)
        c.add("new", on, np.where(age < 1, hi, body))
        K._EXTRA["new_on"] = on
        return
    ys, xs = np.nonzero(mk)                                                # ripple
    my, mx = (ys.min() + ys.max() + 1) / 2, (xs.min() + xs.max() + 1) / 2
    r = np.hypot(c.yy + 0.5 - my, c.xx + 0.5 - mx) / max((xs.max() - xs.min() + 1) / 2, 1)
    u = min(g, 1.0)
    front, wd = fx["ring_reach"] * u ** RIPPLE_POW, fx["ring_width"]
    ring = sum(a * np.exp(-((r - (front - RIPPLE_SPACING * wd * k)) / wd) ** 2) for k, a in RIPPLE_ECHOES)
    ring = np.clip(ring, 0, 1) * (1 - u * u)                               # Ring verebbt bis zum Ende der Wachstumszeit
    spark = noise < ring
    inside = mk & (r <= front)
    c.add("new", inside, np.where(spark, hi, body))
    K._EXTRA["new_on"] = inside
    out = spark & ~mk
    for name, _, lv, _, _ in c.layers:                                     # Funken nie ueber Schrift
        if name in ("title", "date", "new"):
            out &= np.isnan(lv)
    c.add("ripple", out, hi)
    K._EXTRA["ripple_on"] = out


def finale_layers(c, f, n0):
    """Finale (orbit_state -> finale) auf den Plakatsatz ab Ebene n0: Teile in f["parts"] zerfallen nach vorn
    (_fly), die Begriffe setzen ein (word_layer), dann das
    Zoom-Gluehen: die Schrift von SPARK und KICK-OFF/Datum, GLOW_SAMPLES-mal um die Zoom-Mitte vergroessert bis
    exp(f["glow"]), Gewicht faellt nach aussen, in der hellsten Stufe ueber den Untergrund (wie qr_glow), nie ueber
    Schrift."""
    import kickoff_loop as KL
    L, px = c.L, c.px
    centre = (L["star"][1] / px - 0.5, L["star"][0] / px - 0.5)
    lum = c.pal @ KL.LUMA
    hi = c.lvl(int(lum.argmax()))
    if f["dissolve"] > 0:
        out = [ly for ly in c.layers[n0:] if ly[0] in f["parts"]]
        c.layers[n0:] = [ly for ly in c.layers[n0:] if ly[0] not in f["parts"]]
        if out and f["dissolve"] < 1:
            v = np.full((c.gh, c.gw), np.nan, np.float32)
            for ly in out:
                v = np.where(np.isnan(ly[2]), v, ly[2])
            m, val = _fly(c, ~np.isnan(v), v, f["dissolve"], f["scale"], centre)
            c.add("qr", m, val)
    for w in f["words"]:
        word_layer(c, w, f["effect"], f["fx"], hi)
    if f["glow"] > 0:
        text = np.zeros((c.gh, c.gw), bool)
        for name, _, lv, _, _ in c.layers[n0:]:
            if name in ("title", "date"):
                text |= ~np.isnan(lv)
        anytype = np.zeros_like(text)
        for _, _, lv, _, _ in c.layers[n0:]:
            anytype |= ~np.isnan(lv)
        g = np.zeros((c.gh, c.gw), np.float32)
        for j in range(1, GLOW_SAMPLES + 1):
            sc = math.exp(f["glow"] * j / GLOW_SAMPLES)
            sy = np.round(centre[0] + (c.yy - centre[0]) / sc).astype(int)
            sx = np.round(centre[1] + (c.xx - centre[1]) / sc).astype(int)
            ok = (sy >= 0) & (sy < c.gh) & (sx >= 0) & (sx < c.gw)
            hit = np.zeros_like(text)
            hit[ok] = text[sy[ok], sx[ok]]
            g = np.maximum(g, hit * (1 - j / (GLOW_SAMPLES + 1)))
        u = KL.under(c)
        c.add("glow", (g > GLOW_MIN) & ~anytype, u + (hi - u) * g)


def finale_check(st, img):
    """Befund am letzten Bild des Finales: (QR noch lesbar?, Lesbarkeit SPARK und KICK-OFF/Datum + neue Zeilen, Anteil
    reines Schwarz #000 ausserhalb der Schrift, eine Zelle Rand). Die
    Masken setzt das Rendern (K._EXTRA), deshalb wird das letzte Bild hier einmal im Prozess gerendert."""
    S.render(st, "9x16", layers=False)
    K._EXTRA["date"] = K._EXTRA["date"] | K._EXTRA.get("new", False)
    px = S.BASE["R"] * S.SIZES["9x16"][2]
    text = S.up(binary_dilation(K._EXTRA["title"] | K._EXTRA["date"], iterations=1), px)[:img.shape[0], :img.shape[1]]
    black = float((img[~text] == 0).all(-1).mean())                       # O10: Endbild blankes Schwarz ausser Schrift
    return K.check_qr(img, px), K.legible(img, px), black


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
    js = [j for j in (0, 5, 11) if orbit_time(cfg, j) < t_s]
    same = [np.array_equal(img(orbit_state(cfg, orbit_time(cfg, j))), img(poster_digital(cfg, phi0 + j))) for j in js]
    bites = not np.array_equal(img(orbit_state(cfg, orbit_time(cfg, js[-1] + 0.5))), img(poster_digital(cfg, phi0 + js[-1])))
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
    off = max(1.0, 2 * orbit_rate(cfg, t_s) / fps)                         # 2 Videobilder Bahnweg (Loop x1.6: 1.3/Bild)
    good, bad = probe(0.0), probe(off)
    lines.append(f"Bahn stetig am Bild (Sternflaeche S2): Schritt beim Wechsel x{good:.2f} des groesseren Nachbarn "
                 f"(Grenze x{RELEASE_JUMP}): {'ok' if good <= RELEASE_JUMP else 'FEHLER'}; Gegenprobe {off:.1f} Bahnframes versetzt "
                 f"x{bad:.2f}: {'schlaegt an' if bad > RELEASE_JUMP else 'TEST BLIND'}")
    ok &= good <= RELEASE_JUMP < bad

    m = orbit_measure(cfg)
    probe_cfg = copy.deepcopy(cfg)                                         # ohne check_orbit: bewusst falsche Werte
    if cfg["ending"]["orbit_path"] == "dive":
        probe_cfg["ending"]["orbit_dive_lead_frames"] = 0
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

    if cfg["ending"].get("orbit_sparks"):
        good, more = sparks_rate_check(cfg)
        lines += more
        ok &= good
    elif cfg["ending"]["orbit_path"] == "dive":
        good, more = zoom_rate_check(cfg)
        lines += more
        ok &= good

    def loops(c):                                                          # Bahnframes vom Karussell-Ende bis zum Wurf
        return (orbit_release(c)[1] - orbit_clock(c)[0]) / n
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


def sparks_rate_check(cfg):
    """O9, Matrjoschka aus Sternen: hoechstens SPARKS_PER_FRAME neue Puppen pro Videobild (sonst steht kein Stern lang
    genug, um ihn zu sehen, und es wird "direkt unscharf" wie O8). Gemessen an der Bahn bis zum Gipfel (danach faellt
    die Rate).
    Gegenprobe: dieselbe Variante ohne orbit_zoom_max_per_frame (Zoom wie O8) schlaegt an."""
    import copy
    fps, b = cfg["video"]["timeline_fps"], beat(cfg)
    t_s, _ = orbit_switch(cfg)

    def most(c):
        e = c["ending"]
        end = min(e["orbit_close_at_beats"], e["orbit_zoom_peak_beats"]) * b                # schnellste Stelle: der Gipfel
        R = [orbit_star(c, k / fps)["star"][2] for k in range(math.floor(t_s * fps), math.floor(end * fps) + 2)]
        return max(np.diff(np.log(R))) / math.log(1 / e["orbit_sparks_ratio"])
    old = copy.deepcopy(cfg)
    old["ending"].pop("orbit_zoom_max_per_frame", None)
    got, bad = most(cfg), most(old)
    good = got <= SPARKS_PER_FRAME
    return good and bad > SPARKS_PER_FRAME, [
        f"Sterne pro Bild (Matrjoschka): hoechstens {got:.2f} (Grenze {SPARKS_PER_FRAME}): {'ok' if good else 'FEHLER'}; "
        f"Gegenprobe ohne Deckel {bad:.3g}: {'schlaegt an' if bad > SPARKS_PER_FRAME else 'TEST BLIND'}"]


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
        if cfg["ending"].get("orbit_spin_stop_beats"):
            sp, line = spin_selftest(cfg)
            lines.append(line)
            good &= sp
        if "orbit_words" in cfg["ending"]:
            wd, line = words_selftest(cfg)
            lines.append(line)
            good &= wd
    return ok and good, lines


def words_selftest(cfg):
    """Begriffe (O10). sparkle/ripple am fertigen Bild, erster Begriff ueber seine Wachstumszeit: die gesetzten Zellen
    (K._EXTRA["new_on"]) wachsen monoton (einmal gesetzt, bleibt gesetzt), am Ende ist es der ganze Begriff, und er
    steht mittig (Mitte der Maske hoechstens 1 Zelle neben der Bildmitte). Gegenprobe: neuer Zufall je Bild (Pixel
    flackern statt nacheinander aufzuleuchten) ist nicht monoton; ripple: die Funken ausserhalb (verloeschen hinter dem
    Ring) sind nicht monoton, und im fertigen Bild steht keiner mehr.
    zoom, je Videobild: jeder fliegende Begriff waechst nur, seine Oberkante liegt nie ueber der Sternmitte (er fliegt
    nach unten, nie in SPARK), und vor dem Videoende ist er aus dem Bild. Gegenprobe: Begriff mittig auf der Puppe
    (gap_frac = -cap_frac/2) waechst nach oben."""
    import copy
    e, b = cfg["ending"], beat(cfg)
    W, H = cfg["video"]["size_px"]
    end = cfg["ending"]["length_bars"] * 4 - cfg["ending"]["carousel_bars"] * 4    # Beats nach dem Karussell-Ende
    if e["orbit_words_effect"] == "zoom":
        def probe(c):
            last, ok = {}, True
            for k in range(int(e["orbit_words_at_beats"] * b * 24), int(end * b * 24)):
                dt = k / 24
                cy = orbit_star(c, dt)["star"][1]
                for w in finale_words(c, dt, None):
                    if "cap" in w:
                        ok &= w["top"] >= cy - 1e-6 and w["cap"] >= last.get(w["seed"], 0)
                        last[w["seed"]] = w["cap"]
            gone = all(w.get("cap") is None for w in finale_words(c, end * b - 1e-3, None))
            return ok and gone, gone
        ok, gone = probe(cfg)
        bad = copy.deepcopy(cfg)
        bad["ending"]["orbit_words_zoom_gap_frac"] = -bad["ending"]["orbit_words_zoom_cap_frac"] / 2
        bites = not probe(bad)[0]
        return ok and bites, (f"Begriffe zoomen mit: wachsen nur, nie ueber der Sternmitte, am Ende {'raus' if gone else 'NOCH IM BILD'}: "
                              f"{'ok' if ok else 'FEHLER'}; Gegenprobe mittig auf der Puppe: {'schlaegt an' if bites else 'TEST BLIND'}")
    t0 = e["orbit_words_at_beats"] * b
    gb = e["orbit_words_grow_beats"] * b
    ts = [t0 + gb * u for u in (0.2, 0.4, 0.6, 0.8, 1 + e.get("orbit_words_flash_frac", 0) + 0.05)]

    ripple = e["orbit_words_effect"] == "ripple"

    def probe(reseed):
        sets, field = [], []
        for k, t in enumerate(ts):
            st = orbit_state(cfg, t)
            if reseed:
                for w in st["loop"]["digital"]["zoom"]["finale"]["words"]:
                    w["seed"] += 17 * (k + 1)
            S.render(st, "9x16", layers=False)
            sets.append(K._EXTRA["new_on"].copy())
            field.append(K._EXTRA["ripple_on"].copy())
        return (field if ripple and reseed else sets), K._EXTRA["new"], field
    sets, full, field = probe(False)
    mono = all((a <= b_).all() for a, b_ in zip(sets, sets[1:]))
    whole = (sets[-1] == full).all()
    ys, xs = np.nonzero(full)
    gh, gw = full.shape
    off = max(abs((ys.min() + ys.max() + 1) / 2 - gh / 2), abs((xs.min() + xs.max() + 1) / 2 - gw / 2))
    ok = mono and whole and off <= 1 and not field[-1].any()
    bad = probe(True)[0]
    bites = not all((a <= b_).all() for a, b_ in zip(bad, bad[1:]))
    return ok and bites, (f"Begriffe ({e['orbit_words_effect']}): monoton {'ja' if mono else 'NEIN'}, am Ende ganzer Begriff "
                          f"{'ja' if whole else 'NEIN'}, Mitte {off:.1f} Zellen neben der Bildmitte, Funken am Ende {int(field[-1].sum())}: "
                          f"{'ok' if ok else 'FEHLER'}; Gegenprobe "
                          f"{'Funken ausserhalb' if ripple else 'neuer Zufall je Bild'}: {'schlaegt an' if bites else 'TEST BLIND'}")


def spin_selftest(cfg):
    """Finale: die Drehung laeuft aus und steht gerade (Vadim 2.10.). Am Stern je Videobild ab dem Wurf: Tempo stetig
    am Wurf (x0.67..1.5 des letzten Bahnschritts), nie rueckwaerts, faellt nur, am Ende 0 und Lage = rest + n x 60.
    Gegenprobe: die alte Drehung (orbit_spin_speedup, ohne Auslauf) steht am Ende nicht."""
    fps, b = cfg["video"]["timeline_fps"], beat(cfg)
    t_r, _ = orbit_release(cfg)
    end = (cfg["ending"]["orbit_close_at_beats"]) * b

    def probe(c):
        k0 = math.floor(t_r * fps)
        rot = [orbit_star(c, k / fps)["star"][3] for k in range(k0 - 1, math.floor(end * fps))]
        d = (np.diff(rot) + STAR_SYM_DEG / 2) % STAR_SYM_DEG - STAR_SYM_DEG / 2   # 6 Zacken: +-240 Grad am Wurf = gleiche Lage
        rest = (rot[-1] - c["ending"].get("orbit_spin_rest_deg", 0.0) + 30) % STAR_SYM_DEG - 30
        cont = abs(d[1]) / max(abs(d[0]), 1e-9)
        ok = 1 / RELEASE_JUMP <= cont <= RELEASE_JUMP and (d[1:] * np.sign(d[0]) >= -1e-9).all() \
            and (np.abs(d[2:]) <= np.abs(d[1:-1]) + 1e-9).all() and abs(d[-1]) < 1e-6 and abs(rest) < 1e-6
        return ok, cont, rest, d[-1]
    ok, cont, rest, last = probe(cfg)
    old = json.loads(json.dumps(cfg))
    del old["ending"]["orbit_spin_stop_beats"]
    bites = not probe(old)[0]
    return ok and bites, (f"Drehung laeuft aus (Finale): Tempo am Wurf x{cont:.2f}, am Ende {last:.4f} Grad/Bild, Lage "
                          f"{rest:+.4f} Grad neben gerade: {'ok' if ok else 'FEHLER'}; Gegenprobe alte Drehung: "
                          f"{'schlaegt an' if bites else 'TEST BLIND'}")


if __name__ == "__main__":
    import kickoff_loop as KL
    if len(sys.argv) < 3 or sys.argv[1] != "test":
        sys.exit(__doc__)
    ok, lines = selftest(KL.load(sys.argv[2]))
    print("\n".join(lines))
    sys.exit(0 if ok else 1)
