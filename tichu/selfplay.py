"""Reproducible paired tournaments and evolutionary self-play policy optimization.

No neural dependency or accelerator is required. Each seed is played twice with
team assignments exchanged; confidence intervals use the deal pair as the unit.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import time

from .agents import (BaselineAgent, StrategicAgent, Weights, agent_step,
                     current_actor)
from .game import Round, Match

DEFAULT_MODEL = Path(__file__).with_name('trained_weights.json')


def make_agent(spec, seed=None):
    if spec['name'] == 'scoring':
        from .scoring import ScoringAgent, ScoringWeights
        from .tactics import TacticalWeights
        return ScoringAgent(Weights(**spec['weights']), TacticalWeights(**spec['tactics']),
                            ScoringWeights(**spec['scoring']))
    if spec['name'] == 'baseline':
        return BaselineAgent()
    if spec['name'] in ('tactical', 'stochastic'):
        from .tactics import TacticalAgent, TacticalWeights
        policy = TacticalAgent
        options = spec.get('options', {}).copy()
        if spec['name'] == 'stochastic':
            from .stochastic import StochasticAgent
            policy = StochasticAgent
            options['seed'] = seed
        return policy(Weights(**spec['weights']),
                             TacticalWeights(**spec.get('tactics', {})),
                             **options)
    return StrategicAgent(Weights(**spec.get('weights', asdict(Weights()))),
                          **spec.get('options', {}))


def agent_spec(name, model=None, **options):
    if name == 'scoring':
        from .scoring import read_spec
        return read_spec(model)
    if name == 'baseline':
        return {'name': name}
    if name == 'competitive':
        from .tactics import load_spec, DEFAULT_COMPETITIVE_MODEL
        return {**load_spec(model if model is not None else DEFAULT_COMPETITIVE_MODEL),
                'options': options}
    model = model if model is not None else DEFAULT_MODEL
    weights = Weights.load(model) if name in ('trained', 'tactical') else Weights()
    return {'name': name, 'weights': asdict(weights), 'options': options}


def _play_round(game, policies, stats):
    for _ in range(5000):
        if game.phase == 'over':
            break
        seat = current_actor(game)
        # Skip forced no-ops at the coordinator, not inside the policy.
        if game.phase == 'bomb_window' and not game.available_plays(seat, interrupt=True):
            game.decline_bomb(seat)
            continue
        started = time.perf_counter()
        agent_step(game, policies[seat])
        stats['decision_seconds'][seat % 2] += time.perf_counter() - started
        stats['decisions'][seat % 2] += 1
    else:
        raise RuntimeError('Round did not terminate within 5000 actions')
    all_cards = (game.deck.cards + game.pile + game.discarded +
                 [c for p in game.players for c in p.hand + p.stack])
    if len(all_cards) != 56 or len(set(all_cards)) != 56:
        raise AssertionError('Card conservation failed')
    calls = sum(p.call if p.number == game.finish_order[0] else -p.call for p in game.players)
    base = 200 if game.finish_order[0] % 2 == game.finish_order[1] % 2 else 100
    if sum(game.scores) != base + calls:
        raise AssertionError('Score conservation failed')


def paired_trial(task):
    seed, candidate, opponent, mode, target = task
    results = []
    for side in (0, 1):
        policies = []
        for seat in range(4):
            spec = candidate if seat % 2 == side else opponent
            # Separate policy PRNGs never consume the deal shuffler. The same
            # seat uses the same stream across side swaps; seats do not share it.
            material = f"policy:{spec.get('policy_seed', 819)}:{seed}:{seat}".encode()
            policy_seed = int.from_bytes(hashlib.sha256(material).digest()[:8], 'big')
            policies.append(make_agent(spec, seed=policy_seed))
        if candidate.get('solo'):
            # One improved agent with an unchanged baseline partner. Alternate
            # its position so both seats within each partnership are represented.
            primary = side + 2 * (seed % 2)
            policies[(primary + 2) % 4] = BaselineAgent()
        stats = {'decision_seconds': [0., 0.], 'decisions': [0, 0]}
        match = Match(seed=seed, target=target)
        rounds, calls, successes, firsts, doubles = 0, 0, 0, 0, 0
        while True:
            game = match.round
            _play_round(game, policies, stats)
            rounds += 1
            firsts += game.finish_order[0] % 2 == side
            doubles += (game.finish_order[0] % 2 == game.finish_order[1] % 2 == side)
            for p in game.players:
                if p.number % 2 == side and p.call:
                    calls += 1
                    successes += p.number == game.finish_order[0]
            match.next_round()
            if mode == 'round' or match.winner is not None:
                break
            if rounds >= 200:
                raise RuntimeError('Match exceeded 200 rounds')
        difference = match.scores[side] - match.scores[1 - side]
        results.append({'score_difference': difference,
                        'win': 1. if difference > 0 else .5 if difference == 0 else 0.,
                        'rounds': rounds, 'calls': calls, 'successful_calls': successes,
                        'first_out': firsts, 'double_victories': doubles,
                        'decision_seconds': stats['decision_seconds'][side],
                        'decisions': stats['decisions'][side]})
    return {'seed': seed, 'games': results}


def summarize(pairs):
    differences = [statistics.mean(g['score_difference'] for g in p['games']) for p in pairs]
    wins = [statistics.mean(g['win'] for g in p['games']) for p in pairs]

    def interval(values, bounded=False):
        mean = statistics.mean(values)
        margin = 1.96 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None
        if margin is None:
            return None
        low, high = mean - margin, mean + margin
        return [max(0., low), min(1., high)] if bounded else [low, high]

    games = [g for p in pairs for g in p['games']]
    totals = {key: sum(g[key] for g in games) for key in
              ('rounds', 'calls', 'successful_calls', 'first_out', 'double_victories',
               'decision_seconds', 'decisions')}
    return {'deal_pairs': len(pairs), 'games': len(games),
            'mean_score_difference': statistics.mean(differences),
            'score_difference_95ci': interval(differences),
            'win_rate': statistics.mean(wins), 'win_rate_95ci': interval(wins, True),
            'call_success_rate': totals['successful_calls'] / totals['calls'] if totals['calls'] else None,
            'mean_decision_ms': 1000 * totals['decision_seconds'] / max(1, totals['decisions']),
            **totals}


def paired_score_difference(full, comparison):
    """Incremental benefit on the same deal pairs, not independent-game errors."""
    values = {p['seed']: statistics.mean(g['score_difference'] for g in p['games'])
              for p in full['pairs']}
    differences = [values[p['seed']] - statistics.mean(g['score_difference'] for g in p['games'])
                   for p in comparison['pairs']]
    mean = statistics.mean(differences)
    margin = (1.96 * statistics.stdev(differences) / math.sqrt(len(differences))
              if len(differences) > 1 else None)
    return {'mean_points_per_round': mean,
            '95ci': [mean - margin, mean + margin] if margin is not None else None}


def evaluate(candidate, opponent, seeds, *, workers=1, mode='round', target=1000, pool=None):
    tasks = [(s, candidate, opponent, mode, target) for s in seeds]
    if pool is not None:
        pairs = list(pool.map(paired_trial, tasks))
    elif workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            pairs = list(executor.map(paired_trial, tasks))
    else:
        pairs = list(map(paired_trial, tasks))
    return {'candidate': candidate, 'opponent': opponent, 'mode': mode, 'target': target,
            'summary': summarize(pairs), 'pairs': pairs}


BOUNDS = {'groups': (2, 20), 'loose': (0, 6), 'control': (0, 8), 'shed': (0, 3),
          'rank': (0, .8), 'partner': (0, 35), 'bomb': (0, 15), 'urgency': (0, 10),
          'lead': (0, 8), 'gift': (0, 3), 'call_threshold': (-1, 5)}


def train(output, *, generations=5, population=10, deals=24, workers=2, seed=1729):
    """CEM-style episodic policy search against a changing league.

    Candidate policies receive only their own observations; reward is final team
    score difference. Every generation uses fresh training deals, common across
    candidates. Final checkpoint selection uses separate validation deals. The
    CLI's evaluation seeds are disjoint and never consumed here.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    initial = asdict(Weights())
    center = initial.copy()
    champion = initial.copy()
    archive = [initial]
    history = []
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for generation in range(generations):
            candidates = [champion]
            for _ in range(population - 1):
                candidate = {}
                for key, (low, high) in BOUNDS.items():
                    sigma = (high - low) * (.18 * .86 ** generation)
                    candidate[key] = min(high, max(low, rng.gauss(center[key], sigma)))
                candidates.append(candidate)
            seeds = list(range(10000 + generation * 1000, 10000 + generation * 1000 + deals))
            opponents = [{'name': 'baseline'}, {'name': 'strategic', 'weights': initial},
                         {'name': 'selfplay', 'weights': champion}]
            scored = []
            for i, weights in enumerate(candidates):
                spec = {'name': 'candidate', 'weights': weights}
                tasks = [(s, spec, opponents[j % len(opponents)], 'round', 1000)
                         for j, s in enumerate(seeds)]
                pairs = list(pool.map(paired_trial, tasks))
                summary = summarize(pairs)
                scored.append({'weights': weights, 'summary': summary, 'pairs': pairs})
                print(f'generation {generation + 1}/{generations} candidate {i + 1}/{population}: '
                      f"{summary['mean_score_difference']:+.1f} points", flush=True)
            ranked = sorted(scored, key=lambda r: r['summary']['mean_score_difference'], reverse=True)
            champion = ranked[0]['weights']
            archive.append(champion)
            elite = ranked[:max(2, population // 3)]
            center = {key: statistics.mean(r['weights'][key] for r in elite) for key in initial}
            history.append({'generation': generation, 'seeds': seeds, 'opponents': opponents,
                            'candidates': scored})
            (output / 'training.json').write_text(json.dumps({'seed': seed, 'history': history}, indent=2) + '\n')
        validation = []
        for i, weights in enumerate(archive):
            spec = {'name': 'candidate', 'weights': weights}
            tasks = [(s, spec, {'name': 'strategic', 'weights': initial} if s % 2 else
                      {'name': 'baseline'}, 'round', 1000) for s in range(500000, 500080)]
            pairs = list(pool.map(paired_trial, tasks))
            result = {'weights': weights, 'summary': summarize(pairs), 'pairs': pairs}
            validation.append(result)
            print(f"validation checkpoint {i}: {result['summary']['mean_score_difference']:+.1f} points", flush=True)
    best = max(validation, key=lambda r: r['summary']['mean_score_difference'])
    report = {'algorithm': 'episodic evolutionary policy search with self-play league',
              'seed': seed, 'generations': generations, 'population': population, 'deals': deals,
              'validation': validation, 'elapsed_seconds': time.perf_counter() - started,
              'training_file_sha256': hashlib.sha256((output / 'training.json').read_bytes()).hexdigest()}
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    Weights(**best['weights']).save(output / 'weights.json', training_seed=seed,
                                  training_deal_range=[10000, 10000 + (generations - 1) * 1000 + deals - 1],
                                  validation_deal_range=[500000, 500079],
                                  validation_mean_score=best['summary']['mean_score_difference'])
    return report


def benchmark_suite(output, *, model=DEFAULT_MODEL, pairs=200, matches=60, workers=2):
    """Frozen-policy final evaluation. These seeds are never used by train()."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    trained = agent_spec('trained', model)
    baseline = agent_spec('baseline')
    strategic = agent_spec('strategic')
    tests = [('initial-v-baseline', strategic, baseline, 'round', pairs),
             ('trained-v-baseline', trained, baseline, 'round', pairs),
             ('trained-v-initial', trained, strategic, 'round', pairs)]
    for option in ('teamwork', 'planning', 'calls', 'exchange'):
        ablated = {**trained, 'options': {option: False}}
        tests.append((f'without-{option}', ablated, baseline, 'round', pairs))
    tests += [('matches-v-baseline', trained, baseline, 'match', matches),
              ('matches-v-initial', trained, strategic, 'match', matches),
              ('solo-v-baseline', {**trained, 'solo': True}, baseline, 'round', pairs),
              ('solo-matches-v-baseline', {**trained, 'solo': True}, baseline, 'match', matches)]
    results = {}
    detailed = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for name, candidate, opponent, mode, count in tests:
            start = 1000000 if mode == 'round' else 2000000
            result = evaluate(candidate, opponent, range(start, start + count),
                              mode=mode, pool=pool)
            (output / f'{name}.json').write_text(json.dumps(result, indent=2) + '\n')
            results[name] = result['summary']
            detailed[name] = result
            print(f"{name}: {result['summary']['win_rate']:.1%} wins, "
                  f"{result['summary']['mean_score_difference']:+.1f} points", flush=True)
    manifest = {'model_sha256': hashlib.sha256(Path(model).read_bytes()).hexdigest(),
                'round_seed_start': 1000000, 'match_seed_start': 2000000,
                'pairs': pairs, 'match_pairs': matches, 'results': results}
    manifest['paired_ablation_deltas'] = {
        name: paired_score_difference(detailed['trained-v-baseline'], detailed[name])
        for name in ('without-planning', 'without-teamwork', 'without-exchange',
                     'without-calls', 'initial-v-baseline')}
    (output / 'summary.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    evaluation = sub.add_parser('evaluate')
    evaluation.add_argument('--candidate', choices=('baseline', 'strategic', 'trained', 'competitive', 'scoring'), default='trained')
    evaluation.add_argument('--opponent', choices=('baseline', 'strategic', 'trained', 'competitive'), default='baseline')
    evaluation.add_argument('--model', type=Path, help='candidate checkpoint override')
    evaluation.add_argument('--opponent-model', type=Path, help='opponent checkpoint override')
    evaluation.add_argument('--solo', action='store_true',
                            help='one candidate agent with an original baseline partner')
    evaluation.add_argument('--pairs', type=int, default=200)
    evaluation.add_argument('--seed-start', type=int, default=1000000)
    evaluation.add_argument('--mode', choices=('round', 'match'), default='round')
    evaluation.add_argument('--target', type=int, default=1000)
    evaluation.add_argument('--workers', type=int, default=2)
    evaluation.add_argument('--output', type=Path, required=True)
    training = sub.add_parser('train')
    training.add_argument('--output', type=Path, required=True)
    training.add_argument('--generations', type=int, default=5)
    training.add_argument('--population', type=int, default=10)
    training.add_argument('--deals', type=int, default=24)
    training.add_argument('--workers', type=int, default=2)
    training.add_argument('--seed', type=int, default=1729)
    suite = sub.add_parser('suite')
    suite.add_argument('--output', type=Path, required=True)
    suite.add_argument('--model', type=Path, default=DEFAULT_MODEL)
    suite.add_argument('--pairs', type=int, default=200)
    suite.add_argument('--matches', type=int, default=60)
    suite.add_argument('--workers', type=int, default=2)
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error('--workers must be positive')
    if args.command == 'train':
        if args.generations < 1 or args.population < 2 or args.deals < 3:
            parser.error('Training needs positive generations, population >=2 and deals >=3')
        train(args.output, generations=args.generations, population=args.population,
              deals=args.deals, workers=args.workers, seed=args.seed)
    elif args.command == 'suite':
        if args.pairs < 2 or args.matches < 2:
            parser.error('Use at least two pairs for each benchmark')
        benchmark_suite(args.output, model=args.model, pairs=args.pairs,
                        matches=args.matches, workers=args.workers)
    else:
        if args.pairs < 1 or args.target < 1:
            parser.error('--pairs and --target must be positive')
        candidate = agent_spec(args.candidate, args.model)
        if args.solo:
            candidate['solo'] = True
        result = evaluate(candidate, agent_spec(args.opponent, args.opponent_model),
                          range(args.seed_start, args.seed_start + args.pairs),
                          workers=args.workers, mode=args.mode, target=args.target)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
