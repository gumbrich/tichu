"""Optional training by search-policy distillation; inference is standard-library only.

Examples are teacher actions selected from that seat's legal moves and public
observation. The authoritative replay never exports opponents' hidden hands.
This is supervised policy learning, not reinforcement learning.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import threading

from .agents import hand_plan
from .cards import DOG, PHOENIX, DRAGON
from .scoring import ControlEstimate, initial_spec

FEATURES = (
    'pass', 'remaining_groups', 'remaining_loose', 'remaining_control',
    'remaining_cards', 'shed', 'rank', 'bomb', 'dog', 'dragon', 'phoenix_single',
    'enemy_secure', 'signed_pot', 'played_points', 'pass_partner', 'overtake_partner',
    'play_partner_call', 'own_call_groups', 'enemy_call_danger', 'matching_enemy_size',
    'lead_rank', 'lead_shed', 'enemy_size_remaining', 'pass_partner_size',
    'finish', 'break_bomb', 'partner_first_remaining', 'enemy_first_control',
    'unresolved_groups',
) + tuple(f'{k}_{metric}' for k in ('single', 'pair', 'triple', 'full_house', 'straight', 'pairs')
          for metric in ('present', 'rank'))


def features(obs, play, plan=None, control=None):
    plan = plan or hand_plan(obs.hand)
    control = control or ControlEstimate(obs)
    passed = play is None
    if passed and not obs.can_pass:
        raise ValueError('Cannot featurize illegal pass')
    mask = plan.full if passed else plan.full ^ plan.mask(play.cards)
    groups, loose = plan.partition(mask)
    controls = plan.controls(mask)
    remaining = mask.bit_count()
    shed = 0 if passed else len(play.cards)
    top = obs.top if passed else play
    winner = obs.trick_winner if passed else obs.seat
    partner = (obs.seat+2) % 4
    enemies = [s for s in range(4) if s % 2 != obs.seat % 2 and obs.counts[s]]
    secure = control.secure(top) if top and top.kind != 'dog' else 0.0
    pot = obs.pile_points + (0 if passed else sum(c.points for c in play.cards))
    ours = winner is not None and winner % 2 == obs.seat % 2
    signed = 2*secure-1 if ours else -1
    if top and top.kind == 'single' and top.cards[0].rank == DRAGON:
        signed = -1 if ours else 1
    danger = 0.0
    if top and not obs.finish_order:
        for s in enemies:
            urgency = 1 if obs.counts[s] == len(top.cards) else 1/(1+obs.counts[s]/3)
            answer = 1 if passed and winner == s else control.answer(s, top)
            danger += obs.calls[s]/200 * urgency * answer
    rank = 0 if passed else play.rank/16
    partner_winning = obs.trick_winner == partner and obs.counts[partner] > 0
    broke = sum(bool(bomb & mask) and bomb & mask != bomb for bomb in plan.bombs)
    first = obs.finish_order[0] if obs.finish_order else None
    row = [float(passed), groups/7, loose/7, controls/5, remaining/14, shed/14, rank,
           float(bool(play and play.is_bomb)), float(bool(play and play.kind == 'dog')),
           float(bool(play and play.cards[0].rank == DRAGON)),
           float(bool(play and len(play.cards) == 1 and play.cards[0].rank == PHOENIX)),
           secure, pot*signed/50, 0 if passed else sum(c.points for c in play.cards)/25,
           float(passed and partner_winning), float(not passed and partner_winning),
           (not passed)*obs.calls[partner]/200, obs.calls[obs.seat]/200*groups/7,
           danger, float(any(obs.counts[s] == shed for s in enemies)),
           (obs.top is None)*rank, (obs.top is None)*shed/14,
           min((obs.counts[s] for s in enemies), default=0)*remaining/196,
           passed*obs.counts[partner]/14, float(remaining == 0), float(broke),
           (first == partner)*remaining/14,
           (first is not None and first % 2 != obs.seat % 2)*controls/5,
           (first is None)*groups/7]
    for kind in ('single', 'pair', 'triple', 'full_house', 'straight', 'pairs'):
        matches = play is not None and play.kind == kind
        row.extend([float(matches), matches*rank])
    assert len(row) == len(FEATURES)
    return row


def choose(obs, coefficients, baseline=None, blend=1.0):
    plan, control = hand_plan(obs.hand), ControlEstimate(obs)
    choices = ([None] if obs.can_pass else []) + list(obs.plays)
    if not choices:
        return None
    scores = [sum(w*x for w, x in zip(coefficients, features(obs, p, plan, control)))
              for p in choices]
    if baseline is not None:
        if len(baseline) != len(scores):
            raise ValueError('Baseline must score every legal choice')
        def normalize(values):
            mean = sum(values)/len(values)
            scale = math.sqrt(sum((v-mean)**2 for v in values)/len(values))
            return [(v-mean)/scale if scale else 0.0 for v in values]
        scores = [blend*a+(1-blend)*b for a, b in zip(normalize(scores), normalize(baseline))]
    return choices[max(range(len(scores)), key=scores.__getitem__)]


def encode_record(record):
    from .external import observation, combo_from_wire
    request = record['request']
    obs = observation(request)  # Independent legal-set and information checks.
    label = record['label']
    teacher = None if label is None else combo_from_wire(request['plays'][label])
    choices = ([None] if obs.can_pass else []) + list(obs.plays)
    if len(choices) < 2:
        return None
    plan, control = hand_plan(obs.hand), ControlEstimate(obs)
    rows = [tuple(features(obs, p, plan, control)) for p in choices]
    # Equivalent feature vectors must not receive extra probability merely
    # because many suit selections encode the same decision.
    unique = list(dict.fromkeys(rows))
    target = unique.index(rows[choices.index(teacher)])
    if len(unique) < 2:
        return None
    return unique, target, record['pair']


def extract(sources, output, binary, workers):
    import numpy as np
    from concurrent.futures import ProcessPoolExecutor
    sources = [Path(p) for p in sources]
    output = Path(output)
    if output.suffix != '.npz':
        raise ValueError('Dataset output must end in .npz')
    if output.exists() or output.with_suffix('.json').exists():
        raise FileExistsError(output)
    if not sources or any(not p.is_file() for p in sources):
        raise ValueError('Every training source must be an existing file')
    feed_errors = []
    def feed(stream):
        try:
            for path in sources:
                opener = gzip.open if path.suffix == '.gz' else open
                with opener(path, 'rt') as handle:
                    # Collector workers finish out of order. Canonical deal
                    # order makes the optimizer's seeded shuffle reproducible.
                    for line in sorted(handle, key=lambda value: json.loads(value)['pair']):
                        stream.write(line)
        except Exception as error:
            feed_errors.append(error)
        finally:
            stream.close()
    with subprocess.Popen([binary, 'export-teacher'], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, text=True) as proc:
        writer = threading.Thread(target=feed, args=(proc.stdin,))
        writer.start()
        rows, offsets, targets, groups = [], [0], [], []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            # Bounded batches avoid reading all request histories into memory.
            batch = []
            def consume(items):
                for result in pool.map(encode_record, items, chunksize=16):
                    if result is None:
                        continue
                    vectors, target, group = result
                    rows.extend(vectors); offsets.append(len(rows)); targets.append(target); groups.append(group)
            for line in proc.stdout:
                batch.append(json.loads(line))
                if len(batch) == 256:
                    consume(batch); batch.clear()
            if batch:
                consume(batch)
        writer.join()
        if proc.wait():
            raise RuntimeError('Teacher export failed; dataset not written')
        if feed_errors:
            raise RuntimeError('Training input failed; dataset not written') from feed_errors[0]
    if not targets:
        raise ValueError('No trainable decisions; dataset not written')
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, x=np.asarray(rows, dtype=np.float32), offsets=offsets,
                        targets=targets, groups=groups)
    metadata = {'features': FEATURES, 'decisions': len(targets), 'options': len(rows),
                'sources': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],
                'binary_sha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest()}
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps(metadata, indent=2))


def train(data, output, epochs=30):
    import numpy as np
    data = Path(data); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    metadata = json.loads(data.with_suffix('.json').read_text())
    if metadata['features'] != list(FEATURES):
        raise ValueError('Feature schema mismatch')
    corpus = np.load(data, allow_pickle=False)
    x, offsets, targets, groups = (corpus[k] for k in ('x', 'offsets', 'targets', 'groups'))
    if x.ndim != 2 or x.shape[1] != len(FEATURES) or not np.isfinite(x).all():
        raise ValueError('Invalid feature matrix')
    train_ids, valid_ids = np.flatnonzero(groups % 8 != 0), np.flatnonzero(groups % 8 == 0)
    if not len(train_ids) or not len(valid_ids):
        raise ValueError('Need both training and grouped validation deals')
    rng = np.random.default_rng(16281)
    w = np.zeros(x.shape[1], dtype=np.float64)
    m, v = np.zeros_like(w), np.zeros_like(w)
    history, best, step = [], float('inf'), 0
    def assess(ids):
        loss = correct = 0
        for i in ids:
            z = np.sum(x[offsets[i]:offsets[i+1]] * w, axis=1)
            z -= np.max(z)
            loss += np.log(np.exp(z).sum()) - z[targets[i]]
            correct += int(np.argmax(z) == targets[i])
        return float(loss/len(ids)), float(correct/len(ids))
    for epoch in range(epochs):
        rng.shuffle(train_ids)
        for start in range(0, len(train_ids), 128):
            ids = train_ids[start:start+128]
            gradient = np.zeros_like(w)
            for i in ids:
                matrix = x[offsets[i]:offsets[i+1]]
                z = np.sum(matrix * w, axis=1); z -= np.max(z)
                p = np.exp(z); p /= p.sum()
                gradient += np.sum(p[:, None] * matrix, axis=0) - matrix[targets[i]]
            gradient = gradient/len(ids) + .0002*w
            step += 1
            m = .9*m + .1*gradient; v = .999*v + .001*gradient**2
            w -= .035*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
            if not np.isfinite(w).all():
                raise ValueError('Nonfinite trained coefficients')
        loss, accuracy = assess(valid_ids)
        history.append({'epoch': epoch+1, 'validation_loss': loss, 'accuracy': accuracy})
        print(json.dumps(history[-1]), flush=True)
        if loss < best:
            best = loss
            spec = initial_spec()
            spec['move_features'] = list(FEATURES)
            spec['move_weights'] = w.tolist()
            # Calls remain conservative until separately tested in arena.
            spec['scoring']['grand_threshold'] = 4.2
            # Preserve frozen play/call preferences outside learned ordinary turns.
            for key in ('points', 'initiative', 'call_defense', 'king_control'):
                spec['scoring'][key] = 0.0
            (output/'weights.json').write_text(json.dumps(spec, indent=2)+'\n')
    (output/'training.json').write_text(json.dumps({
        'method': 'supervised linear softmax policy distillation with Adam',
        'python': sys.version, 'numpy': np.__version__,
        'dataset_sha256': hashlib.sha256(data.read_bytes()).hexdigest(),
        'seed': 16281, 'train_decisions': len(train_ids), 'validation_decisions': len(valid_ids),
        'split': 'entire deal groups: pair index modulo 8 equals zero held out',
        'history': history, 'best_validation_loss': best}, indent=2)+'\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    e = sub.add_parser('extract'); e.add_argument('sources', nargs='+')
    e.add_argument('--output', required=True)
    e.add_argument('--binary', default='/private/tmp/tichu-teacher-build/release/tichu-external-benchmark')
    e.add_argument('--workers', type=int, default=4)
    t = sub.add_parser('train'); t.add_argument('data'); t.add_argument('--output', required=True)
    t.add_argument('--epochs', type=int, default=30)
    args = vars(p.parse_args()); command = args.pop('command')
    if args.get('workers', 1) < 1 or args.get('epochs', 1) < 1:
        p.error('workers and epochs must be positive')
    (extract if command == 'extract' else train)(**args)


if __name__ == '__main__':
    main()
