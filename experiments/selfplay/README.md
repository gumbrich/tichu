# Self-play experiment record

Run date: 11 November 2026. Agent implementation: commit `581b83a` on
`codex/self-play-bots`; later report helpers do not change policy decisions.
Python 3.13.7, local CPU, two worker processes. No third-party dependencies.

## Data and provenance

- `pilot.json`: 80 paired exploratory deals, seeds 1000–1079; untuned vs original.
- `generator-benchmark.json`: 100 random 14-card hands, RNG seed 90811; exact
  action-set comparison and cold-cache timing versus the exhaustive oracle.
- `training/training.json`: every candidate's weights, league opponents, seed list,
  paired terminal scores and aggregate metrics, by generation.
- `training/validation.json`: every archived checkpoint's validation outcomes,
  training configuration, duration and a SHA-256 of the training record.
- `training/weights.json`: selected checkpoint, copied unchanged to
  `tichu/trained_weights.json` for play.
- `heldout/*.json`: full per-pair outcomes for each named benchmark/ablation.
- `heldout/summary.json`: aggregate metrics, model SHA-256, paired ablation effects.

The generator, rule tests and declaration adapter reject illegal actions. Each
simulation round also checks all 56 cards remain unique/conserved and that the
score total is 100 or 200 before call adjustments. All recorded runs completed
without an illegal-action, progress-limit or conservation failure. These are not
claims about every possible Tichu position.

## Exact budgets and seed separation

| Stage | Budget | Seeds |
| --- | --- | --- |
| Training | 6 generations × 12 candidates × 36 pairs × 2 sides = 5,184 rounds | Each generation g uses 10000 + 1000g through +35, g=0..5 |
| Checkpoint validation | 7 checkpoints × 80 pairs × 2 sides = 1,120 rounds | 500000–500079 |
| Round evaluation | 8 conditions × 200 pairs × 2 sides = 3,200 rounds | 1000000–1000199 |
| Full-match evaluation | 3 conditions × 60 pairs × 2 sides = 360 matches, 4,484 rounds | 2000000–2000059 |

Final evaluation therefore contains **7,684 rounds**. Paired outcomes and ablations
reuse the same deals intentionally; they are not all independent samples. Reported
uncertainty treats a deal pair as the independent unit. Full-match paired games
share a deal stream prefix, but can end after different numbers of rounds.

The league cycles between original baseline, fixed untuned planner and the
incumbent champion. Candidate selection uses final team score difference, not
individual finishing position. The top third of candidates updates the search
center; fresh training deals are used in each generation. Checkpoint selection
uses validation only, with generation 3 winning this run. Final test results were
not used to retune the shipped weights.

The solo condition keeps the improved agent's partner as the original baseline.
Its primary position alternates between the two seats of its team by seed parity;
the paired run also swaps teams. No second trained policy is secretly helping it.

## Reproduce

Run at the repository root:

```sh
python3 -m unittest discover -v
python3 -m tichu.selfplay train --output experiments/retrain \
  --generations 6 --population 12 --deals 36 --workers 2 --seed 1729
python3 -m tichu.selfplay suite --model experiments/retrain/weights.json \
  --pairs 200 --matches 60 --workers 2 --output experiments/rebenchmark
```

Reproduce only the solo full-match condition:

```sh
python3 -m tichu.selfplay evaluate --candidate trained --opponent baseline \
  --solo --mode match --pairs 60 --seed-start 2000000 --workers 2 \
  --output experiments/solo-matches.json
```

Outcomes, checkpoints and policy decisions are deterministic for the same seeds
and code. Wall-clock timings, record file hashes containing timings, and aggregate
latency will vary across runs/machines. For a genuinely new assessment rather than
reproduction, choose new, unused seed ranges; repeated checking of the published
test seeds is not a fresh held-out test.

## How to read the statistics

`mean_score_difference` is candidate-team score minus opposing-team score,
averaged over both assignments and then deal pairs. `win_rate` counts ties as 0.5.
The 95% intervals use mean ± 1.96 × sample standard error over deal pairs; these
are approximate intervals, not independent-binomial intervals over all games.
Ablation intervals use the pairwise difference between full policy and ablation
on the exact same seeds. `calls` and `first_out` count events for the candidate
team, including its unchanged partner in the solo condition. Latency is the team
mean across policy decisions, not per-action maximum latency.

Ablations disable:

- `planning`: exact partition and loose-singleton features in play/exchange value;
  the declaration gate still uses hand shape.
- `teamwork`: in-play partner support; partner-aware exchanges remain enabled.
- `exchange`: structured exchanges, replaced by the original lowest-three policy.
- `calls`: all Small Tichu calls, including immediate-finish declarations.

The strategic interpretation is in [Strategic findings](../../docs/strategic-findings.md).
