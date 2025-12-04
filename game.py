#!/usr/bin/env python3
"""
Game orchestration layer for BVB.
This module provides high-level game functions that coordinate between
variables and utility functions, managing game state through context.
"""
import variables as v
import functions as f


def create_game_context():
    """
    Create a comprehensive game context dictionary.
    Merges configuration and runtime state.
    
    Returns:
        dict: Complete game context with config and state
    """
    ctx = {
        # Configuration
        'config': v.config,
        'args': v.args,
        
        # Layout
        'WIDTH': v.WIDTH,
        'HEIGHT': v.HEIGHT,
        'NUM_BALLS': v.NUM_BALLS,
        'NUM_LANES': v.NUM_LANES,
        'LANE_POSITIONS': v.LANE_POSITIONS,
        'STARTING_LINE': v.STARTING_LINE,
        
        # Timing
        'base_sleep': v.base_sleep,
        'min_sleep': v.min_sleep,
        'notification_duration_seconds': v.notification_duration_seconds,
        'FRAME_SLEEP_LEVEL_MULTIPLIER': v.FRAME_SLEEP_LEVEL_MULTIPLIER,
        
        # Physics
        'SPEED_MIN': v.SPEED_MIN,
        'SPEED_MAX': v.SPEED_MAX,
        'BALL_SPEEDS_DEFAULT': v.BALL_SPEEDS_DEFAULT,
        
        # Progression
        'XP_BASE': v.XP_BASE,
        'GRADE_EXP_FACTOR': v.GRADE_EXP_FACTOR,
        'LEVEL_SCORE_BASE': v.LEVEL_SCORE_BASE,
        'LEVEL_SCORE_FACTOR': v.LEVEL_SCORE_FACTOR,
        
        # Eggs and rarity
        'EGG_PROBS': v.EGG_PROBS,
        'RARITY_WEIGHTS': v.RARITY_WEIGHTS,
        
        # Bats
        'BAT_HP_BY_TIER': v.BAT_HP_BY_TIER,
        'BAT_LOOT_BASE_WEIGHTS': v.BAT_LOOT_BASE_WEIGHTS,
        'SCARED_BASE_SECONDS': v.SCARED_BASE_SECONDS,
        'SCARED_SPEED_BOOST_SECONDS': v.SCARED_SPEED_BOOST_SECONDS,
        
        # Obstacles
        'OBSTACLE_MAX_HP_BY_TIER': v.OBSTACLE_MAX_HP_BY_TIER,
        
        # Combo
        'COMBO_WINDOW_FRAMES': v.COMBO_WINDOW_FRAMES,
        'YELLOW_BLUE_CHAIN_WINDOW': v.YELLOW_BLUE_CHAIN_WINDOW,
        
        # Combat
        'BAT_CENTER_OFFSET': v.BAT_CENTER_OFFSET,
        'XP_BONUS_PER_TIER': v.XP_BONUS_PER_TIER,
        'OBSTACLE_SCORE_MULTIPLIER': v.OBSTACLE_SCORE_MULTIPLIER,
        
        # Special bird constants
        'DINOSAUR_PRESSES_TO_BOUNCE': v.DINOSAUR_PRESSES_TO_BOUNCE,
        'DINOSAUR_PRESS_CHUNK': v.DINOSAUR_PRESS_CHUNK,
        'DINOSAUR_RECOVERY_ON_EGG': v.DINOSAUR_RECOVERY_ON_EGG,
        'STEALTH_TANGIBLE_SECONDS': v.STEALTH_TANGIBLE_SECONDS,
        'CLOCKWORK_DECAY_SECONDS': v.CLOCKWORK_DECAY_SECONDS,
        'CLOCKWORK_INITIAL_CHARGE': v.CLOCKWORK_INITIAL_CHARGE,
        'CLOCKWORK_MIN_CHARGE': v.CLOCKWORK_MIN_CHARGE,
        'CLOCKWORK_MAX_CHARGE': v.CLOCKWORK_MAX_CHARGE,
        'GLITCH_BOUNCE_IGNORE_CHANCE': v.GLITCH_BOUNCE_IGNORE_CHANCE,
        'GLITCH_LOOT_IGNORE_CHANCE': v.GLITCH_LOOT_IGNORE_CHANCE,
        'GLITCH_LOOT_PROMOTE_CHANCE': v.GLITCH_LOOT_PROMOTE_CHANCE,
        'GLITCH_SURVIVE_ON_FLOOR_CHANCE': v.GLITCH_SURVIVE_ON_FLOOR_CHANCE,
        'GLITCH_FLIP_CHANCE': v.GLITCH_FLIP_CHANCE,
        'GLITCH_SWAP_CHANCE': v.GLITCH_SWAP_CHANCE,
        'ORANGE_RECOVER_CHANCE': v.ORANGE_RECOVER_CHANCE,
        
        # Shuffle
        'SHUFFLE_LEVEL_BASE': v.SHUFFLE_LEVEL_BASE,
        'SHUFFLE_LEVEL_PLUS': v.SHUFFLE_LEVEL_PLUS,
        'SHUFFLE_LEVEL_PLUSPLUS': v.SHUFFLE_LEVEL_PLUSPLUS,
        'SHUFFLE_LEVEL_MAX': v.SHUFFLE_LEVEL_MAX,
        
        # Game state (runtime, to be updated during gameplay)
        'score': 0,
        'level': 1,
        'frame_count': 0,
        'per_bird_xp': [],
        'ball_lost': [],
        'bird_power_used': [],
        'bird_power_uses': [],
        'purple_state': [],
        'purple_just_fired_frames': [],
        'ball_vy': [],
        'random_lanes': [],
        'achievements': {},
        'notifications': [],
        'bird_grades': [],
    }
    
    return ctx


