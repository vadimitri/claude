#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Musik des Kick-off-Loops als Mashup: IGOR-Brummen [→ IGOR-Beat] → Maker-Night-Drop auf dem Impact.

Alle Stellschrauben in kickoff_loop/loop.toml, Abschnitt [mashup]. Zwei Varianten zum Anhoeren:
  A  IGOR im Original ab dem Einstieg (Drone + Drum-Einsatz, dann Beat, 81.61 BPM) → Maker-Night-Drop
  B  nur das IGOR-Brummen aus dem Intro, ein Tiefpass oeffnet sich ueber das Karussell (120-BPM-Raster) → Drop

  uv run src/kickoff_loop_music.py      → kickoff_loop/ref/audio/mashup_{A,B}.wav + .json (Zeitraster fuer das Video)
                                          kickoff_loop/previz/music/mashup_{A,B}.m4a (-14 LUFS) + report.txt (Befunde)

Der Uebergang ist in beiden gleich und bewusst kein Crossfade (Vadim mag keine Standard-Effekte): das Abgeschnittene
endet hart ½ Beat vor dem Impact, in der "Luft" klingt nur sein Hall nach (so lang wie der Ausbruch im Bild), auf der
Eins setzt der Drop ein. Die Maker-Night-Musik wird dafuer neu synthetisiert (makernight_loop.arrangement), um
[mashup].maker_night_tune_cents verstimmt: IGOR liegt ~+53 Cent ueber D und bleibt so unangetastet (kein Resampling).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib

import numpy as np

import makernight_audio as A
import makernight_loop as ML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "kickoff_loop")
CONFIG = os.path.join(PROJECT, "loop.toml")
CACHE = os.path.join(PROJECT, "_cache")
AUDIO = os.path.join(PROJECT, "ref", "audio")
OUT = os.path.join(PROJECT, "previz", "music")
SR = A.SR                                 # 48 kHz wie der Song-Ausschnitt und die Maker-Night-Musik

MN_SEED = 26                              # Zufallsphasen der Saws: wie makernight_audio.rng, damit 0 Cent = loop_full.wav
MN_DRIVE = 1.3                            # Saettigung + Spitzenpegel wie makernight_loop.main (-1 dBFS)
PEAK = 0.89                               # -1 dBFS: Spitzenpegel der fertigen Datei (statisch, keine Dynamik veraendert)
D1_HZ = 36.7081                           # Referenz fuer die Tonhoehen-Befunde (D1, A4 = 440 Hz)
HEAR_LUFS = -14                           # Hoerversionen: Reel/Story-Norm, als reine Verstaerkung (kein loudnorm-Regler)
BUILD_HZ = (500, 8000)                    # Befund Tiefpass-Aufbau (B): Anteil der Mitten/Hoehen am Gesamtpegel
ONSET_FRAC = 0.5                          # Anschlag = Huellkurve erreicht 50 % ihres Maximums (wie igor_beats.json)


# ---------------------------------------------------------------- Konfiguration

