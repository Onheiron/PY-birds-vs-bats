# Stats

Birds and enemies are described by stats. Bird stats first, enemy stats and
elites below.

## Bird stats

Every number that describes how a bird flies, fights and scores is a **stat**,
computed by `src/engine/stats.py`. A bird's value is built in layers:

```
value = (default + kind value + grade growth + flat modifiers)
        × product of multiplier modifiers, clamped to the stat's range
```

- **Default:** the table below (can be overridden in `bird_stats.defaults`).
- **Kind:** `bird_stats.types.<TYPE>` sets the value for one kind of bird
  (Dinosaur is 3 rows tall, White scores ×1.5...).
- **Grade:** `bird_stats.growth.<GRADE>` adds a bonus from that grade on.
  For each stat the highest grade reached that names it wins, so a bonus set
  at A1 holds at A2 and S unless they set another one.
  `bird_stats.type_growth.<TYPE>_<GRADE>` adds a bonus for one kind only
  (e.g. `RED_B1: {damage_bonus: 1}`).
- **Modifiers:** added during a run by cards, boosts and pacts
  (`stats.add_modifier(target, stat, add=, mul=, seconds=)`), for one bird or for
  the whole flock (`'flock'`), permanent or for some game seconds. They are
  saved with the game; a bird's own modifiers go away when its slot gets a new bird.

**Scale.** Speeds are ×10 of the movement code's points: a bird with speed
`S` moves one cell every `max(1, 6 − S/10)` ticks (speed 20 → every 4 ticks,
50+ → every tick), so a bird at 21 is a little faster than one at 20. Damage,
enemy HP, armor and defences are on a ×10 scale too (`combat.hp_scale: 10`):
XP from damage and score from kills divide by it, so they did not change.

### Base

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `speed` | 20 | 0 … 100 | base speed (10 = 1 cell every 5 ticks, 50+ = 1 cell per tick) |
| `damage` | 10 | 0 … 99999 | base contact damage |

### Movement

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `rise_speed_bonus` | 0 | -40 … 40 | speed added while rising |
| `fall_speed_bonus` | 0 | -40 … 40 | speed added while falling (negative: falls slower) |
| `bounce_sprint` | 0 | 0 … 40 | speed added for a moment after each bounce |
| `bounce_sprint_seconds` | 1 | 0 … 10 | how long the bounce sprint lasts |
| `weight` | 1 | 0 … 10 | share of the flock centre of mass (drives momentum) |
| `presses_to_bounce` | 1 | 1 … 99 | UP presses needed to bounce it |
| `hitbox_height` | 2 | 1 … 5 | rows the bird occupies when colliding |
| `hitbox_width` | 5 | 1 … 15 | columns the bird occupies when colliding (centred on its lane) |

### Attack

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `damage_bonus` | 0 | 0 … 999 | flat damage added to the base damage |
| `damage_mult` | 1 | 0 … 100 | multiplier on all damage dealt |
| `speed_damage` | 1 | 0 … 5 | how strongly current speed multiplies damage (1 = damage × speed) |
| `vs_bats` | 0 | -1 … 10 | extra damage against bats (0.5 = +50%) |
| `vs_obstacles` | 0 | -1 … 10 | extra damage against obstacles |
| `vs_elites` | 0 | -1 … 10 | extra damage against elites and bosses |
| `armor_pierce` | 0 | 0 … 99 | armor points ignored |
| `crit_chance` | 0 | 0 … 1 | chance of a critical hit |
| `crit_damage` | 2 | 1 … 20 | damage multiplier of a critical hit |
| `affliction_chance` | 0 | 0 … 1 | chance to apply the bird's affliction (freeze, poison, bleed) on hit |
| `knockback` | 0 | 0 … 10 | rows a hit pushes a bat back up |
| `impact_stun` | 1 | 0 … 5 | multiplier on the stun suffered when hitting something that survives |

