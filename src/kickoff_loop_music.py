#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Musik des Kick-off-Loops, M1 "neuer Song": nur IGOR. Brummen → Spannung → eigener Drop → Luft → Impact → Endkarte.

Das Brummen kommt aus IGORs Intro (Songzeit bis in_s, igor_beats.json). Ab in_s kaemen IGORs Drums: dort setzen eigene,
prozedural gebaute Drums ein, auf IGORs Raster (81.606 BPM) und Stimmung (808 und Impact-Sub auf D + tune_cents). Die Hats
laufen in 32tel-Triolen = 48 pro Takt = 16.32/s, genau das Bildtempo T16: das Karussell wird hoerbar.

  uv run src/kickoff_loop_music.py [toml]   (Standard kickoff_loop/previz/review/M1.toml, Abschnitt [mashup])
  → kickoff_loop/ref/audio/mashup_M1{a,b}.wav + .json (Raster fuers Video), boil_test.wav
    kickoff_loop/previz/music/mashup_M1{a,b}.m4a + boil_test.m4a (-14 LUFS) + report.txt (Befunde)
"""
import json
import os
import re
import subprocess
import sys
import tomllib

import numpy as np

import makernight_audio as A

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "kickoff_loop")
CONFIG = os.path.join(PROJECT, "previz", "review", "M1.toml")
AUDIO = os.path.join(PROJECT, "ref", "audio")
OUT = os.path.join(PROJECT, "previz", "music")
SR = A.SR                                 # 48 kHz wie igor_beats.json (Songzeit = Sample-Index / 48000)
STEPS = 48                                # Schritte pro Takt: 32tel-Triolen = 4 Viertel x 12 (16.32/s bei 81.6 BPM = T16)
PEAK = 0.89                               # -1 dBFS: Spitzenpegel der WAV
D1_HZ = 36.7081                           # D1 bei A4 = 440 Hz
HEAR_LUFS = -14                           # Hoerversionen: Reel/Story-Norm, als reine Verstaerkung
TRUE_PEAK_MAX = -1.0                      # dBTP-Grenze der Hoerversion (Streaming-Norm)
LIMIT = 0.79                              # Hoerversion: Limiter-Decke -2 dBFS, AAC legt ~1 dB Ueberschwinger drauf (Befund M1a)
ONSET_FRAC = 0.5                          # Anschlag = Huellkurve erreicht 50 % des lokalen Maximums (wie igor_beats.json)
HAT_BAND_HZ = 6000                        # Befund Raster: Hats liegen ueber 6 kHz (hat() = Hochpass 7.5 kHz)
SEED = 2                                  # Zufall der Rausch-Instrumente, reproduzierbar


# ---------------------------------------------------------------- Konfiguration

def load(path):
    """[mashup] + IGOR-Raster lesen und pruefen, bevor gerendert wird."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    mx = cfg.get("mashup", {})
    for k in ("pre_bars", "build_bars", "drop_bars", "end_bars", "carousel", "tune_cents", "hat", "a_kick", "b_kick"):
        assert k in mx, f"{path}: [mashup].{k} fehlt (M1-Format, siehe previz/review/M1.toml)"
    grid = json.load(open(os.path.join(AUDIO, "igor_beats.json")))
    assert sum(b for _, b in mx["carousel"]) == mx["pre_bars"] + mx["drop_bars"], \
        "[mashup].carousel: Summe der Takte muss pre_bars + drop_bars sein (Impact = Ende des Karussells)"
    bad = [p for p, _ in mx["carousel"] if STEPS % p and 16 % p]
    assert not bad, f"[mashup].carousel: {bad} Wechsel pro Takt passen weder auf 16tel noch auf 32tel-Triolen"
    assert mx["build_bars"] <= mx["pre_bars"], "[mashup].build_bars > pre_bars"
    assert mx["pre_bars"] * grid["bar_s"] <= grid["in_s"], "[mashup].pre_bars: so viel Intro hat IGOR nicht"
    for v in "ab":
        for inst in ("kick", "clap", "snare"):
            assert len(mx[f"{v}_{inst}"]) == STEPS, f"[mashup].{v}_{inst}: genau {STEPS} Zeichen (32tel-Triolen)"
    assert len(mx["hat"]) == STEPS, f"[mashup].hat: genau {STEPS} Zeichen"
    return cfg, grid


