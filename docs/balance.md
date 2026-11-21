# Balance: what the analysis found, and what was changed

Everything here comes from simulated games: `tools/simulate.py`,
`tools/analyze.py` (`factors`, `decisions`, `levels`, `powers`, `cards`) and
`tools/campaign.py`. The bot profiles stand for players: **expert** ~15
keys/s and 150 ms reactions (a very good human), **average** ~10 keys/s and
250 ms, **novice** ~6 keys/s and 400 ms. With 30–40 games a rate carries about
±10 points of noise.

## 1. What makes a level hard

`python3 tools/analyze.py levels` measures, level by level, birds lost per
minute, split between the level and its boss fight, and what the lost birds
had in common (scared by a bat, stunned by an obstacle, bats on screen, gear).

What it showed before this pass (average bot):

| Level | Lost / min outside boss | during boss | Gear |
|---|--:|--:|--:|
| 1 | 0.00 | – | – |
| 2 | 0.19 | – | 6.9 |
| 3 | 1.26 | 2.3 | 7.1 |
| 4 | 1.59 | – | 7.9 |
| 5 | 1.08 | – | 8.0 |
| 6 | 0.43 | **7.9** | 8.1 |

- **Speed is the main source of difficulty.** Birds lost per minute jump with
  every gear; bats and obstacles add much less (only 2–15% of the birds lost
  were scared at the time, almost none stunned). The gear reached 7–8 by
  level 2, so difficulty peaked before the first bat and then stopped growing.
- **The world-2 boss carried the whole world**: ~8–10 birds lost a minute
  during the fight, 0.2–0.4 in the rest of level 6. Its HP mattered little
  (4,500 → 7,500 HP: expert 59% → 50%); its **wind** did (up to +5 fall
  speed at gear 8). Softening the wind alone sent the average bot from 16%
  to 50% past world 2.
- **More bats move little**: doubling the world-2 bats changed the pass rate
  by a few points; speed changed it by tens.

So difficulty now ramps up **by speed, world by world** (`speed.max_gear_by_world`),
with bats, obstacles and boss HP growing alongside, and the bosses as filters.

## 2. Are the powers used well?

`python3 tools/analyze.py powers` (a flock with every synergy, expert bot)
counts what each power actually does:

| Power | Uses / game | What they did |
|---|--:|---|
| Yellow | ~196 | 88% of uses bounce no one (only Yellow / Patchwork neighbours are bounced); they mostly **slow** falling neighbours (180 a game). It cures a scared Blue 0.6 times a game: the Yellow-Blue synergy practically never happens. |
| White | ~260 | bounces 446 falling neighbours a game; relays a power in half of its uses |
| Red | ~70 shots | 41% with a battery bonus (+1), 4% with +2; ~63% of shots hit |
| Purple | ~40 | charge tiers 0/1/2/3: 9 / 6.5 / 4.5 / 8 a game |
| Blue | ~92 | the sprint hits something in 11% of the uses |

Fixes: the White relay still used the old "two uses at A grades" rule (now
the `power_uses` stat); the bot used only one power per ascent, now uses the
extra ones; it now waits for the Red battery (bonus shots +48%) and keeps a
Purple charging up to 2 s when it can.

**Powers on or off give the same median level** (30 games each, expert, same
flock): powers are used sensibly, but their effects are too small to matter.
That is a design problem, not a bot one (see the proposals below).

## 3. Which power-ups matter

`python3 tools/analyze.py cards`: 400 games with **cards taken at random**,
cards taken in the first 6 minutes against levels gained in the next 6,
holding constant the level, birds alive and eggs opened at 6 minutes (ridge
regression). One "copy" is a common card; rarer copies count their rarity
scale (an epic copy = 3.5).

First measure: **power-ups barely mattered**. The best common card was worth
+0.07 levels; movement cards changed the fall speed by 0.15 speed points
against a gear-8 game. They were made stronger (movement ×2.5–3, fear,
damage, pierce, training). Measured again:

{cards}

By stat (every card that raises it, added up):

{stats}

Read (* = clear beyond noise):

- **Falling slower is what helps** (each −1 fall speed +0.03 levels;
  Feather Brake, −4, is the best common card, +0.08 per copy, and Updraft
  is now a 20-second version of it).
- **Rising faster hurts** (−0.014 per +1): birds reach the ceiling and fall
  again sooner, so there is more to juggle. Hollow Bones, Jet Stream and
  Glass Wings came out negative; Hollow Bones and the Light Bones upgrade
  now add damage too, and Jet Stream became Updraft.
- **Luck and egg luck** pay off over the run (rarer eggs, better cards);
  so does a second power use (Second Wind, +0.42 per use, rare).
- **Damage, crits, pierce are worth ~0**: contact hits already kill most
  bats; extra damage only shortens fights that were not the danger.
- **Most bird cards are negative** (Red −0.25, Yellow −0.16, Twister −0.66):
  one more bird is one more bird to keep in the air. Clockwork (bounces by
  itself) and Stealth (passes through) are the exceptions.
- Score and score-flavoured cards (Show-off, Golden Hour) cost levels: they
  take a slot from a useful card.

## 4. The changes

| What | Before | Now |
|---|---|---|
| Top gear per world (`speed.max_gear_by_world`) | 10 everywhere (7–8 by level 2) | 5, 9, 9, 9, 10, 10 |
| Momentum gain | 100 | 115 |
| Bats in world 2 | up to 1, every 200 ticks, tiers 70/25/5 | up to 4, every 90, tiers 40/35/25 |
| Bats in later worlds | 2 / 3 / 4 / 5 at most | 3 / 4 / 5 / 6, spawning faster |
| Obstacles | biome_base 40 | 34 (a little denser) |
| Boss HP | fixed | +50% per world after the first; world-2 boss 6,000 |
| XP from moving | ×1 | ×0.3 (grades reached S within minutes) |
| Bat HP per level | – | +5% per level |
| Red / Purple shots | 10 +10 per shooter / 10–640 | 30 +20 / 30–900 |
| Movement and fear cards | tiny | ×2.5–3 (see section 3) |

## 5. Result

Single games, flock and upgrades from scratch (32 games each):

| Bot | past world 2 | past world 3 | past world 4 | past world 6 |
|---|--:|--:|--:|--:|
| average | 19% | 0% | 0% | 0% |
| expert | 62% | 47% | 22% | 9% |

Before this pass (wind softened, gear 10 everywhere) the average bot got
past world 2 in 41–50% of first runs; now first runs stop at the world-2
wall, as wanted, and an expert can still reach the end.

CAMPAIGN

## 6. Further proposals (not applied)

- **Powers as a real choice.** They are used well but do not change the
  outcome: make them strong where the danger is (falling): e.g. a Yellow that
  bounces *every* falling neighbour, a Blue sprint that also shields from
  fear, a White that saves a bird from the floor.
- **The Yellow–Blue synergy** (cure a scared Blue) happens 0.6 times a game:
  widen it (any scared neighbour) or drop it.
- **Bird cards** cost more than they give: a hatch could come with a short
  shield, or add a life.
- **Damage cards** are near-worthless; trade some for fall-time and fear.
- **Evolutions**: Gold has 2 damage; evolving into it can weaken the flock.
- **Skill is 45% of the outcome**: the cursor assists (Bounce / Trigger on
  enter) could be bought with gold for slower hands.
