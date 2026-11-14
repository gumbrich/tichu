"""Account-free Dave Orr benchmark bridge. No opponent hands cross this boundary.

The pinned external engine referees both teams. Its legal moves are independently
checked against our generator plus the documented external wish/bomb convention.
Failures stop the experiment; there is no substitute move or fallback agent.
"""
import argparse
from dataclasses import replace
import hashlib
import gzip
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

from .agents import Observation, load_agent
from .cards import Card, DOG, MAHJONG, PHOENIX, DRAGON
from .combinations import Combination, classify, legal_plays
from .game import PublicAction

EXTERNAL_REV = 'ede1c2948eff1bcbc27bafd8c8af385253475b59'
ROOT = Path(__file__).resolve().parents[1]
SUITS = ('jade', 'sword', 'pagoda', 'star')
SPECIALS = {'dog': DOG, 'mahjong': MAHJONG, 'phoenix': PHOENIX, 'dragon': DRAGON}
KINDS = {'single': 'single', 'pair': 'pair', 'triple': 'triple',
         'fullHouse': 'full_house', 'straight': 'straight',
         'consecutivePairs': 'pairs', 'fourOfAKindBomb': 'four_bomb',
         'straightFlushBomb': 'straight_bomb'}


def card_from_wire(value):
    if value['type'] == 'normal':
        return Card(SUITS.index(value['suit']), value['rank'])
    if value['type'] == 'special':
        return Card(4, SPECIALS[value['name']])
    raise ValueError('Unknown card type')


def card_to_wire(card):
    if card.suit < 4:
        return {'type': 'normal', 'suit': SUITS[card.suit], 'rank': card.rank}
    return {'type': 'special', 'name': next(k for k, v in SPECIALS.items() if v == card.rank)}


def combo_from_wire(value):
    if value is None:
        return None
    cards = tuple(sorted(map(card_from_wire, value['cards'])))
    kind = 'dog' if cards == (Card(4, DOG),) else KINDS[value['type']]
    # The external engine uses 15 for the Dragon's play strength; ours uses 16.
    rank = DRAGON if cards == (Card(4, DRAGON),) and value['rank'] == 15 else value['rank']
    combo = Combination(cards, kind, rank, value.get('phoenixAs'))
    if len(cards) != value['length']:
        raise ValueError('Combination length mismatch')
    readings = classify(cards)
    if cards == (Card(4, PHOENIX),):
        if kind != 'single' or not 1.5 <= combo.rank <= 14.5:
            raise ValueError('Invalid Phoenix singleton')
    elif combo not in readings:
        raise ValueError(f'External combination does not classify: {combo!r}')
    return combo


def public_history(log):
    """Reconstruct prior tops/wishes from public actions, excluding private passes.

    External on-turn bombs are wish-exempt too. Label them 'bomb' so our history
    inference cannot mistake that exemption for proof of rank absence.
    """
    top = winner = wish = None
    events = []
    for action in log:
        kind = action['type']
        if kind == 'wish':
            wish = action['rank']
        elif kind in ('resolveTrick', 'giveDragon'):
            top = winner = None
        elif kind in ('play', 'bomb'):
            cards = tuple(sorted(map(card_from_wire, action['cards'])))
            readings = classify(cards)
            if cards == (Card(4, PHOENIX),):
                combo = replace(readings[0], rank=top.rank + .5 if top else 1.5)
            else:
                phoenix = action.get('phoenixAs')
                matches = [c for c in readings if c.phoenix_rank == phoenix]
                if len(matches) != 1:
                    raise ValueError('Ambiguous or invalid public play')
                combo = matches[0]
            event_kind = 'bomb' if kind == 'bomb' or combo.is_bomb else 'play'
            events.append(PublicAction(action['seat'], event_kind, combo, top, winner, wish))
            if any(c.rank == wish for c in cards):
                wish = None
            if combo.kind == 'dog':
                top = winner = None
            else:
                top, winner = combo, action['seat']
        elif kind == 'passTurn':
            events.append(PublicAction(action['seat'], 'pass', None, top, winner, wish))
        elif kind not in ('grandTichu', 'smallTichu', 'passCards'):
            raise ValueError(f'Unknown public action: {kind}')
    return tuple(events)