# ---------------------------------------------------------------- Bausteine

def n(t):
    return int(round(t * SR))


def decode(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def declick(x, sec):
    k = min(n(sec), len(x) // 2)
    x = x.copy()
    x[:k] *= np.linspace(0, 1, k)[:, None]
    x[len(x) - k:] *= np.linspace(1, 0, k)[:, None]
    return x


def put(buf, t, s, g=1.0, pan=0.0):
    """Mono-Schlag s bei Sekunde t in den Stereo-Puffer legen (Pan -1..1, gleiche Leistung)."""
    i = n(t)
    if i >= len(buf):
        return
    s = s[:len(buf) - i] * g
    buf[i:i + len(s), 0] += s * np.sqrt((1 - pan) / 2) * np.sqrt(2)
    buf[i:i + len(s), 1] += s * np.sqrt((1 + pan) / 2) * np.sqrt(2)


def kick808(hz, decay):
    """808-Kick, deren Ausklang auf hz steht (IGORs Stimmung): Pitch-Fall von hz+140 Hz, Klick, leicht angezerrt."""
    t = np.arange(n(decay * 4 + 0.05)) / SR
    f = hz + 140 * np.exp(-t / 0.025)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    click = A.hp(A.noise(len(t) / SR), 2500) * np.exp(-t / 0.003) * 0.3
    return np.tanh((body + click) * 1.6)


def impact_hit(hz):
    """Impact: Sub-Fall auf hz/2 + Rauschschlag (gleiche Bauart wie makernight_audio.boom, aber gestimmt)."""
    t = np.arange(n(2.4)) / SR
    f = hz / 2 + 70 * np.exp(-t / 0.12)
    sub = np.tanh(2.2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t / 0.9)
    return sub + A.lp(A.noise(2.4), 4000) * np.exp(-t / 0.1) * 0.6


def steps(pattern):
    """Muster → [(Schritt, Lautstaerke 0..1)]: x = 1, Ziffer = Ziffer/9, Punkt = nichts."""
    return [(k, 1.0 if c == "x" else int(c) / 9) for k, c in enumerate(pattern) if c != "."]


def drone(song, grid, mx, t0, length):
    """IGOR-Brummen ab Songzeit t0, ueber in_s hinaus als Schleife der letzten drone_loop_bars davor (dort spielt IGOR
    sonst Drums). Naht mit gleich-Leistungs-Ueberblendung."""
    a, b = grid["in_s"] - mx["drone_loop_bars"] * grid["bar_s"], grid["in_s"]
    xf = n(mx["loop_xfade_s"])
    out = song[n(t0):n(b) + xf].copy()                   # bis b + xf: das Ende blendet aus, waehrend die Schleife
                                                         # genau auf b (Taktstrich) einsetzt
    tile = song[n(a):n(b) + xf]
    w = np.sqrt(np.linspace(0, 1, xf))[:, None]
    while len(out) < n(length):
        head = tile.copy()
        out[-xf:] = out[-xf:] * w[::-1] + head[:xf] * w     # Schleifenstart = letzter Taktstrich, Ende klingt aus
        out = np.concatenate([out, head[xf:]])
    return out[:n(length)]


# ---------------------------------------------------------------- Song

def build(cfg, grid, song, v):
    """Eine Variante (v = 'a' | 'b'): (Audio, Raster-Dict, Hat-Zeiten). Zeiten ab Videoanfang in Sekunden."""
    mx = cfg["mashup"]
    rng = np.random.default_rng(SEED)
    A.rng = rng
    bar, beat = grid["bar_s"], grid["beat_s"]
    pre, drop_n, end_n = mx["pre_bars"], mx["drop_bars"], mx["end_bars"]
    t_drop = pre * bar
    impact = (pre + drop_n) * bar
    end = impact + end_n * bar
    burst = impact - mx["air_beats"] * beat
    t0 = grid["in_s"] - t_drop                                       # Songzeit von Videosekunde 0
    root = D1_HZ * 2 * 2 ** (mx["tune_cents"] / 1200)                # D2 + tune_cents
    # Brummen: bis zum Drop roh, im Drop weiter, in der Endkarte hinter Tiefpass
    dr = drone(song, grid, mx, t0, end)
    gap = mx[f"{v}_gap_beats"] * beat
    if gap:                                                          # a: Brummen bricht vor dem Drop ab (Luft)
        dr[n(t_drop - gap):n(t_drop)] = 0
        dr[:n(t_drop - gap)] = declick(dr[:n(t_drop - gap)], mx["fade_cut_s"])
    tail = dr[n(impact):].copy()
    dr[n(impact):] = np.stack([A.lp(tail[:, c], mx["drone_end_lp_hz"]) for c in range(2)], 1)
    drums = np.zeros((n(end), 2))
    verb_in = np.zeros((n(end), 2))
    hat_g = 10 ** (mx["hat_db"] / 20)
    hats = []
    step_s = bar / STEPS
    # Spannung: Hats auf jeder 32tel-Triole schwellen an (leise → voll), b zusaetzlich Snare-Wirbel
    b0 = (pre - mx["build_bars"]) * bar
    for k in range(int(round((t_drop - b0) / step_s))):
        t = b0 + k * step_s
        if t >= t_drop - gap:
            break
        ramp = (k * step_s / (t_drop - b0)) ** 2
        vel = steps(mx["hat"])[k % STEPS][1]
        put(drums, t, A.hat(), hat_g * vel * (0.15 + 0.85 * ramp), pan=0.3 * (-1) ** k)
        hats.append(t)
    if mx[f"{v}_roll"]:
        for k in range(int(round((t_drop - b0) / step_s))):          # 8tel- → 16tel- → 32tel-Triolen, steigend
            frac = k * step_s / (t_drop - b0)
            every = 8 if frac < 0.5 else 4 if frac < 0.75 else 2 if frac < 0.9 else 1
            if k % every == 0:
                put(drums, b0 + k * step_s, A.snare(1 + 0.3 * frac), 0.25 + 0.6 * frac ** 2)
    # Drop: Muster jeden Takt, Hats durchgehend
    kicks = []
    for bi in range(drop_n):
        tb = t_drop + bi * bar
        for k, vel in steps(mx["hat"]):
            t = tb + k * step_s
            if t < burst:
                put(drums, t, A.hat(), hat_g * vel, pan=0.3 * (-1) ** k)
                hats.append(t)
        for k, vel in steps(mx[f"{v}_kick"]):
            t = tb + k * step_s
            if t < burst:
                put(drums, t, kick808(root, mx[f"{v}_kick_decay_s"]), vel)
                kicks.append(t)
        for k, vel in steps(mx[f"{v}_clap"]):
            t = tb + k * step_s
            if t < burst:
                c = A.clap() * 1.4 * vel
                put(drums, t, c)
                put(verb_in, t, c)
        for k, vel in steps(mx[f"{v}_snare"]):
            t = tb + k * step_s
            if t < burst:
                put(drums, t, A.snare(), 0.35 * vel)
    # Luft vor dem Impact: alles, was ueber burst hinausklingt, hart weg; nur der Hall bleibt
    drums[n(burst):] = 0
    verb_in[:n(t_drop)] += drums[:n(t_drop)] * 0.3
    verb_in[n(t_drop):n(burst)] += drums[n(t_drop):n(burst)] * 0.25
    # Impact + Endkarte: gestimmter Schlag, Clap, dann Kick auf jeder Eins und leise Hats (Puls fuer die 16tel-Reveals)
    hit = impact_hit(root)
    put(drums, impact, hit, 1.2)
    put(drums, impact, A.clap(), 1.4)
    put(verb_in, impact, A.clap() * 1.6)
    kicks.append(impact)
    for bi in range(end_n):
        tb = impact + bi * bar
        if bi:
            put(drums, tb, kick808(root, mx[f"{v}_kick_decay_s"]), 0.8)
            kicks.append(tb)
        for k, vel in steps(mx["hat"]):
            put(drums, tb + k * step_s, A.hat(), hat_g * vel * 0.45 * (1 - (bi * STEPS + k) / (end_n * STEPS)))
    wet = A.reverb(verb_in, mx["reverb_s"])
    x = dr + (drums + 0.5 * wet) * 10 ** (mx["drums_db"] / 20)
    x = declick(x, mx["fade_cut_s"])
    d = mx["master_drive"]
    x = np.tanh(x * d) / np.tanh(d)
    x *= PEAK / np.abs(x).max()
    six = [round(k * bar / 16, 6) for k in range(16 * (pre + drop_n) + 1)]
    changes, t = [], 0.0
    for per, bars in mx["carousel"]:
        changes += [round(t + k * bar / per, 6) for k in range(per * bars)]
        t += bars * bar
    downs = [round(k * bar, 6) for k in range(pre + drop_n + end_n + 1)]
    name = f"M1{v}"
    info = dict(variant=name, file=f"ref/audio/mashup_{name}.wav", sr=SR, song_in_s=round(t0, 5),
                note={"a": "hart: 1 Beat Luft vor dem Drop, kurze 808, Clap auf 3",
                      "b": "rollend: Snare-Wirbel in der Spannung, Kick auf 8tel-Triolen (3 gegen 4), lange 808"}[v],
                bpm_carousel=grid["bpm"], bpm_end=grid["bpm"], sixteenth_s=round(bar / 16, 6),
                triplet32_s=round(step_s, 6), carousel_bars=mx["carousel"], changes_s=changes, sixteenths_s=six,
                downbeats_s=downs, drop_s=round(t_drop, 6), hits_s=[round(t, 4) for t in kicks if t < impact],
                burst_s=round(burst, 6), impact_s=round(impact, 6), end_s=round(end, 6),
                explain="Zeiten ab Videoanfang. carousel_bars [Wechsel pro Takt, Takte]; 48 = 32tel-Triolen "
                        "(triplet32_s). changes_s: jeder Plakatwechsel bis vor impact_s. drop_s = eigene Drums setzen "
                        "ein (= IGORs Drum-Einsatz in_s). hits_s: Kicks (Kamera-Stoss). burst_s = Luft/Ausbruch.")
    return x, info, hats


# ---------------------------------------------------------------- Pruefungen + Ausgabe

def ebur(x):
    """(integrierte Lautheit LUFS, True Peak dBTP) ueber ffmpeg ebur128."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-af", "ebur128=peak=true", "-f", "null", "-"], input=x.astype("<f4").tobytes(),
                       capture_output=True).stderr.decode()
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]), float(re.findall(r"Peak:\s+(-?[\d.inf]+) dBFS", r)[-1])


def pitch(x, lo, hi):
    m = x.mean(1) * np.hanning(len(x))
    N = 2 ** int(np.ceil(np.log2(len(m))) + 2)
    F, f = np.abs(np.fft.rfft(m, N)), np.fft.rfftfreq(N, 1 / SR)
    sel = np.nonzero((f > lo) & (f < hi))[0]
    i = sel[np.argmax(F[sel])]
    a, b, c = np.log(F[i - 1:i + 2])
    hz = (i + 0.5 * (a - c) / (a - 2 * b + c)) * SR / N
    return hz, 1200 * np.log2(hz / (D1_HZ * 2 ** round(np.log2(hz / D1_HZ))))


def onsets_vs_grid(x, times):
    """Raster-Treffer am fertigen Audio: Hat-Band (> 6 kHz) Huellkurve, Anschlag je erwartetem Schlag = steilster Anstieg
    in -10..+20 ms (die 50-%-Schwelle scheitert an leisen Hats im Ausklang der lauten davor: 61 ms Abstand).
    (Median, 95 %, Max |Abweichung| ms)."""
    h = A.hp(x.mean(1), HAT_BAND_HZ, 4)
    env = np.sqrt(np.convolve(h ** 2, np.ones(n(0.001)) / n(0.001), "same"))
    dev = []
    for t in times:
        i0, i1 = n(t - 0.010), n(t + 0.020)
        dev.append((i0 + np.argmax(np.diff(env[i0:i1]))) / SR - t)    # steilster Anstieg = Anschlag
    dev = np.abs(np.array(dev)) * 1000
    return float(np.median(dev)), float(np.percentile(dev, 95)), float(dev.max())


def period(x, a, b, lo, hi):
    """Staerkste Periode der Hat-Band-Huellkurve zwischen a und b s (Autokorrelation, lo..hi s): misst, ob der Puls
    hoerbar im Bildtempo liegt."""
    h = A.hp(x[n(a):n(b)].mean(1), HAT_BAND_HZ, 4)
    env = np.convolve(np.abs(h), np.ones(n(0.002)), "same")
    env -= env.mean()
    ac = np.fft.irfft(np.abs(np.fft.rfft(env, 2 * len(env))) ** 2)[:len(env)]
    i = n(lo) + np.argmax(ac[n(lo):n(hi)])
    return i / SR


def write(path, x, m4a=None):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s24le", path], input=x.astype("<f4").tobytes(), check=True)
    if m4a:
        gain = HEAR_LUFS - ebur(x)[0]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-af", f"volume={gain:.2f}dB,alimiter=limit={LIMIT}:attack=1:release=50:level=false", "-c:a", "aac",
                        "-b:a", "256k", m4a], check=True)
        y = decode(m4a)
        lu, tp = ebur(y)
        clip = int((np.abs(y) >= 1.0).sum())
        return (f"  Hoerversion {os.path.relpath(m4a, PROJECT)}: {lu:.1f} LUFS, True Peak {tp:.1f} dBTP "
                f"({'ok' if tp <= TRUE_PEAK_MAX else 'UEBER ' + str(TRUE_PEAK_MAX)}), Samples >= 0 dBFS: {clip} "
                f"({'ok' if not clip else 'CLIPPING'})")


def boil_test(x, info, mx):
    """Boil-Test: Endkarte ab dem Impact (M1a), dazu ein trockener Tick auf jedem Boil-Wechsel (alle boil_on Bilder bei
    boil_fps = 12/s auf Zweiern). Die Ticks liegen auf dem Bildraster, nicht auf dem Musikraster: man hoert, ob die
    12/s gegen die 16.32/s der Musik stehen."""
    a = n(info["impact_s"])
    y = x[a:a + n(mx["boil_s"])].copy()
    A.rng = np.random.default_rng(SEED)
    tick = A.bp(A.noise(0.03), 2500, 6000) * A.env(0.03, 0.0003, 0.004)
    tick *= 0.5 / np.abs(tick).max() * 10 ** (mx["boil_db"] / 20)
    dt = mx["boil_on"] / mx["boil_fps"]
    times = np.arange(0, mx["boil_s"] - 0.03, dt)
    for k, t in enumerate(times):
        put(y, t, tick, pan=0.4 * (-1) ** k)
    y = declick(y, mx["fade_cut_s"])
    return y * PEAK / np.abs(y).max(), dt, times


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else CONFIG
    cfg, grid = load(path)
    mx = cfg["mashup"]
    os.makedirs(OUT, exist_ok=True)
    song = decode(os.path.join(AUDIO, "igors_theme.mp3"))
    hz, c = pitch(song[n(2):n(22)], 60, 90)
    root = D1_HZ * 2 * 2 ** (mx["tune_cents"] / 1200)
    rep = [f"Musik M1 (neuer Song, nur IGOR) · uv run src/kickoff_loop_music.py {os.path.relpath(path, ROOT)}", "",
           f"Stimmung: IGOR-Brummen (Intro 2-22 s) D2 {hz:.2f} Hz {c:+.0f} c; eigene 808/Impact auf D2 "
           f"{mx['tune_cents']:+d} c = {root:.2f} Hz", ""]
    for v in "ab":
        x, info, hats = build(cfg, grid, song, v)
        name = info["variant"]
        wav = os.path.join(AUDIO, f"mashup_{name}.wav")
        json.dump(info, open(os.path.join(AUDIO, f"mashup_{name}.json"), "w"), indent=1)
        k_hz, k_c = pitch(x[n(info["drop_s"]):n(info["burst_s"])], 60, 90)
        lu, tp = ebur(x)
        drop_hats = [t for t in hats if info["drop_s"] <= t < info["burst_s"]]
        med, p95, mxd = onsets_vs_grid(x, drop_hats)
        per = period(x, info["drop_s"], info["burst_s"], 0.04, 0.1)
        rep += [f"{name}: {info['note']}",
                f"  Zeitachse: 0-{info['drop_s'] - mx['build_bars'] * grid['bar_s']:.2f} s Brummen, bis "
                f"{info['drop_s']:.2f} s Spannung, Drop {info['drop_s']:.2f} s, Luft {info['burst_s']:.2f} s, "
                f"Impact {info['impact_s']:.2f} s, Ende {info['end_s']:.2f} s ({grid['bpm']} BPM)",
                f"  Karussell {' + '.join(f'{b}x{p}' for p, b in mx['carousel'])} (Takte x Wechsel) = "
                f"{len(info['changes_s'])} Wechsel, {len(info['hits_s'])} Kicks als Stoesse",
                f"  WAV {lu:.1f} LUFS, True Peak {tp:.1f} dBTP, Spitze -1 dBFS statisch",
                f"  Drop tiefster Teilton 60-90 Hz: {k_hz:.2f} Hz {k_c:+.0f} c gegen D (Ziel IGOR +48..+65 c: "
                f"{'ok' if 40 <= k_c <= 70 else 'DANEBEN'})",
                f"  Raster: {len(drop_hats)} Hats im Drop, Anschlag vs 32tel-Triole Median {med:.1f} ms, 95 % "
                f"{p95:.1f} ms, max {mxd:.1f} ms ({'ok' if p95 <= 5 else 'DANEBEN'}, Grenze 95 % <= 5 ms)",
                f"  Puls (Autokorrelation Hat-Band im Drop): {1000 * per:.1f} ms = {1 / per:.2f}/s, Bildtempo "
                f"{1000 * info['triplet32_s']:.1f} ms = {1 / info['triplet32_s']:.2f}/s "
                f"({'ok' if abs(per - info['triplet32_s']) < 0.002 else 'ANDERER Puls'})",
                write(wav, x, os.path.join(OUT, f"mashup_{name}.m4a")), ""]
        if v == "a":
            y, dt, times = boil_test(x, info, mx)
            bw = os.path.join(AUDIO, "boil_test.wav")
            bp = period(y, 0, len(y) / SR, 0.05, 0.11)
            rep += [f"Boil-Test {os.path.relpath(bw, PROJECT)}: Endkarte M1a ab Impact, {mx['boil_s']:g} s, "
                    f"{len(times)} Ticks alle {1000 * dt:.1f} ms ({1 / dt:g}/s = {mx['boil_fps']} fps auf "
                    f"{mx['boil_on']}ern); gemessener Puls {1000 * bp:.1f} ms",
                    write(bw, y, os.path.join(OUT, "boil_test.m4a")), ""]
    open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8").write("\n".join(rep))
    print("\n".join(rep))


if __name__ == "__main__":
    sys.exit(main())
