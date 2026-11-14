"""Run the predeclared v4 validation or final suite; never select a model here."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil
from types import SimpleNamespace

from tichu.external import benchmark, EXTERNAL_REV
from tichu.improve import paired_change
from tichu.selfplay import agent_spec


SCHEDULES = {
    'validation': [('rounds', 256, 22000000), ('games', 100, 22100000),
                   ('round', 256, 22200000)],
    'final': [('rounds', 1000, 23000000), ('games', 200, 24000000),
              ('round', 1000, 25000000), ('match', 150, 25100000)],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--stage', choices=SCHEDULES, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--native-workers', type=int, default=2)
    parser.add_argument('--reuse-baseline', type=Path,
                        help='completed suite with identical v3 seeds; no new baseline evidence is created')
    args = parser.parse_args()
    if min(args.workers, args.native_workers) < 1:
        parser.error('worker counts must be positive')
    policy = json.loads(args.model.read_text())['policy']
    agent_spec(policy, args.model)  # Validate before starting a long run.
    args.output.mkdir(parents=True, exist_ok=False)
    model = (args.output/'candidate.json').resolve()
    model.write_bytes(args.model.read_bytes())
    baseline = Path('experiments/partnership/v3.json').resolve()
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != 'b7883435e25b66f84baaf84383465848bcdbb7157e4b0d1b522acd82df73f5dd':
        raise ValueError('Frozen v3 changed')
    manifest = {'stage': args.stage, 'status': 'running', 'policy': policy,
                'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
                'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'schedule': SCHEDULES[args.stage]}
    if args.reuse_baseline:
        manifest['baseline_reused_from'] = str(args.reuse_baseline)
    manifest_path = args.output/'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')

    def external():
        for mode, pairs, seed in SCHEDULES[args.stage][:2]:
            for label, name, path in [('candidate', policy, model), ('v3', 'scoring', baseline)]:
                if label == 'v3' and args.reuse_baseline:
                    source = args.reuse_baseline/f'v3-{mode}'
                    recorded = json.loads((source/'manifest.json').read_text())
                    expected = {'seed': seed, 'pairs': pairs, 'mode': mode, 'status': 'complete',
                                'opponent': 'eg:pimc20/hibs', 'external_revision': EXTERNAL_REV,
                                'model_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest()}
                    if any(recorded.get(key) != value for key, value in expected.items()):
                        raise ValueError('Reusable baseline is not this fixed comparison')
                    if hashlib.sha256((source/'candidate.json').read_bytes()).hexdigest() != expected['model_sha256']:
                        raise ValueError('Reusable baseline model changed')
                    shutil.copytree(source, args.output/f'{label}-{mode}')
                    continue
                print('External', label, mode, flush=True)
                benchmark(SimpleNamespace(binary='tools/dave_bridge/target/release/tichu-external-benchmark',
                    opponent='eg:pimc20/hibs', candidate=name, model=str(path), pairs=pairs,
                    seed=seed, workers=args.workers, mode=mode, output=str(args.output/f'{label}-{mode}')))

    def native():
        for mode, pairs, seed in SCHEDULES[args.stage][2:]:
            print('Native versus v3', mode, flush=True)
            with (args.output/f'native-{mode}.log').open('w') as log:
                subprocess.run([sys.executable, '-m', 'tichu.selfplay', 'evaluate',
                    '--candidate', policy, '--model', str(model), '--opponent', 'scoring',
                    '--opponent-model', str(baseline), '--pairs', str(pairs),
                    '--seed-start', str(seed), '--mode', mode, '--workers', str(args.native_workers),
                    '--output', str(args.output/f'native-{mode}.json')],
                    stdout=log, stderr=subprocess.STDOUT, check=True)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(external), pool.submit(native)]
            for job in jobs:
                job.result()
        report = {mode+'_paired_gain': paired_change(args.output/f'candidate-{mode}', args.output/f'v3-{mode}')
                  for mode in ('rounds', 'games')}
        report['native'] = {mode: json.loads((args.output/f'native-{mode}.json').read_text())['summary']
                            for mode, _, _ in SCHEDULES[args.stage][2:]}
        (args.output/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
        manifest['status'] = 'complete'
    except BaseException:
        manifest['status'] = 'failed'
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