def observation(request):
    view = request['view']
    if view['settings']['clockwise']:
        raise ValueError('Only seat+1 play direction is supported')
    seat = view['seat']
    for action in view['log']:
        if action['type'] == 'passCards' and action['seat'] != seat:
            raise ValueError('Private opponent exchange leaked into player view')
    players = view['players']
    hand = tuple(sorted(map(card_from_wire, view['hand'])))
    if len(set(hand)) != len(hand) or len(hand) != players[seat]['card_count']:
        raise ValueError('Hand count or uniqueness mismatch')
    sent = ()
    if view['my_pass'] is not None:
        sent = tuple(sorted(((seat + offset) % 4, card_from_wire(view['my_pass'][key]))
                            for key, offset in (('right', 1), ('partner', 2), ('left', 3))))
    phase = {'grand': 'grand', 'exchange': 'exchange', 'dragon': 'dragon',
             'bomb': 'bomb_window'}.get(request['kind'], 'playing')
    wire_plays = tuple(map(combo_from_wire, request.get('plays', [])))
    top = combo_from_wire(view['current_trick'])
    # Preserve our frozen policy's original move ordering, including wild readings.
    generated = legal_plays(hand, top)
    if request['kind'] in ('play', 'bomb'):
        if request['kind'] == 'bomb':
            expected = tuple(c for c in generated if c.is_bomb)
            can_pass = True
        else:
            fulfills = lambda c: any(card.rank == view['wish'] for card in c.cards)
            required = view['wish'] is not None and any(fulfills(c) for c in generated)
            expected = tuple(c for c in generated if not required or c.is_bomb or fulfills(c))
            can_pass = top is not None and not required
        if set(wire_plays) != set(expected) or len(wire_plays) != len(set(wire_plays)):
            raise ValueError(f'Legal-move disagreement: missing={set(expected)-set(wire_plays)!r}; '
                             f'extra={set(wire_plays)-set(expected)!r}')
        if request['can_pass'] != can_pass:
            raise ValueError('Pass legality disagreement')
        plays = expected
    else:
        plays = ()
        can_pass = False
    outs = tuple(sorted((s for s in range(4) if players[s]['out_order']),
                        key=lambda s: players[s]['out_order']))
    public = tuple(sorted(map(card_from_wire, view['played_cards'])))
    if len(set(public)) != len(public) or set(public) & set(hand):
        raise ValueError('Public-card conservation disagreement')
    return Observation(
        seat, phase, hand, tuple(p['card_count'] for p in players),
        tuple({'none': 0, 'small': 100, 'grand': 200}[p['tichu']] for p in players),
        players[seat]['has_played_first_card'], top, view['last_played_by'], view['wish'],
        outs, public, sent, plays, can_pass,
        sum(card_from_wire(c).points for p in view['trick_plays'] for c in p['combo']['cards']),
        public_history(view['log']), tuple(view.get('scores', (0, 0))),
        view['settings'].get('target_score', 1000))


class Bridge:
    def __init__(self, candidate='competitive', model=None):
        self.agent = load_agent(candidate, model)

    def respond(self, request):
        obs = observation(request)
        kind = request['kind']
        if kind == 'grand':
            return self.agent.choose(obs).call
        if kind == 'small':
            # The external simulator offers calls to all seats before play. Our
            # frozen policy calls on its own turn, so do not add earlier calls.
            if request['view']['turn'] != obs.seat:
                return False
            generated = legal_plays(obs.hand, obs.top)
            fulfills = lambda c: any(card.rank == obs.wish for card in c.cards)
            required = obs.wish is not None and any(map(fulfills, generated))
            plays = tuple(c for c in generated if not required or c.is_bomb or fulfills(c))
            return self.agent.choose(replace(obs, plays=plays,
                                            can_pass=obs.top is not None and not required)).call
        if kind == 'wish':
            if hasattr(self.agent, 'wish'):
                return self.agent.wish(obs)
            return next((c.rank for s, c in obs.sent if s == (obs.seat + 1) % 4
                         and 2 <= c.rank <= 14 and c not in obs.public_cards), None)
        decision = self.agent.choose(obs)
        if kind == 'exchange':
            gifts = dict(decision.gifts)
            return {key: card_to_wire(gifts[(obs.seat + offset) % 4])
                    for key, offset in (('left', 3), ('partner', 2), ('right', 1))}
        if kind == 'dragon':
            return decision.recipient
        if kind in ('play', 'bomb'):
            if decision.play is None:
                if not obs.can_pass:
                    raise ValueError('Policy declined a mandatory play')
                return None
            return tuple(map(combo_from_wire, request['plays'])).index(decision.play)
        raise ValueError(f'Unknown request kind {kind}')


