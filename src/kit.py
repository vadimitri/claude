#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "scikit-image", "qrcode", "opencv-python-headless"]
# ///
"""Spark Kit: Bausteine fuer den Schnitt in DaVinci Resolve (Vadim 10.10.: "Claude Bausteine, ich Schnitt").

Warum Grauwerte: Python rendert jedes Element als Wertfeld (0 = Grund, 1 = Tinte), die Spark Lens in Resolve (DCTL, gleiche
Mathe wie der Figma-Shader "Spark Lens" v5 und styles.dither) rastert und faerbt es. So ist jede Colorway ein Klick statt
ein neuer Render, und Text+ aus Resolve wird durch die Lens automatisch Pixel-Schrift auf dem Raster (T2 Clash-Bit).

  uv run src/kit.py lens        DCTLs -> kit/out/lens/ + Resolve-LUT-Ordner (Effekt "Spark Lens" + je Colorway eine LUT)
  uv run src/kit.py elements    Spark-Loops S2/S7, Spark-Blende, Flow-Gruende, Wortmarke, Logo (grau, Alpha) -> kit/out/elements/
  uv run src/kit.py sound       Hits, Riser, Whoosh, Klicks, Chiptune, MN-Bett -> kit/out/sound/
  uv run src/kit.py brand       Colorway-Bogen + Testbild fuer die Lens -> kit/out/brand/
  uv run src/kit.py qr [URL]     gluehender QR (Telegram) als Grau-Element, Lesbarkeit nach Lens in allen Colorways geprueft
  uv run src/kit.py wall WORT    Wortwand (Begriff in Zeilen, Clash-Bit) je Format
  uv run src/kit.py sheet [P]    Standbilder aller Elemente durch die Lens (~10 s, vor dem Rendern ansehen)
  uv run src/kit.py look IMG P11  ein Bild durch die Lens (numpy-Referenz) -> kit/out/look_<name>_<P>.png
  uv run src/kit.py all         lens + brand + sound + elements
  uv run src/kit.py test        Selbsttest (Lens = styles.dither, Kanten-Schnapp, Loops nahtlos, Sound ohne Klick)
  uv run src/kit.py publish     kit/out -> [publish].dir (Team-Nextcloud)
Resolve-Projekt bauen: src/kit_resolve.py (siehe docs/RESOLVE.md).
"""
import math
import shutil
import subprocess
import sys
import tomllib
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import styles as S
from makernight_sparks import PROF

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"
OUT = KIT / "out"
STEPS = 6                                                                  # Lens: 6 Colorway-Stufen (k/5)
P_KEY = {code: key for code, key, *_ in next(a for a in S.AXES if a[0] == "P")[3]}   # "P11" -> "cherenkov"
LUMA = np.array([0.2126, 0.7152, 0.0722])                                  # Rec.709, wie der Figma-Shader
SNAP_PX = 2                                                                # Kanten-Schnapp: Nachbarn +-2 px (Shader)


def load(path=KIT / "kit.toml"):
    """Config lesen und vor dem Rendern pruefen (Klartext statt Abbruch nach Minuten)."""
    cfg = tomllib.loads(path.read_text())
    order = cfg["lens"]["order"]
    bad = [p for p in order if p not in P_KEY]
    if bad:
        sys.exit(f"kit.toml [lens].order: unbekannte Colorway {bad}, bekannt: {sorted(P_KEY)}")
    if len(set(order)) != len(order):
        sys.exit("kit.toml [lens].order: Colorway doppelt")
    if cfg["resolve"]["default_colorway"] not in order:
        sys.exit("kit.toml [resolve].default_colorway fehlt in [lens].order")
    e = cfg["elements"]
    for k, (w, h) in e["formats"].items():
        if w % cfg["lens"]["cell_px"] or h % cfg["lens"]["cell_px"]:      # 4:5 = 1080x1350 ist Instagram-Pflicht
            print(f"Hinweis: {k} {w}x{h} nicht durch cell_px teilbar, letzte Zellreihe ist halb so hoch")
    for k in ("spin_loop_s", "nest_loop_s", "cover_s", "flow_loop_s"):
        if abs(e["fps"] * e[k] - round(e["fps"] * e[k])) > 1e-9:
            sys.exit(f"kit.toml [elements].{k} * fps muss ganzzahlig sein (sonst Sprung an der Naht)")
    return cfg


def pal6(code):
    """6 Stufen RGB 0..255; 4-stufige Paletten (P6, P9, P26) gedoppelt 0 1 1 2 2 3 wie flow.pal6 und Figma."""
    pal = S.hexpal(P_KEY[code])
    return pal[np.round(np.arange(STEPS) * (len(pal) - 1) / (STEPS - 1)).astype(int)].astype(np.uint8)


def name(code):
    return f"{code} {S.CODENAME[P_KEY[code]]}"


def main_root():
    """Hauptcheckout: gitignorierte Eingaben (makernight/loop) liegen nur dort, nicht in einem Worktree."""
    common = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True).stdout.strip()
    return Path(common).parent if common else ROOT


# ---------------------------------------------------------------- Lens: DCTL + numpy-Referenz

