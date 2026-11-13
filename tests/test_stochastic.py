import random
import io
from contextlib import redirect_stdout
from dataclasses import replace
import unittest

from tichu.agents import observe, load_agent, apply_decision, current_actor
from tichu.cards import Card
from tichu.game import Round
from tichu.cli import main
from tichu.selfplay import agent_spec, paired_trial, make_agent
from tichu.stochastic import StochasticAgent, sample_play
from tests.test_combinations import combo
from tests.test_game import scenario


class StochasticTests(unittest.TestCase):
    def test_softmax_frequencies_and_gap(self):
        a, b = combo(2), combo(3)
        rng = random.Random(213)
        outcomes = [sample_play([(a, 0.), (b, 1.)], rng, 1.) for _ in range(10000)]
        self.assertAlmostEqual(outcomes.count(b) / len(outcomes), .73106, delta=.02)
        self.assertTrue(all(sample_play([(a, 0.), (b, 1.)], rng, 20., .5) == b for _ in range(100)))
        self.assertEqual(sample_play([(a, -1e300), (b, 1e300)], rng, .01), b)

    def test_intent_multiplicity_does_not_bias_sampling(self):
        a, b = combo(2), combo(3)
        variants = [replace(a, cards=(Card(s, 2),)) for s in range(4)]
        scored = [(v, 0.) for v in variants] + [(b, 0.)]
        rng = random.Random(214)
        outcomes = [sample_play(scored, rng, 0.) for _ in range(10000)]
        self.assertAlmostEqual(outcomes.count(b) / len(outcomes), .5, delta=.02)
        self.assertTrue(all(v in outcomes for v in variants))

    def test_zero_temperature_preserves_v2_every_decision(self):
        frozen = load_agent('competitive')
        stochastic = StochasticAgent(frozen.weights, frozen.tactics, seed=41)
        state = stochastic.rng.getstate()
        game = Round(rng=random.Random(913))
        for _ in range(5000):
            if game.phase == 'over':
                break
            seat = current_actor(game); obs = observe(game, seat)
            expected = frozen.choose(obs)
            self.assertEqual(stochastic.choose(obs), expected)
            apply_decision(game, seat, expected)
        self.assertEqual(game.phase, 'over')
        self.assertEqual(stochastic.rng.getstate(), state)

    def test_immediate_and_proven_finishes_stay_protected_at_high_temperature(self):
        agent = StochasticAgent(temperature=1000, seed=9)
        for hand, expected in [((2,), combo(2)), ((16, 2), combo(16))]:
            obs = observe(scenario(hand, (3,), (4,), (5,)), 0)
            for _ in range(20):
                self.assertEqual(agent.choose(obs).play, expected)

    def test_reproducible_streams_and_identical_stochastic_side_swap(self):
        spec = {**agent_spec('competitive'), 'name': 'stochastic',
                'options': {'temperature': 1.}, 'policy_seed': 88}
        task = (9001, spec, agent_spec('competitive'), 'round', 1000)
        a, b = paired_trial(task), paired_trial(task)
        self.assertEqual([g['score_difference'] for g in a['games']],
                         [g['score_difference'] for g in b['games']])
        same = paired_trial((9002, spec, spec, 'round', 1000))
        self.assertEqual(sum(g['score_difference'] for g in same['games']), 0)
        self.assertNotEqual(make_agent(spec, seed=1).rng.getstate(),
                            make_agent(spec, seed=2).rng.getstate())

    def test_invalid_sampling_parameters(self):
        for value in (-1, float('nan'), float('inf'), True):
            with self.assertRaises(ValueError):
                StochasticAgent(temperature=value)
            with self.assertRaises(ValueError):
                StochasticAgent(max_gap=value)

    def test_terminal_seed_reproduces_sampling_and_default_stays_frozen(self):
        outputs = []
        for _ in range(2):
            output = io.StringIO()
            with redirect_stdout(output):
                main(['--demo', '--seed', '7', '--target', '100',
                      '--temperature', '.5', '--bot-seed', '42'])
            outputs.append(output.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn('Experimental sampling', outputs[0])
        output = io.StringIO()
        with redirect_stdout(output):
            main(['--demo', '--seed', '7', '--target', '100'])
        self.assertIn('Round score: 65 : 35', output.getvalue())
        self.assertIn('Round score: -25 : 125', output.getvalue())


if __name__ == '__main__':
    unittest.main()