def serve(candidate='competitive', model=None):
    bridge = Bridge(candidate, model)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            reply = {'id': request['id'], 'value': bridge.respond(request)}
        except Exception as exc:
            reply = {'id': request['id'], 'error': f'{type(exc).__name__}: {exc}'}
        print(json.dumps(reply), flush=True)
        if 'error' in reply:
            return 1
    return 0


def interval(samples):
    mean = statistics.mean(samples)
    half = 1.96 * statistics.stdev(samples) / math.sqrt(len(samples)) if len(samples) > 1 else None
    return {'mean': mean, 'ci95': [mean-half, mean+half] if half is not None else None}


def summarize(records, expected):
    if len(records) != expected or {r['pair'] for r in records} != set(range(expected)):
        raise ValueError('Incomplete or duplicate pairs; no aggregate strength result')
    if any('error' in r for r in records):
        raise ValueError('Failed pairs; no aggregate strength result')
    for record in records:
        if len(record['games']) != 2 or [g['our_team'] for g in record['games']] != [0, 1]:
            raise ValueError('Missing swapped seating')
        for game in record['games']:
            totals = [0, 0]
            for round_ in game['rounds']:
                score = audit_score(round_)
                totals = [a+b for a, b in zip(totals, score)]
                if totals != round_['scores']:
                    raise ValueError('Cumulative score mismatch')
            team = game['our_team']
            if game['scores'] != totals or game['our_margin'] != totals[team]-totals[1-team]:
                raise ValueError('Final score mismatch')
    samples = [statistics.mean(g['our_margin'] for g in r['games']) for r in records]
    games = [g for r in records for g in r['games']]
    rounds = [rr for g in games for rr in g['rounds']]
    result = {'pairs': len(records), 'games_or_rounds': len(games), 'rounds': len(rounds),
              'paired_margin': interval(samples), 'errors': 0, 'fallbacks': 0,
              'decision_requests': sum(g['requests'] for g in games),
              'max_python_request_ms': max(g['max_request_ms'] for g in games)}
    if records[0]['mode'] == 'games':
        paired_wins = [statistics.mean(g['our_win'] for g in r['games']) for r in records]
        result['match_win_rate'] = interval(paired_wins)
        result['match_wins'] = sum(g['our_win'] for g in games)
    else:
        result['round_wins'] = sum(g['our_margin'] > 0 for g in games)
        result['round_ties'] = sum(g['our_margin'] == 0 for g in games)
    for label, ours in (('ours', True), ('opponent', False)):
        calls = made = grands = grand_made = doubles = firsts = 0
        for game in games:
            team = game['our_team'] if ours else 1-game['our_team']
            for rr in game['rounds']:
                r = rr['result']
                first = r['out_order'][0]
                firsts += first % 2 == team
                doubles += r['double_victory'] == team
                for seat in (team, team+2):
                    if r['tichu_calls'][seat] == 'small':
                        calls += 1
                        made += seat == first
                    elif r['tichu_calls'][seat] == 'grand':
                        grands += 1
                        grand_made += seat == first
        result[label] = {'small_calls': calls, 'small_made': made, 'grand_calls': grands,
                         'grand_made': grand_made, 'double_victories': doubles, 'first_out': firsts}
    return result


