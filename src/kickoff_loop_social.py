#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""Social-Fassung (Vadim 9.10.): in den Foto-Platten den gedruckten QR (Telegram) gegen den Rickroll-QR tauschen, so dass
er aussieht wie mitfotografiert. photos/aligned/NN.png → photos/aligned_social/NN.png (F17BS liest sie, [photos].aligned_dir).

  uv run src/kickoff_loop_social.py          alle 64 Platten + photos/social_qr.png (je Platte vorher | nachher) + Report
  danach (Pack-Root):
    SPARK_SOCIAL=1 uv run src/kickoff_loop.py preview kickoff_loop/previz/review/F17BS/F17BS.toml --master
    SPARK_SOCIAL=1 uv run src/kickoff_loop_f16.py video kickoff_loop/previz/review/F19S/F19S.toml --master

Umkehrung der Foto-Methode (Plakat im Foto ~ digital): der QR wird im Foto selbst umgefaerbt, nicht hineinkopiert. Je Platte:
  1. Lage des QR im Plakat aus dem Druck print/NN.png (Vorlage, 1 Zelle = 4 px wie die Platte).
  2. Lage im Foto: Grobsuche per Vorlage (+-SEARCH_PX), dann Phasenkorrelation je Feld (4 x 4) → Homographie, dann
     Restverformung als glattes Feld (6 x 6, Thin-Plate): die Platten sind ueber die Marken ausgerichtet, aber gewoelbt
     (Litfasssaeule) und bis ~15 px versetzt/gedreht.
  3. Modell aus dem Foto (sRGB), je Kanal auf der QR-Platte (robust gegen Spiegelungen): foto ~ L(x, y) + Kern * t, t = Modul-
     muster (0 hell .. 1 dunkel), Kern 11 x 11 = Kantenantwort der Kamera (Unschaerfe + Nachschaerfen), L und der
     Kontrast als Ebenen (Licht). Neu = foto + Kern * (t_neu - t_alt): nur die getauschten Module aendern sich, Korn,
     Rauschen und Licht des Fotos bleiben. (Gauss statt Kern: die Halos der alten Kanten blieben als Praegung stehen.)
     (Erster Versuch mit der umgekehrten fit_color-Abbildung des Drucks: gruen/magenta Module, weil Kanaele mit wenig
     Kontrast im Druck die Kanal-Verstaerkung nicht tragen. t ist in jedem Kanal derselbe, voller Kontrast.)
Pruefung je Platte: neuer QR dekodiert, alter nicht mehr, Korrelation mit neuem Muster >> mit altem.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

import kickoff_loop as KL
import kickoff_loop_photos as P

S = KL.S
SRC, DST = (os.path.join(P.DIR, d) for d in ("aligned", "aligned_social"))
MOD_PX = KL.MODULE_CELLS * KL.PREVIEW_CELL_PX     # ein QR-Modul in der Platte (2 Zellen x 4 px)
WIN_PX = 48                                       # Fenster um den QR (12 Zellen: Ruhezone, Gluehen, Rand fuer die Lage)
SEARCH_PX = 40                                    # Grobsuche: so weit darf der QR im Foto von seiner Sollage liegen
COARSE_BLUR_PX = 4                                # ... weich (1 Zelle), damit 1-2 Grad Drehung den Treffer nicht kippen (31)
GRID = 4                                          # Feinlage: Felder je Seite ueber dem QR (16 Punkte fuer die Homographie)
PATCH_PX = 72                                     # ... Feldgroesse (9 Module): genug Struktur fuer die Phasenkorrelation
MIN_RESP = 0.1                                    # ... Feld zaehlt ab dieser Spitze der Phasenkorrelation (Spiegelung: ~0)
SCORE_BLUR_PX = 0.75                              # Lagebewertung: Muster so weich (typische Foto-Schaerfe, s. Report)
DEFORM_GRID = 6                                   # Restverformung: Felder je Seite (Abstand ~6 Module) ...
DEFORM_PATCH_PX = 48                              # ... Feldgroesse (6 Module)
DEFORM_MAX_PX = 3.0                               # ... Verschiebungen darueber sind Fehltreffer (Feld bleibt glatt)
DEFORM_SMOOTH = 1.0                               # ... Glaettung der Thin-Plate (px^2), einzelne Ausreisser ziehen nicht
DEFORM_ITERS = 3                                  # ... Runden, solange die Passung steigt
REFINE_STEPS_PX = (0.5, 0.125)                    # zuletzt Verschiebung +-2 Schritte je Stufe auf die Korrelation (bis 1/8 px)
FIT_PAD_PX = 4                                    # Fit auf der QR-Platte: Module + 1 Zelle (Ruhezone ist 1 Modul)
KERNEL_PX = 5                                     # Kantenantwort: Kern 11 x 11 (Unschaerfe bis sigma ~1.75 + Schaerfungs-Halo)
ROBUST_ITER = 6                                   # Licht-Fit: so oft neu gewichten (Cauchy wie fit_color)
MIN_NCC_GAIN = 0.2                                # Pruefung: Korrelation mit neuem Muster so viel ueber der mit altem


