"""Observation-only agents: no policy receives authoritative Round state."""
from dataclasses import dataclass, asdict, replace
import copy
from functools import lru_cache
from itertools import combinations
import json
import math
from pathlib import Path

from .cards import Card, DOG, MAHJONG, PHOENIX, DRAGON
from .combinations import Combination, legal_plays
from .game import PublicAction


@dataclass(frozen=True)
class Observation:
    seat: int
    phase: str
    hand: tuple[Card, ...]
    counts: tuple[int, ...]
    calls: tuple[int, ...]
    has_played: bool
    top: Combination | None
    trick_winner: int | None
    wish: int | None
    finish_order: tuple[int, ...]
    public_cards: tuple[Card, ...]
    sent: tuple[tuple[int, Card], ...]
    plays: tuple[Combination, ...]
    can_pass: bool
    pile_points: int
    history: tuple[PublicAction, ...] = ()


@dataclass(frozen=True)
class Decision:
    kind: str
    play: Combination | None = None
    gifts: tuple[tuple[int, Card], ...] = ()
    recipient: int | None = None
    wish: int | None = None
    call: bool = False


def current_actor(game):
    if game.phase == 'grand':
        return min(game.grand_pending)
    if game.phase == 'exchange':
        return next(s for s in range(4) if s not in game.exchanges)
    return game.actor


def observe(game, seat):
    """Trusted boundary. Only the requested seat's private information crosses it."""
    player = game.players[seat]
    interrupt = game.phase == 'bomb_window'
    public = game.pile + game.discarded + [c for p in game.players for c in p.stack]
    # A sender knows their own gifts even while other commitments are still secret.
    sent = tuple(sorted(game.exchanges.get(seat, {}).items()))
    return Observation(seat, game.phase, tuple(sorted(player.hand)),
                       tuple(len(p.hand) for p in game.players),
                       tuple(p.call for p in game.players), player.has_played,
                       game.top, game.trick_winner, game.wish, tuple(game.finish_order),
                       tuple(sorted(public)), sent,
                       game.available_plays(seat, interrupt=interrupt),
                       game.can_pass(seat), sum(c.points for c in game.pile),
                       tuple(game.public_history))


def apply_decision(game, seat, decision):
    """Adapter: validate a combined declaration/play before committing either."""
    if decision.call:
        trial = copy.deepcopy(game)
        trial.call_tichu(seat)
        _apply_action(trial, seat, decision)
        game.call_tichu(seat)
    _apply_action(game, seat, decision)


def _apply_action(game, seat, decision):
    if decision.kind == 'grand':
        game.decide_grand(seat, False)
    elif decision.kind == 'exchange':
        game.exchange(seat, dict(decision.gifts))
    elif decision.kind == 'play':
        game.play(seat, decision.play, decision.wish)
    elif decision.kind == 'bomb':
        game.bomb(seat, decision.play)
    elif decision.kind == 'pass':
        game.pass_turn(seat)
    elif decision.kind == 'decline':
        game.decline_bomb(seat)
    elif decision.kind == 'dragon':
        game.give_dragon(seat, decision.recipient)
    else:
        raise ValueError(f'Unknown decision {decision.kind}')


def agent_step(game, agent):
    seat = current_actor(game)
    observation = observe(game, seat)
    decision = agent.choose(observation)
    apply_decision(game, seat, decision)
    return decision


class BaselineAgent:
    """Original policy, retained unchanged as an honest benchmark opponent."""
    def choose(self, obs):
        if obs.phase == 'grand':
            return Decision('grand')
        if obs.phase == 'exchange':
            hand = sorted(obs.hand, key=lambda c: (c.rank, c.suit))
            return Decision('exchange', gifts=tuple(((obs.seat + i + 1) % 4, c)
                                                    for i, c in enumerate(hand[:3])))
        if obs.phase == 'dragon':
            return Decision('dragon', recipient=(obs.seat + 1) % 4)
        plays = obs.plays
        if obs.phase == 'bomb_window':
            plays = tuple(c for c in plays if len(c.cards) == len(obs.hand) or
                          (obs.top.kind == 'single' and obs.top.rank == DRAGON and
                           obs.trick_winner % 2 != obs.seat % 2))
        if not plays:
            return Decision('decline' if obs.phase == 'bomb_window' else 'pass')
        choice = min(plays, key=lambda c: (c.is_bomb, -len(c.cards), c.rank, c.cards,
                                           c.phoenix_rank or 0))
        return Decision('bomb' if obs.phase == 'bomb_window' else 'play', play=choice)