def audit_score(round_):
    """Independent point/call accounting from the external terminal state."""
    players = round_['final_players']
    actual_outs = sorted((s for s in range(4) if players[s]['out_order']),
                         key=lambda s: players[s]['out_order'])
    order = actual_outs + [s for s in range(4) if s not in actual_outs]
    first, second, last = order[0], order[1], order[-1]
    all_cards = [card_from_wire(c) for p in players for c in p['hand']]
    all_cards += [card_from_wire(c) for p in players for trick in p['tricks_won'] for c in trick]
    if Card(4, DOG) not in all_cards:
        all_cards.append(Card(4, DOG))  # A played Dog is not captured in a trick.
    from .tactics import ALL_CARDS
    if len(all_cards) != 56 or set(all_cards) != ALL_CARDS:
        raise ValueError('End-of-round card conservation failed')
    points, bonuses = [0, 0], [0, 0]
    double = first % 2 if first % 2 == second % 2 else None
    if double is not None:
        points[double] = 200
    else:
        for s, p in enumerate(players):
            recipient = first if s == last else s
            points[recipient % 2] += sum(card_from_wire(c).points for t in p['tricks_won'] for c in t)
            points[1-last % 2] += sum(card_from_wire(c).points for c in p['hand'])
    for s, p in enumerate(players):
        bonus = {'none': 0, 'small': 100, 'grand': 200}[p['tichu']]
        bonuses[s % 2] += bonus if s == first else -bonus
    result = round_['result']
    if (points != result['card_points'] or bonuses != result['tichu_bonuses']
            or order != result['out_order'] or double != result['double_victory']
            or [p['tichu'] for p in players] != result['tichu_calls']):
        raise ValueError('Independent round scoring disagrees')
    return [a+b for a, b in zip(points, bonuses)]


def benchmark(args):
    if args.candidate == 'partnership' and not args.model:
        raise ValueError('Experimental partnership policy requires --model')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    model = Path(args.model).resolve() if args.model else (
        ROOT/'tichu/scoring_weights.json' if args.candidate == 'scoring'
        else ROOT/'tichu/competitive_weights.json')
    if args.candidate == 'scoring' and not args.model and not model.exists():
        from .scoring import initial_spec
        (output/'candidate.json').write_text(json.dumps(initial_spec(), indent=2)+'\n')
    else:
        (output/'candidate.json').write_bytes(model.read_bytes())
    snapshot = (output/'candidate.json').resolve()
    command = [str(Path(args.binary).resolve()), args.opponent, str(args.pairs),
               str(args.seed), str(args.workers), args.mode, sys.executable, str(ROOT),
               args.candidate, str(snapshot)]
    manifest = {'external_repository': 'https://github.com/dave-orr/Tichu-ai',
                'external_revision': EXTERNAL_REV, 'opponent': args.opponent,
                'our_bot': args.candidate, 'our_git_revision': subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'model_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                'binary_sha256': hashlib.sha256(Path(args.binary).read_bytes()).hexdigest(),
                'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'seed': args.seed, 'pairs': args.pairs, 'mode': args.mode, 'workers': args.workers,
                'referee': 'pinned external engine; default counterclockwise rules',
                'command': command, 'status': 'running'}
    manifest_path = output/'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    start = time.monotonic()
    try:
        with (output/'pairs.jsonl').open('w') as raw, (output/'stderr.log').open('w') as errors:
            proc = subprocess.run(command, cwd=ROOT, stdout=raw, stderr=errors, check=False)
        if proc.returncode:
            raise RuntimeError(f'Bridge exited {proc.returncode}; inspect {output}/stderr.log')
        records = [json.loads(line) for line in (output/'pairs.jsonl').read_text().splitlines()]
        report = summarize(records, args.pairs)
        report['elapsed_seconds'] = time.monotonic()-start
        (output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
        with gzip.open(output/'pairs.jsonl.gz', 'wt') as compressed:
            for record in sorted(records, key=lambda r: r['pair']):
                compressed.write(json.dumps(record, separators=(',', ':'))+'\n')
        (output/'pairs.jsonl').unlink()
        manifest['status'] = 'complete'
        print(json.dumps(report, indent=2))
    except BaseException:
        manifest['status'] = 'failed'
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    server = sub.add_parser('serve')
    server.add_argument('--candidate', choices=('competitive', 'scoring', 'partnership'), default='competitive')
    server.add_argument('--model')
    run = sub.add_parser('benchmark')
    run.add_argument('--binary', default='tools/dave_bridge/target/release/tichu-external-benchmark')
    run.add_argument('--opponent', default='pimc20')
    run.add_argument('--candidate', choices=('competitive', 'scoring', 'partnership'), default='competitive')
    run.add_argument('--model')
    run.add_argument('--pairs', type=int, default=1000)
    run.add_argument('--seed', type=int, default=14000000)
    run.add_argument('--workers', type=int, default=4)
    run.add_argument('--mode', choices=('rounds', 'games'), default='rounds')
    run.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'serve':
        return serve(args.candidate, args.model)
    if args.pairs < 1 or args.workers < 1 or args.seed < 0:
        parser.error('pairs/workers must be positive and seed nonnegative')
    benchmark(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
