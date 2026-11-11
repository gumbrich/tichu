"""Conservative public-information tactics, with no sampled hidden-hand oracle."""
from collections import Counter
from dataclasses import dataclass, asdict
from functools import lru_cache
import math
import json
from pathlib import Path

from .agents import StrategicAgent, Decision, Weights, hand_plan
from .cards import Card, DOG, MAHJONG, PHOENIX, DRAGON
from .combinations import legal_plays

ALL_CARDS = frozenset([Card(s, r) for s in range(4) for r in range(2, 15)] +
                      [Card(4, r) for r in (DOG, MAHJONG, PHOENIX, DRAGON)])
DEFAULT_COMPETITIVE_MODEL = Path(__file__).with_name('competitive_weights.json')


def load_spec(path=DEFAULT_COMPETITIVE_MODEL):
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1 or data.get('policy') != 'tactical':
        raise ValueError('Unsupported tactical policy checkpoint')
    return {'name': 'tactical', 'weights': asdict(Weights(**data['weights'])),
            'tactics': asdict(TacticalWeights(**data['tactics']))}


def save_spec(path, spec, **metadata):
    data = {'schema_version': 1, 'policy': 'tactical',
            'weights': asdict(Weights(**spec['weights'])),
            'tactics': asdict(TacticalWeights(**spec['tactics'])), **metadata}
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def proven_voids(history):
    """An ordinary declined playable singleton wish proves rank absence.

    Ordinary passes without such an obligation are NOT proof. Interrupt bombs
    are wish-exempt and likewise cannot create a void. No cards are received
    after play begins, so these proven absences persist through the round.
    """
    voids = [set() for _ in range(4)]
    for event in history:
        if event.kind not in ('play', 'pass') or event.wish is None:
            continue
        if event.combo and any(c.rank == event.wish for c in event.combo.cards):
            continue
        top = event.previous_top
        if top is None or (top.kind == 'single' and event.wish > top.rank):
            voids[event.seat].add(event.wish)
    return tuple(frozenset(ranks) for ranks in voids)


def possible_cards(obs, seat, *, use_history=True):
    """An upper bound on a seat's hand, not an estimate of its actual cards."""
    unknown = ALL_CARDS - set(obs.hand) - set(obs.public_cards)
    excluded = {c for recipient, c in obs.sent if recipient != seat}
    voids = proven_voids(obs.history)[seat] if use_history else ()
    return tuple(sorted(c for c in unknown - excluded if c.rank not in voids))


@lru_cache(maxsize=8192)
def can_beat_from_pool(pool, top, max_cards, exact_size=None):
    """Whether ANY hand subset of the pool can beat top within the size limit.

    This is deliberately pessimistic: cards in the pool may be held by different
    people. False means a counterplay is impossible; True does not say it exists.
    No subset expansion over a 42-card unseen pool is needed.
    """
    if max_cards < 1 or top is None or top.kind == 'dog':
        return False
    counts = Counter(c.rank for c in pool)
    wild = int(counts[PHOENIX] > 0)

    def allowed(size):
        return size <= max_cards and (exact_size is None or size == exact_size)

    # Bombs may override any ordinary shape, but not an equal/higher bomb.
    if allowed(4):
        if any(counts[r] == 4 and (not top.is_bomb or
               (len(top.cards) == 4 and r > top.rank)) for r in range(2, 15)):
            return True
    for suit in range(4):
        ranks = {c.rank for c in pool if c.suit == suit}
        for low in range(2, 11):
            for high in range(low + 4, min(14, low + max_cards - 1) + 1):
                size = high - low + 1
                if allowed(size) and all(r in ranks for r in range(low, high + 1)):
                    if not top.is_bomb or (size, high) > (len(top.cards), top.rank):
                        return True
    if top.is_bomb:
        return False
    size = len(top.cards)
    if not allowed(size):
        return False
    if top.kind == 'single':
        return (any(counts[r] and r > top.rank for r in range(1, 15)) or
                bool(counts[DRAGON] and top.rank < DRAGON) or
                bool(wild and top.rank < DRAGON))
    if top.kind in ('pair', 'triple'):
        return any(r > top.rank and counts[r] + wild >= size for r in range(2, 15))
    if top.kind == 'full_house':
        return any(triple > top.rank and max(0, 3 - counts[triple]) + max(0, 2 - counts[pair]) <= wild
                   for triple in range(2, 15) for pair in range(2, 15) if pair != triple)
    width = size if top.kind == 'straight' else size // 2
    copies = 1 if top.kind == 'straight' else 2
    start = 1 if top.kind == 'straight' else 2
    for low in range(start, 16 - width):
        high = low + width - 1
        if high <= top.rank or (low == 1 and not counts[MAHJONG]):
            continue
        missing = sum(max(0, copies - counts[r]) for r in range(low, high + 1))
        if missing <= wild:
            return True
    return False


