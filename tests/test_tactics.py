import copy
from dataclasses import replace, FrozenInstanceError
import random
from pathlib import Path
import tempfile
import unittest

from tichu.agents import observe, Decision, apply_decision, current_actor, load_agent
from tichu.cards import Card
from tichu.combinations import legal_plays
from tichu.game import PublicAction, Round
from tichu.tactics import (ALL_CARDS, Counterplay, TacticalAgent, TacticalWeights,
                          can_beat_from_pool, forced_finish, possible_cards, proven_voids,
                          load_spec, save_spec)
from tichu.selfplay import paired_trial, agent_spec
from tests.test_combinations import cards, combo
from tests.test_game import scenario, decline


class CounterplayTests(unittest.TestCase):
    def test_pool_bounds_match_exact_generator(self):
        rng = random.Random(819)
        deck = sorted(ALL_CARDS)
        tops = [combo(*ranks) for ranks in [(2,), (14,), (16,), (15,), (4, 4),
                (5, 5, 5), (3, 3, 4, 4), (4, 4, 4, 2, 2),
                (3, 4, 5, 6, 7), (6, 6, 6, 6)]]
        tops += list(legal_plays(tuple(Card(0, r) for r in range(2, 9))))
        # Exact small hands plus deliberately structured/wild-heavy pools.
        pools = [tuple(sorted(rng.sample(deck, rng.randint(1, 14)))) for _ in range(160)]
        pools += [tuple(cards(*r)) for r in [(15, 7, 7, 8, 8), (15, 5, 6, 7, 8),
                  (15, 8, 8, 8, 9), (14, 14, 14, 14), (1, 2, 3, 4, 15)]]
        for pool in pools:
            for top in tops:
                plays = legal_plays(pool, top)
                with self.subTest(pool=pool, top=top):
                    self.assertEqual(can_beat_from_pool(pool, top, len(pool)), bool(plays))
                    self.assertEqual(can_beat_from_pool(pool, top, len(pool), len(pool)),
                                     any(len(p.cards) == len(pool) for p in plays))
                    for limit in (1, 3, 4, 5):
                        self.assertEqual(can_beat_from_pool(pool, top, limit),
                                         any(len(p.cards) <= limit for p in plays))

    def test_only_compulsory_wish_failure_proves_absence(self):
        event = PublicAction(1, 'pass', None, combo(3), 0, 8)
        self.assertEqual(proven_voids([event])[1], {8})
        for changed in [replace(event, wish=None), replace(event, previous_top=combo(9)),
                        replace(event, previous_top=combo(3, 3)), replace(event, kind='bomb'),
                        replace(event, kind='play', combo=combo(8))]:
            self.assertFalse(proven_voids([changed])[1])
        self.assertEqual(proven_voids([replace(event, kind='play', previous_top=None,
                                             combo=combo(2))])[1], {8})

    def test_pool_respects_known_gifts_and_wish_history(self):
        obs = observe(scenario((2, 3), (4,), (5,), (6,)), 0)
        gift = Card(1, 14)
        obs = replace(obs, sent=((1, gift),), history=(PublicAction(3, 'pass', None, combo(2), 0, 13),))
        self.assertIn(gift, possible_cards(obs, 1))
        self.assertNotIn(gift, possible_cards(obs, 2))
        self.assertFalse(any(c.rank == 13 for c in possible_cards(obs, 3)))
        self.assertTrue(any(c.rank == 13 for c in possible_cards(obs, 3, use_history=False)))

    def test_history_is_public_immutable_and_failed_actions_atomic(self):
        game = scenario((2, 3), (4,), (5,), (6,))
        with self.assertRaises(ValueError):
            apply_decision(game, 0, Decision('play', play=combo(14), call=True))
        self.assertEqual(game.public_history, [])
        game.play(0, combo(2)); decline(game)
        obs = observe(game, 1)
        self.assertEqual(obs.history[0].combo, combo(2))
        self.assertIsNone(obs.history[0].previous_top)
        with self.assertRaises(FrozenInstanceError):
            obs.history[0].seat = 3
        altered = copy.deepcopy(game)
        altered.players[2].hand, altered.players[3].hand = altered.players[3].hand, altered.players[2].hand
        self.assertEqual(obs, observe(altered, 1))
        self.assertEqual(TacticalAgent().choose(obs), TacticalAgent().choose(observe(altered, 1)))

    def test_dragon_finish_is_proven_only_without_possible_bombs(self):
        obs = observe(scenario((16, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11)), 0)
        self.assertEqual(forced_finish(obs, Counterplay(obs)), combo(16))
        self.assertIsNone(forced_finish(replace(obs, counts=(2, 4, 3, 3)),
                                       Counterplay(replace(obs, counts=(2, 4, 3, 3)))))
        decision = TacticalAgent().choose(obs)
        self.assertEqual(decision.play, combo(16))
        self.assertTrue(decision.call)
        # The proof must cover partner intervention as well as enemies.
        obs = replace(obs, counts=(2, 3, 4, 3))
        self.assertIsNone(forced_finish(obs, Counterplay(obs)))

    def test_dog_and_phoenix_are_not_guaranteed_lead_retainers(self):
        for special in (0, 15):
            obs = observe(scenario((special, 2), (3,), (4,), (5,)), 0)
            self.assertFalse(Counterplay(obs).secure(combo(special)))

    def test_proof_respects_future_wish(self):
        obs = observe(scenario((16, 2, 3), (4,), (5,), (6,)), 0)
        # All other cards have been seen; 3 is secure but the outstanding 2
        # wish forces leading 2 first after the Dragon, breaking the sequence.
        unseen = {Card(s, 3) for s in (1, 2, 3)}
        obs = replace(obs, public_cards=tuple(sorted(ALL_CARDS - set(obs.hand) - unseen)),
                      plays=(combo(16),))
        self.assertEqual(forced_finish(obs, Counterplay(obs)), combo(16))
        self.assertIsNone(forced_finish(replace(obs, wish=2), Counterplay(obs)))

    def test_tactical_games_terminate_and_weights_validate(self):
        for seed in (31, 32):
            pair = paired_trial((seed, agent_spec('tactical'), agent_spec('trained'), 'round', 1000))
            self.assertEqual(len(pair['games']), 2)
        for value in (-1, float('nan'), True):
            with self.assertRaises(ValueError):
                TacticalWeights(threat=value)

    def test_real_hidden_hands_stay_inside_bounds_and_disabled_tactics_match_v1(self):
        frozen = load_agent('trained')
        disabled = TacticalAgent(frozen.weights, TacticalWeights(0, 0, 0), proofs=False)
        for seed in (813, 918):
            game = Round(rng=random.Random(seed))
            for _ in range(5000):
                if game.phase == 'over':
                    break
                seat = current_actor(game)
                obs = observe(game, seat)
                if game.phase in ('playing', 'bomb_window'):
                    counter = Counterplay(obs)
                    for other in counter.pools:
                        self.assertTrue(set(game.players[other].hand) <= set(counter.pools[other]))
                decision = frozen.choose(obs)
                self.assertEqual(disabled.choose(obs), decision)
                apply_decision(game, seat, decision)
            self.assertEqual(game.phase, 'over')

    def test_checkpoint_roundtrip(self):
        spec = agent_spec('tactical')
        spec['tactics'] = {'secure': 2, 'threat': 4, 'points': .1}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'policy.json'
            save_spec(path, spec, training_seed=71)
            loaded = load_spec(path)
            self.assertEqual(loaded['weights'], spec['weights'])
            self.assertEqual(loaded['tactics'], spec['tactics'])
            policy = load_agent('competitive', path)
            self.assertIsInstance(policy, TacticalAgent)
            self.assertEqual(policy.tactics, TacticalWeights(**spec['tactics']))
            path.write_text('{"schema_version": 2, "policy": "tactical"}')
            with self.assertRaises(ValueError):
                load_spec(path)
            path.write_text('{"schema_version": 1, "policy": "tactical"}')
            with self.assertRaises(ValueError):
                load_spec(path)


if __name__ == '__main__':
    unittest.main()
