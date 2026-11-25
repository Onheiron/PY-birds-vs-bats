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
The new loop starts at the bar and beat the old one was at, so a change of
flock or gear never restarts the piece.

## Bosses

Every kind of boss has its theme (`boss.py`), written in C and played on the
world's tonic:

| Boss | Character | Instruments |
|---|---|---|
| Bat King (normal) | a solemn march in minor | church organ, tuba, choir, timpani |
| Tree | slow and heavy | cello, bassoon, strings, toms, timpani |
| Wind | whirling runs | piccolo, cello, choir, driving drums |
| Jelly | soft, chromatic, wobbling | vibraphone, synth bass, strings |
| Owl | a night waltz in 3/4 | ocarina, bassoon, choir |

- **Arrival**: the world's music is corrupted for 8 bars (`bridge`): for 4
  the boss's bass creeps in while the world's music wobbles out of tune, for
  4 more its lead takes over while the world's music is muffled, dirtied and
  pushed away. Then the boss's loop plays alone.
- **The flock** plays its parts on the boss's chords, in its style: marcato
  (Bat King), staccato and an octave down (Tree), echoed an octave up (Wind),
  wobbling (Jelly), sparser in 3/4 (Owl).
- **Health**: at 66%, 33% and 10% of the boss's health the world's melody
  comes back over the boss's loop, louder each time, in the boss's mode,
  and the boss's lead steps back.
- **Defeat**: the boss_death effect, then the world's music again.

The music is always on when the game starts; SETTINGS > SOUND turns it off
for the session.

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
| hit | a bird hits an enemy or an obstacle | a short dry low tom (0.12 s) |
| destroy | an obstacle or an enemy is destroyed | one damped timpani stroke (0.3 s) |
| powerup | a power-up is picked up | harp glissando up, celesta |
| egg | an egg is picked up | celesta chime, glockenspiel |
| level_up | a new level | trumpet arpeggio, brass chord, crash |
| bird_lost | a bird is lost | clarinet falling a minor third |
| bat_death | a bat is killed | a tiny chiptune squeak (0.18 s) |
| boss_scream | the Bat King arrives, or screams | tremolo strings and choir sliding down, taiko |
| tree_arrive | the Old Tree arrives | two cellos creaking down, timpani |
| wind_arrive | the Gale arrives | piccolo and strings sweeping up, choir swell |
| jelly_arrive | the Jelly arrives | a low synth bass "blorp", vibraphone cluster |
| owl_arrive | the Night Owl arrives | "hoo... hoo-hoo" on the ocarina, low choir |
| branch_break | a branch of the Tree breaks | dry toms, timpani, a cello cracking down |
| flower_bloom | a flower of the Tree opens | three music box notes up (0.4 s) |
| wind_gust | the Gale's wind turns | a pan flute sliding up (0.5 s) |
| jelly_spawn | the Jelly spits a bat | a short synth bass squish (0.3 s) |
| owl_spell | the Owl casts a spell | diminished celesta run, choir |
| meteor | the Owl's meteor shower | tremolo strings diving, timpani impact |
| boss_death | a boss is defeated | timpani roll, big major chord, harp run |
| game_over | the game is over | the sad trombone |
| swap | two birds swap | pan flute swoop |
| card_take | a card or a pact is taken | harp arpeggio, celesta |
| menu_move / menu_select / menu_back | menus and choices | music box tick, celesta up / down |

The bounce has none on purpose: it would play all the time. The effects that
play very often (hit, destroy, bat killed, flower, gust, jelly spit) are short, dry and soft, so they
never cover the music. Without the
sample bank the effects fall back to the synthesized ones (`synth.py`).

## Changing it

- The notes: `src/services/music/score.py` (themes, chords, one function per part).
- The instruments: `src/services/music/instruments.py`; after changing which
  instruments or notes are sampled, rebuild the bank (needs FluidSynth and a
  GM SoundFont, e.g. `apt install fluidsynth fluid-soundfont-gm`):

```bash
python3 tools/build_sample_bank.py
```
