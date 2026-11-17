# Removed and dormant mechanics

A record of everything that was in the code base but could not happen in a
game, removed during the November 2026 cleanup. Each entry says what it did
and where it lived, so it can be brought back or redesigned.

Everything listed here still exists in commit `7b9d259`. To read an old file:

```bash
git show 7b9d259:src/engine/actions.py
```

The second half of this page lists **configuration the game ignores by
mistake**: those are bugs, not removed features, and are still in the code.

---

## Gameplay mechanics

### Bounce Boost power-up
- **What it did:** while active, every bounce gave the bird a short speed boost
  (`speed_boosts`). Four strengths (`bounce_boost`, `+`, `++`, `_max`) lasting
  10 / 20 / 25 / 50 "seconds" with a 4 / 4 / 8 / 12 boost.
- **Why it was dead:** the loot pools only drop Wide Cursor, Tailwind and
  Timelapse, so it could never be picked up.
- **Where:** `_POWERUPS` in `src/engine/logic/loot.py`, timer in
  `update_powerup_timers` (`src/engine/logic/effects.py`), applied in
  `_bounce_bird_up` (`src/engine/actions.py`), drawn as `↺` in
  `src/ui/layers/enemies.py`, state `powerups.bounce_boost_*`, config section
  `bounce_boost`.

### Suction power-up (and the DOWN key)
- **What it did:** while active, DOWN pulled the rising birds under the cursor
  back down, optionally with a speed boost. Same four strengths and durations
  as Bounce Boost.
- **Why it was dead:** not in any loot pool. DOWN did nothing otherwise; the
  CONTROLS menu still offered to rebind it.
- **Where:** `handle_suction` in `src/engine/actions.py`, the `SUCTION` key
  binding (state, input handler, CONTROLS menu, guide page), timer in
  `effects.py`, drawn as `⥥`, state `powerups.suction_*`, config section `suction`.

### Shuffle power-up
- **What it did:** `perform_shuffle(count)` moved the birds farthest from the
  centre into free (or more central) lanes, 2 / 4 / 6 birds by strength, and
  reset the moved birds to the starting line, rising.
- **Why it was dead:** never called; not in the loot pools; no config section
  in `config.yml` (only in an old sample).
- **Where:** `perform_shuffle` and `_swap_lanes` in `src/engine/birds.py`;
  achievements `power_shuffle_1` and `power_shuffle_10`.

### Combos
- **What it did:** bounces, fires, suctions, stealth and twister powers were
  logged with `append_recent_action`, and `detect_combos` looked for two
  patterns: Fire → Suction → Bounce → Fire ("Elemental Chain") and a Yellow
  bounce near a Blue speed boost ("Fearless Flip"). Config: `combo.window_frames`
  (200), `combo.yellow_blue_chain_window` (60).
- **Why it was dead:** `detect_combos` was never called, so the log only grew.
- **Where:** `src/services/achievements.py`, calls in `actions.py` and `powers.py`.

### Synergy XP transfer
- **What it did:** `on_synergy_triggered` gave the weakest bird taking part in
  a synergy 10% of the XP gap to the strongest (`synergy.transfer_ratio: 0.1`).
- **Why it was dead:** never called (the hook it expected was never passed).
  The synergy *achievements* (two or three different powers in quick
  succession) still work.
- **Where:** `src/services/achievements.py`.

### Achievements with nothing to unlock them
29 achievements were defined but no game event ever triggered them:

| Achievements | Missing trigger |
|---|---|
| `destroy_obstacle_10`, `destroy_obstacle_100` | no `destroy_obstacle` event was ever sent |
| `hold_top50_100/200`, `hold_top30_200/400` | keeping the flock in the top 50% / 30% of the screen was never measured |
| `original_alive_300/700/2000` | survival of the starting flock was never measured |
| `count_<colour>_5/7`, `count_all_9` (15 in all) | flock composition was never counted |
| `synergy_adjacent_red` | the adjacent-Red synergy never reported itself |
| `power_shuffle_1/10` | Shuffle could not be obtained |
| `combo_fire_suction_bounce_fire`, `combo_yellow_blue_bounce_chain` | combos were never detected |

The definitions and their handlers (`area_hold`, `original_survive`,
`color_count`, `destroy_obstacle`) were in `init_achievements` and
`check_achievements_event` in `src/services/achievements.py`. Most of them
would be cheap to bring back: emit an event from the place where it happens
(for example `events.emit('obstacle_destroyed', ...)` where obstacles are removed).

### Biome discovery
- **What it did:** `discover_biome` recorded visited biomes in the Birdpedia
  save file.
- **Why it was dead:** never called; the BIOMES page shows every biome anyway.
- **Where:** `src/services/save_manager.py`, `state.discovery.biomes`.

### Online leaderboard reading, achievement sync, crash reports
- **What they did:** `get_leaderboard`, `sync_achievements`, `report_crash` and
  `sign_in_anonymous` in `src/services/firebase_client.py` read the top scores,
  uploaded the achievement list, sent crash traces and signed in anonymously.
- **Why they were dead:** nothing called them. Sending scores, unlocking
  achievements and logging events still works.

