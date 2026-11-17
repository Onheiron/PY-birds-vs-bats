"""What each kind of bird is like, asked by bird index instead of by colour.

Game code used to compare a bird's colour with STEALTH, DINOSAUR... wherever
a kind behaved differently. Traits shared by several systems are answered
here instead, so a kind's rules are written once:

  height(i)          rows the bird's sprite occupies (collision box)
  is_intangible(i)   passes through enemies, obstacles and loot
  is_phased_in(i)    a Stealth bird that made itself tangible (power active)

Powers live in src/engine/powers.py, in the POWERS table keyed by bird type.
"""

from dataclasses import dataclass

from src.core import state
from src.entities.bird_types import BirdType, get_bird_type_by_color


@dataclass(frozen=True)
class Traits:
    height: int = 2
    # Phases through everything unless its power made it tangible
    phases: bool = False


TRAITS = {
    BirdType.DINOSAUR: Traits(height=3),
    BirdType.STEALTH: Traits(phases=True),
}
_DEFAULT = Traits()


def kind(i):
    """Bird type of bird ``i`` (e.g. 'STEALTH'), or None for an unknown colour."""
    return get_bird_type_by_color(state.birds.colors[i])


def traits(i):
    return TRAITS.get(kind(i), _DEFAULT)


def height(i):
    return traits(i).height


def is_phased_in(i):
    """A phasing bird whose power currently makes it tangible."""
    return traits(i).phases and i in state.special.stealth_timers


def is_intangible(i):
    return traits(i).phases and i not in state.special.stealth_timers