DCTL = """// Spark Lens - generiert von src/kit.py aus kit/kit.toml + styles.PALS. Nicht von Hand aendern: neu erzeugen.
// Wie Figma-Shader "Spark Lens" v5 und styles.dither: Graustufe an der Zellmitte -> Bayer 4x4 -> 6 Colorway-Stufen.
// Effekt: Edit/Color page > OpenFX > ResolveFX Color > DCTL > "Spark Lens". Als LUT: Node > LUT > Spark > Colorways.
DEFINE_UI_PARAMS(pal, Colorway, DCTLUI_COMBO_BOX, {default}, {{ {enums} }}, {{ {labels} }})
DEFINE_UI_PARAMS(cell, Cell size px, DCTLUI_SLIDER_INT, {cell}, 1, 24, 1)
DEFINE_UI_PARAMS(transp, Transparent ground, DCTLUI_CHECK_BOX, 0)
DEFINE_UI_PARAMS(ditherTo, Photo fade dither up to, DCTLUI_SLIDER_FLOAT, 1.0, 0.0, 1.0, 0.01)
DEFINE_UI_PARAMS(fadeLen, Photo fade length, DCTLUI_SLIDER_FLOAT, 0.35, 0.01, 1.0, 0.01)
DEFINE_UI_PARAMS(fadeAng, Photo fade angle, DCTLUI_SLIDER_FLOAT, 0.0, -180.0, 180.0, 15.0)
DEFINE_UI_PARAMS(journey, Journey frames per colorway, DCTLUI_SLIDER_INT, 0, 0, 24, 1)
DEFINE_UI_PARAMS(jset, Journey set, DCTLUI_COMBO_BOX, 0, {{ J_ALL, J_MN, J_KICK }}, {{ All colorways, Maker Night purple, Kick-off no purple }})
DEFINE_UI_PARAMS(boil, Boil frames, DCTLUI_SLIDER_INT, 0, 0, 12, 1)
DEFINE_DCTL_ALPHA_MODE_STRAIGHT

__CONSTANT__ float PAL[{npal}] = {{ {pal} }};
// Journey (Kick-off: jedes Bild eine andere Welt): Colorway-Index-Listen je Set, Start = gewaehlte Colorway
__CONSTANT__ int SETS[{nsets}] = {{ {sets} }};
__CONSTANT__ int SET_OFF[3] = {{ {set_off} }};
__CONSTANT__ int SET_LEN[3] = {{ {set_len} }};
// Boil (Korn kocht wie der 15-fps-Boil des MN-Teasers): Bayer-Muster je Schritt um (x, y) Zellen verschoben
__CONSTANT__ int SHIFT[8] = {{ {shift} }};
__CONSTANT__ float BAYER[16] = {{ 0.0f, 8.0f, 2.0f, 10.0f, 12.0f, 4.0f, 14.0f, 6.0f, 3.0f, 11.0f, 1.0f, 9.0f, 15.0f, 7.0f, 13.0f, 5.0f }};

__DEVICE__ float bayer4(int x, int y)
{{
    return (BAYER[(y % 4) * 4 + (x % 4)] + 0.5f) / 16.0f;
}}

// Wert eines Pixels: Luma (Rec.709 auf Codewerten), straight alpha ueber Schwarz (= Grund) komponiert wie im Figma-Shader
__DEVICE__ float val(int w, int h, float x, float y, __TEXTURE__ r, __TEXTURE__ g, __TEXTURE__ b, __TEXTURE__ a)
{{
    const int xi = (int)_clampf(x, 0.0f, (float)(w - 1));
    const int yi = (int)_clampf(y, 0.0f, (float)(h - 1));
    const float l = 0.2126f * _tex2D(r, xi, yi) + 0.7152f * _tex2D(g, xi, yi) + 0.0722f * _tex2D(b, xi, yi);
    return _saturatef(l * _tex2D(a, xi, yi));
}}

// Abstand zur naechsten Stufe k/5, in Stufen
__DEVICE__ float off(float v)
{{
    const float x = v * 5.0f;
    return _fabs(x - _round(x));
}}

__DEVICE__ float4 transform(int p_Width, int p_Height, int p_X, int p_Y, __TEXTURE__ p_TexR, __TEXTURE__ p_TexG, __TEXTURE__ p_TexB, __TEXTURE__ p_TexA)
{{
    const int cx = p_X / cell;
    const int cy = p_Y / cell;
    const float c = (float)cell;
    // Foto-Fade: Zelle fuer Zelle loest sich der Dither in Bayer-Reihenfolge (transponiert) ins Original auf. 1 = nie Foto.
    const float ang = fadeAng * 3.14159265f / 180.0f;
    const float ux = ((float)cx + 0.5f) * c / (float)p_Width - 0.5f;
    const float uy = ((float)cy + 0.5f) * c / (float)p_Height - 0.5f;
    const float along = ux * _sinf(ang) - uy * _cosf(ang) + 0.5f;
    const float keep = _saturatef(1.0f - (along - ditherTo) / _fmaxf(fadeLen, 0.0001f));
    if (keep < bayer4(cy, cx)) {{
        return make_float4(_tex2D(p_TexR, p_X, p_Y), _tex2D(p_TexG, p_X, p_Y), _tex2D(p_TexB, p_X, p_Y), _tex2D(p_TexA, p_X, p_Y));
    }}
    // Journey + Boil haengen am Timeline-Bild (nur im ResolveFX-Plugin; als LUT ist TIMELINE_FRAME_INDEX = 1, Regler 0)
    const int fr = TIMELINE_FRAME_INDEX;
    int sxo = 0;
    int syo = 0;
    if (boil > 0) {{
        const int k = (fr / boil) % 4;
        sxo = SHIFT[2 * k];
        syo = SHIFT[2 * k + 1];
    }}
    int p = (int)pal;
    if (journey > 0) {{
        const int s = (int)jset;
        int start = 0;
        for (int i = 0; i < SET_LEN[s]; i++) {{
            if (SETS[SET_OFF[s] + i] == p) start = i;
        }}
        p = SETS[SET_OFF[s] + (start + fr / journey) % SET_LEN[s]];
    }}
    // Abtastung in der Zellmitte, wie styles.py Felder an Zellmitten auswertet
    const float sx = (float)(cx * cell + cell / 2);
    const float sy = (float)(cy * cell + cell / 2);
    float v = val(p_Width, p_Height, sx, sy, p_TexR, p_TexG, p_TexB, p_TexA);
    // Kanten-Schnapp: geglaettete Kanten (Text+, skalierte Clips) hart entscheiden, echte Verlaeufe bleiben.
    // Abweichung vom Figma-Shader v5: kein "v liegt nicht auf einer Stufe"-Schutz. Befund 10.10.: Kantensaum-Werte wie 0.4
    // liegen genau auf Stufe 2 und blieben als Streupixel stehen (368 px in der Wortmarke); gewaehlt wird ohnehin nur mn/mx.
    const float va = val(p_Width, p_Height, sx - {snap}.0f, sy, p_TexR, p_TexG, p_TexB, p_TexA);
    const float vb = val(p_Width, p_Height, sx + {snap}.0f, sy, p_TexR, p_TexG, p_TexB, p_TexA);
    const float vc = val(p_Width, p_Height, sx, sy - {snap}.0f, p_TexR, p_TexG, p_TexB, p_TexA);
    const float vd = val(p_Width, p_Height, sx, sy + {snap}.0f, p_TexR, p_TexG, p_TexB, p_TexA);
    const float mn = _fminf(_fminf(va, vb), _fminf(vc, vd));
    const float mx = _fmaxf(_fmaxf(va, vb), _fmaxf(vc, vd));
    if (off(mn) < 0.2f && off(mx) < 0.2f && mx - mn > 0.1f) {{
        v = _round((v > 0.5f * (mn + mx) ? mx : mn) * 5.0f) / 5.0f;
    }}
    // styles.dither: x = v*5 + 1e-4, idx = floor(x) + (frac > bayer)
    const float x = v * 5.0f + 0.0001f;
    const float lo = _floorf(x);
    const int idx = (int)_fminf(lo + (x - lo > bayer4(cx + 4 - sxo, cy + 4 - syo) ? 1.0f : 0.0f), 5.0f);
    if (transp != 0 && idx == 0) {{
        return make_float4(0.0f, 0.0f, 0.0f, 0.0f);
    }}
    const int o = (p * 6 + idx) * 3;
    return make_float4(PAL[o], PAL[o + 1], PAL[o + 2], 1.0f);
}}
"""


