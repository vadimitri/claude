"""Musik v1 fuer den Kick-off-Loop: der Intro-Synth aus IGOR'S THEME (Tyler, The Creator) nachgebaut, dazu die
Stop-Motion-Klicks, der Swoosh hinter dem Kopf und der Hit beim Wechsel ins Digitale.

Nachbau, kein Sample: die Aufnahme (kickoff_loop/ref/audio/, nicht im Git) wurde am 30.9. vermessen, gebaut wird aus
den Messwerten (HARM_DB, BANDS_DB), additiv in numpy. Befund der Messung (1-22 s, FFT 0.05 Hz Aufloesung):
  - ein einziger stehender Akkord, 23 s lang, keine Tonhoehenaenderung
  - alle Spitzen liegen auf der Obertonreihe von ~37.8 Hz: Grundton 75.6 (2.), Quinte (3.), Dezime (5.) = Dur-Akkord
  - jede Spitze ist dreifach aufgespalten (-5/0/+11 Cent): drei verstimmte Stimmen → langsame Schwebung ~2.5 s
  - unten steil, ab 500 Hz ein flaches Plateau (-16 bis -18 dB) aus Rauschen zwischen den Obertoenen ("Fizz")
  - Stereo-Korrelation 0.8 (breit, aber mono-kompatibel)

Aufruf ueber kickoff_loop_video.preview (schreibt music.wav in die Version). Werte: [audio] in loop.toml.
"""
import numpy as np
from scipy.signal import butter, sosfilt

RATE = 48000
# Obertonpegel in dB (relativ zum lautesten), Index 0 = 1. Oberton von root_hz. Gemessen an der Aufnahme.
HARM_DB = [-28, 0, -18, -6, -21, -20, -31, -20, -31, -25, -34, -24, -37, -28, -43, -27, -44, -29, -45, -30,
           -52, -31, -48, -31, -49, -34, -56, -32, -62, -38, -57, -34, -60, -58, -61, -34, -61, -59, -64, -35]
# Bandenergie der Aufnahme in dB relativ zum Band 60-120 Hz (Grundton). Das Rauschen fuellt, was die Obertoene nicht bringen.
BANDS_DB = [((250, 500), -13), ((500, 1000), -16), ((1000, 2000), -17), ((2000, 4000), -18), ((4000, 8000), -23),
            ((8000, 11000), -32)]
PAN_VOICES = (-0.35, 0.0, 0.35)          # drei Stimmen im Stereobild (ergibt Korrelation ~0.8 wie das Original)


def harm_db(k):
    """Pegel des k-ten Obertons (1-basiert). Ueber die Messung hinaus (k > 40) laeuft die Reihe mit -6 dB/Oktave weiter,
    ungerade Obertoene 10 dB leiser (so verhalten sie sich in der gemessenen Reihe auch)."""
    if k <= len(HARM_DB):
        return HARM_DB[k - 1]
    return -35 - 6 * np.log2(k / 40) - (10 if k % 2 else 0)


def pan(x, p):
    """Konstante Leistung: p = -1 links, 0 Mitte, 1 rechts."""
    a = (np.asarray(p) + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1)


def band_rms(x, lo, hi):
    sos = butter(4, [lo, min(hi, RATE / 2 - 100)], "band", fs=RATE, output="sos")
    return float(np.sqrt(np.mean(sosfilt(sos, x) ** 2)))


def drone(cfg, seconds, cutoff):
    """Der Synth: Obertonreihe von root_hz, jede Stimme verstimmt, Tiefpass als Pegel pro Oberton (additiv = exakt).
    cutoff: Array (Hz) pro Sample. Rueckgabe Stereo (n, 2), Grundton-Band bei ~0 dBFS-Relativpegel."""
    a = cfg["audio"]
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    rng = np.random.default_rng(38)
    out = np.zeros((n, 2))
    kmax = int(12000 / a["root_hz"])
    for cents, p in zip(a["detune_cents"], PAN_VOICES):
        f0 = a["root_hz"] * 2 ** (cents / 1200)
        voice = np.zeros(n)
        for k in range(1, kmax + 1):
            f = k * f0
            gain = 10 ** (harm_db(k) / 20) / np.sqrt(1 + (f / cutoff) ** 4)       # Tiefpass 2. Ordnung
            voice += gain * np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi))
        out += pan(voice, p)
    return out


def fizz(cfg, seconds, ref, cutoff):
    """Rauschplateau zwischen den Obertoenen: pro Messband so laut, dass Obertoene + Rauschen die gemessene Bandenergie
    ergeben (Analyse durch Synthese). ref = der Drone ohne Tiefpass, an ihm wird kalibriert."""
    n = int(seconds * RATE)
    rng = np.random.default_rng(11)
    mono = ref.mean(1)
    base = band_rms(mono, 60, 120)
    out = np.zeros((n, 2))
    for (lo, hi), db in BANDS_DB:
        want = base * 10 ** (db / 20)
        have = band_rms(mono, lo, hi)
        if want <= have:
            continue
        sos = butter(4, [lo, min(hi, RATE / 2 - 100)], "band", fs=RATE, output="sos")
        noise = sosfilt(sos, rng.standard_normal((n, 2)), axis=0)
        noise *= np.sqrt(want ** 2 - have ** 2) / noise.std()
        mid = np.sqrt(lo * hi)
        out += noise * (1 / np.sqrt(1 + (mid / cutoff) ** 4))[:, None]
    return out