@dataclass(frozen=True)
class Weights:
    groups: float = 8.0
    loose: float = 1.6
    control: float = 1.8
    shed: float = 0.35
    rank: float = 0.12
    partner: float = 12.0
    bomb: float = 5.0
    urgency: float = 4.0
    lead: float = 2.0
    gift: float = 1.2
    call_threshold: float = 1.5

    def __post_init__(self):
        for key, value in asdict(self).items():
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'{key} must be a finite number')
            if key != 'call_threshold' and value < 0:
                raise ValueError(f'{key} must not be negative')

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if data.get('schema_version', 1) != 1:
            raise ValueError('Unsupported policy schema version')
        return cls(**data.get('weights', data))

    def save(self, path, **metadata):
        Path(path).write_text(json.dumps({'schema_version': 1, 'weights': asdict(self),
                                         **metadata}, indent=2) + '\n')


class HandPlan:
    """Exact minimum-combination cover of one's own hand (not a game-tree oracle).

    Bitmask dynamic programming retains card identity, including suits. It finds
    the fewest future plays, breaking ties by low singleton count. This does not
    assume those plays will win the intervening tricks.
    """
    def __init__(self, hand):
        self.hand = hand
        self.index = {c: 1 << i for i, c in enumerate(hand)}
        self.full = (1 << len(hand)) - 1
        self.by_card = [[] for _ in hand]
        self.bombs = []
        for play in legal_plays(hand):
            mask = self.mask(play.cards)
            loose = int(len(play.cards) == 1 and 1 <= play.rank <= 10)
            for i in range(len(hand)):
                if mask & (1 << i):
                    self.by_card[i].append((mask, loose))
            if play.is_bomb:
                self.bombs.append(mask)
        self.cache = {0: (0, 0)}

    def mask(self, cards):
        return sum(self.index[c] for c in cards)

    def partition(self, mask):
        if mask not in self.cache:
            bit = (mask & -mask).bit_length() - 1
            best = (99, 99)
            for selection, loose in self.by_card[bit]:
                if selection & mask == selection:
                    groups, singles = self.partition(mask ^ selection)
                    best = min(best, (groups + 1, singles + loose))
            self.cache[mask] = best
        return self.cache[mask]

    def controls(self, mask):
        value = sum({14: 1.0, PHOENIX: 1.1, DRAGON: 1.3}.get(c.rank, 0)
                    for i, c in enumerate(self.hand) if mask & (1 << i))
        return value + 1.5 * sum(mask & bomb == bomb for bomb in self.bombs)


@lru_cache(maxsize=512)
def hand_plan(hand):
    return HandPlan(tuple(sorted(hand)))