### Fear

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `fear_resist` | 0 | 0 … 1 | share of the fear fall-speed bonus ignored |
| `fear_duration_mult` | 1 | 0 … 5 | multiplier on fear duration |
| `fear_duration_cut` | 0 | 0 … 10 | seconds removed from fear (never below 1 s) |
| `fear_immunity` | 0 | 0 … 1 | chance to ignore a scare entirely |

### Power

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `power_uses` | 1 | 0 … 10 | power activations per ascent |
| `power_potency` | 1 | 0 … 10 | multiplier on power strength |
| `power_duration` | 1 | 0 … 10 | multiplier on power duration |

### Survival

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `floor_save` | 0 | 0 … 1 | chance to bounce back instead of being lost at the floor |

### Economy

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `prestige` | 0 | 0 … 99 | prestige the bird adds to the flock |
| `score_mult` | 1 | 0 … 100 | score multiplier for this kind of bird |
| `score_grade_bonus` | 0 | 0 … 10 | score bonus from grade (+0.1 = ×1.1) |
| `xp_gain` | 1 | 0 … 10 | multiplier on XP earned |
| `pickup_radius` | 2 | 0 … 10 | columns within which it collects loot |
| `luck` | 0 | 0 … 1 | chance to upgrade the rarity of what it collects |

### Formulas that use them

- **Damage:** `round(((gear − 3) + damage + boosts + damage_bonus) × (1 + speed_damage × (speed/10 − 1))
  × damage_mult × (1 + vs_<target>) × crit)`, at least 1. The target is a bat,
  an obstacle or an elite (bosses). Armor is reduced by `armor_pierce` first.
- **Fear:** a scare lasts `seconds × fear_duration_mult − fear_duration_cut`
  (at least 1 s when a cut applies); `fear_immunity` is the chance to ignore it;
  while scared the bird falls `10 × (1 − fear_resist)` speed faster.
- **Score per move:** `speed × score_mult × (1 + score_grade_bonus)`.
- **Prestige:** `1 + Σ prestige` over the living birds.

### Grades

Grades add the same bonuses to every bird: prestige (C1 +0.03 … A2 +1, S +5)
and a score bonus (C1 +10% … S +100%); from B1 scares last one second less;
from A1 a bird fires its power twice per ascent (S included). Per-kind growth
can be added in `bird_stats.type_growth`.

## Enemy stats

Bats and obstacles have stats too (`src/engine/enemy_stats.py`), resolved once
when they spawn and stored in the enemy's `stats` field. Layers, from the
`enemy_stats` config section:

`defaults` → `tiers.<n>` → `kinds.<kind>` → `worlds.<w>` (its own stats, then
its `tiers.<n>` and `kinds.<kind>`) → elite stats → `elite_kinds.<kind>` (and its
`worlds.<w>`) → affixes (plain elites only).

Flat stats add up (+), multipliers multiply (×). Every number of every kind
(abilities included) is a stat, so each can change world by world
(`worlds.<w>`) and for the elites of a kind (`elite_kinds.<kind>`). Armored bats
also get `bat_enemy.armored.armor_by_tier` as armor.

Bat kinds: armored, diver, spellcaster, healer, bomber, plague, necromancer
(`src/engine/bat_ai.py`, `src/engine/logic/bat_abilities.py`). Which kinds
appear, how often, how many bats and of which tiers is set per world in
`bat_enemy.worlds`. Obstacle kinds (emerging, stalactite, peak, stone) come
from the world hazards (`hazards` section, `src/engine/hazards.py`) and from bombers.

