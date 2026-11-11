import copy
from dataclasses import FrozenInstanceError, replace
import random
from pathlib import Path
import tempfile
import unittest

from tichu.agents import (BaselineAgent, StrategicAgent, Weights, Observation,
                          Decision, apply_decision, observe, agent_step,
                          current_actor, hand_plan, load_agent)
from tichu.cards import Card, Deck
from tichu.combinations import reference_combinations, legal_plays
from tichu.game import Round
from tichu.selfplay import paired_trial, summarize
from tests.test_game import scenario, decline
from tests.test_combinations import cards, combo


class ObservationTests(unittest.TestCase):
    def test_failed_combined_declaration_and_play_is_atomic(self):
        game = scenario((2, 3), (4,), (5,), (6,))
        before = copy.deepcopy(game.players)
        with self.assertRaises(ValueError):
            apply_decision(game, 0, Decision('play', play=combo(14), call=True))
        self.assertEqual(game.players, before)
        self.assertFalse(game.events)

    def test_hidden_cards_and_deck_cannot_change_observation_or_decision(self):
        game = Round(rng=random.Random(4))
        for seat in range(4):
            game.decide_grand(seat)
        before = observe(game, 0)
        altered = copy.deepcopy(game)
        altered.players[1].hand, altered.players[2].hand = altered.players[2].hand, altered.players[1].hand
        altered.deck.cards.reverse()
        # Another player's committed exchange must remain hidden.
        altered.exchanges[1] = dict(zip((0, 2, 3), altered.players[1].hand[:3]))
        after = observe(altered, 0)
        self.assertEqual(before, after)
        policy = StrategicAgent()
        self.assertEqual(policy.choose(before), policy.choose(after))
        self.assertNotIn('players', before.__dataclass_fields__)
        self.assertNotIn('deck', before.__dataclass_fields__)
        with self.assertRaises(FrozenInstanceError):
            before.seat = 2

    def test_both_policies_complete_valid_games(self):
        for seed in range(4):
            game = Round(rng=random.Random(seed))
            agents = [BaselineAgent(), StrategicAgent()]
            for _ in range(5000):
                if game.phase == 'over':
                    break
                agent_step(game, agents[current_actor(game) % 2])
            self.assertEqual(game.phase, 'over')


class StrategicTests(unittest.TestCase):
    def test_policy_roundtrip_and_invalid_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'policy.json'
            weights = Weights(partner=22.5, call_threshold=-.5)
            weights.save(path, training_seed=99)
            self.assertEqual(Weights.load(path), weights)
            self.assertEqual(load_agent('trained', path).weights, weights)
            path.write_text('{"schema_version":99,"weights":{}}')
            with self.assertRaises(ValueError):
                Weights.load(path)
        with self.assertRaises(ValueError):
            Weights(groups=float('nan'))
        with self.assertRaises(ValueError):
            Weights(partner=-1)

    def test_partition_preserves_full_house_and_run(self):
        hand = tuple(cards(2, 2, 2, 3, 3, 5, 6, 7, 8, 9))
        plan = hand_plan(hand)
        self.assertEqual(plan.partition(plan.full), (2, 0))
        # A subset query must not use cards already spent in a different play.
        remainder = plan.full ^ plan.mask(cards(2, 2, 2))
        self.assertEqual(plan.partition(remainder), (2, 0))

    def test_partner_is_not_unnecessarily_overtaken(self):
        game = scenario((14, 2, 3), (4, 5, 6, 7, 8), (13, 7, 8), (8, 9, 10, 11, 12), turn=2)
        game.play(2, combo(13)); decline(game)
        game.pass_turn(3); decline(game)
        self.assertEqual(game.turn, 0)
        self.assertEqual(StrategicAgent().choose(observe(game, 0)).kind, 'pass')
        self.assertEqual(BaselineAgent().choose(observe(game, 0)).kind, 'play')

    def test_finish_takes_priority_over_partner_support(self):
        game = scenario((14,), (5, 6), (13, 7, 8), (9, 10), turn=2)
        game.play(2, combo(13)); decline(game)
        game.pass_turn(3); decline(game)
        decision = StrategicAgent().choose(observe(game, 0))
        self.assertEqual(decision.play, combo(14))
        self.assertTrue(decision.call)

    def test_forced_wish_cannot_be_ignored_to_support_partner(self):
        game = scenario((14, 2, 3), (5, 6), (13, 7, 8), (9, 10), turn=2)
        game.play(2, combo(13)); decline(game)
        game.pass_turn(3); decline(game)
        game.wish = 14
        self.assertEqual(StrategicAgent().choose(observe(game, 0)).play, combo(14))

    def test_exchange_gives_distinct_owned_cards_to_all_other_seats(self):
        game = Round(rng=random.Random(11))
        for seat in range(4):
            game.decide_grand(seat)
        decision = StrategicAgent().choose(observe(game, 0))
        self.assertEqual({s for s, c in decision.gifts}, {1, 2, 3})
        self.assertEqual(len({c for s, c in decision.gifts}), 3)
        self.assertTrue(all(c in game.players[0].hand for s, c in decision.gifts))


class TournamentTests(unittest.TestCase):
    def test_identical_policies_cancel_when_sides_swap(self):
        spec = {'name': 'baseline'}
        pair = paired_trial((102, spec, spec, 'round', 1000))
        self.assertEqual(sum(g['score_difference'] for g in pair['games']), 0)
        summary = summarize([pair])
        self.assertEqual(summary['win_rate'], .5)
        self.assertIsNone(summary['score_difference_95ci'])

    def test_seed_and_agent_parameters_reproduce_scores(self):
        task = (512, {'name': 'strategic'}, {'name': 'baseline'}, 'round', 1000)
        results = [paired_trial(task), paired_trial(task)]
        self.assertEqual([g['score_difference'] for g in results[0]['games']],
                         [g['score_difference'] for g in results[1]['games']])


if __name__ == '__main__':
    unittest.main()
