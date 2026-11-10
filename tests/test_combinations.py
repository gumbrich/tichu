import unittest
from tichu.cards import Card, Deck
from tichu.combinations import classify, legal_plays


def cards(*ranks):
    counts = {}
    result = []
    for rank in ranks:
        suit = counts.get(rank, 0)
        result.append(Card(4 if rank in (0, 1, 15, 16) else suit, rank))
        counts[rank] = suit + 1
    return result


def combo(*ranks):
    return classify(cards(*ranks))[0]


class CombinationTests(unittest.TestCase):
    def test_deck_and_points(self):
        deck = Deck()
        self.assertEqual(len(set(deck.cards)), 56)
        self.assertEqual(sum(c.points for c in deck.cards), 100)
        with self.assertRaises(ValueError):
            Card(0, 15)

    def test_ordinary_shapes(self):
        for ranks, kind in [((2,), 'single'), ((2, 2), 'pair'), ((3, 3, 3), 'triple'),
                            ((3, 3, 3, 2, 2), 'full_house'),
                            ((2, 2, 3, 3, 4, 4), 'pairs'),
                            ((1, 2, 3, 4, 5), 'straight')]:
            self.assertEqual(combo(*ranks).kind, kind)
        self.assertFalse(classify(cards(2, 2, 4, 4)))
        self.assertFalse(classify(cards(2, 3, 4, 5)))
        c = Card(0, 2)
        self.assertFalse(classify([c, c]))

    def test_bomb_order_and_equal_lengths(self):
        four = combo(14, 14, 14, 14)
        short = combo(2, 3, 4, 5, 6)
        long = combo(2, 3, 4, 5, 6, 7)
        self.assertTrue(four.beats(combo(16)))
        self.assertTrue(short.beats(four))
        self.assertTrue(long.beats(short))
        self.assertFalse(short.beats(long))
        self.assertFalse(combo(3, 3, 4, 4, 5, 5).beats(combo(2, 2, 3, 3)))
        self.assertFalse(four.beats(combo(0)))
        self.assertFalse(combo(2).beats(combo(2)))

    def test_full_house_triple_controls_comparison(self):
        self.assertTrue(combo(4, 4, 4, 2, 2).beats(combo(3, 3, 3, 14, 14)))
        self.assertFalse(combo(3, 3, 3, 14, 14).beats(combo(3, 3, 3, 2, 2)))

    def test_phoenix_combinations(self):
        self.assertEqual(combo(2, 15).kind, 'pair')
        self.assertEqual(combo(2, 2, 15).kind, 'triple')
        self.assertEqual(combo(2, 2, 3, 15).kind, 'pairs')
        self.assertEqual({c.rank for c in classify(cards(2, 2, 3, 3, 15))}, {2, 3})
        self.assertEqual(combo(2, 2, 2, 3, 15).rank, 2)
        self.assertFalse(classify(cards(2, 2, 2, 2, 15)))
        self.assertFalse(classify(cards(2, 2, 2, 15)))
        self.assertEqual({c.phoenix_rank for c in classify(cards(3, 4, 5, 6, 15))}, {2, 7})
        self.assertEqual(combo(1, 2, 4, 5, 15).phoenix_rank, 3)
        self.assertNotIn(1, {c.phoenix_rank for c in classify(cards(2, 3, 4, 5, 15))})
        self.assertFalse(combo(2, 3, 4, 5, 15).is_bomb)

    def test_single_phoenix_context(self):
        hand = cards(15)
        self.assertEqual(legal_plays(hand)[0].rank, 1.5)
        self.assertEqual(legal_plays(hand, combo(14))[0].rank, 14.5)
        self.assertFalse(legal_plays(hand, combo(16)))
        self.assertFalse(legal_plays(hand, combo(2, 2)))

    def test_specials_and_generator(self):
        for ranks in [(0, 2), (16, 2, 3, 4, 5), (1, 15)]:
            self.assertFalse(classify(cards(*ranks)))
        # Duplicate ranks in a hand must not hide an available straight.
        hand = cards(2, 2, 3, 4, 5, 6)
        self.assertEqual(sum(c.kind in ('straight', 'straight_bomb')
                             for c in legal_plays(hand)), 2)
        self.assertFalse(any(c.kind == 'dog' for c in legal_plays(cards(0), combo(2))))


if __name__ == '__main__':
    unittest.main()