| Stat | Default | Combines | Meaning |
|---|:-:|:-:|---|
| `hp_mult` | 1 | × | multiplier on spawn HP |
| `defense` | 0 | + | damage removed from every hit |
| `contact_defense` | 0 | + | damage removed from bird contact hits |
| `projectile_defense` | 0 | + | damage removed from projectile hits |
| `armor` | 0 | + | damage removed from contact hits; lowered by freeze, bleed and armor pierce |
| `damage_taken` | 1 | × | multiplier on damage received |
| `regen` | 0 | + | HP regenerated per second (up to max HP) |
| `fear_strength` | 1 | × | multiplier on how long its scare lasts |
| `fear_radius` | 0 | + | lanes on each side also scared on contact |
| `speed` | 1 | × | horizontal speed multiplier |
| `descent_interval` | 5 | + | ticks per row while descending to its height |
| `move_step` | 2 | + | columns per horizontal move |
| `linger` | 60 | + | seconds on screen before it flies away |
| `fear_push` | 1 | + | extra fall speed (speed points) of a bird it scares |
| `ability_chance` | 0 | + | chance per second to use its ability when ready |
| `ability_interval` | 0 | + | seconds before its ability is ready again |
| `dive_rows` | 10 | + | diver: rows of a dive |
| `dive_interval` | 2 | + | diver: ticks per row while diving |
| `dive_stun` | 1.5 | + | diver: seconds it stays stunned after a dive |
| `return_interval` | 6 | + | diver: ticks per row while climbing back |
| `dive_push` | 1 | + | diver: extra fall speed of a bird that hits it mid-dive |
| `dive_push_time` | 0.5 | + | diver: seconds that push lasts |
| `spells` | 1 | + | spellcaster: spells known (silence, repugnant wind, exile) |
| `cast_time` | 0.5 | + | spellcaster: seconds of casting before the spell lands |
| `silence_time` | 3 | + | spellcaster: seconds of silence |
| `wind_time` | 3 | + | spellcaster: seconds of repugnant wind |
| `wind_push` | 1 | + | spellcaster: fall speed added and rise speed removed by its wind |
| `heal_pct` | 0 | + | healer: share of max HP healed on the bats around it |
| `heal_range` | 0 | + | healer: columns its healing reaches |
| `stone_hp` | 0 | + | bomber: HP of a dropped stone |
| `stone_interval` | 0 | + | bomber: ticks per row of a falling stone |
| `stone_stun` | 0 | + | bomber: seconds a stone stuns the bird it hits |
| `plague_time` | 0 | + | plague: seconds before the infection kills the bird |
| `plague_presses` | 0 | + | plague: UP presses that cure it |
| `plague_spread` | 0 | + | plague: chance per second to infect the bird in a lane next to it |
| `zombies` | 0 | + | necromancer: zombie birds it keeps at most |
| `zombie_fear` | 0 | + | necromancer: seconds its zombies scare a bird |
| `zombie_bite` | 0 | + | necromancer: chance that a zombie passing a falling bird turns it into a zombie |
| `double_cast` | 0 | + | spellcaster: chance to cast two spells at once (charging twice as long) |
| `dive_wind` | 0 | + | diver: headwind strength on its lane and the two beside it while it dives |
| `overheal` | 0 | + | healer: share above max HP it can heal bats to |
| `stone_blast` | 0 | + | bomber: 1 = its stones explode when broken |
| `blast_push` | 0 | + | bomber: extra fall speed of a bird caught in a stone blast |
| `blast_push_time` | 0 | + | bomber: seconds that push lasts |
| `blast_fear` | 0 | + | bomber: seconds a stone blast scares a bird |
| `plague_bleed` | 0 | + | plague: seconds the infection bleeds (UP presses hurt) before it turns to poison |
| `stun` | 1 | + | seconds it stuns a bird that hits it |
| `knock` | 0 | + | extra fall speed of a bird that hits it |
| `knock_time` | 0 | + | seconds that extra fall speed lasts |
| `fall_interval` | 5 | + | ticks per row while falling |
| `xp_mult` | 1 | × | multiplier on kill XP |
| `score_mult` | 1 | × | multiplier on kill score |
| `loot_rarity_bonus` | 0 | + | rarity steps added to its drop |

**Damage taken:** `max(1, round(damage × damage_taken) − defense − <contact|projectile>_defense
− max(0, armor − debuffs − armor_pierce))`; armor only counts against contact hits.

