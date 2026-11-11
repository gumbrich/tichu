"""Pure combination classification and a complete reference move generator."""
from collections import Counter
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import combinations, product

from .cards import Card, DOG, MAHJONG, PHOENIX, DRAGON


@dataclass(frozen=True)
class Combination:
    cards: tuple[Card, ...]
    kind: str
    rank: float
    phoenix_rank: int | None = None

    @property
    def is_bomb(self):
        return self.kind in ('four_bomb', 'straight_bomb')

    def beats(self, other):
        if other is None:
            return True
        if other.kind == 'dog' or self.kind == 'dog':
            return False
        if self.is_bomb:
            return (not other.is_bomb or
                    (len(self.cards), self.rank) > (len(other.cards), other.rank))
        return (not other.is_bomb and self.kind == other.kind and
                len(self.cards) == len(other.cards) and self.rank > other.rank)

    def __str__(self):
        wild = f' (Phoenix = {Card.ranks[self.phoenix_rank]})' if self.phoenix_rank else ''
        ordered = sorted(self.cards, key=lambda c: (c.rank, c.suit))
        return f'{self.kind}: ' + ', '.join(map(str, ordered)) + wild


def classify(cards):
    """Return every interpretation, including ambiguous Phoenix full houses/runs.

    A Phoenix singleton is valued at 1.5 here; legal_plays contextualizes it.
    Invalid/duplicate selections produce no interpretations.
    """
    cards = tuple(sorted(cards))
    if not cards or len(set(cards)) != len(cards):
        return ()
    n = len(cards)
    ranks = [c.rank for c in cards]
    if n == 1:
        rank = 1.5 if ranks[0] == PHOENIX else ranks[0]
        return (Combination(cards, 'dog' if rank == DOG else 'single', rank),)
    if DOG in ranks or DRAGON in ranks:
        return ()
    wild = PHOENIX in ranks
    counts = Counter(r for r in ranks if r != PHOENIX)
    values = sorted(counts)
    result = []

    def add(kind, rank, substitute=None):
        result.append(Combination(cards, kind, rank, substitute))

    if min(values) >= 2:
        if n in (2, 3) and len(values) == 1:
            add('pair' if n == 2 else 'triple', values[0], values[0] if wild else None)
        if n == 4 and not wild and len(values) == 1:
            add('four_bomb', values[0])
        if n == 5 and len(values) == 2:
            for triple in values:
                pair = next(v for v in values if v != triple)
                missing = {triple: 3 - counts[triple], pair: 2 - counts[pair]}
                if all(v >= 0 for v in missing.values()) and sum(missing.values()) == int(wild):
                    add('full_house', triple,
                        next((r for r, v in missing.items() if v), None))
        if n >= 4 and n % 2 == 0 and values == list(range(values[0], values[-1] + 1)):
            missing = [r for r in values if counts[r] == 1]
            if all(v <= 2 for v in counts.values()) and len(missing) == int(wild):
                add('pairs', values[-1], missing[0] if wild else None)
    if n >= 5 and len(values) == n - int(wild):
        for low in range(1, 16 - n):
            target = set(range(low, low + n))
            missing = target - set(values)
            if set(values) <= target and len(missing) == int(wild):
                if wild and min(missing) == MAHJONG:
                    continue  # Phoenix never substitutes for a special card.
                flush = not wild and len({c.suit for c in cards}) == 1
                add('straight_bomb' if flush else 'straight', low + n - 1,
                    next(iter(missing)) if wild else None)
    return tuple(result)


def reference_combinations(hand):
    """Slow exhaustive oracle retained for differential testing."""
    hand = tuple(sorted(hand))
    return tuple(combo for size in range(1, len(hand) + 1)
                 for subset in combinations(hand, size) for combo in classify(subset))


@lru_cache(maxsize=2048)
def _hand_combinations(hand):
    """Generate rank patterns, retaining every suit choice and wild interpretation."""
    groups = {rank: tuple(c for c in hand if c.rank == rank) for rank in range(1, 15)}
    phoenix = tuple(c for c in hand if c.rank == PHOENIX)
    candidates = {(c,) for c in hand}

    def choices(rank, count):
        ordinary = list(combinations(groups[rank], count))
        if phoenix and rank >= 2:
            ordinary += [cs + phoenix for cs in combinations(groups[rank], count - 1)]
        return ordinary

    def add_products(options):
        if not all(options):
            return
        for parts in product(*options):
            selection = tuple(sorted(c for part in parts for c in part))
            if len(set(selection)) == len(selection):
                candidates.add(selection)

    for rank in range(2, 15):
        for count in (2, 3):
            candidates.update(tuple(sorted(cs)) for cs in choices(rank, count))
        if len(groups[rank]) == 4:
            candidates.add(groups[rank])
        for pair in range(2, 15):
            if pair != rank:
                add_products([choices(rank, 3), choices(pair, 2)])
    for count, minimum, start in ((1, 5, 1), (2, 2, 2)):
        for low in range(start, 15):
            for length in range(minimum, min(15 - low, len(hand) // count) + 1):
                options = [choices(rank, count) for rank in range(low, low + length)]
                add_products(options)
    return tuple(combo for selection in sorted(candidates, key=lambda cs: (len(cs), cs))
                 for combo in classify(selection))


def legal_plays(hand, top=None):
    """All card selections and interpretations that beat top; no turn/wish policy."""
    result = []
    for combo in _hand_combinations(tuple(sorted(hand))):
        if len(combo.cards) == 1 and combo.cards[0].rank == PHOENIX:
            if top is not None:
                if top.kind != 'single' or top.rank >= DRAGON:
                    continue
                combo = replace(combo, rank=top.rank + 0.5)
        if combo.beats(top):
            result.append(combo)
    return tuple(result)
