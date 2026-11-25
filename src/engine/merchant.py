"""The merchant: between worlds, after the boss's pact, wares paid with the run's gold.

It is a choice like an egg's (src/engine/choices.py): the wares are listed with
their price, ENTER buys the one selected (if the run has earned that much
gold) and the merchant leaves; the last option leaves without buying. What
is spent comes off the gold the run pays when it ends (meta.spend).

``merchant`` in config.yml lists the wares (an egg to open, lives, rerolls),
the ones always offered and one more of the extras per Merchant Stock level.
Prices follow the difficulty (as the run's gold does) and Haggling lowers them.
"""

from src.core import constants, state
from src.engine import meta
from src.engine.notifications import notify

LEAVE = {'id': 'leave', 'name': 'Leave', 'kind': 'refuse', 'rarity': 'common', 'effects': [], 'drawbacks': []}
LAST_WORLD = 6


def _cfg():
    node = getattr(constants, 'merchant', None)
    return node if isinstance(node, dict) else vars(node) if node is not None else {}


def _as_dict(node):
    return node if isinstance(node, dict) else vars(node) if node is not None else {}


def price(base):
    """A ware's price this run: × the difficulty's factor, less Haggling."""
    discount = min(90.0, meta.upgrade_value('merchant_discount')) if state.meta.profile else 0.0
    return max(1, int(round(float(base) * meta.difficulty_factor() * (1 - discount / 100))))


def wares():
    """The wares offered now, as cards: {'id', 'name', 'kind': 'ware', 'price', ...}."""
    cfg = _cfg()
    table = _as_dict(cfg.get('wares'))
    names = list(cfg.get('stock') or [])
    extra = int(meta.upgrade_value('merchant_stock')) if state.meta.profile else 0
    names += list(cfg.get('extra') or [])[:extra]
    out = []
    for name in names:
        entry = _as_dict(table.get(name))
        if not entry:
            continue
        ware = dict(entry, id=name, kind='ware', rarity=entry.get('egg', 'common'))
        ware['price'] = price(entry.get('price', 1))
        out.append(ware)
    return out


def visit(world):
    """The merchant comes after the boss of ``world`` (not after the last one)."""
    if world >= LAST_WORLD or state.meta.run is None:
        return
    items = wares()
    if not items:
        return
    from src.engine import choices

    choices.open_offer(
        {
            'kind': 'merchant',
            'title': 'THE MERCHANT',
            'rarity': 'common',
            'cards': items + [dict(LEAVE)],
            'index': 0,
            'refusable': True,
        }
    )


def buy(ware):
    """Pay for ``ware`` and get it; False (and the merchant stays) when the run cannot pay."""
    if not meta.spend(ware['price']):
        notify(f"Not enough gold: {ware['price']} (you have {meta.run_gold()})", title='Merchant')
        return False
    from src.engine import cards, choices

    if ware.get('lives'):
        state.game.lives += int(ware['lives'])
    for allowance in ('rerolls', 'skips'):
        if ware.get(allowance):
            cards.apply_effect({allowance: ware[allowance]}, source='merchant')
    if ware.get('egg'):
        choices.offer_egg(ware['egg'])
    notify(f"{ware['name']}  -{ware['price']} gold", title='Merchant')
    return True
