"""External protocol tests; no Rust toolchain or downloaded engine required."""
import copy
import unittest

from tichu.cards import Card, DOG, PHOENIX, DRAGON
from tichu.combinations import legal_plays, classify
from tichu.external import (Bridge, KINDS, audit_score, card_from_wire,
                            card_to_wire, combo_from_wire, observation,
                            public_history, summarize)
from tichu.tactics import ALL_CARDS, proven_voids


def wire_combo(combo):
    value = {'type': 'single' if combo.kind == 'dog' else
             next(k for k, v in KINDS.items() if v == combo.kind),
             'cards': list(map(card_to_wire, combo.cards)), 'rank': combo.rank,
             'length': len(combo.cards)}
    if combo.cards == (Card(4, DRAGON),):
        value['rank'] = 15
    if combo.phoenix_rank is not None:
        value['phoenixAs'] = combo.phoenix_rank
    return value


def request(hand, top=None, wish=None, kind='play'):
    generated = legal_plays(hand, top)
    fulfills = lambda c: any(card.rank == wish for card in c.cards)
    required = wish is not None and any(map(fulfills, generated))
    plays = [c for c in generated if not required or c.is_bomb or fulfills(c)]
    if kind == 'bomb':
        plays = [c for c in generated if c.is_bomb]
    players = [dict(card_count=len(hand) if s == 0 else 14, tichu='none',
                    out_order=0, has_played_first_card=True) for s in range(4)]
    view = dict(seat=0, settings={'clockwise': False}, players=players,
                hand=list(map(card_to_wire, hand)), log=[], my_pass=None,
                current_trick=wire_combo(top) if top else None, last_played_by=1 if top else None,
                wish=wish, played_cards=[], trick_plays=[], turn=0)
    return dict(id=1, kind=kind, view=view, plays=list(map(wire_combo, reversed(plays))),
                can_pass=kind == 'bomb' or top is not None and not required)


class ExternalProtocolTests(unittest.TestCase):
    def test_all_cards_round_trip(self):
        self.assertEqual(len({str(card_to_wire(c)) for c in ALL_CARDS}), 56)
        for c in ALL_CARDS:
            self.assertEqual(card_from_wire(card_to_wire(c)), c)

    def test_dragon_strength_and_contextual_phoenix(self):
        dragon = classify([Card(4, DRAGON)])[0]
        self.assertEqual(combo_from_wire(wire_combo(dragon)), dragon)
        ace = classify([Card(0, 14)])[0]
        obs = observation(request([Card(4, PHOENIX)], ace))
        self.assertEqual(obs.plays[0].rank, 14.5)
        self.assertFalse(observation(request([Card(4, PHOENIX)], dragon)).plays)

    def test_ambiguous_phoenix_and_original_order(self):
        hand = [Card(0, 7), Card(1, 7), Card(0, 8), Card(1, 8), Card(4, PHOENIX)]
        obs = observation(request(hand))
        self.assertEqual(obs.plays, legal_plays(hand))
        self.assertEqual({p.rank for p in obs.plays if p.kind == 'full_house'}, {7, 8})

    def test_wish_exempt_external_bomb(self):
        hand = [Card(s, 3) for s in range(4)] + [Card(0, 7)]
        top = classify([Card(0, 2)])[0]
        obs = observation(request(hand, top, 7))
        self.assertFalse(obs.can_pass)
        self.assertTrue(any(p.is_bomb for p in obs.plays))
        self.assertEqual(len(obs.plays), 2)
        interrupt = observation(request(hand, top, 7, 'bomb'))
        self.assertTrue(interrupt.can_pass)
        self.assertTrue(all(p.is_bomb for p in interrupt.plays))

    def test_reject_missing_move_duplicate_move_and_bad_pass(self):
        original = request([Card(0, 2), Card(1, 3)])
        for mutation in ('missing', 'duplicate', 'pass'):
            bad = copy.deepcopy(original)
            if mutation == 'missing':
                bad['plays'].pop()
            elif mutation == 'duplicate':
                bad['plays'].append(bad['plays'][0])
            else:
                bad['can_pass'] = True
            with self.assertRaises(ValueError):
                observation(bad)

    def test_reject_private_exchange_and_public_card_leak(self):
        original = request([Card(0, 2)])
        bad = copy.deepcopy(original)
        bad['view']['log'] = [{'type': 'passCards', 'seat': 1, 'pass': {}}]
        with self.assertRaisesRegex(ValueError, 'Private opponent'):
            observation(bad)
        bad = copy.deepcopy(original)
        bad['view']['played_cards'] = bad['view']['hand']
        with self.assertRaisesRegex(ValueError, 'conservation'):
            observation(bad)

    def test_gifts_keep_recipients(self):
        req = request([Card(0, 2)])
        gifts = {'right': card_to_wire(Card(0, 3)), 'partner': card_to_wire(Card(0, 14)),
                 'left': card_to_wire(Card(4, DOG))}
        req['view']['my_pass'] = gifts
        self.assertEqual(dict(observation(req).sent),
                         {1: Card(0, 3), 2: Card(0, 14), 3: Card(4, DOG)})

    def test_history_on_turn_bomb_does_not_prove_void(self):
        log = [{'type': 'wish', 'seat': 0, 'rank': 7},
               {'type': 'play', 'seat': 1, 'cards': [card_to_wire(Card(s, 3)) for s in range(4)],
                'phoenixAs': None}, {'type': 'resolveTrick'},
               {'type': 'play', 'seat': 3, 'cards': [card_to_wire(Card(0, 2))], 'phoenixAs': None},
               {'type': 'passTurn', 'seat': 2}]
        history = public_history(log)
        self.assertEqual(history[0].kind, 'bomb')
        self.assertFalse(proven_voids(history)[1])
        self.assertEqual(proven_voids(history)[2], frozenset({7}))

    def test_frozen_grand_and_wish_behavior(self):
        bridge = Bridge()
        req = request([Card(0, 2)], kind='grand')
        self.assertFalse(bridge.respond(req))
        req['kind'] = 'wish'
        req['view']['my_pass'] = {'right': card_to_wire(Card(0, 8)),
                                  'partner': card_to_wire(Card(0, 14)),
                                  'left': card_to_wire(Card(4, DOG))}
        self.assertEqual(bridge.respond(req), 8)

    def test_score_audit_and_missing_card(self):
        players = [dict(hand=[], tricks_won=[], out_order=s+1 if s < 3 else 0,
                        tichu='small' if s == 0 else 'none') for s in range(4)]
        players[0]['tricks_won'] = [list(map(card_to_wire, sorted(ALL_CARDS)))]
        round_ = {'final_players': players, 'result': {
            'card_points': [100, 0], 'tichu_bonuses': [100, 0],
            'out_order': [0, 1, 2, 3], 'double_victory': None,
            'tichu_calls': ['small', 'none', 'none', 'none']}}
        self.assertEqual(audit_score(round_), [200, 0])
        players[0]['tricks_won'][0].pop(0)
        with self.assertRaisesRegex(ValueError, 'conservation'):
            audit_score(round_)

    def test_failed_incomplete_and_duplicate_pairs_not_reported(self):
        for records in ([], [{'pair': 0, 'error': 'bad move'}],
                        [{'pair': 4}], [{'pair': 0}, {'pair': 0}]):
            with self.assertRaises(ValueError):
                summarize(records, 1)


if __name__ == '__main__':
    unittest.main()
