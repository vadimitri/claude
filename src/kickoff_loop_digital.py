#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "qrcode", "scikit-image", "opencv-python-headless", "img2pdf"]
# ///
"""Kick-off Loop, digitale Endsequenz: der Stern gross zentral, frontal, stuelpt sich als 4D-Koerper durch sich selbst.

Stellschrauben: Abschnitt [digital] der Review-TOML (Kopie von loop.toml). Zwei Ansaetze, beide nahtlos per Konstruktion:
  droste  log-polarer Zoom: Schale j hat Radius R*q^(j-t) und Drehung 30*(j-t). Nach t=1 ist jede Schale genau ihre
          aeussere Nachbarin (Massstab 1/q, Drehung +30 Grad: Spitzen und Kerben tauschen pro Schale).
  sphaere Hypersphaere: jede Schale ist ein Breitenkreis auf einer Kugel, die sich dreht; stereografisch projiziert
          (rho = R*tan(theta/2)) waechst sie aus dem Kern, ueberquert den Umriss (Aequator), rast ins Unendliche (Nordpol)
          und kommt als innerste wieder. Auf der Rueckseite (theta > 90 Grad) zeigt sie die andere Tinte: umgestuelpt.
Stile: s33 (Matrjoschka: Schalenband, nach innen in Korn auslaufend), s19 (nur Umrisslinien, Rosette/Hoehenlinien).

  uv run src/kickoff_loop_digital.py sheet  [toml]   Kontaktbogen (Sekunden)
  uv run src/kickoff_loop_digital.py video  [toml]   alle Varianten als MP4 mit IGOR darunter
  uv run src/kickoff_loop_digital.py test   [toml]   Nahtlosigkeit am fertigen Bild: Frame 0 == Frame N
"""
import os, sys, subprocess, tomllib, hashlib
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import styles  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF_TOML = os.path.join(ROOT, "kickoff_loop/previz/review/D1.toml")
INRADIUS = 0.5   # Dreieck mit Umkreisradius 1 hat Inkreisradius 1/2: so liegt die Sternspitze bei d = 1


def load(path):
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    d = cfg.get("digital")
    if d is None:
        sys.exit(f"{path}: Abschnitt [digital] fehlt")
    need = ["size_px", "cell_px", "fps", "duration_s", "cycles", "R_frac", "spin_deg", "shells", "q_frac", "band_frac",
            "variants", "sheet_frames", "turns", "rot0_deg", "front_lvl", "back_lvl", "air_lvl", "fade_frac", "droste_exit", "audio", "audio_start_s"]
    miss = [k for k in need if k not in d]
    if miss:
        sys.exit(f"[digital] fehlt: {', '.join(miss)}")
    if not 0 < d["q_frac"] < 1:
        sys.exit("[digital].q_frac muss zwischen 0 und 1 liegen (Massstab zwischen zwei Schalen)")
    for v in d["variants"]:
        if v["mode"] not in ("droste", "sphaere") or v["style"] not in ("s33", "s19"):
            sys.exit(f"[digital].variants: unbekannt {v} (mode droste|sphaere, style s33|s19)")
        if v["pal"] not in styles.PALS or styles.lila(v["pal"]):
            sys.exit(f"[digital].variants: Palette {v['pal']} fehlt oder ist Lila (gehoert der Maker Night)")
    if d["cycles"] != int(d["cycles"]):
        sys.exit("[digital].cycles muss ganzzahlig sein, sonst ist der Loop nicht nahtlos")
    return d


def star_d(xx, yy, rot_deg):
    """Hexagramm-Abstand: < 1 innen, Spitzen bei 1, homogen vom Grad 1 (doppelter Abstand = doppelter Wert).
    Vereinigung zweier Dreiecke = Minimum ihrer Dreiecksabstaende (Maximum ueber die drei Kantennormalen)."""
    out = []
    for base in (-90.0, 90.0):                       # Dreieck mit Spitze oben bzw. unten
        a = np.radians(rot_deg + base + np.array([0.0, 120.0, 240.0]))
        proj = xx[..., None] * np.cos(a) + yy[..., None] * np.sin(a)
        out.append(proj.max(-1) / INRADIUS)
    return np.minimum(*out)


def shells(d, mode, t):
    """(Radius relativ zu R, Drehung Grad, Tiefe 0..1 innen->aussen, Rueckseite?) je Schale, aussen zuerst."""
    n, q, spin = d["shells"], d["q_frac"], d["spin_deg"]
    out = []
    if mode == "droste":
        for j in range(-3, n + 40):                  # j < 0: schon ueber den Rand, j gross: kleiner als eine Zelle
            s = j - t
            r = q ** s
            if r * d["R_frac"] * 2000 < 0.5:
                continue
            if r > d["droste_exit"]:                  # ueber den Austrittsradius: weg (ab dort nur noch Luft)
                continue
            out.append((r, spin * s, np.clip(s / n, 0, 1), False))
    else:
        for j in range(n):
            th = np.pi * ((j + t) / n % 1.0)          # Breitengrad: 0 = Kern (Suedpol), pi = Unendlich (Nordpol)
            r = np.tan(th / 2) if th < np.pi - 1e-6 else 1e6
            out.append((r, spin * 2 * th / np.pi, 1 - th / np.pi, th > np.pi / 2))
    return sorted(out, key=lambda s: -s[0])


