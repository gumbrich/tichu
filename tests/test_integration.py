"""Whole-game checks exercise transitions and global invariants, not just examples."""
import contextlib
import io
import random
import subprocess
import sys
import unittest
from pathlib import Path

from tichu.cards import Card, Deck, MAHJONG
from tichu.cli import Console, QuitGame, bot_step, main
from tichu.game import Match, Round

ROOT = Path(__file__).resolve().parents[1]


def all_cards(game):
    return (game.deck.cards + game.pile + game.discarded +
            [c for p in game.players for c in p.hand + p.stack])


def random_step(game, rng):
    if game.phase == 'grand':
        game.decide_grand(min(game.grand_pending), rng.random() < .2)
    elif game.phase == 'exchange':
        seat = next(s for s in range(4) if s not in game.exchanges)
        gifts = rng.sample(game.players[seat].hand, 3)
        game.exchange(seat, dict(zip([(seat + i) % 4 for i in (1, 2, 3)], gifts)))
    elif game.phase == 'dragon':
        game.give_dragon(game.actor, (game.actor + rng.choice((1, 3))) % 4)
    else:
        seat = game.actor
        if not game.players[seat].has_played and not game.players[seat].call and rng.random() < .08:
            game.call_tichu(seat)
        if game.phase == 'bomb_window':
            moves = game.available_plays(seat, interrupt=True)
            if moves and rng.random() < .4:
                game.bomb(seat, rng.choice(moves))
            else:
                game.decline_bomb(seat)
        else:
            moves = game.available_plays(seat)
            if not moves or (game.can_pass(seat) and rng.random() < .25):
                game.pass_turn(seat)
            else:
                move = rng.choice(moves)
                wish = rng.randint(2, 14) if any(c.rank == MAHJONG for c in move.cards) else None
                game.play(seat, move, wish)


class SimulationTests(unittest.TestCase):
    def test_randomized_rounds_conserve_cards_and_score(self):
        expected = set(Deck().cards)
        for seed in range(40):
            with self.subTest(seed=seed):
                game = Round(rng=random.Random(seed))
                rng = random.Random(seed + 1000)
                steps = 0
                while game.phase != 'over':
                    random_step(game, rng)
                    actual = all_cards(game)
                    self.assertEqual(len(actual), 56)
                    self.assertEqual(set(actual), expected)
                    self.assertEqual(len(game.finish_order), len(set(game.finish_order)))
                    if game.phase in ('playing', 'bomb_window'):
                        self.assertTrue(game.players[game.actor].hand)
                    steps += 1
                    self.assertLess(steps, 5000, 'A round must make progress')
                adjustments = sum(p.call if p.number == game.finish_order[0] else -p.call
                                  for p in game.players)
                base = 200 if game.finish_order[0] % 2 == game.finish_order[1] % 2 else 100
                self.assertEqual(sum(game.scores) - adjustments, base)

    def test_full_match_is_reproducible_and_resets_rounds(self):
        histories = []
        for _ in range(2):
            match = Match(seed=7)
            for _ in range(100):
                while match.round.phase != 'over':
                    bot_step(match.round)
                match.next_round()
                if match.winner is not None:
                    break
                self.assertEqual([len(p.hand) for p in match.round.players], [8] * 4)
                self.assertFalse(any(p.stack or p.call or p.has_played for p in match.round.players))
                self.assertIsNone(match.round.wish)
            self.assertIsNotNone(match.winner)
            self.assertGreaterEqual(max(match.scores), 1000)
            histories.append(match.history)
        self.assertEqual(*histories)
        # Frozen baseline: refactoring agents must not weaken the comparison bot.
        self.assertEqual(histories[0], [(0, 200), (60, 40), (80, 20), (200, 0),
                                       (45, 55), (80, 20), (20, 80), (200, 0),
                                       (200, 0), (200, 0)])


class ConsoleTests(unittest.TestCase):
    def test_import_is_quiet_and_demo_completes(self):
        imported = subprocess.run([sys.executable, '-c', 'import main'], cwd=ROOT,
                                  text=True, capture_output=True, check=True)
        self.assertEqual(imported.stdout, '')
        result = subprocess.run([sys.executable, 'main.py', '--demo', '--seed', '7',
                                 '--target', '100'], cwd=ROOT, text=True,
                                capture_output=True, check=True)
        self.assertIn('Winners:', result.stdout)
        self.assertEqual(result.stderr, '')

    def test_human_game_end_to_end_with_hidden_handoff(self):
        game = Round(rng=random.Random(11))
        prompts = []
        output = []

        def read(prompt):
            prompts.append(prompt)
            if 'Pass the terminal' in prompt:
                return ''
            if 'Grand Tichu' in prompt:
                return 'no'
            if 'Give three card' in prompt:
                return '3 1 2'
            if 'Choose Phoenix' in prompt:
                return '1'
            if 'Wish rank' in prompt:
                return '8'
            if 'Give Dragon' in prompt:
                return str((game.actor + 1) % 4 + 1)
            if 'Bomb response' in prompt:
                return ''
            plays = game.available_plays(game.actor)
            if not plays:
                return 'pass'
            move = min(plays, key=lambda c: (-len(c.cards), c.rank))
            hand = sorted(game.players[game.actor].hand, key=lambda c: (c.rank, c.suit))
            return ' '.join(str(hand.index(card) + 1) for card in move.cards)

        Console(humans=4, read=read, write=output.append).play_round(game)
        self.assertEqual(game.phase, 'over')
        self.assertTrue(any('Pass the terminal' in p for p in prompts))
        self.assertTrue(any('Round score:' in line for line in output))
        self.assertFalse(any('Please try again' in line for line in output))

    def test_bad_input_and_quit_are_clean(self):
        game = Round(rng=random.Random(0))
        answers = iter(['maybe', 'tichu 5', 'q'])
        output = []
        with self.assertRaises(QuitGame):
            Console(read=lambda _: next(answers), write=output.append).human_step(game, 0)
        self.assertTrue(any('Enter yes or no' in line for line in output))
        self.assertEqual(game.phase, 'grand')
        self.assertEqual(len(game.players[0].hand), 8)
        with self.assertRaises(ValueError):
            Console.select('1 1 2', game.players[0].hand, 3)
        with self.assertRaises(ValueError):
            Console.select('0', game.players[0].hand)

    def test_exchange_input_order_and_call(self):
        game = Round(rng=random.Random(5))
        for seat in range(4):
            game.decide_grand(seat)
        hand = sorted(game.players[0].hand, key=lambda c: (c.rank, c.suit))
        answers = iter(['tichu', '3 1 2'])
        Console(read=lambda _: next(answers), write=lambda _: None).human_step(game, 0)
        self.assertEqual(game.players[0].call, 100)
        self.assertEqual(game.exchanges[0], {1: hand[2], 2: hand[0], 3: hand[1]})

    def test_cli_bad_target(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(['--target', '0'])
        self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
