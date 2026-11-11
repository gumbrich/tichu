import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from tichu.selfplay import agent_spec, evaluate

if __name__ == '__main__':
    out = Path('experiments/competitive/pilot'); out.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=4) as pool:
        for name, tactics, options in [
                ('defaults', {}, {}),
                ('proofs-only', {'secure':0, 'threat':0, 'points':0}, {}),
                ('secure-small', {'secure':1, 'threat':0, 'points':0}, {}),
                ('threat-small', {'secure':0, 'threat':3, 'points':0}, {}),
                ('no-proofs', {}, {'proofs':False})]:
            spec = agent_spec('tactical', **options); spec['tactics'] = tactics
            result = evaluate(spec, agent_spec('trained'), range(3100000,3100100), pool=pool)
            (out / (name + '.json')).write_text(json.dumps(result, indent=2)+'\n')
            print(name, result['summary'], flush=True)
