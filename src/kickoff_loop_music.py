#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Musik des Kick-off-Loops, M3: reiner IGOR-Schnitt, 16-20 s. Brumm-Einblende → IGORs Drums → Luft → DROP → Ausklang.

  Einblende  IGOR im Original ab einem Taktstrich vor seinem Drum-Einsatz (in_s): erst Brummen, dann setzen seine Drums
             ein, ohne Schnitt. Darauf ein Tiefpass, der sich oeffnet, und ein Lautstaerke-Fade, wie Variante B vom 30.9.
  Luft       das Material endet air_bars vor dem Drop, nur sein Hall klingt nach (wie die alte "Luft", air_tail/reverb)
  Drop       auf der Eins Sprung in den B-Teil (45.963 s, Tyler singt ab ~47.0 s), kurz Original
  Ausklang   Tiefpass schliesst und Pegel faellt auf null, waehrend das Bild in den Stern zoomt und auf Schwarz blendet

Vadim 2.10. zu M2: "M2a, aber alles kuerzer (16-20 s), Loop zu langsam, Brumm-Fade-in wie frueher, kleine Pause mit
Reverb, jetzt springt das zu sehr". Eigene Toene sind raus (M2-Runde: "Xylophon komplett raus").

  uv run src/kickoff_loop_music.py [toml]   (Standard kickoff_loop/previz/review/M3a.toml, Abschnitt [mashup])
  → kickoff_loop/ref/audio/mashup_M3{a,b}.wav + .json (Raster fuers Video)
    kickoff_loop/previz/music/mashup_M3{a,b}.m4a (-14 LUFS) + report.txt (Befunde)

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
CONFIG = os.path.join(PROJECT, "previz", "review", "M3a.toml")
AUDIO = os.path.join(PROJECT, "ref", "audio")
OUT = os.path.join(PROJECT, "previz", "music")
SR = A.SR                                 # 48 kHz wie igor_beats.json (Songzeit = Sample-Index / 48000)
PEAK = 0.89                               # -1 dBFS: Spitzenpegel der WAV
HEAR_LUFS = -14                           # Hoerversionen: Reel/Story-Norm
TRUE_PEAK_MAX = -1.0                      # dBTP-Grenze der Hoerversion (Streaming-Norm)
LIMIT = 0.79                              # Hoerversion: Limiter-Decke -2 dBFS, AAC legt ~1 dB Ueberschwinger drauf (Befund M1a)
HAT_HZ = (4000, 12000)                    # Band fuer die Raster-Messung am Sprung (Hats: scharfe Anschlaege)
ONSET_HOP = 48                            # 1 ms Aufloesung der Onset-Huellkurve


# ---------------------------------------------------------------- Konfiguration

