#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Musik des Kick-off-Loops, M2: reiner IGOR-Zusammenschnitt. Brummen → IGORs Drums → DROP = Sprung in den B-Teil.

Vadim 2.10.: M1 (synthetische 808, 32tel-Hats) "zu ernst, zu trocken, harter Techno". M2 nimmt nur IGOR: das Brummen
aus dem Intro, seine Drums ab in_s (igor_beats.json), und auf dem Drop springt der Song auf einen Downbeat im B-Teil
(~46-49 s), wo Tyler singt; das Original laeuft unter der Endkarte weiter. Alle Schnitte liegen auf IGORs Taktstrichen.
Eigene Overlays (Klatschen, Tamburin, Marimba) sind raus (Vadim: "erst den IGOR-Zusammenschnitt raw", Entwurf in 6b0d667).

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
HEAR_LUFS = -14                           # Hoerversionen: Reel/Story-Norm
TRUE_PEAK_MAX = -1.0                      # dBTP-Grenze der Hoerversion (Streaming-Norm)
LIMIT = 0.79                              # Hoerversion: Limiter-Decke -2 dBFS, AAC legt ~1 dB Ueberschwinger drauf (Befund M1a)
HAT_HZ = (4000, 12000)                    # Band fuer die Raster-Messung am Sprung (Hats: scharfe Anschlaege)
ONSET_HOP = 48                            # 1 ms Aufloesung der Onset-Huellkurve
SEED = 2                                  # Zufall der Boil-Ticks, reproduzierbar


# ---------------------------------------------------------------- Konfiguration

