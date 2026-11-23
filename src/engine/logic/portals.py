"""Cave portals (Void Cave biome)."""


from src.core import constants, state


def update_portals():
    """Update portals - fixed position, handle teleportation/destruction.

    Portals come only from the Owl Boss's bend_space spell.
    """
    if not any(p.get('from_owl_boss') for p in state.enemies.portals):
        if state.enemies.portals:
            _return_birds_to_home_lanes()
            state.enemies.portals = []
        return

    # Remove expired portals - when a portal pair expires, return birds to home lanes
    expired_pairs = set()
    for portal in state.enemies.portals[:]:
        if state.game.frame_count >= portal.get('expire_frame', float('inf')):
            expired_pairs.add(portal['pair_id'])
            state.enemies.portals.remove(portal)

    # If any portals expired, check if we need to return birds to home lanes
    if expired_pairs:
        _return_birds_to_home_lanes()

    # Check bird-portal collisions (teleportation)
    _check_bird_portal_teleport()

    # Check obstacle-portal collisions (destruction)
    _check_obstacle_portal_destruction()


def _return_birds_to_home_lanes():
    """Return all birds to their home lanes (where they belong when no portals exist)."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        home_lane = state.birds.home_lanes[i]
        current_lane = state.birds.random_lanes[i]

        if current_lane != home_lane:
            # Return bird to home lane
            state.birds.random_lanes[i] = home_lane
            state.birds.cols[i] = constants.layout.lane_positions[home_lane]


def _get_portal_pair(portal):
    """Get the paired portal for a given portal."""
    pair_id = portal['pair_id']
    portal_idx = portal['portal_idx']
    other_idx = 1 - portal_idx  # 0 -> 1, 1 -> 0

    for p in state.enemies.portals:
        if p['pair_id'] == pair_id and p['portal_idx'] == other_idx:
            return p
    return None


def _check_bird_portal_teleport():
    """Check if any birds CROSS through a portal and teleport them.

    CRITICAL: Birds MUST ALWAYS teleport when crossing a portal!
    If a bird passes through without teleporting, it ends up in the wrong
    part of the lane and overlaps with another bird.

    We check if the bird CROSSED the portal this frame by comparing
    previous position with current position.
    """
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_y = state.birds.y[i]
        bird_vy = state.birds.vy[i]  # -1 = up, +1 = down

        # Calculate where bird was BEFORE this frame's movement
        prev_y = bird_y - bird_vy

        for portal in state.enemies.portals:
            portal_lane = portal['lane']

            # Bird must be in the same lane as the portal
            if bird_lane != portal_lane:
                continue

            py = portal['y_pos']
            ph = portal['height']
            portal_top = py
            portal_bottom = py + ph - 1

            # Check if bird CROSSED through the portal zone
            # Either: currently inside, OR crossed through it this frame
            inside_now = portal_top <= bird_y <= portal_bottom

            # Check if bird crossed the portal boundary this frame
            crossed_going_up = bird_vy == -1 and prev_y >= portal_bottom and bird_y <= portal_top
            crossed_going_down = bird_vy == 1 and prev_y <= portal_top and bird_y >= portal_bottom

            if inside_now or crossed_going_up or crossed_going_down:
                # Find paired portal
                other_portal = _get_portal_pair(portal)
                if other_portal is None:
                    continue

                # Teleport to other portal based on direction
                new_lane = other_portal['lane']
                other_py = other_portal['y_pos']
                other_ph = other_portal['height']

                if bird_vy == -1:
                    # Going UP: exit ABOVE the other portal
                    new_y = other_py - 1
                else:
                    # Going DOWN: exit BELOW the other portal
                    new_y = other_py + other_ph

                # One bird per lane: a bird living in the exit lane takes this one's lane
                for j in range(constants.layout.num_balls):
                    if j != i and not state.birds.lost[j] and state.birds.random_lanes[j] == new_lane:
                        state.birds.random_lanes[j] = bird_lane
                        state.birds.cols[j] = constants.layout.lane_positions[bird_lane]

                # Update bird position - teleport to new lane
                # NOTE: home_lane is NOT changed! Bird keeps its original home lane.
                # When portals expire, bird returns to original home_lane.
                state.birds.cols[i] = constants.layout.lane_positions[new_lane]
                state.birds.random_lanes[i] = new_lane
                state.birds.y[i] = new_y
                # vy stays the same - bird continues in same direction!

                break


def _check_obstacle_portal_destruction():
    """Check if obstacles touch portals and destroy them."""
    for portal in state.enemies.portals:
        px = portal['x_pos']
        py = portal['y_pos']
        pw = portal['width']
        ph = portal['height']

        for obs in state.enemies.obstacles[:]:
            # Calculate obstacle x position from lane (centered on lane)
            obs_lane = obs.get('lane', 0)
            sprite = obs.get('sprite')
            if sprite:
                sprite_width = max(len(line) for line in sprite)
            else:
                sprite_width = obs.get('sprite_width', 5)

            # Obstacle is centered on lane
            lane_x = constants.layout.lane_positions[obs_lane]
            ox = lane_x - sprite_width // 2
            oy = obs['y_pos']
            ow = sprite_width
            oh = len(sprite) if sprite else obs.get('sprite_height', 3)

            # Check overlap
            if ox < px + pw and ox + ow > px and oy < py + ph and oy + oh > py:
                # Destroy obstacle
                state.enemies.obstacles.remove(obs)
                break  # One obstacle per portal per frame
