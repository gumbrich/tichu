"""Recorded external-opponent parameter selection, separate from final testing."""
import argparse
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

from .external import benchmark, interval


def evaluate(model, output, *, pairs, seed, workers, candidate='scoring'):
    benchmark(SimpleNamespace(binary='tools/dave_bridge/target/release/tichu-external-benchmark',
        opponent='eg:pimc20/hibs', pairs=pairs, seed=seed, workers=workers,
        mode='rounds', output=str(output), candidate=candidate, model=str(model) if model else None))
    return json.loads((Path(output)/'summary.json').read_text())


def paired_change(candidate, baseline):
    def margins(path):
        with gzip.open(Path(path)/'pairs.jsonl.gz', 'rt') as handle:
            return {r['pair']: sum(g['our_margin'] for g in r['games'])/2
                    for r in map(json.loads, handle)}
    a, b = margins(candidate), margins(baseline)
    if a.keys() != b.keys():
        raise ValueError('Pair indices differ')
    return interval([a[i]-b[i] for i in sorted(a)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pairs', type=int, default=64)
    parser.add_argument('--seed', type=int, default=16001000)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for path in sorted(args.candidates.glob('*.json')):
        print(f'Candidate {path.stem}', flush=True)
        report = evaluate(path, args.output/path.stem, pairs=args.pairs,
                          seed=args.seed, workers=args.workers)
        rows.append({'candidate': path.stem, 'model': str(path), 'summary': report})
        (args.output/'ranking.json').write_text(json.dumps(sorted(rows,
            key=lambda r: r['summary']['paired_margin']['mean'], reverse=True), indent=2)+'\n')
    print('Screen complete; these are selection results, not held-out estimates.', flush=True)


if __name__ == '__main__':
    main()
