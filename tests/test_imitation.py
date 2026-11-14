from dataclasses import replace
import json
import random
from pathlib import Path
import tempfile
import unittest

from tichu.agents import load_agent, observe
from tichu.cards import Card
from tichu.imitation import FEATURES, choose, encode_record, features
from tichu.scoring import ScoringAgent, initial_spec, read_spec
from tests.test_external import request
from tests.test_game import scenario
from tests.test_combinations import combo


class ImitationTests(unittest.TestCase):
    def test_features_are_finite_and_inference_selects_legal_action(self):
        obs = observe(scenario((2, 3, 4, 15), (5, 6), (7, 8), (9, 10)), 0)
        weights = [random.Random(i).uniform(-2, 2) for i in range(len(FEATURES))]
        action = choose(obs, weights)
        self.assertIn(action, obs.plays)
        for play in obs.plays:
            self.assertEqual(len(features(obs, play)), len(FEATURES))
        self.assertEqual(action, choose(obs, weights))

    def test_teacher_encoding_uses_exact_legal_label(self):
        req = request([Card(0, r) for r in (2, 3, 4)])
        record = {'pair': 7, 'request': req, 'label': 1}
        rows, target, group = encode_record(record)
        self.assertEqual(group, 7)
        self.assertTrue(0 <= target < len(rows))
        bad = dict(record, label=99)
        with self.assertRaises(IndexError):
            encode_record(bad)

    def test_learned_checkpoint_roundtrip_and_schema_validation(self):
        spec = initial_spec()
        spec.update(move_features=list(FEATURES), move_weights=[0.0]*len(FEATURES))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'weights.json'
            path.write_text(json.dumps(spec))
            self.assertEqual(read_spec(path)['move_weights'], spec['move_weights'])
            self.assertIsInstance(load_agent('scoring', path), ScoringAgent)
            spec['move_features'][0] = 'unknown'
            path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError):
                read_spec(path)
        for weights in ([1.0], [float('nan')]*len(FEATURES)):
            with self.assertRaises(ValueError):
                ScoringAgent(move_weights=weights)

    def test_pass_requires_permission(self):
        obs = observe(scenario((2, 3), (4,), (5,), (6,)), 0)
        with self.assertRaises(ValueError):
            features(obs, None)
        obs = replace(obs, top=combo(14), trick_winner=1, can_pass=True, plays=())
        self.assertIsNone(choose(obs, [0.0]*len(FEATURES)))

    def test_blending_preserves_baseline_at_zero_and_handles_equal_scores(self):
        obs = observe(scenario((2, 3, 4), (5,), (6,), (7,)), 0)
        baseline = list(range(len(obs.plays)))
        self.assertEqual(choose(obs, [0.0]*len(FEATURES), baseline, 0), obs.plays[-1])
        self.assertIn(choose(obs, [0.0]*len(FEATURES), [0.0]*len(obs.plays), .5), obs.plays)
        with self.assertRaises(ValueError):
            ScoringAgent(move_blend=1.01)


if __name__ == '__main__':
    unittest.main()
