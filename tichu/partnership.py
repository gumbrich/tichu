"""Experimental partnership policy; all decisions use only the seat's observation.

Parameters live in explicit experiment models. The frozen scoring policy remains
the default until independent match evaluation supports promotion.
"""
from dataclasses import asdict, dataclass, replace
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import random

from .agents import Decision, Weights, hand_plan
from .cards import DOG, MAHJONG, PHOENIX, DRAGON
from .scoring import ScoringAgent, ScoringWeights, grand_strength, validate_spec
from .tactics import TacticalAgent, TacticalWeights


@dataclass(frozen=True)
class PartnershipWeights:
    exchange: str = 'planner'
    convention: str = 'none'
    parity: bool = False
    wait_small: bool = False
    gentle_wish: bool = False
    temperature: float = 0.0
    max_gap: float = .25
    random_ties: bool = False
    risk: float = 0.0
    seed: int = 82171

    def __post_init__(self):
        if self.exchange not in ('planner', 'team') or self.convention not in ('none', 'greek', 'concentrate'):
            raise ValueError('Unknown passing convention')
        for key in ('parity', 'wait_small', 'gentle_wish', 'random_ties'):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f'{key} must be boolean')
        for key in ('temperature', 'max_gap', 'risk'):
            v = getattr(self, key)
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                raise ValueError(f'{key} must be finite and nonnegative')
        if type(self.seed) is not int:
            raise ValueError('seed must be an integer')


def read_spec(path):
    if path is None:
        raise ValueError('Experimental partnership policy requires an explicit model')
    value = json.loads(Path(path).read_text())
    if value.get('schema_version') != 3 or value.get('policy') != 'partnership':
        raise ValueError('Unsupported partnership policy')
    result = validate_spec({**value, 'schema_version': 2, 'policy': 'scoring'})
    return {**result, 'name': 'partnership', 'policy': 'partnership', 'schema_version': 3,
            'partnership': asdict(PartnershipWeights(**value['partnership']))}


def from_spec(spec):
    return PartnershipAgent(Weights(**spec['weights']), TacticalWeights(**spec['tactics']),
                            ScoringWeights(**spec['scoring']), spec.get('move_weights'),
                            spec.get('move_blend', 1.0),
                            partnership=PartnershipWeights(**spec['partnership']))


