#!/usr/bin/env python3
"""
Utility functions for BVB game.
All functions accept a 'ctx' parameter containing game state and globals.
"""
import threading


def safe_call(func, *a, **kw):
    """Safely call a function, catching all exceptions."""
    try:
        func(*a, **kw)
    except Exception:
        pass


def background_call(func, *a, **kw):
    """Execute function in background thread."""
    try:
        t = threading.Thread(target=safe_call, args=(func,)+a, kwargs=kw, daemon=True)
        t.start()
    except Exception:
        pass


def rgb_escape(r: int, g: int, b: int) -> str:
    """Generate RGB color escape sequence."""
    return f"\033[38;2;{r};{g};{b}m"


def color_from_hp(base_rgb: tuple, hp: int, max_hp: int) -> str:
    """
    Interpolate color from base RGB based on HP ratio.
    Returns ANSI escape code.
    """
    if max_hp <= 0:
        return rgb_escape(*base_rgb)
    ratio = hp / max_hp
    darker_r = int(base_rgb[0] * ratio)
    darker_g = int(base_rgb[1] * ratio)
    darker_b = int(base_rgb[2] * ratio)
    return rgb_escape(darker_r, darker_g, darker_b)


def render_patchwork_line(line: str) -> str:
    """Render a line with patchwork coloring (each char different color)."""
    try:
        # Rotate through multiple colors
        colors = [
            "\033[38;5;226m",  # Yellow
            "\033[38;5;196m",  # Red
            "\033[38;5;21m",   # Blue
            "\033[38;5;201m",  # Purple
            "\033[38;5;208m",  # Orange
        ]
        result = ""
        for i, ch in enumerate(line):
            result += colors[i % len(colors)] + ch
        return result + "\033[0m"
    except Exception:
        return line


def render_clockwork_line(line: str, charge: int, blink_on: bool) -> str:
    """Render clockwork bird with charge indicator."""
    try:
        # Colors by charge level
        charge_colors = {
            0: "\033[38;5;240m",  # Dark gray (no charge)
            1: "\033[38;5;178m",  # Gold
            2: "\033[38;5;226m",  # Bright yellow
            3: "\033[38;5;202m",  # Bright orange (max)
        }
        # Blink effect at max charge
        if charge >= 3 and not blink_on:
            return "\033[38;5;15m" + line + "\033[0m"  # White flash
        color = charge_colors.get(charge, "\033[38;5;178m")
        return color + line + "\033[0m"
    except Exception:
        return line


def calculate_level_threshold(level, ctx):
    """Calculate score threshold for given level."""
    try:
        base = float(ctx.get('LEVEL_SCORE_BASE', 500.0))
        factor = float(ctx.get('LEVEL_SCORE_FACTOR', 1.07))
        return int(base ** (factor ** (level + 1)))
    except Exception:
        return int(500 ** (1.07 ** (level + 1)))


def compute_level_from_score(score, ctx):
    """Compute current level from score."""
    lvl = 1
    try:
        while score >= calculate_level_threshold(lvl, ctx):
            lvl += 1
    except Exception:
        pass
    return lvl


def compute_grade_from_xp(xp, ctx):
    """Map XP to a grade (D, C1, C2, B1, B2, A1, A2, S) with colour."""
    try:
        xp = int(float(xp))
    except Exception:
        xp = 0
    
    # Use configurable progression constants
    try:
        base = float(ctx.get('XP_BASE', 500.0))
        factor = float(ctx.get('GRADE_EXP_FACTOR', 1.07))
    except Exception:
        base = 500.0
        factor = 1.07
    
    # Color constants
    GREEN = "\033[32m"
    ORANGE = "\033[38;5;208m"
    WHITE = "\033[37m"
    GOLD = "\033[38;5;220m"
    RED = "\033[31m"
    DARK_GRAY = "\033[90m"
    
    # If below base, D
    if xp < int(base):
        return ('D', GREEN)
    
    # Build thresholds for C1, C2, B1, B2, A1, A2, S using configurable factor
    labels = ['C1', 'C2', 'B1', 'B2', 'A1', 'A2', 'S']
    exps = [(factor ** n) for n in range(len(labels))]
    thresholds = [int(round(base ** e)) for e in exps]
    
    # Find highest label satisfied
    for lbl, thr in reversed(list(zip(labels, thresholds))):
        if xp >= thr:
            # Map letter to colour by prefix
            prefix = lbl[0]
            color_map = {'D': GREEN, 'C': ORANGE, 'B': WHITE, 'A': GOLD, 'S': RED}
            return (lbl, color_map.get(prefix, DARK_GRAY))
    
    # If not matched, fallback to C1
    return ('C1', ORANGE)


def compute_prestige(ctx):
    """Compute prestige based on bird grades."""
    try:
        per_bird_xp = ctx.get('per_bird_xp', [])
        grade_value_map = {
            'D': 0, 'C1': 1, 'C2': 2,
            'B1': 3, 'B2': 4,
            'A1': 5, 'A2': 6,
            'S': 7
        }
        total = 0
        for xp in per_bird_xp:
            grade, _ = compute_grade_from_xp(xp, ctx)
            total += grade_value_map.get(grade, 0)
        return total
    except Exception:
        return 0


def adjust_rarity_weights(base_weights, prestige):
    """
    Adjust rarity weights based on prestige.
    Higher prestige shifts distribution toward rarer items.
    """
    try:
        if prestige <= 0:
            return base_weights
        # Each prestige point shifts 1% from common to uncommon, uncommon to rare, rare to epic
        shift = min(prestige, 30)  # Cap at 30% shift
        adjusted = base_weights.copy()
        
        # Common loses, uncommon gains
        if len(adjusted) >= 2:
            loss = adjusted[0] * (shift / 100.0)
            adjusted[0] -= loss
            adjusted[1] += loss * 0.7  # 70% goes to uncommon
            if len(adjusted) >= 3:
                adjusted[2] += loss * 0.25  # 25% to rare
            if len(adjusted) >= 4:
                adjusted[3] += loss * 0.05  # 5% to epic
        
        return adjusted
    except Exception:
        return base_weights


def get_scared_frames(bird_idx, base_seconds, ctx):
    """Calculate scared duration in frames."""
    try:
        base_sleep = ctx.get('base_sleep', 0.2)
        return int(base_seconds / base_sleep)
    except Exception:
        return int(base_seconds / 0.2)