class Counterplay:
    def __init__(self, obs, use_history=True):
        self.obs = obs
        self.pools = {seat: possible_cards(obs, seat, use_history=use_history)
                      for seat in range(4) if seat != obs.seat and obs.counts[seat]}

    def can_beat(self, seat, play, exact_size=None):
        return seat in self.pools and can_beat_from_pool(
            self.pools[seat], play, self.obs.counts[seat], exact_size)

    def secure(self, play, include_partner=True):
        if play.kind == 'dog':
            return False
        return not any(self.can_beat(seat, play) for seat in self.pools
                       if include_partner or seat % 2 != self.obs.seat % 2)

    def enemy_can_finish(self, play):
        return any(self.can_beat(seat, play, self.obs.counts[seat])
                   for seat in self.pools if seat % 2 != self.obs.seat % 2)


def forced_finish(obs, counter):
    """Find a fixed uninterrupted finish valid for EVERY consistent hidden deal.

    Only consider small hands. Every non-final play must be unanswerable even by
    the partner, including bombs; future leads must satisfy an outstanding wish.
    Dog transfers the lead and cannot be an intermediate step. No per-world
    plan selection (strategy fusion) and no guessed opponent cards are involved.
    """
    if len(obs.hand) > 8 or not obs.plays:
        return None
    plan = hand_plan(obs.hand)
    leads = [(plan.mask(p.cards), p) for p in legal_plays(obs.hand)]

    @lru_cache(maxsize=None)
    def finish(mask, wish):
        if not mask:
            return True
        required = any(c.rank == wish and mask & plan.index[c] for c in obs.hand)
        for selection, play in leads:
            if selection & mask != selection:
                continue
            fulfills = any(c.rank == wish for c in play.cards)
            if required and not fulfills:
                continue
            left = mask ^ selection
            if not left or (counter.secure(play) and finish(left, None if fulfills else wish)):
                return True
        return False

    for play in obs.plays:
        mask = plan.full ^ plan.mask(play.cards)
        wish = None if any(c.rank == obs.wish for c in play.cards) else obs.wish
        if not mask or (counter.secure(play) and finish(mask, wish)):
            return play
    return None


@dataclass(frozen=True)
class TacticalWeights:
    secure: float = 3.0
    threat: float = 8.0
    points: float = 0.08

    def __post_init__(self):
        for key, value in asdict(self).items():
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f'{key} must be finite and nonnegative')


class TacticalAgent(StrategicAgent):
    """Frozen planner plus public-history counterplay bounds and proven finishes."""
    def __init__(self, weights=None, tactics=None, *, history=True, proofs=True, **options):
        super().__init__(weights, **options)
        self.tactics = tactics or TacticalWeights()
        self.history_enabled = history
        self.proofs_enabled = proofs
        self.counter = None

    def choose(self, obs):
        self.counter = Counterplay(obs, self.history_enabled) if obs.phase in ('playing', 'bomb_window') else None
        if self.counter and self.proofs_enabled and not obs.calls[(obs.seat + 2) % 4]:
            proof = forced_finish(obs, self.counter)
            if proof:
                call = self.calls and not obs.has_played and not obs.calls[obs.seat] and not obs.finish_order
                return Decision('bomb' if obs.phase == 'bomb_window' else 'play', play=proof, call=call)
        return super().choose(obs)

    def _pass_score(self, obs, plan):
        score = super()._pass_score(obs, plan)
        if self.counter and obs.top and self.counter.enemy_can_finish(obs.top):
            score -= self.tactics.threat
        return score

    def _play_score(self, obs, plan, play):
        score = super()._play_score(obs, plan, play)
        if self.counter:
            if self.counter.secure(play, include_partner=False):
                score += self.tactics.secure
                points = obs.pile_points + sum(c.points for c in play.cards)
                if play.kind == 'single' and play.cards[0].rank == DRAGON:
                    points = -points
                score += self.tactics.points * points
            if self.counter.enemy_can_finish(play):
                score -= self.tactics.threat
        return score