### Old frame timing
- **What it did:** the game used to sleep a variable time per frame depending
  on the gear: `get_frame_sleep_for_speed`, `calculate_frame_sleep`, config
  `speed.frame_sleep_at_speed_1/10`, `timing.min_sleep`,
  `timing.frame_sleep_level_multiplier`.
- **Why it was dead:** replaced by the fixed 60 FPS loop with a physics tick
  every N frames (`src/engine/timing.py`).

---

## Unused art

Sprites defined in `src/entities/sprites.py` that nothing drew:

- `BIRD_PATCH_UP_1/2`, `BIRD_PATCH_DOWN_1/2`: dedicated Patchwork bird frames
  (Patchwork uses the normal sprite with random colours instead).
- `WIND_BOSS_ANIM_SEQUENCE`, `JELLY_SPAWN_ANIM_FRAMES`, `OWL_BOSS_STATE_CYCLE`:
  animation tables the bosses do not follow.
- `OWL_PORTAL_FRAME_1/2`: Owl Boss portal art (portals use the cave portal sprites).
- `MOUNTAIN_CLOUD_SPRITES`: cloud shapes for the Mountain Range (clouds are
  generated procedurally).
- `BG_PATTERN`, `OBSTACLE_SPRITE`, `BATS_BASE_RGB`, `OBST_BASE_RGB`, `BLACK`;
  `render_patchwork_line` / `render_clockwork_line` (two copies each, in
  `sprites.py` and `src/ui/layers/birds.py`).

---

## Configuration keys that did nothing

Removed from `config.yml`, the difficulty presets and the samples; the
schema was regenerated. Values are those of `config.yml` at `7b9d259`.

| Key | Note |
|---|---|
| `bat_enemy.max_on_screen` | The real limit is `bat_enemy.max_bats_by_level`. The difficulty presets set it, with no effect. |
| `bat_enemy.spawn_interval_range` | The real spawn rate is `bat_enemy.spawn_rate_by_level`. Also set, uselessly, by the presets. |
| `bat_enemy.spawning.*`, `bat_enemy.tiers.*` | Old spawn tables; the game uses `tier_weights_by_level`, `target_y_by_level`, `hp_by_tier`. |
| `bat_enemy.scared.*`, `bat.*` | Old fear settings; fear duration is `combat.scared_duration`. |
| `obstacle.spawning.consecutive_spawn_limit`, `retry_timer_divisor`, `retry_timer_min` | Old spawn pacing. |
| `owl_boss.spells.overgrowth.flower_probability`, `spawn_radius_x`, `spawn_radius_y` | The spell uses fixed values. |
| `powers.*` | `blue_adjacent_boost_seconds` (5.0) and an empty `default` table. |
| `gold.score_value` | Gold scoring is `loot.gold_bird_score_per_tick`. |
| `despawn.*` | Despawn times are `loot.bat_despawn_time` / `loot.loot_despawn_time`. |
| `glitch.damage`, `glitch.loot_ignore_chance`, `glitch.loot_promote_chance` | Duplicates of `combat.glitch_dmg_multiplier_*` and `loot.glitch_*`. |
| `clockwork.lanes`, `clockwork.min_charge`, `dinosaur.recovery_on_egg`, `orange.out_of_play_y` | Never read (`out_of_play_y` is hard-coded as 999). |
| `combat.bat_center_offset`, `obstacle_score_multiplier`, `xp_bonus_per_tier` | Never read. |
| `layout.min_lane_index`, `layout.max_lane_index`, `levels.distance_increment_start`, `game_over.separator_width` | Never read. |
| `limits.*`, `physics.*`, `collision.*`, `rendering.*`, `controls.*` | Whole sections never read (key bindings live in the settings, not the config). |
| `eggs.rarity_weights` | A copy of `eggs.rarity_candidates`. |
| `combo.*`, `synergy.*`, `bounce_boost.*`, `suction.*`, `speed.frame_sleep_*`, `timing.min_sleep`, `timing.frame_sleep_level_multiplier` | Belonged to the mechanics above. |

`tools/config_usage.py` finds keys like these: it plays every biome and boss
with every bird type while recording which configuration values are read.

---

## Configuration the game ignores by mistake (bugs, still present)

These are meant to work, so they were **not** removed. Fixing them changes the
balance, so they are waiting for a decision.

### Egg tables (`eggs.rarity_candidates`)
The configuration is converted so that these tables end up in a shape
`_choose_egg` (`src/engine/loot_tables.py`) does not recognise, and it always
falls back to a table written in the code:

| Rarity rolled | Eggs in config.yml | Eggs the game actually drops |
|---|---|---|
| common | yellow, red, blue, patchwork | yellow, red, blue |
| uncommon | frosty, poison, berserk, purple, rock | blue, patchwork, purple |
| rare | clockwork, cookie, stealth, twister | white, orange, gold |
| epic | white, orange, gold | dinosaur, glitch |
| legendary | dinosaur, glitch | **yellow** |
| mythical | rainbow | **yellow** |

So Frosty, Poison, Berserk, Rock, Clockwork, Cookie, Stealth, Twister and
Rainbow never hatch, and a legendary or mythical drop is a yellow egg.

### Swamp flowers (`swamp_flowers.bloom_probability`)
The `swamp_flowers` section is not in `SECTIONS` (`src/core/constants.py`), so
it is never loaded: obstacles in the Dark Swamp bloom with the code default of
30% instead of the configured 50%.