### Elite bats

A spawning bat becomes an elite with chance `elites.chance_by_biome[biome − 1]`
(0 in world 1, then 3%, 6%, 9%, 12%, 15%). An elite:

- gets `elites.stats`: ×2 HP, ×2 XP, ×2 score and its drop one rarity higher;
- if it is a plain bat, gets `affix_count_by_biome` random affixes (1 up to world 3,
  then 2); an elite of a special kind gets `enemy_stats.bats.elite_kinds.<kind>`
  instead (see docs/worlds.md);
- looks like the others with yellow ears, and its arrival is announced on the right panel;
- counts as an elite for the birds' `vs_elites` bonus (bosses do too).

| Affix | Effect |
|---|---|
| Ironclad | +20 armor |
| Regenerating | heals 20 HP per second |
| Terrifying | scares 1.5× longer, and the lanes next to the hit bird too |
| Swift | moves 1.5× faster |
| Warded | −30 damage from projectiles |
| Hulking | ×1.5 HP, takes 20% less damage |
| Bountiful | ×1.5 XP, drop one more rarity higher |

## The sheets

Generated with `python3 tools/stat_sheets.py`.

### Birds (grade D)

#### Base and movement

| Bird | Speed | Rise + | Fall + | Bounce sprint | Sprint s | Weight | Presses | Width | Height |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Yellow | 21 | 0 | -2 | 0 | 1 | 1 | 1 | 5 | 2 |
| Red | 30 | 0 | 0 | 0 | 1 | 1.1 | 1 | 5 | 2 |
| Blue | 42 | 0 | 5 | 8 | 0.6 | 0.8 | 1 | 5 | 2 |
| Patchwork | 30 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |
| Purple | 28 | 0 | 0 | 0 | 1 | 1.1 | 1 | 5 | 2 |
| Clockwork | 20 | 0 | 0 | 0 | 1 | 1.3 | 1 | 5 | 2 |
| White | 40 | 0 | 0 | 0 | 1 | 1.2 | 1 | 5 | 2 |
| Orange | 50 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |
| Gold | 58 | 0 | 0 | 0 | 1 | 0.7 | 1 | 5 | 2 |
| Cookie | 29 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |
| Stealth | 31 | 0 | 0 | 0 | 1 | 0.9 | 1 | 5 | 2 |
| Dinosaur | 38 | 0 | 6 | 0 | 1 | 2.5 | 15 | 9 | 3 |
| Glitch | 30 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |
| Rainbow | 60 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |
| Twister | 40 | 5 | -5 | 0 | 1 | 0.9 | 1 | 5 | 2 |
| Frosty | 29 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |
| Poison | 31 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |
| Berserk | 32 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |
| Rock | 19 | 0 | 3 | 0 | 1 | 2 | 1 | 5 | 2 |
| Zombie | 20 | 0 | 0 | 0 | 1 | 1 | 1 | 5 | 2 |

#### Attack

