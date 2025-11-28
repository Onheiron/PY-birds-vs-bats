# BVB - Bird vs Bat Juggling Game

A roguelike arcade game where you juggle 9 colorful birds that bounce and battle against obstacles and bats!
# BVB — Bird vs Bat (terminal arcade)

Bird vs Bat (BVB) is a lightweight terminal arcade/roguelike where you juggle 9 birds, use per-bird powers,
manage lanes, and fight dynamically spawning bats and obstacles. This README documents how to play,
what changed recently, developer notes and configuration.

All content below is in English.

## Quick start

From source (recommended for development):

```bash
python3 start.py
```

Standalone binary (if present):
- macOS: `dist/BVB` (run `./dist/BVB`)
- Windows: `dist/BVB.exe`

## Controls

- ← / → : Move cursor between lanes
- ↑ : Bounce the bird in the selected lane (if already rising, activates that bird's power — once per ascent)
- ↓ : Suction (if you have the suction power active) — pulls affected birds down
- SPACE : Swap mode (select a lane, press again to swap two birds). Swap costs points (200 × current level).
- Q or Ctrl+C : Quit

## What's new (high level)

- Added new bird types: STEALTH, PATCHWORK, GOLD and their eggs.
- `stealth_egg`: a new rare egg (rarity = "rare", weight = 10) that spawns a STEALTH bird when collected.
- STEALTH bird behaviour:
  - Normally invisible: rendering alternates between visible dark-gray and ANSI "conceal" (SGR 8) so it is
    hidden on supporting terminals.
  - Pass-through: while stealth (non-tangible) it passes through bats, obstacles and loot.
  - Power (press ↑ while rising): become tangible for a short window and deal heavy damage to nearby enemies.
  - Power also grants a short speed boost (speed = 6) for the power duration.
- PATCHWORK bird and `patchwork_egg` (uncommon): per-character multicolor sprite for visual variety.
- GOLD bird and `gold_egg` (rare): special scoring bird (higher passive score / fast speed).
- Blue sprint behaviour fixed: sprint now times out correctly and the bird returns to its normal color when the boost ends.
- Despawn: bats and loot older than 60 seconds are cleaned up automatically to avoid screen clutter.
- Firebase telemetry: total play time is now tracked and submitted with game-over events.
- Misc: audio/music backend removed for determinism in terminal builds.

## Birds (summary)

Each bird has a base speed and a special power triggered while the bird is rising (↑ twice).

- Yellow (speed 2)
  - Power: slow adjacent falling birds for a short duration (except other yellows, which are bounced).

- Red (speed 3)
  - Power: fires a projectile upward. Projectile damage increases when adjacent red/patchwork birds are rising.

- Blue (speed 4)
  - Power: temporary speed boost and +1 damage. The bird is visually highlighted (CYAN) while boosted.
  - Sprint is limited-time and will stop either on bounce or when the boost duration expires.

- White (speed 4)
  - Power: affects multiple lanes (±2 lanes). Can bounce falling birds or trigger rising birds' powers.

- Purple (speed 3)
  - Power: special interactions with obstacles/bats (useful for tile control).

- Grey (speed 2)
  - Auto-bounce on floor (helps keep lanes active). Does not die on floor like other birds.

- PATCHWORK (speed 3)
  - Visual-only special: per-character colored sprite. Counts for adjacency synergies like other colors.

- GOLD (speed 6)
  - High-scoring special bird. Scores larger passive points each frame when alive.

- STEALTH (speed 3 base)
  - Stealth behavior (see "Stealth mechanics" below).

## Stealth mechanics (detailed)

- Stealth birds alternate between visible DARK_GRAY and ANSI conceal (hidden) while flying.
- While in stealth (non-tangible) they pass through bats, obstacles and loot — they won't collide or collect.
- Activating the stealth power (↑ while rising) makes the bird tangible for a short duration (configurable in code):
  - During tangibility the bird deals heavy damage to nearby bats/obstacles and destroys nearby loot.
  - The bird's speed is temporarily set to 6 for the duration of the tangible window.
  - The bird displays a bright color (WHITE) while tangible so the player sees the power.
- The power is allowed only once per ascent (the internal `bird_power_used` flag prevents re-activation until the bird
  falls and then rises again).

## Loot system (brief)

- Loot drop logic takes the enemy tier and current empty lanes into account. Eggs are only dropped when there are
  empty lanes available (to avoid unreachable eggs).
- New egg: `stealth_egg` included in the "rare" egg pool with weight 10.

Rare egg composition now includes: blue_egg, grey_egg, purple_egg, gold_egg, stealth_egg (weights: 40, 20, 20, 10, 10).

When a `stealth_egg` is collected, it spawns a STEALTH bird in the first available (dead) bird slot.

## Enemies & despawn

- Obstacles and bats spawn in tiers with increasing HP and difficulty.
- Entities older than 60 seconds are automatically removed from the world (both bats and loot) to reduce clutter.

## Achievements & telemetry

- Basic achievements are tracked and displayed as short notifications.
- If a Firebase client is configured, the game attempts to submit analytics events in the background.
- On game over the session's elapsed play time (seconds + formatted string) is included with the score submission.

## Developer notes

Run locally:

```bash
python3 start.py
```

Build a single-file executable with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --name BVB --console start.py
```

Configuration & tuning

- Many gameplay timings are derived from `base_sleep` at the top of `start.py`.
  - `base_sleep` controls the global frame speed; durations are converted to frame counts using `int(seconds/base_sleep)`.
- To tune power durations, search for values like `int(2.0 / base_sleep)` or `int(5.0 / base_sleep)` in `start.py`.
- Stealth tangible window and speed boost are applied near the code path where `stealth_timers[...]` is set.

Terminal compatibility notes

- The stealth effect uses ANSI SGR 8 (conceal) to hide the sprite on terminals that support it. Not all terminals honor
  SGR 8; on terminals that ignore it the invisibility will be a no-op and the bird will still appear. If you see no
  invisibility, the bird will still behave correctly (pass-through mechanics are logic-based).

Debugging tips

- Enable on-screen notifications (they are used for achievements and some debug messages). They appear in the footer.
- If a power doesn't look like it activated, check whether `bird_power_used` is True for that bird (logic prevents multiple
  activations per ascent).

Contributing

- Open a PR with focused changes. Prefer minimal, isolated diffs. If changing tune constants, include the rationale and
  observable impact (e.g. "increased blue sprint to 8s for better feel").

License & credits

- This project is provided as-is. See repository for license information and credits.

Enjoy and let me know if you want any of these behaviours tuned or documented further.
