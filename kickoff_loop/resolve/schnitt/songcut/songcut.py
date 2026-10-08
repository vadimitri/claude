#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy", "pillow"]
# ///
"""Songschnitt: IGOR um ganze Takte kuerzen, ohne dass man die Naht hoert (Vadim 8.10.: Resolve-Remix kann das nicht).

Warum ganze Takte im 4er-Abstand: IGORs Drum-Loop wiederholt sich alle 4 Takte. Gemessen (log-Spektrum, 40 Baender, 1 Beat):
A1 gegen A2 an derselben Loop-Stelle 2.4-3.0 dB, ein beliebiger anderer Takt 5.7 dB. Ein 4-Takt-Sprung klingt also wie
durchgespielt, ein 3-Takt-Sprung wie ein Taktwechsel (Raster bleibt, Muster springt).
Verfahren je Schnitt: Sprung = bars x Takt, per Korrelation der Onset-Huelle auf +-fine_ms nachjustiert (der Song liegt
nicht exakt auf 81.606 BPM); Schnitt auf die staerkste Transiente nahe at_s gezogen, equal-power Crossfade endet kurz
davor (der Anschlag deckt die Naht, Vorwaertsmaskierung).

  uv run songcut.py <songcut.toml>        <out_dir>/<Code>.wav (beginnt auf Timeline-Bild 0), songcut.png, songcut.txt
  uv run songcut.py <songcut.toml> test   Selbsttest: Raster nach der Naht = Raster des Songs; Gegenprobe Sprung +1/3 16tel
"""
import json
import os
import subprocess
import sys
import tomllib

import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as ss
from PIL import Image, ImageDraw, ImageFont

PROJECT = "/Users/vadim/Developer/spark/motion-pack/kickoff_loop"
SR = 48000
HOP = 96                    # Onset-Huelle alle 2 ms
PRE_MS = 12                 # Crossfade endet so weit vor dem Huellen-Gipfel (Fenster 21 ms: der Gipfel liegt im Anschlag)
PHASE_GATE_MS = 8           # Raster nach der Naht darf so weit vom Songraster abweichen (16tel = 184 ms)


def load(path):
    c = tomllib.load(open(path, "rb"))
    g = json.load(open(os.path.join(PROJECT, c["grid"])))
    assert c["cut"], "[cut.<Code>] fehlt"
    for k, v in c["cut"].items():
        assert 0 < v["at_s"] < c["length_s"] - v["bars"] * g["bar_s"], f"[cut.{k}]: at_s liegt hinter dem Ende nach dem Sprung"
    c["bar_s"], c["s16"] = g["bar_s"], g["sixteenth_s"]
    c["in_tl"] = g["in_s"] - c["start_song_s"]                       # Taktstrich 1 auf der Timeline
    return c


def decode(c):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(PROJECT, c["source"]), "-ss", str(c["start_song_s"]),
                          "-t", str(c["length_s"]), "-ar", str(SR), "-ac", "2", "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def flux(x):
    f, t, Z = ss.stft(x.mean(1), SR, nperseg=1024, noverlap=1024 - HOP)
    M = np.log1p(np.abs(Z) * 50)
    return t[1:], np.maximum(0, np.diff(M, axis=1)).sum(0)


def logspec(x, a, d):
    f, t, Z = ss.stft(x.mean(1), SR, nperseg=2048, noverlap=2048 - 240)
    P, e = np.abs(Z) ** 2, np.geomspace(30, 16000, 41)
    L = 10 * np.log10(np.stack([P[(f >= lo) & (f < hi)].sum(0) for lo, hi in zip(e[:-1], e[1:])]) + 1e-10)
    return L[:, (t >= a) & (t < a + d)]