| Bird | Damage | Dmg + | Dmg × | Speed weight | vs bats | vs obstacles | vs elites | Pierce | Crit % | Crit × | Affliction % | Knockback | Impact stun × |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Yellow | 9 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0% | 2 | 0% | 0 | 1 |
| Red | 11 | 0 | 1 | 1 | 0 | +25% | 0 | 3 | 12% | 2.2 | 0% | 0 | 1 |
| Blue | 10 | 0 | 1 | 2 | +10% | 0 | 0 | 0 | 5% | 2 | 0% | 0 | 1 |
| Patchwork | 10 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0% | 2 | 0% | 0 | 1 |
| Purple | 10 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 5% | 2 | 0% | 0 | 1 |
| Clockwork | 11 | 0 | 1 | 1 | 0 | 0 | 0 | 3 | 0% | 2 | 0% | 0 | 0.7 |
| White | 20 | 0 | 1 | 1 | 0 | 0 | +20% | 0 | 0% | 2 | 0% | 0 | 1 |
| Orange | 999 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0% | 2 | 0% | 0 | 0 |
| Gold | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0% | 2 | 0% | 0 | 1 |
| Cookie | 9 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0% | 2 | 0% | 0 | 1 |
| Stealth | 75 | 0 | 1 | 1 | 0 | 0 | +30% | 5 | 20% | 2.5 | 0% | 0 | 1 |
| Dinosaur | 50 | 0 | 1 | 1 | 0 | +40% | 0 | 0 | 0% | 2 | 0% | 1 | 0.5 |
| Glitch | 10 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 10% | 3 | 0% | 0 | 1 |
| Rainbow | 30 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0% | 2 | 0% | 0 | 1 |
| Twister | 45 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0% | 2 | 0% | 1 | 1 |
| Frosty | 28 | 0 | 1 | 1 | 0 | 0 | +10% | 0 | 0% | 2 | 30% | 0 | 0.8 |
| Poison | 27 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 5% | 2 | 30% | 0 | 1 |
| Berserk | 40 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 15% | 2 | 30% | 0 | 1.3 |
| Rock | 31 | 0 | 1 | 1 | 0 | 0 | 0 | 4 | 0% | 2 | 0% | 1 | 0.6 |
| Zombie | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0% | 2 | 0% | 0 | 1 |

#### Fear, power and survival

| Bird | Fear resist % | Fear time × | Fear −s | Fear immunity % | Power uses | Potency × | Power time × | Floor save % |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Yellow | 30% | 0.8 | 0 | 0% | 1 | 1 | 1 | 0% |
| Red | 0% | 1 | 0 | 0% | 1 | 1 | 1 | 0% |
| Blue | 0% | 1.3 | 0 | 0% | 1 | 1 | 1 | 0% |
| Patchwork | 10% | 1 | 0 | 0% | 1 | 1 | 1 | 0% |
| Purple | 20% | 1 | 0 | 0% | 1 | 1.1 | 1 | 0% |
| Clockwork | 0% | 1 | 0 | 15% | 1 | 1 | 1 | 0% |
| White | 40% | 1 | 0 | 0% | 1 | 1 | 1.2 | 0% |
| Orange | 0% | 1 | 0 | 50% | 1 | 1 | 1 | 0% |
| Gold | 0% | 1 | 0 | 0% | 1 | 1 | 1 | 0% |
| Cookie | 0% | 1.1 | 0 | 0% | 1 | 1 | 1 | 0% |
| Stealth | 0% | 1 | 0 | 0% | 1 | 1 | 1 | 0% |
| Dinosaur | 0% | 1 | 0 | 40% | 1 | 1 | 1 | 0% |
| Glitch | 0% | 1 | 0 | 0% | 1 | 1 | 1 | 10% |
| Rainbow | 30% | 1 | 0 | 0% | 1 | 1 | 1 | 0% |
| Twister | 20% | 1 | 0 | 0% | 1 | 1 | 1 | 0% |
| Frosty | 0% | 0.9 | 0 | 0% | 1 | 1 | 1 | 0% |
| Poison | 0% | 1 | 0 | 0% | 1 | 1 | 1.1 | 0% |
| Berserk | 0% | 1 | 0 | 25% | 1 | 1 | 1 | 0% |
| Rock | 30% | 1 | 0 | 0% | 1 | 1 | 1 | 0% |
| Zombie | 0% | 1 | 0 | 0% | 1 | 1 | 1 | 0% |

#### Economy

