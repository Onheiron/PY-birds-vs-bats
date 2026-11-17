# Bot strategies

The bot (`src/sim/bot.py`) always tries to keep its birds alive; a
**strategy** (`src/sim/strategy.py`) says what else it is after. Every
strategy is a set of bot fields, so they can be mixed and tuned.

| Field | What it does |
|---|---|
| `max_gear` | Above this gear, swap two birds to shed momentum (a swap costs 20% of the momentum to the next gear). Slower game: less damage, score and distance per minute, more time to react. 0 = never. |
| `brake_when_falling` | Also brake when this many birds are falling at once. 0 = never. |
| `formation` | Swap birds into an arrangement where synergies work: `red_battery` (Reds, Purples, Patchworks side by side: each rising neighbour adds to a Red's shot), `yellow_guard` (Blues next to Yellows: a Yellow's chain cures scared Blues beside the birds it bounces), `white_center` (Whites in the middle, Yellows / Reds / Blues within their two-lane relay). One swap at most every `formation_every` frames. |
| `keep_birds` | Look after at most this many birds; the least valuable (grade, prestige) are let fall. |
| `favorites`, `cull_others` | Kinds to protect first and to take from bird cards; with `cull_others` the other birds are let go to free lanes for new eggs. |
| `min_lives_to_cull` | Every lost bird costs a life: birds are let go only while lives stay above this (default 3). |
| `card_policy`, `pact_policy` | `smart` (rarity, then kind), `adaptive` (what the flock needs now: fear cards when birds are scared, survival when lives are low, luck / prestige / more choices early, boosts during a boss...), `first`, `random`; pacts also `refuse`. |
| `swap_slack` | Frames of margin a strategic swap needs before the next bird is due. |

Named strategies (`STRATEGIES`):

| Name | Fields |
|---|---|
| default | none |
| brake | `max_gear=7` |
| brake_hard | `max_gear=5`, `brake_when_falling=4` |
| red_battery / yellow_guard / white_center | `formation=...` |
| few_birds | `keep_birds=5` |
| favorites | `favorites=[RED, PURPLE, WHITE, STEALTH]`, `cull_others=true` |
| adaptive | `card_policy=adaptive`, `pact_policy=adaptive` |
| cautious | `max_gear=7`, `keep_birds=7`, adaptive cards and pacts |

## Running them

Compare strategies on the same seeds:

```bash
python3 tools/simulate.py --runs 24 --max-minutes 12 --strategies default,brake,yellow_guard,few_birds,adaptive
```

Tune one, or mix fields, with variants (`bot.` keys are bot fields):

```bash
python3 tools/simulate.py --runs 24 --variant "gear 6: bot.max_gear=6" --variant "gear 8: bot.max_gear=8"
```

```bash
python3 tools/simulate.py --variant "reds: bot.strategy=favorites; bot.favorites=[RED, PURPLE]"
```

Watch one play:

```bash
python3 game.py --bot expert --strategy yellow_guard
```

The report has a "Strategy" section: swaps, brakes, formation swaps and
birds let go per game.

## First results

Expert bot, default flock, 24 games per strategy, 12 minutes of game time
at most (`--seed 1`):

| Strategy | Game over within 12 min | Median level | Median score | Mean gear | Kills | Swaps | Birds let go |
|---|:-:|:-:|--:|:-:|:-:|:-:|:-:|
| default | 88% | 7 | 1,135,276 | 6.9 | 21.2 | 0.0 | 0.0 |
| brake | 54% | 8 | 2,874,505 | 6.5 | 23.5 | 4.5 | 0.0 |
| brake_hard | 58% | 4 | 30,502 | 3.3 | 9.3 | 93.9 | 0.0 |
| red_battery | 92% | 7 | 818,068 | 6.7 | 21.0 | 1.9 | 0.0 |
| yellow_guard | 75% | 7 | 2,219,522 | 7.0 | 27.1 | 2.4 | 0.0 |
| white_center | 67% | 7.5 | 2,805,830 | 6.9 | 22.4 | 2.4 | 0.0 |
| few_birds | 100% | 5 | 107,256 | 6.2 | 9.2 | 0.0 | 6.1 |
| favorites | 96% | 5.5 | 387,420 | 6.4 | 12.3 | 0.0 | 4.4 |
| adaptive | 100% | 7 | 724,480 | 6.9 | 20.2 | 0.0 | 0.0 |
| cautious | 79% | 5.5 | 88,924 | 6.1 | 11.5 | 2.3 | 5.5 |

What it suggests, with the caveat that 24 games leave ±10 points of noise on
the game-over rate:

- **Braking a little works.** Keeping the gear at 7 or below (4–5 swaps a
  game) brings game over from 88% to 54%, reaches a level further and more
  than doubles the score: the extra control is worth more than the speed.
  Braking hard (gear 5, ~95 swaps) also survives more, but the run crawls
  (median level 4, a fraction of the score): the bot spends its time
  swapping and the game barely moves.
- **Formations help, for the wrong reasons in part.** Yellow guard and White
  centre do better than default, but each formation swap also brakes and
  sends two birds back to the starting line; the gain is not only synergy.
  Red battery does nothing measurable.
- **Letting birds go costs lives.** Every lost bird is a life, so few_birds
  and favorites end in game over more often; with lives regained only by
  hatching, the trade-off does not pay with the current rules.
- **The adaptive card choice is not better yet** than the simple rarity-first
  rule: its weights (`_STAT_NEED` in `src/sim/strategy.py`) are a first guess
  to tune.
