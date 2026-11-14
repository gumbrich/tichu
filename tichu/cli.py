"""Terminal frontend with selectable self-play-trained and baseline bots."""
import argparse
import random
import sys

from .cards import Card, MAHJONG
from .game import Match, RuleError
from .agents import BaselineAgent, agent_step, load_agent, current_actor


class QuitGame(Exception):
    pass


def bot_step(game):
    """Compatibility wrapper for the original benchmark policy."""
    return agent_step(game, BaselineAgent())


class Console:
    def __init__(self, humans=1, read=input, write=print, bot=None, bots=None):
        self.humans = set(range(humans))
        self.bot = bot if bot is not None else load_agent()
        self.bots = bots
        self.read = read
        self.write = write
        self.last_seat = None
        self.event_index = 0

    def ask(self, game, seat, prompt):
        while True:
            answer = self.read(prompt).strip().lower()
            if answer in ('q', 'quit', 'exit'):
                raise QuitGame
            if answer.split()[:1] == ['tichu']:
                try:
                    parts = answer.split()
                    if len(parts) > 2:
                        raise ValueError('Use tichu or tichu <seat number>')
                    caller = seat if len(parts) == 1 else int(parts[1]) - 1
                    if caller not in self.humans:
                        raise ValueError('Choose a human-controlled seat')
                    game.call_tichu(caller)
                    self.write(f'{game.players[caller].name} calls Tichu!')
                except (ValueError, RuleError) as error:
                    self.write(str(error))
                continue
            return answer

    def table(self, game):
        for event in game.events[self.event_index:]:
            self.write(event)
        self.event_index = len(game.events)
        self.write(' | '.join(f'{p.number + 1} {p.name}: {len(p.hand)} cards'
                              + (f', call {p.call}' if p.call else '') for p in game.players))
        if game.wish:
            self.write(f'Outstanding wish: {Card.ranks[game.wish]}')
        if game.top:
            self.write(f'Table: {game.top}')

    def hand(self, game, seat):
        if len(self.humans) > 1 and seat != self.last_seat:
            if sys.stdout.isatty():
                self.write('\033[2J\033[H')
            answer = self.read(f'Pass the terminal to {game.players[seat].name}; Enter when ready. ')
            if answer.strip().lower() in ('q', 'quit', 'exit'):
                raise QuitGame
        self.last_seat = seat
        self.write(f'\n{game.players[seat].name}, your hand:')
        ordered = sorted(game.players[seat].hand, key=lambda c: (c.rank, c.suit))
        self.write(' | '.join(f'{i + 1}: {c}' for i, c in enumerate(ordered)))
        return ordered

    @staticmethod
    def select(answer, hand, count=None):
        indices = [int(word) - 1 for word in answer.split()]
        if not indices or len(set(indices)) != len(indices) or any(i not in range(len(hand)) for i in indices):
            raise ValueError('Use distinct card numbers shown in your hand')
        if count is not None and len(indices) != count:
            raise ValueError(f'Select exactly {count} cards')
        return tuple(sorted(hand[i] for i in indices))

    def human_step(self, game, seat):
        hand = self.hand(game, seat)
        while True:
            try:
                if game.phase == 'grand':
                    answer = self.ask(game, seat, 'Grand Tichu on these eight cards? yes/no: ')
                    if answer not in ('y', 'yes', 'n', 'no'):
                        raise ValueError('Enter yes or no')
                    game.decide_grand(seat, answer in ('y', 'yes'))
                elif game.phase == 'exchange':
                    targets = [(seat + i) % 4 for i in (1, 2, 3)]
                    names = ', '.join(game.players[s].name for s in targets)
                    answer = self.ask(game, seat, f'Give three card numbers in order to {names}: ')
                    # Keep the input order: each position names a recipient.
                    self.select(answer, hand, 3)
                    gifts = [hand[int(word) - 1] for word in answer.split()]
                    game.exchange(seat, dict(zip(targets, gifts)))
                elif game.phase == 'dragon':
                    opponents = [s + 1 for s in range(4) if s % 2 != seat % 2]
                    answer = self.ask(game, seat, f'Give Dragon trick to seat {opponents}: ')
                    game.give_dragon(seat, int(answer) - 1)
                else:
                    interrupt = game.phase == 'bomb_window'
                    plays = game.available_plays(seat, interrupt=interrupt)
                    prompt = ('Bomb response: card numbers or Enter to decline' if interrupt else
                              'Play card numbers, or pass')
                    answer = self.ask(game, seat, prompt + ' (moves/tichu [seat]/q): ')
                    if answer == 'moves':
                        for c in plays:
                            numbers = ' '.join(str(hand.index(card) + 1) for card in c.cards)
                            self.write(f'{numbers}: {c}')
                        continue
                    if interrupt and answer in ('', 'pass'):
                        game.decline_bomb(seat)
                        return
                    if not interrupt and answer == 'pass':
                        game.pass_turn(seat)
                        return
                    selected = self.select(answer.removeprefix('play '), hand)
                    interpretations = [c for c in plays if c.cards == selected]
                    if not interpretations:
                        raise ValueError('That selection is not legal; type moves to see options')
                    index = 0
                    if len(interpretations) > 1:
                        for i, c in enumerate(interpretations):
                            self.write(f'{i + 1}: {c}')
                        index = int(self.ask(game, seat, 'Choose Phoenix interpretation: ')) - 1
                        if index not in range(len(interpretations)):
                            raise ValueError('Choose a listed interpretation')
                    selection = interpretations[index]
                    if interrupt:
                        game.bomb(seat, selection)
                    else:
                        wish = None
                        if any(c.rank == MAHJONG for c in selection.cards):
                            answer = self.ask(game, seat, 'Wish rank 2-14 (J=11,Q=12,K=13,A=14), 0 for none: ')
                            wish = int(answer) or None
                        game.play(seat, selection, wish=wish)
                return
            except (ValueError, RuleError) as error:
                self.write(f'Please try again: {error}')

    def play_round(self, game):
        self.event_index = 0
        self.last_seat = None
        while game.phase != 'over':
            if game.phase == 'grand':
                seat = min(game.grand_pending)
            elif game.phase == 'exchange':
                seat = next(s for s in range(4) if s not in game.exchanges)
            else:
                seat = game.actor
            # No decision is lost by automatically declining an impossible bomb.
            if game.phase == 'bomb_window' and not game.available_plays(seat, interrupt=True):
                game.decline_bomb(seat)
                continue
            self.table(game)
            if seat in self.humans:
                self.human_step(game, seat)
            else:
                agent_step(game, self.bots[seat] if self.bots is not None else self.bot)
        self.table(game)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Four-player Tichu in your terminal')
    parser.add_argument('--humans', type=int, choices=range(5), default=1,
                        help='human seats (0-4); default: you and three trained bots')
    parser.add_argument('--seed', type=int, help='reproducible deals')
    parser.add_argument('--target', type=int, default=1000, help='match points (default 1000)')
    parser.add_argument('--demo', action='store_true', help='play bots only, with round summaries')
    parser.add_argument('--bot', choices=('baseline', 'strategic', 'trained', 'competitive', 'scoring', 'partnership'),
                        help='default: scoring (verified v3); sampling options select competitive (v2)')
    parser.add_argument('--weights', help='custom policy JSON file for the selected bot')
    parser.add_argument('--temperature', type=float, default=0.,
                        help='experimental move sampling in score units; 0 preserves deterministic play')
    parser.add_argument('--random-ties', action='store_true', help='randomize equal-score choices at temperature 0')
    parser.add_argument('--max-score-gap', type=float, help='sample only moves within this score gap of the best')
    parser.add_argument('--bot-seed', type=int, help='sampling seed, separate from the --seed used for deals')
    args = parser.parse_args(argv)
    if args.bot is None:
        sampling = args.temperature != 0 or args.random_ties or args.max_score_gap is not None
        args.bot = 'competitive' if sampling else 'scoring'
    if args.target <= 0:
        parser.error('--target must be positive')
    match = Match(target=args.target, seed=args.seed)
    try:
        seed_source = random.Random(args.bot_seed)
        bots = [load_agent(args.bot, args.weights, temperature=args.temperature,
                           random_ties=args.random_ties, max_gap=args.max_score_gap,
                           seed=seed_source.getrandbits(64)) for _ in range(4)]
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))
    console = Console(0 if args.demo else args.humans, bot=bots[0], bots=bots)
    print('Tichu — Alice + Charlie vs Bob + Eve. Seats 1→2→3→4 play to the right.')
    print(f'Bot policy: {args.bot}')
    if args.temperature or args.random_ties or args.max_score_gap is not None:
        print(f'Experimental sampling: temperature={args.temperature}, '
              f'random ties={args.random_ties}, max score gap={args.max_score_gap}')
    if not args.demo:
        print('Type q to quit; tichu [seat] calls before that human plays their first card.')
    try:
        while match.winner is None:
            game = match.round
            print(f'\nRound {game.number}')
            if args.demo:
                while game.phase != 'over':
                    agent_step(game, bots[current_actor(game)])
                print(f'Round score: {game.scores[0]} : {game.scores[1]}')
            else:
                console.play_round(game)
            match.next_round()
            print(f'Match score: {match.scores[0]} : {match.scores[1]}')
        print('Winners: ' + ('Alice + Charlie' if match.winner == 0 else 'Bob + Eve'))
    except (QuitGame, EOFError, KeyboardInterrupt):
        print('\nGame ended. No match result recorded for an unfinished round.')
    return 0
