#!/usr/bin/env python3
"""Ton fuer das Motion-Labor (M11 Finsternis, M12 Sternlicht, M13 Portal, M14 Kreuz-Welle).

Die Cues kommen aus demselben Code wie das Bild (lab_motion: Weg-Funktionen, Treffer-Zeiten), also framegenau.
120 BPM wie das Bild. Jede Spur ist ein nahtloser Loop: Ereignisse fuer drei Zyklen setzen, alles filtern
und verhallen, den mittleren Zyklus behalten (Hallfahnen wickeln sich um die Naht).
Instrumente aus makernight_audio (nur Import).

  uv run -q --with numpy --with scipy --with pillow --with qrcode --with scikit-image python src/lab_motion_audio.py [code ...]
-> styles/lab/motion/<code>_<key>.wav + <code>_<key>_sound.mp4 (loudnorm I=-14 TP=-1, linear) + Pruefbilder in sheets/
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

import lab_motion as lm
from makernight_audio import SR, Bus, bell, boom, bp, clap, env, hat, hp, hz, kick, lp, noise, pluck, reverb, saw, snare, sweep_lp

CHORDS = {"lav": [50, 57, 60, 64, 65], "paper": [46, 53, 57, 60, 62], "acid": [48, 55, 59, 62, 64]}   # Dm9, Bbmaj9, C(add9)
ARP = (2, 4, 3, 1, 2, 4, 3, 0)                                   # Reihenfolge der Akkordtoene (die Arp-Melodie)


class Loop:
    """Drei Zyklen Puffer: add() setzt ein Ereignis in jeden Zyklus, mid() liefert den mittleren."""

    def __init__(self, T):
        self.T, self.n = T, round(T * SR)
        self.bus = Bus(3 * self.n)
        self.t = np.arange(3 * self.n) / SR

    def add(self, sig, t0, gain=1.0, pan=0.0):
        t0 %= self.T                                              # Auftakt vor 0 = Ende des Zyklus davor
        for k in range(3):
            self.bus.add(sig, t0 + k * self.T, gain, pan)

    def cont(self, fn):
        """Durchgehendes Signal aus periodischer Zeit (t mod T), stereo (n, 2)."""
        return fn(self.t % self.T, self.t)

    def mid(self, x):
        return x[self.n:2 * self.n]


def ctrl(f, T):
    """Steuerkurve f(t) (Skalar) auf Samplelaenge ueber drei Zyklen, stueckweise linear aus 1-kHz-Stuetzstellen."""
    tt = np.arange(0, 3 * T, 1e-3)
    return np.interp(np.arange(round(3 * T * SR)) / SR, tt, [f(x % T) for x in tt])


def psaw(f, ta, T, det=0.0, ph0=0.0):
    """Saege mit auf 1/T gerundeter Frequenz: genau ganzzahlig viele Perioden pro Zyklus (keine Naht)."""
    fq = round(f * (1 + det) * T) / T
    return 2 * ((ta * fq + ph0) % 1) - 1


def psin(f, ta, T):
    return np.sin(2 * np.pi * round(f * T) / T * ta)


def pan2(x, p):
    a = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1) * np.sqrt(2)


def rev_cym(sec=0.9):
    return hp(noise(sec), 3000)[::-1] * np.linspace(0, 1, int(sec * SR)) ** 3


def strum(notes, t0, loop, gain, cutoff=4000, spread=0.009):
    for j, m in enumerate(notes):
        loop.add(pluck(hz(m), cutoff, 0.9), t0 + j * spread, gain, pan=(j - 2) * 0.18)


def master(x, drive=1.2):
    x = hp(x.T, 25).T
    x = np.tanh(x * drive) / np.tanh(drive)
    return x * (0.9 / np.abs(x).max())


# ---------------------------------------------------------------- weiche Bausteine (fuer M12, M13)

def soft_pluck(freq, cutoff=2000, sec=0.6, attack=0.006, decay=0.18):
    """Pluck ohne Knack: Dreieck + leise Saege, langsamer Anstieg, tiefer Filter."""
    t = np.arange(int(sec * SR)) / SR
    ph = (t * freq + 0.25) % 1
    tri = 2 * np.abs(2 * ph - 1) - 1
    x = lp(tri + 0.25 * saw(freq, sec, 0.004)[:len(t)], cutoff)
    return x * np.minimum(t / attack, 1) * np.exp(-t / decay)


def thump(g=1.0, f0=52):
    """Weicher Sub-Schlag statt Kick: kaum Pitch-Sweep, kein Klick, 5 ms Anstieg."""
    t = np.arange(int(0.7 * SR)) / SR
    f = f0 + 30 * np.exp(-t / 0.05)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.3) * np.minimum(t / 0.005, 1) * g


def shaker(sec=0.12):
    t = np.arange(int(sec * SR)) / SR
    return lp(bp(noise(sec), 2500, 6000), 7000) * np.minimum(t / 0.012, 1) * np.exp(-t / 0.035)


def crash(sec=1.6):
    t = np.arange(int(sec * SR)) / SR
    return hp(noise(sec), 4500) * np.exp(-t / 0.5) * np.minimum(t / 0.001, 1)


def pad_voice(notes, sec, gain=0.045, cutoff=1200):
    """Akkord als detunte Saegen-Wolke, 20-ms-Fades (Zufallsphasen knacken sonst), stereo."""
    n = int(sec * SR)
    x = np.zeros((n, 2))
    for m in notes:
        for side, det in ((0, -0.004), (1, 0.004), (0, 0.0015), (1, -0.0015)):
            x[:, side] += saw(hz(m), sec, det)[:n] * gain
    f = int(0.02 * SR)
    ramp = np.minimum(np.minimum(np.arange(n), n - 1 - np.arange(n)) / f, 1)
    return np.stack([lp(x[:, c], cutoff) for c in range(2)], 1) * ramp[:, None]


# ---------------------------------------------------------------- M11 Finsternis

def finsternis():
    """Der dunkle Stern waechst aus der Mitte: Drone schliesst mit der Deckung, Einatmen folgt dem Wachsen,
    Totalitaet auf Schlag 4 (Boom + Glas), beim Zurueckziehen kommt das Licht als Arp-Schimmer zurueck."""
    T = 4.0
    lp_ = Loop(T)
    HIT = lm.EC_HIT
    tt = np.arange(0, T, 0.01)
    occ = np.array([lm.ec_occ(x, T, step=3) for x in tt])
    OCC = np.interp(lp_.t % T, tt, occ, period=T)
    S = np.array([lm.ec_state(x % T, T)[0] for x in np.arange(0, 3 * T, 1e-3)])
    S = np.interp(np.arange(len(lp_.t)) / SR, np.arange(len(S)) * 1e-3, S)
    dS = np.gradient(S) * SR
    grow = np.clip(dS / dS.max(), 0, 1)
    shrink = np.clip(-dS / -dS.min(), 0, 1)

    # Drone D: Sub + Saws, Filter schliesst sich mit der Deckung (das Licht wird weggesaugt), oeffnet im Treffer
    def drone(tm, ta):
        x = psin(hz(26), ta, T) * 0.5 + psin(hz(38), ta, T) * 0.25
        s = sum(psaw(hz(m), ta, T, d, 0.3 * j) for j, (m, d) in enumerate(((38, -0.003), (45, 0.003), (50, 0.0015))))
        cut = lambda u: 1500 - 1250 * OCC[min(int(u * SR), len(OCC) - 1)] \
            + 2600 * np.exp(-max(0, (u % T) - HIT) / 0.35) * ((u % T) >= HIT)              # noqa: E731
        s = sweep_lp(s * 0.18, cut)
        return np.stack([x + s, x + s], 1) * (0.2 + 0.45 * OCC ** 1.5)[:, None]
    drone_x = lp_.cont(drone)

    # Wachsen hoerbar: Einatmen (Rauschen, Filter geht mit dem Wachstum auf), Zurueckziehen = sanfter Ausatmer
    nl, nr = noise(3 * T), noise(3 * T)
    ctl = lambda u: 300 + 2600 * float(np.interp(u * SR, np.arange(len(grow)), grow))      # noqa: E731
    breath = np.stack([sweep_lp(nl, ctl), sweep_lp(nr, ctl)], 1) * (0.55 * grow ** 1.4 + 0.25 * shrink ** 2)[:, None]

    # Herzschlag auf den Schlaegen vor dem Treffer, leise auf 6 + 7 (fuehrt in den Loop)
    for n, g in ((0, 0.3), (1, 0.36), (2, 0.44), (3, 0.54), (6, 0.2), (7, 0.25)):
        lp_.add(lp(kick(0.9), 180), n * lm.BEAT, g)
    rt = np.arange(int(1.8 * SR)) / SR
    riser = sweep_lp(noise(1.8), lambda s: 400 * 12 ** (s / 1.8)) * (rt / 1.8) ** 2.5
    lp_.add(riser * (rt < 1.8 - 0.14), HIT - 1.8, 0.32)
    lp_.add(rev_cym(0.9), HIT - 0.9, 0.28)
    # Totalitaet: Sub-Boom, Glas (Dm9 oben), Perlen an den Spitzen als kleine Glasklicks
    lp_.add(boom(), HIT, 1.1)
    lp_.add(kick(1.2), HIT, 0.85)
    for j, m in enumerate((86, 93, 96)):
        lp_.add(bell(hz(m), 2.0, 0.55), HIT + 0.012 * j, 0.13, pan=(-0.4, 0.4, 0)[j])
    rng = np.random.default_rng(11)
    for j in range(9):
        lp_.add(bell(hz(rng.choice([93, 96, 100])), 0.4, 0.12), HIT + 0.03 + 0.045 * j, 0.03, pan=rng.uniform(-0.7, 0.7))
    # Licht kehrt zurueck: Arp-Schimmer, der mit dem Schrumpfen heller wird
    step = lm.BEAT / 4
    for i in range(14):
        t = HIT + lm.BEAT + i * step
        m = CHORDS["lav"][ARP[i % 8]] + 24
        lp_.add(pluck(hz(m), 2200 + 150 * i), t, 0.075 * (1 - i / 17), pan=0.5 * np.sin(i * 1.3))

    tm = lp_.t % T
    gap = 1 - 0.9 * np.clip(np.minimum(tm - (HIT - 0.14), HIT - tm) / 0.01, 0, 1)
    bed = (drone_x + breath) * gap[:, None]
    fx = lp_.bus.x
    wet = 0.4 * reverb(fx, 2.4, 7000, seed=2) + 0.2 * reverb(bed, 2.2, 5000)
    mix = bed + fx + wet * np.maximum(gap, 0.3)[:, None]
    return T, master(lp_.mid(mix))


# ---------------------------------------------------------------- M13 Portal (weich)

def portal():
    """Weich statt hart: Sub-Schlag statt Kick, Dreieck-Plucks, tiefe Filter, kein offener Hat, Rauschen bis 2,4 kHz."""
    T = 3.0
    lp_ = Loop(T)
    tt = np.arange(0, 3 * T, 1e-3)
    lam = np.array([lm.portal_lam(x % T) + 3 * (x // T) for x in tt])          # stetig ueber die Zyklen
    vel = np.gradient(lam, 1e-3)
    ts = lp_.t
    V = np.interp(ts, tt, vel)
    V = np.clip(V / V.max(), -1, 1)

    # Sturz: weiches Luftrauschen, Filter geht nur bis ~2,4 kHz auf
    dive = sweep_lp(noise(3 * T), lambda u: 200 + 1500 * max(0.0, float(np.interp(u, ts[::64], V[::64]))) ** 1.5)
    dive = dive * np.clip(V, 0, 1) ** 1.8 * 0.32
    bed = pan2(dive, 0.2)

    # Jede Dimension ein Akkord (Dm9 Nacht, Bbmaj9 Papier, C Schwarzlicht) als warmes Pad, Landung = Sub + Strum + Glas
    chords = (CHORDS["lav"], CHORDS["paper"], CHORDS["acid"])
    for k, c in enumerate(chords):
        t0 = k * 1.0
        lp_.add(pad_voice([m + 12 for m in c[:4]], 1.08, 0.03, 900), t0 - 0.04, 1.0)
        lp_.add(thump(1.0), t0, 0.4)
        bass = lp(np.sin(2 * np.pi * hz(c[0] - 12) * np.arange(int(0.8 * SR)) / SR), 300) * env(0.8, 0.01, 0.35)
        lp_.add(bass, t0, 0.2)
        for j, m in enumerate(c):
            lp_.add(soft_pluck(hz(m + 12), 1800, 0.9, 0.01, 0.3), t0 + 0.012 + j * 0.018, 0.07, pan=(j - 2) * 0.2)
        lp_.add(bell(hz(c[0] + 24), 1.8, 0.9), t0 + 0.02, 0.035, pan=0.3)
        lp_.add(shaker(), t0 + 0.5, 0.05, pan=0.3)
        for i in range(8):                                                       # Arp in der Haltephase
            m = c[ARP[i]] + 12 + 12 * (i == 4)
            lp_.add(soft_pluck(hz(m), 1500), t0 + 0.0625 + i * 0.0625, 0.05 * (1 if i % 4 == 0 else 0.7), pan=0.4 * np.sin(i * 1.3))
    ph = lp_.t % 1.0
    duck = 1 - 0.35 * np.exp(-ph / 0.12)
    fx = lp_.bus.x
    mix = bed * duck[:, None] + fx + 0.45 * reverb(fx, 2.8, 4500, seed=3)
    mix = lp(mix.T, 9000).T                                                      # weiche Hoehen
    return T, master(lp_.mid(mix), drive=0.7)


# ---------------------------------------------------------------- M12 Sternlicht (3D-Licht)

def sternlicht():
    """Dunkel, dann Licht: Pad oeffnet mit der Helligkeit, Luft folgt dem Licht im Stereobild,
    Ankunft in der Mitte (Schlag 8) = Glasakkord, danach schliesst alles wieder ins Dunkel."""
    T = 8.0
    lp_ = Loop(T)
    MID = lm.SL_MID

    def light(t):
        (x, _, _), inten = lm.sl_light(t % T, T)
        return x, inten
    tt = np.arange(0, 3 * T, 2e-3)
    L = np.array([light(x) for x in tt])
    ti = np.arange(len(lp_.t)) / SR
    LX = np.interp(ti, tt, L[:, 0])
    BR = np.interp(ti, tt, L[:, 1] * (0.35 + 0.65 * np.exp(-((L[:, 0] - 240) / 230) ** 2)))
    spd = np.abs(np.gradient(LX)) * SR
    spd = spd / spd.max()

    def pad(tm, ta):
        n = len(ta)
        x = np.zeros((n, 2))
        for j, m in enumerate(CHORDS["lav"]):
            for i, (side, det) in enumerate(((0, -0.004), (1, 0.004), (0, 0.0015), (1, -0.0015))):
                x[:, side] += psaw(hz(m), ta, T, det, 0.17 * j + 0.29 * i) * 0.05
        ctl = lambda u: 160 + 2600 * float(np.interp(u * SR, np.arange(n), BR)) ** 1.6    # noqa: E731
        x = np.stack([sweep_lp(x[:, c], ctl) for c in range(2)], 1)
        sub = psin(hz(38), ta, T) * 0.22 + psin(hz(26), ta, T) * 0.3
        return x * (0.05 + 0.95 * BR)[:, None] + (sub * (0.08 + 0.45 * BR))[:, None]
    pad_x = lp_.cont(pad)
    air = sweep_lp(noise(3 * T), lambda u: 300 + 1900 * float(np.interp(u * SR, np.arange(len(spd)), spd)))
    air_x = pan2(air * spd ** 1.3 * (0.2 + BR) * 0.35, (LX - 240) / 260)

    # Ankunft in der Mitte: weicher Sog hinein, Glasakkord + Sub-Bluete (kein harter Schlag)
    lp_.add(rev_cym(1.4), MID - 1.4, 0.14)
    lp_.add(lp(boom(), 160), MID, 0.5)
    for j, m in enumerate((74, 81, 84, 88, 89)):
        lp_.add(bell(hz(m), 3.0, 1.4), MID + 0.03 * j, 0.06, pan=(j - 2) * 0.25)
    # im Licht: langsamer Arp in Achteln (Dm9), Lautstaerke und Filter folgen der Helligkeit
    for i in range(16):
        t = 2.0 + i * lm.BEAT / 2
        b = float(np.interp(t, tt, L[:, 1] * (0.35 + 0.65 * np.exp(-((L[:, 0] - 240) / 230) ** 2))))
        m = CHORDS["lav"][ARP[i % 8]] + 12
        lp_.add(soft_pluck(hz(m), 1200 + 2400 * b, 0.7, 0.006, 0.22), t, 0.09 * b, pan=0.45 * np.sin(i * 1.1))

    fx = lp_.bus.x
    bed = pad_x + air_x
    mix = bed + fx + 0.3 * reverb(bed, 2.6, 5000) + 0.5 * reverb(fx, 3.4, 7000, seed=2)
    return T, master(lp_.mid(mix))


# ---------------------------------------------------------------- M14 Kreuz-Welle (Banger mit der Teaser-Melodie)

KW_BARS = ([48, 55, 59, 62, 64], [50, 57, 60, 64, 65], [46, 53, 57, 60, 62], [50, 57, 60, 64, 65])   # C, Dm9, Bbmaj9, Dm9


def kreuzwelle():
    """16 Schlaege = 4 Takte, zwei Drops (Schlag 4 und 12 = Welle rollt los). Nach jedem Drop Groove
    (Four-on-the-floor, Offbeat-Bass, Clap auf 2+4, Hats, Arp offen), dann Build (Stern atmet ein): Snare-Roll,
    Riser, Arp-Filter oeffnet, Kick weicher, auf Schlag 3 kein Kick, 0,2 s Luftloch, Reverse-Becken in den Drop."""
    T, B = 8.0, lm.BEAT
    mus, fx = Loop(T), Loop(T)
    HIT = lm.KW_HIT
    chord = lambda b: KW_BARS[int(b // 4) % 4]                                    # noqa: E731
    build = lambda b: (b % 8) in (1, 2, 3)                                        # noqa: E731
    kicks = []
    for b in range(16):
        if b % 8 == 3:
            continue                                                               # Luft vor dem Drop (Bild: keine Kick-Glut)
        if build(b):
            mus.add(lp(kick(0.9), 1500), b * B, 0.5 + 0.1 * (b % 8))
        else:
            mus.add(kick(1.1), b * B, 0.95)
        kicks.append((b * B, 0.35 if build(b) else 0.75))
    for b in range(16):
        c = chord(b)
        if not build(b):                                                           # Groove
            root = c[0] - 12
            tb = b * B + B / 2
            bass = np.tanh(2.2 * lp(saw(hz(root), 0.24) + saw(hz(root), 0.24, 0.007), 480)) * env(0.24, 0.004, 0.13)
            sub = np.sin(2 * np.pi * hz(root - 12) * np.arange(int(0.24 * SR)) / SR) * env(0.24, 0.006, 0.14)
            mus.add(bass + 0.6 * sub, tb, 0.45)
            mus.add(hat(open_=True), tb, 0.12, pan=0.25)
            for q in (0.25, 0.75):
                mus.add(hat(), b * B + B * q, 0.075, pan=-0.3)
            if b % 2 == 1:
                mus.add(clap(), b * B, 0.5)
    for k in range(4):                                                             # Pad je Takt
        mus.add(pad_voice([m + 12 for m in KW_BARS[k]], 4 * B + 0.02, 0.028, 1400), k * 4 * B, 1.0)
    # Arp: die Teaser-Melodie in 16teln, im Groove Pluck-LP 5 kHz, im Build zu und wieder auf
    for i in range(64):
        t = i * B / 4
        b = t / B
        s = t % (T / 2)
        if HIT - 0.2 <= s < HIT:
            continue                                                               # Luftloch
        c = chord(b)
        seq = [c[2] + 12, c[4] + 12, c[3] + 12, c[1] + 12, c[2] + 24, c[4] + 12, c[3] + 12, c[0] + 24]
        if build(int(b)):
            p = (s - 0.5) / 1.3
            cut, g = 1000 * 4.5 ** p, 0.09 + 0.05 * p
        else:
            cut, g = 5000, 0.14
        mus.add(pluck(hz(seq[i % 8]), cut), t, g * (1 if i % 4 == 0 else 0.7), pan=0.35 * np.sin(i * 1.3))
    # Build + Drop je Haelfte
    for h in (0, T / 2):
        t = h + 0.5
        while t < h + HIT - 0.22:
            s = t - h
            rate = 2 if s < 1.0 else 4 if s < 1.5 else 8
            fx.add(snare(1 + (s - 0.5) * 0.3), t, 0.08 + 0.22 * (s - 0.5) / 1.3, pan=0.15 * np.sin(9 * s))
            t += B / rate
        rt = np.arange(int(1.3 * SR)) / SR
        riser = sweep_lp(noise(1.3), lambda x: 350 * 20 ** (x / 1.3)) * (rt / 1.3) ** 2
        fx.add(riser, h + 0.5, 0.32)
        fx.add(rev_cym(0.9), h + HIT - 0.9, 0.3)
        fx.add(boom(), h + HIT, 0.7)
        fx.add(crash(), h + HIT, 0.14, pan=-0.15)
        fx.add(bell(hz(81), 1.6, 0.6), h + HIT, 0.05, pan=0.3)
    # Sidechain-Pumpen auf jedem Kick, Luftloch 0,2 s vor dem Drop
    tm = mus.t % T
    g = np.ones(len(tm))
    for tk, depth in kicks:
        d = (tm - tk) % T
        g *= 1 - depth * np.exp(-d / 0.11)
    s = tm % (T / 2)
    gap = 1 - 0.9 * np.clip(np.minimum(s - (HIT - 0.2), HIT - s) / 0.01, 0, 1)
    m = mus.bus.x * (g * gap)[:, None]
    m = m + 0.22 * reverb(m, 2.0, 5000)
    f = fx.bus.x + 0.4 * reverb(fx.bus.x, 3.0, 7000, seed=2)
    return T, master(mus.mid(m + f), drive=1.3)


# ---------------------------------------------------------------- Ausgabe + Pruefung

JOBS = {"M11": ("finsternis", finsternis), "M12": ("sternlicht", sternlicht), "M13": ("portal", portal),
        "M14": ("kreuzwelle", kreuzwelle)}


def write(code):
    key, fn = JOBS[code]
    T, x = fn()
    base = os.path.join(lm.OUT, f"{code}_{key}")
    with wave.open(base + ".wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    # Lautheit in zwei Durchgaengen, linear (statische Verstaerkung, biegt die Loop-Naht nicht)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", base + ".wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", base + ".mp4", "-i", base + ".wav", "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", ln, "-ar", str(SR), "-c:a", "aac", "-b:a", "256k", "-shortest", base + "_sound.mp4"],
                   check=True)
    d = os.path.join(lm.OUT, "sheets")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", base + ".wav", "-lavfi",
                    "showspectrumpic=s=1600x500:legend=1:fscale=log", os.path.join(d, f"{code}_spectrum.png")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", base + ".wav", "-lavfi",
                    "showwavespic=s=1600x300:split_channels=1", os.path.join(d, f"{code}_waves.png")], check=True)
    seam = float(np.abs(x[0] - x[-1]).max())
    typical = float(np.percentile(np.abs(np.diff(x, axis=0)).max(1), 99.9))
    eb = subprocess.run(["ffmpeg", "-hide_banner", "-i", base + "_sound.mp4", "-af", "ebur128=peak=true", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    summ = " ".join(eb[eb.rindex("Summary:"):].split())
    print(code, f"seam step {seam:.4f} vs p99.9 step {typical:.4f} |", summ, flush=True)


if __name__ == "__main__":
    for c in sys.argv[1:] or list(JOBS):
        write(c)