| Bird | Prestige | Score × | Grade bonus | XP × | Pickup | Luck % |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|
| Yellow | 0 | 1 | 0 | 1.1 | 3 | 5% |
| Red | 0 | 1 | 0 | 1 | 2 | 0% |
| Blue | 0 | 1 | 0 | 1 | 2 | 0% |
| Patchwork | 0 | 1 | 0 | 1.2 | 2 | 5% |
| Purple | 1 | 1 | 0 | 1 | 2 | 0% |
| Clockwork | 2 | 1 | 0 | 1 | 2 | 0% |
| White | 3 | 1.5 | 0 | 1 | 3 | 0% |
| Orange | 3 | 0.5 | 0 | 1 | 2 | 0% |
| Gold | 3 | 10 | 0 | 1 | 4 | 15% |
| Cookie | 2 | 1 | 0 | 1.5 | 3 | 0% |
| Stealth | 2 | 1.2 | 0 | 1 | 2 | 0% |
| Dinosaur | 4 | 2 | 0 | 1 | 2 | 0% |
| Glitch | 0 | 1 | 0 | 1 | 2 | 10% |
| Rainbow | 5 | 1.3 | 0 | 1 | 3 | 10% |
| Twister | 2 | 1 | 0 | 1 | 2 | 0% |
| Frosty | 1 | 1 | 0 | 1 | 2 | 0% |
| Poison | 1 | 1 | 0 | 1 | 2 | 0% |
| Berserk | 1 | 1 | 0 | 1 | 2 | 0% |
| Rock | 1 | 1 | 0 | 1 | 2 | 0% |
| Zombie | 0 | 0 | 0 | 0 | 0 | 0% |

### Enemies

#### Bats

| Enemy | HP | Defence | Contact def | Projectile def | Armor | Dmg taken × | Regen/s | Fear × | Fear radius | Speed × | Descent | Fear push | Stays (s) | Stun (s) | Knock | Fall (ticks/row) | XP × | Score × | Drop + |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Mini bat T0 | 160 | 0 | 0 | 0 | 0 | 1 | 0 | 1.2 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Bat T1 | 240 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Bat T2 | 480 | 1 | 0 | 0 | 0 | 1 | 0 | 1.1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Bat T3 | 960 | 2 | 0 | 0 | 0 | 1 | 5 | 1.2 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Bat T4 | 1920 | 4 | 0 | 0 | 0 | 1 | 10 | 1.3 | 0 | 0.9 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Armored T2 | 624 | 1 | 0 | -5 | 0 | 1 | 0 | 1.32 | 0 | 0.6 | 6 | 2 | 150 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Armored T3 | 1248 | 2 | 0 | -5 | 0 | 1 | 5 | 1.44 | 0 | 0.6 | 6 | 2 | 150 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Armored T4 | 2496 | 4 | 0 | -5 | 0 | 1 | 10 | 1.56 | 0 | 0.54 | 6 | 2 | 150 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Diver T1 | 192 | 0 | -3 | 0 | 0 | 1 | 0 | 1.3 | 0 | 1.3 | 5 | 1 | 60 | 1 | 0 | 5 | 1.2 | 1 | 0 |
| Diver T2 | 384 | 1 | -3 | 0 | 0 | 1 | 0 | 1.43 | 0 | 1.3 | 5 | 1 | 60 | 1 | 0 | 5 | 1.2 | 1 | 0 |
| Diver T3 | 768 | 2 | -3 | 0 | 0 | 1 | 5 | 1.56 | 0 | 1.3 | 5 | 1 | 60 | 1 | 0 | 5 | 1.2 | 1 | 0 |
| Diver T4 | 1536 | 4 | -3 | 0 | 0 | 1 | 10 | 1.69 | 0 | 1.17 | 5 | 1 | 60 | 1 | 0 | 5 | 1.2 | 1 | 0 |
| Spellcaster T2 | 336 | 1 | -2 | 5 | 0 | 1 | 0 | 1.65 | 1 | 0.9 | 5 | 1 | 60 | 1 | 0 | 5 | 1.4 | 1.4 | 0 |
| Spellcaster T3 | 672 | 2 | -2 | 5 | 0 | 1 | 5 | 1.8 | 1 | 0.9 | 5 | 1 | 60 | 1 | 0 | 5 | 1.4 | 1.4 | 0 |
| Spellcaster T4 | 1344 | 4 | -2 | 5 | 0 | 1 | 10 | 1.95 | 1 | 0.81 | 5 | 1 | 60 | 1 | 0 | 5 | 1.4 | 1.4 | 0 |
| Healer T2 | 384 | 1 | 0 | 0 | 0 | 1 | 0 | 0.88 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Healer T3 | 768 | 2 | 0 | 0 | 0 | 1 | 5 | 0.96 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Healer T4 | 1536 | 4 | 0 | 0 | 0 | 1 | 10 | 1.04 | 0 | 0.9 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Bomber T2 | 432 | 1 | 0 | 0 | 0 | 1 | 0 | 1.1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Bomber T3 | 864 | 2 | 0 | 0 | 0 | 1 | 5 | 1.2 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Bomber T4 | 1728 | 4 | 0 | 0 | 0 | 1 | 10 | 1.3 | 0 | 0.9 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Plague T2 | 432 | 1 | 0 | 0 | 0 | 1 | 0 | 1.1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Plague T3 | 864 | 2 | 0 | 0 | 0 | 1 | 5 | 1.2 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Plague T4 | 1728 | 4 | 0 | 0 | 0 | 1 | 10 | 1.3 | 0 | 0.9 | 5 | 1 | 60 | 1 | 0 | 5 | 1.3 | 1.3 | 0 |
| Necromancer T3 | 1056 | 2 | 0 | 3 | 0 | 1 | 5 | 1.44 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1.5 | 1.5 | 0 |
| Necromancer T4 | 2112 | 4 | 0 | 3 | 0 | 1 | 10 | 1.56 | 0 | 0.9 | 5 | 1 | 60 | 1 | 0 | 5 | 1.5 | 1.5 | 0 |

