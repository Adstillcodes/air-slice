"""Sound effects: real audio files if present, synthesized fallback otherwise.

Drop WAV/OGG/MP3 files into assets/sounds/ to replace any effect:

    slice*.wav      one or more swoosh/splat variants, picked at random
    combo*.wav      one or more combo dings; sorted by name, indexed by level
    bomb.wav  tick.wav  go.wav  gameover.wav  highscore.wav  submit.wav

Effects without a matching file are synthesized with numpy at startup, so the
game always has a full sound set. If the mixer can't initialize (no audio
device, Docker), sounds are silently off. Only commit sounds you have the
rights to distribute (e.g. CC0) — not ripped commercial game assets.
"""

import random
from pathlib import Path

import numpy as np
import pygame

ASSET_DIR = Path(__file__).parent.parent / "assets" / "sounds"
AUDIO_EXTS = ("*.wav", "*.ogg", "*.mp3")

# default volume per effect (applied to files and synth alike)
VOLUMES = {
    "slice": 0.55, "combo": 0.5, "bomb": 0.9, "tick": 0.4,
    "go": 0.5, "gameover": 0.6, "highscore": 0.6, "submit": 0.5,
}


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


def _load_files(stem):
    """All audio files in ASSET_DIR whose name starts with `stem`, sorted."""
    if not ASSET_DIR.is_dir():
        return []
    paths = sorted(p for ext in AUDIO_EXTS for p in ASSET_DIR.glob(ext)
                   if p.stem.lower().startswith(stem))
    sounds = []
    for p in paths:
        try:
            sounds.append(pygame.mixer.Sound(str(p)))
        except pygame.error as e:
            print(f"sounds: could not load {p.name}: {e}")
    return sounds


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

        loaded = []
        slice_files = _load_files("slice")
        if slice_files:
            loaded.append("slice")
        self._slices = slice_files or [
            self._make(_swoosh(rng, sr, smooth=s)) for s in (3, 6, 10)
        ]
        combo_files = _load_files("combo")
        if combo_files:
            loaded.append("combo")
        self._dings = combo_files or [
            self._make(_tone(620 * (1.13 ** i), 0.22, sr, tau=0.09)) for i in range(5)
        ]
        synth = {
            "bomb": lambda: _boom(rng, sr),
            "tick": lambda: _tone(880, 0.07, sr, tau=0.03, harmonics=(1.0,)),
            "go": lambda: _tone(1320, 0.28, sr, tau=0.12),
            "gameover": lambda: _jingle([660, 494, 440], 0.22, sr),
            "highscore": lambda: _jingle([523, 659, 784, 1047], 0.13, sr),
            "submit": lambda: _tone(1047, 0.15, sr, tau=0.07),
        }
        for name, make in synth.items():
            files = _load_files(name)
            if files:
                loaded.append(name)
            self._sounds[name] = files[0] if files else self._make(make())

        for s in self._slices:
            s.set_volume(VOLUMES["slice"])
        for s in self._dings:
            s.set_volume(VOLUMES["combo"])
        for name, s in self._sounds.items():
            s.set_volume(VOLUMES[name])

        if loaded:
            print(f"sounds: loaded from {ASSET_DIR}: {', '.join(loaded)}")
        self.ok = True

    @staticmethod
    def _make(mono):
        wave = np.clip(mono, -1.0, 1.0)
        pcm = (wave * 32767 * 0.85).astype(np.int16)
        stereo = np.ascontiguousarray(np.column_stack([pcm, pcm]))
        return pygame.sndarray.make_sound(stereo)

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
