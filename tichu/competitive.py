"""Train public-information tactics and gate promotion against the frozen v1 bot.

Train/validation/final seed ranges are deliberately separated. Outcomes, policy
parameters and deal pairs are written to disk, including unsuccessful candidates.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import statistics

from .selfplay import (agent_spec, evaluate, paired_trial, summarize,
                       paired_score_difference, DEFAULT_MODEL)
from .tactics import TacticalWeights, save_spec, load_spec, DEFAULT_COMPETITIVE_MODEL

# Existing hand/exchange weights remain fixed. Tune only play tactics here.
BOUNDS = {'tactics.secure': (0, 8), 'tactics.threat': (0, 24),
          'tactics.points': (0, .3), 'weights.urgency': (0, 10),
          'weights.lead': (0, 8), 'weights.rank': (0, .6),
          'weights.partner': (8, 32)}


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def train(output, *, generations=5, population=10, deals=64, workers=4, seed=819):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    initial = agent_spec('tactical')
    initial['tactics'] = asdict(TacticalWeights())
    champion = deepcopy(initial)
    center = deepcopy(initial)
    archive = [initial]
    history = []
    frozen = agent_spec('trained')
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for generation in range(generations):
            candidates = [champion, initial]
            for _ in range(population - 2):
                spec = deepcopy(center)
                for key, (low, high) in BOUNDS.items():
                    section, field = key.split('.')
                    sigma = (high - low) * .2 * .85 ** generation
                    spec[section][field] = min(high, max(low, rng.gauss(center[section][field], sigma)))
                candidates.append(spec)
            start = 4000000 + 1000 * generation
            seeds = list(range(start, start + deals))
            opponents = [frozen, frozen, agent_spec('strategic'), champion]
            scored = []
            for i, spec in enumerate(candidates):
                tasks = [(s, spec, opponents[j % 4], 'round', 1000) for j, s in enumerate(seeds)]
                pairs = list(pool.map(paired_trial, tasks))
                result = {'candidate': spec, 'pairs': pairs, 'summary': summarize(pairs)}
                scored.append(result)
                print(f'generation {generation + 1} candidate {i + 1}: '
                      f"{result['summary']['mean_score_difference']:+.2f}", flush=True)
            ranked = sorted(scored, key=lambda r: r['summary']['mean_score_difference'], reverse=True)
            champion = deepcopy(ranked[0]['candidate'])
            archive.append(champion)
            elite = ranked[:max(2, population // 3)]
            for key in BOUNDS:
                section, field = key.split('.')
                center[section][field] = statistics.mean(r['candidate'][section][field] for r in elite)
            history.append({'generation': generation, 'seeds': seeds,
                            'opponents': opponents, 'candidates': scored})
            write(output / 'training.json', {'seed': seed, 'history': history})
        validation = []
        for i, spec in enumerate(archive):
            result = evaluate(spec, frozen, range(5000000, 5000300), pool=pool)
            validation.append(result)
            print(f"validation checkpoint {i}: {result['summary']['mean_score_difference']:+.2f}", flush=True)
    best = max(validation, key=lambda r: r['summary']['mean_score_difference'])
    write(output / 'validation.json', {'seed': seed, 'results': validation})
    save_spec(output / 'weights.json', best['candidate'], training_seed=seed,
              training_seed_start=4000000, training_generations=generations,
              training_pairs_per_candidate=deals, population=population,
              validation_seed_range=[5000000, 5000299],
              validation_mean_score=best['summary']['mean_score_difference'],
              parent_sha256=hashlib.sha256(DEFAULT_MODEL.read_bytes()).hexdigest())


def suite(output, *, model=DEFAULT_COMPETITIVE_MODEL, pairs=1000, matches=150, workers=4):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    candidate = load_spec(model)
    frozen = agent_spec('trained')
    tests = [('v2-v-v1', candidate, frozen, 'round', pairs),
             ('v2-v-initial', candidate, agent_spec('strategic'), 'round', pairs),
             ('v2-v-baseline', candidate, agent_spec('baseline'), 'round', pairs),
             ('v2-matches-v-v1', candidate, frozen, 'match', matches),
             ('v2-matches-v-baseline', candidate, agent_spec('baseline'), 'match', matches)]
    for option in ('proofs', 'history'):
        tests.append((f'without-{option}', {**candidate, 'options': {option: False}}, frozen, 'round', pairs))
    tests.append(('without-counterplay-scores', {**candidate, 'tactics':
                  {'secure': 0, 'threat': 0, 'points': 0}}, frozen, 'round', pairs))
    detailed = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for name, spec, opponent, mode, count in tests:
            start = 6000000 if mode == 'round' else 7000000
            result = evaluate(spec, opponent, range(start, start + count), pool=pool, mode=mode)
            detailed[name] = result
            write(output / f'{name}.json', result)
            s = result['summary']
            print(f"{name}: {s['mean_score_difference']:+.2f} points, {s['win_rate']:.1%} wins", flush=True)
    round_ci = detailed['v2-v-v1']['summary']['score_difference_95ci']
    match_ci = detailed['v2-matches-v-v1']['summary']['win_rate_95ci']
    # A clear improvement over frozen v1 is necessary in BOTH settings.
    promoted = bool(round_ci and round_ci[0] > 0 and match_ci and match_ci[0] > .5)
    manifest = {'model_sha256': hashlib.sha256(Path(model).read_bytes()).hexdigest(),
                'parent_sha256': hashlib.sha256(DEFAULT_MODEL.read_bytes()).hexdigest(),
                'round_seed_start': 6000000, 'match_seed_start': 7000000,
                'pairs': pairs, 'match_pairs': matches, 'promotion_gate_passed': promoted,
                'gate': 'round margin lower 95% CI > 0 AND match win-rate lower 95% CI > 0.5 vs frozen v1',
                'results': {k: v['summary'] for k, v in detailed.items()},
                'paired_ablation_deltas': {k: paired_score_difference(detailed['v2-v-v1'], v)
                                          for k, v in detailed.items() if k.startswith('without-')}}
    write(output / 'summary.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    training = sub.add_parser('train')
    training.add_argument('--generations', type=int, default=5)
    training.add_argument('--population', type=int, default=10)
    training.add_argument('--deals', type=int, default=64)
    training.add_argument('--seed', type=int, default=819)
    evaluation = sub.add_parser('suite')
    evaluation.add_argument('--model', type=Path, default=DEFAULT_COMPETITIVE_MODEL)
    evaluation.add_argument('--pairs', type=int, default=1000)
    evaluation.add_argument('--matches', type=int, default=150)
    for command in (training, evaluation):
        command.add_argument('--workers', type=int, default=4)
        command.add_argument('--output', type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    if args['workers'] < 1:
        parser.error('--workers must be positive')
    if command == 'train' and (args['generations'] < 1 or args['population'] < 3 or not 4 <= args['deals'] <= 1000):
        parser.error('Use positive generations, population >= 3 and 4 <= deals <= 1000')
    if command == 'suite' and (args['pairs'] < 2 or args['matches'] < 2):
        parser.error('Use at least two deal/match pairs')
    (train if command == 'train' else suite)(**args)


if __name__ == '__main__':
    main()
