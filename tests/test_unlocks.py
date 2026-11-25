"""Fixed unlocks of the meta progression: formation, opening card, start grades, the merchant,
the difficulties that must be earned, upgrade levels that add up."""

from src.core import state
from src.engine import choices, grades, merchant, meta
from src.entities.bird_types import BirdType, get_bird_type_by_color
from tests.harness import Simulation


def new_run(upgrades=None, **profile):
    state.meta.profile = meta.new_profile()
    state.meta.profile['upgrades'] = dict(upgrades or {})
    state.meta.profile.update(profile)
    state.init(seed=3)
    state.settings.difficulty = 1
    state.game.meta_applied = False
    meta.start_run()


def test_upgrade_levels_add_up():
    with Simulation(seed=1, key_rate=0):
        new_run({'gold_digger': 5, 'extra_life': 3})
        assert meta.upgrade_value('gold_pct') == 50
        assert meta.upgrade_value('lives') == 3


def test_a_chosen_formation_is_the_starting_flock():
    with Simulation(seed=1, key_rate=0):
        flock = [BirdType.RED] * 9
        new_run({'formation': 1}, formation=flock)
        assert [get_bird_type_by_color(c) for c in state.birds.colors] == flock
        new_run({}, formation=flock)  # without the upgrade: the default flock
        assert [get_bird_type_by_color(c) for c in state.birds.colors] != flock
        assert BirdType.WHITE not in meta.formation_choices()  # evolved birds are never chosen


def test_training_and_veterans_start_birds_graded_up():
    with Simulation(seed=1, key_rate=0):
        new_run({'training': 1, 'veteran_red': 1})
        steps = grades.grade_steps()
        for color, xp in zip(state.birds.colors, state.birds.per_bird_xp):
            want = 2 if get_bird_type_by_color(color) == BirdType.RED else 1
            assert xp == steps[want]


def test_the_opening_card_offers_a_common_egg():
    with Simulation(seed=1, key_rate=0):
        new_run({'opening_card': 1})
        assert state.choice.active['kind'] == 'egg' and state.choice.active['rarity'] == 'common'


def test_the_merchant_sells_for_the_runs_gold():
    with Simulation(seed=1, key_rate=0):
        new_run({'merchant_stock': 1, 'haggling': 1})
        state.choice.active = None
        state.meta.run['level'] = 30  # 30 gold earned so far
        merchant.visit(1)
        offer = state.choice.active
        names = [c['id'] for c in offer['cards']]
        assert names == ['common_egg', 'rare_egg', 'mend', 'epic_egg', 'leave']
        rare = offer['cards'][1]
        assert rare['price'] == round(8 * 0.8)
        lives = state.game.lives
        choices.pick(2)  # mend
        assert state.game.lives == lives + 1 and meta.run_gold() == 30 - offer['cards'][2]['price']
        merchant.visit(1)
        state.meta.run['spent'] = 30  # nothing left to pay with
        assert choices.pick(1) is None and state.choice.active is not None  # the merchant waits
        choices.pick(len(state.choice.active['cards']) - 1)  # leave
        assert state.choice.active is None
        merchant.visit(6)  # never after the last world
        assert state.choice.active is None


def test_survival_and_legendary_must_be_earned():
    with Simulation(seed=1, key_rate=0):
        new_run()
        assert meta.difficulty_unlocked('ADVENTURE') and meta.difficulty_unlocked('PEACEFUL')
        assert not meta.difficulty_unlocked('SURVIVAL') and not meta.difficulty_unlocked('LEGENDARY')
        meta.profile()['lifetime'] = {'adventure_world4': 1}
        assert meta.difficulty_unlocked('SURVIVAL') and not meta.difficulty_unlocked('LEGENDARY')
        meta.profile()['lifetime']['won_survival'] = 1
        assert meta.difficulty_unlocked('LEGENDARY')
