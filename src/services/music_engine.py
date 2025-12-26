"""Minimal deterministic beat player.

This file implements a tiny MusicEngine that plays a fixed 8-step pattern
`10100100` in a loop. Each step is 1.0 second long. When the pattern value
is 1 the engine plays a single-tone 1s WAV; when 0 it plays silence (1s).

Playback on macOS uses `afplay` (safe). If `afplay` is not present and
`simpleaudio` is available, it will use that; otherwise the engine is a no-op
and logs to /tmp/bvb-music.log.

This is intentionally tiny and deterministic so it's easy to inspect and
modify: change PATTERN or TONE_FREQ at the top of the file.
"""
from threading import Thread, Lock
import time
import math
import os
import sys
import tempfile
import wave
import array
import subprocess
import shutil

LOG_PATH = '/tmp/bvb-music.log'

SAMPLE_RATE = 22050
# Two independent 8-step patterns (snare and kick)
# Instrument names and default 8-step patterns (keep deterministic)
INSTRUMENT_NAMES = [
    'snare', 'kick', 'hat', 'open_hat', 'clap', 'tom_low', 'tom_high', 'rim', 'bass'
]

# Default 8-step patterns for each instrument (user-editable later)
INSTRUMENT_PATTERNS = {
    'snare':   [1,0,1,0,1,0,1,0],
    'kick':    [0,1,0,1,0,1,0,1],
    'hat':     [1,1,0,1,1,0,1,1],
    'open_hat':[0,0,1,0,0,1,0,0],
    'clap':    [0,1,0,0,1,0,0,1],
    'tom_low': [0,0,1,0,0,1,0,0],
    'tom_high':[1,0,0,1,0,0,1,0],
    'rim':     [0,0,0,1,0,0,0,1],
    'bass':    [1,0,0,0,1,0,0,0],
}
STEP_SECONDS = 0.05
# How many pattern cycles to concatenate into one playback file. Increasing
# this reduces the frequency of the (small) gap when playback restarts.
# Set to 1 for minimal memory use, or larger (e.g. 8 or 16) to hide gaps.
PATTERN_REPEAT = 16
TONE_FREQ = 440.0
TONE_AMPLITUDE = 0.25  # 0..1

# simpleaudio has caused native crashes on some macOS/ARM/Python builds (see
# crash report). Avoid importing/using it in-process to prevent EXC_BAD_ACCESS
# crashes. Prefer sounddevice (streaming) or macOS `afplay` subprocess.
SIMPLEAUDIO_AVAILABLE = False
sa = None

# Try sounddevice + numpy for low-latency streaming playback (preferred)
try:
    import sounddevice as sd
    import numpy as np
    SOUNDEVICE_AVAILABLE = True
except Exception:
    sd = None
    np = None
    SOUNDEVICE_AVAILABLE = False

AFPLAY_AVAILABLE = sys.platform == 'darwin' and shutil.which('afplay') is not None


def _log(msg: str):
    # Logging disabled to avoid interfering with game UI.
    # If you need logs for debugging later, restore writing to a file
    # or enable stderr output manually.
    return


