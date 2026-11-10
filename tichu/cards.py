"""Cards retain the original project's suit and rank numbering."""
from dataclasses import dataclass
import random

DOG, MAHJONG, PHOENIX, DRAGON = 0, 1, 15, 16


@dataclass(frozen=True, order=True)
class Card:
    suit: int
    rank: int

    suits = ('Red', 'Black', 'Blue', 'Green', 'Special')
    ranks = ('Dog', 'Mah Jong', '2', '3', '4', '5', '6', '7', '8', '9',
             '10', 'J', 'Q', 'K', 'A', 'Phoenix', 'Dragon')

    def __post_init__(self):
        if not ((0 <= self.suit < 4 and 2 <= self.rank <= 14) or
                (self.suit == 4 and self.rank in (DOG, MAHJONG, PHOENIX, DRAGON))):
            raise ValueError('Invalid card')

    @property
    def points(self):
        return {5: 5, 10: 10, 13: 10, PHOENIX: -25, DRAGON: 25}.get(self.rank, 0)

    def __str__(self):
        return (f'{self.suits[self.suit]} {self.ranks[self.rank]}'
                if self.suit < 4 else self.ranks[self.rank])

    def show(self):
        print(self)


class Deck:
    def __init__(self, rng=None):
        self.cards = [Card(s, r) for s in range(4) for r in range(2, 15)]
        self.cards += [Card(4, r) for r in (DOG, MAHJONG, PHOENIX, DRAGON)]
        self.rng = rng if rng is not None else random.Random()
        self.shuffle()

    def shuffle(self):
        self.rng.shuffle(self.cards)

    def draw(self):
        return self.cards.pop()
