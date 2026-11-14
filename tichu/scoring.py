"""Experimental point-aware policy, with public-information control estimates.

The estimates bound the chance that a random unseen hand can answer; they are
not calibrated win probabilities or a claim that an opponent will always answer.
No actual opponent hand, external policy implementation or private log is used.
"""
from collections import Counter
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
import json
import math
from pathlib import Path

from .agents import Decision, Weights, hand_plan
from .cards import Card, DOG, MAHJONG, PHOENIX, DRAGON
from .tactics import ALL_CARDS, TacticalAgent, TacticalWeights, load_spec


@dataclass(frozen=True)
class ScoringWeights:
    points: float = .22
    initiative: float = 2.0
    call_defense: float = .25
    partner_call: float = 1.0
    grand_threshold: float = 3.6
    small_adjustment: float = 0.0
    king_control: float = .15
    partner_finish: bool = True
    strong_finish: bool = True

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key in ('partner_finish', 'strong_finish'):
                if type(value) is not bool:
                    raise ValueError(f'{key} must be boolean')
            elif type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'{key} must be finite')
        if min(self.points, self.initiative, self.call_defense, self.partner_call) < 0:
            raise ValueError('Utility weights must be nonnegative')


def initial_spec():
    return {**load_spec(), 'schema_version': 2, 'policy': 'scoring', 'name': 'scoring',
            'scoring': asdict(ScoringWeights())}


def read_spec(path=None):
    value = json.loads(Path(path).read_text()) if path else initial_spec()
    if value.get('schema_version') != 2 or value.get('policy') != 'scoring':
        raise ValueError('Unsupported scoring policy')
    return {'name': 'scoring', 'schema_version': 2, 'policy': 'scoring',
            'weights': asdict(Weights(**value['weights'])),
            'tactics': asdict(TacticalWeights(**value['tactics'])),
            'scoring': asdict(ScoringWeights(**value['scoring']))}


@lru_cache(maxsize=4096)
def at_least(population, successes, draws, needed):
    """Hypergeometric tail; all arguments describe only the unseen-card pool."""
    if needed <= 0:
        return 1.0
    if needed > min(draws, successes):
        return 0.0
    denominator = math.comb(population, draws)
    return sum(math.comb(successes, k) * math.comb(population-successes, draws-k)
               for k in range(needed, min(draws, successes)+1)
               if 0 <= draws-k <= population-successes) / denominator


class ControlEstimate:
    def __init__(self, obs):
        self.obs = obs
        self.known = {s: set() for s in range(4)}
        for seat, card in obs.sent:
            if card not in obs.public_cards:
                self.known[seat].add(card)
        self.pool = ALL_CARDS - set(obs.hand) - set(obs.public_cards) - set().union(*self.known.values())
        self.counts = Counter(c.rank for c in self.pool)
        self.cache = {}

    def answer(self, seat, play):
        key = (seat, play.kind, play.rank, len(play.cards))
        if key in self.cache:
            return self.cache[key]
        value = self._answer(seat, play)
        self.cache[key] = value
        return value

    def _answer(self, seat, play):
        count = self.obs.counts[seat]
        if not count or play.kind == 'dog':
            return 0.0
        known = self.known[seat]
        draws = count - len(known)
        population = len(self.pool)
        if not 0 <= draws <= population:
            raise ValueError('Inconsistent public card counts')

        def all_present(cards):
            cards = tuple(cards)
            missing = set(cards) - known
            if not missing <= self.pool or len(cards) > count:
                return 0.0
            return at_least(population, len(missing), draws, len(missing))

        # Union bound over bombs, retaining exact suits and known passed cards.
        bomb = 0.0
        for rank in range(2, 15):
            if not play.is_bomb or (len(play.cards) == 4 and rank > play.rank):
                bomb += all_present(Card(suit, rank) for suit in range(4))
        for suit in range(4):
            width = max(5, len(play.cards)) if play.is_bomb else 5
            for low in range(2, 16-width):
                if not play.is_bomb or width > len(play.cards) or low+width-1 > play.rank:
                    bomb += all_present(tuple(Card(suit, r) for r in range(low, low+width)))
            # For a straight bomb, one extra card beats it regardless of rank.
            if play.kind == 'straight_bomb' and width < 13:
                for low in range(2, 15-width):
                    bomb += all_present(tuple(Card(suit, r) for r in range(low, low+width+1)))
        if play.is_bomb:
            return min(1.0, bomb)
        if len(play.cards) > count:
            return min(1.0, bomb)
        if play.kind == 'single':
            higher = lambda c: (2 <= c.rank <= 14 and c.rank > play.rank
                                or c.rank == DRAGON and play.rank < DRAGON
                                or c.rank == PHOENIX and play.rank < DRAGON)
            normal = 1.0 if any(map(higher, known)) else at_least(
                population, sum(map(higher, self.pool)), draws, 1)
        elif play.kind in ('pair', 'triple'):
            width = len(play.cards)
            kc = Counter(c.rank for c in known)
            normal = 0.0
            for rank in range(int(play.rank)+1, 15):
                need = width-kc[rank]
                if Card(4, PHOENIX) in known:
                    normal += at_least(population, self.counts[rank], draws, need-1)
                else:
                    normal += at_least(population, self.counts[rank], draws, need)
                    if Card(4, PHOENIX) in self.pool and draws:
                        normal += draws/population * at_least(
                            population-1, self.counts[rank], draws-1, need-1)
        else:
            # A conservative rank/length proxy for multi-rank shapes. Do not
            # present this heuristic as an exact probability calculation.
            normal = max(0., (14-play.rank)/12) * min(1., count/(len(play.cards)*2))
        return min(1.0, normal + bomb)

    def secure(self, play):
        return math.prod(1-self.answer(s, play) for s in range(4)
                         if s % 2 != self.obs.seat % 2)


