"""Resume deterministic teacher deals by index, audit and save a sorted corpus."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from tichu.external import EXTERNAL_REV, audit_score


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True, help='append-only JSONL checkpoint')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--binary', required=True)
    p.add_argument('--count', type=int, required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--workers', type=int, default=8)
    args = p.parse_args()
    if min(args.count, args.workers) < 1:
        p.error('count and workers must be positive')
    if args.output.exists():
        raise FileExistsError(args.output)
    records = {}
    if args.source.exists():
        raw = args.source.read_bytes()
        # An interrupted write may leave only a partial final line. Regenerate
        # that deterministic deal, never discard a completed outcome.
        complete = raw[:raw.rfind(b'\n')+1]
        for line in complete.splitlines():
            record = json.loads(line)
            i = record['pair']
            if i in records or not 0 <= i < args.count:
                raise ValueError('Duplicate or out-of-range teacher deal')
            if record['seed'] != args.seed or record['external_revision'] != EXTERNAL_REV:
                raise ValueError('Checkpoint provenance mismatch')
            records[i] = record
        args.source.write_bytes(complete)
    initial_count = len(records)
    missing = [i for i in range(args.count) if i not in records]
    ranges = []
    for i in missing:
        if ranges and ranges[-1][1] == i:
            ranges[-1][1] += 1
        else:
            ranges.append([i, i+1])
    print(f'Resuming {initial_count} completed deals; {len(missing)} remaining', flush=True)
    with args.source.open('ab') as output:
        for start, stop in ranges:
            subprocess.run([args.binary, 'collect-teacher', str(stop-start), str(args.seed),
                            str(args.workers), str(start)], stdout=output, check=True)
    lines = args.source.read_text().splitlines()
    records = [json.loads(line) for line in lines]
    if len(records) != args.count or {r['pair'] for r in records} != set(range(args.count)):
        raise ValueError('Incomplete corpus')
    for record in records:
        if record['seed'] != args.seed or record['external_revision'] != EXTERNAL_REV or not record['teacher_all']:
            raise ValueError('Invalid teacher provenance')
        for game in record['games']:
            for round_ in game['rounds']:
                audit_score(round_)
    with gzip.GzipFile(filename=str(args.output), mode='wb', mtime=0) as output:
        for record in sorted(records, key=lambda r: r['pair']):
            output.write((json.dumps(record, separators=(',', ':'))+'\n').encode())
    metadata = {'rounds': args.count, 'seed': args.seed, 'resumed_records': initial_count,
                'workers': args.workers, 'external_revision': EXTERNAL_REV,
                'binary_sha256': hashlib.sha256(Path(args.binary).read_bytes()).hexdigest(),
                'corpus_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
                'audited_rounds': args.count, 'status': 'complete'}
    args.output.with_suffix('.manifest.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == '__main__':
    main()
