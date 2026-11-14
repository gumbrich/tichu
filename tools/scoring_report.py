"""Account for paired round-score changes without treating them as causal effects."""
import argparse
import gzip
import json
from pathlib import Path

from tichu.external import interval
from tichu.improve import paired_change

COMPONENTS = ('ordinary_card_points', 'double_victory_points', 'small_calls', 'grand_calls')


def components(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text())
    if manifest['status'] != 'complete' or manifest['mode'] != 'rounds':
        raise ValueError('Need a completed paired round experiment')
    pairs = {}
    with gzip.open(directory/'pairs.jsonl.gz', 'rt') as handle:
        for record in map(json.loads, handle):
            values = dict.fromkeys(COMPONENTS, 0.0)
            for game in record['games']:
                assert len(game['rounds']) == 1
                r = game['rounds'][0]['result']
                team = game['our_team']
                card = r['card_points'][team]-r['card_points'][1-team]
                key = 'ordinary_card_points' if r['double_victory'] is None else 'double_victory_points'
                parts = dict.fromkeys(COMPONENTS, 0)
                parts[key] = card
                for seat, call in enumerate(r['tichu_calls']):
                    if call == 'none':
                        continue
                    bonus = 200 if call == 'grand' else 100
                    bonus *= 1 if r['out_order'][0] == seat else -1
                    parts[call+'_calls'] += bonus if seat % 2 == team else -bonus
                assert sum(parts.values()) == game['our_margin']
                for key, value in parts.items():
                    values[key] += value/2
            pairs[record['pair']] = values
    return pairs


def match_win_change(candidate, baseline):
    paired_change(candidate, baseline)  # Also verifies matching experiment manifests.
    def wins(directory):
        manifest = json.loads((Path(directory)/'manifest.json').read_text())
        if manifest['mode'] != 'games':
            raise ValueError('Need full-match experiments')
        values = {}
        with gzip.open(Path(directory)/'pairs.jsonl.gz', 'rt') as handle:
            for record in map(json.loads, handle):
                for game in record['games']:
                    assert game['our_win'] == (game['our_margin'] > 0)
                values[record['pair']] = sum(g['our_win'] for g in record['games'])/2
        return values
    a, b = wins(candidate), wins(baseline)
    return interval([a[i]-b[i] for i in sorted(a)])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    total = paired_change(args.candidate, args.baseline)
    a, b = components(args.candidate), components(args.baseline)
    report = {'unit': 'points per round; paired deal is the uncertainty unit',
              'interpretation': 'Score accounting, not causal feature effects; policy changes alter trajectories.',
              'total_improvement': total,
              'candidate': {k: interval([a[i][k] for i in sorted(a)]) for k in COMPONENTS},
              'baseline': {k: interval([b[i][k] for i in sorted(b)]) for k in COMPONENTS},
              'change': {k: interval([a[i][k]-b[i][k] for i in sorted(a)]) for k in COMPONENTS}}
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