def grand_strength(hand):
    ranks = Counter(c.rank for c in hand)
    return (ranks[14] + .45*ranks[13] + .2*ranks[12]
            + 1.4*ranks[DRAGON] + 1.4*ranks[PHOENIX] - .5*ranks[DOG]
            + .15*ranks[MAHJONG] + 1.8*sum(ranks[r] == 4 for r in range(2, 15))
            + .3*sum(ranks[r] == 3 for r in range(2, 15)))


class ScoringAgent(TacticalAgent):
    def __init__(self, weights=None, tactics=None, scoring=None):
        spec = initial_spec()
        super().__init__(weights or Weights(**spec['weights']),
                         tactics or TacticalWeights(**spec['tactics']))
        self.scoring = scoring or ScoringWeights()
        self.control = None

    def _call(self, obs, plan):
        if not self.calls or obs.has_played or obs.calls[obs.seat] or obs.finish_order:
            return False
        if obs.calls[(obs.seat+2) % 4]:
            return False
        groups, loose = plan.partition(plan.full)
        kings = sum(c.rank == 13 for c in obs.hand)
        strength = plan.controls(plan.full) - .65*groups - .25*loose + self.scoring.king_control*kings
        return strength >= self.weights.call_threshold + self.scoring.small_adjustment

    def _point_value(self, obs, play, winner):
        if play is None:
            return 0.0
        ours = winner % 2 == obs.seat % 2
        probability = self.control.secure(play) if ours else 0.0
        # Passing behind our partner can still bank the trick's points.
        signed = 2*probability-1
        if play.kind == 'single' and play.cards[0].rank == DRAGON:
            signed = -signed
        return signed

    def _call_danger(self, obs, play):
        if obs.finish_order:
            return 0.0
        danger = 0.0
        for seat in range(4):
            if seat % 2 != obs.seat % 2 and obs.calls[seat] and obs.counts[seat]:
                # Matching their hand size can let them finish immediately;
                # otherwise granting control is more urgent as their hand shrinks.
                urgency = 1.0 if obs.counts[seat] == len(play.cards) else 1/(1+obs.counts[seat]/3)
                danger += obs.calls[seat] * urgency * self.control.answer(seat, play)
        return danger

    def _pass_score(self, obs, plan):
        score = super()._pass_score(obs, plan)
        if obs.top is not None:
            score += self.scoring.points * obs.pile_points * self._point_value(obs, obs.top, obs.trick_winner)
            score -= self.scoring.call_defense * self._call_danger(obs, obs.top)
        return score

    def _play_score(self, obs, plan, play):
        score = super()._play_score(obs, plan, play)
        if play.kind != 'dog':
            pot = obs.pile_points + sum(c.points for c in play.cards)
            score += self.scoring.points * pot * self._point_value(obs, play, obs.seat)
            score += self.scoring.initiative * self.control.secure(play)
            score -= self.scoring.call_defense * self._call_danger(obs, play)
        elif obs.calls[(obs.seat+2) % 4] and not obs.finish_order:
            score += self.scoring.partner_call * obs.calls[(obs.seat+2) % 4] * .2
        return score

    def choose(self, obs):
        if obs.phase == 'grand':
            return Decision('grand', call=grand_strength(obs.hand) >= self.scoring.grand_threshold
                            and not obs.calls[(obs.seat+2) % 4])
        self.control = ControlEstimate(obs) if obs.phase in ('playing', 'bomb_window') else None
        finishers = [p for p in obs.plays if len(p.cards) == len(obs.hand)]
        partner = (obs.seat+2) % 4
        if finishers and self.scoring.partner_finish and obs.calls[partner] and not obs.finish_order:
            # Do not automatically destroy a partner's unresolved declaration.
            # Keep a legal forced finish if passing is forbidden or an enemy is
            # threatening an immediate finish; otherwise yield the opportunity.
            danger = any(obs.counts[s] <= len(finishers[0].cards)
                         for s in range(4) if s % 2 != obs.seat % 2 and obs.counts[s])
            if obs.can_pass and not danger:
                return Decision('decline' if obs.phase == 'bomb_window' else 'pass')
        if finishers and self.scoring.strong_finish:
            choice = max(finishers, key=lambda p: (p.is_bomb, p.rank))
            return Decision('bomb' if obs.phase == 'bomb_window' else 'play', play=choice,
                            call=not obs.has_played and not obs.calls[obs.seat]
                            and not obs.finish_order and not obs.calls[partner],
                            wish=next((c.rank for s, c in obs.sent if s == (obs.seat+1)%4
                                       and 2 <= c.rank <= 14 and c not in obs.public_cards), None)
                            if any(c.rank == MAHJONG for c in choice.cards) else None)
        return super().choose(obs)
