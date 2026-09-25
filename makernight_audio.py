#!/usr/bin/env python3
"""Sounddesign + Musik fuer makernight.py, rein prozedural, sample-genau auf die Bild-Cues.

120 BPM, Beatraster ab 0,15 s -> Beat 16 = 8,15 s = Titel-Drop. Dm9-Farbe (dunkel, aber warm).
  uv run --with numpy --with scipy python makernight_audio.py      # -> makernight/makernight.wav + muxt alle MP4/MOV
"""
import glob
import os
import subprocess
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "makernight")
SR, DUR = 48000, 14.5
N = int(SR * DUR)
T = np.arange(N) / SR
BEAT, T0 = 0.5, 0.15
DROP, COLLAPSE = 8.15, 13.3
rng = np.random.default_rng(26)


def beat(n):
    return T0 + n * BEAT


def hz(midi):
    return 440 * 2 ** ((np.asarray(midi) - 69) / 12)


# ---------------------------------------------------------------- Bausteine

def lp(x, f, o=2):
    return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)


def hp(x, f, o=2):
    return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, o=2):
    return sosfilt(butter(o, [lo, hi], "band", fs=SR, output="sos"), x)


def sweep_lp(x, f_of_t, block=256):
    """Zeitvariabler Tiefpass: blockweise neue Koeffizienten (2. Ordnung, Zustand wird mitgenommen)."""
    out, zi = np.empty_like(x), np.zeros((1, 2))
    for i in range(0, len(x), block):
        f = float(np.clip(f_of_t(i / SR), 20, SR / 2.2))
        sos = butter(2, f, "low", fs=SR, output="sos")
        out[i:i + block], zi = sosfilt(sos, x[i:i + block], zi=zi)
    return out


def noise(sec):
    return rng.standard_normal(int(sec * SR))


def env(sec, attack, decay):
    t = np.arange(int(sec * SR)) / SR
    return np.minimum(t / max(attack, 1e-4), 1) * np.exp(-t / decay)


def saw(freq, sec, detune=0.0):
    t = np.arange(int(sec * SR)) / SR
    ph = (t * freq * (1 + detune) + rng.random()) % 1
    return 2 * ph - 1


class Bus:
    def __init__(self, n=N):
        self.x = np.zeros((n, 2))

    def add(self, sig, t0, gain=1.0, pan=0.0):
        i, n = int(round(t0 * SR)), len(self.x)
        if i >= n:
            return
        sig = sig[:n - i]
        if sig.ndim == 1:                                    # Equal-Power-Pan
            a = (pan + 1) * np.pi / 4
            sig = np.stack([sig * np.cos(a), sig * np.sin(a)], 1) * np.sqrt(2)
        self.x[i:i + len(sig)] += sig * gain


def reverb(x, sec=2.4, tone=6000, seed=1):
    """Faltungshall mit synthetischer IR: dekorreliertes, gefiltertes, exponentiell abklingendes Rauschen."""
    r = np.random.default_rng(seed)
    t = np.arange(int(sec * SR)) / SR
    ir = np.stack([lp(r.standard_normal(len(t)), tone) * np.exp(-t * 6.9 / sec) for _ in range(2)], 1)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]   # kurzer Predelay-Fade
    ir /= np.sqrt((ir ** 2).sum(0))
    return np.stack([fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], 1)


# ---------------------------------------------------------------- Instrumente

def kick(g=1.0):
    t = np.arange(int(0.55 * SR)) / SR
    f = 45 + 110 * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.28)
    click = hp(noise(0.55), 2000) * np.exp(-t / 0.004) * 0.35
    return np.tanh((body + click) * 1.8 * g)


def boom():
    """Zuendung: tiefer Sub mit Pitch-Drop, angezerrt, plus Rauschschlag."""
    t = np.arange(int(2.4 * SR)) / SR
    f = 32 + 60 * np.exp(-t / 0.12)
    sub = np.tanh(2.5 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t / 0.9)
    hit = lp(noise(2.4), 3500) * np.exp(-t / 0.08) * 0.5
    return sub + hit


