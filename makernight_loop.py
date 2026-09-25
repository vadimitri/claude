#!/usr/bin/env python3
"""Nahtloser Musik-Loop aus dem Maker-Night-Drop: Dm9 | Bbmaj9 | C(add9) | C(add9), je 2 Takte, 120 BPM = 16 s.

Nahtlos, weil 3 Zyklen gerendert und nur der mittlere ausgeschnitten wird: Hall- und Release-Fahnen
vom Zyklusende liegen dann schon am Anfang, genau wie beim echten Wiederholen.

  uv run --with numpy --with scipy python makernight_loop.py
  -> makernight/loop/  loop_full.wav (mit Drums)  loop_bed.wav (nur Pad + Arp, unter Sprache)
                       *_60s.wav/.m4a (4 Zyklen mit Fade, fuer Stellen ohne Loop-Funktion)
"""
import os
import subprocess
import wave

import numpy as np

from makernight_audio import (BEAT, OUT, SR, Bus, clap, env, hat, hz, kick, lp, pluck, reverb, rng, saw,
                              snare)

CHORDS = [[50, 57, 60, 64, 65],        # Dm9
          [46, 53, 57, 60, 62],        # Bbmaj9
          [48, 55, 59, 62, 64],        # C(add9)
          [48, 55, 59, 62, 64]]
BARS = 2                               # Takte pro Akkord
BAR = 4 * BEAT
CYC = len(CHORDS) * BARS * BAR         # 16 s
REPS = 3


def fade(x, sec=0.02):
    """Kurze Ein-/Ausblende, sonst knackt jeder Saw-Start (zufaellige Phase)."""
    k = min(int(sec * SR), len(x) // 2)
    x[:k] *= np.linspace(0, 1, k)
    x[-k:] *= np.linspace(1, 0, k)
    return x


def arrangement(drums):
    """Ein Zyklus trocken, Ueberhang (Release, Fill) kreisfoermig auf den Anfang gefaltet -> exakt periodisch.
    Dann 3x kacheln, Filter/Sidechain/Hall drauf und den mittleren Zyklus nehmen: auch die Fahnen sind nahtlos."""
    a, tail = int(round(CYC * SR)), int(1.5 * SR)
    music, pads, kicks = Bus(a + tail), Bus(a + tail), Bus(a + tail)
    for ci, c in enumerate(CHORDS):
        t0, sec = ci * BARS * BAR, BARS * BAR
        for m in c:                                            # Pad: 4 detunte Saws pro Ton
            for pan, det in ((-0.8, -0.004), (0.8, 0.004), (-0.3, 0.0015), (0.3, -0.0015)):
                pads.add(fade(saw(hz(m), sec + 0.02, det)) * 0.06, t0, pan=pan)   # 20 ms Crossfade in den naechsten Akkord
    for i in range(int(round(CYC / (BEAT / 4)))):              # Arp: die Melodie aus dem Drop
        c = CHORDS[i // (BARS * 16)]
        seq = [c[2] + 12, c[4] + 12, c[3] + 12, c[1] + 12, c[2] + 24, c[4] + 12, c[3] + 12, c[0] + 24]
        music.add(pluck(hz(seq[i % 8]), 5000), i * BEAT / 4, 0.22 * (1 if i % 4 == 0 else 0.7), pan=0.35 * np.sin(i * 1.3))
    if drums:
        for b in range(int(CYC / BEAT)):
            tb = b * BEAT
            root = CHORDS[b // (BARS * 4)][0] - 12
            kicks.add(kick(1.1), tb, 0.9)
            music.add(np.tanh(2 * lp(saw(hz(root), 0.22) + saw(hz(root), 0.22, 0.007), 420)) * env(0.22, 0.004, 0.12),
                      tb + BEAT / 2, 0.42)
            music.add(hat(open_=(b % 2 == 1)), tb + BEAT / 2, 0.16, pan=0.25)
            for q in (0.25, 0.75):
                music.add(hat(), tb + BEAT * q, 0.07, pan=-0.3)
            if b % 2 == 1:
                music.add(clap(), tb, 0.5)
        for j in range(8):                                     # Snare-Fill zurueck in den Anfang
            music.add(snare(1.2), CYC - 2 * BEAT + j * BEAT / 4, 0.1 + 0.03 * j, pan=rng.uniform(-0.2, 0.2))

    def ring(bus):
        x = bus.x[:a].copy()
        x[:tail] += bus.x[a:a + tail]
        return np.tile(x, (3, 1))

    pad, mus, kk = ring(pads), ring(music), ring(kicks)
    pad = np.stack([lp(pad[:, c], 1750) for c in range(2)], 1)
    x = mus + pad
    if drums:                                                  # Sidechain: alles pumpt, nur die Kick nicht
        x = x * (1 - 0.75 * np.exp(-(np.arange(len(x)) / SR % BEAT) / 0.11))[:, None] + kk
    x = x + 0.28 * reverb(x, 2.0, 5000)
    return x[a:2 * a]                                          # mittlerer Zyklus = nahtlos


def write(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def main():
    out = os.path.join(OUT, "loop")
    os.makedirs(out, exist_ok=True)
    for name, drums in (("loop_full", True), ("loop_bed", False)):
        x = arrangement(drums)
        x = np.tanh(x * 1.3) / np.tanh(1.3)
        x *= 0.89 / np.abs(x).max()                            # -1 dBFS Peak, statisch: Loudnorm wuerde die Naht verbiegen
        write(os.path.join(out, f"{name}.wav"), x)
        long = np.tile(x, (4, 1))
        long *= np.clip((len(long) / SR - np.arange(len(long)) / SR) / 4, 0, 1)[:, None]   # 4 s Fade-out
        wav60 = os.path.join(out, f"{name}_60s.wav")
        write(wav60, long)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav60, "-c:a", "aac", "-b:a", "256k",
                        wav60[:-4] + ".m4a"], check=True)
        print(name, f"{len(x) / SR:.2f}s")


if __name__ == "__main__":
    main()