def matrix(url):
    import qrcode
    q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(url)
    q.make(fit=True)
    return np.array(q.get_matrix(), bool)


def up(q):
    return np.kron(q, np.ones((MOD_PX, MOD_PX))).astype(np.float32)


def qr_box(n, q_old):
    """Lage des QR im Druck n auf Plattengroesse: linke obere Ecke (y, x) im Plakat, Kantenlaenge s in Pixeln."""
    im = Image.open(os.path.join(KL.PROJECT, "print", f"{n:02d}.png")).convert("L").reduce(P.PRINT_TO_PLATE)
    r = cv2.matchTemplate(-np.asarray(im, np.float32), up(q_old), cv2.TM_CCOEFF_NORMED)
    _, score, _, (x, y) = cv2.minMaxLoc(r)
    assert score > 0.95, f"Druck {n}: QR nicht gefunden (Vorlage {score:.2f})"
    return y, x, len(q_old) * MOD_PX


def decode(rgb_u8):
    """Text des QR im Bild ('' = nicht lesbar), bei mehreren Groessen wie ein Handy aus Abstand."""
    g = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2GRAY)
    for k in (1.0, 0.5, 2.0, 0.75):
        for det in (cv2.QRCodeDetector(), cv2.QRCodeDetectorAruco()):
            try:
                t = det.detectAndDecode(cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_AREA))[0]
            except cv2.error:
                t = ""
            if t:
                return t
    return ""


def ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-12))


def warped(im, warp, ws):
    return cv2.warpPerspective(im, warp, (ws, ws), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)


