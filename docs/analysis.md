# Analysing what matters

> **Out of date.** These numbers were measured before the November 2026
> changes: bot at human key rates with two hands and sweeps, per-world bat
> tables and new bats (healer, bomber, plague, necromancer), world hazards,
> elite behaviours, card levels (6 per type, 4 types a run), the Gold and fear
> caps, the tougher first boss. The tools still work; rerun them
> (`tools/analyze.py`, `tools/campaign.py`) before trusting any figure below.
> What each world adds now: `docs/worlds.md`.

`tools/analyze.py` plays many games with the bot and measures **how much each
factor and each choice changes the outcome**, instead of trying fixed
strategies one by one.

## Factors: what matters most

```bash
python3 tools/analyze.py factors --runs 240
```

```bash
python3 tools/analyze.py factors --runs 240 --factor "cards.drop_chance.bat=[0.5, 1.0]" --factor "speed.max_speed=[8, 10]"
```

Every game draws **every factor at random and independently**: the bot's
strategy and play style (`BOT_FACTORS` in the tool: max gear, formation,
birds kept, powers on/off, how far a bird falls before an early bounce,
dodging, card and pact policy) plus any configuration value given with
`--factor`. Since the factors are independent, the average outcome for each
value of a factor is a fair comparison, all else being equal on average (a
randomised factorial experiment). The report ranks factors by:

- **Explains**: the share of the variation in the level reached that the
  factor accounts for (eta²);
- **Gap**: the difference between its best and worst value, in levels.

Each value also gets its number of games, the standard error (±), minutes
survived and log10 score; `--json` saves every game.

## Decisions: what is worth taking, and when

```bash
python3 tools/analyze.py decisions --runs 300 --by phase,lives,birds,scared,boss,gear
```

The bot takes egg cards and pacts **at random**, and every choice is recorded
with its situation (level, lives, birds alive, gear, prestige, scared birds,
boss, bats) and what happened in the **next two minutes**: score = levels
gained + 0.3 × birds kept − 3 if the game ended. A card's **worth** is its
mean score when it was taken minus when it was offered and left: since the
choice was random, the difference is what taking it is worth. The same is
computed inside each situation (`--by`), and the clear differences (larger
than twice their standard error) become **rules**: "when lives <= 3, take X".

The rules are a starting point: with ~40 cards and ~10 situations, a few
rules at 2 standard errors are expected by chance. Confirm one by running
more games, or by turning it into a bot policy and comparing it with
`tools/simulate.py`.

## First results (expert bot, 12 minutes per game)

### Factors (240 games)

## Ranking by level reached

| Factor | Explains | Best value | Worst value | Gap (levels) |
|---|--:|---|---|--:|
| bot.dodge | 23.7% | False (7.24) | True (5.44) | +1.81 |
| bot.max_gear | 4.6% | 7 (6.83) | 0 (5.76) | +1.07 |
| bot.keep_birds | 3.8% | 9 (6.88) | 5 (5.97) | +0.91 |
| bot.pact_policy | 2.2% | 'adaptive' (6.63) | 'smart' (5.96) | +0.67 |
| bot.formation | 1.4% | 'white_center' (6.68) | 'none' (6.07) | +0.62 |
| bot.bounce_from | 1.4% | 0.35 (6.62) | 0.6 (6.09) | +0.52 |
| bot.card_policy | 0.9% | 'random' (6.59) | 'adaptive' (6.16) | +0.43 |
| bot.use_powers | 0.1% | True (6.42) | False (6.30) | +0.12 |


Read:

- **Dodging is the single biggest factor, and it hurts**: the bot holding a
  bounce while an enemy sits above the bird loses 1.8 levels on average. It is
  now off by default in the bot (`dodge`), which also means the strategy
  comparison of `docs/strategies.md` was made with a handicapped bot.
- **Braking to gear 7** is the best play-style choice (+1.1 levels over never
  braking); 8 is too late, 6 too slow.
