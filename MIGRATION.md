# Migration Guide: Bird Types Refactoring

## Obiettivo
Eliminare l'uso diretto dei colori ANSI come identificatori di bird e sostituirli con `BirdType` enum e il dizionario `BIRD_TYPES`.

## Prima (❌ Old Way)
```python
from sprites import YELLOW, RED, BLUE

# Controllare tipo bird
if state.ball_colors[i] == YELLOW:
    # do something

# Get display name
name = constants.COLOR_NAME_MAP[YELLOW]  # ❌ Deprecated

# Get spawn limit
limit = constants.COLOR_LIMITS[YELLOW]  # ❌ Deprecated

# Spawn bird from egg
if egg_type == 'yellow_egg':
    color = constants.EGG_TO_COLOR[egg_type]  # ❌ Deprecated

# Get speed
speed = constants.BALL_SPEEDS_DEFAULT['YELLOW']  # ❌ Deprecated
```

## Dopo (✅ New Way)
```python
from bird_types import BirdType, BIRD_TYPES, get_display_name, get_spawn_limit, get_bird_type_from_egg, get_default_speed, get_color_for_bird_type

# Controllare tipo bird (usa ancora colori per compatibilità)
bird_type = BirdType.YELLOW
color = BIRD_TYPES[bird_type]['color']

if state.ball_colors[i] == color:
    # do something

# Get display name
name = get_display_name(BirdType.YELLOW)  # ✅ "Yellow"

# Get spawn limit  
limit = get_spawn_limit(BirdType.YELLOW)  # ✅ None (unlimited)

# Spawn bird from egg
bird_type = get_bird_type_from_egg('yellow_egg')  # ✅ BirdType.YELLOW
color = get_color_for_bird_type(bird_type)

# Get speed
speed = get_default_speed(BirdType.YELLOW)  # ✅ 2
```

## Variabili Rimosse da constants.py

- ❌ `COLOR_NAME_MAP` → ✅ `get_display_name(bird_type)`
- ❌ `COLOR_LIMITS` → ✅ `get_spawn_limit(bird_type)`  
- ❌ `EGG_TO_COLOR` → ✅ `get_bird_type_from_egg(egg)`
- ❌ `BALL_SPEEDS_DEFAULT` → ✅ `get_default_speed(bird_type)`

## Migration Steps

### Step 1: Identificare usi di colori legacy
```bash
grep -r "YELLOW\|RED\|BLUE" --include="*.py" .
```

### Step 2: Sostituire inizializzazioni
```python
# Prima
ball_colors = [YELLOW, YELLOW, RED]

# Dopo
from bird_types import BirdType, get_color_for_bird_type
formation = [BirdType.YELLOW, BirdType.YELLOW, BirdType.RED]
ball_colors = [get_color_for_bird_type(bt) for bt in formation]
```

### Step 3: Sostituire confronti
```python
# Prima
if bird_color == YELLOW:

# Dopo (opzione A - tramite bird_type)
bird_type = get_bird_type_by_color(bird_color)
if bird_type == BirdType.YELLOW:

# Dopo (opzione B - mantenendo color per performance)
if bird_color == BIRD_TYPES[BirdType.YELLOW]['color']:
```

### Step 4: Sostituire lookup dati
```python
# Prima
display_name = COLOR_NAME_MAP[color]
spawn_limit = COLOR_LIMITS[color]
speed = BALL_SPEEDS_DEFAULT['YELLOW']

# Dopo  
bird_type = get_bird_type_by_color(color)
display_name = get_display_name(bird_type)
spawn_limit = get_spawn_limit(bird_type)
speed = get_default_speed(bird_type)
```

## File da Migrare (Priority Order)

1. **state.py** - Inizializzazione ball_colors usando formation
2. **functions.py** - Funzioni che usano COLOR_NAME_MAP, COLOR_LIMITS
3. **start_new.py** - Main loop che confronta colori
4. **render.py** - Rendering che usa colori
5. **achievements.py** - Check achievement per colori specifici

## Note

- I colori ANSI restano in `sprites.py` come legacy per compatibilità
- Durante la migrazione, `state.ball_colors` continuerà a contenere stringhe ANSI
- Eventualmente `state.ball_colors` può diventare `state.ball_types` con BirdType enum
- Non c'è fretta: la migrazione può essere graduale

## Vantaggi

✅ Singola fonte di verità per tutti i dati bird  
✅ Facile aggiungere nuovi bird types  
✅ Type safety con enum-like  
✅ Codice più leggibile: `BirdType.YELLOW` invece di `"\033[38;5;220m"`  
✅ Facile estendere con nuovi attributi (cooldown, cost, etc.)
