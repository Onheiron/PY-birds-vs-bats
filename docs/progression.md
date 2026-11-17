# Meta progression

What carries over from one run to the next (`src/engine/meta.py`): a
**profile** saved in the save folder (`profile.json`) with the **gold**, the
**upgrades** bought, the **global achievements** unlocked and lifetime
counters.

## Gold and achievements

Gold comes from achievements. There are two kinds (`achievements` in
`config.yml`):

- **Run achievements** are goals for a single run. They can be met again
  every run, and pay their gold every time: they are a run's income.
- **Global achievements** are goals over every run played. Each pays once,
  the first time.

The run's gold is banked when the run ends (game over, quit or back to the
title), multiplied by the Gold Digger upgrade; the game over screen shows it.
Achievements met during a run are announced on the right panel. The title
menu's ACHIEVEMENTS pages list both kinds, with the global ones already
unlocked ticked.

A goal is `all: {counter: minimum}` and optionally `most: {counter:
maximum}` ("reach level 6 losing at most 3 birds"). Counters, counted from
game events: level, score, bats, elites, mini_bats, bosses, eggs,
rare/epic/legendary/mythical_eggs, hatched, pacts, swaps, powers,
double_powers (second uses in an ascent), battery_shots (Red shots with two
shooters beside), full_charges (Purple), birds_lost; global goals also have
runs. Lifetime counters add the runs up, except level and score, which keep
the best.

### Run achievements

| Achievement | Goal | Gold |
|---|---|--:|
| First Steps | Reach level 1-2 | 2 |
| Forest Edge | Reach level 1-3 | 3 |
| Borderlands | Reach the second world | 5 |
| Border Keeper | Reach level 2-3 | 8 |
| Beyond the Border | Reach the third world | 15 |
| Deep Woods | Reach the fourth world | 20 |
| Swamp Walker | Reach the fifth world | 25 |
| Cave Diver | Reach the last world | 30 |
| Summit | Reach level 6-3 | 40 |
| Boss Down | Defeat a boss | 5 |
| Double Trouble | Defeat two bosses in a run | 10 |
| Boss Rush | Defeat four bosses in a run | 20 |
| Lord of the Skies | Defeat six bosses in a run | 40 |
| Pest Control | Kill 25 bats in a run | 4 |
| Exterminator | Kill 75 bats in a run | 8 |
| Plague Doctor | Kill 150 bats in a run | 15 |
| Elite Hunter | Kill an elite bat | 4 |
| Elite Slayer | Kill 5 elite bats in a run | 10 |
| Rare Find | Open a rare egg | 2 |
| Epic Find | Open an epic egg | 5 |
| Legendary Find | Open a legendary egg | 12 |
| Mythical Find | Open a mythical egg | 30 |
| Full Nest | Hatch 3 birds in a run | 4 |
| Deal Maker | Make a pact | 3 |
| Red Battery | Fire 5 Red shots with two shooters beside | 5 |
| Full Charge | Fire a fully charged Purple shot | 4 |
| Encore | Fire 10 second powers in a run | 4 |
| Untouched | Reach level 1-3 without losing a bird | 6 |
| Careful Flock | Reach level 2-3 losing at most 3 birds | 12 |
| Six Figures | Score 100 | 4 |
| Millionaire | Score 1 | 10 |
| Tycoon | Score 10 | 20 |

### Global achievements

| Achievement | Goal | Gold |
|---|---|--:|
| Hatchling | Play your first run | 10 |
| Regular | Play 10 runs | 30 |
| Devoted | Play 50 runs | 80 |
| Bat Bane | Kill 500 bats in all | 30 |
| Bat Doom | Kill 2 | 80 |
| Elite Bane | Kill 25 elite bats in all | 40 |
| Boss Bane | Defeat 10 bosses in all | 40 |
| Second World | Reach level 2-3 for the first time | 25 |
| Third World | Reach the third world for the first time | 40 |
| Fourth World | Reach the fourth world for the first time | 60 |
| Last World | Reach the last world for the first time | 100 |
| Champion | Reach level 6-3 | 200 |
| Egg Collector | Open 200 eggs in all | 30 |
| Legend Hunter | Open 5 legendary eggs in all | 60 |
| Nursery | Hatch 30 birds in all | 40 |
| Dealer | Make 10 pacts in all | 30 |

