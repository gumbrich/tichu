import copy
import random
import unittest

from tichu.cards import Card
from tichu.game import Match, Round, RuleError
from tests.test_combinations import cards, combo


def scenario(*hands, turn=0):
    game = Round(rng=random.Random(0))
    for p, hand in zip(game.players, hands):
        p.hand = cards(*hand)
    game.phase = 'playing'
    game.turn = turn
    return game


def decline(game):
    while game.phase == 'bomb_window':
        game.decline_bomb(game.actor)


def pass_all(game):
    decline(game)
    while game.phase == 'playing' and game.top:
        game.pass_turn(game.turn)
        decline(game)


class SetupTests(unittest.TestCase):
    def test_staged_deal_exchange_and_lead(self):
        game = Round(rng=random.Random(1))
        self.assertEqual([len(p.hand) for p in game.players], [8] * 4)
        game.decide_grand(0, True)
        with self.assertRaises(RuleError):
            game.decide_grand(0, True)
        for seat in (1, 2, 3):
            game.decide_grand(seat)
        self.assertEqual(game.phase, 'exchange')
        original = [p.hand[:] for p in game.players]
        gifts = []
        for seat in range(4):
            recipients = sorted(set(range(4)) - {seat})
            gift = dict(zip(recipients, original[seat][:3]))
            gifts.append(gift)
            game.exchange(seat, gift)
            if seat < 3:
                self.assertEqual([p.hand for p in game.players], original)
        self.assertEqual(game.phase, 'playing')
        self.assertIn(Card(4, 1), game.players[game.turn].hand)
        for seat, p in enumerate(game.players):
            self.assertEqual(len(p.hand), 14)
            self.assertEqual(set(p.hand), set(original[seat][3:] +
                             [gifts[s][seat] for s in range(4) if s != seat]))
        self.assertEqual(len({c for p in game.players for c in p.hand}), 56)

    def test_invalid_exchange_is_atomic(self):
        game = Round()
        for seat in range(4):
            game.decide_grand(seat)
        before = copy.deepcopy(game.__dict__)
        c = game.players[0].hand[0]
        with self.assertRaises(RuleError):
            game.exchange(0, {1: c, 2: c, 3: c})
        self.assertEqual(game.exchanges, before['exchanges'])
        self.assertEqual(game.players, before['players'])

    def test_call_deadlines(self):
        game = scenario((2, 3), (4,), (5,), (6,))
        game.call_tichu(1)
        with self.assertRaises(RuleError):
            game.call_tichu(1)
        game.play(0, combo(2))
        with self.assertRaises(RuleError):
            game.call_tichu(0)
        game.call_tichu(2)  # Out of turn, before own first play is fine.


class TrickTests(unittest.TestCase):
    def test_invalid_play_leaves_state_unchanged(self):
        game = scenario((2, 3), (4,), (5,), (6,))
        before = copy.deepcopy(game.players)
        for seat, selection, wish in [(1, combo(4), None), (0, combo(4), None),
                                      (0, combo(2), 8), (0, combo(2, 2), None)]:
            with self.assertRaises(RuleError):
                game.play(seat, selection, wish)
            self.assertEqual(game.players, before)
            self.assertIsNone(game.top)
        with self.assertRaises(RuleError):
            game.pass_turn(0)

    def test_finished_leader_does_not_skip_another_player(self):
        game = scenario((14,), (2, 3), (4, 5), (6, 7))
        game.play(0, combo(14))
        pass_all(game)
        self.assertEqual(game.finish_order, [0])
        self.assertEqual(game.turn, 1)
        self.assertEqual(game.players[0].stack, cards(14))
        self.assertEqual([len(p.hand) for p in game.players], [0, 2, 2, 2])

    def test_pass_does_not_exclude_player_from_later_response(self):
        game = scenario((2, 14), (3, 13), (4, 12), (5, 11))
        game.play(0, combo(2)); decline(game)
        game.pass_turn(1); decline(game)
        game.play(2, combo(4)); decline(game)
        game.pass_turn(3); decline(game)
        game.pass_turn(0); decline(game)
        self.assertEqual(game.turn, 1)
        game.play(1, combo(13))

    def test_dog_partner_and_finished_partner(self):
        game = scenario((0, 3), (4,), (5,), (6,))
        game.play(0, combo(0))
        self.assertEqual((game.phase, game.turn, game.top), ('playing', 2, None))
        self.assertEqual(game.discarded, cards(0))
        game = scenario((0, 3), (4,), (), (6,))
        game.finish_order = [2]
        game.play(0, combo(0))
        self.assertEqual(game.turn, 3)

    def test_dragon_gift_and_lead(self):
        game = scenario((16, 2), (3,), (4,), (5,))
        game.play(0, combo(16)); pass_all(game)
        self.assertEqual(game.phase, 'dragon')
        with self.assertRaises(RuleError):
            game.give_dragon(0, 2)
        game.give_dragon(0, 3)
        self.assertEqual(game.players[3].stack, cards(16))
        self.assertEqual(game.turn, 0)

    def test_bomb_dragon_out_of_turn_and_own_trick(self):
        game = scenario((16, 2), (3,), (4, 4, 4, 4, 7), (5,))
        game.play(0, combo(16))
        game.decline_bomb(1)
        game.bomb(2, combo(4, 4, 4, 4))
        pass_all(game)
        self.assertEqual(game.phase, 'playing')
        self.assertEqual(sum(c.points for c in game.players[2].stack), 25)
        self.assertEqual(game.turn, 2)
        game = scenario((2, 4, 4, 4, 4, 7), (3,), (5,), (6,))
        game.play(0, combo(2))
        for seat in (1, 2, 3):
            game.decline_bomb(seat)
        game.bomb(0, combo(4, 4, 4, 4))
        self.assertEqual(game.trick_winner, 0)

    def test_bomb_after_final_pass_and_counterbomb_priority(self):
        game = scenario((2, 3), (4, 4, 4, 4, 7), (5, 5, 5, 5, 8), (6, 9))
        game.play(0, combo(2)); decline(game)
        for seat in (1, 2):
            game.pass_turn(seat); decline(game)
        game.pass_turn(3)
        self.assertEqual(game.phase, 'bomb_window')
        game.decline_bomb(0)
        game.bomb(1, combo(4, 4, 4, 4))
        self.assertEqual(game.actor, 2)
        game.bomb(2, combo(5, 5, 5, 5))
        self.assertEqual(game.actor, 3)
        self.assertFalse(game.passed)


