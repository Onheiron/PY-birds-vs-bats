# Worlds: what each one adds

Every world introduces something. All the numbers are in `config.yml`:
`bat_enemy.worlds` (how many bats, how often, which tiers and kinds),
`enemy_stats` (the stats of every tier and kind, per world: `worlds.<w>`, and
for elites: `elite_kinds`) and `hazards` (the world hazards). Stat list and
sheets: `docs/stats.md`.

| World | New |
|---|---|
| 1 Windy Woods | tailwind gusts on 2–4 adjacent lanes; mini bats (10%) |
| 2 The Borders | bats, divers |
| 3 Rotten Marshes | obstacles that emerge from the marsh; armored bats, spellcasters (silence only), healers |
| 4 The Dark Swamp | flowers on obstacles; bombers, plague bats |
| 5 The Void Cave | darkness and fireflies, stalactites, hard rocks, obstacles out of the dark; necromancers |
| 6 Mountain Range | fog, peaks, tail- and headwinds |

## Bats per world (`bat_enemy.worlds`)

| World | On screen | Every (ticks) | T1/T2/T3/T4 | Armored | Diver | Spellcaster | Healer | Bomber | Plague | Necromancer | Mini bat |
|---|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | 0 | – | – | – | – | – | – | – | – | – | 10% |
| 2 | 3 | 110 | 65/30/5/0 | – | 8% | – | – | – | – | – | 20% |
| 3 | 4 | 95 | 45/35/17/3 | 8% | 10% | 6% | 6% | – | – | – | 30% |
| 4 | 4 | 85 | 30/40/22/8 | 10% | 12% | 8% | 6% | 8% | 6% | – | 40% |
| 5 | 5 | 70 | 15/35/35/15 | 15% | 12% | 10% | 8% | 10% | 8% | 5% | 50% |
| 6 | 6 | 55 | 5/25/45/25 | 20% | 14% | 12% | 8% | 10% | 10% | 8% | 60% |

Elites: 0, 3, 6, 9, 12, 15% (`elites.chance_by_biome`). Jumpscares are 15% of mini bats.

## Bat kinds

- **Armored** (tier 2+): armor, slower, stays 150 s; a bird it scares falls faster (`fear_push` 2).
- **Diver**: dives `dive_rows` rows, stays stunned `dive_stun` s, climbs back; a bird that hits it mid-dive is pushed down.
- **Spellcaster** (tier 2+): silence (no powers), repugnant wind (faster falls, slower climbs), exile (swaps your best bird out of its lanes).
- **Healer** (tier 2+): heals the bats around it (`heal_pct` of max HP within `heal_range` columns) every `ability_interval` s. Badge `+`.
- **Bomber** (tier 2+): drops stones: small obstacles that fall fast (`stone_interval` ticks per row) and stun briefly. Badge `o`.
- **Plague** (tier 2+): a bird it touches is infected: it dies after `plague_time` s unless cured with `plague_presses` UP presses (3); every second it may infect a bird in a lane next to it (`plague_spread`, 5%), wherever it is. Badge `¤`.
- **Necromancer** (tier 3+): raises zombie birds (`@`) in your empty lanes, `zombies` at most (2; elites 3). They bounce by themselves while it lives and scare a falling bird they pass in a lane next to theirs. Badge `†`.

## Hazards (`hazards`)

- **Winds** (worlds 1 and 6): every 12–20 s (6–10 s) 2–4 adjacent lanes get tailwind (`^` on the starting line: climb faster, fall slower) for 5 s; in world 6 half are headwinds (`v`, the opposite).
- **Emerging obstacles** (worlds 3 and 5): a quarter of the obstacles appear at 35–70% of the screen height, as bubbles for 1 s (not solid), then fall as usual.
- **Darkness** (world 5): only the cursor's lane and the ones beside it can be seen, plus the lanes of Clockwork birds. Bats drop fireflies (`✦`, 15%): light everywhere for 8 s.
- **Stalactites** (world 5): every 6–10 s a lane cracks at the top for 1 s, then a stalactite falls down it fast.
- **Hard rocks** (world 5): rocks have ×1.5 HP and +3 defence.
- **Peaks** (world 6): a quarter of the obstacles are peaks: ×2 HP, +15 armor, and a bird that hits one falls faster for 1 s.
- **Fog** (world 6): cloud banks drifting down over the birds.

The bot does not know about darkness and fog: it sees the whole screen.
