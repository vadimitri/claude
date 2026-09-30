#!/usr/bin/env python3
"""SPARK Kick-off (14.10., 17 Uhr): bunte Plakatkampagne auf dem Maker-Night-System, aber ohne Lila (Lila = Maker Night).

Eigener Satz (riesiges SPARK, KICK-OFF, Datum, JOIN US ueber dem QR), sonst dieselben Bausteine: D3, R3, Paletten ohne
lila(), Sterne S2/S7/S33 aus styles.py und die freigegebenen Sterne aus dem Spark-Labor, Kompositionen K aus KOMP.
Der QR ist eingebettet: helle Module als geditherter Verlauf in den zwei hellsten Stufen, die Platte dithert in den Grund aus.
Jeder QR wird nach dem Rendern dekodiert (OpenCV), sonst bricht der Lauf ab.

  uv run -q --with numpy --with pillow --with scipy --with qrcode --with scikit-image --with opencv-python-headless \
      python src/kickoff.py [N] [SEED] [a3|9x16]        # N Unikat-Plakate (Standard 24, Seed 1, a3 + 9x16)
  uv run ... python src/kickoff.py one P17 S33 K1 [9x16]  # ein Plakat
  uv run ... python src/kickoff.py fav                    # nur die Favoriten (FAV)
  uv run ... python src/kickoff.py edit                   # Editor mit Live-Vorschau: http://localhost:8765
  uv run ... python src/kickoff.py grid                   # alle P x S x K als Vorschau + Lesbarkeit -> kickoff/grid/index.html
-> kickoff/posters/*.png (A3 300 dpi), kickoff/story/*.png (9x16), kickoff/index.html
"""
import html
import os
import sys
from collections import Counter
from itertools import product
from multiprocessing import Pool

import numpy as np
from scipy.ndimage import binary_dilation, gaussian_filter, label

import styles as S
from styles import AX, BASE, CODENAME, KOMP, lila, line_mask, up, width_per_cap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "kickoff")
# Ort ist noch offen: bewusst nicht erfunden, hier eintragen (erscheint dann unter dem Datum)
COPY = {"title": "SPARK", "what": "KICK-OFF", "when": "14.10. / 17:00", "where": None, "cta": "JOIN US",
        "qr_url": S.COPY["qr_url"]}
FMTS = {"a3": "posters", "9x16": "story"}

PAL = [(c, v, CODENAME[v]) for c, v, *_ in AX["P"] if not lila(v)]
# Easter Egg: jede Colorway traegt ein Stueck Hex (Kopfzeile links, "07/17 7075"). Alle sammeln, nach Nummer reihen,
# `xxd -r -p` -> SECRET. Das fehlende Lila ist der Hinweis auf die Maker Night. Text frei aenderbar (Laenge egal).
SECRET = "spark{the_purple_returns:20-21.nov!}"
FRAG = {v: bytes(b).hex().upper() for (_, v, _), b in zip(PAL, np.array_split(np.frombuffer(SECRET.encode(), np.uint8), len(PAL)))}
assert bytes.fromhex("".join(FRAG[v] for _, v, _ in PAL)).decode() == SECRET
assert "riso" in [v for _, v, _ in PAL] and "lav" not in [v for _, v, _ in PAL]
SPARKS = [("S2", "grad"), ("S7", "nest"), ("S33", "matrjoschka")]
# Labor-Sterne (Vadims Auswahl + Varianten). OWN = am Titel gebaut, bringen ihre Platzierung selbst mit (K egal -> "K0").
# Raus (Vadim 25.9. nachts): S29, S30, S30b (Glitch), S19b. Geparkt: Dreistern S18b, S18c, S19e.
# Raus (Vadim 26.9.): S19c, Brand-Serie S34 S35 S37 S38 S39 S41 S42 S43. Neu drin: S36 Schmelze, S40 Verkohlung.
LAB = ["S13", "S14", "S19d", "S23", "S24", "S26", "S31", "S31b", "S31c", "S31d", "S31e", "S31f", "S36", "S40"]
OWN = {"S24", "S26", "S31", "S31b", "S31c", "S31d", "S31e", "S31f"}
# Eigene Platzierung im einzeiligen Satz (x0, y0, R in Bruchteilen von W, H, kurzer Seite): Stern gross genug, dass er den Leerraum fuellt
OWN_K = {"S26": (0.60, 0.40, 0.80),          # Kippschrift: riesig hinter dem Titel, reicht bis zum QR
         "S31e": (0.62, 0.30, 0.46)}         # Flare: der Stern als Sonne
