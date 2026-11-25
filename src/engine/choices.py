"""Choices that stop the game: the cards of an egg, the pacts after a boss.

While ``state.choice.active`` is set the session does not advance (the game
clock holds, as in a pause) and the keys move between the options, which are
listed top to bottom: UP / DOWN select, ENTER takes. An egg can also be
rerolled (R) or skipped (S) a few times per run (cards.rerolls / cards.skips). A pact offer also
has a last option to refuse.

An offer is a dict: {'kind': 'egg' | 'pact' | 'merchant', 'title', 'rarity', 'cards': [...],
'index', 'refusable'}. Offers arriving while another one is on screen wait
in ``state.choice.queue``.
"""

import random

from src.core import state
from src.engine import cards, events

REFUSE = {'id': 'refuse', 'name': 'Refuse', 'kind': 'refuse', 'rarity': 'common', 'effects': [], 'drawbacks': []}


def active():
    return state.choice.active


def open_offer(offer):
    """Show any offer (the merchant's), or queue it."""
    _open(offer)


def _open(offer):
    """Show ``offer`` now, or queue it behind the one on screen.

    An egg's cards are drawn when it is shown (``cards`` None until then), so a
    queued egg reflects what the choices before it changed (a bird hatched, a
    card type maxed...).
    """
    if state.choice.active is not None:
        state.choice.queue.append(offer)
        return
    if offer['kind'] == 'egg' and offer.get('cards') is None:
        roll = cards.roll_birds if offer.get('birds_only') else cards.roll_offer
        offer['cards'] = roll(offer['rarity'], random)
    if not offer['cards']:
        _next()
        return
    state.choice.active = offer
    events.emit('choice_offered', offer=offer)


def _next():
    """Show the next queued offer, if any."""
    if state.choice.active is None and state.choice.queue:
        _open(state.choice.queue.pop(0))


def offer_egg(rarity, rng=random, birds_only=False):
    """Stop the game and offer the cards of an egg of ``rarity`` (``birds_only``: bird cards only,
    the merchant's brood)."""
    roll = cards.roll_birds if birds_only else cards.roll_offer
    _open(
        {
            'kind': 'egg',
            'title': 'BROOD' if birds_only else f'{rarity.upper()} EGG',
            'rarity': rarity,
            'birds_only': birds_only,
            # Drawn now if shown now; a queued egg draws its cards when its turn comes
            'cards': roll(rarity, rng) if state.choice.active is None else None,
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


def _allowance(name):
    """Rerolls or skips left this run (starting from cards.rerolls / cards.skips)."""
    value = getattr(state.choice, name)
    if value is None:
        from src.core import constants

        value = int(getattr(getattr(constants, 'cards', None), name, 3))
        setattr(state.choice, name, value)
    return value


def rerolls_left():
    return _allowance('rerolls')


def skips_left():
    return _allowance('skips')


def reroll(rng=random):
    """New cards for the egg on screen (an egg only; uses one reroll)."""
    offer = state.choice.active
    if offer is None or offer['kind'] != 'egg' or rerolls_left() <= 0:
        return False
    state.choice.rerolls -= 1
    offer['cards'] = (cards.roll_birds if offer.get('birds_only') else cards.roll_offer)(offer['rarity'], rng)
    offer['index'] = 0
    events.emit('choice_rerolled', offer=offer)
    return True


def skip():
    """Leave the egg on screen without taking anything (uses one skip)."""
    offer = state.choice.active
    if offer is None or offer['kind'] != 'egg' or skips_left() <= 0:
        return False
    state.choice.skips -= 1
    state.choice.active = None
    events.emit('choice_made', offer=offer, card=dict(REFUSE, id='skip', name='Skip'))
    _next()
    return True


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
    if offer['kind'] == 'merchant' and card['kind'] == 'ware':
        from src.engine import merchant

        if not merchant.buy(card):
            return None  # not enough gold: the merchant waits
        state.choice.active = None
        events.emit('choice_made', offer=offer, card=card)
        _next()
        return card
    state.choice.active = None
    if card['kind'] != 'refuse':
        state.choice.taken.append(
            {
                'id': card.get('id'),
                'name': card.get('name', card.get('id')),
                'kind': card['kind'],
                'rarity': card.get('rarity'),
            }
        )
    cards.took(card)
    if card['kind'] == 'pact':
        cards.apply_pact(card)
    elif card['kind'] != 'refuse':
        cards.apply_card(card)
    events.emit('choice_made', offer=offer, card=card)
    if offer['kind'] == 'pact':
        from src.services import save_manager

        save_manager.checkpoint()  # a boss beaten and its pact settled
    _next()
    return card


def handle_key(key):
    """Keys while a choice is on screen: UP / DOWN move, ENTER takes, R rerolls, S skips."""
    if key in ('UP', 'DOWN'):
        from src.services import sound

        sound.menu_key(key)
    if key == 'UP':
        move(-1)
    elif key == 'DOWN':
        move(1)
    elif key == 'ENTER':
        pick()
    elif key in ('R', 'r'):
        reroll()
    elif key in ('S', 's'):
        skip()