def dctl(cfg, default=0, alpha=True):
    """alpha=False: LUT-Fassung fuer Nodes/Timeline-Grade. Befund 10.10.: als Node-LUT reicht Resolve eine float4-DCTL
    (Alpha) stumm durch (Testbild kam grau zurueck), Alpha-DCTLs laufen nur im ResolveFX-DCTL-Plugin (README Abschnitt 7)."""
    order = cfg["lens"]["order"]
    vals = [f"{c / 255:.6f}f" for p in order for c in pal6(p).ravel()]
    sets = journey_sets(order)
    off = [0, len(sets[0]), len(sets[0]) + len(sets[1])]
    src = DCTL.format(default=default, enums=", ".join(f"CW_{p}" for p in order),
                      labels=", ".join(name(p) for p in order), cell=cfg["lens"]["cell_px"], npal=len(vals),
                      pal=", ".join(vals), snap=SNAP_PX, nsets=sum(map(len, sets)),
                      sets=", ".join(str(i) for s in sets for i in s), set_off=", ".join(map(str, off)),
                      set_len=", ".join(str(len(s)) for s in sets), shift=", ".join(str(v) for xy in BOIL for v in xy))
    if alpha:
        return src
    tex = "_tex2D(p_TexR, p_X, p_Y), _tex2D(p_TexG, p_X, p_Y), _tex2D(p_TexB, p_X, p_Y)"
    for a, b in [("DEFINE_DCTL_ALPHA_MODE_STRAIGHT\n", ""),
                 ("DEFINE_UI_PARAMS(transp, Transparent ground, DCTLUI_CHECK_BOX, 0)\n", ""),
                 (", __TEXTURE__ b, __TEXTURE__ a)", ", __TEXTURE__ b)"), ("l * _tex2D(a, xi, yi)", "l"),
                 (", p_TexB, p_TexA)", ", p_TexB)"), ("__TEXTURE__ p_TexB, __TEXTURE__ p_TexA)", "__TEXTURE__ p_TexB)"),
                 ("__DEVICE__ float4 transform", "__DEVICE__ float3 transform"),
                 (f"make_float4({tex}, _tex2D(p_TexA, p_X, p_Y))", f"make_float3({tex})"),
                 ("    if (transp != 0 && idx == 0) {\n        return make_float4(0.0f, 0.0f, 0.0f, 0.0f);\n    }\n", ""),
                 ("make_float4(PAL[o], PAL[o + 1], PAL[o + 2], 1.0f)", "make_float3(PAL[o], PAL[o + 1], PAL[o + 2])"),
                 ("// Effekt:", "// LUT-Fassung ohne Alpha (Node-LUTs reichen Alpha-DCTLs durch). Effekt mit Alpha:")]:
        assert a in src, f"DCTL-Vorlage geaendert, LUT-Fassung passt nicht mehr: {a!r}"
        src = src.replace(a, b)
    assert "p_TexA" not in src and "float4" not in src
    return src


BOIL = [(0, 0), (2, 1), (1, 3), (3, 2)]                   # Boil-Verschiebungen (x, y) in Zellen: jede Phase eine andere Lage


def journey_sets(order):
    """Indizes in order: alle, Maker Night (lila), Kick-off (ohne Lila), wie "Lila gehoert der Maker Night"."""
    return [list(range(len(order))), [i for i, p in enumerate(order) if S.lila(P_KEY[p])],
            [i for i, p in enumerate(order) if not S.lila(P_KEY[p])]]


