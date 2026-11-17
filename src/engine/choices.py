"""Choices that stop the game: the cards of an egg, the pacts after a boss.

While ``state.choice.active`` is set the session does not advance (the game
clock holds, as in a pause) and the keys move between the options, which are
listed top to bottom: UP / DOWN select, ENTER takes. A pact offer also
has a last option to refuse.

An offer is a dict: {'kind': 'egg' | 'pact', 'title', 'rarity', 'cards': [...],
'index', 'refusable'}. Offers arriving while another one is on screen wait
in ``state.choice.queue``.
"""

import random

from src.core import state
from src.engine import cards, events

REFUSE = {'id': 'refuse', 'name': 'Refuse', 'kind': 'refuse', 'rarity': 'common', 'effects': [], 'drawbacks': []}


def active():
    return state.choice.active


def _open(offer):
    if not offer['cards']:
        return
    if state.choice.active is None:
        state.choice.active = offer
        events.emit('choice_offered', offer=offer)
    else:
        state.choice.queue.append(offer)


def offer_egg(rarity, rng=random):
    """Stop the game and offer the cards of an egg of ``rarity``."""
    _open(
        {
            'kind': 'egg',
            'title': f'{rarity.upper()} EGG',
            'rarity': rarity,
            'cards': cards.roll_offer(rarity, rng),
            'index': 0,
            'refusable': False,
        }
    )


def offer_pact(boss_number, rng=random):
    """Stop the game and offer the pacts of the ``boss_number``-th boss (with a way to refuse)."""
    pacts = cards.roll_pacts(boss_number, rng)
    if not pacts:
        return
    _open(
        {
            'kind': 'pact',
            'title': 'A PACT IS OFFERED',
            'rarity': pacts[0]['rarity'],
            'cards': pacts + [dict(REFUSE)],
            'index': 0,
            'refusable': True,
            'boss': boss_number,
        }
    )


def move(step):
    offer = state.choice.active
    if offer:
        offer['index'] = (offer['index'] + step) % len(offer['cards'])


def pick(index=None):
    """Take the option at ``index`` (default: the selected one) and resume the game."""
    offer = state.choice.active
    if offer is None:
        return None
    card = offer['cards'][offer['index'] if index is None else index]
    state.choice.active = None
    if card['kind'] == 'pact':
        cards.apply_pact(card)
    elif card['kind'] != 'refuse':
        cards.apply_card(card)
    events.emit('choice_made', offer=offer, card=card)
    if state.choice.queue:
        _open(state.choice.queue.pop(0))
    return card


def handle_key(key):
    """Keys while a choice is on screen: UP / DOWN move, ENTER takes."""
    if key == 'UP':
        move(-1)
    elif key == 'DOWN':
        move(1)
    elif key == 'ENTER':
        pick()