def _write_wav_tone(fname: str, freq: float, duration: float, amp: float):
    frames = int(round(SAMPLE_RATE * duration))
    max_amp = int(32767 * amp)
    arr = array.array('h')
    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        v = math.sin(2.0 * math.pi * freq * t)
        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_snare(fname: str, duration: float, amp: float):
    """Synthesize a deterministic snare-like 1s sound using pseudo-noise
    plus a short tonal body. Uses an LCG for deterministic noise.
    """
    frames = int(round(SAMPLE_RATE * duration))
    max_amp = int(32767 * amp)
    arr = array.array('h')

    # simple deterministic LCG PRNG (32-bit)
    seed = 0x12345678
    state = seed

    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        # envelope: fast attack, medium decay
        env = math.exp(-10.0 * t)
        # deterministic noise sample in [-1,1]
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        noise = ((state >> 16) & 0x7FFF) / 32767.0
        noise = (noise * 2.0) - 1.0

        # tonal body (slightly pitched click)
        tone = math.sin(2.0 * math.pi * 180.0 * t) * math.exp(-20.0 * t)

        # mix: mostly noise with a small tonal click
        v = (noise * 0.9 + tone * 0.5) * env

        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)

    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_kick(fname: str, duration: float, amp: float):
    """Synthesize a deterministic kick-like sound (low sine with fast decay)."""
    frames = int(round(SAMPLE_RATE * duration))
    max_amp = int(32767 * amp)
    arr = array.array('h')
    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        # quick exponential decay
        env = math.exp(-12.0 * t)
        # falling pitch (simulate kick pitch drop)
        freq = 100.0 * (1.0 - 0.8 * (t / max(1e-9, duration)))
        v = math.sin(2.0 * math.pi * freq * t) * env
        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_hat(fname: str, duration: float, amp: float):
    """Short high-frequency noise (closed hi-hat)."""
    frames = int(round(SAMPLE_RATE * duration))
    max_amp = int(32767 * amp * 0.6)
    arr = array.array('h')
    state = 0xabcdef01
    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        env = math.exp(-50.0 * t)
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        noise = ((state >> 16) & 0x7FFF) / 32767.0
        noise = (noise * 2.0) - 1.0
        v = noise * env
        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_open_hat(fname: str, duration: float, amp: float):
    """Longer decay open hi-hat (noise with slower envelope)."""
    frames = int(round(SAMPLE_RATE * duration))
    max_amp = int(32767 * amp * 0.5)
    arr = array.array('h')
    state = 0x13579bdf
    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        env = math.exp(-8.0 * t)
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        noise = ((state >> 16) & 0x7FFF) / 32767.0
        noise = (noise * 2.0) - 1.0
        v = noise * env
        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_clap(fname: str, duration: float, amp: float):
    """Clap: stacked short noise bursts (deterministic)."""
    frames = int(round(SAMPLE_RATE * duration))
    max_amp = int(32767 * amp * 0.7)
    arr = array.array('h')
    state = 0x86420
    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        env = math.exp(-30.0 * t)
        # create two micro-bursts offset deterministically
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        noise1 = (((state >> 16) & 0x7FFF) / 32767.0) * 2.0 - 1.0
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        noise2 = (((state >> 16) & 0x7FFF) / 32767.0) * 2.0 - 1.0
        v = (noise1 * 0.6 + noise2 * 0.4) * env
        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_tom(fname: str, duration: float, amp: float, high=False):
    """Tom: low/med pitch sine with exponential decay."""
    frames = int(round(SAMPLE_RATE * duration))
    base = 220.0 if high else 120.0
    max_amp = int(32767 * amp * (0.8 if high else 0.9))
    arr = array.array('h')
    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        env = math.exp(-6.0 * t)
        # slight pitch glide
        freq = base * (1.0 - 0.5 * t / max(1e-9, duration))
        v = math.sin(2.0 * math.pi * freq * t) * env
        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_rim(fname: str, duration: float, amp: float):
    """Rim click: short high-frequency click"""
    frames = int(round(SAMPLE_RATE * duration))
    max_amp = int(32767 * amp * 0.7)
    arr = array.array('h')
    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        env = math.exp(-80.0 * t)
        v = math.sin(2.0 * math.pi * 3000.0 * t) * env
        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_bass(fname: str, duration: float, amp: float):
    """Bass synth: low sine with quick attack and medium decay."""
    frames = int(round(SAMPLE_RATE * duration))
    max_amp = int(32767 * amp * 0.9)
    arr = array.array('h')
    for n in range(frames):
        t = n / float(SAMPLE_RATE)
        env = math.exp(-5.0 * t)
        freq = 55.0 * (1.0 - 0.2 * t / max(1e-9, duration))
        v = math.sin(2.0 * math.pi * freq * t) * env
        s = int(max(-32767, min(32767, v * max_amp)))
        arr.append(s)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


def _write_wav_silence(fname: str, duration: float):
    frames = int(round(SAMPLE_RATE * duration))
    arr = array.array('h', [0] * frames)
    with wave.open(fname, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())


