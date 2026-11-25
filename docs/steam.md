# BVB on Steam (Linux, Steam Deck)

The Steam build is the same game in a window of its own: a small terminal
emulator (`src/ui/window.py`, pygame-ce) draws what the game would print in a
terminal, with a bundled monospace font (DejaVu Sans Mono), and reads the
keyboard and any gamepad SDL knows: Xbox, PlayStation, the Steam Deck's
controls through Steam Input. It opens full screen; F11 or Alt+Enter toggles.

From the sources the same mode is `python3 game.py --window` (or `--fullscreen`),
with `pip install pygame-ce`.

## Controller layout

| Button | Playing | Egg cards, pacts | Menus, game over |
|---|---|---|---|
| D-pad ← → / left stick | move the cursor | — | move the selection |
| D-pad ↑ ↓ / left stick | ↑ bounce | move the selection | move the selection |
| LB / RB (L1 / R1) | move the cursor | — | move the selection |
| A (✕ on PlayStation) | **bounce** (and fire powers) | nothing (it is the bounce) | **select** |
| X (□) | — | **take** | — |
| Y (△) | show the XP bars | reroll | — |
| B (○) | **swap** (press on a lane, move, press again) | skip | back |
| RT (R2) | bounce | — | — |
| Start / Select (☰ / ⧉) | pause | pause | pause / resume |

Egg cards and pacts are taken with X, not A: A is the bounce, often mashed while
playing, and would take a card before it is even seen.

Typing a name at game over: the D-pad moves on the on-screen keyboard, A types
the key under the cursor (OK confirms, aA switches case), B deletes, Start
confirms. Held directions repeat.

The hints on screen name the controls of the device used last
(`src/ui/controls.py`): keys on the keyboard, [A] [B] [X] [Y] and LB/RB on an
Xbox pad, L1/R1 on the Steam Deck, ✕ ○ □ △ and L1/R1 on a PlayStation pad.
SETTINGS > CONTROLS > BUTTON LABELS fixes one (AUTO, KEYBOARD, XBOX,
PLAYSTATION, STEAM DECK); the COMMANDS page of the guide lists them too.

The thumbs split like on a keyboard: the left one moves (D-pad, or LB/RB
without leaving the face buttons), the right one bounces (A) and swaps (B).

In Steamworks set the default controller configuration to the **Gamepad**
template: Steam Input then passes the Deck's (or any pad's) buttons as an
Xbox controller, which the game maps as above. No custom Steam Input config
is needed.

## Building the Linux depot

Valve asks Linux games to be built in the Steam Linux Runtime 3 ("sniper"),
so that they run on the Steam Deck and on every distribution:

```bash
packaging/steam/build-linux.sh
```

It runs the build in the `registry.gitlab.steamos.cloud/steamrt/sniper/sdk`
container (docker or podman), with a standalone Python 3.12 and PyInstaller
(`packaging/steam/BVB-Steam.spec`). The result:

- `dist/BVB/`: the depot, the `BVB` executable plus `_internal/`;
- `dist/BVB-<version>-steam-linux.tar.gz`: the same, as one file.

The Release workflow (`.github/workflows/release.yml`) builds it too, in the
same container, and attaches the archive to the GitHub release.

## Uploading to Steam

1. In Steamworks create the app and a Linux depot; in `packaging/steam/app_build.vdf`
   and `depot_build_linux.vdf` put their IDs in place of `0000000` / `0000001`.
2. Build (above), then upload with steamcmd:

   ```bash
   steamcmd +login <builder account> +run_app_build "$PWD/packaging/steam/app_build.vdf" +quit
   ```

3. Launch options: executable `BVB`, operating system Linux, and set the
   app's launch to run in the **Steam Linux Runtime 3.0 (sniper)** (Steamworks →
   Installation → Linux Runtime).
4. Controller: default configuration **Gamepad** (see above); on the Deck
   compatibility page the game uses the full 1280×800 screen.

## Notes

- Saves, settings and recordings live in `~/.bvb/`. To keep them in Steam
  Cloud, add that folder in Steamworks → Steam Cloud (Auto-Cloud, root
  "Linux Home", path `.bvb`).
- Sound goes through SDL audio (pygame-ce's mixer), bundled with the game:
  nothing else to install.
- Menu hints still name keyboard keys (`↑↓ Navigate ⏎ Select`).
