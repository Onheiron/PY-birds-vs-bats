# Meta progression

What carries over from one run to the next (`src/engine/meta.py`): a
**profile** saved in the save folder (`profile.json`) with the **gold**, the
**upgrades** bought, the **global achievements** unlocked and lifetime
counters.

## Gold and achievements

Gold comes from two places (`run_reward` and `achievements` in `config.yml`):

- **The run's reward**, paid at the end of every run (game over, quit or back
  to the title): 1 gold per level reached, 4 per boss defeated and 1 per 25
  bats, multiplied by the difficulty (PEACEFUL x0.5, ADVENTURE x1,
  SURVIVAL x1.5, LEGENDARY x2) and by the Gold Digger upgrade.
- **Achievements**, each paid once, the first time it is reached. They are
  grouped (Exploration, Bosses, Flock, Skill, Build, Collection, Totals) and
  pay 2520 gold in all.

The game over screen shows the run's reward and what the achievements
reached in it paid. Achievements are announced on the right panel when they
are reached; the title menu's ACHIEVEMENTS lists the groups with how many are
done, and each page ticks the ones already reached.

A goal is `all: {counter: minimum}` and optionally `most: {counter:
maximum}` ("reach level 6 losing at most 3 birds"). Goals are over every run
played (lifetime counters: they add the runs up, except level, score and
max_gear, which keep the best), or, with `in_a_run: true`, within a single
run. Counters, counted from game events: level, score, max_gear, bats,
elites, mini_bats, bosses, eggs, rare/epic/legendary/mythical_eggs, hatched,
pacts, swaps, powers, double_powers (second uses in an ascent),
battery_shots (Red shots with two shooters beside), full_charges (Purple),
birds_lost, evolved_gold/white/orange (evolutions), won, won_survival,
won_legendary; per world, counted when its boss falls: clean_worlds (no bird
lost), swapless_worlds, full_house_worlds (every lane with a living bird),
clean_bosses (no bird lost during the boss); and runs, boss_kinds (kinds of
boss defeated) and birds_discovered (Birdpedia).

### Achievements

**Exploration**

| Achievement | Goal | Gold |
|---|---|--:|
| First Steps | Reach level 1-2 | 10 |
| Borderlands | Reach the second world | 20 |
| Beyond the Border | Reach the third world | 35 |
| Deep Woods | Reach the fourth world | 50 |
| Swamp Walker | Reach the fifth world | 70 |
| Cave Diver | Reach the last world | 90 |
| Summit | Reach level 6-3 | 120 |
| Champion | Defeat the last boss | 200 |
| Survivor | Win on SURVIVAL | 250 |
| Legend | Win on LEGENDARY | 400 |

**Bosses**

| Achievement | Goal | Gold |
|---|---|--:|
| Boss Down | Defeat a boss | 15 |
| Boss Bane | Defeat 10 bosses in all | 40 |
| Menagerie | Defeat every kind of boss | 100 |

**Flock**

| Achievement | Goal | Gold |
|---|---|--:|
| Golden Touch | Evolve a Yellow into Gold | 40 |
| Templar | Evolve a Blue into White | 40 |
| Rebirth | Evolve a Red into Phoenix | 40 |
| Birdwatcher | Discover every bird | 100 |
| Full House | End a world with all 9 birds | 50 |
| Nursery | Hatch 30 birds in all | 40 |

**Skill**

| Achievement | Goal | Gold |
|---|---|--:|
| Not a Feather | A world without losing a bird | 40 |
| Flawless | A boss without losing a bird | 40 |
| Top Gear | Reach gear 10 | 30 |
| Steady Hands | A world without swapping | 30 |
| Careful Flock | Reach 2-3 losing at most 3 birds (in one run) | 40 |

**Build**

| Achievement | Goal | Gold |
|---|---|--:|
| Red Battery | 5 Red battery shots in a run (in one run) | 25 |
| Full Charge | Fire a fully charged Purple shot | 15 |
| Deal Maker | Make 3 pacts in a run (in one run) | 40 |
| Encore | 10 second powers in a run (in one run) | 20 |

**Collection**

| Achievement | Goal | Gold |
|---|---|--:|
| Egg Collector | Open 200 eggs in all | 30 |
| Legend Hunter | Open 5 legendary eggs in all | 60 |
| Mythical Find | Open a mythical egg | 100 |

**Totals**

| Achievement | Goal | Gold |
|---|---|--:|
| Hatchling | Play your first run | 10 |
| Regular | Play 10 runs | 30 |
| Devoted | Play 50 runs | 80 |
| Bat Bane | Kill 500 bats in all | 30 |
| Bat Doom | Kill 2 | 80 |
| Elite Bane | Kill 25 elite bats in all | 40 |
| Millionaire | Score 1 | 20 |
| Tycoon | Score 10 | 50 |

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
| Fortune | **Gold Digger** | More gold at the end of every run | +10% gold per level (max 5: +10% gold) | 15, 25, 40, 60, 90 | — |
| Fortune | **Lucky Eggs** | Enemies drop rarer eggs | +2% luck (rarer drops) per level (max 3: +6% luck (rarer drops)) | 30, 50, 80 | Gold Digger 1 |
| Fortune | **Rerolls** | One more egg reroll per run | +1 egg reroll this run per level (max 3: +1 egg reroll this run) | 25, 45, 70 | Gold Digger 2 |
| Fortune | **Skips** | One more egg skip per run | +1 egg skip this run per level (max 2: +1 egg skip this run) | 30, 55 | Rerolls 1 |
| Fortune | **Renown** | Start with more prestige | +0.5 prestige per level (max 4: +2 prestige) | 35, 55, 85, 130 | Lucky Eggs 1 |

Maxing the whole tree costs 3515 gold.

## Fixed unlocks

Besides the stat upgrades, the tree has upgrades that change how a run starts
and goes (`upgrades.tree` in config.yml):

- **Formation** (Flock, 60 gold): choose the nine starting birds among the
  ones discovered (TITLE > FORMATION; evolved birds and zombies never). The
  choice is kept in the profile.
- **Opening Card** (Flock, 40): every run starts with a free common egg.
- **Training** (Flock, 80 and 150): every bird starts one grade higher per
  level. **Veterans** (one per bird type, 30 each): birds of that type start
  one grade higher (on top of Training).
- **Merchant Stock** (Fortune, 50 and 90) and **Haggling** (60 and 100): see
  the merchant below.
- **Rerolls** and **Skips** go up to 5 levels.

Every level of an upgrade adds its effect again (Extra Life 3 is +3 lives,
Gold Digger 5 is +50% gold).

### The merchant

Between worlds, after the boss's pact (not after the last world), the
merchant offers wares paid with the run's gold, which then comes off the
gold the run pays at its end (`merchant` in config.yml): a common egg (4), a
rare egg (8), a life (5); with Merchant Stock an epic egg (14) and a lucky
feather (one more reroll, 3). Prices follow the difficulty like the reward
does (x0.5 on PEACEFUL ... x2 on LEGENDARY), less 20% per Haggling level.
One ware per visit, or leave.

### Difficulties to earn

PEACEFUL and ADVENTURE are always open; SURVIVAL opens once the fourth world
is reached on ADVENTURE, LEGENDARY once a run is won on SURVIVAL (`unlocks`
in config.yml). A locked one shows "(locked)" at NEW GAME and says what it
needs.

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