# Utility functions - delegating to functions.py

def safe_call(func, *args, ctx=None, **kwargs):
    """
    Safely call a function with exception handling.
    Delegates to functions.safe_call with context.
    """
    return f.safe_call(func, *args, ctx=ctx or {}, **kwargs)


def background_call(func, *args, ctx=None, **kwargs):
    """
    Call a function in a background thread.
    Delegates to functions.background_call with context.
    """
    return f.background_call(func, *args, ctx=ctx or {}, **kwargs)


def rgb_escape(r, g, b, ctx=None):
    """Generate RGB escape sequence."""
    return f.rgb_escape(r, g, b, ctx or {})


def color_from_hp(current_hp, max_hp, ctx=None):
    """Get color based on HP percentage."""
    return f.color_from_hp(current_hp, max_hp, ctx or {})


def render_patchwork_line(bird_index, frame_offset, ctx=None):
    """Render a line of the patchwork bird sprite."""
    return f.render_patchwork_line(bird_index, frame_offset, ctx or {})


def render_clockwork_line(bird_index, frame_offset, ctx=None):
    """Render a line of the clockwork bird sprite."""
    return f.render_clockwork_line(bird_index, frame_offset, ctx or {})


# Game calculation functions

def calculate_level_threshold(level, ctx=None):
    """
    Calculate score threshold for a given level.
    Uses LEVEL_SCORE_BASE and LEVEL_SCORE_FACTOR from context.
    """
    return f.calculate_level_threshold(level, ctx or {})


def compute_level_from_score(score, ctx=None):
    """
    Compute current level based on score.
    Uses LEVEL_SCORE_BASE and LEVEL_SCORE_FACTOR from context.
    """
    return f.compute_level_from_score(score, ctx or {})


def compute_grade_from_xp(xp, ctx=None):
    """
    Compute bird grade from XP.
    Uses XP_BASE and GRADE_EXP_FACTOR from context.
    """
    return f.compute_grade_from_xp(xp, ctx or {})


def compute_prestige(bird_grades, ctx=None):
    """
    Compute prestige multiplier based on bird grades.
    """
    return f.compute_prestige(bird_grades, ctx or {})


def adjust_rarity_weights(level, base_weights, ctx=None):
    """
    Adjust rarity weights based on level.
    """
    return f.adjust_rarity_weights(level, base_weights, ctx or {})


