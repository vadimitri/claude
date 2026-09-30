"""MacBook-Pro-Wallpaper 3456x2234: Spark-Stern mittig, Feld -> Bayer 4x4 (D3), R3 = 4 px. -> wallpaper/"""
import os, sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
sys.path.insert(0, os.path.dirname(__file__))
from styles import star_r, bayer
import styles

PX = 4
BLUES = {  # zusaetzliche Blau-Rampen (dunkel -> hell)
    "abyss": ["#01040C", "#03113A", "#062A80", "#0B5CE0", "#48B6FF", "#E6F8FF"],
    "ikb": ["#000418", "#000F5C", "#002FA7", "#2F5BFF", "#9DB4FF", "#F4F6FF"],
    "glacier": ["#020A12", "#0A2A3F", "#0F5C7A", "#26A6C9", "#9BE7F5", "#F2FEFF"],
    "neon": ["#02010A", "#0A0A4A", "#1B1BD6", "#00A2FF", "#00FFE0", "#F0FFFD"],
    "dusk": ["#05030F", "#101A4A", "#1F3F9E", "#4C7BFF", "#FF9A5C", "#FFF1E0"],
}

def hexpal(p):
    return np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in (BLUES.get(p) or styles.PALS[p])], np.float32)

def setup(WW, HH, scale=0.36):
    global W, H, w, h, x, y, cx, cy, dx, dy, rr, R, B, th, edge
    W, H = WW, HH
    w, h = W // PX, -(-H // PX)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    dx, dy = x - cx, y - cy
    rr = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    R = scale * min(w, h)
    B = np.tile(bayer(4), (h // 4 + 1, w // 4 + 1))[:h, :w]
    edge = rr / np.hypot(cx, cy)            # 0 Mitte -> 1 Ecke

def bg(a=0.42):  # Gradient bis in die Ecken, keine flachen Flaechen
    return a * (1 - edge) ** 1.3 + 0.03

def d(scale, rot=0.0):
    return rr / (star_r(dx, dy, rot) * R * scale)

def glut():      # S2: Stern als Lichtquelle, Gradient + Bloom
    s = np.clip(1 - d(1.0), 0, 1) ** 0.7
    return np.clip(np.maximum(bg(0.5), 0.85 * s + 0.6 * gaussian_filter((d(1) < 1) * 1.0, 40)), 0, 1)

def nest():      # S7: XOR-Nest, jede Ebene eigene Stufe
    par = sum((d(0.62 ** k, 12 * k) < 1) for k in range(-2, 7)) % 2
    k = np.floor(np.log(np.maximum(d(1), 1e-3)) / np.log(1 / 0.62))
    return np.clip(np.where(par, 0.95 - 0.35 * edge, bg(0.4)) + 0.08 * np.tanh(-k / 4), 0, 1)

def gegenlicht():  # S31: Sonnenfinsternis hinter dem Stern, Strahlen bis in die Ecken
    dd = d(1.0)
    rng = np.random.default_rng(3)
    a = np.linspace(-np.pi, np.pi, 2048, endpoint=False)
    ray = gaussian_filter(rng.random(2048), 3, mode="wrap") + 0.6 * gaussian_filter(rng.random(2048), 1, mode="wrap")
    ray = (ray - ray.min()) / np.ptp(ray)
    rays = np.interp(th, a, ray, period=2 * np.pi) ** 2.2
    out = np.maximum(dd - 1, 0)
    halo = np.exp(-out * 2.2)
    beams = rays * np.exp(-out * 0.55)                     # lange Strahlen
    tips = 0.5 * (np.cos(6 * (th - np.pi / 2)) * 0.5 + 0.5) ** 8 * np.exp(-out * 0.9)
    rim = np.exp(-np.abs(dd - 1) * 45)
    light = 0.8 * halo + 0.55 * beams + tips + bg(0.35)
    core = 0.02 + 0.14 * (1 - dd) ** 3                     # Silhouette: fast schwarz, zum Rand ein Hauch
    return np.clip(np.where(dd < 1, core, light) + 0.9 * rim, 0, 1)

def matrjoschka():  # S33: 4 Sterne mit Luft, aussen loest sich in Rauschen auf
    rng = np.random.default_rng(7)
    n = rng.random((h, w))
    v = np.full((h, w), 0.06)
    for i, sc in enumerate([1.25, 0.9, 0.58, 0.3]):
        dd = d(sc)
        ring = (dd < 1) & (dd > 0.82 if i < 3 else True)
        lvl = 0.3 + 0.2 * i
        v = np.where(ring & (n > 0.5 - 0.17 * i), lvl, v)
    return np.maximum(v + 0.12 * gaussian_filter(v, 20), bg(0.4))

def render(v, pal):
    P = hexpal(pal)
    idx = np.clip(np.floor(np.clip(v, 0, 1) * (len(P) - 1) + B), 0, len(P) - 1).astype(int)
    img = P[idx].astype(np.uint8).repeat(PX, 0).repeat(PX, 1)[:H, :W]
    return Image.fromarray(img)

STYLES = dict(gegenlicht=gegenlicht, nest=nest, glut=glut, matrjoschka=matrjoschka)
PALS = ["cherenkov", "klein", "abyss", "ikb", "glacier", "neon", "dusk", "tokio"]
OUT = "wallpaper/v2"
os.makedirs(OUT, exist_ok=True)
cards = []
for tag, size, sc in [("mbp", (3456, 2234), 0.42), ("pfp", (2048, 2048), 0.34)]:
    setup(*size, sc)
    for sn, f in STYLES.items():
        if tag == "pfp" and sn not in ("gegenlicht", "nest"):
            continue
        v = f()
        for p in PALS:
            fn = f"{tag}_{sn}_{p}.png"
            render(v, p).save(f"{OUT}/{fn}")
            cards.append(fn)
open(f"{OUT}/index.html", "w").write(
    "<body style='background:#111;color:#eee;font:14px monospace;display:grid;grid-template-columns:repeat(4,1fr);gap:8px'>"
    + "".join(f"<a href='{c}'><img src='{c}' style='width:100%'><br>{c}</a>" for c in cards))
print(len(cards))

# v3: Gegenlicht ohne Strahlen, Staerke-Staffel (Halo-Intensitaet a, Reichweite f)
def gl_soft(a, f):
    dd = d(1.0)
    out = np.maximum(dd - 1, 0)
    light = a * np.exp(-out * f) + bg(0.22 * a + 0.08)
    rim = (0.25 + 0.5 * a) * np.exp(-np.abs(dd - 1) * 50)
    return np.clip(np.where(dd < 1, 0.02 + 0.08 * (1 - dd) ** 3, light) + rim, 0, 1)

OUT = "wallpaper/v3"
os.makedirs(OUT, exist_ok=True)
cards = []
LV = [("1_hauch", 0.25, 4.0), ("2_leise", 0.4, 3.0), ("3_mittel", 0.55, 2.4), ("4_kraeftig", 0.7, 1.8), ("5_voll", 0.85, 1.3)]
for tag, size, sc in [("mbp", (3456, 2234), 0.42), ("pfp", (2048, 2048), 0.34)]:
    setup(*size, sc)
    for lv, a, f in LV:
        v = gl_soft(a, f)
        for p in ["ikb", "abyss", "cherenkov", "klein", "glacier"]:
            fn = f"{tag}_gl{lv}_{p}.png"
            render(v, p).save(f"{OUT}/{fn}")
            cards.append(fn)
open(f"{OUT}/index.html", "w").write(
    "<body style='background:#111;color:#eee;font:14px monospace;display:grid;grid-template-columns:repeat(5,1fr);gap:8px'>"
    + "".join(f"<a href='{c}'><img src='{c}' style='width:100%'><br>{c}</a>" for c in cards))
