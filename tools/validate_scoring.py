"""Run the predeclared validation suite after a complete parameter screen."""
import argparse
import json
from pathlib import Path

from tichu.improve import evaluate
from tichu.selfplay import agent_spec, evaluate as native_evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screen', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    ranking = json.loads((args.screen/'ranking.json').read_text())
    if len(ranking) != 16 or any(r['summary']['pairs'] != 64 for r in ranking):
        raise ValueError('The predeclared screen must finish before selection')
    finalists = ranking[:3]
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'selection.json').write_text(json.dumps(finalists, indent=2)+'\n')
    results = []
    for row in finalists:
        name = row['candidate']
        model = args.screen/name/'candidate.json'
        print('Validating', name, flush=True)
        native = native_evaluate(agent_spec('scoring', model), agent_spec('competitive'),
                                 range(17100000, 17100128), workers=args.workers)
        (args.output/(name+'-native.json')).write_text(json.dumps(native, indent=2)+'\n')
        external = evaluate(model, args.output/name, pairs=256, seed=17000000,
                            workers=args.workers)
        results.append({'candidate': name, 'native': native['summary'], 'external': external})
        (args.output/'results.json').write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    main()
