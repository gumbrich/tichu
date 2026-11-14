from dataclasses import replace
import itertools
import random
import unittest

from tichu.agents import Decision, apply_decision, load_agent, observe
from tichu.cards import Card
from tichu.combinations import legal_plays
from tichu.game import Round
from tichu.scoring import ControlEstimate, ScoringAgent, ScoringWeights, at_least, grand_strength
from tichu.selfplay import agent_spec, paired_trial
from tests.test_game import scenario
from tests.test_combinations import combo


class ScoringTests(unittest.TestCase):
    def test_hypergeometric_matches_exhaustive_small_pools(self):
        for n in range(1, 8):
            for good in range(n+1):
                for draws in range(n+1):
                    hands = list(itertools.combinations(range(n), draws))
                    for needed in range(4):
                        expected = sum(sum(c < good for c in h) >= needed for h in hands)/len(hands)
                        self.assertAlmostEqual(at_least(n, good, draws, needed), expected)

    def test_grand_action_does_not_call_small_first(self):
        game = Round(rng=random.Random(93))
        self.assertEqual(len(game.players[0].hand), 8)
        apply_decision(game, 0, Decision('grand', call=True))
        self.assertEqual(game.players[0].call, 200)
        self.assertEqual(len(game.players[0].hand), 14)
        apply_decision(game, 1, Decision('grand'))
        self.assertEqual(game.players[1].call, 0)

    def test_strong_finishing_phoenix_reading(self):
        game = scenario((7, 7, 8, 8, 15), (2, 3), (4, 5), (6, 9))
        obs = observe(game, 0)
        decision = ScoringAgent().choose(obs)
        self.assertEqual(decision.play.kind, 'full_house')
        self.assertEqual(decision.play.rank, 8)
        self.assertEqual(len(decision.play.cards), 5)

    def test_protect_partner_call_but_not_illegal_pass(self):
        game = scenario((14,), (2, 3, 4), (5, 6), (7, 8, 9))
        obs = replace(observe(game, 0), top=combo(10), trick_winner=2,
                      plays=(combo(14),), can_pass=True, calls=(0, 0, 200, 0))
        self.assertEqual(ScoringAgent().choose(obs).kind, 'pass')
        self.assertEqual(ScoringAgent().choose(replace(obs, can_pass=False)).kind, 'play')
        self.assertEqual(ScoringAgent().choose(replace(obs, finish_order=(2,))).kind, 'play')

    def test_imminent_enemy_finish_overrides_partner_wait(self):
        obs = observe(scenario((14,), (2,), (5, 6), (7, 8, 9)), 0)
        obs = replace(obs, top=combo(10), trick_winner=2, plays=(combo(14),),
                      can_pass=True, calls=(0, 0, 100, 0))
        self.assertEqual(ScoringAgent().choose(obs).kind, 'play')

    def test_native_bomb_decline_can_protect_partner(self):
        obs = observe(scenario((3, 3, 3, 3), (2, 4, 5, 6, 7), (8, 9), (10, 11, 12, 13, 14)), 0)
        obs = replace(obs, phase='bomb_window', top=combo(14), trick_winner=2,
                      plays=tuple(p for p in obs.plays if p.is_bomb),
                      can_pass=False, calls=(0, 0, 100, 0))
        self.assertEqual(ScoringAgent().choose(obs).kind, 'decline')

    def test_dragon_is_not_rewarded_for_getting_bombed(self):
        obs = observe(scenario((16, 2), (3, 4, 5, 6), (7, 8), (9, 10, 11, 12)), 0)
        bot = ScoringAgent()
        bot.control = ControlEstimate(obs)
        self.assertEqual(bot._point_value(obs, combo(16), 0), -1)
        self.assertEqual(bot._point_value(obs, combo(16), 1), 1)

    def test_dragon_gift_sign_and_possible_last_player(self):
        obs = replace(observe(scenario((2,), (3,), (4, 5), (6, 7, 8)), 0),
                      phase='dragon', pile_points=30)
        self.assertEqual(ScoringAgent().choose(obs).recipient, 3)
        self.assertEqual(ScoringAgent().choose(replace(obs, pile_points=-5)).recipient, 1)

    def test_known_gift_and_empty_hand_control(self):
        obs = observe(scenario((2, 3), (4,), (5,), (6,)), 0)
        obs = replace(obs, sent=((1, Card(4, 16)),))
        control = ControlEstimate(obs)
        self.assertEqual(control.answer(1, combo(14)), 1)
        self.assertEqual(ControlEstimate(replace(obs, counts=(2, 0, 1, 1), sent=())).answer(1, combo(14)), 0)
        self.assertEqual(control.answer(1, combo(16)), 0)

    def test_unknown_cards_do_not_enter_grand_decision(self):
        game = Round(rng=random.Random(4))
        obs = observe(game, 0)
        old = ScoringAgent().choose(obs)
        game.players[1].hand, game.players[2].hand = game.players[2].hand, game.players[1].hand
        self.assertEqual(obs, observe(game, 0))
        self.assertEqual(old, ScoringAgent().choose(observe(game, 0)))

    def test_grand_prefers_control_cards(self):
        weak = tuple(Card(0, r) for r in range(2, 10))
        strong = (Card(4, 16), Card(4, 15), Card(0, 14), Card(1, 14),
                  Card(0, 13), Card(1, 13), Card(0, 12), Card(1, 12))
        self.assertLess(grand_strength(weak), 3.6)
        self.assertGreater(grand_strength(strong), 3.6)

    def test_invalid_weights_rejected(self):
        for value in (-1, float('nan'), True):
            with self.assertRaises(ValueError):
                ScoringWeights(points=value)
        with self.assertRaises(ValueError):
            ScoringWeights(partner_finish=1)

    def test_native_rounds_with_grand_are_legal_and_deterministic(self):
        candidate = agent_spec('scoring')
        candidate['scoring']['grand_threshold'] = 0
        task = (16000011, candidate, agent_spec('competitive'), 'round', 1000)
        a, b = paired_trial(task), paired_trial(task)
        for result in (a, b):
            for game in result['games']:
                del game['decision_seconds']
        self.assertEqual(a, b)
        self.assertGreaterEqual(sum(g['calls'] for g in a['games']), 2)


if __name__ == '__main__':
    unittest.main()
