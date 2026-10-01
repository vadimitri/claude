#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Musik des Kick-off-Loops, M2: nur IGOR, mit seinen eigenen Drums, und der Drop springt in den B-Teil mit Gesang.

Vadim 2.10. zu M1 (synthetische 808, 32tel-Hats): "zu ernst, zu trocken, harter Techno, kein Spass". M2 nimmt IGORs Drums
(Songzeit ab in_s, igor_beats.json) und legt Menschliches drueber: eine Klatsch-Menge, die waehrend des Aufbaus waechst
(Leute kommen dazu), Tamburin mit Swing, eine Marimba-Hook in IGORs Stimmung (D + tune_cents), Hall. Ablauf:

  Brummen (Intro) → IGORs Drums (je Variante: hinter der Wand / pur / mit IGORs eigenem Stopp) → Spannung (Stutter auf
  Triolen, Riser) → Stillstand mit Marimba-Lauf → DROP = Sprung auf einen Downbeat im B-Teil (~46-49 s, Tyler singt)
  → das Original laeuft unter der Endkarte, Claps/Tamburin/Hook nur dort, wo Tyler gerade nicht singt (gemessen).

  uv run src/kickoff_loop_music.py [toml]   (Standard kickoff_loop/previz/review/M2a.toml, Abschnitt [mashup])
  → kickoff_loop/ref/audio/mashup_M2{a,b,c}.wav + .json (Raster fuers Video), boil_test.wav
    kickoff_loop/previz/music/mashup_M2{a,b,c}.m4a + boil_test.m4a (-14 LUFS) + report.txt (Befunde)

Das Video importiert dieses Modul (decode, lufs, write_wav, SR): die Namen bleiben.
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
CONFIG = os.path.join(PROJECT, "previz", "review", "M2a.toml")
AUDIO = os.path.join(PROJECT, "ref", "audio")
OUT = os.path.join(PROJECT, "previz", "music")
SR = A.SR                                 # 48 kHz wie igor_beats.json (Songzeit = Sample-Index / 48000)
PEAK = 0.89                               # -1 dBFS: Spitzenpegel der WAV
D1_HZ = 36.7081                           # D1 bei A4 = 440 Hz
HEAR_LUFS = -14                           # Hoerversionen: Reel/Story-Norm
TRUE_PEAK_MAX = -1.0                      # dBTP-Grenze der Hoerversion (Streaming-Norm)
LIMIT = 0.79                              # Hoerversion: Limiter-Decke -2 dBFS, AAC legt ~1 dB Ueberschwinger drauf (Befund M1a)
VOCAL_HZ = (300, 3400)                    # Band, in dem Tylers Stimme liegt (Gate fuer eigene Elemente nach dem Drop)
HAT_HZ = (4000, 12000)                    # Band fuer die Raster-Messung am Sprung (Hats: scharfe Anschlaege)
ONSET_HOP = 48                            # 1 ms Aufloesung der Onset-Huellkurve
SEED = 2                                  # Zufall (Rauschen, menschliche Streuung), reproduzierbar
MIDI_D1 = 26


# ---------------------------------------------------------------- Konfiguration