- **Keeping all 9 birds** beats keeping 7 or 5 (+0.9 levels).
- **Powers barely matter** (0.1%): firing them or not changes little. Power
  values (Red shots, Purple charge, Blue sprint...) are weak next to contact
  hits; see the measurements below.
- Card policy matters little (random is as good as the others: the cards
  are close in value), pact policy a bit more (refusing or adaptive beats the
  "fewest drawbacks" rule).

### Powers (simulator, 16 games of 10 minutes, after letting the bot use extra uses)

Per game: Yellow ~220 uses, White ~80, Red ~80 (30 of them second uses), Blue
~34, the rarer birds a few each. Red shots get a neighbour bonus in 23% of the
cases with the default flock and in 50% with the `red_battery` formation;
about 70% of the shots hit something. Birds reach grade S within minutes:
nearly all XP comes from movement (score), so the A-grade double use is
common.

### Decisions (300 games, 5735 egg choices, 449 pacts)

## Egg cards, overall

| Card | Worth | ± | Taken | Left | Times taken |
|---|--:|--:|--:|--:|--:|
| bird:ROCK | +1.07 | 0.63 | 0.11 | -0.96 | 16 |
| bird:BERSERK | +0.95 | 0.55 | 0.08 | -0.87 | 22 |
| bird:PURPLE | +0.62 | 0.71 | -0.25 | -0.87 | 15 |
| bird:RED | +0.45 | 0.31 | -0.10 | -0.56 | 63 |
| reckless | +0.42 | 0.29 | 0.06 | -0.36 | 71 |
| sharp_beaks * | +0.38 | 0.18 | 0.26 | -0.12 | 169 |
| wide_wings | +0.28 | 0.17 | 0.11 | -0.17 | 194 |
| bird:FROSTY | +0.25 | 0.52 | -0.30 | -0.55 | 24 |
| bird:CLOCKWORK | +0.24 | 0.60 | 0.32 | 0.07 | 18 |
| show_off | +0.22 | 0.19 | 0.12 | -0.10 | 162 |
| lumberjack | +0.17 | 0.17 | 0.20 | 0.03 | 194 |
| steady_nerves | +0.16 | 0.18 | 0.04 | -0.12 | 193 |
| potent_powers | +0.15 | 0.17 | -0.03 | -0.18 | 212 |
| golden_hour | +0.13 | 0.17 | 0.19 | 0.07 | 169 |
| bat_hunter | +0.10 | 0.18 | 0.06 | -0.04 | 165 |
| clover | +0.09 | 0.17 | 0.09 | 0.00 | 191 |
| gamblers_luck | +0.07 | 0.43 | 0.31 | 0.24 | 26 |
| glass_wings | +0.06 | 0.23 | 0.36 | 0.30 | 84 |
| wide_cursor | +0.04 | 0.17 | 0.00 | -0.04 | 201 |
| piercing_talons | +0.04 | 0.17 | 0.19 | 0.15 | 200 |
| lasting_powers | +0.03 | 0.19 | -0.21 | -0.24 | 176 |
| brave_hearts | +0.02 | 0.18 | -0.06 | -0.08 | 175 |
| bird:YELLOW | +0.00 | 0.36 | -0.37 | -0.38 | 50 |
| heavy_blows | -0.01 | 0.18 | -0.06 | -0.05 | 171 |
| heavy_crown | -0.04 | 0.26 | -0.00 | 0.03 | 87 |
| tailwind | -0.04 | 0.18 | -0.18 | -0.14 | 198 |
| giant_slayer | -0.04 | 0.27 | -0.03 | 0.02 | 94 |
| bird:COOKIE | -0.05 | 0.66 | 0.12 | 0.17 | 18 |
| hollow_bones | -0.05 | 0.18 | -0.18 | -0.13 | 199 |
| feather_brake | -0.06 | 0.17 | -0.01 | 0.06 | 189 |
| frenzy | -0.10 | 0.18 | -0.26 | -0.16 | 177 |
| fame | -0.10 | 0.18 | -0.01 | 0.09 | 174 |
| keen_eyes | -0.10 | 0.19 | -0.24 | -0.13 | 165 |
| escape_hatch | -0.13 | 0.26 | -0.03 | 0.10 | 93 |
| lucky_nest | -0.14 | 0.48 | -0.07 | 0.06 | 31 |
| jet_stream | -0.14 | 0.18 | -0.18 | -0.03 | 161 |
| second_chance | -0.15 | 0.47 | -0.34 | -0.18 | 33 |
| fearless | -0.16 | 0.17 | -0.08 | 0.08 | 183 |
| lucky_feather | -0.17 | 0.17 | -0.09 | 0.08 | 195 |
| quick_study | -0.22 | 0.18 | -0.27 | -0.05 | 186 |
| timelapse | -0.22 | 0.18 | -0.22 | 0.00 | 182 |
| bird:PATCHWORK | -0.23 | 0.53 | -0.68 | -0.45 | 30 |
| bird:BLUE | -0.26 | 0.34 | -1.00 | -0.74 | 49 |
| training | -0.29 | 0.19 | -0.33 | -0.04 | 175 |
| bird:POISON | -0.48 | 0.57 | -0.61 | -0.13 | 22 |
| safety_net | -0.54 | 0.45 | -0.64 | -0.09 | 39 |
| blood_price | -0.93 | 0.47 | -0.54 | 0.40 | 36 |