## Upgrades

Bought with gold from the title menu (UPGRADES: one screen per branch; the
line under the list says what the next level does or what it needs). Every
upgrade has levels; each level costs more and adds its effect again. They
apply once, at the start of every new run (a saved run that is loaded keeps
what it had).

| Branch | Upgrade | What it does | Effect | Costs | Needs |
|---|---|---|---|---|---|
| Talons | **Sharp Talons** | Every bird hits harder | +4% damage per level (max 5: +20% damage) | 15, 25, 40, 60, 90 | — |
| Talons | **Piercing** | Ignore some armor | +3 armor pierce per level (max 3: +9 armor pierce) | 30, 50, 80 | Sharp Talons 2 |
| Talons | **Keen Eye** | More critical hits | +3% crit chance per level (max 3: +9% crit chance) | 40, 65, 100 | Piercing 1 |
| Talons | **Giant Slayer** | More damage to elites and bosses | +8% damage vs elites per level (max 3: +24% damage vs elites) | 35, 60, 95 | Sharp Talons 3 |
| Wings | **Light Bones** | Birds rise faster | +1.5 rising speed per level (max 5: +7.5 rising speed) | 15, 25, 40, 60, 90 | — |
| Wings | **Air Brakes** | Birds fall more slowly | −1.5 falling speed per level (max 4: −6 falling speed) | 20, 35, 55, 85 | Light Bones 1 |
| Wings | **Encore** | One more power per ascent | +1 power use per ascent per level (max 1: +1 power use per ascent) | 250 | Air Brakes 3 |
| Nerve | **Steady** | Scared birds fall less fast | +5% fear resistance per level (max 4: +20% fear resistance) | 15, 25, 40, 65 | — |
| Nerve | **Short Fear** | Scares wear off sooner | −8% fear duration per level (max 3: −24% fear duration) | 30, 50, 80 | Steady 2 |
| Nerve | **Fearless** | Some scares miss | +5% fear immunity per level (max 3: +15% fear immunity) | 45, 70, 110 | Short Fear 1 |
| Nest | **Extra Life** | Start with one more life | +1 starting lives per level (max 3: +1 starting lives) | 25, 60, 120 | — |
| Nest | **Safety Net** | Birds may bounce back from the floor | +3% floor save per level (max 3: +9% floor save) | 40, 70, 110 | Extra Life 1 |
| Nest | **Wide Nest** | Every egg offers one more card | +1 choice per egg per level (max 1: +1 choice per egg) | 180 | Safety Net 1 |
| Fortune | **Gold Digger** | More gold from achievements | +10% gold per level (max 5: +10% gold) | 15, 25, 40, 60, 90 | — |
| Fortune | **Lucky Eggs** | Enemies drop rarer eggs | +2% luck (rarer drops) per level (max 3: +6% luck (rarer drops)) | 30, 50, 80 | Gold Digger 1 |
| Fortune | **Rerolls** | One more egg reroll per run | +1 egg reroll this run per level (max 3: +1 egg reroll this run) | 25, 45, 70 | Gold Digger 2 |
| Fortune | **Skips** | One more egg skip per run | +1 egg skip this run per level (max 2: +1 egg skip this run) | 30, 55 | Rerolls 1 |
| Fortune | **Renown** | Start with more prestige | +0.5 prestige per level (max 4: +2 prestige) | 35, 55, 85, 130 | Lucky Eggs 1 |

Maxing the whole tree costs 3515 gold.

## Tuning it

`tools/campaign.py` plays **campaigns**: a player's runs one after the
other, from a new profile, spending the gold on upgrades between runs
(`--buy balanced`, `cheapest` or a branch). It reports, run by run, the
median level, how many players reach each world and the gold earned:

```bash
python3 tools/campaign.py --campaigns 12 --runs 15 --bot average
```

The aim (`docs/balance.md`): in the first runs the second world is hard to
get past; upgrades bought over a few runs open it, and the later worlds
after that.