def click(rng):
    """Stop-Motion-Klick: zwei kurze Transienten (Verschluss auf/zu, 28 ms), Bandpass 1.5-7 kHz."""
    n = int(0.06 * RATE)
    x = np.zeros(n)
    for at, g in ((0, 1.0), (int(0.028 * RATE), 0.6)):
        m = int(0.006 * RATE)
        x[at:at + m] += g * rng.standard_normal(m) * np.exp(-np.arange(m) / (0.0012 * RATE))
    return sosfilt(butter(2, [1500, 7000], "band", fs=RATE, output="sos"), x)


def swoosh(rng, dur):
    """Luftzug, der hinter dem Kopf von rechts nach links zieht: Rauschen, Bandpass faellt 3 kHz → 700 Hz (Doppler),
    Pegel steigt bis zur Mitte (Stern am naechsten) und faellt, Panorama rechts → links."""
    n = int(dur * RATE)
    u = np.linspace(0, 1, n)
    x = rng.standard_normal(n)
    y = np.zeros(n)
    blocks = np.array_split(np.arange(n), 48)                         # Filter blockweise nachfuehren
    zi = None
    for b in blocks:
        fc = 3000 * (700 / 3000) ** u[b[0]]
        sos = butter(2, [fc / 1.6, fc * 1.6], "band", fs=RATE, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        y[b], zi = sosfilt(sos, x[b], zi=zi)
    env = np.sin(np.pi * u) ** 2
    return pan(y * env / (np.abs(y).max() + 1e-9), 1 - 2 * u)


def hit(cfg, rng):
    """Synth-Hit beim Wechsel ins Digitale: Sub-Kick (120 → 38 Hz), Rauschschlag, und der Akkord eine Oktave hoeher
    als kurzer Stab (gleiche Obertonreihe, schneller Einschwinger, 1.4 s Ausklang)."""
    n = int(2.0 * RATE)
    t = np.arange(n) / RATE
    kick = np.sin(2 * np.pi * np.cumsum(38 + 82 * np.exp(-t / 0.045)) / RATE) * np.exp(-t / 0.35)
    noise = sosfilt(butter(2, 180, "high", fs=RATE, output="sos"), rng.standard_normal(n)) * np.exp(-t / 0.06) * 0.35
    stab = np.zeros(n)
    f0 = 2 * cfg["audio"]["root_hz"]
    for k in range(1, int(9000 / f0)):
        stab += 10 ** (harm_db(k) / 20) * np.sin(2 * np.pi * k * f0 * t + rng.uniform(0, 2 * np.pi))
    stab *= np.minimum(t / 0.004, 1) * np.exp(-t / 0.55) / (np.abs(stab).max() + 1e-9)
    return pan(0.9 * kick + noise, 0) + pan(0.7 * stab, -0.15) + pan(0.7 * stab, 0.15) * 0.8


def music(cfg, tl, path=None):
    """Ganze Spur zur Zeitachse tl (kickoff_loop_video.Timeline): Drone ab 0, Tiefpass oeffnet bis zum Wechsel ins
    Digitale, dort 150 ms Luftholen (Drone taucht ab), dann der Hit; Klick auf jedem Plakatwechsel, Swoosh bei jedem
    Loop-Neustart (Stern fliegt hinter dem Kopf herum). Ende: Drone klingt in 1 s aus. Rueckgabe Stereo float32."""
    a, fps = cfg["audio"], cfg["video"]["timeline_fps"]
    total = tl.total / fps
    n = int(total * RATE)
    t = np.arange(n) / RATE
    switch = tl.zoom_end / fps
    cutoff = np.where(t < switch, a["filter_start_hz"] * (16000 / a["filter_start_hz"]) ** np.clip(t / switch, 0, 1), 16000)
    body = drone(cfg, total, cutoff)
    body += fizz(cfg, total, drone(cfg, min(total, 4.0), np.full(int(min(total, 4.0) * RATE), 16000.0)), cutoff)
    body /= np.abs(body).max()
    gap = np.clip(np.abs(t - (switch - 0.075)) / 0.075, 0, 1) ** 2 * 0.9 + 0.1       # 150 ms Luftholen vor dem Hit
    fade = np.clip((total - t) / 1.0, 0, 1) * np.clip(t / 0.02, 0, 1)
    out = body * (gap * fade)[:, None]

    rng = np.random.default_rng(5)
    db = lambda v: 10 ** (v / 20)                                                    # noqa: E731
    for f, k in tl.changes:
        i = int(f / fps * RATE)
        c = click(rng) * db(a["tick_db"]) * (1.6 if k == 0 else 1)
        out[i:i + len(c)] += pan(c, rng.uniform(-0.2, 0.2))[:len(out) - i]
        if k == 0 and f > 0:                                                         # Neustart: hinter dem Kopf herum
            s = swoosh(rng, 0.6) * db(a["swoosh_db"])
            j = i - len(s) // 2
            out[max(j, 0):j + len(s)] += s[max(-j, 0):len(out) - j]
    h = hit(cfg, rng) * db(a["hit_db"])
    i = int(switch * RATE)
    out[i:i + len(h)] += h[:len(out) - i]

    out = sosfilt(butter(2, 25, "high", fs=RATE, output="sos"), out, axis=0)
    out = np.tanh(1.2 * out / np.abs(out).max()) / np.tanh(1.2)                     # Kleber, Spitzen rund
    out = (0.89 * out / np.abs(out).max()).astype(np.float32)                        # -1 dBFS Spitze
    if path:
        write_wav(path, out)
    return out


def write_wav(path, x):
    import wave
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