SPARKS += [(c, "lab:" + c) for c in LAB]
# Zweitlicht (S31c): zweite Palette pro Colorway, nie Lila
ALT2 = {"laser": "cherenkov", "phosphor": "eclipse", "cherenkov": "eclipse", "holo": "eclipse", "eclipse": "cherenkov",
        "blueprint": "eclipse", "riso": "tokio", "cga": "laser", "signal": "cherenkov", "lava": "klein", "kirsche": "holo",
        "klein": "lava", "minze": "orangerie", "orangerie": "eis", "eis": "orangerie", "zitrone": "klein", "tokio": "eclipse",
        "cga0": "laser"}
assert not any(map(lila, ALT2.values()))
_EXTRA = {}                                   # pro Prozess: Zusatzebenen in zweiter Palette + Schriftmaske des letzten Renders
KS = [(c, v) for c, v, *_ in AX["K"]]
S.SIZES["prev"] = (1168, 1652, 1)                 # Vorschau: gleiches Zellraster wie A3 (292 x 413), 4 statt 12 px pro Zelle
# Vadims Favoriten (26.9.), laufen in jeder Serie mit. Optional 4. Eintrag = Editor-Export, z. B. dict(star=(x, y, R), rot=14)
# P21 zweimal geraten: diktiert als "P...undzwanzig", die Einerstelle fehlte
FAV = [("P17", "S7", "K4"), ("P19", "S33", "K5"), ("P21", "S7", "K6"), ("P9", "S2", "K3"), ("P25", "S2", "K7"),
       ("P21", "S2", "K2"), ("P6", "S2", "K2"), ("P20", "S7", "K1"), ("P16", "S33", "K7"), ("P19", "S2", "K2"),
       ("P23", "S33", "K6"), ("P14", "S2", "K5"), ("P18", "S2", "K3"), ("P26", "S7", "K6"), ("P6", "S7", "K4")]


