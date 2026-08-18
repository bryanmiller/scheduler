from enum import Enum

from .base import Ranker
from .default import DefaultRanker
from .additive import AdditiveRanker

from lucupy.types import Instantiable


__all__ = [
    'Rankers',
]


class Rankers(Instantiable[Ranker], Enum):
    DEFAULT = Instantiable(lambda: DefaultRanker())
    ADDITIVE = Instantiable(lambda: AdditiveRanker())