class PartnershipAgent(ScoringAgent):
    def __init__(self, *args, partnership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.partnership = partnership or PartnershipWeights()

    def _risk(self, obs):
        ours, theirs = obs.match_scores[obs.seat % 2], obs.match_scores[1-obs.seat % 2]
        near_end = max(0., min(1., (max(ours, theirs)-obs.target+300)/300))
        return self.partnership.risk * near_end * max(-1., min(1., (theirs-ours)/400))

    def _call(self, obs, plan):
        if not self.calls or obs.has_played or obs.calls[obs.seat] or obs.finish_order or obs.calls[(obs.seat+2)%4]:
            return False
        groups, loose = plan.partition(plan.full)
        strength = plan.controls(plan.full) - .65*groups - .25*loose
        strength += self.scoring.king_control*sum(c.rank == 13 for c in obs.hand)
        return strength >= self.weights.call_threshold + self.scoring.small_adjustment - self._risk(obs)

    def _exchange(self, obs):
        p = self.partnership
        if p.exchange == 'planner':
            gifts = super()._exchange(obs).gifts
        else:
            plan = hand_plan(obs.hand)
            partner = (obs.seat+2)%4
            power = sum(c.rank in (14, PHOENIX, DRAGON) for c in obs.hand)
            quality = lambda c: {DOG: -1, MAHJONG: 0, PHOENIX: 18, DRAGON: 17}.get(c.rank, c.rank)
            best_card = max(obs.hand, key=quality)
            dog = next((c for c in obs.hand if c.rank == DOG), None)
            required = None
            keep_dog = False
            if obs.calls[partner]:
                required, keep_dog = best_card, True
            elif obs.calls[obs.seat]:
                required = dog
            elif dog:
                # A strong holder gives partner a way to return the lead;
                # a weak holder retains it to feed the stronger partner.
                if self._call(obs, plan):
                    required = dog
                else:
                    keep_dog = True
            if required is None and not obs.calls[partner] and p.convention != 'none':
                give_power = power >= 2 if p.convention == 'greek' else power <= 1
                required = best_card if give_power else None
            best, gifts = float('-inf'), None
            for triple in combinations(obs.hand, 3):
                if keep_dog and dog in triple:
                    continue
                retained = self._value(plan, plan.full ^ plan.mask(triple))
                for friendly in triple:
                    if required is not None and friendly != required:
                        continue
                    enemies = tuple(c for c in triple if c != friendly)
                    if any(c.rank in (DOG, MAHJONG, 14, PHOENIX, DRAGON) for c in enemies):
                        continue
                    support = self.weights.gift*quality(friendly)*(1.8 if obs.calls[partner] else 1)
                    if obs.calls[obs.seat]:
                        support *= .15
                    if p.convention != 'none' and required is None and friendly.rank in (14, PHOENIX, DRAGON):
                        support -= 12
                    score = retained + support - .7*sum(c.rank for c in enemies)
                    if score > best:
                        best = score
                        gifts = (((obs.seat+1)%4, enemies[0]), (partner, friendly),
                                 ((obs.seat+3)%4, enemies[1]))
            if gifts is None:
                gifts = super()._exchange(obs).gifts
        if p.parity:
            mapping = dict(gifts)
            right, left = (obs.seat+1)%4, (obs.seat+3)%4
            a, b = mapping[right], mapping[left]
            if (b.rank % 2 == 1) + (a.rank % 2 == 0) > (a.rank % 2 == 1) + (b.rank % 2 == 0):
                mapping[right], mapping[left] = b, a
            gifts = tuple(mapping.items())
        return Decision('exchange', gifts=gifts)

    def _select_play(self, obs, plan):
        p = self.partnership
        if not (p.temperature or p.random_ties) or self.move_weights is None or obs.phase != 'playing':
            return super()._select_play(obs, plan)
        from .imitation import score_choices
        baseline = None
        if self.move_blend < 1:
            baseline = ([TacticalAgent._pass_score(self, obs, plan)] if obs.can_pass else [])
            baseline += [TacticalAgent._play_score(self, obs, plan, move) for move in obs.plays]
        choices, scores = score_choices(obs, self.move_weights, baseline, self.move_blend)
        if not choices:
            return None
        best = max(scores)
        gap = p.max_gap if p.temperature else 0.
        eligible = [i for i, score in enumerate(scores) if best-score <= gap]
        # Local reproducible randomness: neither the shuffle stream nor another
        # seat's private state influences this action. Repeated callbacks agree.
        seed = hashlib.sha256(f'{p.seed}:{obs!r}'.encode()).digest()
        rng = random.Random(seed)
        weights = [math.exp((scores[i]-best)/p.temperature) if p.temperature else 1. for i in eligible]
        return choices[rng.choices(eligible, weights=weights, k=1)[0]]

    def wish(self, obs, play=None):
        top = play or obs.top
        if self.partnership.gentle_wish and top and len(top.cards) > 1:
            return None
        return next((c.rank for s, c in obs.sent if s == (obs.seat+1)%4
                     and 2 <= c.rank <= 14 and c not in obs.public_cards), None)

    def choose(self, obs):
        if obs.phase == 'grand':
            return Decision('grand', call=grand_strength(obs.hand) >= self.scoring.grand_threshold-self._risk(obs)
                            and not obs.calls[(obs.seat+2)%4])
        decision = super().choose(obs)
        if self.partnership.wait_small and decision.kind in ('pass', 'decline'):
            decision = replace(decision, call=False)
        if self.partnership.gentle_wish and decision.play and any(c.rank == MAHJONG for c in decision.play.cards):
            decision = replace(decision, wish=self.wish(obs, decision.play))
        return decision
