"""Run the fixed scoring-policy final tests after validation selects a model."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from tichu.external import benchmark
from tichu.improve import paired_change
from tichu.scoring import read_spec


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, default=6, help='workers per external policy')
    p.add_argument('--native-workers', type=int, default=2)
    args = p.parse_args()
    if args.workers < 1 or args.native_workers < 1:
        p.error('worker counts must be positive')
    read_spec(args.model)
    args.output.mkdir(parents=True, exist_ok=False)
    model = (args.output/'candidate.json').resolve()
    model.write_bytes(args.model.read_bytes())
    manifest = {'status': 'running', 'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
                'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'external_round_pairs': 1000, 'external_round_seed': 18000000,
                'external_match_pairs': 100, 'external_match_seed': 18100000,
                'native_round_pairs': 1000, 'native_round_seed': 19000000,
                'native_match_pairs': 150, 'native_match_seed': 19100000}
    manifest_path = args.output/'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')

    def external(policy):
        for mode, pairs, seed in [('rounds', 1000, 18000000), ('games', 100, 18100000)]:
            print('Final external', policy, mode, flush=True)
            benchmark(SimpleNamespace(binary='tools/dave_bridge/target/release/tichu-external-benchmark',
                opponent='eg:pimc20/hibs', candidate=policy,
                model=str(model) if policy == 'scoring' else None,
                pairs=pairs, seed=seed, workers=args.workers, mode=mode,
                output=str(args.output/f'{policy}-{mode}')))

    def native():
        for mode, pairs, seed in [('round', 1000, 19000000), ('match', 150, 19100000)]:
            print('Final native', mode, flush=True)
            with (args.output/f'native-{mode}.log').open('w') as log:
                subprocess.run([sys.executable, '-m', 'tichu.selfplay', 'evaluate',
                    '--candidate', 'scoring', '--model', str(model), '--opponent', 'competitive',
                    '--pairs', str(pairs), '--seed-start', str(seed), '--mode', mode,
                    '--workers', str(args.native_workers),
                    '--output', str(args.output/f'native-{mode}.json')],
                    stdout=log, stderr=subprocess.STDOUT, check=True)

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = [pool.submit(external, policy) for policy in ('scoring', 'competitive')]
            jobs.append(pool.submit(native))
            for job in jobs:
                job.result()
        improvement = paired_change(args.output/'scoring-rounds', args.output/'competitive-rounds')
        match_improvement = paired_change(args.output/'scoring-games', args.output/'competitive-games')
        native_round = json.loads((args.output/'native-round.json').read_text())['summary']
        native_match = json.loads((args.output/'native-match.json').read_text())['summary']
        report = {'external_round_improvement': improvement,
                  'external_final_match_margin_improvement': match_improvement,
                  'native_round': native_round, 'native_match': native_match,
                  'promotion_gate_passed': (improvement['ci95'][0] > 0
                      and native_round['score_difference_95ci'][0] > 0
                      and native_match['win_rate_95ci'][0] > .5)}
        (args.output/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
        manifest['status'] = 'complete'
    except BaseException:
        manifest['status'] = 'failed'
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