def load(path):
    """[mashup] + IGOR-Raster lesen und pruefen, bevor gerendert wird."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    mx = cfg.get("mashup", {})
    for k in ("variants", "land_bar", "fade_cut_s", "lp_hz", "lp_curve", "air_tail", "air_reverb_s"):
        assert k in mx, f"{path}: [mashup].{k} fehlt (M3-Format, siehe previz/review/M3a.toml)"
    grid = json.load(open(os.path.join(AUDIO, "igor_beats.json")))
    lo, hi = mx["lp_hz"]
    assert 20 < lo < hi < SR / 2.2, "[mashup].lp_hz: [zu, offen] in Hz, aufsteigend, unter 21 kHz"
    land = grid["in_s"] + mx["land_bar"] * grid["bar_s"]
    assert 40 < land < 60, f"[mashup].land_bar: Sprung auf {land:.2f} s, gewuenscht B-Teil ~46-49 s"
    burst = cfg["endcard"]["burst_beats"] / 4
    for v in mx["variants"]:
        for k in ("from_bar", "bars", "fade_in_s", "lp_open_bars", "air_bars", "after_bars", "fade_out_bars"):
            assert f"{v}_{k}" in mx, f"[mashup].{v}_{k} fehlt"
        get = lambda k: mx[f"{v}_{k}"]                                        # noqa: E731
        assert isinstance(get("bars"), int) and get("bars") > 0, f"[mashup].{v}_bars: ganze Takte (Karussell)"
        assert grid["in_s"] + get("from_bar") * grid["bar_s"] >= 0, f"[mashup].{v}_from_bar: vor dem Songanfang"
        assert get("from_bar") + get("bars") <= mx["land_bar"], f"[mashup].{v}: Material ueberlappt den Sprung"
        assert burst <= get("air_bars") < get("bars"), \
            f"[mashup].{v}_air_bars: zwischen Ausbruch ({burst} Takt) und Laenge des Karussells"
        assert get("lp_open_bars") <= get("bars") - get("air_bars"), f"[mashup].{v}_lp_open_bars: laenger als Material"
        assert 0 < get("fade_out_bars") <= get("after_bars"), f"[mashup].{v}_fade_out_bars: 0 < fade <= after_bars"
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
    """Lineare Mini-Blende an den Schnittkanten (Millisekunden, gegen den Knack), keine hoerbare Ueberblendung."""
    k = min(n(sec), len(x) // 2)
    x = x.copy()
    if start:
        x[:k] *= np.linspace(0, 1, k)[:, None]
    if end:
        x[len(x) - k:] *= np.linspace(1, 0, k)[:, None]
    return x


def sweep(x, f_of_t):
    return np.stack([A.sweep_lp(x[:, c], f_of_t) for c in range(2)], 1)


def air(pre, sec, mx):
    """Die Luft vor dem Drop: nur der Hall des Abgeschnittenen (die letzten 4 * `sec` davor), `sec` lang, blendet zum
    Drop hin aus. Hall statt Stille, damit die Pause nach Absicht klingt und nicht nach Aussetzer (wie 30.9.)."""
    last = pre[-n(sec * 4):]
    wet = A.reverb(np.concatenate([last, np.zeros((n(sec), 2))]), mx["air_reverb_s"])[len(last):]
    return declick(wet * mx["air_tail"], mx["fade_cut_s"])        # auch vorn: das Material davor endet auf 0


# ---------------------------------------------------------------- Song

def build(cfg, grid, song, v):
    """Eine Variante: (Audio, Raster-Dict). Zeiten ab Videoanfang in Sekunden."""
    mx = cfg["mashup"]
    get = lambda k: mx[f"{v}_{k}"]                                            # noqa: E731
    bar, beat = grid["bar_s"], grid["beat_s"]
    impact = get("bars") * bar
    stop = impact - get("air_bars") * bar                                     # hier endet das Material, Luft beginnt
    end = impact + get("after_bars") * bar
    fade_from = end - get("fade_out_bars") * bar
    land = grid["in_s"] + mx["land_bar"] * bar
    s0 = grid["in_s"] + get("from_bar") * bar                                 # Songzeit von Videosekunde 0
    lo, hi = mx["lp_hz"]
    # Einblende: Original ab s0, Tiefpass oeffnet ueber lp_open_bars (Kurve > 1 = bleibt laenger dunkel), Pegel-Fade
    pre = song[n(s0):n(s0) + n(stop)].copy()
    t_open = get("lp_open_bars") * bar
    pre = sweep(pre, lambda t: lo * (hi / lo) ** (min(t / t_open, 1) ** mx["lp_curve"]) if t < t_open else hi)
    k = n(get("fade_in_s"))
    pre[:k] *= (np.linspace(0, 1, k) ** 2)[:, None]                           # quadratisch: leise Anfaenge bleiben leise
    pre = declick(pre, mx["fade_cut_s"], start=False)
    x = np.zeros((n(end), 2))
    x[:len(pre)] = pre
    x[len(pre):n(impact)] = air(pre, n(impact) / SR - len(pre) / SR, mx)[:n(impact) - len(pre)]
    # Drop + Ausklang: B-Teil im Original, im letzten Stueck schliesst der Tiefpass und der Pegel faellt auf null
    drop = declick(song[n(land):n(land) + n(end) - n(impact)], mx["fade_cut_s"], end=False)
    f0, fl = n(fade_from - impact), n(end - fade_from)
    tail = drop[f0:]
    tail = sweep(tail, lambda t: hi * (lo / hi) ** (min(t / (fl / SR), 1) ** mx["lp_curve"]))
    tail *= (np.cos(np.linspace(0, np.pi / 2, len(tail))) ** 2)[:, None]       # Ausblende auf exakt 0 am Ende
    drop[f0:] = tail
    x[n(impact):] = drop
    x *= PEAK / np.abs(x).max()
    hits = [round(h + grid["in_s"] - s0, 4) for h in grid["hits_s"] if 0 <= h + grid["in_s"] - s0 < stop]
    per = cfg["loop"]["changes_per_bar"] or 48
    name = f"M3{v}"
    info = dict(variant=name, file=f"ref/audio/mashup_{name}.wav", sr=SR, note=get("note"),
                bpm_carousel=grid["bpm"], bpm_end=grid["bpm"], sixteenth_s=round(bar / 16, 6),
                carousel_bars=[[per, get("bars")]],
                sixteenths_s=[round(i * bar / 16, 6) for i in range(16 * get("bars") + 1)],
                downbeats_s=[round(i * bar, 6) for i in range(int(end / bar + 1e-6) + 1)] +
                            ([round(end, 6)] if (end / bar) % 1 > 1e-6 else []),
                hits_s=hits + [round(impact, 4)], air_s=round(stop, 6),
                burst_s=round(impact - cfg["endcard"]["burst_beats"] * beat, 6),
                drop_s=round(impact, 6), impact_s=round(impact, 6), fade_from_s=round(fade_from, 6),
                fade_s=round(end - fade_from, 6), end_s=round(end, 6), song_in_s=round(s0, 5),
                jump_song_s=round(land, 5),
                explain="Zeiten ab Videoanfang. 0..air_s IGOR im Original ab song_in_s (Brummen, dann Drums), mit "
                        "Tiefpass- und Pegel-Einblende. air_s..drop_s Luft (nur Hall). drop_s = impact_s = Sprung in "
                        "den B-Teil (jump_song_s, Songzeit). fade_from_s..end_s Ausklang auf Stille (fade_s lang) = "
                        "Zeit fuer Zoom + Fade to Black. hits_s: IGORs Drum-Hits + Drop.")
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


def db(x, a, b):
    return 20 * np.log10(np.sqrt((x[n(a):n(b)] ** 2).mean()) + 1e-12)


def checks(x, t, bar):
    """Befunde am fertigen Audio: Einblende steigt, Luft leiser als davor, Drop-Sprung, kein Knack, Ende auf Stille."""
    jump = np.abs(np.diff(x, axis=0)).max(1)
    typ = np.percentile(jump, 99.9)
    worst = max(jump[n(c) - 2:n(c) + 2].max() / typ for c in (t["air_s"], t["drop_s"]))   # Sprung genau an der Kante
    q = t["air_s"] / 4
    rise = [db(x, i * q, (i + 1) * q) for i in range(4)]
    last = np.abs(x[-n(0.01):]).max()
    return [f"  Einblende (Viertel bis zur Luft): {' → '.join(f'{r:.0f}' for r in rise)} dBFS "
            f"({'ok, steigt' if all(b > a for a, b in zip(rise, rise[1:])) else 'steigt NICHT stetig'})",
            f"  Luft {t['drop_s'] - t['air_s']:.2f} s: {db(x, t['air_s'], t['drop_s']):.1f} dBFS gegen den Takt davor "
            f"{db(x, t['air_s'] - bar, t['air_s']):.1f}, erster Takt nach dem Drop "
            f"{db(x, t['drop_s'], min(t['drop_s'] + bar, t['fade_from_s'])):.1f} dBFS",
            f"  Schnitte {t['air_s']:.2f} / {t['drop_s']:.2f} s: Sample-Sprung an der Kante {worst:.2f}x des 99.9-%-Werts "
            f"({'ok, kein Knack' if worst <= 1 else 'KNACK?'}); letzte 10 ms Spitze {20 * np.log10(last + 1e-12):.0f} "
            f"dBFS ({'ok, klingt aus' if last < 1e-3 else 'endet NICHT in Stille'})"]


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


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else CONFIG
    cfg, grid = load(path)
    mx = cfg["mashup"]
    os.makedirs(OUT, exist_ok=True)
    song = decode(os.path.join(AUDIO, "igors_theme.mp3"))
    land = grid["in_s"] + mx["land_bar"] * grid["bar_s"]
    ph = grid_phase(song, land, land + 4 * grid["bar_s"], grid["in_s"], grid["sixteenth_s"])
    ph0 = grid_phase(song, grid["in_s"], grid["in_s"] + 4 * grid["bar_s"], grid["in_s"], grid["sixteenth_s"])
    rep = [f"Musik M3 (IGOR-Schnitt 16-20 s) · uv run src/kickoff_loop_music.py {os.path.relpath(path, ROOT)}", "",
           f"Sprung auf Songzeit {land:.3f} s (B-Anfang, Tyler ab ~47.0 s). Phase (Kamm-Fit Hat-Band, 4 Takte): B-Teil "
           f"{ph:+.0f} ms, IGORs Drums ab in_s {ph0:+.0f} ms gegen das Raster, Differenz {ph - ph0:+.0f} ms "
           f"({'ok' if abs(ph - ph0) <= 20 else 'PRUEFEN'}, Grenze 20 ms ~ Raster-Streuung 19 ms)", ""]
    for v in mx["variants"]:
        x, t = build(cfg, grid, song, v)
        name = t["variant"]
        wav = os.path.join(AUDIO, f"mashup_{name}.wav")
        write_wav(wav, x)
        json.dump(t, open(os.path.join(AUDIO, f"mashup_{name}.json"), "w"), indent=1)
        lu, tp = ebur(x)
        drums = grid["in_s"] - t["song_in_s"]
        rep += [f"{name}: {t['note']}",
                f"  Verlauf: 0 s Einblende (Song {t['song_in_s']:.2f} s, Brummen; Tiefpass offen bei "
                f"{mx[v + '_lp_open_bars'] * grid['bar_s']:.2f} s), IGORs Drum-Loop ab {drums:.2f} s (erster Hit "
                f"{drums + grid['hits_s'][0]:.2f} s), Luft {t['air_s']:.2f} s, Ausbruch {t['burst_s']:.2f} s, "
                f"DROP {t['drop_s']:.3f} s, Ausklang {t['fade_from_s']:.2f}-{t['end_s']:.2f} s ({t['fade_s']:.2f} s)",
                f"  Laenge {t['end_s']:.2f} s, Karussell {t['carousel_bars'][0][1]} Takte x {t['carousel_bars'][0][0]} = "
                f"{t['carousel_bars'][0][0] * t['carousel_bars'][0][1]} Wechsel (16.32/s), {len(t['hits_s'])} Hits",
                *checks(x, t, grid["bar_s"]),
                f"  WAV {lu:.1f} LUFS, True Peak {tp:.1f} dBTP, Spitze -1 dBFS statisch",
                hear(wav, x, os.path.join(OUT, f"mashup_{name}.m4a")), ""]
    open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8").write("\n".join(rep))
    print("\n".join(rep))


if __name__ == "__main__":
    sys.exit(main())