class StrategicAgent:
    """Exact hand planning + partnership tactics; weights can be self-play tuned."""
    def __init__(self, weights=None, *, teamwork=True, planning=True, calls=True,
                 exchange=True):
        self.weights = weights or Weights()
        self.teamwork = teamwork
        self.planning = planning
        self.calls = calls
        self.exchange_enabled = exchange

    def _value(self, plan, mask):
        groups, loose = plan.partition(mask) if self.planning else (mask.bit_count(), 0)
        w = self.weights
        return -w.groups * groups - w.loose * loose + w.control * plan.controls(mask)

    def _call(self, obs, plan):
        if not self.calls or obs.has_played or obs.calls[obs.seat] or obs.finish_order:
            return False
        partner = (obs.seat + 2) % 4
        if obs.calls[partner]:
            return False
        groups, loose = plan.partition(plan.full)
        strength = plan.controls(plan.full) - .65 * groups - .25 * loose
        return strength >= self.weights.call_threshold

    def _exchange(self, obs):
        plan = hand_plan(obs.hand)
        w = self.weights
        partner = (obs.seat + 2) % 4
        best, best_gifts = float('-inf'), None
        # Evaluate all distinct three-card commitments, not received hidden cards.
        for gifted in combinations(obs.hand, 3):
            mask = plan.full ^ plan.mask(gifted)
            remaining_value = self._value(plan, mask)
            for friendly in gifted:
                enemies = tuple(c for c in gifted if c != friendly)
                quality = {DOG: -1, MAHJONG: 0, PHOENIX: 17, DRAGON: 18}.get(friendly.rank, friendly.rank)
                support = w.gift * quality * (1.8 if obs.calls[partner] else 1)
                if obs.calls[obs.seat]:
                    support *= .15
                danger = sum({PHOENIX: 20, DRAGON: 22}.get(c.rank, c.rank) for c in enemies)
                score = remaining_value + support - .7 * danger
                if score > best:
                    best = score
                    best_gifts = (((obs.seat + 1) % 4, enemies[0]),
                                  (partner, friendly), ((obs.seat + 3) % 4, enemies[1]))
        return Decision('exchange', gifts=best_gifts)

    def _pass_score(self, obs, plan):
        partner = (obs.seat + 2) % 4
        partner_winning = self.teamwork and obs.trick_winner == partner and obs.counts[partner] > 0
        return self._value(plan, plan.full) + (self.weights.partner if partner_winning else 0)

    def _play_score(self, obs, plan, play):
        w = self.weights
        partner = (obs.seat + 2) % 4
        partner_winning = self.teamwork and obs.trick_winner == partner and obs.counts[partner] > 0
        enemies = [(obs.seat + 1) % 4, (obs.seat + 3) % 4]
        urgent = max(0, max((4 - obs.counts[s] for s in enemies if obs.counts[s]), default=0))
        remaining = plan.full ^ plan.mask(play.cards)
        score = self._value(plan, remaining) + w.shed * len(play.cards) - w.rank * play.rank
        strength = min(1.0, max(0, (play.rank - 8) / 6))
        score += w.urgency * urgent * strength
        if obs.top is None:
            score += w.lead * (1 - strength)
            if any(obs.counts[s] == len(play.cards) for s in enemies):
                score += w.urgency * strength
        if play.is_bomb:
            score -= w.bomb
        if play.kind == 'dog':
            score += (w.partner * .6 if self.teamwork and obs.counts[partner] else -w.partner)
            if obs.calls[obs.seat]:
                score -= w.partner
        if obs.calls[partner] and self.teamwork:
            score -= w.partner * .5 if partner_winning else 0
        return score

    def choose(self, obs):
        if obs.phase == 'grand':
            return Decision('grand')  # Keep the high-variance 8-card bet disabled.
        if obs.phase == 'exchange':
            return self._exchange(obs) if self.exchange_enabled else BaselineAgent().choose(obs)
        if obs.phase == 'dragon':
            opponents = [(obs.seat + 1) % 4, (obs.seat + 3) % 4]
            # A likely last player's captured trick will transfer to first finisher.
            recipient = min(opponents, key=lambda s: obs.counts[s])
            if obs.finish_order and obs.finish_order[0] % 2 == obs.seat % 2:
                recipient = max(opponents, key=lambda s: obs.counts[s])
            if obs.pile_points < 0:
                recipient = max(opponents, key=lambda s: obs.counts[s])
            return Decision('dragon', recipient=recipient)
        interrupt = obs.phase == 'bomb_window'
        decline = 'decline' if interrupt else 'pass'
        if not obs.plays:
            return Decision(decline)
        # Going out wins precedence over preserving resources or supporting partner.
        finishers = [p for p in obs.plays if len(p.cards) == len(obs.hand)]
        if finishers:
            choice = min(finishers, key=lambda c: (c.rank, c.cards))
            return Decision('bomb' if interrupt else 'play', play=choice,
                            call=self.calls and not obs.has_played and not obs.calls[obs.seat]
                            and not obs.finish_order and not obs.calls[(obs.seat + 2) % 4])
        plan = hand_plan(obs.hand)
        pass_score = self._pass_score(obs, plan)
        best_score = pass_score if interrupt or obs.can_pass else float('-inf')
        best = None
        for play in obs.plays:
            score = self._play_score(obs, plan, play)
            if score > best_score:
                best, best_score = play, score
        call = self._call(obs, plan) if not interrupt else False
        if best is None:
            return Decision(decline, call=call)
        wish = None
        if any(c.rank == MAHJONG for c in best.cards):
            # Exact knowledge from our own exchange, not an opponent-hand peek.
            wish = next((c.rank for seat, c in obs.sent if seat == (obs.seat + 1) % 4
                         and 2 <= c.rank <= 14 and c not in obs.public_cards), None)
        return Decision('bomb' if interrupt else 'play', play=best, wish=wish, call=call)


def load_agent(name='trained', path=None):
    if name == 'competitive':
        from .tactics import TacticalAgent, TacticalWeights, load_spec, DEFAULT_COMPETITIVE_MODEL
        spec = load_spec(path if path is not None else DEFAULT_COMPETITIVE_MODEL)
        return TacticalAgent(Weights(**spec['weights']), TacticalWeights(**spec['tactics']))
    if name == 'baseline':
        return BaselineAgent()
    if name == 'strategic':
        return StrategicAgent()
    if name != 'trained':
        raise ValueError(f'Unknown bot {name}')
    model = Path(path) if path is not None else Path(__file__).with_name('trained_weights.json')
    return StrategicAgent(Weights.load(model))