def bell(freq, sec=2.2, decay=0.7):
    t = np.arange(int(sec * SR)) / SR
    parts = [(1, 1), (2.01, 0.45), (3.0, 0.25), (4.17, 0.12), (5.43, 0.06)]   # leicht inharmonisch = Glas/Metall
    return sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t / (decay / r ** 0.5)) for r, a in parts) \
        * np.minimum(t / 0.002, 1)


def pluck(freq, cutoff=2500, sec=0.35):
    x = saw(freq, sec) + saw(freq, sec, 0.006)
    t = np.arange(len(x)) / SR
    return lp(x, cutoff) * np.exp(-t / 0.11) * np.minimum(t / 0.002, 1)


def clap():
    x = np.zeros(int(0.4 * SR))
    for k, dt in enumerate((0, 0.011, 0.023)):
        i = int(dt * SR)
        seg = bp(noise(0.4), 900, 2600) * env(0.4, 0.001, 0.012 if k < 2 else 0.14)
        x[i:] += seg[:len(x) - i]
    return x


def hat(open_=False):
    return hp(noise(0.3), 7500, 4) * env(0.3, 0.0005, 0.12 if open_ else 0.028)


def snare(pitch=1.0):
    t = np.arange(int(0.25 * SR)) / SR
    tone = np.sin(2 * np.pi * 185 * pitch * t) * np.exp(-t / 0.05)
    return bp(noise(0.25), 400, 7000) * np.exp(-t / 0.09) + 0.5 * tone


def key_click():
    """Mechanische Taste: Anschlag + leiser Release 45 ms spaeter."""
    x = np.zeros(int(0.09 * SR))
    x += bp(noise(0.09), 1800, 5200) * env(0.09, 0.0003, 0.004)
    i = int(rng.uniform(0.038, 0.05) * SR)
    x[i:] += 0.4 * (bp(noise(0.09), 2500, 7000) * env(0.09, 0.0003, 0.003))[:len(x) - i]
    t = np.arange(len(x)) / SR
    return x + 0.15 * np.sin(2 * np.pi * rng.uniform(420, 520) * t) * np.exp(-t / 0.01)


# ---------------------------------------------------------------- Arrangement

CHORDS = [(0.7, [50, 57, 60, 64, 65]),                  # Dm9 (D A C E F)
          (DROP + 4 * BEAT, [46, 53, 57, 60, 62]),      # Bbmaj9
          (DROP + 8 * BEAT, [48, 55, 59, 62, 64])]      # C(add9) -> zieht nach oben


def chord_at(t):
    c = CHORDS[0][1]
    for t0, notes in CHORDS:
        if t >= t0:
            c = notes
    return c


def pad():
    """Detunte Saw-Wolke, Dm9 -> Filter oeffnet ueber die ganze Build-Phase, Akkordwechsel im Drop."""
    x = np.zeros((N, 2))
    for (t0, notes), t1 in zip(CHORDS, [c[0] for c in CHORDS[1:]] + [DUR]):
        a, b = int(t0 * SR), int(t1 * SR)
        for m in notes:
            for side, det in ((0, -0.004), (1, 0.004), (0, 0.0015), (1, -0.0015)):
                x[a:b, side] += saw(hz(m), (b - a + 1) / SR, det)[:b - a] * 0.06
    cut = lambda t: 350 + 900 * np.clip((t - 3) / 5, 0, 1) + 1400 * (t > DROP) * np.exp(-(t - DROP) / 1.5) + 500 * (t > DROP)
    x = np.stack([sweep_lp(x[:, c], cut) for c in range(2)], 1)
    swell = np.clip((T - 0.7) / 2.5, 0, 1) ** 2 * (0.55 + 0.45 * (T > DROP))
    return x * swell[:, None]


