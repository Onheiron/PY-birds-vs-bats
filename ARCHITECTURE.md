# BVB Architecture

## File Organization

### constants.py
Contiene tutte le **costanti di configurazione** che vengono lette all'avvio e non vengono mai modificate durante il gioco:
- Layout (WIDTH, HEIGHT, NUM_BALLS, LANE_POSITIONS, etc.)
- Timing (BASE_SLEEP, MIN_SLEEP, FRAME_SLEEP_LEVEL_MULTIPLIER)
- Physics (SPEED_MIN, SPEED_MAX, BALL_SPEEDS_DEFAULT)
- Bird types (BIRD_TYPES dictionary con tutte le configurazioni)
- Spawn rates e probabilità
- Damage values
- Colors e costanti grafiche
- Keyboard controls (KEY_*)

**Convenzione**: Tutte le costanti sono in `MAIUSCOLO_SNAKE_CASE`

### state.py
Contiene tutte le **variabili mutabili** che cambiano durante il gameplay:
- Score, level, lives
- Posizioni e velocità dei bird (ball_y, ball_vy, ball_speeds, etc.)
- Stato dei birds (ball_colors, ball_lost, ball_cols)
- Entità attive (bats, obstacles, loot_items, projectiles)
- Timers (frame_count, bat_spawn_timer, obstacle_spawn_timer)
- Power-ups attivi (powerups dictionary)
- Player state (player_lane, selected_lane, paused)
- XP e progression (per_bird_xp, transformed_s)
- Special abilities state (purple_state, clockwork_charge, stealth_timers, etc.)

### Regola generale:
- **constants.py**: "Quanto dovrebbe essere?" → Configurazione
- **state.py**: "Com'è adesso?" → Stato corrente

## Import Convention

```python
# constants.py - import diretto
import constants

# Usato come: constants.WIDTH, constants.KEY_ACTION

# state.py - import as module
import state

# Usato come: state.score, state.ball_y[i]
```

## Future Work
- Considerare Redux/state management per state.py
- Separare state.py in moduli più piccoli (entities, player, progression, etc.)