def get_scared_frames(is_speed_boost, ctx=None):
    """
    Get number of frames a bat stays scared.
    Uses SCARED_BASE_SECONDS and SCARED_SPEED_BOOST_SECONDS from context.
    """
    return f.get_scared_frames(is_speed_boost, ctx or {})


# High-level game state functions
# These would typically manipulate game state in start.py
# For now, they serve as entry points that could be implemented

def add_score(amount, ctx, by_bird=None):
    """
    Add score to the game, applying prestige multiplier.
    Updates ctx['score'] and awards XP.
    
    Args:
        amount: Raw score amount before prestige
        ctx: Game context dictionary
        by_bird: Index of bird that earned the score (for XP award)
    
    Returns:
        Actual score added (after prestige)
    """
    try:
        # Compute prestige multiplier
        bird_grades = ctx.get('bird_grades', [])
        prestige = compute_prestige(bird_grades, ctx)
        
        # Apply prestige to score
        actual_score = int(amount * prestige)
        ctx['score'] = ctx.get('score', 0) + actual_score
        
        # Award XP to the bird
        if by_bird is not None and 0 <= by_bird < len(ctx.get('per_bird_xp', [])):
            award_xp(by_bird, amount, ctx)
        
        # Check for level up
        new_level = compute_level_from_score(ctx['score'], ctx)
        old_level = ctx.get('level', 1)
        if new_level > old_level:
            ctx['level'] = new_level
            # Could trigger level-up effects here
        
        return actual_score
    except Exception as e:
        print(f"Error in add_score: {e}")
        return 0


def award_xp(bird_index, amount, ctx):
    """
    Award XP to a specific bird.
    Updates ctx['per_bird_xp'] and ctx['bird_grades'].
    
    Args:
        bird_index: Index of bird to award XP to
        amount: XP amount to award
        ctx: Game context dictionary
    """
    try:
        per_bird_xp = ctx.get('per_bird_xp', [])
        if bird_index < 0 or bird_index >= len(per_bird_xp):
            return
        
        # Add XP
        per_bird_xp[bird_index] = per_bird_xp.get(bird_index, 0) + amount
        
        # Compute new grade
        new_grade = compute_grade_from_xp(per_bird_xp[bird_index], ctx)
        
        # Update bird grades
        bird_grades = ctx.get('bird_grades', [0] * len(per_bird_xp))
        if bird_index < len(bird_grades):
            old_grade = bird_grades[bird_index]
            if new_grade > old_grade:
                bird_grades[bird_index] = new_grade
                # Could trigger grade-up effects here
                
    except Exception as e:
        print(f"Error in award_xp: {e}")


def add_notification(text, ctx):
    """
    Add a notification to the game.
    Updates ctx['notifications'] with frame-based duration.
    
    Args:
        text: Notification text
        ctx: Game context dictionary
    """
    try:
        notifications = ctx.get('notifications', [])
        frame_count = ctx.get('frame_count', 0)
        base_sleep = ctx.get('base_sleep', 0.2)
        duration_seconds = ctx.get('notification_duration_seconds', 3.0)
        
        # Calculate frame duration
        frames = int(duration_seconds / base_sleep) if base_sleep > 0 else 150
        
        # Add notification with expiry frame
        notifications.append({
            'text': text,
            'expires_at_frame': frame_count + frames
        })
        
        # Keep only recent notifications (limit to 5)
        if len(notifications) > 5:
            notifications[:] = notifications[-5:]
            
    except Exception as e:
        print(f"Error in add_notification: {e}")


def unlock_achievement(aid, ctx):
    """
    Unlock an achievement.
    Updates ctx['achievements'] and could send to firebase.
    
    Args:
        aid: Achievement ID
        ctx: Game context dictionary
    """
    try:
        achievements = ctx.get('achievements', {})
        
        # Mark as unlocked if not already
        if aid not in achievements or not achievements[aid]:
            achievements[aid] = True
            
            # Add notification
            add_notification(f"Achievement unlocked: {aid}", ctx)
            
            # Could send to firebase here if available
            # firebase_client = ctx.get('firebase_client')
            # if firebase_client:
            #     firebase_client.unlock_achievement(aid)
            
    except Exception as e:
        print(f"Error in unlock_achievement: {e}")


