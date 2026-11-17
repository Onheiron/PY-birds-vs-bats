# Bird stats

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

Speeds are in the game's speed points: a bird moves one cell every
`max(1, 6 − speed)` ticks, so fractional bonuses (+0.5) work.

## Movement

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `rise_speed_bonus` | 0 | -4 … 4 | speed points added while rising |
| `fall_speed_bonus` | 0 | -4 … 4 | speed points added while falling (negative: falls slower) |
| `bounce_sprint` | 0 | 0 … 4 | speed points added for a moment after each bounce |
| `bounce_sprint_seconds` | 1 | 0 … 10 | how long the bounce sprint lasts |
| `weight` | 1 | 0 … 10 | share of the flock centre of mass (drives momentum) |
| `presses_to_bounce` | 1 | 1 … 99 | UP presses needed to bounce it |
| `hitbox_height` | 2 | 1 … 5 | rows the bird occupies when colliding |

## Attack

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

## Fear

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `fear_resist` | 0 | 0 … 1 | share of the fear fall-speed bonus ignored |
| `fear_duration_mult` | 1 | 0 … 5 | multiplier on fear duration |
| `fear_duration_cut` | 0 | 0 … 10 | seconds removed from fear (never below 1 s) |
| `fear_immunity` | 0 | 0 … 1 | chance to ignore a scare entirely |

## Power

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `power_uses` | 1 | 0 … 10 | power activations per ascent |
| `power_potency` | 1 | 0 … 10 | multiplier on power strength |
| `power_duration` | 1 | 0 … 10 | multiplier on power duration |

## Survival

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `floor_save` | 0 | 0 … 1 | chance to bounce back instead of being lost at the floor |

## Economy

| Stat | Default | Range | Meaning |
|---|:-:|:-:|---|
| `prestige` | 0 | 0 … 99 | prestige the bird adds to the flock |
| `score_mult` | 1 | 0 … 100 | score multiplier for this kind of bird |
| `score_grade_bonus` | 0 | 0 … 10 | score bonus from grade (+0.1 = ×1.1) |
| `xp_gain` | 1 | 0 … 10 | multiplier on XP earned |
| `pickup_radius` | 2 | 0 … 10 | columns within which it collects loot |
| `luck` | 0 | 0 … 1 | chance to upgrade the rarity of what it collects |

## Formulas that use them

- **Damage:** `round((gear bonus + DMG + boosts + damage_bonus) × (1 + speed_damage × (SPD − 1))
  × damage_mult × (1 + vs_<target>) × crit)`, at least 1. The target is a bat,
  an obstacle or an elite (bosses). Armor is reduced by `armor_pierce` first.
- **Fear:** a scare lasts `seconds × fear_duration_mult − fear_duration_cut`
  (at least 1 s when a cut applies); `fear_immunity` is the chance to ignore it;
  while scared the bird falls `1 − fear_resist` speed points faster.
- **Score per move:** `speed × score_mult × (1 + score_grade_bonus)`.
- **Prestige:** `1 + Σ prestige` over the living birds.

## What the kinds and grades set today

See `bird_stats` in `config.yml`. In short: grades add prestige (C1 +0.03 …
A2 +1, S +5) and a score bonus (C1 +10% … S +100%); from B1 scares last one
second less; from A1 a bird fires its power twice per ascent (S included).
