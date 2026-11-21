# Birds

What every bird does, read from the code (not from the descriptions in
`bird_types.py`, which are sometimes out of date). Values are those of
`config.yml`; the numbers behind each bird are stats, listed in `docs/stats.md`.

## Rules every bird follows

- **Bounce:** UP on a falling bird sends it back up. A bird reaching the
  floor is lost (one life). Birds only collide with enemies while rising.
- **Power:** UP on a rising bird fires its power, once per ascent; birds at
  grade A1 and above can fire it twice.
- **Damage on contact:** `round(((gear − 3) + damage) × speed/10)`, then scaled
  by the bird's attack stats (crit, bonus against bats / obstacles / elites,
  armor pierce...). Speed and damage are on a ×10 scale, like enemy HP. Every
  bird's full sheet is in `docs/stats.md`.
- **Score:** every time a bird moves it scores `speed points × type multiplier ×
  grade multiplier (1.0 D … 2.0 S)`, then × the flock-height multiplier
  (0.5–2.0), × the level multiplier (1.0 at 1-1 … 2.7 at 6-3), × prestige.
- **Grades:** XP from hits and kills raises the grade D → C1 → C2 → B1 → B2 →
  A1 → A2 → S. From B1 up a scare lasts one second less; from A1 up (S too)
  a bird gets two powers per ascent; S gives +5 prestige and evolves three birds (below).
- **Prestige:** 1 + a bonus per living bird for its kind (column "Prestige")
  + a bonus for its grade (C1 +0.03 … A2 +1, S +5). It multiplies the score
  and pushes loot towards rarer drops.
- **Unique birds:** at most one White, one Orange and one Gold at a time.

## The birds

| Bird | Speed | DMG | Power (UP while rising) | Always | Prestige | Card rarity |
|---|:-:|:-:|---|---|:-:|:-:|
| **Yellow** | 21 | 9 | Neighbours (±1 lane) that are falling: Yellow and Patchwork are bounced, any other bird is slowed for 3 s | — | 0 | common |
| **Red** | 30 | 11 | Fires a projectile up its lane: damage 10, +10 for every neighbour that is a rising Red, Purple or Patchwork | — | 0 | common |
| **Blue** | 42 | 10 | Sprint for 3 s: +10 speed while rising and +10 speed in its damage | — | 0 | common |
| **Patchwork** | 30 | 10 | none of its own | Counts as Yellow for the Yellow chain and as Red for the Red bonus; drawn in random colours | 0 | common |
| **Purple** | 28 | 10 | Charged shot: the bird stops and charges while UP keeps being pressed, then fires on release; 10 / 40 / 160 / 640 damage after 0 / 1 / 2 / 3 s (fires by itself at 3 s) | Can be bounced while scared | +1 | uncommon |
| **Clockwork** | 20 | 11 | +1 charge (max 3); its speed equals its charge | Bounces by itself at the starting line while charged; starts with 2, loses 1 every 30 s; at 0 it drops at top speed (a bounce gives 1 back) | +2 | rare |
| **White** ("Templar") | 40 | 20 | Within ±2 lanes: bounces falling birds (not scared or stunned ones) and fires the powers of rising Yellow, Red and Blue birds | ×1.5 score; unique | +3 | epic |
| **Orange** ("Phoenix") | 50 | 999 | none | Kills any enemy in one hit; at the ceiling it turns into a dormant egg in its lane (and drops an orange egg); UP on its lane has a 10% chance to wake it; an obstacle crushes the dormant egg (bird lost); never dies at the floor; ×0.5 score; unique | +3 | epic |
| **Gold** | 58 | 2 | none | Scores a flat 100 per move instead of the usual formula; damage 2, so it barely hurts enemies; unique | +3 | epic |
| **Cookie** | 29 | 9 | Drops a crumb worth 75% of its XP for another bird to pick up; dies after its 5th crumb | Earns 1.5× XP; cannot pick crumbs up itself | +2 | rare |
| **Stealth** | 31 | 75 | Turns solid for 3 s: speed 60, +40 damage, bats cannot scare it | Otherwise passes through enemies, obstacles and loot (and cannot collect loot); ×1.2 score | +2 | rare |
| **Dinosaur** | 38 | 50 | none | Needs 15 presses to bounce (every 3rd press slows its fall); 3 rows tall, so a bigger target; ×2 score | +4 | legendary |
| **Glitch** | 30 | 10 | none | Random speed 10–60 every tick and damage ×1–8; random prestige 1–7; each tick small chances to flip direction (0.3%), swap lanes with another bird (0.3%), nudge your cursor (0.2%) or copy itself into a random lane (0.2%, replacing that bird or reviving an empty slot); ignores 2% of bounces; survives the floor 10% of the time; ignores 5% of loot and upgrades 10% of what it collects | random | legendary |
| **Rainbow** | 60 | 30 | none | Wraps from the floor to the ceiling instead of dying while it has charge; charge 100, −5 per second; every UP on its lane has a 25% chance of +25; dies at 0 | +5 | mythical |
| **Twister** | 40 | 45 | Tailwind for 2 s on its lane and both neighbours: +20 speed rising, −10 falling | — | +2 | rare |
| **Frosty** | 29 | 28 | For 2 s its freeze chance becomes 60% | Hitting a bat or a boss: 30% chance (a third of that on bosses) to freeze it for 3 s: it moves at 40% speed and has 20 less armor | +1 | uncommon |
| **Poison** | 31 | 27 | For 2 s its poison chance becomes 60% | Hitting a bat or a boss: 30% chance (a third on bosses) to poison it, 20 HP/s for 5 s | +1 | uncommon |
| **Berserk** | 32 | 40 | For 2 s its bleed chance becomes 60% | Hitting a bat or a boss: 30% chance (a third on bosses) to make it bleed, 10 HP/s for 10 s and 10 less armor | +1 | uncommon |
| **Rock** | 19 | 31 | For 3 s: pushes 2 rows and speed 30 | Hitting a bat pushes it up 1 row | +1 | uncommon |

