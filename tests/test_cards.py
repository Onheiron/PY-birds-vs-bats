"""Rarity eggs, card offers, the choice that stops the game, boss pacts."""

import random
from collections import Counter

from src.core import constants
from src.engine import cards, choices, enemy_stats, stats
from src.engine.enemy_stats import RARITIES
from tests.harness import Simulation


def offers(rarity, n=300):
    rng = random.Random(1)
    return [cards.roll_offer(rarity, rng) for _ in range(n)]


def test_an_egg_guarantees_one_card_of_its_rarity():
    with Simulation(seed=1, key_rate=0):
        for rarity in RARITIES[:-1]:  # mythical cards are birds only (see below)
            for offer in offers(rarity, 50):
                assert len(offer) == 3
                # At least one card of the egg's rarity (the others can even be rarer)
                assert rarity in [c['rarity'] for c in offer]
                assert [RARITIES.index(c['rarity']) for c in offer] == sorted(
                    (RARITIES.index(c['rarity']) for c in offer), reverse=True
                ), 'rarest first'
                assert len({c['id'] for c in offer}) == 3, 'no duplicate cards'


def test_mythical_cards_are_birds_only():
    with Simulation(seed=1, key_rate=0) as sim:
        assert all(c['rarity'] != 'mythical' for o in offers('mythical', 50) for c in o)  # no free slot
        sim.state.birds.lost[0] = True
        mythical = [c for o in offers('mythical', 50) for c in o if c['rarity'] == 'mythical']
        assert mythical and all(c['kind'] == 'bird' for c in mythical)


def test_free_slots_bring_bird_eggs():
    with Simulation(seed=1, key_rate=0) as sim:
        for i in (0, 1, 2):
            sim.state.birds.lost[i] = True
        assert all(any(c['kind'] == 'bird' for c in o) for o in offers('common', 100))
        sim.state.birds.lost[1] = sim.state.birds.lost[2] = False
        share = sum(any(c['kind'] == 'bird' for c in o) for o in offers('common', 300)) / 300
        assert share >= 0.6


def test_rarer_eggs_never_offer_much_commoner_cards():
    with Simulation(seed=1, key_rate=0):
        legendary = Counter(c['rarity'] for o in offers('legendary') for c in o)
        assert legendary['common'] == legendary['uncommon'] == 0
        assert legendary['epic'] > 0 and legendary['rare'] > 0
        epic = Counter(c['rarity'] for o in offers('epic') for c in o)
        assert epic['common'] == 0
        rare = Counter(c['rarity'] for o in offers('rare') for c in o)
        assert 0 < rare['common'] < 0.1 * sum(rare.values())
        # Not every card of a rare egg is rare
        assert rare['uncommon'] > rare['rare'] * 0.5


def test_more_choices_and_rarity_scaling():
    with Simulation(seed=1, key_rate=0):
        stats.add_modifier('flock', 'choices', add=1)
        assert len(cards.roll_offer('common')) == 4
        common = cards._make_card('sharp_beaks', cards._catalog()['sharp_beaks'], 'common')
        epic = cards._make_card('sharp_beaks', cards._catalog()['sharp_beaks'], 'epic')
        assert epic['effects'][0]['pct'] == common['effects'][0]['pct'] * cards.rarity_scale('epic')


def test_bird_cards_need_a_free_lane_and_respect_unique_birds(monkeypatch):
    with Simulation(seed=1, key_rate=0) as sim:
        assert all(c['kind'] != 'bird' for o in offers('epic', 100) for c in o)
        sim.state.birds.lost[0] = True
        birds = [c['bird'] for o in offers('epic', 200) for c in o if c['kind'] == 'bird']
        assert birds and set(birds) <= {
            'WHITE',
            'ORANGE',
            'GOLD',
            'CLOCKWORK',
            'COOKIE',
            'STEALTH',
            'TWISTER',
            'FROSTY',
            'POISON',
            'BERSERK',
            'PURPLE',
            'ROCK',
            'DINOSAUR',
            'GLITCH',
        }
        from src.entities.sprites import WHITE

        sim.state.birds.colors[1] = WHITE
        birds = [c['bird'] for o in offers('epic', 200) for c in o if c['kind'] == 'bird']
        assert 'WHITE' not in birds


def test_picking_up_an_egg_stops_the_game_until_a_card_is_taken():
    with Simulation(seed=2, key_rate=0) as sim:
        state = sim.state
        sim.run(30)
        choices.offer_egg('rare', random.Random(4))
        assert state.choice.active is not None
        before = state.game.frame_count
        sim.run(120)
        assert state.game.frame_count == before, 'the game does not advance while choosing'
        card = state.choice.active['cards'][1]
        sim.step(key='DOWN')
        sim.step(key='ENTER')
        assert state.choice.active is None
        assert any(m['source'] == f"card:{card['id']}" for m in state.stats.modifiers) or card['kind'] in (
            'bird',
            'powerup',
            'training',
        )
        sim.run(30)
        assert state.game.frame_count > before