def load(path=CONFIG):
    """[mashup] + Songraster lesen und pruefen, bevor irgendetwas gerendert wird."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    assert "mashup" in cfg, "loop.toml: Abschnitt [mashup] fehlt"
    mx = cfg["mashup"]
    grid = json.load(open(os.path.join(PROJECT, cfg["music"]["grid"])))
    for key in ("a_carousel", "b_carousel"):
        bad = [per for per, _ in mx[key] if per not in (8, 16)]
        assert not bad, f"[mashup].{key}: Wechsel pro Takt nur 8 oder 16, nicht {bad}"
    assert mx["a_pre_bars"] < sum(b for _, b in mx["a_carousel"]), \
        "[mashup].a_carousel: mehr Takte als a_pre_bars, sonst kommt der IGOR-Beat nie"
    drums = grid["in_s"] + grid["hits_s"][0]                        # erster Drum-Hit im Song (24.04 s)
    need = sum(b for _, b in mx["b_carousel"]) * 4 * A.BEAT
    assert mx["b_drone_from_s"] + need <= drums, \
        f"[mashup].b_drone_from_s: das Brummen reicht nur bis {drums:.2f} s (dann Drums), B braucht {need:.1f} s"
    assert mx["a_pre_bars"] * grid["bar_s"] <= grid["in_s"], "[mashup].a_pre_bars: so viel Song gibt es vor dem Einstieg nicht"
    lo, hi = mx["b_lp_hz"]
    assert 20 < lo < hi < SR / 2.2, "[mashup].b_lp_hz: [zu, offen] in Hz, aufsteigend, unter 21 kHz"
    return cfg, grid


# ---------------------------------------------------------------- Quellen

def decode(path):
    """Datei → float32 (Samples, 2) bei 48 kHz, ueber ffmpeg (Songzeit = Sample-Index / 48000 wie in igor_beats.json)."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def maker_night(cents):
    """Maker-Night-Loop (loop_full: Dm9 | Bbmaj9 | C | C mit Drums, 16 s) um `cents` verstimmt neu synthetisiert.

    Gleicher Code wie makernight_loop.main, nur hz() verschoben: Pads, Arp und Bass folgen der Stimmung, die Kick bleibt
    (Geraeusch, keine Tonhoehe). Zufallsphasen neu gesaet, damit das Ergebnis reproduzierbar ist. Gecacht nach
    Verstimmung + Quelltext der beiden Module (ein Lauf ~10 s)."""
    src = "".join(open(os.path.join(ROOT, "src", f), encoding="utf-8").read()
                  for f in ("makernight_audio.py", "makernight_loop.py"))
    key = hashlib.sha1(f"{cents!r}{src}".encode()).hexdigest()[:12]
    path = os.path.join(CACHE, f"makernight_{key}.npy")
    if os.path.exists(path):
        return np.load(path)
    A.rng = ML.rng = np.random.default_rng(MN_SEED)
    ML.hz = lambda m: A.hz(m) * 2 ** (cents / 1200)                               # noqa: E731
    x = ML.arrangement(True)
    x = np.tanh(x * MN_DRIVE) / np.tanh(MN_DRIVE)
    x *= PEAK / np.abs(x).max()
    os.makedirs(CACHE, exist_ok=True)
    np.save(path, x)
    return x


# ---------------------------------------------------------------- Bausteine

def n(t):
    return int(round(t * SR))