"Card rarity": new birds hatch from bird cards, offered by eggs of that
rarity while a lane is free (see `docs/cards.md`).

## Afflictions on enemies

Frosty, Poison and Berserk afflict what they hit by contact (not mini bats,
obstacles or projectiles); `src/engine/logic/afflictions.py`.

- **Frozen:** moves at 40% speed, 20 less armor, for 3 s.
- **Poisoned:** 20 HP per second for 5 s (100 in all).
- **Bleeding:** 10 HP per second for 10 s (100 in all) and 10 less armor.

Damage over time is scaled by the enemy's `damage_taken` (Hulking elites take
less) but ignores defence and armor; its XP and the kill go to the bird that
applied it. Hitting an afflicted enemy again restarts the affliction; different
afflictions stack. Marks above the enemy: `*` frozen, `%` poisoned, `~` bleeding.

## Synergies

A synergy is "X next to Y does Z": neighbours are the birds in the lanes right
next to a bird. **Patchwork counts as the partner of every synergy** (passive).
Values are in `config.yml` `synergies` (code: `src/engine/synergies.py`).

- **Yellow next to Yellow:** a Yellow's power bounces the falling Yellow (and
  Patchwork) next to it. Pairs of Yellows at the edges keep the cursor in the
  middle.
- **Red / Purple next to Red:** a Red's shot gains damage for each neighbour
  (left and right) that is a rising Red, Purple or Patchwork; fire while they
  climb.
- **Yellow next to Blue:** a scared Blue falling past a rising Yellow (at most
  1 row apart) is no longer scared, so it can be bounced again.
- **Red next to Phoenix:** each Red adds +5% to the chance that UP wakes the
  dormant Phoenix egg (base 10%).
- **Yellow next to Clockwork:** the Yellow power slows the falling Clockwork
  like any other bird and adds 1 to its charge (never above the maximum).
- **Twister next to Blue:** each Twister adds +4 to the Blue's sprint after a
  bounce (faster, and more damage: speed damage counts active boosts).
- **Frosty / Poison next to Red or Purple:** the shots freeze or poison what
  they hit (contact hits are not affected).
- **Cookie next to Cookie:** each Cookie neighbour adds +25% to the XP a
  Cookie earns, so its crumbs (75% of its XP) carry more.
- **White relay** (its power, not a synergy): a White fires the powers of the
  rising Yellow, Red and Blue birds within two lanes, and bounces the falling
  ones, in one press. Relayed powers cost those birds their own use.
- **Cookie feeding:** Cookie crumbs pass XP to whichever bird flies through
  them: a way to rank up a weak bird.
- **Twister lanes:** its tailwind lifts its neighbours too.
- **Evolutions at grade S:** Yellow → Gold, Red → Orange, Blue → White. Since
  those are unique, a second S bird waits until the first one is lost.
- **Synergy achievements:** two or three different powers fired within a few
  seconds unlock "Get Along" and "Frenship Is Magic" (achievements only).

## Inconsistencies spotted while writing this

- The Yellow power has a Glitch check that can never be true (it only looks
  at Yellow and Patchwork neighbours).
- The in-game Bird-Dex lists 13 birds (no Rainbow, Twister, Frosty, Poison,
  Berserk or Rock) with its own descriptions, separate from `bird_types.py`.