def locate(seen_l, t_old, ws):
    """Warp Foto-Pixel → Muster (3 x 3, fuer warped). Grobsuche per Vorlage (ganze Pixel), dann je Feld eines 4 x 4-Rasters
    ueber dem QR die Subpixel-Verschiebung per Phasenkorrelation und daraus eine Homographie (LMedS, robust gegen einzelne
    Felder mit Spiegelung), sonst affin. Zaehlt nur, wenn das Muster danach besser zum Foto passt als die Grobsuche.
    (ECC lief auf dem QR-Muster selbst von der richtigen Lage weg, Befund 9.10.: Platte 11 Grobsuche 0.995 bei 0/0,
    ECC landet bei 37/59 px; OpenCV 5 wirft dazu "Iterations do not converge".)"""
    s32 = lambda im, s: gaussian_filter(im, s).astype(np.float32)   # noqa: E731
    pat, seen = s32(1 - t_old, 1), s32(seen_l, 1)
    core = s32(1 - t_old, COARSE_BLUR_PX)[SEARCH_PX:ws - SEARCH_PX, SEARCH_PX:ws - SEARCH_PX]
    r = cv2.matchTemplate(s32(seen_l, COARSE_BLUR_PX), core, cv2.TM_CCOEFF_NORMED)
    _, _, _, (x, y) = cv2.minMaxLoc(r)
    dx, dy = x - SEARCH_PX, y - SEARCH_PX                                  # Foto = Muster + (dx, dy)
    best = np.array([[1, 0, -dx], [0, 1, -dy], [0, 0, 1]], np.float32)
    h, qs = PATCH_PX // 2, ws - 2 * WIN_PX
    R = (slice(WIN_PX + dy + MOD_PX, WIN_PX + dy + qs - MOD_PX), slice(WIN_PX + dx + MOD_PX, WIN_PX + dx + qs - MOD_PX))
    raw = seen_l.astype(np.float32)
    # Bewertung nur auf den Modulen (JOIN US, Plattenkante, Gluehen kennt das Muster nicht), Foto ungefiltert
    score = lambda w: ncc(raw[R], gaussian_filter(warped(1 - t_old, w, ws), SCORE_BLUR_PX)[R])   # noqa: E731
    top, how = score(best), "T"
    han = cv2.createHanningWindow((PATCH_PX, PATCH_PX), cv2.CV_32F)
    src, dst = [], []
    for i in range(GRID):
        for j in range(GRID):
            cy, cx = (WIN_PX + round(qs * (k + 0.5) / GRID) for k in (i, j))
            if not (h <= cy + dy <= ws - h and h <= cx + dx <= ws - h):     # Feld im Foto ausserhalb des Fensters
                continue
            (sx, sy), resp = cv2.phaseCorrelate(pat[cy - h:cy + h, cx - h:cx + h],
                                                seen[cy + dy - h:cy + dy + h, cx + dx - h:cx + dx + h], han)
            if resp > MIN_RESP:
                src.append((cx + dx + sx, cy + dy + sy))
                dst.append((cx, cy))
    src, dst = np.float32(src), np.float32(dst)
    cands = []
    if len(src) >= 6:
        H, _ = cv2.findHomography(src, dst, cv2.LMEDS)
        cands += [(H, "H")] if H is not None else []
    if len(src) >= 3:
        A, _ = cv2.estimateAffine2D(src, dst, method=cv2.LMEDS)
        cands += [(np.vstack([A, [0, 0, 1]]), "A")] if A is not None else []
    for w, name in cands:
        s = score(w.astype(np.float32))
        if s > top:
            top, best, how = s, w.astype(np.float32), name
    for step in REFINE_STEPS_PX:                  # Restversatz unter 1 px: sonst bleiben Saeume an alten Modulkanten (12, 39)
        base = best
        for ty in np.arange(-2, 3) * step:
            for tx in np.arange(-2, 3) * step:
                w = np.array([[1, 0, tx], [0, 1, ty], [0, 0, 1]], np.float32) @ base
                s = score(w)
                if s > top:
                    top, best = s, w
    return best, how


def deform(seen_l, t_old, warp, ws):
    """Restverformung nach der Homographie (Plakat gewoelbt, Befund 19: R2 0.71, gelbe Saeume an alten Kanten): je Feld
    eines feineren Rasters die Verschiebung per Phasenkorrelation, als glattes Feld (Thin-Plate) dazu, solange die Passung
    steigt. Zurueck: remap-Karten (Foto-Pixel → Muster) und die Feldgroesse (max. Verschiebung in px)."""
    from scipy.interpolate import RBFInterpolator
    yy, xx = np.mgrid[0:ws, 0:ws].astype(np.float32)

    def maps(d):
        qx, qy = xx - d[..., 0], yy - d[..., 1]
        den = warp[2, 0] * qx + warp[2, 1] * qy + warp[2, 2]
        return ((warp[0, 0] * qx + warp[0, 1] * qy + warp[0, 2]) / den).astype(np.float32), \
            ((warp[1, 0] * qx + warp[1, 1] * qy + warp[1, 2]) / den).astype(np.float32)
    d = np.zeros((ws, ws, 2), np.float32)
    m = maps(d)
    box = remap(np.pad(np.ones((ws - 2 * WIN_PX,) * 2, np.float32), WIN_PX), m) > 0.5
    R = cv2.erode(box.astype(np.uint8), np.ones((2 * MOD_PX + 1,) * 2, np.uint8)) > 0
    score = lambda m: ncc(seen_l[R], gaussian_filter(1 - remap(t_old, m), SCORE_BLUR_PX)[R])   # noqa: E731
    top = score(m)
    ys, xs = np.nonzero(R)
    h = DEFORM_PATCH_PX // 2
    han = cv2.createHanningWindow((DEFORM_PATCH_PX, DEFORM_PATCH_PX), cv2.CV_32F)
    sl = gaussian_filter(seen_l, 1).astype(np.float32)
    for _ in range(DEFORM_ITERS):
        pw = gaussian_filter(1 - remap(t_old, m), 1).astype(np.float32)
        pts, vals = [], []
        for cy in np.linspace(ys.min() + h, ys.max() - h, DEFORM_GRID).round().astype(int):
            for cx in np.linspace(xs.min() + h, xs.max() - h, DEFORM_GRID).round().astype(int):
                (sx, sy), resp = cv2.phaseCorrelate(pw[cy - h:cy + h, cx - h:cx + h], sl[cy - h:cy + h, cx - h:cx + h], han)
                if resp > MIN_RESP and max(abs(sx), abs(sy)) < DEFORM_MAX_PX:
                    pts.append((cy, cx))
                    vals.append((sx, sy))
        if len(pts) < 6:
            break
        f = RBFInterpolator(np.float32(pts), np.float32(vals), kernel="thin_plate_spline", smoothing=DEFORM_SMOOTH)
        dd = f(np.c_[yy.ravel(), xx.ravel()]).reshape(ws, ws, 2).astype(np.float32)
        nd = d + np.clip(dd, -DEFORM_MAX_PX, DEFORM_MAX_PX)
        nm = maps(nd)
        s = score(nm)
        if s <= top:
            break
        top, d, m = s, nd, nm
    return m, float(np.abs(d[box]).max()) if box.any() else 0.0


