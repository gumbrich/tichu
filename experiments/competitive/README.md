# Competitive bot experiment record

11 November 2026. Python 3.13.7, local CPU, four worker processes; standard library
only. Tactical implementation: `b35273a`; training and checkpoint integration:
`0946dd0`. The frozen parent remains `tichu/trained_weights.json` from v1.

## Method and selection

The candidate adds conservative counterplay bounds and guaranteed small-hand
finishes to the existing exact hand planner. Evolutionary policy search tunes
three new tactical scores and four existing play weights. Hand partition,
exchange, control, bomb-cost and call-threshold weights remain frozen.

Each generation uses a league: frozen v1 on half its deal pairs, the untuned
planner on a quarter, and the previous tactical champion on a quarter. Candidates
share those deals. Final team score is the reward; no policy sees hidden cards.

Five generations of ten candidates produce five champions, plus the initial
candidate. Validation compares all six on a separate fixed set against frozen v1.
The generation-four champion wins selection; generation five retained it.
The initial untuned tactics scored +8.50 and the selected policy +16.62 points
per round on validation. These selection numbers are not final test results.

The selected file is copied unchanged from `training/weights.json` to
`tichu/competitive_weights.json`. No weights are selected or modified using the
final evaluation. v1 is never overwritten. Checkpoint hashes in the held-out
summary identify both policies.

## Budgets and separation

| Stage | Budget | Seeds |
| --- | --- | --- |
| Exploratory pilot | 5 conditions × 100 pairs × 2 sides = 1,000 rounds | 3100000–3100099 |
| Training | 5 generations × 10 candidates × 64 pairs × 2 sides = 6,400 rounds | 4000000 + 1000g through +63, g=0..4 |
| Checkpoint validation | 6 candidates × 300 pairs × 2 sides = 3,600 rounds | 5000000–5000299 |
| Final round tests and ablations | 6 conditions × 1,000 pairs × 2 sides = 12,000 rounds | 6000000–6000999 |
| Final full-match tests | 2 conditions × 150 pairs × 2 sides = 600 matches | 7000000–7000149 |

The older v1 experiment used other ranges. Smoke and correctness-test deals are
not included as evidence of strength. Training includes duplicate controls and
champions; all evaluations are retained, not just distinct parameter vectors.

## Evaluation and promotion

Each seed is played twice with team assignments swapped. A round test measures
final team score difference and round win rate. Match tests continue until a team
wins at the 1,000-point target, including tied-target continuation. Round ties
count as half wins. The two sides of a seed form one statistical cluster.

Approximate 95% intervals use the standard error over **pair means**, not over
individual games. Reported ablation differences compare policies on the same
seed pairs; they are conditional effects and must not be added together.

The promotion rule was specified before final testing: both the lower 95% bound
on round score margin must exceed zero and the lower bound on full-match win rate
must exceed 50%, against frozen v1. The final `heldout/summary.json` records the
pass/fail result. This gate supports a local improvement claim, not superiority
to AlphaTichu or humans. It does not constitute a population-wide skill rating.

All simulation rounds validate action legality, termination, unique ownership of
all 56 cards and score conservation. The tactical predicate is separately checked
against generated legal moves across random and structured hands, combination
types and card-count limits. Public-information tests verify that actual hidden
hands stay within the conservative pools, and disabling all tactical changes
reproduces v1 decisions.

## Files and reproduction

- `pilot.py` and `pilot/*.json`: the exploratory configurations and outcomes.
- `training/training.json`: candidates, league opponents, seeds and per-pair results.
- `training/validation.json`: every archived checkpoint, outcomes and summaries.
- `training/weights.json`: selected checkpoint and parent provenance.
- `heldout/*.json`: complete outcomes for each final test.
- `heldout/summary.json`: confidence intervals, ablation deltas and promotion result.

Run from the repository root:

```sh
PYTHONPATH=. python3 experiments/competitive/pilot.py
python3 -m tichu.competitive train --output experiments/retrain-v2 \
  --generations 5 --population 10 --deals 64 --workers 4 --seed 819
python3 -m tichu.competitive suite --model experiments/retrain-v2/weights.json \
  --pairs 1000 --matches 150 --workers 4 --output experiments/rebenchmark-v2
python3 main.py --bot competitive --weights experiments/retrain-v2/weights.json
python3 -m unittest discover -v
```

These commands intentionally reproduce the frozen experiment. Future policy
selection needs **new** final-test seeds, rather than repeated tuning against
these now-published outcomes. The generic `tichu.selfplay evaluate` command accepts
new seeds and independently specified candidate/opponent checkpoints.

See [strategic findings](../../docs/strategic-findings.md) for the interpretation,
and [AlphaTichu comparison](../../docs/alphatichu-comparison.md) for the external
benchmark requirements and source analysis.
