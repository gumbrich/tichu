"""Opt-in, seeded Boltzmann action selection over the frozen tactical scores.

Temperature is in heuristic score units, not an LLM's calibrated logit scale.
Proofs, immediate finishes, wishes, declarations and exchanges retain their
existing handling. Only ordinary play/pass and optional bombs are sampled.
"""
import math
import random

from .tactics import TacticalAgent


def intent(play):
    """Avoid giving an intent extra probability merely for having more suits."""
    if play is None:
        return ('pass',)
    return (play.kind, len(play.cards), play.rank, play.phoenix_rank)


def sample_play(scored, rng, temperature, max_gap=None):
    """Sample intents by their best concrete score, then uniform best realizations.

    At zero temperature this helper samples exact best-score ties. The policy
    bypasses it when both temperature and random_ties are zero, preserving v2
    byte-for-byte decision behavior. Optional gap filtering uses the global best.
    """
    groups = {}
    for play, score in scored:
        key = intent(play)
        if key not in groups or score > groups[key][0]:
            groups[key] = (score, [play])
        elif score == groups[key][0]:
            groups[key][1].append(play)
    best = max(score for score, plays in groups.values())
    eligible = [(score, plays) for score, plays in groups.values()
                if (max_gap is None or best - score <= max_gap) and
                   (temperature > 0 or score == best)]
    if temperature == 0:
        selected = rng.choice(eligible)
    else:
        weights = [math.exp((score - best) / temperature) for score, _ in eligible]
        selected = rng.choices(eligible, weights=weights, k=1)[0]
    return rng.choice(selected[1])


class StochasticAgent(TacticalAgent):
    def __init__(self, weights=None, tactics=None, *, temperature=0., random_ties=False,
                 max_gap=None, seed=None, **options):
        if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature < 0:
            raise ValueError('temperature must be finite and nonnegative')
        if max_gap is not None and (type(max_gap) not in (int, float) or
                                   not math.isfinite(max_gap) or max_gap < 0):
            raise ValueError('max_gap must be finite and nonnegative')
        super().__init__(weights, tactics, **options)
        self.temperature = temperature
        self.random_ties = random_ties
        self.max_gap = max_gap
        self.rng = random.Random(seed)

    def _select_play(self, obs, plan):
        if self.temperature == 0 and not self.random_ties:
            return super()._select_play(obs, plan)
        scored = [(play, self._play_score(obs, plan, play)) for play in obs.plays]
        if obs.phase == 'bomb_window' or obs.can_pass:
            scored.insert(0, (None, self._pass_score(obs, plan)))
        return sample_play(scored, self.rng, self.temperature, self.max_gap)