def check_achievements_event(event_type, event_data, ctx):
    """
    Check if any achievements should be unlocked based on an event.
    
    Args:
        event_type: Type of event (e.g., 'score', 'level', 'grade', 'combo')
        event_data: Event-specific data
        ctx: Game context dictionary
    """
    try:
        # This is a placeholder for complex achievement logic
        # In the real game, this would check various conditions
        # and call unlock_achievement() as needed
        
        achievements = ctx.get('achievements', {})
        score = ctx.get('score', 0)
        level = ctx.get('level', 1)
        
        # Example: score milestones
        if event_type == 'score':
            if score >= 10000 and not achievements.get('score_10k'):
                unlock_achievement('score_10k', ctx)
            if score >= 50000 and not achievements.get('score_50k'):
                unlock_achievement('score_50k', ctx)
        
        # Example: level milestones
        elif event_type == 'level':
            if level >= 10 and not achievements.get('level_10'):
                unlock_achievement('level_10', ctx)
            if level >= 25 and not achievements.get('level_25'):
                unlock_achievement('level_25', ctx)
                
    except Exception as e:
        print(f"Error in check_achievements_event: {e}")


def deduct_score(amount, ctx):
    """
    Deduct score from the game (e.g., for penalties).
    Updates ctx['score'], preventing negative values.
    
    Args:
        amount: Score amount to deduct
        ctx: Game context dictionary
    
    Returns:
        Actual score deducted
    """
    try:
        current_score = ctx.get('score', 0)
        actual_deduction = min(amount, current_score)
        ctx['score'] = current_score - actual_deduction
        
        # Check if level decreased
        new_level = compute_level_from_score(ctx['score'], ctx)
        old_level = ctx.get('level', 1)
        if new_level < old_level:
            ctx['level'] = new_level
        
        return actual_deduction
    except Exception as e:
        print(f"Error in deduct_score: {e}")
        return 0


# Additional helper functions for game logic

def init_game_state(ctx, num_birds=9):
    """
    Initialize game state arrays in context.
    
    Args:
        ctx: Game context dictionary
        num_birds: Number of birds in the game
    """
    try:
        ctx['per_bird_xp'] = [0] * num_birds
        ctx['bird_grades'] = [0] * num_birds
        ctx['ball_lost'] = [False] * num_birds
        ctx['bird_power_used'] = [False] * num_birds
        ctx['bird_power_uses'] = [0] * num_birds
        ctx['purple_state'] = [''] * num_birds
        ctx['purple_just_fired_frames'] = [0] * num_birds
        ctx['ball_vy'] = [0] * num_birds
        ctx['random_lanes'] = list(range(num_birds))
        ctx['score'] = 0
        ctx['level'] = 1
        ctx['frame_count'] = 0
        ctx['achievements'] = {}
        ctx['notifications'] = []
    except Exception as e:
        print(f"Error in init_game_state: {e}")


def update_frame_count(ctx):
    """
    Increment frame counter and clean up expired notifications.
    
    Args:
        ctx: Game context dictionary
    """
    try:
        ctx['frame_count'] = ctx.get('frame_count', 0) + 1
        
        # Clean up expired notifications
        frame_count = ctx['frame_count']
        notifications = ctx.get('notifications', [])
        ctx['notifications'] = [
            n for n in notifications
            if n.get('expires_at_frame', 0) > frame_count
        ]
    except Exception as e:
        print(f"Error in update_frame_count: {e}")


# Module info
if __name__ == '__main__':
    print("BVB Game Orchestration Module")
    print("=" * 50)
    print("This module provides high-level game functions.")
    print("Import it in start.py to use the modular structure.")
    print()
    print("Example usage:")
    print("  import game")
    print("  ctx = game.create_game_context()")
    print("  game.init_game_state(ctx, num_birds=9)")
    print("  game.add_score(100, ctx, by_bird=0)")
