#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""Stern-Bahn-Editor in DaVinci Resolve: Vadim keyt den Flug des Sterns im Fusion-Tab, Python liest ihn zurueck.

Warum: Die Bahn ist Animation, und die animiert Vadim am liebsten selbst, mit Keyframes, in Resolve. Resolve zeigt dafuer
nur eine Hilfe (Plakat ohne Stern, weisser Stern, Satz halbtransparent darueber). Die echten Plakate (Palette, Dither,
Satz, QR) rendert weiter Python, aus der Bahn, die `pull` aus Resolve holt: je Frame (x, y, r, rot) wie `KL.orbit`.

  uv run src/kickoff_loop_resolve.py assets   Hilfsbilder → kickoff_loop/resolve/editor/ (layout, type_overlay, star)
  uv run src/kickoff_loop_resolve.py push     Projekt + Timeline "Stern-Bahn" bauen, Startbahn = KL.orbit
                                    push --force  bestehende Timeline auf KL.orbit zuruecksetzen (Vadims Keys weg!)
  uv run src/kickoff_loop_resolve.py pull     Bahn je Frame aus Resolve → kickoff_loop/star_path.json
  uv run src/kickoff_loop_resolve.py check    Selbsttest: push + pull auf einer Wegwerf-Timeline, Vergleich mit KL.orbit
  uv run src/kickoff_loop_resolve.py verify [F ...]   Frames der Stern-Bahn aus Resolve rendern, Silhouette gegen Python (IoU)

Konventionen (Befund 30.9. mit Resolve 21.1, `verify`):
  unsere Bahn   x, y = Bruchteil von Plakatbreite/-hoehe, y nach unten; r = Spitzenradius / Plakatbreite;
                rot = Grad im Uhrzeigersinn (Bildkoordinaten, wie styles.star_r)
  Fusion Merge  Center = 0..1 je Achse, y nach OBEN; Angle = Grad GEGEN den Uhrzeigersinn;
                Size = Massstab des Vordergrunds in seinen eigenen Pixeln → r = Size * star_png_radius_px / Plakatbreite
Zeit: Timeline-Frame k (ab Clipanfang) = Comp-Zeit RenderStart + k = Plakat-Frame k + 1.

Resolve-Zugriff: externes Python (uv) mit DaVinciResolveScript, Einstellung Preferences > System > General >
External scripting = Local. Details und die geprueften API-Punkte: kickoff_loop/resolve/STERN_BAHN.md.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kickoff as K                      # noqa: E402
import kickoff_loop as KL                # noqa: E402
import styles as S                       # noqa: E402

OUT = os.path.join(KL.PROJECT, "resolve", "editor")
ASSETS = {k: os.path.join(OUT, f"{k}.png") for k in ("layout", "type_overlay", "star")}

# Vorschlag fuer loop.toml [resolve]. Steht der Abschnitt dort, gilt er (Schluessel fuer Schluessel); bis dahin diese Werte.
RESOLVE_DEFAULT = dict(
    project="SPARK_Kickoff_Loop",   # Resolve-Projekt (neu, nur fuer den Editor)
    timeline="Stern-Bahn",          # Timeline mit dem Editor-Clip; check baut daneben "<timeline> Test" und loescht sie
    fps=24,                         # Wiedergabe im Editor. 1 Timeline-Frame = 1 Plakat-Frame, die fps sind nur Vorschau
    key_every=4,                    # Startkeyframes aus KL.orbit alle n Frames (weiche Kurven, gut zu bearbeiten).
                                    # Haelt die Kurve die Toleranzen nicht, nimmt push automatisch 2, dann 1
    star_png_radius_px=1024,        # Spitzenradius in star.png. Groesser = schaerfer bei grossen Sternen, Size kleiner
    overlay_alpha_frac=0.6,         # Deckkraft der Satz-Hilfe (Titel, Datum, JOIN US, QR mit Hof) ueber dem Stern
    path_file="star_path.json",     # Ausgabe von pull, relativ zu kickoff_loop/
    tol_pos_frac=0.005,             # check: Lage, Abweichung als Bruchteil der Plakatbreite (x und y)
    tol_size_frac=0.01,             # check: Groesse, relativ
    tol_rot_deg=1.0,                # check: Drehung
    iou_min=0.95,                   # verify: Silhouette aus Resolve vs. Python, Schnitt/Vereinigung
)

# Technische Konstanten
RESOLVE_MODULES = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"  # README 21.1
OFF_CANVAS_STAR = (-10.0, -10.0, 0.01)   # Stern (x, y, r) weit ausserhalb: Plakat ohne Stern und ohne sein Glimmen
                                         # (styles.background: Glimmen faellt mit exp(-Abstand / R) ab, hier ~ e^-1000)
