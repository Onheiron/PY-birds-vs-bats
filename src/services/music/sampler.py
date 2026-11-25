"""Plays the score with the instrument samples (media/music/bank/).

A part (score.py) becomes a loop of mono audio: every note takes the nearest
sample of its instrument, pitched by resampling, cut with a short fade at its
end (held notes of winds and strings loop the middle of the sample). Notes
that run past the end of the loop wrap round to its start, so the loop has no
seam. The parts are then panned, summed, given a room (a short reverb, also
wrapped round) and a gentle limiter.

Needs numpy, and pygame's mixer to decode the Ogg samples.
"""

import json
import threading
from pathlib import Path

import numpy as np

from src.services.music.instruments import INSTRUMENTS, SAMPLE_RATE

BANK_DIR = Path(__file__).resolve().parents[3] / 'media' / 'music' / 'bank'
ATTACK = 0.004  # seconds of fade-in of every note (no clicks)
MASTER = 2.6

_bank = None
_bank_lock = threading.Lock()


def available():
    return (BANK_DIR / 'bank.json').exists()


def bank():
    """instrument -> sorted [(MIDI note, mono float32 sample)], decoded once."""
    global _bank
    with _bank_lock:
        if _bank is None:
            import pygame

            index = json.loads((BANK_DIR / 'bank.json').read_text())
            loaded = {}
            for name, notes in index.items():
                samples = []
                for midi_note, filename in notes.items():
                    sound = pygame.mixer.Sound(str(BANK_DIR / filename))
                    data = pygame.sndarray.array(sound).astype(np.float32) / 32768.0
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    samples.append((int(midi_note), data))
                loaded[name] = sorted(samples, key=lambda item: item[0])
            _bank = loaded
        return _bank


def _nearest(samples, midi_note):
    return min(samples, key=lambda item: abs(item[0] - midi_note))


def render_part(events, instrument, bpm, beats):
    """Mono audio of a part: ``events`` (start beat, beats, notes, velocity) over ``beats`` beats."""
    spec = INSTRUMENTS[instrument]
    samples = bank()[instrument]
    beat = 60.0 / bpm
    total = int(round(beats * beat * SAMPLE_RATE))
    out = np.zeros(total, dtype=np.float32)
    release = spec.get('release', 0.12)
    sustain = spec.get('sustain', False)
    attack = int(ATTACK * SAMPLE_RATE)
    for start, length, notes, velocity in events:
        gain = (velocity / 127.0) ** 1.6
        for midi_note in notes:
            base, sample = _nearest(samples, midi_note)
            ratio = 2.0 ** ((midi_note - base) / 12.0)
            held = length * beat
            seconds = (
                held + release
                if sustain
                else max(held + release, min(len(sample) / SAMPLE_RATE / ratio, held * 1.5 + 0.3))
            )
            n = int(seconds * SAMPLE_RATE)
            if n <= attack:
                continue
            pos = np.arange(n, dtype=np.float64) * ratio
            end = len(sample) - 2
            if sustain and pos[-1] > end:
                # Held longer than the sample: loop its middle
                loop_start, loop_end = int(len(sample) * 0.35), int(len(sample) * 0.85)
                over = pos > loop_end
                pos[over] = loop_start + (pos[over] - loop_start) % (loop_end - loop_start)
            pos = np.minimum(pos, end)
            wave = np.interp(pos, np.arange(len(sample)), sample).astype(np.float32)
            envelope = np.ones(n, dtype=np.float32)
            envelope[:attack] = np.linspace(0, 1, attack, dtype=np.float32)
            fade = min(n, int(release * SAMPLE_RATE))
            envelope[n - fade :] *= np.linspace(1, 0, fade, dtype=np.float32)
            wave *= envelope * gain
            first = int(round(start * beat * SAMPLE_RATE)) % total
            _add_wrapped(out, wave, first)
    return out * spec.get('gain', 1.0)


def _add_wrapped(out, wave, first):
    total = len(out)
    while len(wave):
        room = total - first
        out[first : first + min(room, len(wave))] += wave[:room]
        wave = wave[room:]
        first = 0


_impulse = {}


def _room(n):
    """A small room's impulse response (decaying noise), as long as the loop for a wrapped convolution."""
    key = n
    if key not in _impulse:
        rng = np.random.default_rng(7)
        length = int(1.4 * SAMPLE_RATE)
        t = np.arange(length) / SAMPLE_RATE
        ir = rng.standard_normal(length) * np.exp(-t * 4.2)
        ir[: int(0.012 * SAMPLE_RATE)] = 0  # pre-delay
        ir /= np.sqrt(np.sum(ir**2))
        padded = np.zeros(n)
        padded[:length] = ir[:n]
        _impulse.clear()
        _impulse[key] = np.fft.rfft(padded)
    return _impulse[key]


def mix(parts, wet=0.18):
    """Stereo loop from [(mono audio, gain, pan -1..1)]: summed, a room added, limited. float32 (n, 2)."""
    n = max(len(audio) for audio, _gain, _pan in parts)
    left = np.zeros(n)
    right = np.zeros(n)
    for audio, gain, pan in parts:
        angle = (pan + 1) * np.pi / 4  # constant power
        left[: len(audio)] += audio * gain * np.cos(angle)
        right[: len(audio)] += audio * gain * np.sin(angle)
    room = _room(n)
    for channel in (left, right):
        channel += wet * np.fft.irfft(np.fft.rfft(channel) * room, n)
    stereo = np.stack([left, right], axis=1) * MASTER
    return np.tanh(stereo).astype(np.float32)  # gentle limiter: no clipping, no loudness jumps
