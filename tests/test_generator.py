import random
import unittest

from tichu.cards import Deck
from tichu.combinations import reference_combinations, legal_plays
from tests.test_combinations import cards


class FastGeneratorTests(unittest.TestCase):
    def test_random_full_hands_match_exhaustive_oracle(self):
        rng = random.Random(8031)
        deck = Deck(rng).cards
        for i in range(80):
            hand = rng.sample(deck, 14 if i < 40 else rng.randint(1, 14))
            with self.subTest(i=i):
                self.assertEqual(set(legal_plays(hand)), set(reference_combinations(hand)))

    def test_dense_wildcard_and_suit_cases_match_oracle(self):
        hands = [cards(2, 2, 2, 2, 3, 3, 3, 4, 4, 5, 6, 7, 8, 15),
                 cards(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15),
                 cards(2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 15)]
        for hand in hands:
            self.assertEqual(set(legal_plays(hand)), set(reference_combinations(hand)))


