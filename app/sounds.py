"""Procedurally synthesized sound effects — no audio asset files needed.

Everything is generated with numpy at startup and turned into pygame Sounds.
If the mixer can't initialize (no audio device, Docker), sounds are silently off.
"""

import random

import numpy as np
import pygame


def _env(n, sr, attack=0.005, tau=0.08):
    t = np.arange(n) / sr
    env = np.exp(-t / tau)
    a = max(1, int(attack * sr))
    env[:a] *= np.linspace(0.0, 1.0, a)
    return env


def _tone(freq, dur, sr, tau=0.1, harmonics=(1.0, 0.35, 0.15)):
    n = int(dur * sr)
    t = np.arange(n) / sr
    w = np.zeros(n)
    for i, amp in enumerate(harmonics):
        w += amp * np.sin(2 * np.pi * freq * (i + 1) * t)
    return w * _env(n, sr, tau=tau) * 0.6


def _swoosh(rng, sr, dur=0.16, smooth=6, tau=0.05):
    n = int(dur * sr)
    noise = rng.standard_normal(n)
    kernel = np.ones(smooth) / smooth  # crude lowpass sets the "brightness"
    noise = np.convolve(noise, kernel, mode="same")
    noise /= max(1e-9, np.max(np.abs(noise)))
    return noise * _env(n, sr, attack=0.015, tau=tau) * 0.9


def _boom(rng, sr):
    dur = 0.6
    n = int(dur * sr)
    t = np.arange(n) / sr
    freq = 150 * np.exp(-t * 4.0) + 45  # falling pitch
    w = np.sin(2 * np.pi * np.cumsum(freq) / sr)
    thump = _swoosh(rng, sr, dur=0.12, smooth=24, tau=0.05)
    w[: len(thump)] += thump * 0.8
    return w * _env(n, sr, tau=0.2) * 0.95


def _jingle(freqs, dur_each, sr, tau=0.14):
    return np.concatenate([_tone(f, dur_each, sr, tau=tau) for f in freqs])


class Sfx:
    def __init__(self):
        self.ok = False
        self._slices = []
        self._dings = []
        self._sounds = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(44100, -16, 2, 256)
        except pygame.error:
            return
        sr = pygame.mixer.get_init()[0]
        rng = np.random.default_rng(7)

        self._slices = [
            self._make(_swoosh(rng, sr, smooth=s), 0.55) for s in (3, 6, 10)
        ]
        # one ding per combo level (x2..x6+), rising in pitch
        self._dings = [
            self._make(_tone(620 * (1.13 ** i), 0.22, sr, tau=0.09), 0.5)
            for i in range(5)
        ]
        self._sounds = {
            "bomb": self._make(_boom(rng, sr), 0.9),
            "tick": self._make(_tone(880, 0.07, sr, tau=0.03, harmonics=(1.0,)), 0.4),
            "go": self._make(_tone(1320, 0.28, sr, tau=0.12), 0.5),
            "gameover": self._make(_jingle([660, 494, 440], 0.22, sr), 0.6),
            "highscore": self._make(_jingle([523, 659, 784, 1047], 0.13, sr), 0.6),
            "submit": self._make(_tone(1047, 0.15, sr, tau=0.07), 0.5),
        }
        self.ok = True

    @staticmethod
    def _make(mono, volume):
        wave = np.clip(mono, -1.0, 1.0)
        pcm = (wave * 32767 * 0.85).astype(np.int16)
        stereo = np.ascontiguousarray(np.column_stack([pcm, pcm]))
        sound = pygame.sndarray.make_sound(stereo)
        sound.set_volume(volume)
        return sound

    def play(self, name):
        if not self.ok:
            return
        if name == "slice":
            random.choice(self._slices).play()
        elif name in self._sounds:
            self._sounds[name].play()

    def combo(self, level):
        if self.ok and level > 1:
            self._dings[min(level - 2, len(self._dings) - 1)].play()
