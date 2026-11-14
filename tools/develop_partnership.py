"""Run the recorded larger-corpus, combination and match-risk selection screens."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from tichu.improve import evaluate, paired_change
from tichu.partnership import PartnershipWeights


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def screen(root, models, *, pairs, seed, workers, mode='rounds'):
    root.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, model in sorted(models.items()):
        path = root/(name+'.json')
        save(path, model)
        print('Screen', root.name, name, flush=True)
        summary = evaluate(path, root/name, pairs=pairs, seed=seed, workers=workers,
                           candidate=model['policy'], mode=mode)
        rows.append({'name': name, 'model': str(path), 'summary': summary})
        key = 'match_win_rate' if mode == 'games' else 'paired_margin'
        rows.sort(key=lambda row: (row['summary'][key]['mean'],
                                  row['summary']['paired_margin']['mean']), reverse=True)
        save(root/'ranking.json', rows)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--learned', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, default=10)
    args = p.parse_args()
    if args.workers < 1:
        p.error('workers must be positive')
    team_root = Path('experiments/partnership/team-screen')
    team_rows = json.loads((team_root/'ranking.json').read_text())
    if len(team_rows) != 12 or any(r['summary']['pairs'] != 96 for r in team_rows):
        raise ValueError('Complete the twelve-candidate partnership screen first')
    base = json.loads(Path('experiments/partnership/v3.json').read_text())
    trained = json.loads(args.learned.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    models = {'v3': base}
    for blend in (.25, .5, .75):
        models[f'blend{blend:.2f}'] = {**trained, 'move_blend': blend}
    rows = screen(args.output/'blends', models, pairs=128, seed=21300000, workers=args.workers)
    best = models[rows[0]['name']]
    save(args.output/'blends/comparison.json', {
        row['name']: paired_change(args.output/'blends'/row['name'], args.output/'blends/v3')
        for row in rows})

    options = {'control': {}, 'parity-delay': {'parity': True, 'wait_small': True}}
    positive_temps = [r for r in team_rows if r['candidate'].startswith('temp')
                      and paired_change(team_root/r['candidate'], team_root/'control')['mean'] > 0]
    if positive_temps:
        winner = max(positive_temps, key=lambda r: r['summary']['paired_margin']['mean'])
        temperature = json.loads((team_root/winner['candidate']/'candidate.json').read_text())['partnership']['temperature']
        options['parity-delay-temperature'] = {'parity': True, 'wait_small': True, 'temperature': temperature}
    if paired_change(team_root/'ties', team_root/'control')['mean'] > 0:
        options['parity-delay-ties'] = {'parity': True, 'wait_small': True, 'random_ties': True}
    combined = {name: {**best, 'name': 'partnership', 'policy': 'partnership', 'schema_version': 3,
                      'partnership': asdict(PartnershipWeights(**option))}
                for name, option in options.items()}
    rows = screen(args.output/'combinations', combined, pairs=128, seed=21310000, workers=args.workers)
    best = combined[rows[0]['name']]
    save(args.output/'combinations/comparison.json', {
        row['name']: paired_change(args.output/'combinations'/row['name'], args.output/'combinations/control')
        for row in rows})

    risks = {}
    for risk in (0., .4, .8):
        model = deepcopy(best)
        model['partnership']['risk'] = risk
        risks[f'risk{risk:.1f}'] = model
    rows = screen(args.output/'risk', risks, pairs=32, seed=21400000, workers=args.workers, mode='games')
    save(args.output/'selection.json', {
        'purpose': 'development selection only; validation and final seeds remain unused',
        'candidate': rows[0],
        'model': risks[rows[0]['name']],
        'risk_comparisons': {row['name']: paired_change(args.output/'risk'/row['name'], args.output/'risk/risk0.0')
                             for row in rows}})
    print('Development complete; selected', rows[0]['model'], flush=True)


if __name__ == '__main__':
    main()
