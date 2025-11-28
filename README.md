# BVB - Bird vs Bat Juggling Game

A roguelike arcade game where you juggle 9 colorful birds that bounce and battle against obstacles and bats!

## How to Play

### Standalone Executable
The compiled executable is in the `dist/` folder:
- **macOS**: `dist/BVB` (double-click or from terminal: `./dist/BVB`)
- For Windows/Linux: recompile with PyInstaller on the target system

### From Source
```bash
python start.py
```

## Controls

- **← →**: Move cursor between lanes
- **↑**: Bounce bird upward (activate power if already rising)
- **↓**: Suction power (if active) - pull bird down
- **SPACE**: Swap mode - swap birds between lanes (costs 200 × level points)
- **Q** or **Ctrl+C**: Quit

## Birds and Powers

Ogni bird ha una velocità e un potere speciale (doppio tap ↑ mentre sale):

### 🟡 Yellow Bird (Speed 2)
- **Power**: Slows adjacent falling birds (-1 speed for 3s)
- **Special**: Bounces other yellow birds instead of slowing them
- **Strategy**: Blue birds lose fear if they cross a rising yellow

### 🔴 Red Bird (Speed 3)
- **Power**: Launches projectile (⋅) that rises quickly
- **Damage**: +1 for each adjacent rising red bird (becomes •)
- **Target**: Hits bats and obstacles

### 🔵 Blue Bird (Speed 4)
- **Power**: +1 speed AND +1 damage bonus (turns CYAN when active)
- **Pride**: Loses fear immediately if crossing a rising yellow

### ⚪ White Bird (Speed 4)
- **Power**: Multi-lane effect (±2 lanes)
  - Falling birds → bounced
  - Rising birds → their power activated

### 🟣 Purple Bird (Speed 3)
- **Power**: Può rimbalzare ostacoli e bat in lane occupata
- **Special**: Può occupare lane già occupate da altri birds
- **Strategia**: Utile per liberare lane bloccate

### ⚫️ Grey Bird (Speed 2)
- **Power**: Rimbalzo immediato su pavimento e soffitto
- **Special**: Non muore mai, non lascia X sul pavimento
- **Strategia**: Ottimo per mantenere lane sempre attive

## Enemies

### Obstacles (4 Tiers)
- Tier 1: Brown (4 HP)
- Tier 2: Dark Olive (6 HP)
- Tier 3: Olive Green (10 HP)
- Tier 4: Lime Green (16 HP)

### Bats (4 Tiers)
- Tier 1: Dark Purple (16 HP) - 1s no bounce
- Tier 2: Medium Purple (32 HP) - 2s no bounce
- Tier 3: Bright Purple (64 HP) - 2s no bounce + 3s speed boost
- Tier 4: Shocking Magenta (128 HP) - 3s no bounce + 3s speed boost

## Loot System

Bats drop power-ups with increasing rarity by tier:

### Common (60-35%)
- Yellow Egg, Wide Cursor (3 lanes, 10s), Bounce Boost (+1 speed 4s), Suction (10s)

### Uncommon (25-30%)
- Red Egg, Wide Cursor+ (20s), Bounce Boost+ (20s), Suction+ (20s)

### Rare (10-20%)
- Blue Egg, Wide Cursor++ (5 lanes, 25s), Bounce Boost++ (8s boost, 25s), Suction++ (25s)

### Epic (5-15%)
- White Egg, Wide Cursor Max (7 lanes, 50s), Boost Max (12s boost, 50s), Suction Max (8s boost, 50s)

## Advanced Mechanics

- **Swap**: Exchange two birds between lanes (teleport to starting line)
- **Lane Protection**: Maximum 1 obstacle per lane at a time
- **Fear System**: Birds hit by bats temporarily can't bounce
- **Strategic Combos**: Position red birds together for powered projectiles

## Build

To create the executable on other systems:

```bash
pip install pyinstaller
pyinstaller --onefile --name BVB --console start.py
```

The executable will be in `dist/BVB` (or `dist/BVB.exe` on Windows).

## Requirements (source only)

- Python 3.7+
- Terminal with ANSI color support (native macOS/Linux, Windows Terminal on Windows)

---

Have fun! 🎮