#### Bat abilities (highest tier, world 1 values; worlds change them)

| Kind | Ability stats |
|:--|:-:|
| Armored | armor 0; fear_push 2; linger 150; move_step 1 |
| Diver | ability_chance 0.2; ability_interval 0; dive_rows 10; dive_interval 2; dive_stun 1.5; return_interval 6; dive_push 1; dive_push_time 0.5 |
| Spellcaster | ability_chance 0.1; ability_interval 3; cast_time 0.5; spells 3; silence_time 5; wind_time 4.5; wind_push 1 |
| Healer | ability_chance 1; ability_interval 3; heal_pct 0.1; heal_range 12 |
| Bomber | ability_chance 0.5; ability_interval 4; stone_hp 30; stone_interval 2; stone_stun 0.5 |
| Plague | plague_time 15; plague_presses 3; plague_spread 0.05 |
| Necromancer | ability_chance 0.25; ability_interval 5; zombies 2; zombie_fear 1.5 |

#### Obstacles

| Enemy | HP | Defence | Contact def | Projectile def | Armor | Dmg taken × | Regen/s | Fear × | Fear radius | Speed × | Descent | Fear push | Stays (s) | Stun (s) | Knock | Fall (ticks/row) | XP × | Score × | Drop + |
|:--|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Tree T1 | 50 (+10%/level) | 0 | 0 | -3 | 0 | 1 | 0 | 1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Rock T2 | 80 (+10%/level) | 3 | 0 | 3 | 0 | 1 | 0 | 1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Cloud T3 | 160 (+10%/level) | 0 | 0 | 5 | 0 | 1.2 | 0 | 1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Barrier T4 | 320 (+10%/level) | 2 | 0 | 0 | 8 | 1 | 0 | 1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 5 | 1 | 1 | 0 |
| Stalactite (T1 base) | 50 (+10%/level) | 0 | 0 | -3 | 0 | 1 | 0 | 1 | 0 | 1 | 5 | 1 | 60 | 1 | 0 | 2 | 1 | 1 | 0 |
| Peak (T4 base) | 640 (+10%/level) | 2 | 0 | 0 | 23 | 1 | 0 | 1 | 0 | 1 | 5 | 1 | 60 | 1 | 2 | 5 | 1 | 1 | 0 |
