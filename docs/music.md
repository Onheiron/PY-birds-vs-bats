# Music

The game writes its own music and plays it with real instrument samples
(`src/services/music/`). Nothing is pre-recorded but the samples: a few notes
per instrument (one every half octave), 3 MB in `media/music/bank/`, recorded
once from the FluidR3 General MIDI SoundFont (MIT licence,
`media/music/LICENSE-FluidR3.txt`) by `tools/build_sample_bank.py`.

## What plays

Every world has a theme of 16 bars for its own instrument, a key, a chord for
every bar and a tempo (`score.py`, `WORLDS`):

| World | Theme | Instrument | Key | Tempo |
|---|---|---|---|---|
| Windy Woods | Soaring The Woods | flute | C major | 100 |
| The Borders | Creeps | alto sax | C ionian #5 | 92 |
| Rotten Marshes | Entering The Wastes | harpsichord | B locrian | 84 |
| The Dark Swamp | The Circle | bass guitar | E phrygian | 76 |
| The Void Cave | The Leech | overdriven guitar | D dorian | 120 |
| Mountain Range | Homebound | violin | A minor | 72 |

On top of the theme and the world's drums, every bird type in the flock plays
its part on the same chords, with its instrument:

| Bird | Instrument | Part |
|---|---|---|
| Yellow | marimba | bouncing arpeggios |
| Red | trumpet (2+ Reds: brass section) | stabs, chords, fanfares |
| Blue | clarinet | guide tones, countermelody |
| Purple | French horn | long swelling notes |
| White | celesta | bright accents |
| Gold | glockenspiel | sparkles up the chord |
| Orange (Phoenix) | trombones | power fifths |
| Patchwork | accordion | oom-pah |
| Cookie | pizzicato strings | light offbeats |
| Clockwork | music box | ticking figure |
| Stealth | choir | soft held chords |
| Dinosaur | tuba | the bass line |
| Glitch | square wave (chiptune) | random chord tones |
| Twister | pan flute | gliding long notes |
| Frosty | harp | icy arpeggios |
| Poison | oboe | a slow, sour line |
| Berserk | taiko | war drums |
| Rock | timpani | deep strokes |
| Rainbow | string ensemble | the richest chords |
| Zombie | bassoon | clumsy staccato |
| bats | tremolo strings | a dissonant cluster |

Each part has 3 x 3 versions:

- **quantity**: 1 bird of the type, 2-3, 4 or more (bats: 1-2, 3-4, 5+): more
  voices, fuller (one Red is a trumpet, more Reds a brass section). White,
  Gold, Orange and Rainbow, one at a time, always play the first;
- **speed**: gears 1-3, 4-6, 7-10: the tempo (x0.92, x1.08, x1.26 of the
  world's) and a calmer or more driving rhythm.

The loop (64 beats) is rendered in the background when what plays changes
step, and cross-faded in (`arrangement.py`, `sampler.py`, `src/services/audio.py`);
parts already rendered are kept. The level is steady whatever the flock.

## Screens

- **Title and its menus**: a theme in G major that loops (flute and violin,
  harp, pizzicato bass, strings, light drums).
- **Game over**: the sad trombone, then a short A minor phrase (violin,
  strings, harp) and a calm loop (strings, harp, celesta) while the screen stays.

The music holds while the game is paused (`src/services/music/screens.py`).

## Sound effects

Played with the same instruments (`src/services/music/effects.py`), made once
in the background when the audio opens:

| Effect | When | Sound |
|---|---|---|
| hit | a bird hits an enemy or an obstacle | low tom, short low pizzicato |
| destroy | an obstacle or an enemy is destroyed | timpani, crash, harp run down |
| powerup | a power-up is picked up | harp glissando up, celesta |
| egg | an egg is picked up | celesta chime, glockenspiel |
| level_up | a new level | trumpet arpeggio, brass chord, crash |
| bird_lost | a bird is lost | clarinet falling a minor third |
| bat_death | a bat is killed | chiptune squeak sliding down |
| boss_scream | a boss screams | tremolo strings and choir sliding down, taiko |
| boss_death | a boss is defeated | timpani roll, big major chord, harp run |
| game_over | the game is over | the sad trombone |
| swap | two birds swap | pan flute swoop |
| card_take | a card or a pact is taken | harp arpeggio, celesta |
| menu_move / menu_select / menu_back | menus and choices | music box tick, celesta up / down |

The bounce has none on purpose: it would play all the time. Without the
sample bank the effects fall back to the synthesized ones (`synth.py`).

## Changing it

- The notes: `src/services/music/score.py` (themes, chords, one function per part).
- The instruments: `src/services/music/instruments.py`; after changing which
  instruments or notes are sampled, rebuild the bank (needs FluidSynth and a
  GM SoundFont, e.g. `apt install fluidsynth fluid-soundfont-gm`):

```bash
python3 tools/build_sample_bank.py
```
