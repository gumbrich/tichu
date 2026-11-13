"""Controlled temperature experiment; never replaces the shipped checkpoint.

Tune six sampling settings against two frozen opponents, select one, then test
on untouched round and full-match seeds. No heuristic weights are retrained.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import statistics

from .selfplay import agent_spec, evaluate, paired_score_difference
from .tactics import DEFAULT_COMPETITIVE_MODEL

SETTINGS = [('ties', {'temperature': 0., 'random_ties': True}),
            ('temperature-0.1', {'temperature': .1}),
            ('temperature-0.5', {'temperature': .5}),
            ('temperature-1', {'temperature': 1.}),
            ('temperature-3', {'temperature': 3.}),
            ('near-best', {'temperature': 1., 'max_gap': 1.})]


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def run(output, *, tuning_pairs=200, test_pairs=1000, match_pairs=150, workers=4):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    frozen = agent_spec('competitive')
    opponents = {'v2': frozen, 'v1': agent_spec('trained')}
    tuning = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for name, options in [('deterministic', None)] + SETTINGS:
            spec = frozen if options is None else {
                **frozen, 'name': 'stochastic', 'options': options, 'policy_seed': 819}
            tuning[name] = {}
            for opponent_name, opponent in opponents.items():
                result = evaluate(spec, opponent, range(9000000, 9000000 + tuning_pairs), pool=pool)
                tuning[name][opponent_name] = result
                write(output / f'tuning-{name}-v-{opponent_name}.json', result)
                print(f"tuning {name} vs {opponent_name}: {result['summary']['mean_score_difference']:+.2f}", flush=True)
        ranking = sorted((name for name, _ in SETTINGS), key=lambda name: statistics.mean(
            r['summary']['mean_score_difference'] for r in tuning[name].values()), reverse=True)
        selected = ranking[0]
        candidate = tuning[selected]['v2']['candidate']
        selection = {'selected': selected, 'candidate': candidate, 'ranking': ranking,
                     'criterion': 'highest mean team score margin equally weighted across frozen v2 and v1',
                     'tuning': {name: {opp: r['summary'] for opp, r in results.items()}
                                for name, results in tuning.items()},
                     'paired_tuning_deltas': {name: {opp: paired_score_difference(r, tuning['deterministic'][opp])
                                                    for opp, r in results.items()}
                                             for name, results in tuning.items() if name != 'deterministic'}}
        write(output / 'selection.json', selection)
        print(f'Selected {selected}; now freezing it for held-out tests.', flush=True)
        heldout = {}
        for name, opponent, mode, start, count in [
                ('rounds-v-v2', frozen, 'round', 10000000, test_pairs),
                ('rounds-v-v1', opponents['v1'], 'round', 10000000, test_pairs),
                ('matches-v-v2', frozen, 'match', 11000000, match_pairs)]:
            result = evaluate(candidate, opponent, range(start, start + count), mode=mode, pool=pool)
            heldout[name] = result['summary']
            write(output / f'{name}.json', result)
            print(f"{name}: {result['summary']['mean_score_difference']:+.2f} points, "
                  f"{result['summary']['win_rate']:.1%} wins", flush=True)
    score_ci = heldout['rounds-v-v2']['score_difference_95ci']
    win_ci = heldout['matches-v-v2']['win_rate_95ci']
    promoted = score_ci[0] > 0 and win_ci[0] > .5
    report = {'selected': selected, 'candidate': candidate,
              'checkpoint_sha256': hashlib.sha256(DEFAULT_COMPETITIVE_MODEL.read_bytes()).hexdigest(),
              'tuning_seed_start': 9000000, 'round_seed_start': 10000000,
              'match_seed_start': 11000000, 'tuning_pairs': tuning_pairs,
              'test_pairs': test_pairs, 'match_pairs': match_pairs,
              'policy_seed': 819, 'policy_seed_derivation': 'SHA256(policy:root:deal_seed:seat) first 8 bytes big-endian',
              'gate': 'round score lower 95% CI > 0 AND full-match win lower 95% CI > 0.5 against frozen v2',
              'promotion_gate_passed': promoted, 'results': heldout}
    write(output / 'summary.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tuning-pairs', type=int, default=200)
    parser.add_argument('--test-pairs', type=int, default=1000)
    parser.add_argument('--match-pairs', type=int, default=150)
    parser.add_argument('--workers', type=int, default=4)
    args = vars(parser.parse_args())
    if args['workers'] < 1 or any(args[k] < 2 or args[k] > 1000000 for k in ('tuning_pairs', 'test_pairs', 'match_pairs')):
        parser.error('Use positive workers and 2..1000000 pairs per phase')
    run(**args)


if __name__ == '__main__':
    main()