def remap(im, m):
    return cv2.remap(im, m[0], m[1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def swap(n, q_old, q_new):
    plate = np.asarray(Image.open(os.path.join(SRC, f"{n:02d}.png")).convert("RGB"))
    pw, ph = S.SIZES[KL.PREVIEW][:2]
    y0, x0 = (plate.shape[0] - ph) // 2, (plate.shape[1] - pw) // 2      # Plakat mittig in der Platte (photos._plate)
    qy, qx, qs = qr_box(n, q_old)
    ws = qs + 2 * WIN_PX
    win = (slice(y0 + qy - WIN_PX, y0 + qy - WIN_PX + ws), slice(x0 + qx - WIN_PX, x0 + qx - WIN_PX + ws))
    seen = plate[win].astype(np.float32) / 255      # sRGB, nicht linear: Rauschen und Nachschaerfen der Kamera leben im
    seen_l = seen @ KL.LUMA                         # Gamma-Raum; linear blies der Uebertrag hell → dunkel das Korn zu Sprenkeln auf
    place = lambda q: np.pad(up(q), WIN_PX)       # noqa: E731  Muster im Fenster, Sollage
    warp, how = locate(seen_l, place(q_old), ws)
    m, field = deform(seen_l, place(q_old), warp, ws)
    move = lambda im: remap(im, m)                # noqa: E731
    to, tn, box = move(place(q_old)), move(place(q_new)), move(np.pad(np.ones((qs, qs), np.float32), WIN_PX))
    grow = lambda px: cv2.dilate((box > 0.5).astype(np.uint8), np.ones((2 * px + 1,) * 2, np.uint8)) > 0   # noqa: E731
    fit, upd = grow(FIT_PAD_PX), grow(FIT_PAD_PX + KERNEL_PX + 1)        # Fit auf der QR-Platte, Aenderung reicht so weit
    offs = [(dy, dx) for dy in range(-KERNEL_PX, KERNEL_PX + 1) for dx in range(-KERNEL_PX, KERNEL_PX + 1)]
    stack = lambda t: np.stack([np.roll(t, o, (0, 1))[upd] for o in offs], -1)   # noqa: E731  t(x - o) je Kern-Tap
    So, Sn = stack(to), stack(tn)
    yy, xx = (np.mgrid[0:ws, 0:ws] / ws - 0.5).astype(np.float32)
    xf, yf, inf = xx[upd], yy[upd], fit[upd]
    base = np.c_[np.ones_like(xf), xf, yf]

    def robust(A, b):
        w = np.ones(int(inf.sum()), np.float32)
        for _ in range(ROBUST_ITER):
            coef = np.linalg.lstsq(A[inf] * w[:, None], b[inf] * w, rcond=None)[0]
            r = b[inf] - A[inf] @ coef
            w = 1 / (1 + (r / (2 * 1.4826 * np.median(np.abs(r)) + 1e-6)) ** 2)
        return coef, r

    # Kantenantwort des Fotos (Unschaerfe + Nachschaerfen der Kamera: Halos) als Kern auf der Helligkeit, dann je Kanal
    # Kern + Licht (Ebene) + Kontrastverlauf (Ebene): foto ~ L(x, y) + sum k_c(o) t(x - o) + (b1 x + b2 y) (k * t)
    kl, rl = robust(np.c_[base, So], seen_l[upd])
    k = kl[3:] / kl[3:].sum()
    tko, tkn = So @ k, Sn @ k
    delta = np.empty((len(xf), 3), np.float32)
    for ch in range(3):
        coef, _ = robust(np.c_[base, So, tko * xf, tko * yf], seen[..., ch][upd])
        delta[:, ch] = (np.c_[base * 0, Sn - So, (tkn - tko) * xf, (tkn - tko) * yf]) @ coef
    out_f = seen.copy()
    out_f[upd] += delta
    out = plate.copy()
    out[win] = np.round(np.clip(out_f, 0, 1) * 255).astype(np.uint8)
    ol, sl = out_f[upd] @ KL.LUMA, seen_l[upd]
    rep = dict(n=n, how=how, shift=(float(warp[0, 2]), float(warp[1, 2])), field=field,
               r2=float(1 - np.var(rl) / np.var(sl[inf])), halo=float(-k[k < 0].sum()),
               ncc_new=ncc(ol[inf], -tkn[inf]), ncc_old=ncc(ol[inf], -tko[inf]),
               dec_before=decode(plate[win]), dec_after=decode(out[win]))
    return out, rep, (plate[win], out[win])


def main():
    assert not S.SOCIAL, "ohne SPARK_SOCIAL starten: das Skript sucht den gedruckten QR als Vorlage"
    q_old, q_new = matrix(S.PRINT_QR_URL), matrix(S.SOCIAL_QR_URL)
    assert q_old.shape == q_new.shape, f"neue URL braucht eine andere QR-Version ({q_new.shape} statt {q_old.shape})"
    os.makedirs(DST, exist_ok=True)
    rows, thumbs, bad, reps = [], [], [], []
    name = {S.PRINT_QR_URL: "Telegram", S.SOCIAL_QR_URL: "Rickroll", "": "-"}
    for n in range(1, 65):
        out, r, (a, b) = swap(n, q_old, q_new)
        Image.fromarray(out).save(os.path.join(DST, f"{n:02d}.png"))
        ok = r["ncc_new"] - r["ncc_old"] > MIN_NCC_GAIN and r["dec_after"] == S.SOCIAL_QR_URL
        bad += [] if ok else [n]
        reps.append(r)
        rows.append(f"{n:02d}  Lage {r['how']} {r['shift'][0]:+6.2f} {r['shift'][1]:+6.2f} Feld {r['field']:4.2f}  "
                    f"Modell R2 {r['r2']:.3f}  "
                    f"Halo {r['halo']:.2f}  nachher neu {r['ncc_new']:.3f} / alt {r['ncc_old']:.3f}  "
                    f"QR vorher {name.get(r['dec_before'], '?'):9s}nachher {name.get(r['dec_after'], '?')}"
                    f"{'' if ok else '  << PRUEFEN'}")
        print(rows[-1], flush=True)
        thumbs.append(np.concatenate([a, b], 1))
    grid = np.concatenate([np.concatenate(thumbs[i:i + 8], 1) for i in range(0, 64, 8)])
    Image.fromarray(grid).save(os.path.join(P.DIR, "social_qr.png"))
    nr = sum(r["dec_after"] == S.SOCIAL_QR_URL for r in reps)
    nt = sum(r["dec_before"] == S.PRINT_QR_URL for r in reps)
    summary = f"lesbar: vorher {nt}/64 Telegram, nachher {nr}/64 Rickroll; pruefen: {bad or 'keine'}"
    rep = os.path.join(KL.PROJECT, "previz", "review", "F17BS", "social_qr.txt")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    open(rep, "w").write("\n".join(rows) + f"\n\n{summary}\n")
    print(summary)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