def build(music, fx):
    # Arp: 16tel ab Nest-Lock, Filter oeffnet sich mit dem Tunnel, im Drop voll
    step, i = BEAT / 4, 0
    t = beat(6)
    while t < COLLAPSE:
        c = chord_at(t)
        seq = [c[2] + 12, c[4] + 12, c[3] + 12, c[1] + 12, c[2] + 24, c[4] + 12, c[3] + 12, c[0] + 24]
        drop = t >= DROP
        g = 0.05 + 0.1 * np.clip((t - 3) / 5, 0, 1) + (0.07 if drop else 0)
        cutoff = 900 + 2600 * np.clip((t - 4.5) / 3.5, 0, 1) + (1500 if drop else 0)
        if not (7.9 <= t < DROP):                                # Luftloch vor dem Drop
            music.add(pluck(hz(seq[i % 8]), cutoff), t, g * (1 if i % 4 == 0 else 0.7), pan=0.35 * np.sin(i * 1.3))
        t, i = t + step, i + 1

    # Build: Kick in Vierteln, Snare-Roll 8tel -> 16tel -> 32tel, Riser
    for n in range(10, 16):
        if beat(n) < 7.9:
            music.add(lp(kick(0.8), 1200), beat(n), 0.3 + 0.06 * (n - 10))
    t = beat(12)
    while t < 7.95:
        rate = 2 if t < beat(14) else 4 if t < beat(15) else 8
        music.add(snare(1 + (t - beat(12)) * 0.25), t, 0.12 + 0.25 * (t - beat(12)) / 1.8, pan=rng.uniform(-0.2, 0.2))
        t += BEAT / rate
    rt = np.arange(int(3.05 * SR)) / SR
    riser = sweep_lp(noise(3.05), lambda s: 300 * 25 ** (s / 3.05)) * (rt / 3.05) ** 2
    ph = np.cumsum(110 * 8 ** (rt / 3.05)) / SR
    riser = riser + 0.25 * lp(2 * (ph % 1) - 1, 4000) * (rt / 3.05) ** 3
    fx.add(riser, 4.9, 0.55)
    rev = hp(noise(0.9), 3000)[::-1] * np.linspace(0, 1, int(0.9 * SR)) ** 3     # Reverse-Becken in den Drop
    fx.add(rev, DROP - 0.9, 0.35)

    # Drop: Four-on-the-floor, Offbeat-Bass, Clap 2+4, Hats
    for n in range(16, 26):
        tb = beat(n)
        if tb >= COLLAPSE:
            break
        music.add(kick(1.1), tb, 0.9)
        root = chord_at(tb)[0] - 12
        music.add(np.tanh(2 * lp(saw(hz(root), 0.22) + saw(hz(root), 0.22, 0.007), 420)) * env(0.22, 0.004, 0.12),
                  tb + BEAT / 2, 0.42)
        music.add(hat(open_=(n % 2 == 1)), tb + BEAT / 2, 0.16, pan=0.25)
        for q in (0.25, 0.75):
            music.add(hat(), tb + BEAT * q, 0.07, pan=-0.3)
        if n % 2 == 1:
            music.add(clap(), tb, 0.5)
    music.add(boom(), DROP, 0.7)                                 # Impact unter dem Titel


def sidechain():
    g = np.ones(N)
    for n in range(10, 26):
        tb = beat(n)
        if tb < 7.9 or tb >= DROP:
            d = np.clip(T - tb, 0, None)
            g *= 1 - (0.75 if tb >= DROP else 0.4) * np.exp(-d / 0.11) * (T >= tb)
    return g