## Pacts, overall

| Card | Worth | ± | Taken | Left | Times taken |
|---|--:|--:|--:|--:|--:|
| blood_oath | +0.43 | 0.28 | 0.91 | 0.47 | 74 |
| hunters_moon | +0.31 | 0.45 | -0.79 | -1.10 | 40 |
| thick_skin | +0.27 | 0.25 | 1.38 | 1.11 | 46 |
| glass_cannon | +0.27 | 0.25 | 1.40 | 1.13 | 49 |
| refuse | +0.22 | 0.37 | 0.64 | 0.42 | 38 |
| featherweight | +0.15 | 0.30 | 0.59 | 0.44 | 77 |
| greedy_nest | -0.17 | 0.27 | 1.17 | 1.35 | 54 |
| war_drums | -0.24 | 0.49 | -1.12 | -0.87 | 30 |
| tempest | -0.66 | 0.54 | -1.56 | -0.90 | 18 |
| iron_will * | -1.27 | 0.43 | -1.83 | -0.56 | 23 |


## Rules found

- When **early (levels 1-6)**: avoid **blood_price** (-1.46 ±0.47)
- When **late (levels 7+)**: take **sharp_beaks** (+1.16 ±0.48), **bird:RED** (+1.09 ±0.54), **wide_cursor** (+0.95 ±0.39)
- When **late (levels 7+)**: avoid **feather_brake** (-0.98 ±0.41)
- When **lives <= 3**: avoid **second_chance** (-1.50 ±0.60)
- When **lives > 3**: take **second_chance** (+1.47 ±0.55), **reckless** (+0.75 ±0.32), **golden_hour** (+0.34 ±0.14)
- When **birds <= 6**: take **wide_cursor** (+0.61 ±0.30)
- When **birds > 6**: take **reckless** (+0.77 ±0.31), **wide_wings** (+0.51 ±0.16)
- When **none scared**: take **brave_hearts** (+0.55 ±0.24)
- When **none scared**: avoid **blood_price** (-1.40 ±0.62)
- When **some scared**: take **sharp_beaks** (+0.49 ±0.24)
- When **some scared**: avoid **safety_net** (-1.28 ±0.63)
- When **no boss**: take **sharp_beaks** (+0.37 ±0.18)

Only differences larger than twice their standard error (±) are listed as rules.
