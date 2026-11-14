"""Apply the fixed two-finalist selection rule, then freeze one final-test model."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from tichu.improve import paired_change
from tichu.selfplay import agent_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    candidates = []
    for name in ('learned', 'partnership'):
        root = args.validation/name
        manifest = json.loads((root/'manifest.json').read_text())
        if manifest['stage'] != 'validation' or manifest['status'] != 'complete':
            raise ValueError('Both full validation suites must finish before selection')
        model = root/'candidate.json'
        if hashlib.sha256(model.read_bytes()).hexdigest() != manifest['model_sha256']:
            raise ValueError('Validation model changed')
        native = json.loads((root/'native-round.json').read_text())
        if native['candidate'] != agent_spec(manifest['policy'], model):
            raise ValueError('Native validation used a different model')
        for mode, count, seed in (('rounds', 256, 22000000), ('games', 100, 22100000)):
            recorded = json.loads((root/f'candidate-{mode}'/'manifest.json').read_text())
            if ((recorded['mode'], recorded['pairs'], recorded['seed']) != (mode, count, seed)
                    or recorded['model_sha256'] != manifest['model_sha256']):
                raise ValueError('External validation used a different model or schedule')
            paired_change(root/f'candidate-{mode}', root/f'v3-{mode}')
        if {p['seed'] for p in native['pairs']} != set(range(22200000, 22200256)):
            raise ValueError('Native validation used different deals')
        rounds = json.loads((root/'candidate-rounds/summary.json').read_text())
        matches = json.loads((root/'candidate-games/summary.json').read_text())
        candidates.append({'name': name, 'model': str(model), 'model_sha256': manifest['model_sha256'],
                           'policy': manifest['policy'], 'native': native['summary'],
                           'external_rounds': rounds, 'external_matches': matches})
    eligible = [row for row in candidates if row['native']['mean_score_difference'] > 0]
    if not eligible:
        raise ValueError('No finalist passed the predeclared native selection criterion')
    chosen = max(eligible, key=lambda row: (row['external_matches']['match_win_rate']['mean'],
                                          row['external_matches']['paired_margin']['mean']))
    args.output.mkdir(parents=True)
    (args.output/'candidate.json').write_bytes(Path(chosen['model']).read_bytes())
    report = {'status': 'frozen-before-final-tests',
              'rule': 'Highest external validation match win rate among positive native round means; tie: match margin',
              'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'selected': chosen['name'], 'model_sha256': chosen['model_sha256'],
              'candidates': candidates}
    (args.output/'selection.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'selected': chosen['name'], 'model_sha256': chosen['model_sha256']}, indent=2))


if __name__ == '__main__':
    main()