def load(path):
    """[mashup] + IGOR-Raster lesen und pruefen, bevor gerendert wird."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    mx = cfg.get("mashup", {})
    for k in ("variants", "tune_cents", "end_bars", "hook", "swing_frac", "clap_people"):
        assert k in mx, f"{path}: [mashup].{k} fehlt (M2-Format, siehe previz/review/M2a.toml)"
    grid = json.load(open(os.path.join(AUDIO, "igor_beats.json")))
    burst = cfg["endcard"]["burst_beats"]
    for v in mx["variants"]:
        for k in ("segments", "carousel", "land_bar", "stop_beats"):
            assert f"{v}_{k}" in mx, f"[mashup].{v}_{k} fehlt"
        bars = sum(b for _, b, _ in mx[f"{v}_segments"])
        assert sum(b for _, b in mx[f"{v}_carousel"]) == bars, \
            f"[mashup].{v}_carousel: Summe der Takte muss {bars} sein (= Takte der Segmente, Drop am Ende)"
        assert mx[f"{v}_stop_beats"] >= burst, f"[mashup].{v}_stop_beats < [endcard].burst_beats ({burst})"
        for sb, b, fx in mx[f"{v}_segments"]:
            assert fx in ("raw", "wall", "build"), f"[mashup].{v}_segments: fx {fx!r} (raw | wall | build)"
            assert grid["in_s"] + sb * grid["bar_s"] >= 0, f"[mashup].{v}_segments: Takt {sb} liegt vor Songanfang"
        land = grid["in_s"] + mx[f"{v}_land_bar"] * grid["bar_s"]
        assert 40 < land < 60, f"[mashup].{v}_land_bar: Sprung auf {land:.2f} s, gewuenscht ~48 s (B-Teil)"
    return cfg, grid


# ---------------------------------------------------------------- Bausteine (vom Video mitbenutzt: decode, lufs, write_wav)

def n(t):
    return int(round(t * SR))


def decode(path):
    """Datei → float64 (Samples, 2) bei 48 kHz ueber ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def ebur(x):
    """(integrierte Lautheit LUFS, True Peak dBTP) ueber ffmpeg ebur128."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-af", "ebur128=peak=true", "-f", "null", "-"], input=x.astype("<f4").tobytes(),
                       capture_output=True).stderr.decode()
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]), float(re.findall(r"Peak:\s+(-?[\d.inf]+) dBFS", r)[-1])


def lufs(x):
    return ebur(x)[0]


def write_wav(path, x):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s24le", path], input=x.astype("<f4").tobytes(), check=True)


def declick(x, sec, start=True, end=True):
    k = min(n(sec), len(x) // 2)
    x = x.copy()
    if start:
        x[:k] *= np.linspace(0, 1, k)[:, None]
    if end:
        x[len(x) - k:] *= np.linspace(1, 0, k)[:, None]
    return x


def put(buf, t, s, g=1.0, pan=0.0):
    """Mono-Schlag s bei Sekunde t in den Stereo-Puffer (Pan -1..1, gleiche Leistung)."""
    i = n(t)
    if i >= len(buf) or i < 0:
        return
    s = s[:len(buf) - i] * g
    buf[i:i + len(s), 0] += s * np.sqrt(1 - pan)
    buf[i:i + len(s), 1] += s * np.sqrt(1 + pan)


def hz(midi, cents):
    return D1_HZ * 2 ** ((midi - MIDI_D1) / 12 + cents / 1200)


def marimba(f, vel=1.0):
    """Marimba: Grundton + die zwei typischen Obertoene (4x, ~10x) mit kurzen Abklingzeiten, Schlegel-Klick."""
    sec = 1.2
    t = np.arange(n(sec)) / SR
    dec = 0.55 * (440 / f) ** 0.4
    x = (np.sin(2 * np.pi * f * t) * np.exp(-t / dec)
         + 0.25 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t / (dec / 4))
         + 0.06 * np.sin(2 * np.pi * f * 9.2 * t) * np.exp(-t / (dec / 12)))
    x += A.bp(A.noise(sec), 1500, 5000) * np.exp(-t / 0.003) * 0.15
    return x * np.minimum(t / 0.001, 1) * vel


def clapper(rng):
    """Eine Person klatscht: eigenes Band (Handgroesse), 1-2 Vorschlaege, kurzer Ausklang."""
    c = rng.uniform(700, 2400)
    x = np.zeros(n(0.25))
    for k, dt in enumerate([0, rng.uniform(0.006, 0.012)][:rng.integers(1, 3)]):
        seg = A.bp(A.noise(0.25), c * 0.6, c * 1.6) * A.env(0.25, 0.0005, 0.01 if k == 0 else rng.uniform(0.02, 0.05))
        x[n(dt):] += seg[:len(x) - n(dt)]
    return x / np.abs(x).max()


def tambourine(rng):
    t = np.arange(n(0.2)) / SR
    x = np.zeros(len(t))
    for dt in rng.uniform(0, 0.012, 4):                       # Schellen schlagen leicht versetzt an
        x[n(dt):] += (A.hp(A.noise(0.2), 6500, 4) * np.exp(-t / 0.04))[:len(x) - n(dt)]
    return x / np.abs(x).max()


def riser(sec):
    """Rausch-Riser: Tiefpass faehrt von 300 Hz auf 6 kHz, Pegel steigt quadratisch."""
    x = A.sweep_lp(A.noise(sec), lambda s: 300 * (6000 / 300) ** (s / sec))
    t = np.arange(len(x)) / SR
    x = A.hp(x, 200) * (t / sec) ** 2
    return x / (np.abs(x).max() + 1e-9)


def swung(six_idx, six_s, swing):
    """16tel-Index → Zeit mit Swing: jede zweite 16tel um swing * 16tel spaeter."""
    return six_idx * six_s + (six_idx % 2) * swing * six_s


# ---------------------------------------------------------------- Song

def vocal_gate(song, t_song, sec, thr_db):
    """True, wenn Tyler im Fenster [t_song, +sec] leise ist (Band 300-3400 Hz unter thr_db dBFS RMS)."""
    seg = song[n(t_song):n(t_song + sec)].mean(1)
    if len(seg) < 64:
        return False
    v = A.bp(seg, *VOCAL_HZ)
    return 20 * np.log10(np.sqrt((v ** 2).mean()) + 1e-9) < thr_db


def build(cfg, grid, song, v):
    """Eine Variante: (Audio, Raster-Dict, Befund-Dict). Zeiten ab Videoanfang in Sekunden."""
    mx = cfg["mashup"]
    rng = np.random.default_rng(SEED)
    A.rng = rng
    bar, beat = grid["bar_s"], grid["beat_s"]
    six = bar / 16
    cents = mx["tune_cents"]
    segs = mx[f"{v}_segments"]
    impact = sum(b for _, b, _ in segs) * bar
    stop = mx[f"{v}_stop_beats"] * beat
    burst = impact - cfg["endcard"]["burst_beats"] * beat
    end = impact + mx["end_bars"] * bar
    land = grid["in_s"] + mx[f"{v}_land_bar"] * grid["bar_s"]
    x = np.zeros((n(end), 2))
    fx_buf = np.zeros((n(end), 2))                             # eigene Elemente (bekommen Hall)
    song_map, hits = [], []
    # ---- vor dem Drop: Song-Segmente auf dem Raster aneinander, je mit Effekt
    t = 0.0
    for sb, b, fx in segs:
        s0 = grid["in_s"] + sb * bar
        seg = song[n(s0):n(s0) + n(b * bar)].copy()
        if fx == "wall":                                       # Party nebenan: Tiefpass oeffnet sich ueber das Segment
            lo, hi = mx["wall_lp_hz"]
            seg = np.stack([A.sweep_lp(seg[:, c], lambda s: lo * (hi / lo) ** ((s / (b * bar)) ** 2)) for c in range(2)], 1)
        if fx == "build":                                      # Spannung: Stutter auf Triolen in der 2. Haelfte, Riser
            for k, (per, from_beat) in enumerate(((24, 2), (48, 3))):   # 16tel-Triolen ab Beat 3, 32tel-Triolen ab Beat 4
                step = bar / per
                a = n((b - 1) * bar + from_beat * beat)
                z = n((b - 1) * bar + (from_beat + 1) * beat)
                sl = declick(seg[a:a + n(step)], 0.002)
                for i in range(a, z, n(step)):
                    seg[i:i + len(sl)] = sl[:len(seg[i:i + len(sl)])] * (0.8 + 0.2 * k)
            r = np.resize(riser(b * bar), len(seg))
            seg += np.stack([r, r], 1) * mx["riser_gain"]
        seg = declick(seg, mx["fade_cut_s"]) * 10 ** (mx["pre_db"] / 20)
        x[n(t):n(t) + len(seg)] += seg
        song_map.append(dict(video_s=round(t, 4), song_s=round(s0, 4), bars=b, fx=fx))
        for h in grid["hits_s"]:
            if sb * bar <= h < (sb + b) * bar and t + h - sb * bar < impact - stop:
                hits.append(round(t + h - sb * bar, 4))
        t += b * bar
    # Stillstand: alles weg, nur der Hall der eigenen Elemente, dazu ein Marimba-Lauf auf 32tel-Triolen in den Drop
    x[n(impact - stop):n(impact)] = 0
    x[:n(impact - stop)] = declick(x[:n(impact - stop)], mx["fade_cut_s"], start=False)
    run = mx["run"]
    step = bar / 48
    for k, m in enumerate(run):
        put(fx_buf, impact - (len(run) - k) * step, marimba(hz(m, cents), 0.5 + 0.5 * k / len(run)), mx["hook_gain"],
            pan=0.5 * np.sin(k))
    # ---- Klatsch-Menge: waechst von clap_people[0] auf [1] Personen bis zum Stillstand, auf 2 und 4, menschlich gestreut
    start_bar = mx[f"{v}_claps_from_bar"]
    people = [clapper(rng) for _ in range(mx["clap_people"][1])]
    pans = rng.uniform(-0.7, 0.7, len(people))
    claps_until = impact - stop
    for bi in range(start_bar, int(round(impact / bar))):
        for bt in (1, 3):
            tc = bi * bar + bt * beat
            if tc >= claps_until:
                continue
            frac = (tc - start_bar * bar) / max(claps_until - start_bar * bar, 1e-6)
            cnt = int(round(mx["clap_people"][0] + frac * (mx["clap_people"][1] - mx["clap_people"][0])))
            for p in range(cnt):
                put(fx_buf, tc + rng.normal(0, mx["human_ms"] / 1000), people[p],
                    mx["clap_gain"] / np.sqrt(cnt) * rng.uniform(0.7, 1.0), pans[p])
    # ---- Hook im Aufbau (ab hook_from_bar, Marimba, Swing), nach dem Drop nur in Tylers Pausen
    hook_from = mx[f"{v}_hook_from_bar"]
    gated, played = 0, 0                                       # Hook-Toene unter Tyler: geprueft / gespielt
    for bi in range(hook_from, int(round(end / bar)), 2):         # Hook = 2 Takte in 16teln
        for s16, m, vel in mx["hook"]:
            tn = bi * bar + swung(s16, six, mx["swing_frac"]) + rng.normal(0, mx["human_ms"] / 1000)
            if impact - stop <= tn < impact or tn >= end - beat:
                continue
            g = vel * rng.uniform(0.85, 1.0)
            if tn >= impact:                                   # unter Tyler: nur wenn er gerade nicht singt
                gated += 1
                if not vocal_gate(song, land + tn - impact, 0.25, mx["vocal_thr_db"]):
                    continue
                g *= mx["hook_after_drop"]
                played += 1
            put(fx_buf, tn, marimba(hz(m, cents), g), mx["hook_gain"], pan=0.25 * np.sin(m))
    # ---- Tamburin: 8tel mit Swing ab dem Hook, nach dem Drop weiter (hoch, liegt ueber Tylers Stimme)
    tamb = [tambourine(rng) for _ in range(4)]
    for k in range(int(hook_from * 8), int(end / (bar / 8))):
        tt = swung(2 * k, six, mx["swing_frac"]) + rng.normal(0, mx["human_ms"] / 1000)
        if impact - stop <= tt < impact or tt >= end - beat:
            continue
        put(fx_buf, tt, tamb[k % 4], mx["tamb_gain"] * (1.0 if k % 2 else 0.55) * rng.uniform(0.8, 1), pan=0.4)
    # ---- Drop: Sprung in den B-Teil, Original laeuft; Claps auf 2 und 4, Crash + Marimba-Akkord auf der Eins
    drop = song[n(land):n(land) + n(end) - n(impact)]
    fo = n(mx["fade_out_beats"] * beat)
    drop = declick(drop, mx["fade_cut_s"], end=False)
    drop[-fo:] *= np.linspace(1, 0, fo)[:, None]
    x[n(impact):] += drop
    t_ = np.arange(n(2.5)) / SR
    crash = A.hp(A.noise(2.5), 5000, 2) * np.exp(-t_ / 0.8)
    put(fx_buf, impact, crash, mx["crash_gain"])
    for m in mx["drop_chord"]:
        put(fx_buf, impact, marimba(hz(m, cents)), mx["hook_gain"] * 0.8, pan=0.3 * np.sin(m))
    for bi in range(mx["end_bars"]):
        for bt in (1, 3):
            tc = impact + bi * bar + bt * beat
            if tc < end - beat:
                for p in range(mx["clap_people"][1]):
                    put(fx_buf, tc + rng.normal(0, mx["human_ms"] / 1000), people[p],
                        mx["clap_gain"] * mx["claps_after_drop"] / np.sqrt(mx["clap_people"][1]), pans[p])
    hits.append(round(impact, 4))
    wet = A.reverb(fx_buf, mx["reverb_s"])
    x += (fx_buf + mx["reverb_wet"] * wet) * 10 ** (mx["fx_db"] / 20)
    x *= PEAK / np.abs(x).max()
    carousel = mx[f"{v}_carousel"]
    changes, tc = [], 0.0
    for per, bars in carousel:
        changes += [round(tc + k * bar / per, 6) for k in range(per * bars)]
        tc += bars * bar
    name = f"M2{v}"
    info = dict(variant=name, file=f"ref/audio/mashup_{name}.wav", sr=SR, note=mx[f"{v}_note"],
                bpm_carousel=grid["bpm"], bpm_end=grid["bpm"], sixteenth_s=round(six, 6),
                triplet32_s=round(bar / 48, 6), carousel_bars=carousel, changes_s=changes,
                sixteenths_s=[round(k * six, 6) for k in range(int(round(impact / six)) + 1)],
                downbeats_s=[round(k * bar, 6) for k in range(int(round(end / bar)) + 1)],
                hits_s=sorted(hits), stop_s=round(impact - stop, 6), burst_s=round(burst, 6),
                drop_s=round(impact, 6), impact_s=round(impact, 6), end_s=round(end, 6),
                jump_song_s=round(land, 5), song_map=song_map + [dict(video_s=round(impact, 4), song_s=round(land, 4),
                                                                      bars=mx["end_bars"], fx="drop")],
                explain="Zeiten ab Videoanfang. drop_s = impact_s = Sprung in den B-Teil (jump_song_s, Songzeit). "
                        "stop_s = Stillstand beginnt (Musik weg, Marimba-Lauf), burst_s = Ausbruch. hits_s: IGORs "
                        "Drum-Hits im Video + Drop. song_map: welches Stueck Song wo im Video liegt.")
    return x, info, dict(hook_played=played, hook_gated=gated)


# ---------------------------------------------------------------- Pruefungen + Ausgabe

def grid_phase(song, a, b, in_s, six):
    """Phase des Songs zwischen a und b (Songzeit) gegen das 16tel-Raster aus igor_beats.json, in ms: Kamm-Fit. Die
    positive Pegel-Aenderung im Hat-Band (4-12 kHz, scharfe Anschlaege; die 808 gleitet im Tiefband) wird an allen 16teln
    + Versatz aufsummiert, der Versatz mit der groessten Summe gewinnt (-1/2..+1/2 16tel). Einzelne Onsets streuen zu sehr
    (Gesang, Zischlaute), der Kamm mittelt ueber alle 16tel des Fensters."""
    y = A.bp(song[n(a):n(b)].mean(1), *HAT_HZ)
    env = np.sqrt(np.convolve(y ** 2, np.ones(n(0.005)) / n(0.005), "same"))[::ONSET_HOP]
    flux = np.maximum(np.diff(np.log(env + 1e-5)), 0)
    fr = SR / ONSET_HOP
    k0 = np.ceil((a - in_s) / six)
    grid = in_s + six * np.arange(k0, k0 + int((b - a) / six) - 1)
    offs = np.arange(-int(six * 500), int(six * 500)) / 1000
    score = [flux[np.clip(((grid + o - a) * fr).astype(int), 0, len(flux) - 1)].sum() for o in offs]
    return 1000 * float(offs[int(np.argmax(score))])


def hear(wav, x, m4a):
    gain = HEAR_LUFS - lufs(x)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-af",
                    f"volume={gain:.2f}dB,alimiter=limit={LIMIT}:attack=1:release=50:level=false", "-c:a", "aac",
                    "-b:a", "256k", m4a], check=True)
    y = decode(m4a)
    lu, tp = ebur(y)
    clip = int((np.abs(y) >= 1.0).sum())
    return (f"  Hoerversion {os.path.relpath(m4a, PROJECT)}: {lu:.1f} LUFS, True Peak {tp:.1f} dBTP "
            f"({'ok' if tp <= TRUE_PEAK_MAX else 'UEBER ' + str(TRUE_PEAK_MAX)}), Samples >= 0 dBFS: {clip} "
            f"({'ok' if not clip else 'CLIPPING'})")


def boil_test(x, info, mx):
    """Boil-Test: Endkarte ab dem Drop, dazu ein trockener Tick auf jedem Boil-Wechsel (alle boil_on Bilder bei
    boil_fps, auf Zweiern = 12/s). Die Ticks liegen auf dem Bildraster, nicht auf dem Musikraster."""
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
    rep = [f"Musik M2 (IGORs Drums, Sprung in den B-Teil) · uv run src/kickoff_loop_music.py "
           f"{os.path.relpath(path, ROOT)}", "",
           f"Eigene Toene (Marimba) auf D {mx['tune_cents']:+d} c (IGOR-Brummen gemessen D2 +48..+65 c). "
           f"Tylers Gesang setzt nach dem B-Anfang (45.96 s) bei ~47.0 s ein (Band 300-3400 Hz +6 dB gegen davor).", ""]
    for v in mx["variants"]:
        x, info, st = build(cfg, grid, song, v)
        name = info["variant"]
        wav = os.path.join(AUDIO, f"mashup_{name}.wav")
        write_wav(wav, x)
        json.dump(info, open(os.path.join(AUDIO, f"mashup_{name}.json"), "w"), indent=1)
        lu, tp = ebur(x)
        land = info["jump_song_s"]
        ph = grid_phase(song, land, land + 4 * grid["bar_s"], grid["in_s"], grid["sixteenth_s"])
        ph0 = grid_phase(song, grid["in_s"], grid["in_s"] + 4 * grid["bar_s"], grid["in_s"], grid["sixteenth_s"])
        pre = lufs(x[n(info["impact_s"] - 2 * grid["bar_s"]):n(info["stop_s"])])
        post = lufs(x[n(info["impact_s"]):n(info["impact_s"] + 2 * grid["bar_s"])])
        segs = " | ".join(f"{s['video_s']:.2f} s: Song {s['song_s']:.2f} s x{s['bars']} {s['fx']}" for s in info["song_map"])
        rep += [f"{name}: {info['note']}",
                f"  Zeitachse (Video): {segs}",
                f"  Stillstand {info['stop_s']:.2f} s, Ausbruch {info['burst_s']:.2f} s, DROP {info['drop_s']:.3f} s "
                f"= Sprung auf Songzeit {land:.3f} s, Ende {info['end_s']:.2f} s",
                f"  Sprung-Phase (Kamm-Fit Hat-Band, 4 Takte): ab Songzeit {land:.2f} s {ph:+.0f} ms, IGORs Drums vor dem "
                f"Drop (ab in_s) {ph0:+.0f} ms, Differenz {ph - ph0:+.0f} ms "
                f"({'ok' if abs(ph - ph0) <= 20 else 'PRUEFEN'}, Grenze 20 ms ~ Raster-Streuung 19 ms)",
                f"  Lohnt sich: 2 Takte nach dem Drop {post:.1f} LUFS gegen 2 Takte davor {pre:.1f} LUFS "
                f"({post - pre:+.1f} LU)",
                f"  Hook nach dem Drop: {st['hook_played']} von {st['hook_gated']} Toenen gespielt, nur in Tylers Pausen "
                f"(Band 300-3400 Hz im Original unter {mx['vocal_thr_db']} dBFS)",
                f"  Karussell {' + '.join(f'{b}x{p}' for p, b in info['carousel_bars'])} (Takte x Wechsel) = "
                f"{len(info['changes_s'])} Wechsel; {len(info['hits_s'])} Hits",
                f"  WAV {lu:.1f} LUFS, True Peak {tp:.1f} dBTP, Spitze -1 dBFS statisch",
                hear(wav, x, os.path.join(OUT, f"mashup_{name}.m4a")), ""]
        if v == mx["variants"][0]:
            y, dt, times = boil_test(x, info, mx)
            bw = os.path.join(AUDIO, "boil_test.wav")
            write_wav(bw, y)
            rep += [f"Boil-Test {os.path.relpath(bw, PROJECT)}: Endkarte {name} ab Drop, {mx['boil_s']:g} s, "
                    f"{len(times)} Ticks alle {1000 * dt:.1f} ms ({1 / dt:g}/s = {mx['boil_fps']} fps auf "
                    f"{mx['boil_on']}ern)", hear(bw, y, os.path.join(OUT, "boil_test.m4a")), ""]
    open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8").write("\n".join(rep))
    print("\n".join(rep))


if __name__ == "__main__":
    sys.exit(main())
