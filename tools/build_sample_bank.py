#!/usr/bin/env python3
"""Build the instrument sample bank of the music (media/music/bank/).

    python3 tools/build_sample_bank.py [--soundfont FILE.sf2]

The music is played by the game itself (src/services/music/): it writes the
notes of every part and plays them with these samples, pitched to each note.
The samples are recorded once, here, from a General MIDI SoundFont with
FluidSynth: a few notes per instrument (one every half octave), mono,
22050 Hz, Ogg Vorbis. The default SoundFont is FluidR3_GM (MIT licence: the
samples may ship with the game), e.g. ``apt install fluidsynth fluid-soundfont-gm``.

Writes media/music/bank/<instrument>_<note>.ogg and media/music/bank/bank.json.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services.music.instruments import INSTRUMENTS, SAMPLE_RATE  # noqa: E402

BANK = ROOT / 'media' / 'music' / 'bank'
DEFAULT_SF2 = '/usr/share/sounds/sf2/FluidR3_GM.sf2'


def _midi_file(path, program, note, seconds, drum=False):
    import mido

    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(60), time=0))
    channel = 9 if drum else 0
    if not drum:
        track.append(mido.Message('program_change', program=program, channel=channel, time=0))
    track.append(mido.Message('control_change', control=91, value=0, channel=channel, time=0))  # no reverb
    track.append(mido.Message('control_change', control=93, value=0, channel=channel, time=0))  # no chorus
    track.append(mido.Message('note_on', note=note, velocity=100, channel=channel, time=0))
    track.append(mido.Message('note_off', note=note, velocity=0, channel=channel, time=int(seconds * 480)))
    track.append(mido.MetaMessage('end_of_track', time=480))
    mid.tracks.append(track)
    mid.save(path)


def record(sf2, name, spec, note, work):
    midi_path = work / f'{name}_{note}.mid'
    wav_path = work / f'{name}_{note}.wav'
    out = BANK / f'{name}_{note}.ogg'
    _midi_file(midi_path, spec.get('program', 0), note, spec['hold'], drum=spec.get('drum', False))
    subprocess.run(
        [
            'fluidsynth',
            '-ni',
            '-q',
            '-R',
            '0',
            '-C',
            '0',
            '-g',
            '1.0',
            '-r',
            str(SAMPLE_RATE),
            '-F',
            str(wav_path),
            sf2,
            str(midi_path),
        ],
        check=True,
        capture_output=True,
    )
    # Mono, the silence at the end cut, Ogg Vorbis
    subprocess.run(
        [
            'ffmpeg',
            '-y',
            '-loglevel',
            'error',
            '-i',
            str(wav_path),
            '-ac',
            '1',
            '-ar',
            str(SAMPLE_RATE),
            '-af',
            'areverse,silenceremove=start_periods=1:start_threshold=-60dB,areverse',
            '-c:a',
            'libvorbis',
            '-q:a',
            '3',
            str(out),
        ],
        check=True,
    )
    return out.name


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--soundfont', default=DEFAULT_SF2)
    args = parser.parse_args()
    if not Path(args.soundfont).exists():
        raise SystemExit(f'SoundFont not found: {args.soundfont} (apt install fluid-soundfont-gm, or --soundfont)')
    BANK.mkdir(parents=True, exist_ok=True)
    for old in BANK.glob('*.ogg'):
        old.unlink()
    index = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for name, spec in INSTRUMENTS.items():
            notes = (
                spec['notes'] if 'notes' in spec else list(range(spec['low'], spec['high'] + 1, spec.get('step', 6)))
            )
            index[name] = {str(n): record(args.soundfont, name, spec, n, work) for n in notes}
            print(f'{name}: {len(notes)} samples')
    (BANK / 'bank.json').write_text(json.dumps(index, indent=1, sort_keys=True))
    size = sum(f.stat().st_size for f in BANK.glob('*.ogg'))
    print(f'{sum(len(v) for v in index.values())} samples, {size / 1e6:.1f} MB in {BANK}')


if __name__ == '__main__':
    main()