class MusicEngine:
    def __init__(self):
        self._running = False
        self._thread = None
        self._lock = Lock()
        # patterns per instrument (copy defaults so runtime can mutate safely)
        self.instrument_patterns = {k: list(v) for k, v in INSTRUMENT_PATTERNS.items()}
        self.step_seconds = float(STEP_SECONDS)
        self.tone_amp = float(TONE_AMPLITUDE)

        # pre-generate files: one WAV per instrument plus silence and the concatenated pattern
        self._instr_files = {}
        self._silence_file = None
        self._pattern_file = None
        self._pattern_bytes = None
        self._pattern_channels = None
        self._pattern_sampwidth = None
        self._pattern_rate = None
        self._pattern_np = None
        self._pattern_pos = 0
        # handles for currently playing audio so we can stop it immediately
        self._current_play_obj = None
        self._current_proc = None
        # persistent sounddevice stream (if used)
        self._sd_stream = None
        # prepare files (may set _pattern_file/_pattern_np)
        self._prepare_files()

    def _prepare_files(self):
        try:
            # create one file per instrument
            writers = {
                'snare': _write_wav_snare,
                'kick': _write_wav_kick,
                'hat': _write_wav_hat,
                'open_hat': _write_wav_open_hat,
                'clap': _write_wav_clap,
                'tom_low': lambda f, d, a: _write_wav_tom(f, d, a, high=False),
                'tom_high': lambda f, d, a: _write_wav_tom(f, d, a, high=True),
                'rim': _write_wav_rim,
                'bass': _write_wav_bass,
            }
            for instr in INSTRUMENT_NAMES:
                try:
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                    name = tf.name
                    tf.close()
                    # write deterministic instrument
                    writers[instr](name, self.step_seconds, self.tone_amp)
                    self._instr_files[instr] = name
                except Exception:
                    # on failure, skip instrument
                    self._instr_files[instr] = None
            # silence
            sf = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            sfname = sf.name
            sf.close()
            _write_wav_silence(sfname, self.step_seconds)
            self._silence_file = sfname

            # note: mixing will happen below when building the concatenated pattern
            try:
                names = {k: v for k, v in self._instr_files.items()}
                _log(f"music_engine(minimal): prepared instrument files={list(names.keys())} silence={self._silence_file}")
            except Exception:
                pass

            # prepare a concatenated pattern file (one cycle of the patterns)
            try:
                patternf = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                pattern_name = patternf.name
                patternf.close()

                # read raw arrays for each possible step type
                def _read_arr(fname):
                    with wave.open(fname, 'rb') as wf:
                        frames = wf.readframes(wf.getnframes())
                    a = array.array('h')
                    a.frombytes(frames)
                    return a

                # read arrays for each instrument (use silence if instrument missing)
                instr_arrs = {}
                for instr in INSTRUMENT_NAMES:
                    fname = self._instr_files.get(instr)
                    if fname and os.path.exists(fname):
                        instr_arrs[instr] = _read_arr(fname)
                    else:
                        instr_arrs[instr] = _read_arr(self._silence_file)

                # build pattern sequence repeated PATTERN_REPEAT times by mixing active instruments per step
                seq = array.array('h')
                plen = max(len(p) for p in self.instrument_patterns.values())
                repeat = int(max(1, globals().get('PATTERN_REPEAT', 1)))
                step_len = len(instr_arrs[INSTRUMENT_NAMES[0]]) if INSTRUMENT_NAMES[0] in instr_arrs else len(instr_arrs.get(self._silence_file, []))
                for r in range(repeat):
                    for i in range(plen):
                        # initialize per-step mixed buffer
                        # assume all instr arrays are same length (step_len)
                        for sidx in range(step_len):
                            total = 0
                            for instr in INSTRUMENT_NAMES:
                                pattern = self.instrument_patterns.get(instr, [0])
                                val = pattern[i % len(pattern)] if len(pattern) > 0 else 0
                                if val:
                                    total += int(instr_arrs[instr][sidx])
                            # clamp and append
                            if total > 32767:
                                total = 32767
                            elif total < -32767:
                                total = -32767
                            seq.append(int(total))

                # normalize to avoid clipping (scale if necessary)
                if len(seq) > 0:
                    mx = max(abs(x) for x in seq)
                    if mx == 0:
                        scale = 1.0
                    else:
                        scale = min(1.0, 32767.0 / float(mx))
                else:
                    scale = 1.0

                if scale < 0.999999:
                    for idx in range(len(seq)):
                        seq[idx] = int(max(-32767, min(32767, int(seq[idx] * scale))))

                # write pattern file
                with wave.open(pattern_name, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(seq.tobytes())

                self._pattern_file = pattern_name
                # We intentionally do NOT cache simpleaudio WaveObject bytes to avoid
                # importing/using simpleaudio (it can crash on some macOS/Python
                # combinations). If sounddevice is present we'll prepare a numpy
                # buffer instead (below).
                self._pattern_bytes = None
                self._pattern_channels = None
                self._pattern_sampwidth = None
                self._pattern_rate = None

                # If sounddevice + numpy available, create an int16 numpy array of the pattern
                try:
                    if SOUNDEVICE_AVAILABLE and np is not None:
                        # seq is array.array('h') (int16). Convert to numpy int16 without copy
                        self._pattern_np = np.frombuffer(seq.tobytes(), dtype=np.int16)
                        self._pattern_pos = 0
                    else:
                        self._pattern_np = None
                        self._pattern_pos = 0
                except Exception:
                    self._pattern_np = None
                    self._pattern_pos = 0
            except Exception as e:
                _log(f"music_engine(minimal): error preparing pattern file: {e}")
                self._pattern_file = None
        except Exception as e:
            _log(f"music_engine(minimal): error preparing files: {e}")
            self._snare_file = None
            self._kick_file = None
            self._mix_file = None
            self._silence_file = None
            self._pattern_file = None
            self._pattern_bytes = None
            self._pattern_channels = None
            self._pattern_sampwidth = None
            self._pattern_rate = None

    # ----------------------- sounddevice helpers -----------------------
    def _start_sd_stream(self) -> bool:
        """Start a persistent sounddevice OutputStream if possible.
        Returns True if stream started or was already running.
        """
        if not SOUNDEVICE_AVAILABLE or np is None:
            return False
        try:
            if getattr(self, '_sd_stream', None) is None:
                def _sd_callback(outdata, frames, time_info, status):
                    # outdata is (frames, channels)
                    if not getattr(self, '_running', False):
                        outdata.fill(0)
                        return
                    pos = getattr(self, '_pattern_pos', 0)
                    L = len(self._pattern_np) if getattr(self, '_pattern_np', None) is not None else 0
                    if frames <= 0 or L == 0:
                        outdata.fill(0)
                        return
                    if pos + frames <= L:
                        chunk = self._pattern_np[pos:pos+frames]
                        self._pattern_pos = (pos + frames) % L
                    else:
                        first = L - pos
                        chunk = np.empty(frames, dtype=np.int16)
                        chunk[:first] = self._pattern_np[pos:]
                        rem = frames - first
                        if rem > 0:
                            chunk[first:] = self._pattern_np[:rem]
                        self._pattern_pos = rem % L
                    outdata[:] = chunk.reshape(-1, 1)

                self._sd_stream = sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16', callback=_sd_callback)
                self._sd_stream.start()
            return True
        except Exception:
            # ensure we don't leave a half-open stream
            try:
                if getattr(self, '_sd_stream', None) is not None:
                    try:
                        self._sd_stream.stop()
                    except Exception:
                        pass
                    try:
                        self._sd_stream.close()
                    except Exception:
                        pass
            except Exception:
                pass
            self._sd_stream = None
            return False

    def _stop_sd_stream(self):
        try:
            if getattr(self, '_sd_stream', None) is not None:
                try:
                    self._sd_stream.stop()
                except Exception:
                    pass
                try:
                    self._sd_stream.close()
                except Exception:
                    pass
                self._sd_stream = None
        except Exception:
            pass

    def _wait_while_running(self, total_seconds: float):
        # sleep in short increments so stop() can interrupt playback quickly
        waited = 0.0
        step = 0.05
        while self._running and waited < total_seconds:
            time.sleep(min(step, total_seconds - waited))
            waited += step

    def start(self):
        if self._running:
            return
        # Prefer a persistent sounddevice OutputStream (lowest gap) when
        # available. If not available, fall back to an afplay-based thread loop.
        if SOUNDEVICE_AVAILABLE and getattr(self, '_pattern_np', None) is not None:
            try:
                # create a persistent stream that continuously loops the pattern
                def _sd_callback(outdata, frames, time_info, status):
                    if not self._running:
                        outdata.fill(0)
                        return
                    pos = self._pattern_pos
                    L = len(self._pattern_np)
                    if frames <= 0 or L == 0:
                        outdata.fill(0)
                        return
                    if pos + frames <= L:
                        chunk = self._pattern_np[pos:pos+frames]
                        self._pattern_pos = (pos + frames) % L
                    else:
                        first = L - pos
                        chunk = np.empty(frames, dtype=np.int16)
                        chunk[:first] = self._pattern_np[pos:]
                        rem = frames - first
                        if rem > 0:
                            chunk[first:] = self._pattern_np[:rem]
                        self._pattern_pos = rem % L
                    outdata[:] = chunk.reshape(-1, 1)

                self._pattern_pos = getattr(self, '_pattern_pos', 0)
                self._sd_stream = sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16', callback=_sd_callback)
                # mark running before starting stream so callback sees correct flag
                self._running = True
                self._sd_stream.start()
                _log("music_engine(minimal): started persistent sounddevice stream")
                # no thread needed when streaming continuously
                return
            except Exception as e:
                # if stream cannot be started, fall back to afplay loop below
                try:
                    if self._sd_stream is not None:
                        try:
                            self._sd_stream.stop()
                            self._sd_stream.close()
                        except Exception:
                            pass
                        self._sd_stream = None
                except Exception:
                    pass
                _log(f"music_engine(minimal): sounddevice stream failed: {e}")

        # fallback: require afplay to be present
        if not AFPLAY_AVAILABLE:
            _log("music_engine(minimal): no playback backend available (sounddevice/afplay missing)")
            return
        self._running = True
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        _log("music_engine(minimal): started (afplay loop)")

    def stop(self):
        if not self._running:
            return
        # signal loop to stop and immediately terminate any current playback
        self._running = False
        # stop any currently playing simpleaudio PlayObject or subprocess
        try:
            self._stop_current_playback()
        except Exception:
            pass
        # ensure sounddevice stream is stopped as well
        try:
            self._stop_sd_stream()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=1.0)
        _log("music_engine(minimal): stopped")

    def _stop_current_playback(self):
        """Terminate current playback immediately if possible."""
        # stop simpleaudio play object
        try:
            if self._current_play_obj is not None:
                try:
                    self._current_play_obj.stop()
                except Exception:
                    pass
                self._current_play_obj = None
        except Exception:
            pass

        # terminate afplay subprocess if running
        try:
            if self._current_proc is not None:
                try:
                    self._current_proc.kill()
                except Exception:
                    pass
                try:
                    self._current_proc.wait(timeout=0.2)
                except Exception:
                    pass
                self._current_proc = None
        except Exception:
            pass

        # stop sounddevice stream if running
        try:
            if self._sd_stream is not None:
                try:
                    self._sd_stream.stop()
                except Exception:
                    pass
                try:
                    self._sd_stream.close()
                except Exception:
                    pass
                self._sd_stream = None
        except Exception:
            pass

    def update_state(self, current_sleep, bird_counts=None):
        # no-op for minimal engine, kept for API compatibility
        with self._lock:
            pass

    def _play_file_blocking(self, fname: str):
        # Prefer in-memory simpleaudio playback for the main pattern file to avoid
        # process startup latency between loops. If that fails, fall back to afplay.
        # Prefer sounddevice streaming if available for the pattern file (lowest gap)
        if SOUNDEVICE_AVAILABLE and getattr(self, '_pattern_np', None) is not None and fname == getattr(self, '_pattern_file', None):
            try:
                if self._start_sd_stream():
                    total_seconds = len(self._pattern_np) / float(SAMPLE_RATE)
                    self._wait_while_running(total_seconds)
                    return
            except Exception:
                try:
                    self._stop_sd_stream()
                except Exception:
                    pass
        if SIMPLEAUDIO_AVAILABLE and hasattr(self, '_pattern_bytes') and self._pattern_bytes is not None and fname == getattr(self, '_pattern_file', None):
            try:
                wo = sa.WaveObject(self._pattern_bytes, self._pattern_channels, self._pattern_sampwidth, self._pattern_rate)
                po = wo.play()
                # store handle so we can stop it externally
                self._current_play_obj = po
                try:
                    po.wait_done()
                finally:
                    self._current_play_obj = None
                return
            except Exception:
                # fall through to afplay fallback
                self._current_play_obj = None
                pass

        if AFPLAY_AVAILABLE:
            try:
                # spawn afplay as a subprocess so we can kill it from stop()
                proc = subprocess.Popen(['afplay', fname])
                self._current_proc = proc
                try:
                    proc.wait()
                finally:
                    self._current_proc = None
                _log(f"music_engine(minimal): afplay finished file={fname} rc={proc.returncode}")
            except Exception as e:
                _log(f"music_engine(minimal): afplay error: {e}")
        elif SIMPLEAUDIO_AVAILABLE:
            # generic simpleaudio fallback for other files: read file and play
            try:
                import io
                import wave as _wave
                with _wave.open(fname, 'rb') as wf:
                    frames = wf.readframes(wf.getnframes())
                    channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    rate = wf.getframerate()
                wo = sa.WaveObject(frames, channels, sampwidth, rate)
                po = wo.play()
                self._current_play_obj = po
                try:
                    po.wait_done()
                finally:
                    self._current_play_obj = None
                _log(f"music_engine(minimal): simpleaudio played {fname}")
            except Exception as e:
                _log(f"music_engine(minimal): simpleaudio error: {e}")
        else:
            # Shouldn't reach here due to earlier guard
            time.sleep(self.step_seconds)

        # If sounddevice is available and we have an in-memory numpy pattern, prefer streaming
        if SOUNDEVICE_AVAILABLE and self._pattern_np is not None:
            # try to start a non-blocking stream and return (stream will run in callback)
            try:
                if self._start_sd_stream():
                    total_seconds = len(self._pattern_np) / float(SAMPLE_RATE)
                    # wait but allow stop() to interrupt faster
                    self._wait_while_running(total_seconds)
                    return
            except Exception:
                # if streaming fails, fall back to other mechanisms
                try:
                    if self._sd_stream is not None:
                        try:
                            self._sd_stream.stop()
                            self._sd_stream.close()
                        except Exception:
                            pass
                        self._sd_stream = None
                except Exception:
                    pass

        if SIMPLEAUDIO_AVAILABLE and hasattr(self, '_pattern_bytes') and self._pattern_bytes is not None and fname == getattr(self, '_pattern_file', None):
            try:
                wo = sa.WaveObject(self._pattern_bytes, self._pattern_channels, self._pattern_sampwidth, self._pattern_rate)
                po = wo.play()
                # store handle so we can stop it externally
                self._current_play_obj = po
                try:
                    po.wait_done()
                finally:
                    self._current_play_obj = None
                return
            except Exception:
                # fall through to afplay fallback
                self._current_play_obj = None
                pass
    def _run_loop(self):
        # Play the whole pattern file in a loop. This reduces per-step overhead
        # (afplay process startup) so tempos < ~0.1s behave correctly.
        while self._running:
            if self._pattern_file:
                self._play_file_blocking(self._pattern_file)
            else:
                # fallback: sleep for one pattern length
                plen = max(len(self.snare_pattern), len(self.kick_pattern))
                time.sleep(self.step_seconds * max(1, plen))

    def cleanup(self):
        # remove temp files
        try:
            # stop playback and streams first
            try:
                self._stop_current_playback()
            except Exception:
                pass
            try:
                self._stop_sd_stream()
            except Exception:
                pass
            if self._snare_file and os.path.exists(self._snare_file):
                os.unlink(self._snare_file)
            if self._kick_file and os.path.exists(self._kick_file):
                os.unlink(self._kick_file)
            if self._mix_file and os.path.exists(self._mix_file):
                os.unlink(self._mix_file)
            if self._silence_file and os.path.exists(self._silence_file):
                os.unlink(self._silence_file)
            if hasattr(self, '_pattern_file') and self._pattern_file and os.path.exists(self._pattern_file):
                os.unlink(self._pattern_file)
            _log("music_engine(minimal): cleaned up temp files")
        except Exception:
            pass


_global_engine = None


def get_engine():
    global _global_engine
    if _global_engine is None:
        _global_engine = MusicEngine()
    return _global_engine


def _shutdown_engine():
    """Ensure engine is stopped and temp files removed at interpreter exit."""
    try:
        global _global_engine
        if _global_engine is not None:
            try:
                _global_engine.stop()
            except Exception:
                pass
            try:
                _global_engine.cleanup()
            except Exception:
                pass
    except Exception:
        pass


try:
    import atexit
    atexit.register(_shutdown_engine)
except Exception:
    pass