def true_bar(c, x):
    """Echte Taktlaenge: Onset-Huelle Takt 2-4 gegen 4 Takte spaeter (gleiche Loop-Stelle, Korrelation ~0.9), +-fine_ms.
    Ein 3-Takt-Sprung laesst sich nicht selbst justieren (verschiedene Takte, die Korrelation zog M4b um 18 ms daneben)."""
    tt, fl = flux(x)
    a, b, D0 = c["in_tl"] + c["bar_s"], c["in_tl"] + 3.75 * c["bar_s"], 4 * c["bar_s"]
    def corr(d):
        A, B = fl[(tt >= a) & (tt < b)], fl[(tt >= a + D0 + d) & (tt < b + D0 + d)]
        n = min(len(A), len(B))
        return np.corrcoef(A[:n], B[:n])[0, 1]
    lags = np.arange(-c["fine_ms"], c["fine_ms"] + 1, HOP / SR * 1000) / 1000
    return (D0 + lags[np.argmax([corr(d) for d in lags])]) / 4


def plan(c, x, cut, bar):
    """→ (Naht in der Ausgabe in Samples, Sprung in Samples)."""
    tt, fl = flux(x)
    D = cut["bars"] * bar
    w = (tt >= cut["at_s"] + D - c["snap_ms"] / 1000) & (tt <= cut["at_s"] + D + c["snap_ms"] / 1000)
    onset = tt[w][np.argmax(fl[w])]                                 # Transiente, die man nach der Naht hoert (Quelle B)
    return round((onset - D - PRE_MS / 1000) * SR), round(D * SR)


def render(c, x, seam, jump):
    n = round(c["xfade_ms"] / 1000 * SR)
    u = np.linspace(0, 1, n)[:, None] * np.pi / 2
    mix = x[seam - n:seam] * np.cos(u) + x[seam - n + jump:seam + jump] * np.sin(u)
    y = np.concatenate([x[:seam - n], mix, x[seam + jump:]])
    y[-round(0.01 * SR):] *= np.linspace(1, 0, round(0.01 * SR))[:, None]   # 10 ms Auslauf, Ende liegt im Stopp
    return y


def phase_ms(c, x, t0, t1):
    """Mittlere Lage der Anschlaege relativ zum 16tel-Raster des Songs (Kreismittel, Gewicht Flux^2)."""
    tt, fl = flux(x)
    m = (tt >= t0) & (tt < t1)
    ang = np.angle(np.sum(fl[m] ** 2 * np.exp(2j * np.pi * ((tt[m] - c["in_tl"]) / c["s16"] % 1))))
    return ang / (2 * np.pi) * c["s16"] * 1000


def seam_phase(c, x, y, seam, jump):
    """Raster-Abweichung nach der Naht gegen den Song (ms, gewrappt). Song: ab Takt 2 bis zum Stopp."""
    stop = c["length_s"] - 0.66                                     # Stopp = letzter Beat vor dem Ende der Quelle
    ref = phase_ms(c, x, c["in_tl"] + c["bar_s"], stop)
    got = phase_ms(c, y, seam / SR + 0.05, stop - jump / SR)
    return (got - ref + c["s16"] * 500) % (c["s16"] * 1000) - c["s16"] * 500


