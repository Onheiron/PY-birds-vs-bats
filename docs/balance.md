# Balance: what the analysis found, and what was changed

Everything here comes from simulated games (`tools/simulate.py`,
`tools/analyze.py`, `tools/campaign.py`); the bot profiles stand for players:
**expert** ~15 keys/s and 150 ms reactions (a very good human), **average**
~10 keys/s and 250 ms, **novice** ~6 keys/s and 400 ms. Numbers with fewer
than ~30 games carry ±10 points of noise.

## 1. Where the game stood

Before this pass, without upgrades (40 games per bot, up to 40 minutes):

| Bot | Median level | Past world 2 | Where birds die |
|---|:-:|:-:|---|
| expert | 7 | 85% | a spike at level 6, the world-2 boss |
| average | 6 | 22% | spikes at levels 3 and 6, the first two bosses |
| novice | 3 | 0% | levels 1–3 |

- **Damage is almost all contact.** Projectiles and damage over time were a
  rounding error: a Red shot did 10–30 against bats of 240–1,920 HP.
- **Bosses after the second are trivial**: the world-3 boss died in 5 s on
  median, the final boss (the world-1 boss again) instantly. Boss HP did not
  grow with the run while the flock did.
- **Grades come too fast**: moving earned as much XP as score, so every bird
  reached grade S within minutes; the A-grade double power was the norm and
  Yellow / Red / Blue evolved into Gold / Orange / White early (Gold has 2
  damage: an evolution can weaken the flock).

## 2. What matters (320 games, every factor random; average bot, 20 min)

| Factor | Explains | Best → worst |
|---|--:|---|
| **player skill** (keys per second) | **45%** | 15 keys/s → 7.5: **−4 levels** |
| brake to gear 7 | 2.4% | +1.0 level over never braking |
| **boss HP** ×0.7 → ×1.5 | 2.3% | −0.9 levels |
| keep all 9 birds (vs 5) | 1.8% | +0.8 |
| formation yellow_guard (vs none) | 1.5% | +0.85 |
| Red battery bonus 1 → 3 | 1.4% | −0.6 (more damage did not help) |
| refuse pacts | 0.7% | +0.5 over the "fewest drawbacks" rule |
| eggs from every bat (vs half) | 0.6% | +0.4 |
| elites on / off | 0.4% | −0.3 |
| Purple tiers ×3 | 0.4% | +0.3 |
| move XP ×0.2 | 0.3% | +0.3 levels, but score ÷6 |
| Red shot ×4 | 0.1% | +0.2 |
| powers on / off | 0.0% | nothing |
| bat HP +8% per level | 0.0% | nothing |

Read: the game is decided by hands (press rate and reaction) and by the
**bosses**, which are where birds die. Powers, card choices and bat HP move
the result very little; that is why boss HP is the main lever below, and why
the meta progression gives mostly survival and damage upgrades.

Earlier analyses (`docs/analysis.md`, `docs/strategies.md`): the bot's old
"dodging" cost 1.8 levels (now off); braking a little is the best strategy;
letting birds go costs lives and does not pay; card worth per situation and
the rules found.

## 3. The changes (balance pass A)

| What | Before | Now | Why |
|---|---|---|---|
| Boss HP per world (`combat.boss_hp_per_world`) | none | +50% per world after the first (×3.5 in the last) | later bosses were trivial |
| World-2 boss (`wind_boss.hp`) | 3,000 | 6,000 | the second world is the first wall |
| XP from moving (`progression.move_xp_factor`) | ×1 | ×0.3 | grades and evolutions came within minutes |
| Bat HP per level (`bat_enemy.level_hp_multiplier`) | 0 | +5% per level | a slight late-game ramp |
| Red shot (`power_damage`) | 10, +10 per shooter | 30, +20 per shooter | shots did nothing |
| Purple charge | 10 / 40 / 160 / 640 | 30 / 100 / 300 / 900 | idem; short charges count |
| XP fractions | lost to rounding | kept | +6% XP bonuses gave nothing |

And the **meta progression** (`docs/progression.md`): achievements pay gold,
gold buys permanent upgrades.

## 4. Result

Without upgrades (32 games per bot, up to 30 minutes):

| Bot | Past world 1 | Past world 2 | Past world 3 |
|---|:-:|:-:|:-:|
| expert | 100% | 53% (was 85%) | 22% |
| average | 88% | 6% (was 22%) | 0% |

World-2 boss HP turned out to matter little (4,500 → 7,500 HP: expert 59% →
50%): the wall is its wind and the bats of the second world, not its HP.

**Campaigns** (12 average players, 10 runs each, upgrades bought with the
gold between runs, `--buy balanced`):

| Run | Median level | Past world 2 | Past world 3 | Gold earned | Upgrade levels owned |
|---|:-:|:-:|:-:|:-:|:-:|
| 1 | 6 | 8% | 0% | 38 | 4 |
| 2 | 6 | 25% | 8% | 47 | 6 |
| 3 | 6 | 17% | 0% | 56 | 8 |
| 4 | 7 | 50% | 17% | 67 | 13 |
| 5 | 7.5 | 67% | 8% | 101 | 15 |
| 7 | 7 | 58% | 17% | 83 | 21 |
| 10 | 8.5 | 67% | 8% | 98 | 28 |

Every average player passed world 2 by their 4th run on median, 7 of 12
reached world 4 within 10 runs, none world 5: the second world is a wall at
first, the upgrades open it, and the later worlds stay a long-term goal (the
full tree costs 3,515 gold, ~40 runs of an average player). An expert player
earns about twice the gold per run and reached world 6 by run 7 on median
(campaign measured with the world-2 boss at 4,500).

## 5. Further proposals (not applied)

- **Powers as a real choice.** Even ×3 shots leave powers at ~1% of the
  outcome: contact hits do the work. Either make shots pierce (hit every
  enemy in the lane) or let powers score for the momentum, so firing them has
  a cost and a gain.
- **Evolutions.** Evolving into Gold (damage 2) weakens a fighter: give Gold
  a real attack, or make evolution a choice (a card) instead of automatic.
- **Bosses by mechanics, not HP.** The world-2 boss is the wall because of
  its wind; giving every boss a phase that needs a specific answer (swap,
  power, formation) would make strategy matter more than reflexes.
- **Skill dominates (45%).** The cursor assists (Bounce / Trigger on enter)
  and a slower first world would make the game kinder to slower hands; an
  "assist" upgrade branch could unlock them for gold.