PLAIN_SPARK = "S2"                       # Stil fuer layout.png: zeichnet nur in der Silhouette (Labor-Sterne wie S19d
                                         # brauchen den Stern im Bild und brechen ab, wenn er draussen liegt)
DERIV_STEP = 1e-3                        # Frames, zentrale Differenz fuer die Steigung von KL.orbit an den Keyframes
STAR_PAD_PX = 8                          # Rand um den Stern in star.png (Antialiasing + Filter des Merge)
DIFF_MIN = 0.06                          # verify: Pixel gilt als "Stern", wenn Resolve so weit vom Plakat ohne Stern
                                         # abweicht (0..1 je Kanal). Der Stern ist weiss, der Grund dunkel: weit darueber
AMBIG_LUMA = 0.8                         # verify: wo das Plakat ohne Stern schon so hell ist, ist Weiss nicht erkennbar;
                                         # diese Pixel zaehlen in keiner der beiden Silhouetten (Anteil steht im Bericht)


def load():
    """loop.toml + [resolve] (oder RESOLVE_DEFAULT) lesen und pruefen, bevor Resolve angefasst wird."""
    cfg = KL.load()
    rc = dict(RESOLVE_DEFAULT, **cfg.get("resolve", {}))
    bad = sorted(set(rc) - set(RESOLVE_DEFAULT))
    assert not bad, f"[resolve]: unbekannte Schluessel {bad}. Erlaubt: {sorted(RESOLVE_DEFAULT)}"
    assert int(rc["key_every"]) >= 1, "[resolve].key_every: mindestens 1 (Keyframe alle n Frames)"
    assert rc["star_png_radius_px"] >= 64, "[resolve].star_png_radius_px: zu klein fuer eine brauchbare Hilfe"
    assert 0 < rc["overlay_alpha_frac"] <= 1, "[resolve].overlay_alpha_frac: 0..1"
    assert 0 < rc["iou_min"] <= 1, "[resolve].iou_min: 0..1"
    cfg["resolve"] = rc
    return cfg


def poster_px():
    """Breite, Hoehe des Vorschau-Plakats (= Timeline) in Pixeln."""
    return S.SIZES[KL.PREVIEW][:2]


# ---------------------------------------------------------------- Hilfsbilder

def star_alpha(R, rot, w, h, cx, cy):
    """Antialiaste Sternmaske (0..1) in einem w x h-Bild, Mitte (cx, cy) in Pixelkanten-Koordinaten, Spitzenradius R,
    Drehung rot (Grad, Uhrzeigersinn). Dieselbe Form wie im Plakat (styles.star_r), dort aber auf 4-px-Zellen."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
    return np.clip(S.star_r(dx, dy, rot) * R - np.hypot(dx, dy) + 0.5, 0, 1)


def assets(cfg):
    """layout.png (Frame 1 ohne Stern), type_overlay.png (nur der Satz, halbtransparent), star.png (weiss, rot = 0)."""
    rc = cfg["resolve"]
    W, H = poster_px()
    st = KL.poster_style(cfg, 0)
    st["star"], st["S"] = OFF_CANVAS_STAR, KL.S_CODES[PLAIN_SPARK]
    layout = K.frame_of(st, KL.PREVIEW)
    _, layers = S.render(dict(st), KL.PREVIEW)
    rgba = np.zeros((H, W, 4), np.float32)
    for name, lay in layers.items():                         # alles ausser Grund und Stern = Satz (Titel, Datum, QR, CTA)
        if name in ("bg", "spark"):
            continue
        a = lay[..., 3:] / 255.0
        rgba[..., :3] += a * (lay[..., :3] - rgba[..., :3])
        rgba[..., 3:] = np.maximum(rgba[..., 3:], a)
    rgba[..., 3] *= rc["overlay_alpha_frac"]
    R = rc["star_png_radius_px"]
    side = 2 * (R + STAR_PAD_PX)
    a = star_alpha(R, 0.0, side, side, side / 2, side / 2)
    star = np.dstack([np.full((side, side, 3), 255.0), a * 255])
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(layout).save(ASSETS["layout"])
    Image.fromarray(np.round(np.dstack([rgba[..., :3], rgba[..., 3:] * 255])).astype(np.uint8), "RGBA").save(ASSETS["type_overlay"])
    Image.fromarray(np.round(star).astype(np.uint8), "RGBA").save(ASSETS["star"])
    return f"{W}x{H} layout + type_overlay, star {side}x{side} (Spitzenradius {R} px) → {OUT}"


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    cfg = load()
    if cmd == "assets":
        print(assets(cfg))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