def sheet(c, x, outs, path):
    W, row, lm, sec = 1700, 110, 190, 1480 / c["length_s"]
    img = Image.new("RGB", (W, 40 + row * (1 + len(outs))), "white")
    d, font = ImageDraw.Draw(img), ImageFont.load_default(size=15)
    def X(s): return lm + int(s * sec)
    for r, (name, y, seam, jump) in enumerate([("Original", x, None, 0)] + outs):
        top = 40 + r * row
        mid, a = top + row // 2 - 8, np.abs(y.mean(1))
        for k in np.arange(-2, 12):                                  # Taktstriche (nach dem Sprung laufen sie weiter)
            t = c["in_tl"] + k * c["bar_s"]
            if 0 <= t <= len(y) / SR:
                d.line([X(t), top + 4, X(t), top + row - 20], fill=(215, 215, 215))
        for px in range(int(len(y) / SR * sec)):
            seg = a[int(px / sec * SR):int((px + 1) / sec * SR)]
            h = int(min(1, seg.max() * 1.6) * (row // 2 - 14)) if len(seg) else 0
            d.line([lm + px, mid - h, lm + px, mid + h], fill=(40, 40, 60))
        d.text((10, mid - 16), name, fill="black", font=font)
        d.text((10, mid + 2), f"{len(y) / SR:.2f} s", fill=(90, 90, 90), font=font)
        sh = jump / SR
        for t, lab in [(c["in_tl"] + 1.601, "Drums"), (c["in_tl"] + 13.78, "Run"), (c["length_s"] - 0.66, "Stopp")]:
            t = t if seam is None or t < seam / SR + 0.1 else t - sh
            d.text((X(t) + 3, top + row - 18), lab, fill=(0, 120, 60), font=font)
            d.line([X(t), top + row - 22, X(t), top + row - 4], fill=(0, 120, 60), width=2)
        if seam is not None:
            d.line([X(seam / SR), top + 2, X(seam / SR), top + row - 22], fill=(220, 30, 30), width=3)
        d.line([X(c["video_s"]), top + 2, X(c["video_s"]), top + row - 22], fill=(30, 90, 220), width=2)
    d.text((lm, 12), "rot = Naht   blau = Videoende F9/F10 (13.25 s)   grau = Taktstriche   gruen = Ereignisse", fill="black", font=font)
    img.save(path)


def main(path, test=False):
    c = load(path)
    x = decode(c)
    out = os.path.join(PROJECT, c["out_dir"])
    rep, outs, ok = [f"Quelle {c['source']} ab Songzeit {c['start_song_s']:.3f} s, {c['length_s']:.2f} s"], [], True
    bar = true_bar(c, x)
    rep.append(f"Takt gemessen {bar:.5f} s (Raster igor_beats.json {c['bar_s']:.5f} s)")
    for code, cut in c["cut"].items():
        seam, jump = plan(c, x, cut, bar)
        y = render(c, x, seam, jump)
        err = seam_phase(c, x, y, seam, jump)
        ctx = np.abs(logspec(x, seam / SR - 0.735, 0.735) - logspec(x, (seam + jump) / SR - 0.735, 0.735)).mean()
        k = round((seam / SR - c["in_tl"]) / c["s16"])
        pos = f"{1 + k // 16}.{1 + k % 16 // 4}.{1 + k % 4}"
        ok &= abs(err) <= PHASE_GATE_MS
        rep.append(f"{code}: {cut['note']}\n  Naht {seam / SR:.3f} s (Takt {pos}), Sprung {jump / SR:.4f} s "
                   f"(Raster {cut['bars'] * c['bar_s']:.4f}), Laenge {len(y) / SR:.2f} s, Stopp bei {c['length_s'] - 0.66 - jump / SR:.2f} s\n"
                   f"  Raster nach der Naht {err:+.1f} ms (Gate {PHASE_GATE_MS}) {'ok' if abs(err) <= PHASE_GATE_MS else 'FEHLER'}, "
                   f"Kontext davor {ctx:.2f} dB (gleiche Loop-Stelle ~2.5-3, anderer Takt ~5.7)")
        if test:                                                     # Gegenprobe: Sprung 1/3 16tel daneben muss anschlagen
            bad = round(c["s16"] / 3 * SR)
            e2 = seam_phase(c, x, render(c, x, seam, jump + bad), seam, jump + bad)
            ok &= abs(e2) > PHASE_GATE_MS
            rep.append(f"  Gegenprobe Sprung +{bad / SR * 1000:.0f} ms: Raster {e2:+.1f} ms {'schlaegt an' if abs(e2) > PHASE_GATE_MS else 'FEHLER: merkt nichts'}")
        else:
            wavfile.write(os.path.join(out, f"{code}.wav"), SR, y.astype(np.float32))
        outs.append((code, y, seam, jump))
    print("\n".join(rep))
    if not test:
        sheet(c, x, outs, os.path.join(os.path.dirname(os.path.abspath(path)), "songcut.png"))
        open(os.path.join(os.path.dirname(os.path.abspath(path)), "songcut.txt"), "w").write("\n".join(rep) + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1], test=sys.argv[2:] == ["test"])