def declick(x, sec, start=True, end=True):
    """Lineare Mini-Blende an den Schnittkanten (Millisekunden, gegen den Knack), keine hoerbare Ueberblendung."""
    k = min(n(sec), len(x) // 2)
    x = x.copy()
    if start:
        x[:k] *= np.linspace(0, 1, k)[:, None]
    if end:
        x[len(x) - k:] *= np.linspace(1, 0, k)[:, None]
    return x


def air(pre, sec, cfg):
    """Die Luft vor dem Impact: nur der Hall des Abgeschnittenen (die letzten 4 * `sec` davor), `sec` lang, blendet
    zum Drop hin aus. Hall statt Stille, damit die Luft nach Absicht klingt und nicht nach Aussetzer."""
    mx = cfg["mashup"]
    last = pre[-n(sec * 4):]
    wet = A.reverb(np.concatenate([last, np.zeros((n(sec), 2))]), mx["air_reverb_s"])[len(last):]
    return declick(wet * mx["air_tail"], mx["fade_cut_s"], start=False)


def lufs(x):
    """Integrierte Lautheit (EBU R128) ueber ffmpeg ebur128."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-af", "ebur128", "-f", "null", "-"], input=x.astype("<f4").tobytes(), capture_output=True)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr.decode())[-1])


def pitch(x, lo, hi):
    """Staerkster Teilton zwischen lo und hi Hz (FFT, parabolisch verfeinert): (Hz, Cent gegen das naechste D)."""
    m = x.mean(1) * np.hanning(len(x))
    N = 2 ** int(np.ceil(np.log2(len(m))) + 2)
    F, f = np.abs(np.fft.rfft(m, N)), np.fft.rfftfreq(N, 1 / SR)
    sel = np.nonzero((f > lo) & (f < hi))[0]
    i = sel[np.argmax(F[sel])]
    a, b, c = np.log(F[i - 1:i + 2])
    hz = (i + 0.5 * (a - c) / (a - 2 * b + c)) * SR / N
    d = D1_HZ * 2 ** round(np.log2(hz / D1_HZ))
    return hz, 1200 * np.log2(hz / d)


def shift_cents(a, b, lo=100, hi=2000, span=150):
    """Transposition von b gegen a in Cent: Kreuzkorrelation der Log-Spektren auf einem 1-Cent-Raster (lo..hi Hz).
    Misst die Verschiebung des ganzen Klangs, unabhaengig davon, welcher Teilton gerade der lauteste ist."""
    def logspec(x):
        m = x.mean(1) * np.hanning(len(x))
        F = np.abs(np.fft.rfft(m))
        c = np.arange(0, round(1200 * np.log2(hi / lo)))
        s = np.log(np.interp(lo * 2 ** (c / 1200), np.fft.rfftfreq(len(m), 1 / SR), F) + 1e-9)
        return s - s.mean()
    sa, sb = logspec(a), logspec(b)
    lags = np.arange(-span, span + 1)
    return int(lags[np.argmax([np.dot(sa[span:-span], np.roll(sb, -k)[span:-span]) for k in lags])])


def carousel_grid(bar_s, carousel):
    """Taktstriche und 16tel des Karussells ab 0 (konstantes Tempo): (downbeats, sixteenths, Taktstriche der 16tel-Takte)."""
    bars = sum(b for _, b in carousel)
    downs = [k * bar_s for k in range(bars + 1)]
    fast = [k * bar_s for k, per in enumerate(p for p, b in carousel for _ in range(b)) if per == 16]
    return downs, [k * bar_s / 16 for k in range(16 * bars + 1)], fast


# ---------------------------------------------------------------- Varianten

def build(cfg, grid, song, mn, variant):
    """Eine Variante: (Audio, Zeitraster-Dict). Zeiten ab Videoanfang in Sekunden."""
    mx = cfg["mashup"]
    burst = cfg["endcard"]["burst_beats"]                                         # Luft = Ausbruch im Bild
    if variant == "A":
        bar_s, carousel = grid["bar_s"], mx["a_carousel"]
        t0 = grid["in_s"] - mx["a_pre_bars"] * bar_s                              # Songzeit von Videosekunde 0
        downs, six, _ = carousel_grid(bar_s, carousel)
        impact = downs[-1]
        gap = burst * bar_s / 4
        pre = song[n(t0):n(t0) + n(impact - gap)]
        hits = [h + mx["a_pre_bars"] * bar_s for h in grid["hits_s"] if h + mx["a_pre_bars"] * bar_s < impact - gap]
        info = dict(song_in_s=round(t0, 5), note="IGOR im Original ab song_in_s, Drop = Maker Night (neu gestimmt)")
    else:
        bar_s, carousel = 4 * A.BEAT, mx["b_carousel"]
        downs, six, fast = carousel_grid(bar_s, carousel)
        impact = downs[-1]
        gap = burst * A.BEAT
        t0 = mx["b_drone_from_s"]
        pre = song[n(t0):n(t0) + n(impact - gap)]
        lo, hi = mx["b_lp_hz"]
        dur = len(pre) / SR
        f_of_t = lambda t: lo * (hi / lo) ** ((t / dur) ** mx["b_lp_curve"])    # noqa: E731
        pre = np.stack([A.sweep_lp(pre[:, c], f_of_t) for c in range(2)], 1)
        hits = [t for t in fast if 0 < t < impact - gap]                         # kein Schlagzeug: Stoss auf jedem Durchgang
        info = dict(song_in_s=round(t0, 5), note="IGOR-Brummen aus dem Intro mit Tiefpass-Aufbau, Drop = Maker Night")
    mn_bar = 4 * A.BEAT
    end = impact + mx["end_bars"] * mn_bar
    downs = downs + [impact + k * mn_bar for k in range(1, mx["end_bars"] + 1)]
    pre = declick(pre, mx["fade_cut_s"])
    drop = mn[:n(end) - n(impact)]
    gain = 10 ** ((lufs(pre[-n(bar_s):]) + mx[f"{variant.lower()}_drop_db"] - lufs(drop)) / 20)
    x = np.zeros((n(end), 2))
    x[:len(pre)] = pre
    x[len(pre):n(impact)] = air(pre, n(impact) / SR - len(pre) / SR, cfg)[:n(impact) - len(pre)]
    x[n(impact):] = declick(drop * gain, mx["fade_cut_s"], start=False)
    x *= PEAK / np.abs(x).max()
    six = [round(t, 6) for t in six]
    return x, dict(variant=variant, file=f"ref/audio/mashup_{variant}.wav", sr=SR, **info,
                   bpm_carousel=round(240 / bar_s, 3), sixteenth_s=round(bar_s / 16, 6), bpm_end=round(60 / A.BEAT, 3),
                   carousel_bars=carousel, sixteenths_s=six, downbeats_s=[round(t, 6) for t in downs],
                   hits_s=[round(t, 4) for t in hits], burst_s=round(impact - gap, 6), impact_s=round(impact, 6),
                   end_s=round(end, 6),
                   explain="Zeiten ab Videoanfang. sixteenths_s: alle 16tel des Karussells von 0 bis einschliesslich "
                           "impact_s. burst_s = Beginn der Luft/des Ausbruchs (burst_beats vor dem Impact). "
                           "downbeats_s bis einschliesslich end_s. hits_s: Kamera-Stoss.")


# ---------------------------------------------------------------- Pruefungen + Ausgabe

def checks(x, t):
    """Befunde am fertigen Audio: Laenge, Lautheit, Impact auf dem Drop-Anschlag, Knackfreiheit an den Schnitten."""
    out = []
    ok_len = len(x) == n(t["end_s"])
    out.append(f"  Laenge {len(x) / SR:.4f} s = end_s {t['end_s']:.4f} s: {'ok' if ok_len else 'FALSCH'}")
    imp = n(t["impact_s"])
    env = np.sqrt(np.convolve((x ** 2).mean(1), np.ones(n(0.001)) / n(0.001), "same"))
    win = env[imp - n(0.02):imp + n(0.1)]
    onset = (np.argmax(win >= ONSET_FRAC * win.max()) - n(0.02)) / SR
    out.append(f"  Impact {t['impact_s']:.4f} s, Drop-Anschlag {1000 * onset:+.1f} ms daneben: "
               f"{'ok' if abs(onset) <= 0.010 else 'NICHT auf dem Anschlag'} (Grenze +-10 ms)")
    jump = np.abs(np.diff(x, axis=0)).max(1)
    typ = np.percentile(jump, 99.9)
    for name, at in (("Anfang", 0.0), ("Luft", t["burst_s"]), ("Ende", t["end_s"])):
        i = min(n(at), len(jump) - 1)
        w = jump[max(i - n(0.002), 0):i + n(0.002)].max()
        out.append(f"  Schnitt {name} {at:.3f} s: max. Sample-Sprung {w:.4f} = {w / typ:.2f}x des 99.9-%-Werts im "
                   f"ganzen Stueck ({'ok' if w <= typ else 'KNACK?'})")
    step = jump[imp - 1]
    beat = jump[n(t["impact_s"] + 60 / t["bpm_end"]) - 3:n(t["impact_s"] + 60 / t["bpm_end"]) + 3].max()
    out.append(f"  Drop-Einsatz: Sample-Sprung {step:.4f}, auf Beat 2 des Drops {beat:.4f}: das ist der Kick-Anschlag "
               f"selbst ({'ok, kein Schnitt-Knack' if step <= 1.1 * beat else 'GROESSER als ein Kick: Knack?'})")
    bar_s = 240 / t["bpm_carousel"]
    last = x[n(t["burst_s"] - bar_s):n(t["burst_s"])]
    if t["variant"] == "B":                                                       # der Aufbau: wird es heller?
        def hi_db(seg):
            P, f = np.abs(np.fft.rfft(seg.mean(1))) ** 2, np.fft.rfftfreq(len(seg), 1 / SR)
            return 10 * np.log10(P[(f >= BUILD_HZ[0]) & (f < BUILD_HZ[1])].sum() / P.sum())
        gain = hi_db(last) - hi_db(x[:n(bar_s)])
        out.append(f"  Aufbau: Anteil {BUILD_HZ[0]}-{BUILD_HZ[1]} Hz im letzten Karussell-Takt {gain:+.0f} dB gegen den "
                   f"ersten ({'ok' if gain > 0 else 'wird NICHT heller'})")
    out.append(f"  Lautheit: ganz {lufs(x):.1f} LUFS, letzter Karussell-Takt {lufs(last):.1f}, Drop "
               f"{lufs(x[imp:]):.1f} LUFS (Datei statisch auf -1 dBFS Spitze)")
    return out


def write_wav(path, x):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s24le", path], input=x.astype("<f4").tobytes(), check=True)


def main():
    cfg, grid = load()
    mx = cfg["mashup"]
    os.makedirs(OUT, exist_ok=True)
    song = decode(os.path.join(PROJECT, "ref", "audio", "igors_theme.mp3"))
    mn = maker_night(mx["maker_night_tune_cents"])
    drone_hz, drone_c = pitch(song[n(2):n(22)], 60, 90)
    dr3_hz, dr3_c = pitch(song[n(2):n(22)], 140, 160)
    mn0 = maker_night(0)                                                          # = loop_full.wav (gleicher Code)
    moved = shift_cents(mn0[:n(4)], mn[:n(4)])
    rep = ["Musik-Mashup · uv run src/kickoff_loop_music.py · Stellschrauben loop.toml [mashup]", "",
           "Stimmung (staerkster Teilton, Cent gegen D, A4 = 440 Hz):",
           f"  IGOR-Brummen (Intro 2-22 s): D2 {drone_hz:.2f} Hz {drone_c:+.0f} c, D3 {dr3_hz:.2f} Hz {dr3_c:+.0f} c "
           f"(Cluster aus verstimmten Teiltoenen, D2 +48..+65 c, D3 +45..+55 c)",
           f"  Maker Night neu synthetisiert mit {mx['maker_night_tune_cents']:+d} c: gemessene Verschiebung gegen den "
           f"Nachbau bei 0 c {moved:+d} c (Log-Spektrum, Dm9, erste 4 s). Nachbau bei 0 c = loop_full.wav bis auf "
           f"2 LSB (geprueft 30.9.)", ""]
    summary = []
    for v in ("A", "B"):
        x, t = build(cfg, grid, song, mn, v)
        write_wav(os.path.join(AUDIO, f"mashup_{v}.wav"), x)
        json.dump(t, open(os.path.join(AUDIO, f"mashup_{v}.json"), "w"), indent=1)
        m4a = os.path.join(OUT, f"mashup_{v}.m4a")
        gain_db = HEAR_LUFS - lufs(x)                                             # linear: Aufbau → Drop bleibt, wie er ist
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(AUDIO, f"mashup_{v}.wav"), "-af",
                        f"volume={gain_db:.2f}dB", "-c:a", "aac", "-b:a", "256k", m4a], check=True)
        passes = sum(per * b for per, b in t["carousel_bars"]) / 16
        rep += [f"Variante {v}: {t['note']}",
                f"  Karussell {' + '.join(f'{b} Takt(e) {per}tel' for per, b in t['carousel_bars'])} bei "
                f"{t['bpm_carousel']} BPM = {passes:g} Durchgaenge a 16 Frames (minus {cfg['endcard']['burst_beats']} Beat"
                f" Ausbruch), Luft ab {t['burst_s']:.3f} s, Impact {t['impact_s']:.3f} s, Ende {t['end_s']:.3f} s "
                f"({mx['end_bars']} Takte Maker Night, {t['bpm_end']:g} BPM), {len(t['hits_s'])} Kamera-Stoesse"]
        rep += checks(x, t)
        rep.append(f"  Hoerversion {os.path.relpath(m4a, PROJECT)}: {lufs(decode(m4a)):.1f} LUFS")
        rep.append("")
        summary.append(f"{v}: {t['end_s']:.2f} s, Impact {t['impact_s']:.3f} s, {passes:g} Durchgaenge")
    open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8").write("\n".join(rep))
    print("\n".join(rep))
    print(" | ".join(summary))


if __name__ == "__main__":
    sys.exit(main())