def layout(c):
    """Satz in Displaypixeln. Rueckgabe mit denselben Schluesseln wie styles.layout (fuer die Labor-Sterne) plus eigene."""
    W, H, px = c.W, c.H, c.px
    short = min(W, H)
    snap = lambda v: round(v / px) * px                                        # noqa: E731
    m = snap(0.07 * short)
    sc = 0.026 * short
    meta = m + snap(sc)
    cap = ((W - 2 * m) / px // width_per_cap(COPY["title"])) * px
    cap = snap(cap)
    tb = [meta + snap(0.36 * cap) + cap]
    capd = snap(0.30 * cap)
    sub = [s for s in (COPY["what"], COPY["when"], COPY["where"]) if s]
    sb = [tb[0] + snap(0.2 * cap) + capd + i * snap(1.3 * capd) for i in range(len(sub))]
    q = S.qr_matrix()
    qs = (len(q) + 6) * 2 * px
    qbot = H - m
    capj = snap(0.62 * capd)
    jb = qbot - qs - snap(0.45 * capj)
    fx_, fy, fr = c.st.get("star") or KOMP[c.st["K"]]["port"]              # star = freie Platzierung aus dem Editor
    cy = 0.40 * H if fy is None else fy * H                                  # XOR-Titel: einzeiliger Titel, Stern tiefer
    return dict(m=m, sc=sc, title=(COPY["title"],), cap=cap, tb=tb, meta=meta, capd=capd, db=sb[-1], sub=sub, sb=sb,
                q=q, qs=qs, qbot=qbot, capj=capj, jb=jb, star=(fx_ * W, cy, fr * short, c.st.get("rot", 14)))


def type_layers(c):
    L, px, W = c.L, c.px, c.W
    x = L["m"]
    shape = (c.gh, c.gw)
    flip = lambda v: np.where(c.star_m, c.lvl(0), v)                         # noqa: E731
    n0 = len(c.layers)
    qr(c)                                         # zuerst: Halo zaehlt als Licht, der CTA-Streifen liegt darueber
    base = S.background(c)
    for _, _, v, _, _ in c.layers:
        base = np.where(np.isnan(v), base, v)
    bright = c.star_m | (base > 0.5)              # Wertraum (0 = Grund, 1 = Tinte), gilt auch fuer Papier-Paletten

    def flip_glyphs(mk, v):                       # kleine Schrift kippt pro Buchstabe (Mehrheit), nicht pro Pixel: in Strahlen lesbar
        lab, n = label(mk)
        lit = np.bincount(lab.ravel(), bright.ravel(), n + 1) / np.maximum(np.bincount(lab.ravel(), minlength=n + 1), 1)
        return np.where(lit[lab] > 0.5, c.lvl(0), v)

    def fill(bases, capL):                        # geditherter Verlauf in den Buchstaben wie Maker Night
        rel = np.zeros(shape, np.float32)
        for b in bases:
            band = (c.cy <= b + 0.1 * capL) & (c.cy > b - 1.4 * capL)
            rel = np.where(band, np.clip((c.cy - (b - capL)) / capL, 0, 1), rel)
        return S.F_LO + (S.F_HI - S.F_LO) * (1 - rel)

    for name, lines, bases, capL in (("title", L["title"], L["tb"], L["cap"]), ("date", L["sub"], L["sb"], L["capd"]),
                                     ("cta", (COPY["cta"],), [L["jb"]], L["capj"])):
        mk = np.zeros(shape, bool)
        for s, b in zip(lines, bases):
            mk |= line_mask(s, "clash", capL, b, x, px, shape)
        if name == "cta":                         # CTA kippt nie, steht immer auf hartem Etikettstreifen in Grundfarbe
            pad = max(2, round(0.25 * capL / px))
            ys, xs = np.nonzero(mk)                                       # mittig ueber der QR-Platte
            mk = np.roll(mk, round(x / px) + (L["qs"] // px - (xs.max() - xs.min() + 1)) // 2 - xs.min(), 1)
            ys, xs = np.nonzero(mk)
            box = np.zeros(shape, bool)
            box[ys.min() - pad:ys.max() + pad + 1, xs.min() - pad:xs.max() + pad + 1] = True
            c.add("cta", box, c.lvl(0))
            c.add(name, mk, fill(bases, capL))
        else:
            c.add(name, mk, flip(fill(bases, capL)) if name == "title" else flip_glyphs(mk, fill(bases, capL)))
        _EXTRA[name] = mk                         # Masken fuer legible()

    small = lambda s, b, xx, right=False: line_mask(s, "departure", L["sc"], b, xx, px, shape, right)   # noqa: E731
    i = next(i for i, (_, v, _) in enumerate(PAL) if v == c.st["P"])
    mk = small(f"{i + 1:02d}/{len(PAL)} {FRAG[c.st['P']]}", L["meta"], x) | small(PAL[i][2], L["meta"], W - x, True)
    c.add("meta", mk, flip_glyphs(mk, c.ink))
    _EXTRA["type"] = np.maximum.reduce([a for _, a, *_ in c.layers[n0:]]) > 0


def qr(c):
    """Eingebetteter QR: helle Module = Verlauf zwischen den zwei hellsten Stufen (D3), Platte dithert in den Grund aus."""
    L, px = c.L, c.px
    q, n = L["q"], L["qs"] // px
    top, left = round((L["qbot"] - L["qs"]) / px), round(L["m"] / px)
    lum = c.pal @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    ih = int(lum.argmax())
    ih2 = ih - 1 if ih == c.N else ih + 1                                      # Nachbarstufe: der Dither mischt nur diese zwei
    hi, hi2, lo = c.lvl(ih), c.lvl(ih2), c.lvl(int(lum.argmin()))
    yy, xx = c.yy - top, c.xx - left
    g = np.clip((xx + yy) / (2 * n), 0, 1)                                     # diagonal durch die Platte
    amt = 0.55 if lum[ih2] > 0.55 * lum[ih] else 0.0                # dunkle Zweitstufe (Laserrot) weglassen, sonst liest 9x16 nicht
    light = hi + (hi2 - hi) * amt * g
    base = S.background(c)
    for _, _, v, _, _ in c.layers:
        base = np.where(np.isnan(v), base, v)
    dx = np.maximum(np.maximum(-xx, xx - (n - 1)), 0)
    dy = np.maximum(np.maximum(-yy, yy - (n - 1)), 0)
    dist = np.hypot(dx, dy) / 2                                                # in Modulen
    halo = (dist > 0) & (dist < 10)
    e = np.exp(-dist / 2.6)                                                    # ~3 Module fast hell = Ruhezone gegen Moire
    c.add("qr", halo, np.clip(base + (hi - base) * e, 0, 1))
    plate = (xx >= 0) & (xx < n) & (yy >= 0) & (yy < n)
    c.add("qr", plate, light)
    mods = np.zeros((c.gh, c.gw), bool)
    mods[top + 6:top + n - 6, left + 6:left + n - 6] = up(q, 2)
    c.add("qr", mods, lo)


def spark(c):
    """S2/S7/S33 aus styles.py, Labor-Sterne (Codes aus lab_spark.BY) als ganzes Feld mit K-Platzierung."""
    code = c.st["S"]
    if not code.startswith("lab:"):
        return S.spark(c)
    import lab_spark as ls
    g = ls.G(c.st, c.fmt, c)
    if code[4:] not in OWN or "star" in c.st:
        cx, cy, R, _ = c.L["star"]
        g.K = (cx / g.m, cy / g.m, R / g.m)
        g.rot = c.st.get("rot")
    elif code[4:] in OWN_K:
        fx_, fy, fr = OWN_K[code[4:]]
        g.K = (fx_ * c.W / g.m, fy * c.H / g.m, fr)
    r = ls.BY[code[4:]][1](g)
    v, extra = r if isinstance(r, tuple) else (r, [])
    _EXTRA["extra"] = [(v2, up(mask, c.px), ALT2[c.st["P"]]) for v2, mask, _ in extra]
    c.star_m = g.lit if g.lit is not None else v >= 0.5
    c.add("spark", np.ones(v.shape, bool), np.clip(v, 0, 1))


def style(p, s, k, **kw):
    return dict(BASE, P=p, S=s, K=k, layout=layout, type_fn=type_layers, spark_fn=spark, poster=True, **kw)


def st_code(p, s, k, **kw):
    """Codes -> Stil: st_code("P17", "S7", "K4", star=(0.8, 0.6, 0.7), rot=14). S = S2/S7/S33 oder jeder Labor-Code."""
    return style(next(v for c, v, _ in PAL if c == p), dict(SPARKS).get(s, "lab:" + s), dict(KS)[k], **kw)


def favs():
    rng = np.random.default_rng(26)
    return [(f"fav-{i + 1:02d}__{p}-{s}-{k}", st_code(p, s, k, **{"rot": float(rng.uniform(0, 60)),
                                                                 "seed": int(rng.integers(1000)), **(kw[0] if kw else {})}))
            for i, (p, s, k, *kw) in enumerate(FAV)]


def check_qr(img, px):
    """Dekodiert den QR wie ein Handy aus Abstand, bei Modulgroessen 16/8/5/4 Pixel. OpenCV ist launisch
    (liest bei 8 px nicht, bei 5 px schon), deshalb gilt: mindestens 2 von 4 Groessen lesbar."""
    import cv2
    h, w = img.shape[:2]
    ok = 0
    for mod in (16, 8, 5, 4):
        k = mod / (2 * px)
        small = cv2.resize(img[..., ::-1], (round(w * k), round(h * k)), interpolation=cv2.INTER_AREA)
        ok += cv2.QRCodeDetector().detectAndDecode(small)[0] == COPY["qr_url"]
    return ok >= 2


def frame_of(st, fmt):
    _EXTRA.clear()
    frame = S.render(st, fmt)[0]
    for v2, mask, p2 in _EXTRA.get("extra", []):                            # Zweitlicht ausserhalb der Schrift einsetzen
        pl = S.hexpal(p2)
        col = pl[S.dither(v2, len(pl) - 1, st["D"], st["R"] * S.SIZES[fmt][2])]
        frame = np.where((mask & ~_EXTRA["type"])[..., None], col, frame).astype(np.uint8)
    return frame


def job(item):
    name, st, fmt = item
    frame = frame_of(st, fmt)
    path = os.path.join(OUT, FMTS[fmt], f"{name}.png")
    S.save(frame, path, 300 if fmt == "a3" else None)
    return name, fmt, check_qr(frame, st["R"] * S.SIZES[fmt][2])


def combos(sparks=SPARKS):
    return [(p[:2], s, k) for p, s, k in product(PAL, sparks, KS) if s[1] in KOMP[k[1]].get("only", (s[1],))
            and (s[0] not in OWN or k[0] == "K1")]                     # eigene Platzierung: nur einmal (als K0) im Mix


def legible(frame, px):
    """Lesbarkeit von Titel und Datum, 0..1 (Messung, kein Urteil). Pro Kachel um die Schrift (halbe Zeilenhoehe):
    wie gut trennt eine einzige Helligkeitsschwelle Schrift von Umgebung (balancierte Trefferquote, 0.5 = Zufall).
    Halb gekippte Buchstaben und Sternkanten dicht an der Schrift druecken den Wert. Min aus Titel und Datum."""
    cell = frame[px // 2::px, px // 2::px].astype(np.float32) / 255
    L = gaussian_filter((cell @ np.array([0.2126, 0.7152, 0.0722], np.float32)) ** (1 / 2.2), 0.7)   # Dither weg
    out = []
    for mk, lines in ((_EXTRA["title"], 1), (_EXTRA["date"], 2)):
        mk = mk[:L.shape[0], :L.shape[1]]
        ys = np.nonzero(mk.any(1))[0]
        t = max(4, (ys[-1] - ys[0]) // (2 * lines))
        band = binary_dilation(mk, iterations=max(2, t // 3))
        acc, wt = [], []
        for y in range(ys[0] - t, ys[-1] + t, t):
            for x in range(0, L.shape[1], t):
                m, b = mk[max(y, 0):y + t, x:x + t], band[max(y, 0):y + t, x:x + t]
                if not 0.15 < m.sum() / max(b.sum(), 1) < 0.85:
                    continue
                v = L[max(y, 0):y + t, x:x + t][b]
                g = m[b]
                th = np.quantile(v, np.linspace(0.05, 0.95, 19))[:, None]
                tpr, tnr = (v[g] > th).mean(1), (v[~g] <= th).mean(1)
                acc.append(max((tpr + tnr).max(), (2 - tpr - tnr).max()) / 2)
                wt.append(b.sum())
        out.append(np.average(acc, weights=wt) if acc else 0.5)
    return float(np.clip(2 * min(out) - 1, 0, 1))


def mix(n, seed, sparks=SPARKS):
    """n Unikate aus P x S x K, keine Kombi doppelt, gierig die seltensten Bausteine zuerst (wie styles.poster_set)."""
    rng = np.random.default_rng(seed)
    pool = combos(sparks)
    rest, out, cnt = [pool[j] for j in rng.permutation(len(pool))], [], Counter()
    while rest and len(out) < n:
        cb = min(rest, key=lambda cb: sum(cnt[x] for x in cb))     # ponytail: O(n^2), n ~ 400
        rest.remove(cb)
        out.append(cb)
        cnt.update(cb)
    return [(f"{seed:02d}-{i + 1:02d}__{pc}-{sc}-{'K0' if sc in OWN else kc}",
             style(p, s, k, rot=float(rng.uniform(0, 60)), seed=int(rng.integers(1000))))
            for i, ((pc, p), (sc, s), (kc, k)) in enumerate(out)]


def gallery():
    esc = html.escape
    secs = []
    for fmt, d in FMTS.items():
        p = os.path.join(OUT, d)
        fs = sorted(os.listdir(p)) if os.path.isdir(p) else []
        figs = "".join(f'<figure><a href="{d}/{f}"><img loading="lazy" src="{d}/{f}"></a><figcaption><code>'
                       f'{esc(f[:-4].replace("__", " · ").replace("-", " "))}</code></figcaption></figure>' for f in fs)
        secs.append(f'<h2>{"A3 · 300 dpi" if fmt == "a3" else "Story 9x16"}</h2><div class="grid">{figs}</div>')
    pals = " ".join(f"<code>{c}</code> {esc(t)}" for c, _, t in PAL)
    page = f"""<!doctype html><html lang="de"><meta charset="utf-8"><title>SPARK Kick-off</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{S.CSS}
.grid{{grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}}</style><main><h1>SPARK Kick-off · 14.10. · 17:00</h1>
<p class="d">Bunte Kampagne auf dem Maker-Night-System. Kein Lila (gehoert der Maker Night). Jedes Plakat ein Unikat,
jeder QR nach dem Rendern maschinell dekodiert. Dateiname = Serie-Nummer · P S K.<br>
Easter Egg: Kopfzeile links = Nummer/Anzahl + Hex-Stueck der Colorway. Alle {len(PAL)} sammeln, nach Nummer reihen,
<code>xxd -r -p</code> → <code>{html.escape(SECRET)}</code></p>
<p class="d">Colorways: {pals}</p>{"".join(secs)}
<p class="d">Erzeugt von <code>src/kickoff.py</code>. System: <a href="../styles/index.html">styles/</a></p></main></html>"""
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)


EDIT_PAGE = """<!doctype html><html lang="de"><meta charset="utf-8"><title>Kick-off Editor</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{margin:0;background:#0b0b0e;color:#ddd;font:14px/1.4 ui-monospace,Menlo,monospace;display:flex;gap:20px;padding:16px}
aside{width:300px;flex:none;display:flex;flex-direction:column;gap:10px}label{display:grid;grid-template-columns:52px 1fr 48px;
gap:8px;align-items:center}select,button{font:inherit;background:#1b1b22;color:#eee;border:1px solid #333;padding:6px}
button{cursor:pointer}button:hover{border-color:#888}#img{height:calc(100vh - 32px);cursor:crosshair;image-rendering:pixelated}
#st{color:#888;min-height:3em;white-space:pre-wrap;word-break:break-all}#pos{color:#fb0}</style>
<aside><b>SPARK Kick-off · Editor</b>
<label>P<select id=p></select><span></span></label><label>S<select id=s></select><span></span></label>
<label>K<select id=k></select><span></span></label>
<label>x<input id=x type=range min=-0.3 max=1.3 step=0.01><output></output></label>
<label>y<input id=y type=range min=-0.2 max=1.3 step=0.01><output></output></label>
<label>Groesse<input id=r type=range min=0.1 max=2 step=0.01><output></output></label>
<label>Drehung<input id=rot type=range min=0 max=72 step=1><output></output></label>
<label>Seed<input id=seed type=range min=0 max=999 step=1><output></output></label>
<div>Position: <span id=pos></span> <button id=reset>K-Standard</button></div>
<button id=exp>Export A3 + Story (mit QR-Check)</button><div id=st>Klick ins Bild = Stern dorthin, Mausrad = Groesse</div>
</aside><img id=img>
<script>
const D=__DATA__, $=id=>document.getElementById(id), sl=["x","y","r","rot","seed"];let custom=false,busy=false,again=false;
for(const[a,list]of[["p",D.P],["s",D.S],["k",D.K]])for(const c of list)$(a).add(new Option(c,c));
$("p").value="P17";$("s").value="S7";$("k").value="K4";$("rot").value=14;$("seed").value=0;
const h=new URLSearchParams(location.hash.slice(1));for(const a of"psk")if(h.get(a))$(a).value=h.get(a).replace("K0","K1");
function reset(){const[x,y,r]=D.port[$("k").value];$("x").value=x;$("y").value=y??0.4;$("r").value=r;custom=false;draw()}
function q(){const o={p:$("p").value,s:$("s").value,k:$("k").value,rot:$("rot").value,seed:$("seed").value};
 if(custom)Object.assign(o,{x:$("x").value,y:$("y").value,r:$("r").value});return new URLSearchParams(o)}
function draw(){for(const n of sl)$(n).nextElementSibling.value=$(n).value;$("pos").textContent=custom?"frei":"K-Standard";
 if(busy){again=true;return}busy=true;const t=performance.now(),im=new Image();
 im.onload=im.onerror=()=>{$("img").src=im.src;busy=false;$("st").textContent=`Vorschau ${Math.round(performance.now()-t)} ms`;
  if(again){again=false;draw()}};im.src="/render?"+q()}
for(const n of["p","s","k"])$(n).onchange=n=="k"?reset:draw;
for(const n of sl)$(n).oninput=()=>{if(n!="rot"&&n!="seed")custom=true;draw()};
$("reset").onclick=reset;
$("img").onclick=e=>{const b=e.target.getBoundingClientRect();$("x").value=((e.clientX-b.left)/b.width).toFixed(2);
 $("y").value=((e.clientY-b.top)/b.height).toFixed(2);custom=true;draw()};
$("img").onwheel=e=>{e.preventDefault();$("r").value=+$("r").value*(e.deltaY>0?0.95:1.05);custom=true;draw()};
$("exp").onclick=async()=>{$("st").textContent="rendere A3 + Story …";const r=await(await fetch("/export?"+q())).json();
 $("st").textContent=r.files.join("\\n")+(r.qr?"\\nQR ok":"\\nQR NICHT LESBAR")+"\\n\\nFuer FAV in kickoff.py:\\n"+r.fav};
reset()</script></html>"""


def edit(port=8765):
    """Lokaler Editor: P/S/K waehlen, Stern per Klick/Regler platzieren, Live-Vorschau, Export wie `one` (A3 + Story)."""
    import io
    import json
    import time
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qs, urlparse
    from PIL import Image
    import lab_spark as ls
    data = dict(P=[c for c, _, _ in PAL], S=[c for c, _ in SPARKS] + [c for c in ls.BY if c not in dict(SPARKS)],
                K=[c for c, _ in KS], port={c: KOMP[v]["port"] for c, v in KS})
    page = EDIT_PAGE.replace("__DATA__", json.dumps(data)).encode()

    def st_of(q):
        kw = dict(rot=float(q["rot"]), seed=int(q["seed"]))
        if "x" in q:
            kw["star"] = tuple(round(float(q[a]), 3) for a in "xyr")
        return q["p"], q["s"], q["k"], kw

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            u = urlparse(self.path)
            q = {a: v[0] for a, v in parse_qs(u.query).items()}
            try:
                if u.path == "/":
                    body, ctype = page, "text/html; charset=utf-8"
                elif u.path == "/render":
                    p, s, k, kw = st_of(q)
                    buf = io.BytesIO()
                    Image.fromarray(frame_of(st_code(p, s, k, **kw), "prev")).save(buf, "png", compress_level=1)
                    body, ctype = buf.getvalue(), "image/png"
                elif u.path == "/export":
                    p, s, k, kw = st_of(q)
                    name = f"edit-{time.strftime('%H%M%S')}__{p}-{s}-{k}"
                    res = [job((name, st_code(p, s, k, **kw), f)) for f in FMTS]
                    gallery()
                    body = json.dumps(dict(files=[os.path.relpath(os.path.join(OUT, FMTS[f], n + ".png"), ROOT)
                                                  for n, f, _ in res], qr=all(ok for *_, ok in res),
                                           fav=repr((p, s, k, kw)) + ",")).encode()
                    ctype = "application/json"
                else:
                    return self.send_error(404)
            except Exception as e:                # kaputte Kombi soll den Server nicht beenden
                return self.send_error(500, repr(e))
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    print(f"Editor: http://localhost:{port}  (Strg+C beendet)")
    HTTPServer(("127.0.0.1", port), H).serve_forever()   # ponytail: ein Thread, Renders laufen nacheinander (_EXTRA ist global)


TIER = (0.95, 0.88)                               # Lesbarkeit: >= A sichtbare Orte, >= B normal, darunter C = Kunst, versteckt


def job_grid(item):
    (pc, p), (sc, s), (kc, k) = item
    frame = frame_of(style(p, s, k), "prev")
    kc = "K0" if sc in OWN else kc
    S.save(frame[::4, ::4], os.path.join(OUT, "grid", "t", f"{pc}-{sc}-{kc}.png"))     # 1 Pixel pro Zelle
    return pc, sc, kc, round(legible(frame, 4), 3)


def grid():
    """Jede Kombi aus dem Roster als Vorschau (gleiches Raster wie A3) mit gemessener Lesbarkeit, Auswahl -> FAV."""
    import json
    with Pool() as pool:
        rows = []
        for r in pool.imap_unordered(job_grid, combos(), chunksize=4):
            rows.append(r)
            print(f"\r{len(rows)}", end="", flush=True)
    rows.sort()
    sc = np.array([r[3] for r in rows])
    print(f"\n{len(rows)} Plakate, Lesbarkeit Quantile 10/25/50/75/90:", np.round(np.quantile(sc, [.1, .25, .5, .75, .9]), 3))
    data = dict(rows=rows, tier=TIER, P={c: t for c, _, t in PAL}, S=[c for c, _ in SPARKS], K=["K0"] + [c for c, _ in KS])
    open(os.path.join(OUT, "grid", "index.html"), "w", encoding="utf-8").write(GRID_PAGE.replace("__DATA__", json.dumps(data)))
    print(os.path.join(OUT, "grid", "index.html"))


GRID_PAGE = """<!doctype html><html lang="de"><meta charset="utf-8"><title>Kick-off Raster</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--bg:#0b0b0e;--fg:#ddd;--mute:#777;--line:#26262e}body{margin:0;background:var(--bg);color:var(--fg);
font:13px/1.4 ui-monospace,Menlo,monospace}header{position:sticky;top:0;z-index:2;background:var(--bg);padding:10px 16px;
border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:14px;align-items:center}select,button{font:inherit;
background:#1b1b22;color:#eee;border:1px solid #333;padding:4px 8px;cursor:pointer}button.on{border-color:#fb0;color:#fb0}
main{padding:0 16px 120px}h2{margin:28px 0 8px;font-size:15px}table{border-collapse:collapse;width:100%;table-layout:fixed}
th{color:var(--mute);font-weight:400;padding:4px;text-align:left;font-size:12px}th.r{width:92px}td{padding:3px;vertical-align:top}
.c{position:relative;cursor:pointer;outline:3px solid transparent;outline-offset:-1px}.c img{width:100%;display:block}
.c.sel{outline-color:#fb0}.c.dim{opacity:.12}.b{position:absolute;left:3px;bottom:3px;padding:0 4px;font-size:11px;
background:#000c;border-radius:2px}.A{color:#6f6}.B{color:#fd4}.C{color:#f6c}.e{position:absolute;right:3px;bottom:3px;
padding:0 4px;background:#000c;color:#aaa;text-decoration:none;font-size:11px}footer{position:fixed;bottom:0;left:0;right:0;
background:#15151b;border-top:1px solid var(--line);padding:8px 16px;display:flex;gap:12px;align-items:center}
#sel{flex:1;color:var(--mute);white-space:nowrap;overflow:auto}</style>
<header><b>SPARK Kick-off · Raster</b><label>Tabelle je <select id=ax><option>S<option>P<option>K</select></label>
<span>Lesbarkeit: <button data-t=all class=on>alle</button> <button data-t=A>A sichtbar</button>
<button data-t=B>B normal</button> <button data-t=C>C Kunst</button></span>
<span style="color:var(--mute)">Klick = auswaehlen · ✎ = im Editor oeffnen (kickoff.py edit)</span></header>
<main id=m></main><footer><span id=n>0</span><span id=sel></span><button id=cp>FAV kopieren</button><button id=clr>leeren</button></footer>
<script>
const D=__DATA__,$=id=>document.getElementById(id),AX={P:Object.keys(D.P),S:D.S,K:D.K};
let sel=new Set(),tier="all";try{sel=new Set(JSON.parse(localStorage.getItem("sel")||"[]"))}catch(e){}
const T=v=>v>=D.tier[0]?"A":v>=D.tier[1]?"B":"C",key=r=>r.slice(0,3).join(" ");
const byKey=Object.fromEntries(D.rows.map(r=>[key(r),r]));
function render(){const ax=$("ax").value,[ra,ca]="PSK".replace(ax,"").split(""),idx={P:0,S:1,K:2};let h="";
 for(const t of AX[ax]){const rs=D.rows.filter(r=>r[idx[ax]]==t);if(!rs.length)continue;
  const cols=AX[ca].filter(c=>rs.some(r=>r[idx[ca]]==c)),rows=AX[ra].filter(c=>rs.some(r=>r[idx[ra]]==c));
  h+=`<h2>${t} ${D.P[t]||""}</h2><table><tr><th class=r></th>${cols.map(c=>`<th>${c} ${ca=="P"?D.P[c]:""}</th>`).join("")}</tr>`;
  for(const rv of rows){h+=`<tr><th class=r>${rv}<br>${ra=="P"?D.P[rv]:""}</th>`;
   for(const cv of cols){const r=rs.find(r=>r[idx[ra]]==rv&&r[idx[ca]]==cv);
    if(!r){h+="<td></td>";continue}const k=key(r),tt=T(r[3]);
    h+=`<td><div class="c ${sel.has(k)?"sel":""} ${tier!="all"&&tier!=tt?"dim":""}" data-k="${k}"><img loading=lazy src="t/${r.slice(0,3).join("-")}.png">
     <span class="b ${tt}">${tt} ${r[3].toFixed(2)}</span><a class=e target=editor href="http://localhost:8765/#p=${r[0]}&s=${r[1]}&k=${r[2]}">✎</a></div></td>`}
   h+="</tr>"}h+="</table>"}
 $("m").innerHTML=h;foot()}
function foot(){const ks=[...sel].sort();$("n").textContent=ks.length+" gewaehlt";$("sel").textContent=ks.join(" · ");
 try{localStorage.setItem("sel",JSON.stringify(ks))}catch(e){}}
$("m").onclick=e=>{const c=e.target.closest(".c");if(!c||e.target.closest("a"))return;const k=c.dataset.k;
 sel.has(k)?sel.delete(k):sel.add(k);c.classList.toggle("sel");foot()};
$("ax").onchange=render;for(const b of document.querySelectorAll("[data-t]"))b.onclick=()=>{tier=b.dataset.t;
 document.querySelectorAll("[data-t]").forEach(x=>x.classList.toggle("on",x==b));render()};
$("cp").onclick=()=>{const txt=[...sel].sort().map(k=>{const r=byKey[k];return`("${r[0]}", "${r[1]}", "${r[2]=="K0"?"K1":r[2]}"),  # ${T(r[3])} ${r[3]}`}).join("\\n");
 navigator.clipboard.writeText(txt);$("cp").textContent="kopiert";setTimeout(()=>$("cp").textContent="FAV kopieren",1500)};
$("clr").onclick=()=>{sel.clear();render()};render()</script></html>"""


def main():
    args = sys.argv[1:]
    fmts = [a for a in args if a in FMTS] or list(FMTS)
    if "edit" in args:
        return edit()
    if "grid" in args:
        return grid()
    if "one" in args:
        codes = [a for a in args[args.index("one") + 1:] if a[0] in "PSK"]
        p, s, k = (next(c for c in codes if c[0] == a) for a in "PSK")
        items = [("one__" + "-".join(codes), st_code(p, s, k), f) for f in fmts]
    elif "fav" in args:
        items = [(nm, st, f) for f in fmts for nm, st in favs()]
    else:
        nums = [int(a) for a in args if a.isdigit()] + [24, 1]
        items = [(nm, st, f) for f in fmts for nm, st in mix(*nums[:2])[: nums[0] if f == "a3" else 12] + favs()]
    bad = []
    with Pool() as pool:
        for name, fmt, ok in pool.imap_unordered(job, items):
            print(f"{name} {fmt}{'' if ok else ' QR!'}", end=" | ", flush=True)
            bad += [] if ok else [f"{name} {fmt}"]
    print()
    gallery()
    print(os.path.join(OUT, "index.html"))
    assert not bad, f"QR nicht lesbar: {bad}"


if __name__ == "__main__":
    main()