class WishTests(unittest.TestCase):
    def test_wish_forces_play_and_persists_across_tricks(self):
        game = scenario((1, 2), (8, 9), (10,), (11,))
        game.play(0, combo(1), wish=8); decline(game)
        self.assertFalse(game.can_pass(1))
        with self.assertRaises(RuleError):
            game.play(1, combo(9))
        game.play(1, combo(8))
        self.assertIsNone(game.wish)
        game = scenario((1, 14), (2, 3), (4, 5), (6, 7))
        game.play(0, combo(1), wish=8); pass_all(game)
        self.assertEqual(game.wish, 8)

    def test_phoenix_must_help_real_wished_card(self):
        game = scenario((3, 3, 7), (8, 15, 9), (10,), (11,))
        game.play(0, combo(3, 3)); decline(game)
        game.wish = 8
        self.assertFalse(game.can_pass(1))
        self.assertEqual(game.available_plays(1), (combo(8, 15),))
        game.wish = 14  # A wildcard pretending to be the wish does not count.
        self.assertTrue(game.can_pass(1))

    def test_interrupt_exempt_but_ordinary_bomb_required(self):
        game = scenario((1, 2), (8, 4, 4, 4, 4, 7), (10,), (11,))
        game.play(0, combo(1), wish=8)
        game.bomb(1, combo(4, 4, 4, 4))
        self.assertEqual(game.wish, 8)
        pass_all(game)
        self.assertEqual(game.available_plays(1), (combo(8),))
        game = scenario((14, 2), (8, 8, 8, 8, 7), (10,), (11,))
        game.play(0, combo(14)); decline(game)
        game.wish = 8
        self.assertFalse(game.can_pass(1))
        self.assertEqual(game.available_plays(1), (combo(8, 8, 8, 8),))


class ScoringTests(unittest.TestCase):
    def test_double_victory_and_individual_calls(self):
        game = scenario((), (2, 3), (14,), (5, 6), turn=2)
        game.finish_order = [0]
        game.players[0].call = 100
        game.players[2].call = 200
        game.players[1].call = 100
        game.play(2, combo(14))
        self.assertEqual(game.scores, (100, -100))  # 200 + 100 - 200, -100
        self.assertEqual(game.phase, 'over')

    def test_last_cards_and_tricks_transfer(self):
        game = scenario((), (), (14,), (5, 16), turn=2)
        game.finish_order = [0, 1]
        game.players[3].stack = cards(10)
        game.players[0].stack = cards(15)
        game.play(2, combo(14))
        self.assertEqual(game.scores, (15, 0))  # Fixture has only 15 card points.
        self.assertEqual(game.last_player, 3)
        self.assertFalse(game.players[3].hand)
        self.assertFalse(game.players[3].stack)
        self.assertEqual(game.phase, 'over')

    def test_final_dragon_must_be_given_before_scoring(self):
        game = scenario((), (), (16,), (5,), turn=2)
        game.finish_order = [0, 1]
        game.play(2, combo(16))
        self.assertEqual(game.phase, 'dragon')
        self.assertIsNone(game.scores)
        # Give to last player: their tricks subsequently go to first finisher.
        game.give_dragon(2, 3)
        self.assertEqual(game.scores, (30, 0))

    def test_match_target_and_tie(self):
        match = Match(target=100)
        match.round.phase = 'over'; match.round.scores = (100, 100)
        match.next_round()
        self.assertIsNone(match.winner)
        self.assertEqual(match.round.number, 2)
        self.assertEqual([len(p.hand) for p in match.round.players], [8] * 4)
        match.round.phase = 'over'; match.round.scores = (-50, 50)
        self.assertIsNone(match.next_round())
        self.assertEqual(match.winner, 1)
        with self.assertRaises(RuleError):
            match.next_round()
        self.assertEqual(match.scores, [50, 150])


if __name__ == '__main__':
    unittest.main()
