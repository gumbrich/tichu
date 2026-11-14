from dataclasses import replace
import random
import unittest

from tichu.agents import observe, hand_plan
from tichu.game import Match, Round
from tichu.partnership import PartnershipAgent, PartnershipWeights, from_spec
from tichu.scoring import read_spec
from tests.test_game import scenario
from tests.test_combinations import combo


def agent(**options):
    return from_spec({**read_spec(), 'partnership': options})


class PartnershipTests(unittest.TestCase):
    def test_disabled_extensions_preserve_frozen_choices(self):
        from tichu.agents import load_agent, agent_step, current_actor
        old, new = load_agent('scoring'), agent()
        game = Round(rng=random.Random(809))
        for _ in range(600):
            if game.phase == 'over':
                break
            obs = observe(game, current_actor(game))
            self.assertEqual(old.choose(obs), new.choose(obs))
            agent_step(game, old)
        self.assertEqual(game.phase, 'over')

    def test_dog_and_best_card_help_declared_partner(self):
        game = scenario((0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16), (2,), (3,), (4,))
        obs = replace(observe(game, 0), phase='exchange')
        bot = agent(exchange='team', parity=True)
        for calls, expected in [((200, 0, 0, 0), 0), ((0, 0, 200, 0), 16)]:
            gifts = dict(bot.choose(replace(obs, calls=calls)).gifts)
            self.assertEqual(gifts[2].rank, expected)
            self.assertEqual(set(gifts), {1, 2, 3})
            self.assertEqual(len(set(gifts.values())), 3)
            self.assertTrue(set(gifts.values()) <= set(obs.hand))
            self.assertFalse(any(gifts[s].rank in (0, 1, 14, 15, 16) for s in (1, 3)))
            if calls[2]:
                self.assertNotIn(next(c for c in obs.hand if c.rank == 0), gifts.values())

    def test_disabled_wish_extension_preserves_proven_plan(self):
        from tichu.agents import load_agent
        from tichu.cards import Card
        obs = observe(scenario((1, 2, 3, 4, 5, 14), (6, 7), (8, 9), (10, 11)), 0)
        obs = replace(obs, sent=((1, Card(0, 7)),))
        old = load_agent('scoring').choose(obs)
        self.assertEqual(old.play.kind, 'straight')
        self.assertIsNone(old.wish)
        self.assertEqual(agent().choose(obs), old)

    def test_randomness_is_local_reproducible_and_bounded(self):
        obs = observe(scenario((2, 5, 9, 13, 14), (3, 6), (4, 7), (8, 10)), 0)
        bot = agent(temperature=.1, max_gap=.25)
        a = bot.choose(obs)
        bot.choose(replace(obs, seat=2))
        self.assertEqual(a, bot.choose(obs))
        self.assertIn(a.play, obs.plays)
        from tichu.imitation import score_choices
        from tichu.tactics import TacticalAgent
        plan = hand_plan(obs.hand)
        baseline = [TacticalAgent._play_score(bot, obs, plan, p) for p in obs.plays]
        choices, scores = score_choices(obs, bot.move_weights, baseline, bot.move_blend)
        selected = bot._select_play(obs, plan)
        self.assertLessEqual(max(scores)-scores[choices.index(selected)], .25)

    def test_high_temperature_never_overrides_whole_hand_finish(self):
        obs = observe(scenario((14,), (3, 6), (4, 7), (8, 10)), 0)
        self.assertEqual(agent(temperature=100, max_gap=100).choose(obs).play, combo(14))

    def test_delayed_call_does_not_declare_while_passing(self):
        from unittest.mock import patch
        from tichu.agents import Decision
        with patch('tichu.scoring.ScoringAgent.choose', return_value=Decision('pass', call=True)):
            obs = observe(scenario((2,), (3,), (4,), (5,)), 0)
            self.assertFalse(agent(wait_small=True).choose(obs).call)
            self.assertTrue(agent().choose(obs).call)

    def test_declaration_projects_the_changed_play_objective(self):
        from unittest.mock import patch
        from tichu.agents import Decision
        obs = observe(scenario((2,), (3,), (4,), (5,)), 0)
        def choose_after_call(view):
            return Decision('pass') if view.calls[view.seat] else Decision('play', play=combo(2), call=True)
        with patch('tichu.scoring.ScoringAgent.choose', side_effect=choose_after_call):
            result = agent(wait_small=True).choose(obs)
            self.assertEqual(result, Decision('pass'))
        def choose_consistent_play(view):
            return Decision('play', play=combo(2), call=not view.calls[view.seat])
        with patch('tichu.scoring.ScoringAgent.choose', side_effect=choose_consistent_play):
            result = agent(wait_small=True).choose(obs)
            self.assertTrue(result.call)
            self.assertEqual(result.play, combo(2))

    def test_match_risk_uses_only_public_score_and_target(self):
        game = Match(target=500, seed=91)
        obs = observe(game.round, 0)
        self.assertEqual(obs.target, 500)
        bot = agent(risk=.4)
        self.assertEqual(bot._risk(obs), 0)
        self.assertGreater(bot._risk(replace(obs, match_scores=(0, 490))), 0)
        self.assertLess(bot._risk(replace(obs, match_scores=(490, 0))), 0)

    def test_public_score_context_advances_with_match(self):
        game = Match(target=500, seed=91)
        game.round.phase, game.round.scores = 'over', [120, -20]
        game.next_round()
        obs = observe(game.round, 1)
        self.assertEqual(obs.match_scores, (120, -20))
        self.assertEqual(obs.target, 500)
        from tichu.external import observation
        from tests.test_external import request
        wire = request(list(obs.hand))
        wire['view']['scores'] = [120, -20]
        wire['view']['settings']['target_score'] = 500
        converted = observation(wire)
        self.assertEqual(converted.match_scores, obs.match_scores)
        self.assertEqual(converted.target, obs.target)

    def test_bad_options_rejected(self):
        for options in ({'temperature': float('nan')}, {'risk': -1}, {'exchange': 'magic'},
                        {'parity': 1}, {'seed': True}):
            with self.assertRaises(ValueError):
                PartnershipWeights(**options)