def load(path):
    """[mashup] + IGOR-Raster lesen und pruefen, bevor gerendert wird."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    mx = cfg.get("mashup", {})
    for k in ("variants", "end_bars", "fade_out_beats", "fade_cut_s"):
        assert k in mx, f"{path}: [mashup].{k} fehlt (M2-Format, siehe previz/review/M2a.toml)"
    grid = json.load(open(os.path.join(AUDIO, "igor_beats.json")))
    burst = cfg["endcard"]["burst_beats"]
    for v in mx["variants"]:
        for k in ("segments", "carousel", "land_bar", "stop_beats"):
            assert f"{v}_{k}" in mx, f"[mashup].{v}_{k} fehlt"
        bars = sum(b for _, b, _ in mx[f"{v}_segments"])
        assert sum(b for _, b in mx[f"{v}_carousel"]) == bars, \
            f"[mashup].{v}_carousel: Summe der Takte muss {bars} sein (= Takte der Segmente, Drop am Ende)"
        stop = mx[f"{v}_stop_beats"]
        assert stop == 0 or stop >= burst, f"[mashup].{v}_stop_beats: 0 (kein Stillstand) oder >= burst_beats ({burst})"
        for sb, b, fx in mx[f"{v}_segments"]:
            assert fx in ("raw", "wall", "stutter"), f"[mashup].{v}_segments: fx {fx!r} (raw | wall | stutter)"
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


def build(cfg, grid, song, v):
    """Eine Variante: (Audio, Raster-Dict, Befund-Dict). Zeiten ab Videoanfang in Sekunden."""
    mx = cfg["mashup"]
    bar, beat = grid["bar_s"], grid["beat_s"]
    six = bar / 16
    segs = mx[f"{v}_segments"]
    impact = sum(b for _, b, _ in segs) * bar
    stop = mx[f"{v}_stop_beats"] * beat
    burst = impact - cfg["endcard"]["burst_beats"] * beat
    end = impact + mx["end_bars"] * bar
    land = grid["in_s"] + mx[f"{v}_land_bar"] * grid["bar_s"]
    x = np.zeros((n(end), 2))
    song_map, hits = [], []
    # ---- vor dem Drop: Song-Segmente auf dem Raster aneinander, je mit Effekt
    t = 0.0
    for sb, b, fx in segs:
        s0 = grid["in_s"] + sb * bar
        seg = song[n(s0):n(s0) + n(b * bar)].copy()
        if fx == "wall":                                       # Party nebenan: Tiefpass oeffnet sich ueber das Segment
            lo, hi = mx["wall_lp_hz"]
            seg = np.stack([A.sweep_lp(seg[:, c], lambda s: lo * (hi / lo) ** ((s / (b * bar)) ** 2)) for c in range(2)], 1)
        if fx == "stutter":                                    # IGORs letzter Beat zerhackt: 16tel-, dann 32tel-Triolen
            for per, from_beat in ((24, 2), (48, 3)):
                step = bar / per
                a = n((b - 1) * bar + from_beat * beat)
                z = n((b - 1) * bar + (from_beat + 1) * beat)
                sl = declick(seg[a:a + n(step)], 0.002)
                for i in range(a, z, n(step)):
                    seg[i:i + len(sl)] = sl[:len(seg[i:i + len(sl)])]
        seg = declick(seg, mx["fade_cut_s"]) * 10 ** (mx["pre_db"] / 20)
        x[n(t):n(t) + len(seg)] += seg
        song_map.append(dict(video_s=round(t, 4), song_s=round(s0, 4), bars=b, fx=fx))
        for h in grid["hits_s"]:
            if sb * bar <= h < (sb + b) * bar and t + h - sb * bar < impact - stop:
                hits.append(round(t + h - sb * bar, 4))
        t += b * bar
    if stop:                                                   # Stillstand: Stille bis zum Drop
        x[n(impact - stop):n(impact)] = 0
        x[:n(impact - stop)] = declick(x[:n(impact - stop)], mx["fade_cut_s"], start=False)
    # Drop: Sprung in den B-Teil, das Original laeuft unter der Endkarte, letzter Beat blendet aus
    drop = declick(song[n(land):n(land) + n(end) - n(impact)], mx["fade_cut_s"], end=False)
    fo = n(mx["fade_out_beats"] * beat)
    drop[-fo:] *= np.linspace(1, 0, fo)[:, None]
    x[n(impact):] += drop
    hits.append(round(impact, 4))
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
                        "stop_s = Stillstand beginnt (= impact_s, wenn keiner), burst_s = Ausbruch. hits_s: IGORs "
                        "Drum-Hits im Video + Drop. song_map: welches Stueck Song wo im Video liegt.")
    return x, info


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


def cuts(x, info):
    """Befund an den Schnitten: groesster Sample-Sprung +-2 ms um jede Schnittkante gegen den 99.9-%-Wert des ganzen
    Stuecks (> 1 = Knack-Verdacht), und Pegel des letzten Beats vor dem Drop gegen den davor (IGORs Stopp = still)."""
    jump = np.abs(np.diff(x, axis=0)).max(1)
    typ = np.percentile(jump, 99.9)
    at = [m["video_s"] for m in info["song_map"][1:]]
    worst = max(jump[n(c) - n(0.002):n(c) + n(0.002)].max() / typ for c in at)
    beat, imp = 60 / info["bpm_carousel"], info["impact_s"]

    def db(a, b):
        return 20 * np.log10(np.sqrt((x[n(a):n(b)] ** 2).mean()) + 1e-9)
    return (f"  Schnitte {', '.join(f'{c:.2f}' for c in at)} s: max. Sample-Sprung {worst:.2f}x des 99.9-%-Werts "
            f"({'ok, kein Knack' if worst <= 1 else 'KNACK?'}); letzter Beat vor dem Drop {db(imp - beat, imp):.1f} dBFS, "
            f"Beat davor {db(imp - 2 * beat, imp - beat):.1f}, erster Beat danach {db(imp, imp + beat):.1f}")


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
    rep = [f"Musik M2 (reiner IGOR-Schnitt, Sprung in den B-Teil) · uv run src/kickoff_loop_music.py "
           f"{os.path.relpath(path, ROOT)}", "",
           "B-Teil beginnt 45.963 s (Song-Takt 8); Tylers Gesang setzt bei ~47.0 s ein (Band 300-3400 Hz +6 dB gegen "
           "davor, gemessen 2.10.). Naechster Downbeat zu 48 s: 48.904 s (Takt 9), da singt er schon.", ""]
    for v in mx["variants"]:
        x, info = build(cfg, grid, song, v)
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
        segs = " | ".join(f"{m['video_s']:.2f} s: Song {m['song_s']:.2f} s x{m['bars']} {m['fx']}" for m in info["song_map"])
        rep += [f"{name}: {info['note']}",
                f"  Zeitachse (Video): {segs}",
                f"  {'Stillstand ' + format(info['stop_s'], '.2f') + ' s, ' if info['stop_s'] < info['impact_s'] else ''}"
                f"Ausbruch {info['burst_s']:.2f} s, DROP {info['drop_s']:.3f} s "
                f"= Sprung auf Songzeit {land:.3f} s, Ende {info['end_s']:.2f} s",
                f"  Sprung-Phase (Kamm-Fit Hat-Band, 4 Takte): ab Songzeit {land:.2f} s {ph:+.0f} ms, IGORs Drums vor dem "
                f"Drop (ab in_s) {ph0:+.0f} ms, Differenz {ph - ph0:+.0f} ms "
                f"({'ok' if abs(ph - ph0) <= 20 else 'PRUEFEN'}, Grenze 20 ms ~ Raster-Streuung 19 ms)",
                f"  Lohnt sich: 2 Takte nach dem Drop {post:.1f} LUFS gegen 2 Takte davor {pre:.1f} LUFS "
                f"({post - pre:+.1f} LU)",
                cuts(x, info),
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