def frame(d, var, n):
    """Ein Frame als Palettenindex (Displaypixel). n = Framenummer, Phase t = cycles * n / N."""
    W, H = d["size_px"]
    px = d["cell_px"]
    gw, gh = W // px, H // px
    N = round(d["fps"] * d["duration_s"])
    t = d["cycles"] * (n % N) / N
    yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float64)
    R = d["R_frac"] * min(gw, gh)
    X, Y = (xx + 0.5 - gw / 2) / R, (yy + 0.5 - gh / 2) / R
    rot0 = d["rot0_deg"] + 360.0 * d["turns"] * (n % N) / N   # Gesamtdrehung in der Bildebene, ganze 60-Grad-Schritte
    v = np.zeros((gh, gw))
    band, style = d["band_frac"], var["style"]
    pal = styles.hexpal(var["pal"])
    K = len(pal) - 1
    for r, rot, depth, back in shells(d, var["mode"], t):
        if r <= 0:
            continue
        s = star_d(X / r, Y / r, rot0 + rot)
        inside = s < 1
        if not inside.any():
            continue
        lvl = d["front_lvl"] if not back else d["back_lvl"]
        val = lvl[0] + (lvl[1] - lvl[0]) * (1 - depth) if var["mode"] == "droste" else lvl[0] + (lvl[1] - lvl[0]) * abs(1 - 2 * depth)
        if var["mode"] == "droste" and r > 1:     # Austritt: Schale blendet ueber dem Umriss zur Luft ab
            val = d["air_lvl"] + (val - d["air_lvl"]) * max(0.0, (d["droste_exit"] - r) / (d["droste_exit"] - 1))
        rim = s > 1 - band
        if style == "s19":                           # nur der Umriss jeder Schale
            v = np.where(inside & rim, val, np.where(inside, v * 0 + d["air_lvl"], v))
        else:                                        # Matrjoschka: Band, dann Luft, die nach innen in Korn auslaeuft
            fade = np.exp(-np.clip((1 - band) - s, 0, None) / d["fade_frac"])
            v = np.where(inside, np.where(rim, val, d["air_lvl"] + (val - d["air_lvl"]) * fade * 0.6), v)
    idx = styles.dither(v, K, "bayer4", px)
    return idx, pal


def rgb(idx, pal):
    return pal[idx].astype(np.uint8)


def sheet(d, cfg_path):
    W, H = d["size_px"]
    k = d["sheet_frames"]
    N = round(d["fps"] * d["duration_s"])
    th = 0.25
    tw, thh = int(W * th), int(H * th)
    rows = d["variants"]
    img = Image.new("RGB", (tw * k + 16 * (k + 1), (thh + 40) * len(rows) + 16), (12, 12, 12))
    dr = ImageDraw.Draw(img)
    for i, var in enumerate(rows):
        y = 16 + i * (thh + 40)
        dr.text((16, y), f"{var['code']}  {var['mode']} / {var['style']} / {var['pal']}", fill=(230, 230, 230))
        for j in range(k):
            n = j * N // k
            a = rgb(*frame(d, var, n))
            img.paste(Image.fromarray(a).resize((tw, thh), Image.NEAREST), (16 + j * (tw + 16), y + 20))
    out = os.path.join(os.path.dirname(cfg_path), "D1_sheet.png")
    img.save(out)
    print(out)


def audio_file(d):
    for p in (os.path.join(ROOT, d["audio"]), os.path.join(ROOT, "../kickoff-loop", d["audio"]),   # Ton ist gitignored:
              os.path.join(ROOT, "../../..", d["audio"])):                                        # Haupt-Worktree/Checkout
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def video(d, cfg_path):
    W, H = d["size_px"]
    N = round(d["fps"] * d["duration_s"])
    a = audio_file(d)
    only = sys.argv[3:] if len(sys.argv) > 3 else None
    for var in d["variants"]:
        if only and var["code"] not in only:
            continue
        out = os.path.join(os.path.dirname(cfg_path), f"D1_{var['code']}.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(d["fps"]), "-i", "-"]
        if a:
            cmd += ["-ss", str(d["audio_start_s"]), "-i", a, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-tune", "animation", out]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for n in range(N):
            p.stdin.write(rgb(*frame(d, var, n)).tobytes())
        p.stdin.close()
        p.wait()
        print(out, "(Ton: IGOR)" if a else "(OHNE Ton: Datei fehlt)")


def test(d):
    """Nahtlos: Frame N (= naechster Loop-Anfang, ohne Modulo gerechnet) muss Frame 0 pixelgleich sein. Schlaegt an,
    wenn cycles/turns nicht ganzzahlig sind oder die Schalen-Phase nicht genau eine Schale weiterrueckt."""
    N = round(d["fps"] * d["duration_s"])
    ok = True
    for var in d["variants"]:
        dd = dict(d, duration_s=d["duration_s"] * 2, cycles=d["cycles"] * 2, turns=d["turns"] * 2)  # Frame N ohne % N
        a, _ = frame(dd, var, 0)
        b, _ = frame(dd, var, N)
        diff = float((a != b).mean())
        ok &= diff < 1e-3
        print(f"{var['code']}: Frame 0 vs N Pixelabweichung {diff:.5f} {'OK' if diff < 1e-3 else 'FEHLER'}")
    # Gegenprobe: halbe Schale Versatz muss anschlagen
    var = d["variants"][0]
    dd = dict(d, duration_s=d["duration_s"] * 2, cycles=d["cycles"] * 2 + 1, turns=d["turns"] * 2)
    diff = float((frame(dd, var, 0)[0] != frame(dd, var, N)[0]).mean())
    print(f"Gegenprobe halbe Schale: {diff:.3f} {'schlaegt an' if diff > 0.01 else 'TEST BLIND'}")
    return ok and diff > 0.01


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sheet"
    path = sys.argv[2] if len(sys.argv) > 2 else DEF_TOML
    d = load(path)
    if cmd == "sheet":
        sheet(d, path)
    elif cmd == "video":
        video(d, path)
    elif cmd == "test":
        sys.exit(0 if test(d) else 1)