def lens_at(cfg, code, frame, journey=0, jset=0, boil=0):
    """(Colorway, Bayer-Verschiebung y/x) der DCTL in Timeline-Bild `frame`: Referenz fuer Journey und Boil."""
    order = cfg["lens"]["order"]
    if journey:
        s = journey_sets(order)[jset]
        start = s.index(order.index(code)) if order.index(code) in s else 0
        code = order[s[(start + frame // journey) % len(s)]]
    sx, sy = BOIL[(frame // boil) % 4] if boil else (0, 0)
    return code, (sy, sx)


def lens(rgb, code, cell=4, alpha=None, transparent=False, snap=True, shift=(0, 0)):
    """numpy-Referenz der DCTL (ohne Foto-Fade): HxWx3 float 0..1 -> HxWx4 uint8. Fuer Selbsttest und `look`.
    shift = Bayer-Verschiebung (y, x) in Zellen (Boil, siehe lens_at)."""
    h, w = rgb.shape[:2]
    lum = np.clip((rgb @ LUMA) * (1 if alpha is None else alpha), 0, 1)
    sy = np.arange(h // cell) * cell + cell // 2
    sx = np.arange(w // cell) * cell + cell // 2
    at = lambda dy, dx: lum[np.clip(sy + dy, 0, h - 1)][:, np.clip(sx + dx, 0, w - 1)]
    v = at(0, 0)
    if snap:
        nb = np.stack([at(0, -SNAP_PX), at(0, SNAP_PX), at(-SNAP_PX, 0), at(SNAP_PX, 0)])
        mn, mx = nb.min(0), nb.max(0)
        off = lambda a: np.abs(a * 5 - np.round(a * 5))
        hit = (off(mn) < 0.2) & (off(mx) < 0.2) & (mx - mn > 0.1)
        v = np.where(hit, np.round(np.where(v > 0.5 * (mn + mx), mx, mn) * 5) / 5, v)
    idx = S.dither(v, STEPS - 1, "bayer4", cell, shift=shift)
    out = np.zeros((h, w, 4), np.uint8)
    ch, cw = idx.shape
    out[:ch, :cw, :3] = pal6(code)[idx]
    out[:ch, :cw, 3] = np.where(transparent & (idx == 0), 0, 255)
    return out


GLOW_SAMPLES = 16                       # wie kickoff_loop_end.GLOW_SAMPLES: so viele vergroesserte Kopien je Schweif

GLOW = """// Spark Glow - generiert von src/kit.py. Nicht von Hand aendern: neu erzeugen.
// Lichtschweif wie im Kick-off (kickoff_loop_end.glow_layer / flare_layer, Halos F16-F19): das Bild {n}-mal um die Mitte
// vergroessert (bis exp(Length)), Gewicht faellt linear nach aussen, Maximum. Gerechnet an Zellmitten (Raster der Lens).
// Wirkt im Grauraum UNTER der Lens (die rastert und faerbt es). Length keyframen = Halo waechst (Vadim: nur wachsen lassen).
DEFINE_UI_PARAMS(gx, Centre X, DCTLUI_SLIDER_FLOAT, 0.5, 0.0, 1.0, 0.001)
DEFINE_UI_PARAMS(gy, Centre Y, DCTLUI_SLIDER_FLOAT, 0.5, 0.0, 1.0, 0.001)
DEFINE_UI_PARAMS(glen, Length, DCTLUI_SLIDER_FLOAT, 0.6, 0.0, 3.0, 0.01)
DEFINE_UI_PARAMS(peak, Peak, DCTLUI_SLIDER_FLOAT, 0.8, 0.0, 1.0, 0.01)
DEFINE_UI_PARAMS(cell, Cell size px, DCTLUI_SLIDER_INT, {cell}, 1, 24, 1)
{alpha_mode}
// Licht einer Stelle: Luma (Rec.709) x Alpha; ausserhalb des Bildes kein Licht
__DEVICE__ float lum(int w, int h, float x, float y, __TEXTURE__ r, __TEXTURE__ g, __TEXTURE__ b{a_param})
{{
    if (x < 0.0f || y < 0.0f || x >= (float)w || y >= (float)h) return 0.0f;
    const int xi = (int)x;
    const int yi = (int)y;
    return _saturatef((0.2126f * _tex2D(r, xi, yi) + 0.7152f * _tex2D(g, xi, yi) + 0.0722f * _tex2D(b, xi, yi)){a_mul});
}}

__DEVICE__ {ret} transform(int p_Width, int p_Height, int p_X, int p_Y, __TEXTURE__ p_TexR, __TEXTURE__ p_TexG, __TEXTURE__ p_TexB{a_tex})
{{
    const float px = (float)((p_X / cell) * cell + cell / 2);
    const float py = (float)((p_Y / cell) * cell + cell / 2);
    const float mx = gx * (float)p_Width;
    const float my = gy * (float)p_Height;
    float gl = 0.0f;
    for (int j = 1; j <= {n}; j++) {{
        const float s = _expf(glen * (float)j / {n}.0f);
        gl = _fmaxf(gl, lum(p_Width, p_Height, mx + (px - mx) / s, my + (py - my) / s, p_TexR, p_TexG, p_TexB{a_call})
                        * (1.0f - (float)j / {n1}.0f));
    }}
    gl *= peak;
    const float r = _tex2D(p_TexR, p_X, p_Y);
    const float g = _tex2D(p_TexG, p_X, p_Y);
    const float b = _tex2D(p_TexB, p_X, p_Y);
{tail}
}}
"""
GLOW_TAIL_ALPHA = """    const float a = _tex2D(p_TexA, p_X, p_Y);
    const float own = _saturatef((0.2126f * r + 0.7152f * g + 0.0722f * b) * a);
    if (gl <= own) return make_float4(r, g, b, a);
    if (a > 0.999f) return make_float4(gl, gl, gl, 1.0f);
    return make_float4(1.0f, 1.0f, 1.0f, gl);              // Licht ueber Transparenz: weiss mit Deckkraft = Helligkeit"""
GLOW_TAIL_LUT = """    const float own = _saturatef(0.2126f * r + 0.7152f * g + 0.0722f * b);
    if (gl <= own) return make_float3(r, g, b);
    return make_float3(gl, gl, gl);"""


def glow_dctl(cfg, alpha=True):
    """Effekt (alpha=True, ResolveFX) bzw. LUT-Fassung ohne Alpha (fuer den Render-Vergleich gegen glow())."""
    a = alpha
    return GLOW.format(n=GLOW_SAMPLES, n1=GLOW_SAMPLES + 1, cell=cfg["lens"]["cell_px"],
                       alpha_mode="DEFINE_DCTL_ALPHA_MODE_STRAIGHT\n" if a else "",
                       a_param=", __TEXTURE__ a" if a else "", a_mul=" * _tex2D(a, xi, yi)" if a else "",
                       ret="float4" if a else "float3", a_tex=", __TEXTURE__ p_TexA" if a else "",
                       a_call=", p_TexA" if a else "", tail=GLOW_TAIL_ALPHA if a else GLOW_TAIL_LUT)


def glow(lum, gx=0.5, gy=0.5, glen=0.6, peak=0.8, cell=4):
    """numpy-Referenz der Glow-DCTL (LUT-Fassung): Graubild HxW 0..1 -> Graubild mit Lichtschweif."""
    h, w = lum.shape
    yy, xx = np.mgrid[0:h, 0:w]
    py = ((yy // cell) * cell + cell // 2).astype(np.float32)
    px = ((xx // cell) * cell + cell // 2).astype(np.float32)
    my, mx = np.float32(gy * h), np.float32(gx * w)
    gl = np.zeros((h, w), np.float32)
    for j in range(1, GLOW_SAMPLES + 1):
        s = np.float32(math.exp(glen * j / GLOW_SAMPLES))
        qx, qy = mx + (px - mx) / s, my + (py - my) / s
        ok = (qx >= 0) & (qy >= 0) & (qx < w) & (qy < h)
        v = np.where(ok, lum[np.clip(qy, 0, h - 1).astype(int), np.clip(qx, 0, w - 1).astype(int)], 0)
        gl = np.maximum(gl, v * np.float32(1 - j / (GLOW_SAMPLES + 1)))
    return np.maximum(lum, gl * np.float32(peak))


def glow_testchart(w=1080, h=1920):
    """Wortmarke + Logo auf Schwarz: Quelle fuer den Lichtschweif (Render-Vergleich Resolve gegen glow())."""
    img = np.zeros((h, w), np.float32)
    wm = wordmark(round(0.66 * w)).astype(np.float32)[..., 3] / 255
    y0, x0 = h // 2 - wm.shape[0] // 2, (w - wm.shape[1]) // 2
    img[y0:y0 + wm.shape[0], x0:x0 + wm.shape[1]] = wm
    s = round(0.37 * w)
    lg = logo(s).astype(np.float32)[..., 3] / 255
    y1, x1 = round(0.1 * h), (w - s) // 2
    img[y1:y1 + s, x1:x1 + s] = np.maximum(img[y1:y1 + s, x1:x1 + s], lg)
    return img


def cmd_lens(cfg):
    """Effekt mit Colorway-Menue + je Colorway eine LUT-Datei (Voreinstellung = diese Colorway, fuer Node/Timeline-Grade)."""
    out = OUT / "lens"
    shutil.rmtree(out, ignore_errors=True)
    (out / "Colorways").mkdir(parents=True)
    (out / "Spark Lens.dctl").write_text(dctl(cfg))
    (out / "Spark Glow.dctl").write_text(glow_dctl(cfg))
    (OUT / "lens_test").mkdir(parents=True, exist_ok=True)                 # LUT-Fassung nur fuer den Render-Vergleich
    (OUT / "lens_test" / "Spark Glow LUT.dctl").write_text(glow_dctl(cfg, alpha=False))
    for i, p in enumerate(cfg["lens"]["order"]):
        (out / "Colorways" / f"{name(p)}.dctl").write_text(dctl(cfg, i, alpha=False))
    dst = Path(cfg["lens"]["resolve_dir"])
    if dst.parent.is_dir():
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(out, dst)
        print(f"Lens: {1 + len(cfg['lens']['order'])} DCTLs -> {out} + {dst}")
    else:
        print(f"Lens: -> {out} (Resolve-LUT-Ordner fehlt, nicht installiert)")


# ---------------------------------------------------------------- Elemente (Grauwerte, Alpha)

def ffmpeg(path, w, h, fps, alpha, frames):
    """Bilder roh in ffmpeg. Alpha (HxWx4) -> ProRes 4444, sonst Graufeld (HxW) -> H.264 (klein, Resolve-tauglich)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    enc = (["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"] if alpha else
           ["-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba" if alpha else "gray",
                           "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", *enc, str(path)], stdin=subprocess.PIPE)
    n = 0
    for f in frames:
        ff.stdin.write(f.tobytes())
        n += 1
    ff.stdin.close()
    if ff.wait():
        sys.exit(f"ffmpeg fehlgeschlagen: {path}")
    return n


def rgba(v, m):
    """Wertfeld + Maske -> RGBA uint8 (grau)."""
    g = np.round(np.clip(v, 0, 1) * 255).astype(np.uint8)
    return np.dstack([g, g, g, np.where(m, 255, 0).astype(np.uint8)])


def polar(w, h, cx, cy):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    dx, dy = xx - cx, yy - cy
    return np.hypot(dx, dy), np.degrees(np.arctan2(dy, dx))


def star_dp(rr, ang, R, rot):
    """Abstand relativ zum Sternrand (1 = Rand), Profil aus dem echten Logo (makernight_sparks.PROF)."""
    return rr / (np.interp((ang - rot) % 360, np.arange(3601) / 10, np.append(PROF, PROF[0])) * R)


def star_d(w, h, cx, cy, R, rot):
    return star_dp(*polar(w, h, cx, cy), R, rot)


def spin_frames(e):
    """S2: Verlaufsstern dreht in einer Schleife genau 60 Grad (6 Zacken: Bild n = Bild 0)."""
    s, n = e["spin_px"], round(e["fps"] * e["spin_loop_s"])
    pol = polar(s, s, s / 2, s / 2)
    for i in range(n):
        d = star_dp(*pol, e["spin_radius_frac"] * s, 60 * i / n)
        yield rgba(e["grad_low"] + (e["grad_high"] - e["grad_low"]) * np.clip(1 - d, 0, 1) ** 0.7, d < 1)


def nest_frames(e):
    """S7 wie styles.spark: Puppen R*ratio^k, je +30 Grad, XOR; Wert = S2-Verlauf des aeusseren Sterns, Alpha = Nest
    (die Luecken zeigen, was darunter liegt). Dreht wie der Spin 60 Grad je Schleife (alle Puppen 6-zackig: nahtlos)."""
    s, n = e["spin_px"], round(e["fps"] * e["spin_loop_s"])
    R = e["spin_radius_frac"] * s
    pol = polar(s, s, s / 2, s / 2)
    for i in range(n):
        rot, m, k = 60 * i / n, np.zeros((s, s), bool), 0
        while R * e["nest_ratio"] ** k >= 0.5:
            m ^= star_dp(*pol, R * e["nest_ratio"] ** k, rot + e["nest_turn_deg"] * k) < 1
            k += 1
        d = star_dp(*pol, R, rot)
        yield rgba(e["grad_low"] + (e["grad_high"] - e["grad_low"]) * np.clip(1 - d, 0, 1) ** 0.7, m)


def tunnel_frame(e, ph, w, h, pol=None):
    """S7 als Tunnel bildfuellend (Rezept "Infinite Nest", Maker-Night-Teaser 25.9.): Puppen wachsen nach aussen. Puppen,
    die das Bild ganz decken, werden nicht gezeichnet, aber mitgezaehlt (Paritaet kippt nie beim Zoomen), Puppen unter
    einem halben Pixel fallen weg. Die Reihe beginnt bei einer Puppe, die in jeder Drehung deckt: nur dann ist Phase 2 =
    Phase 0 (Befund 10.10.: Start bei Fenstergroesse gab 25 % Abweichung an der Naht). Nach 1 Schritt invertiert."""
    D = math.hypot(w, h) / 2
    R0 = 1.001 * D / PROF.min()
    rr, ang = pol or polar(w, h, w / 2, h / 2)
    m, k = np.zeros((h, w), bool), 0
    while R0 * e["nest_ratio"] ** (k - ph) >= 0.5:
        Rk = R0 * e["nest_ratio"] ** (k - ph)
        if Rk * PROF.min() > D:
            m = ~m
        else:
            m ^= star_dp(rr, ang, Rk, e["nest_turn_deg"] * (k - ph)) < 1
        k += 1
    return np.where(m, 255, 0).astype(np.uint8)


def tunnel_frames(e, w, h):
    n = round(e["fps"] * e["nest_loop_s"])
    pol = polar(w, h, w / 2, h / 2)
    for i in range(n):
        yield tunnel_frame(e, 2 * i / n, w, h, pol)


def cover_frames(e, w, h):
    """Spark-Blende: Tintenstern waechst exponentiell vom Punkt bis bildfuellend (letztes Bild = ganz bedeckt).
    Rueckwaerts abgespielt = Aufdecken. Schnitt auf das letzte Bild legen."""
    n = round(e["fps"] * e["cover_s"])
    r_end = 1.02 * math.hypot(w, h) / 2 / PROF.min()               # Innenradius >= halbe Diagonale: ganz bedeckt
    pol = polar(w, h, w / 2, h / 2)
    for i in range(n):
        u = (i + 1) / n
        R = r_end * 0.02 ** (1 - u)                                   # exponentiell: gleichmaessiges Zoomgefuehl
        yield rgba(np.ones((h, w)), star_dp(*pol, R, e["cover_turn_deg"] * u) < 1)


def flow_frames(e, style, w, h):
    import flow
    st = tomllib.loads(flow.CONFIG.read_text())["style"][style]
    n = round(e["fps"] * e["flow_loop_s"])
    for i in range(n):
        v = flow.field(w, h, i / e["fps"], e["flow_loop_s"], -60.0, cell=1, **st)
        yield np.round(np.clip(v, 0, 1) * 255).astype(np.uint8)


def wordmark(px):
    """SPARK in Clash Display Bold, Kernpaare aus styles.KERN (P-A), weiss auf Alpha. Die Lens rastert es."""
    word, size = "SPARK", px // 3

    def setz(size):
        f = S.font("ClashDisplay-Variable.ttf", size, "Bold")
        cap = f.getbbox("H")[3] - f.getbbox("H")[1]
        xs = [f.getlength(word[:i]) + sum(S.KERN.get(word[j - 1:j + 1], 0) for j in range(1, i + 1)) * cap
              for i in range(len(word))]
        return f, cap, xs, xs[-1] + f.getlength("K")

    f, cap, xs, wd = setz(size)
    f, cap, xs, wd = setz(round(size * px / wd))                      # direkt in Zielgroesse setzen: kein Verkleinern
    pad = round(0.06 * px)                                            # (Befund 10.10.: Lanczos-Ringing gab Streupixel)
    im = Image.new("L", (px + 2 * pad, round(cap + 2 * pad)), 0)
    dr = ImageDraw.Draw(im)
    for x, ch in zip(xs, word):
        dr.text((pad + x, pad + cap), ch, 255, font=f, anchor="ls")
    a = np.array(im)
    return np.dstack([np.full_like(a, 255)] * 3 + [a])


def logo(px):
    d = star_d(px, px, px / 2, px / 2, 0.49 * px, 90)               # Spitze nach oben wie im Logo
    a = np.clip((1 - d) * 0.49 * px + 0.5, 0, 1)                    # 1 px Kantenglaettung, die Lens schnappt sie
    return np.dstack([np.full((px, px), 255, np.uint8)] * 3 + [np.round(a * 255).astype(np.uint8)])


def cmd_elements(cfg):
    e, out = cfg["elements"], OUT / "elements"
    s = e["spin_px"]
    jobs = [("spark_spin_S2.mov", s, s, True, lambda: spin_frames(e)),
            ("spark_nest_S7.mov", s, s, True, lambda: nest_frames(e))]
    for fmt, (w, h) in e["formats"].items():
        jobs.append((f"spark_cover_{fmt}.mov", w, h, True, lambda w=w, h=h: cover_frames(e, w, h)))
        jobs.append((f"nest_tunnel_{fmt}.mp4", w, h, False, lambda w=w, h=h: tunnel_frames(e, w, h)))
        for st in e["flow_styles"]:
            jobs.append((f"flow_{st}_{fmt}.mp4", w, h, False, lambda st=st, w=w, h=h: flow_frames(e, st, w, h)))
    for fn, w, h, alpha, frames in jobs:
        n = ffmpeg(out / fn, w, h, e["fps"], alpha, frames())
        print(f"  {fn}: {n} Bilder ({n / e['fps']:.2f} s)")
    Image.fromarray(wordmark(e["wordmark_px"])).save(out / "wordmark_SPARK.png")
    Image.fromarray(logo(e["logo_px"])).save(out / "logo_spark.png")
    print(f"Elemente -> {out}")


def paper(code):
    """Papier-Colorway: Stufe 0 (Grund) heller als Stufe 5 (Tinte), Wert 1 = dunkel."""
    p = pal6(code).astype(np.float32) @ LUMA
    return p[0] > p[-1]


def qr_element(q, url, on_paper=False):
    """Gluehender QR im Grauraum: helle Module light_value, dunkle 0, Platte mit Ruhezone, aussen Lichtabfall
    exponentiell vom Plattenrand (rund um die Ecken), als Licht: weiss mit Deckkraft = Helligkeit (wie Spark Glow).
    on_paper: fuer Papier-Colorways (Wert 1 = dunkel) gespiegelt, dunkle Module = Tinte auf heller Platte, kein Gluehen
    (Befund 10.10.: ohne Spiegelung las der QR in P8 P16 P21-P24 nicht, er stand invertiert)."""
    import qrcode
    from scipy.ndimage import distance_transform_edt
    qq = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qq.add_data(url)
    qq.make(fit=True)
    m = np.array(qq.get_matrix(), bool)
    mod, quiet = q["module_px"], q["quiet_modules"]
    cell = mod // 2
    plate = np.pad(~m, quiet, constant_values=True).astype(np.float32) * q["light_value"]
    if on_paper:
        plate = 1 - plate
    plate = np.repeat(np.repeat(plate, mod, 0), mod, 1)
    pad = 0 if on_paper else q["glow_cells"] * cell
    if not pad:
        v = np.round(plate * 255).astype(np.uint8)
        return np.dstack([v, v, v, np.full_like(v, 255)])
    n = plate.shape[0] + 2 * pad
    inside = np.zeros((n, n), bool)
    inside[pad:-pad, pad:-pad] = True
    d = distance_transform_edt(~inside) / cell                              # Zellen bis zur Platte
    g = np.where(inside, 0, q["light_value"] * np.exp(-d / q["glow_decay_cells"]) * (d <= q["glow_cells"]))
    out = np.zeros((n, n, 4), np.uint8)
    out[..., :3] = 255
    out[..., 3] = np.round(g * 255)
    v = np.round(plate * 255).astype(np.uint8)
    out[pad:-pad, pad:-pad] = np.dstack([v, v, v, np.full_like(v, 255)])
    return out


def qr_reads(img, url):
    """Dekodiert wie kickoff.check_qr: 4 Modulgroessen, mindestens 2 muessen lesen (OpenCV ist launisch)."""
    import cv2
    h, w = img.shape[:2]
    hits = 0
    for k in (0.5, 0.625, 1.0, 2.0):                                         # 4/5/8/16 px je Modul bei 8-px-Modulen
        small = cv2.resize(np.ascontiguousarray(img[..., 2::-1]), (round(w * k), round(h * k)), interpolation=cv2.INTER_AREA)
        hits += cv2.QRCodeDetector().detectAndDecode(small)[0] == url
    return hits


def cmd_qr(cfg, url=None):
    q, out = cfg["qr"], OUT / "elements"
    url = url or q["url"]
    out.mkdir(parents=True, exist_ok=True)
    slug = "telegram" if url == q["url"] else "".join(ch for ch in url.split("//")[-1] if ch.isalnum())[:24]
    bad = []
    for on_paper, suffix in ((False, ""), (True, "_paper")):
        el = qr_element(q, url, on_paper)
        Image.fromarray(el).save(out / f"qr_{slug}{suffix}.png")
        a = el.astype(np.float32) / 255
        pad = np.zeros((el.shape[0] + 64, el.shape[1] + 64, 3), np.float32)
        pad[32:-32, 32:-32] = a[..., :3] * a[..., 3:]                            # ueber Grund (Wert 0) komponiert
        group = [p for p in cfg["lens"]["order"] if paper(p) == on_paper]
        miss = [p for p in group if qr_reads(lens(pad, p, cfg["lens"]["cell_px"])[..., :3], url) < 2]
        bad += miss
        print(f"QR{suffix or ' dunkel'} {url}: {el.shape[1]} px, liest nach Lens in {len(group) - len(miss)}/{len(group)}"
              f" Colorways ({' '.join(group)})" + (f", NICHT: {miss}" if miss else ""))
    return not bad


def wall_element(word, w, h, lead_frac, margin):
    """Wortwand: Begriff in Zeilen auf voller Satzbreite, weiss auf Schwarz (deckend). In Resolve ueber einer Spark-Blende
    mit Composite Mode Multiply = Wortwand im Stern (Kick-off-Ende)."""
    f = S.font("ClashDisplay-Variable.ttf", 400, "Bold")
    word = word.upper().replace(" ", "  ")                                   # T2: Wortabstand doppelt
    cap0 = f.getbbox("H")[3] - f.getbbox("H")[1]
    size = 400 * (w - 2 * margin) / f.getlength(word)
    f = S.font("ClashDisplay-Variable.ttf", int(size), "Bold")
    cap = cap0 * size / 400
    lead = cap * lead_frac
    rows = max(1, int((h - 2 * margin - cap) // lead) + 1)
    y0 = (h - (cap + (rows - 1) * lead)) / 2 + cap
    im = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(im)
    for r in range(rows):
        dr.text((w / 2, y0 + r * lead), word, 255, font=f, anchor="ms")
    return np.array(im)


def cmd_wall(cfg, word):
    out = OUT / "elements"
    out.mkdir(parents=True, exist_ok=True)
    for fmt, (w, h) in cfg["elements"]["formats"].items():
        a = wall_element(word, w, h, cfg["wall"]["lead_frac"], cfg["wall"]["margin_px"])
        Image.fromarray(a).save(out / f"wall_{word.lower().replace(' ', '_')}_{fmt}.png")
    print(f"Wortwand '{word}' -> {out}/wall_*")


# ---------------------------------------------------------------- Brand: Colorway-Bogen, Lens-Testbild

def testchart(w=1080, h=1920):
    """Graukeil (stetig), 6 exakte Stufen, Kreis mit weicher Kante: zeigt Dither, flache Stufen und Kanten-Schnapp."""
    img = np.zeros((h, w), np.float32)
    img[: h // 3] = np.linspace(0, 1, w)[None, :]
    for k in range(6):
        img[h // 3: h // 2, k * w // 6:(k + 1) * w // 6] = k / 5
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx - w / 2, yy - 0.75 * h)
    img[h // 2:] = np.clip(0.35 * w - r, 0, 1)[h // 2:]                       # weiche Kante (1 px), Schnapp-Test
    return img


def cmd_brand(cfg):
    out = OUT / "brand"
    out.mkdir(parents=True, exist_ok=True)
    order = cfg["lens"]["order"]
    cw, rh = 96, 64
    im = Image.new("RGB", (cw * 6 + 360, rh * len(order)), "white")
    dr = ImageDraw.Draw(im)
    f = S.font("DepartureMono-Regular.otf", 22)
    for i, p in enumerate(order):
        for k, c in enumerate(pal6(p)):
            dr.rectangle([k * cw, i * rh, (k + 1) * cw - 1, (i + 1) * rh - 1], tuple(int(x) for x in c))
        dr.text((cw * 6 + 16, i * rh + 20), name(p), "black", font=f)
    im.save(out / "colorways.png")
    t = testchart()
    Image.fromarray(np.round(t * 255).astype(np.uint8)).save(out / "lens_testchart.png")
    p = cfg["resolve"]["default_colorway"]
    Image.fromarray(lens(np.repeat(t[..., None], 3, 2), p, cfg["lens"]["cell_px"])).save(out / f"lens_testchart_ref_{p}.png")
    gt = glow_testchart()
    Image.fromarray(np.round(gt * 255).astype(np.uint8)).save(out / "glow_testchart.png")
    print(f"Brand -> {out}")


def cmd_sheet(cfg, code=None):
    """Standbilder aller Elemente durch die Lens (numpy-Referenz), ~10 s: erst ansehen, dann `elements` rendern."""
    e, cell = cfg["elements"], cfg["lens"]["cell_px"]
    code = code or cfg["resolve"]["default_colorway"]
    w, h = e["formats"]["9x16"]
    cov = list(cover_frames(e, w, h))
    import flow
    fst = tomllib.loads(flow.CONFIG.read_text())["style"]
    tun = lambda ph: rgba(tunnel_frame(e, ph, w, h) / 255, np.ones((h, w)))
    tiles = [("spin S2", next(spin_frames(e))), ("nest S7", next(nest_frames(e))), ("tunnel 0", tun(0)),
             ("tunnel 0.5", tun(0.5)),
             ("cover 1/3", cov[len(cov) // 3]), ("cover 2/3", cov[2 * len(cov) // 3]),
             *[(f"flow {s}", rgba(flow.field(w, h, 0, e["flow_loop_s"], -60.0, cell=1, **fst[s]), np.ones((h, w))))
               for s in e["flow_styles"]],
             ("wordmark", wordmark(1080)), ("logo", logo(1080))]
    # Kick-off-Effekte: Glow (Schweif um die Bildmitte), gluehender QR, Wortwand im Stern (Multiply ueber der Blende)
    g = glow(glow_testchart(w, h), 0.5, 0.42, 0.9, 0.85, cell)
    tiles.append(("glow", rgba(g, np.ones((h, w)))))
    qe = qr_element(cfg["qr"], cfg["qr"]["url"]).astype(np.float32) / 255
    tiles.append(("qr glow", rgba(qe[..., 0] * qe[..., 3], np.ones(qe.shape[:2]))))
    wall = wall_element("MAKER NIGHT", w, h, cfg["wall"]["lead_frac"], cfg["wall"]["margin_px"]) / 255
    tiles.append(("wall x cover", rgba(wall * (cov[2 * len(cov) // 3][..., 3] / 255), np.ones((h, w)))))
    H = 480
    row = []
    for label, im in tiles:
        a = im.astype(np.float32) / 255
        px = lens(a[..., :3], code, cell, a[..., 3])
        t = Image.fromarray(px).resize((round(px.shape[1] * H / px.shape[0]), H), Image.NEAREST)
        ImageDraw.Draw(t).text((8, 8), label, (255, 255, 255), font=S.font("DepartureMono-Regular.otf", 22))
        row.append(t)
    sheet = Image.new("RGB", (sum(t.width + 8 for t in row), H), "black")
    x = 0
    for t in row:
        sheet.paste(t, (x, 0))
        x += t.width + 8
    o = OUT / f"sheet_{code}.png"
    o.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(o)
    print(o)
    return o


def cmd_look(cfg, src, code):
    a = np.asarray(Image.open(src).convert("RGBA"), np.float32) / 255
    o = OUT / f"look_{Path(src).stem}_{code}.png"
    o.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(lens(a[..., :3], code, cfg["lens"]["cell_px"], a[..., 3])).save(o)
    print(o)
    return o


# ---------------------------------------------------------------- Sound

def chip(freqs, step_s, duty=0.5, decay_s=None, sr=48000):
    """Pulswelle (NES-Art) ueber eine Tonfolge, Lautstaerke in 16 harten Stufen wie der Chip. freqs: Hz je Schritt."""
    n = int(step_s * sr)
    t = np.arange(n) / sr
    env = np.round((np.exp(-t / decay_s) if decay_s else np.ones(n)) * 15) / 15
    return np.concatenate([np.where((t * f) % 1 < duty, 1.0, -1.0) * env for f in freqs])


def fade_end(x, sr, sec=0.025):
    """Linear auf 0 in den letzten 25 ms: kein Klick, wenn ein Stem im Schnitt endet."""
    n = int(sec * sr)
    x = x.copy()
    x[-n:] *= np.linspace(1, 0, n)[:, None]
    return x


def st2(x):
    return np.stack([x, x], 1) if x.ndim == 1 else x


def sounds(sr, bpm):
    """Stems aus den Instrumenten von makernight_audio (Rezept im Skill) + Chiptune fuer die Zumo-Sprites."""
    import makernight_audio as A
    assert A.SR == sr, "makernight_audio rechnet mit 48 kHz"
    bar = 4 * 60 / bpm

    def rev(x, sec=1.8):
        y = np.vstack([st2(x), np.zeros((int(sec * sr), 2))])          # Platz fuer die Hallfahne
        return y + 0.35 * A.reverb(y, sec)

    def layer(*parts):
        x = np.zeros(max(len(p) for _, p in parts))
        for g, p in parts:
            x[: len(p)] += g * p
        return x

    t2 = np.arange(int(2 * bar * sr)) / sr                                # Riser ueber 2 Takte, endet auf der Eins
    u = t2 / (2 * bar)
    riser = A.sweep_lp(A.noise(len(t2) / sr), lambda s: 300 * 25 ** (s / (2 * bar))) * u ** 2
    riser = riser + 0.25 * A.lp(2 * ((np.cumsum(110 * 8 ** u) / sr) % 1) - 1, 4000) * u ** 3
    w = 1.35
    tt = np.arange(int(w * sr)) / sr
    wh = A.sweep_lp(A.noise(w), lambda s: 500 + 3500 * (s / w) ** 2) * np.sin(np.pi * tt / w) ** 2
    pan = tt / w * np.pi / 2                                              # links -> rechts, Equal Power
    hz = A.hz
    stems = {
        "hit_boom": rev(A.boom()),
        "hit_impact": rev(layer((1.0, A.kick(1.1)), (0.5, A.clap()), (0.7, A.boom()))),
        "riser_2bar": riser,
        "reverse_cymbal": A.hp(A.noise(0.9), 3000)[::-1] * np.linspace(0, 1, int(0.9 * sr)) ** 3,
        "whoosh_lr": np.stack([wh * np.cos(pan), wh * np.sin(pan)], 1),
        "glass_ping": rev(A.bell(hz(93), 1.6, 0.6) + 0.3 * A.bell(hz(100), 1.6, 0.4)),
        "key_click": A.key_click(),
        "kick": A.kick(), "clap": A.clap(), "snare": A.snare(), "hat": A.hat(),
        "chip_blip": chip([hz(84)], 0.06, 0.25, 0.04),
        "chip_select": chip([hz(76), hz(83)], 0.05, 0.25),
        "chip_coin": chip([hz(83), hz(88)], 0.07, 0.5, 0.15),
        "chip_jump": chip(np.geomspace(hz(60), hz(84), 10), 0.012, 0.25),
        "chip_win": chip([hz(m) for m in (72, 76, 79, 84, 79, 84)], 0.09, 0.5, 0.2),
        "chip_ko": chip(np.geomspace(hz(79), hz(43), 14), 0.035, 0.5),
        "chip_push": A.lp(np.sign(A.noise(0.25)), 3000) * np.round(np.exp(-np.arange(int(0.25 * sr)) / sr / 0.08) * 15) / 15,
    }
    return {k: fade_end(st2(x), sr) for k, x in stems.items()}


def wav(path, x, sr, peak_db):
    """24-bit-WAV, Spitze auf peak_db (statisch: ein Stem behaelt seine Dynamik)."""
    x = st2(x)
    x = x / max(np.abs(x).max(), 1e-9) * 10 ** (peak_db / 20)
    i = np.round(np.clip(x, -1, 1) * (2 ** 23 - 1)).astype("<i4")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(3)
        f.setframerate(sr)
        f.writeframes(i.view(np.uint8).reshape(-1, 4)[:, :3].tobytes())


def cmd_sound(cfg):
    s, out = cfg["sound"], OUT / "sound"
    out.mkdir(parents=True, exist_ok=True)
    for k, x in sounds(s["sr"], s["bpm"]).items():
        wav(out / f"{k}.wav", x, s["sr"], s["peak_db"])
    mn = main_root() / "makernight" / "loop"                              # MN-Bett: gitignored Ausgabe von makernight_loop.py
    for f in ("loop_full.wav", "loop_bed.wav", "loop_bed_60s.wav"):
        if (mn / f).exists():
            shutil.copy2(mn / f, out / f"MN_{f}")
        else:
            print(f"  fehlt {f}: uv run -q --with numpy --with scipy python src/makernight_loop.py")
    print(f"Sound -> {out}")


# ---------------------------------------------------------------- Publish, Test

def cmd_publish(cfg):
    dst = Path(cfg["publish"]["dir"]).expanduser()
    if not dst.parent.is_dir():
        sys.exit(f"{dst.parent} fehlt (Nextcloud nicht gemountet?)")
    for sub in ("lens", "elements", "sound", "brand"):
        if (OUT / sub).is_dir():
            shutil.copytree(OUT / sub, dst / sub, dirs_exist_ok=True)
    print(f"publish -> {dst}")


def test(cfg):
    """Am fertigen Bild messen; jeder Teil schlaegt am injizierten Fehler an (Gegenprobe im Kommentar)."""
    ok = True
    cell = cfg["lens"]["cell_px"]
    rng = np.random.default_rng(3)
    # 1. Lens = styles.dither, wenn das Feld je Zelle konstant ist (Gegenprobe: Bayer transponiert -> ~40 % falsch)
    v = np.clip(rng.random((48, 27)) * 0.2 + np.linspace(0, 1, 27)[None, :] * 0.8, 0, 1)
    img = np.repeat(np.repeat(v, cell, 0), cell, 1)
    got = lens(np.repeat(img[..., None], 3, 2), "P11", cell, snap=False)[..., :3]
    bad = np.mean(np.any(got != pal6("P11")[S.dither(v, STEPS - 1, "bayer4", cell)], -1))
    print(f"  Lens = styles.dither: {bad:.4f} abweichend (Gate 0)")
    ok &= bad == 0
    # 2. Kanten-Schnapp: weicher Kreis -> fast nur Grund oder Tinte. Einzelne Zellen, deren Mitte genau auf dem 1-px-Saum
    #    liegt und deren Nachbarn beide innen/aussen sind, bleiben wie im Figma-Shader (Paritaet vor Perfektion).
    t = np.repeat(testchart()[960:, :, None], 3, 2)
    mid = lambda sn: np.mean(np.any(np.all(lens(t, "P11", cell, snap=sn)[..., :3].reshape(-1, 3)[:, None]
                                           == pal6("P11")[1:5][None], -1), -1))
    m1, m0 = mid(True), mid(False)
    print(f"  Kanten-Schnapp: {m1:.5f} Zwischenstufen am Kreis (Gate < 0.001; ohne Schnapp {m0:.5f})")
    ok &= m1 < 0.001 and m0 > 3 * m1
    # 3. DCTL: alle Colorways im Menue, Palette vollstaendig (Gegenprobe: 4-Stufen-Palette ungedoppelt -> Laenge falsch)
    src, n = dctl(cfg), len(cfg["lens"]["order"]) * STEPS * 3
    body = src.split(f"PAL[{n}] = {{")[1].split("}")[0] if f"PAL[{n}]" in src else ""
    ok &= body.count("f") == n and src.count("CW_") == len(cfg["lens"]["order"])
    print(f"  DCTL: {len(cfg['lens']['order'])} Colorways, PAL[{n}]")
    # 3b. Journey/Boil: Maker-Night-Set ab P1 alle 2 Bilder weiter (Gegenprobe: Set "alle" gaebe P1 P1 P5 P5 P8 P8 P12 ...
    #     erst ab Bild 6 anders; daher Kick-off-Set ab P11 pruefen, das P1 nie enthalten darf)
    mn = [lens_at(cfg, "P1", f, journey=2, jset=1)[0] for f in range(10)]
    ko = {lens_at(cfg, "P11", f, journey=1, jset=2)[0] for f in range(40)}
    bo = [lens_at(cfg, "P1", f, boil=3)[1] for f in range(12)]
    jb = mn == ["P1", "P1", "P5", "P5", "P8", "P8", "P12", "P12", "P1", "P1"] and not ko & {"P1", "P5", "P8", "P12"} \
        and len(set(bo)) == 4 and bo[0] == bo[2] != bo[3]
    print(f"  Journey/Boil: MN {mn[:8]}, Kick-off ohne Lila {not ko & {'P1', 'P5', 'P8', 'P12'}}, Boil {bo[::3]}")
    ok &= jb
    # 3c. Glow: nie dunkler als die Quelle, Schweif zeigt von der Mitte weg (Licht aussen neben dem Logo, innen nicht)
    gt = glow_testchart(270, 480)
    g = glow(gt, 0.5, 0.5, 0.6, 0.8, cell)
    away, toward = g[40:44, 135].max(), g[160:164, 135].max()            # ueber dem Logo (aussen) / zwischen Logo und Mitte
    print(f"  Glow: >= Quelle {bool((g >= gt - 1e-6).all())}, Schweif aussen {away:.2f} / innen {toward:.2f}")
    ok &= bool((g >= gt - 1e-6).all()) and away > 0.1
    # 4. Loops nahtlos: Spin nach 60 Grad deckungsgleich, Nest nach 2 Schritten gleich und nach 1 invertiert
    e = dict(cfg["elements"], spin_px=216)
    a0, a60 = (star_d(216, 216, 108, 108, e["spin_radius_frac"] * 216, r) < 1 for r in (0, 60))
    seam = np.mean(a0 != a60)
    print(f"  Spin-Naht: {seam:.4f} (Gate < 0.002)")
    ok &= seam < 0.002
    n0, n1, n2 = (tunnel_frame(e, ph, 216, 384) for ph in (0, 1, 2))
    nseam, ninv = np.mean(n0 != n2), np.mean(n0 == n1)
    print(f"  Tunnel-Naht: {nseam:.4f}, Schritt 1 nicht invertiert: {ninv:.4f} (Gates < 0.002)")
    ok &= nseam < 0.002 and ninv < 0.002
    # 5. Sound: endlich, Ende still (letzte ms <= 5 % der Spitze; Gegenprobe ohne fade_end: kick 14 %)
    for k, x in sounds(cfg["sound"]["sr"], cfg["sound"]["bpm"]).items():
        if not np.isfinite(x).all() or np.abs(x[-48:]).max() > 0.05 * np.abs(x).max():
            print(f"  Sound {k}: Ende nicht still oder NaN")
            ok = False
    print("test ok" if ok else "TEST ROT")
    return ok


def main():
    cfg = load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "lens":
        cmd_lens(cfg)
    elif cmd == "elements":
        cmd_elements(cfg)
    elif cmd == "sound":
        cmd_sound(cfg)
    elif cmd == "brand":
        cmd_brand(cfg)
    elif cmd == "qr":
        sys.exit(0 if cmd_qr(cfg, sys.argv[2] if len(sys.argv) > 2 else None) else 1)
    elif cmd == "wall":
        cmd_wall(cfg, " ".join(sys.argv[2:]) or "MAKER NIGHT")
    elif cmd == "sheet":
        cmd_sheet(cfg, sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "look":
        subprocess.run(["open", str(cmd_look(cfg, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "P1"))])
    elif cmd == "all":
        for f in (cmd_lens, cmd_brand, cmd_sound, cmd_elements):
            f(cfg)
    elif cmd == "publish":
        cmd_publish(cfg)
    elif cmd == "test":
        sys.exit(0 if test(cfg) else 1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
