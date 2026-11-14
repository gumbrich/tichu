"""Authoritative round lifecycle. All public commands validate before mutation."""
from dataclasses import dataclass, field
import random

from .cards import Card, Deck, DOG, MAHJONG, DRAGON
from .combinations import Combination, legal_plays


class RuleError(ValueError):
    """An action is not legal in the current state."""


@dataclass(frozen=True)
class PublicAction:
    """Facts visible when a play/pass occurs; no hands or secret exchanges."""
    seat: int
    kind: str
    combo: Combination | None
    previous_top: Combination | None
    previous_winner: int | None
    wish: int | None


@dataclass
class Player:
    name: str
    number: int
    team: int
    hand: list[Card] = field(default_factory=list)
    stack: list[Card] = field(default_factory=list)
    call: int = 0
    has_played: bool = False


class Round:
    """Seats 0..3 progress to the right; opposite seats are partners.

    Phases: grand -> exchange -> playing <-> bomb_window -> dragon -> over.
    Bomb windows precede every ordinary response and trick collection. They
    explicitly distinguish an interrupt (wish exempt) from an ordinary turn.
    """
    def __init__(self, number=1, names=('Alice', 'Bob', 'Charlie', 'Eve'), rng=None):
        if len(names) != 4:
            raise ValueError('Tichu requires four players')
        self.number = number
        self.players = [Player(name, seat, seat % 2) for seat, name in enumerate(names)]
        self.deck = Deck(rng)
        for _ in range(8):
            for player in self.players:
                player.hand.append(self.deck.draw())
        self.phase = 'grand'
        self.grand_pending = set(range(4))
        self.exchanges = {}
        self.turn = None
        self.top = None
        self.trick_winner = None
        self.pile = []
        self.discarded = []  # Dog has no trick-taking power.
        self.passed = set()
        self.bomb_queue = []
        self.wish = None
        self.finish_order = []
        self.scores = None
        self.last_player = None
        self.events = []
        self.public_history = []

    def _player(self, seat):
        if type(seat) is not int or seat not in range(4):
            raise RuleError('Unknown player')
        return self.players[seat]

    def _require(self, condition, message):
        if not condition:
            raise RuleError(message)

    def _next(self, seat):
        return next((seat + step) % 4 for step in range(1, 5)
                    if self.players[(seat + step) % 4].hand)

    @property
    def actor(self):
        if self.phase == 'bomb_window':
            return self.bomb_queue[0]
        if self.phase == 'dragon':
            return self.trick_winner
        if self.phase == 'playing':
            return self.turn
        return None

    def decide_grand(self, seat, call=False):
        player = self._player(seat)
        self._require(self.phase == 'grand' and seat in self.grand_pending,
                      'Grand Tichu must be decided before taking the ninth card')
        self._require(type(call) is bool, 'Grand decision must be yes or no')
        self._require(not (call and player.call), 'A player may make only one Tichu call')
        if call:
            player.call = 200
            self.events.append(f'{player.name} calls Grand Tichu')
        for _ in range(6):
            player.hand.append(self.deck.draw())
        self.grand_pending.remove(seat)
        if not self.grand_pending:
            self.phase = 'exchange'

    def call_tichu(self, seat):
        player = self._player(seat)
        self._require(self.phase in ('grand', 'exchange', 'playing', 'bomb_window') and
                      not player.has_played and player.call == 0,
                      'Call Tichu once, before playing your first card')
        player.call = 100
        self.events.append(f'{player.name} calls Tichu')

    def exchange(self, seat, gifts):
        """Commit one distinct card per other seat; reveal only after all commit."""
        player = self._player(seat)
        self._require(self.phase == 'exchange' and seat not in self.exchanges,
                      'Exchange is not available')
        self._require(set(gifts) == set(range(4)) - {seat},
                      'Give one card to each other player')
        self._require(len(set(gifts.values())) == 3 and
                      all(card in player.hand for card in gifts.values()),
                      'Exchange three different cards from your hand')
        self.exchanges[seat] = dict(gifts)
        if len(self.exchanges) == 4:
            for sender, selections in self.exchanges.items():
                for card in selections.values():
                    self.players[sender].hand.remove(card)
            for selections in self.exchanges.values():
                for recipient, card in selections.items():
                    self.players[recipient].hand.append(card)
            self.turn = next(p.number for p in self.players
                             if Card(4, MAHJONG) in p.hand)
            self.phase = 'playing'
            self.events.append(f'{self.players[self.turn].name} holds Mah Jong and leads')

    def available_plays(self, seat, interrupt=False):
        player = self._player(seat)
        if interrupt:
            if self.phase != 'bomb_window' or seat != self.actor:
                return ()
            return tuple(c for c in legal_plays(player.hand, self.top) if c.is_bomb)
        if self.phase != 'playing' or seat != self.turn:
            return ()
        plays = legal_plays(player.hand, self.top)
        required = tuple(c for c in plays if any(card.rank == self.wish for card in c.cards))
        return required or plays

    def can_pass(self, seat):
        if self.phase != 'playing' or seat != self.turn or self.top is None:
            return False
        return not any(any(card.rank == self.wish for card in c.cards)
                       for c in legal_plays(self._player(seat).hand, self.top))

    def play(self, seat, combo, wish=None):
        self._player(seat)
        self._require(combo in self.available_plays(seat),
                      'Illegal play: check turn, cards, combination, and outstanding wish')
        self._validate_wish(combo, wish)
        self._play(seat, combo, wish)

    def _validate_wish(self, combo, wish):
        self._require(wish is None or (type(wish) is int and 2 <= wish <= 14 and
                      any(c.rank == MAHJONG for c in combo.cards)),
                      'Only a Mah Jong play may wish for a rank from 2 to Ace')

    def bomb(self, seat, combo):
        self._player(seat)
        self._require(combo in self.available_plays(seat, interrupt=True),
                      'Only a higher bomb may interrupt at your response opportunity')
        self._play(seat, combo, None, interrupt=True)

    def _play(self, seat, combo, wish, interrupt=False):
        player = self.players[seat]
        self.public_history.append(PublicAction(seat, 'bomb' if interrupt else 'play',
                                               combo, self.top, self.trick_winner, self.wish))
        for card in combo.cards:
            player.hand.remove(card)
        player.has_played = True
        if any(c.rank == self.wish for c in combo.cards):
            self.wish = None
        if wish is not None:
            self.wish = wish
        self.events.append(f'{player.name} plays {combo}' +
                           (f'; wishes {Card.ranks[wish]}' if wish else ''))
        self.passed.clear()
        self.bomb_queue.clear()
        if not player.hand:
            self.finish_order.append(seat)
            self.events.append(f'{player.name} finishes #{len(self.finish_order)}')
        if combo.kind == 'dog':
            self.discarded.extend(combo.cards)
            partner = (seat + 2) % 4
            self.turn = partner if self.players[partner].hand else self._next(partner)
        else:
            self.top = combo
            self.trick_winner = seat
            self.pile.extend(combo.cards)
            self.turn = self._next(seat)
        if self._double_victory():
            self._score()
        elif len(self.finish_order) == 3:
            if self.top is not None:
                self._collect()
            else:
                self._score()
        elif combo.kind == 'dog':
            self.phase = 'playing'
        else:
            self._open_bombs(seat)

    def pass_turn(self, seat):
        self._player(seat)
        self._require(self.can_pass(seat), 'Cannot pass on a lead or ignore a playable wish')
        self.public_history.append(PublicAction(seat, 'pass', None, self.top,
                                               self.trick_winner, self.wish))
        self.passed.add(seat)
        self.events.append(f'{self.players[seat].name} passes')
        self.turn = self._next(seat)
        self._open_bombs(seat)

    def _open_bombs(self, after):
        self.bomb_queue = [(after + step) % 4 for step in range(1, 5)
                           if self.players[(after + step) % 4].hand]
        self.phase = 'bomb_window'

    def decline_bomb(self, seat):
        self._player(seat)
        self._require(self.phase == 'bomb_window' and seat == self.actor,
                      'Not your bomb response opportunity')
        self.bomb_queue.pop(0)
        if not self.bomb_queue:
            required = {p.number for p in self.players if p.hand} - {self.trick_winner}
            if required <= self.passed:
                self._collect()
            else:
                self.phase = 'playing'

    def _collect(self):
        if self.top.kind == 'single' and self.top.cards[0].rank == DRAGON:
            self.phase = 'dragon'
            return
        self._award(self.trick_winner)

    def give_dragon(self, seat, recipient):
        self._player(seat)
        other = self._player(recipient)
        self._require(self.phase == 'dragon' and seat == self.trick_winner,
                      'Only the Dragon winner chooses its recipient')
        self._require(other.team != self.players[seat].team,
                      'Give the Dragon trick to either opponent, including one who is out')
        self._award(recipient)

    def _award(self, recipient):
        self.players[recipient].stack.extend(self.pile)
        self.events.append(f'{self.players[recipient].name} receives trick '
                           f'({sum(c.points for c in self.pile)} points)')
        leader = self.trick_winner
        self.pile = []
        self.top = None
        self.trick_winner = None
        self.passed.clear()
        self.bomb_queue.clear()
        if len(self.finish_order) == 3:
            self._score()
        else:
            self.turn = leader if self.players[leader].hand else self._next(leader)
            self.phase = 'playing'

    def _double_victory(self):
        return (len(self.finish_order) >= 2 and
                self.finish_order[0] % 2 == self.finish_order[1] % 2)

    def _score(self):
        scores = [0, 0]
        first = self.finish_order[0]
        if self._double_victory():
            scores[first % 2] = 200
        else:
            last = next(p for p in self.players if p.hand)
            self.last_player = last.number
            self.players[first].stack.extend(last.stack)
            last.stack.clear()
            self.players[(last.number + 1) % 4].stack.extend(last.hand)
            last.hand.clear()
            for player in self.players:
                scores[player.team] += sum(c.points for c in player.stack)
        for player in self.players:
            scores[player.team] += player.call if player.number == first else -player.call
        self.scores = tuple(scores)
        self.phase = 'over'
        self.turn = None
        self.bomb_queue.clear()
        self.events.append(f'Round score: {scores[0]} : {scores[1]}')


class Match:
    """Accumulate completed rounds; tied target scores require another round."""
    def __init__(self, names=('Alice', 'Bob', 'Charlie', 'Eve'), target=1000, seed=None):
        if type(target) is not int or target <= 0:
            raise ValueError('Target must be a positive integer')
        self.names = names
        self.target = target
        self.rng = random.Random(seed)
        self.scores = [0, 0]
        self.winner = None
        self.history = []
        self.round = Round(names=names, rng=self.rng)
        self.round.match_scores, self.round.target = tuple(self.scores), self.target

    def next_round(self):
        if self.round.phase != 'over' or self.winner is not None:
            raise RuleError('Finish the current round before advancing; a won match is over')
        self.history.append(self.round.scores)
        self.scores = [a + b for a, b in zip(self.scores, self.round.scores)]
        if max(self.scores) >= self.target and self.scores[0] != self.scores[1]:
            self.winner = 0 if self.scores[0] > self.scores[1] else 1
            return None
        self.round = Round(len(self.history) + 1, self.names, self.rng)
        self.round.match_scores, self.round.target = tuple(self.scores), self.target
        return self.round
