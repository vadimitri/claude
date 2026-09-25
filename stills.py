#!/usr/bin/env python3
"""SPARK Stills: Standbilder (PNG mit Alpha) fuer Figma, Poster, Social, 16:9.

Nutzt dieselben Bausteine wie motionpack.py (Spark-Stern, Raster, Stile). Jedes Design ist ein Feld
v(x, y) in [0, 1]; der Stil macht daraus Pixel. Koordinaten: g.cx/g.cy, Mitte = 0, kurze Seite = 1.

  uv run --with numpy --with pillow python stills.py                  # alles (~10 min)
  uv run --with numpy --with pillow python stills.py one spark_echo 16x9 dots
"""
import math
import os
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

from motionpack import STAR, Grid, Style, ss

ROOT = os.path.dirname(os.path.abspath(__file__))
FORMATS = {"poster_a3": (3508, 4961), "16x9": (3840, 2160), "9x16": (1080, 1920),
           "4x5": (1080, 1350), "1x1": (1080, 1080)}
STYLES = ("dots", "fine", "grain", "halftone", "solid")
COLORS = {"white": (255, 255, 255), "navy": (0x1A, 0x3A, 0x6E)}


class StillStyle(Style):
    """Style plus 'grain': Zufalls-Schwelle statt Bayer, feines Korn wie im Spark-Wallpaper."""
    def __init__(self, style, W, H):
        super().__init__("fine" if style == "grain" else style, W, H)
        if style == "grain":
            self.cell = max(1, round(8 * min(W, H) / 1080) // 3)
            gw, gh = math.ceil(W / self.cell), math.ceil(H / self.cell)
            self.grid = Grid(gw, gh)
            self.thr = np.random.default_rng(1).random((gh, gw))


# ---------------------------------------------------------------- Bausteine

# Stern-Profil glatt und interpoliert: bei Postergroesse sieht man sonst die 1-Grad-Stufen
_S = np.mean([np.roll(STAR, k) for k in range(-2, 3)], axis=0)
_DEG = np.arange(361)
_PROF = np.append(_S, _S[0])
_DPROF = np.gradient(np.concatenate([_S[-1:], _S, _S[:2]]))[1:-1] * 180 / np.pi   # dR/dtheta pro Radiant


def _angle(dx, dy, rot):
    return (np.degrees(np.arctan2(dy, dx)) - rot) % 360


def star_d(dx, dy, size, rot=0.0):
    """Stern-Abstand: < 1 innerhalb eines Spark-Sterns mit Spitzenradius size (rot in Grad, auch Array)."""
    return np.hypot(dx, dy) / (np.interp(_angle(dx, dy, rot), _DEG, _PROF) * size + 1e-9)


def star_line(g, dx, dy, size, w, rot=0.0):
    """Kontur eines Sterns, w Rasterzellen breit. Abstand = f/|grad f|, damit Linien ueberall gleich dick sind."""
    a, r = _angle(dx, dy, rot), np.hypot(dx, dy)
    f = r - np.interp(a, _DEG, _PROF) * size
    slope = size * np.interp(a, _DEG, _DPROF) / np.maximum(r, 1e-6)
    return line(f / np.sqrt(1 + slope ** 2) / px(g), w)


def fill(d, e=0.04):
    return np.clip((1 - d) / e + 0.5, 0, 1)


def px(g):
    return 1 / min(g.w, g.h)                     # eine Rasterzelle in cx-Einheiten


def line(dist, w):
    return np.clip((w - np.abs(dist)) * 4 + 0.5, 0, 1)   # dist, w in Rasterzellen


def h(ix, iy, salt=0):
    """Deterministischer Zufall pro Kachel."""
    return np.abs(np.sin(ix * 12.9898 + iy * 78.233 + salt * 37.719) * 43758.5453) % 1


def cells(g, n, brick=False):
    """n Kacheln ueber die kurze Seite -> Index, lokale Koordinate (-0.5..0.5), Kachelmitte."""
    X, Y = g.cx * n, g.cy * n
    off = 0.5 * (np.floor(Y) % 2) if brick else 0
    X = X + off
    ix, iy = np.floor(X), np.floor(Y)
    return ix, iy, X - ix - 0.5, Y - iy - 0.5, (ix + 0.5 - off) / n, (iy + 0.5) / n


def long_axis(g, xc, yc):
    """0..1 entlang der langen Seite (unten/rechts = 1)."""
    a, ref = (yc, g.cy) if g.portrait else (xc, g.cx)
    return np.clip((a - ref.min()) / (ref.max() - ref.min()), 0, 1)


def gap(g, u, v, n, cells_=1.0):
    """Fuge zwischen Kacheln, cells_ Rasterzellen breit."""
    return ((0.5 - np.maximum(np.abs(u), np.abs(v))) / n > cells_ * px(g) / 2).astype(np.float32)


def xor(*fields):
    return (sum((f > 0.5).astype(int) for f in fields) % 2).astype(np.float32)


# ---------------------------------------------------------------- Spark-Designs

def echo(x0=0.0, y0=0.0, size=0.3, rings=6, step=1.28):
    def f(g):
        dx, dy = g.cx - x0, g.cy - y0
        v = fill(star_d(dx, dy, size))
        for k in range(1, rings + 1):
            s = size * step ** k
            w = max(1.0, 3.5 - 0.45 * k)
            v = np.maximum(v, star_line(g, dx, dy, s, w))
        return v
    return f


def contour(n=9, fade=False):
    def f(g):
        d = star_d(g.cx, g.cy, 1.0)
        r = np.hypot(g.cx, g.cy)
        dist = (np.abs((d * n + 0.5) % 1 - 0.5) / n) * r / (d + 1e-9) / px(g)
        w = 1.2 + (3.5 * np.clip(1 - d, 0, 1) if fade else 0.4)
        return line(dist, w)
    return f


def spiro(n=12):
    def f(g):
        v = 0
        for k in range(n):
            s = 0.46 * 0.93 ** k
            v = np.maximum(v, star_line(g, g.cx, g.cy, s, 1.4, 5 * k))
        return v
    return f


def burst(y0=0.0, size=0.2, rays=12):
    def f(g):
        dx, dy = g.cx, g.cy - y0
        th = np.arctan2(dy, dx) + np.pi / 2               # 0 = nach oben (Spitze des Sterns)
        r = np.hypot(dx, dy)
        long_ray = np.cos(rays / 2 * th) > 0               # jeder zweite Strahl laenger
        wedge = np.cos(rays * th) > 0.82
        reach = np.where(long_ray, 1.6, 0.9) * size * 2.2
        ray = wedge * (r > size * 1.25) * (r < reach)
        return np.maximum(fill(star_d(dx, dy, size)), ray.astype(np.float32))
    return f


def pattern(n=6, brick=False, size=lambda g, ix, iy, xc, yc: 0.36, rot=lambda g, ix, iy: 0.0):
    def f(g):
        ix, iy, u, v, xc, yc = cells(g, n, brick)
        return fill(star_d(u, v, size(g, ix, iy, xc, yc), rot(g, ix, iy)), 0.08)
    return f


def scatter(seed, n=45, lo=0.02, hi=0.13, dust=0.0):
    def f(g):
        rng = np.random.default_rng(seed)
        W, H = g.cx.max(), g.cy.max()
        v = (g.H < dust).astype(np.float32)
        for _ in range(int(n * 4 * W * H)):
            x, y = rng.uniform(-W, W), rng.uniform(-H, H)
            s = lo * (hi / lo) ** rng.random() ** 1.8          # viele kleine, wenige grosse
            v = np.maximum(v, fill(star_d(g.cx - x, g.cy - y, s, rng.uniform(0, 60)), 0.1))
        return v
    return f


def orbit(g):
    v = fill(star_d(g.cx, g.cy, 0.16))
    for k in range(12):
        a = 2 * np.pi * k / 12 - np.pi / 2
        s = 0.06 if k % 2 == 0 else 0.034
        v = np.maximum(v, fill(star_d(g.cx - 0.34 * np.cos(a), g.cy - 0.34 * np.sin(a), s, 30 * (k % 2)), 0.1))
    return v


def frame(g, n=11):
    ix, iy, u, v, xc, yc = cells(g, n)
    edge = np.minimum(g.cx.max() - np.abs(xc), g.cy.max() - np.abs(yc)) * n     # in Kacheln
    s = np.where(edge < 1, 0.4, np.where(edge < 2, 0.16, 0))
    return fill(star_d(u, v, s, 30 * ((ix + iy) % 2)), 0.08)


def star_of_stars(g, n=13):
    ix, iy, u, v, xc, yc = cells(g, n)
    big = star_d(xc, yc, 0.5)
    return fill(star_d(u, v, 0.48 * np.clip(1.3 - big, 0, 1) ** 0.5), 0.08)


def pixel_star(n=16, dissolve=False):
    def f(g):
        ix, iy, u, v, xc, yc = cells(g, n)
        d = star_d(xc, yc, 0.44)
        on = d < 1
        if dissolve:
            on = on | (h(ix, iy, 3) < 0.85 * np.exp(-(d - 1) * 2.2))
        return on * gap(g, u, v, n)
    return f


def glitch(g):
    band = np.floor(g.ny * 40)
    shift = np.where(h(band, 0, 5) < 0.4, (h(band, 1, 9) - 0.5) * 0.35, 0)
    return fill(star_d(g.cx - shift, g.cy, 0.42))


def shade(g):                                        # dicht in der Mitte, luftig zu den Spitzen
    d = star_d(g.cx, g.cy, 0.42)
    return fill(d) * (1 - 0.85 * np.clip(d, 0, 1) ** 1.6)


def glow(g):
    d = star_d(g.cx, g.cy, 0.3)
    return np.maximum(fill(d), 0.85 * np.exp(-np.maximum(d - 1, 0) * 1.6) * (d >= 1))


def grainy(g):                                       # wie spark_wallpaper: weicher Rand, dunkler Kern
    d = star_d(g.cx, g.cy, 0.42)
    return np.clip((1.12 - d) / 0.4, 0, 1) ** 0.8


def graph(g, n=12, stars=False):
    X, Y = g.cx * n, g.cy * n
    fx, fy = np.abs((X + 0.5) % 1 - 0.5), np.abs((Y + 0.5) % 1 - 0.5)
    v = np.maximum(line(fx / n / px(g), 0.9), line(fy / n / px(g), 0.9)) * 0.55
    if stars:
        ix, iy = np.round(X), np.round(Y)
        s = np.where(h(ix, iy, 7) < 0.22, 0.32, 0)
        v = np.maximum(v, fill(star_d(X - ix, Y - iy, s), 0.08))
    return v


SPARK = {
    "spark_mark":        lambda g: fill(star_d(g.cx, g.cy, 0.4)),
    "spark_outline":     lambda g: np.maximum(star_line(g, g.cx, g.cy, 0.4, 4), star_line(g, g.cx, g.cy, 0.32, 1.4)),
    "spark_shade":       shade,
    "spark_glow":        glow,
    "spark_grainy":      grainy,
    "spark_echo":        echo(),
    "spark_echo_corner": lambda g: echo(g.cx.max(), g.cy.max(), 0.45, 8, 1.3)(g),
    "spark_echo_rise":   lambda g: echo(0, g.cy.max(), 0.35, 8, 1.3)(g),
    "spark_contour":     contour(6),
    "spark_contour_bold": contour(7, fade=True),
    "spark_spiro":       spiro(),
    "spark_burst":       burst(),
    "spark_burst_rise":  lambda g: burst(g.cy.max() * 0.72, 0.22)(g),
    "spark_nest":        lambda g: xor(*(fill(star_d(g.cx, g.cy, s, 30 * k)) for k, s in
                                         enumerate((0.48, 0.38, 0.29, 0.2, 0.11)))),
    "spark_twelve":      lambda g: xor(fill(star_d(g.cx, g.cy, 0.42)), fill(star_d(g.cx, g.cy, 0.42, 30))),
    "spark_duo":         lambda g: xor(fill(star_d(g.cx - 0.11, g.cy, 0.34)), fill(star_d(g.cx + 0.11, g.cy, 0.34))),
    "spark_glitch":      glitch,
    "spark_orbit":       orbit,
    "spark_frame":       frame,
    "spark_of_sparks":   star_of_stars,
    "spark_pixel":       pixel_star(),
    "spark_pixel_fine":  pixel_star(28),
    "spark_pixel_dissolve": pixel_star(22, dissolve=True),
    "spark_pattern":     pattern(),
    "spark_pattern_dense": pattern(12, brick=True, rot=lambda g, ix, iy: 30 * (iy % 2)),
    "spark_pattern_mixed": pattern(8, brick=True, size=lambda g, ix, iy, xc, yc: np.where(h(ix, iy) < 0.5, 0.42, 0.17),
                                   rot=lambda g, ix, iy: 30 * (h(ix, iy, 1) < 0.5)),
    "spark_pattern_grow": pattern(10, size=lambda g, ix, iy, xc, yc: 0.03 + 0.43 * long_axis(g, xc, yc) ** 1.3),
    "spark_pattern_wave": pattern(12, size=lambda g, ix, iy, xc, yc:
                                  0.06 + 0.38 * (0.5 + 0.5 * np.cos(2 * np.pi * 2.2 * np.hypot(xc, yc)))),
    "spark_pattern_hole": pattern(12, size=lambda g, ix, iy, xc, yc:
                                  0.44 * ss((star_d(xc, yc, 0.45) - 0.9) / 1.2)),   # Stern-Loch fuer Text/Logo
    "spark_scatter_1":   scatter(1),
    "spark_scatter_2":   scatter(2, 30, 0.03, 0.2),
    "spark_scatter_3":   scatter(3, 90, 0.015, 0.07),
    "spark_constellation": scatter(4, 25, 0.012, 0.05, dust=0.006),
    "spark_graph":       lambda g: graph(g, stars=True),
}


# ---------------------------------------------------------------- Kachel-Designs

def tiles(n, rule, gap_cells=1.0):
    def f(g):
        ix, iy, u, v, xc, yc = cells(g, n)
        return rule(g, ix, iy, xc, yc) * gap(g, u, v, n, gap_cells)
    return f


def quadtree(g, levels=(3, 6, 12, 24, 48)):
    out = np.zeros_like(g.cx)
    done = np.zeros(g.cx.shape, bool)
    for i, n in enumerate(levels):
        ix, iy, u, v, _, _ = cells(g, n)
        split = (h(ix, iy, i) < 0.55) & (i < len(levels) - 1)
        here = ~done & ~split
        out[here] = ((h(ix, iy, i + 50) < 0.45) * gap(g, u, v, n))[here]
        done |= here
    return out


def edge01(g, xc, yc):                              # 0 am Rand .. 1 in der Mitte
    return np.minimum(1 - np.abs(xc) / g.cx.max(), 1 - np.abs(yc) / g.cy.max())


TILES = {
    "tiles_scatter":     tiles(8, lambda g, ix, iy, xc, yc: h(ix, iy) < 0.35),
    "tiles_scatter_fine": tiles(20, lambda g, ix, iy, xc, yc: h(ix, iy) < 0.3),
    "tiles_scatter_micro": tiles(48, lambda g, ix, iy, xc, yc: h(ix, iy) < 0.25),
    "tiles_ramp":        tiles(16, lambda g, ix, iy, xc, yc: h(ix, iy) < ss(long_axis(g, xc, yc) * 1.4 - 0.25)),
    "tiles_ramp_fine":   tiles(36, lambda g, ix, iy, xc, yc: h(ix, iy) < ss(long_axis(g, xc, yc) * 1.4 - 0.25)),
    "tiles_frame":       tiles(18, lambda g, ix, iy, xc, yc: h(ix, iy) < ss(1 - edge01(g, xc, yc) * 3.2)),
    "tiles_corner":      tiles(16, lambda g, ix, iy, xc, yc: h(ix, iy) <
                               ss(1.5 - 1.6 * np.hypot(xc - g.cx.max(), yc - g.cy.max()) / np.hypot(g.cx.max(), g.cy.max()))),
    "tiles_band":        tiles(24, lambda g, ix, iy, xc, yc: h(ix, iy) < np.exp(-(yc / 0.14) ** 2)),
    "tiles_center":      tiles(20, lambda g, ix, iy, xc, yc: h(ix, iy) < ss(1.2 - 2.4 * np.hypot(xc, yc))),
    "tiles_mosaic":      tiles(8, lambda g, ix, iy, xc, yc: np.floor(h(ix, iy) * 5) / 4, 0),
    "tiles_mosaic_ramp": tiles(14, lambda g, ix, iy, xc, yc:
                               np.clip(np.round((long_axis(g, xc, yc) + (h(ix, iy) - 0.5) * 0.5) * 4) / 4, 0, 1), 0),
    "tiles_quadtree":    quadtree,
    "graph_grid":        lambda g: graph(g),
    "graph_grid_fine":   lambda g: graph(g, 24),
    "dither_ramp":       lambda g: g.L,
    "dither_radial":     lambda g: np.clip(1.1 - 1.2 * g.R, 0, 1),
}

DESIGNS = {**SPARK, **TILES}
THIN = {"spark_spiro", "graph_grid_fine"}      # feine Linien: im groben Halftone nur Matsch
GRAY = {"spark_shade", "spark_glow", "spark_grainy", "tiles_mosaic", "tiles_mosaic_ramp",
        "dither_ramp", "dither_radial"}          # Grauwerte: in 'solid' sinnlos, dort weggelassen


# ---------------------------------------------------------------- Ausgabe

def save(alpha, path, rgb):
    px_ = np.empty(alpha.shape + (4,), np.uint8)
    px_[..., :3] = rgb
    px_[..., 3] = alpha
    Image.fromarray(px_, "RGBA").save(path, compress_level=6)


def job(spec, names=None):
    fmt, style = spec
    W, H = FORMATS[fmt]
    st = StillStyle(style, W, H)
    for name in names or DESIGNS:
        if (style == "solid" and name in GRAY) or (style == "halftone" and name in THIN):
            continue
        a = st.render(DESIGNS[name](st.grid))
        for color, rgb in COLORS.items():
            d = f"{ROOT}/stills/{fmt}/{color}"
            os.makedirs(d, exist_ok=True)
            save(a, f"{d}/{name}__{style}.png", rgb)
    return spec


def gallery():
    """stills.html: alle Designs, Format / Stil / Hintergrund umschaltbar."""
    import json
    groups = {"Spark": list(SPARK), "Kacheln, Raster, Verlaeufe": list(TILES)}
    html = """<!doctype html><html lang="de"><head><meta charset="utf-8"><title>SPARK Stills</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--bg:#0b0b0b;--fg:#f2efe6;--mut:#8a877f;--line:#262626}
@media (prefers-color-scheme:light){:root{--bg:#f2efe6;--fg:#141414;--mut:#6b675e;--line:#d8d3c6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 ui-monospace,Menlo,monospace;padding:24px 16px}
h1{font-size:28px;margin:0 0 4px}p{color:var(--mut);margin:0 0 16px;max-width:75ch}
nav{position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:1;display:grid;gap:6px}
nav div{display:flex;flex-wrap:wrap;gap:6px}
button{font:inherit;background:none;color:var(--fg);border:1px solid var(--line);padding:5px 10px;cursor:pointer}
button[aria-pressed=true]{background:var(--fg);color:var(--bg)}
h2{font-size:15px;margin:28px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--w,220px),1fr));gap:14px}
figure{margin:0}img{width:100%;display:block}
figcaption{margin-top:6px;font-size:12px;color:var(--mut);word-break:break-all}
</style></head><body><h1>SPARK Stills</h1>
<p>PNG mit Alpha in <code>stills/&lt;format&gt;/&lt;farbe&gt;/&lt;name&gt;__&lt;stil&gt;.png</code>.
In Figma reinziehen; umfärben: farbiges Rechteck drüber, beide auswählen, PNG unten, <b>Use as mask</b>.</p>
<nav id="nav"></nav><main id="main"></main><script>
const G=__GROUPS__, GRAY=__GRAY__, THIN=__THIN__, OPT={fmt:__FMTS__,style:__STYLES__,bg:["navy","white","black","paper"]};
const BG={navy:["#1A3A6E","white"],white:["#fff","navy"],black:["#000","white"],paper:["#F2EFE6","navy"]};
let st={fmt:"16x9",style:"dots",bg:"navy"};try{Object.assign(st,JSON.parse(localStorage.getItem("stills")||"{}"))}catch(e){}
function draw(){
 document.getElementById("nav").innerHTML=Object.entries(OPT).map(([k,vs])=>"<div>"+vs.map(v=>
  `<button data-k="${k}" data-v="${v}" aria-pressed="${st[k]===v}">${v}</button>`).join("")+"</div>").join("");
 const [bg,col]=BG[st.bg], w=st.fmt==="16x9"?"300px":"180px";
 document.getElementById("main").innerHTML=Object.entries(G).map(([g,ns])=>`<h2>${g}</h2><div class="grid" style="--w:${w}">`+
  ns.filter(n=>!(st.style==="solid"&&GRAY.includes(n))&&!(st.style==="halftone"&&THIN.includes(n))).map(n=>`<figure><img loading="lazy" style="background:${bg}"
  src="stills/${st.fmt}/${col}/${n}__${st.style}.png" alt="${n}"><figcaption>${n}</figcaption></figure>`).join("")+"</div>").join("");
}
document.getElementById("nav").onclick=e=>{const b=e.target.dataset;if(!b.k)return;st[b.k]=b.v;
 try{localStorage.setItem("stills",JSON.stringify(st))}catch(e){};draw()};draw();
</script></body></html>"""
    for k, v in {"__GROUPS__": groups, "__GRAY__": sorted(GRAY), "__THIN__": sorted(THIN), "__FMTS__": list(FORMATS), "__STYLES__": list(STYLES)}.items():
        html = html.replace(k, json.dumps(v))
    open(f"{ROOT}/stills.html", "w", encoding="utf-8").write(html)


def check():
    st = StillStyle("dots", *FORMATS["1x1"])
    for name, fn in DESIGNS.items():
        v = fn(st.grid)
        assert v.shape == st.grid.cx.shape and np.isfinite(v).all(), name
        cov = np.clip(v, 0, 1).mean()
        assert 0.005 < cov < 0.995, (name, cov)          # weder leer noch voll
    print("check ok", len(DESIGNS), "designs")


if __name__ == "__main__":
    check()
    if sys.argv[1:2] == ["check"]:
        sys.exit()
    gallery()
    if sys.argv[1:2] == ["one"]:                          # one <name> <format> <style>
        job((sys.argv[3], sys.argv[4]), [sys.argv[2]])
        sys.exit()
    specs = sorted(((f, s) for f in FORMATS for s in STYLES), key=lambda x: x[0] != "poster_a3")
    with Pool(4) as pool:                                 # ponytail: 4 wegen RAM (Poster-Halftone ~1 GB)
        for i, spec in enumerate(pool.imap_unordered(job, specs), 1):
            print(f"{i}/{len(specs)} {spec}", flush=True)
