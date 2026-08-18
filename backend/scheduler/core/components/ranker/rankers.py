from enum import Enum

from .base import Ranker
from .default import DefaultRanker
# from .greedymax import GreedyMaxOptimizer

from lucupy.types import Instantiable


__all__ = [
    'Rankers',
]


class Rankers(Instantiable[Ranker], Enum):
    DEFAULT = Instantiable(lambda: DefaultRanker())
    # GREEDYMAX = Instantiable(lambda: GreedyMaxOptimizer())