def test_choice_keys_move_up_and_down_and_only_enter_takes():
    with Simulation(seed=2, key_rate=0) as sim:
        choices.offer_egg('common', random.Random(4))
        offer = sim.state.choice.active
        sim.step(key='DOWN')
        assert offer['index'] == 1
        sim.step(key='UP')
        sim.step(key='UP')
        assert offer['index'] == len(offer['cards']) - 1, 'UP from the top wraps to the bottom'
        for key in ('LEFT', 'RIGHT', 'SPACE'):
            sim.step(key=key)
        assert sim.state.choice.active is offer, 'only ENTER takes a card'
        sim.step(key='ENTER')
        assert sim.state.choice.active is None


def test_pacts_scale_with_the_boss_and_can_be_refused():
    with Simulation(seed=3, key_rate=0) as sim:
        state = sim.state
        first = {p['id']: p for p in cards.roll_pacts(1, random.Random(1))}
        last = {p['id']: p for p in cards.roll_pacts(6, random.Random(1))}
        assert len(first) == 3
        for pact_id in set(first) & set(last):
            assert abs(last[pact_id]['effects'][0].get('pct', last[pact_id]['effects'][0].get('add', 0))) > abs(
                first[pact_id]['effects'][0].get('pct', first[pact_id]['effects'][0].get('add', 0))
            )

        choices.offer_pact(1, random.Random(1))
        offer = state.choice.active
        assert offer['cards'][-1]['kind'] == 'refuse'
        choices.pick(len(offer['cards']) - 1)
        assert state.stats.modifiers == [] and state.stats.pacts == []


def test_a_pact_can_make_bats_tougher():
    with Simulation(seed=3, key_rate=0):
        pact = {
            'id': 'test',
            'name': 'Test',
            'kind': 'pact',
            'rarity': 'common',
            'effects': [{'stat': 'damage_mult', 'pct': 10}],
            'drawbacks': [{'enemy': {'hp_mult': 50}}],
        }
        cards.apply_pact(pact)
        bat = enemy_stats.equip_bat({'tier': 1, 'hp': 100, 'max_hp': 100})
        assert bat['max_hp'] == 150
        assert stats.bird(0, 'damage_mult') > 1


def test_enemies_drop_rarity_eggs():
    with Simulation(seed=4, key_rate=0):
        from src.engine.loot_tables import choose_loot_type

        assert choose_loot_type('epic') == 'egg'
        assert vars(constants.cards.drop_chance) == {'bat': 1.0, 'mini_bat': 1.0, 'boss': 1.0}


def test_a_choice_survives_save_and_load(tmp_path, monkeypatch):
    from src.services import save_manager

    monkeypatch.setattr(save_manager, 'get_save_path', lambda slot: tmp_path / f'slot{slot}.json')
    with Simulation(seed=5, key_rate=0) as sim:
        choices.offer_egg('epic', random.Random(2))
        names = [c['name'] for c in sim.state.choice.active['cards']]
        assert save_manager.save_game(1)
        sim.state.choice.active = None
        assert save_manager.load_game(1)
        assert [c['name'] for c in sim.state.choice.active['cards']] == names


def test_rerolls_and_skips_are_limited_per_run():
    with Simulation(seed=6, key_rate=0) as sim:
        for _ in range(3):
            choices.offer_egg('rare', random.Random(1))
            before = [c['id'] for c in sim.state.choice.active['cards']]
            sim.step(key='R')
            assert sim.state.choice.active is not None
            sim.step(key='S')
            assert sim.state.choice.active is None
            assert before
        assert choices.rerolls_left() == 0 and choices.skips_left() == 0
        choices.offer_egg('rare', random.Random(1))
        sim.step(key='R')
        sim.step(key='S')
        assert sim.state.choice.active is not None, 'no skips left: the egg stays until a card is taken'


def test_prestige_cards_add_and_multiply_prestige():
    with Simulation(seed=6, key_rate=0):
        from src.engine.progression import compute_prestige

        base = compute_prestige()
        stats.add_modifier('flock', 'prestige_bonus', add=2)
        assert compute_prestige() == base + 2
        stats.add_modifier('flock', 'prestige_mult', mul=1.5)
        assert compute_prestige() == (base + 2) * 1.5


def test_every_card_shows_kind_duration_and_effects():
    with Simulation(seed=6, key_rate=0):
        for card_id, entry in cards._catalog().items():
            low = cards._as_dict(entry).get('min_rarity', 'common')
            info = cards.card_info(cards._make_card(card_id, entry, low))
            assert info['kind'] and info['duration'] and info['text'] and info['lines'], card_id
        tailwind = cards.card_info(cards._make_card('tailwind', cards._catalog()['tailwind'], 'common'))
        assert tailwind['duration'] == '10 s'


def test_power_ups_last_their_seconds_of_game_time():
    with Simulation(seed=6, key_rate=0) as sim:
        from src.engine import clock
        from src.engine.logic.loot import apply_powerup

        apply_powerup('tailwind')
        start = clock.now()
        while sim.state.powerups.tailwind_active and clock.now() - start < 30:
            sim.step(key=None)
        assert 9.5 < clock.now() - start < 10.6