def sfx(fx):
    # 0,3 s: Knistern zum Flackern des Funkens (jeder 3. Frame gedimmt)
    for f in range(9, 23):
        if f % 3 == 0:
            for _ in range(3):
                fx.add(hp(noise(0.02), 2500) * env(0.02, 0.0002, 0.002), f / 30 + rng.uniform(0, 0.03), 0.25,
                       pan=rng.uniform(-0.4, 0.4))
    # 0,7 s: Zuendung + drei Glastoene fuer die Echo-Ringe
    fx.add(boom(), 0.7, 0.85)
    for j, m in enumerate((81, 88, 93)):
        fx.add(bell(hz(m), 2.4, 0.9), 0.72 + 0.14 * j, 0.1, pan=(-0.5, 0.5, 0)[j])
    # 1,9-3,1 s: Nest dreht sich ein -> Whoosh mit Pan L -> R
    w = 1.35
    tt = np.arange(int(w * SR)) / SR
    wh = sweep_lp(noise(w), lambda s: 500 + 3500 * (s / w) ** 2) * np.sin(np.pi * tt / w) ** 2
    p = (tt / w) * 2 - 1
    a = (p + 1) * np.pi / 4
    fx.add(np.stack([wh * np.cos(a), wh * np.sin(a)], 1) * 1.2, 1.85, 0.4)
    fx.add(bell(hz(74), 2.5, 1.2), 3.05, 0.08)                   # Einrasten
    # 9,3-10,3 s: 13 Tastenanschlaege synchron zum Tippen
    for i in range(1, 14):
        fx.add(key_click(), 9.3 + i / 13 - 0.012, 0.5, pan=rng.uniform(-0.15, 0.15))
    # Kollaps: Reverse-Sog, dann letzter Funke als Glasping
    s = 0.8
    suck = sweep_lp(noise(s), lambda x: 6000 - 5200 * x / s) * np.linspace(0, 1, int(s * SR)) ** 2.5
    fx.add(suck, COLLAPSE, 0.45)
    fx.add(boom()[: int(0.8 * SR)] * np.linspace(1, 0, int(0.8 * SR)), 14.05, 0.45)
    fx.add(bell(hz(93), 1.2, 0.5), 14.05, 0.22)
    fx.add(bell(hz(100), 1.2, 0.4), 14.08, 0.08, pan=0.4)


def tape_stop(x, t0, sec=0.7):
    """Ab t0 wird die Musik wie ein angehaltenes Band langsamer und tiefer."""
    i0, n = int(t0 * SR), int(sec * SR)
    speed = (1 - np.linspace(0, 1, n)) ** 1.6
    pos = i0 + np.cumsum(speed)
    y = x.copy()
    for c in range(2):
        y[i0:i0 + n, c] = np.interp(pos, np.arange(N), x[:, c]) * np.linspace(1, 0, n) ** 0.5
    y[i0 + n:] = 0
    return y


def main():
    music, fx = Bus(), Bus()
    music.x += pad()
    build(music, fx)
    sfx(fx)
    gap = np.clip(np.abs(T - (7.92 + DROP) / 2) / 0.02 - (DROP - 7.92) / 0.04 + 1, 0.12, 1)   # Luftloch vor dem Drop
    build_dip = 1 - 0.3 * ((T > 5) & (T < DROP))
    m = music.x * (sidechain() * gap * build_dip)[:, None]
    m = m + 0.28 * reverb(m, 2.0, 5000)
    m = tape_stop(m, COLLAPSE + 0.05)
    f = fx.x + 0.45 * reverb(fx.x, 3.2, 7000, seed=2)
    mix = m + f
    mix[:, :] = hp(mix.T, 25).T                                  # DC/Rumpel weg
    mix = np.tanh(mix * 1.3) / np.tanh(1.3)                      # sanftes Clipping als Master-Glue
    mix *= np.clip((DUR - T) / 0.25, 0, 1)[:, None]              # Ende sauber
    mix *= 0.93 / np.abs(mix).max()
    os.makedirs(OUT, exist_ok=True)
    wav = os.path.join(OUT, "makernight.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())

    # Muxen: Loudness auf -14 LUFS (Instagram/YouTube), Video wird nur kopiert
    for v in sorted(glob.glob(os.path.join(OUT, "makernight_*x*.m*"))):
        if "_sound" in v:
            continue
        base, ext = os.path.splitext(v)
        acodec = ["-c:a", "pcm_s16le"] if ext == ".mov" else ["-c:a", "aac", "-b:a", "256k"]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", v, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", *acodec, "-af", "loudnorm=I=-14:TP=-1:LRA=9", "-ar", str(SR),
                        "-shortest", f"{base}_sound{ext}"], check=True)
    print(wav)


if __name__ == "__main__":
    main()
