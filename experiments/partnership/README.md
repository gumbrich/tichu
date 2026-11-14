# Partnership, bidding and larger search distillation

14 November 2026. Working branch: `codex/partnership-and-bidding`.
See the [short strategy playbook](../../docs/strategy-playbook.md) and the
[research and fixed protocol](../../docs/partnership-improvement.md).

## Evidence map

| Directory | Purpose | Sample or evidence |
| --- | --- | ---: |
| `bid-screen/` | 20 declaration settings, same play policy | 64 pairs each |
| `bid-baseline/` | Frozen v3 on the bidding deals | 64 pairs |
| `team-screen/` | 12 passing, timing, wish and randomness variants | 96 pairs each |
| `teacher/` | Fresh search self-play, never evaluation data | 2,048 rounds |
| `learned/` | Grouped-validation-selected linear ranker | 81,698 decisions |
| `development/blends/` | Three learned/planner blends plus v3 | 128 pairs each |
| `development/combinations/` | Four combinations on fresh deals | 128 pairs each |
| `development/risk/` | Three match-score risk settings | 32 match pairs each |
| `validation/` | Two frozen finalists and shared v3 control | Reserved validation suite |
| `tie-diagnostic/` | Isolated exact-tie variation on the larger-corpus model | 256 pairs per setting |
| `freeze/` | Selected deterministic model and selection audit | No additional games |
| `final/` | Frozen final comparisons, score accounting and pairing audit | 6,000 standalone rounds + 1,100 full matches (19,143 rounds total) |
| `representation-diagnostic.json` | A residual-pair feature collision | Constructed observation, not a strength test |

The reference is Dave Orr's `eg:pimc20/hibs`, pinned at
`ede1c2948eff1bcbc27bafd8c8af385253475b59`. It is also the search teacher: evaluation
uses unseen deals against a familiar policy, not an unseen opponent family. These
results do not measure AlphaTichu, the unpublished neural model, or online ratings.
No account or live opponent is involved.

Each external run includes an immutable model snapshot, provenance manifest,
compressed paired game logs and independently audited scores. Screening and
validation select models; their intervals are exploratory. Only the selected,
frozen model may use the reserved final seeds. Reused validation controls are
the same evidence, not extra games. The final reference-victory and default-promotion
gates did not pass, so the default remains v3.

## Final outcome

The candidate is frozen at `freeze/candidate.json`, SHA-256
`f46c02e4160dbf597ed13d3485171f15e35976d564b9f2c9b4815e1426fc90d6`.
It improves round scoring against the reference but does not establish superiority
in full matches or earn default promotion. No model or gate changed during testing.

| Fixed final comparison | Result | Approximate paired 95% interval |
| --- | ---: | ---: |
| Candidate vs search, 2,000 rounds | +5.545 points/round | −1.36 to +12.45 |
| V3 vs search, same 2,000 rounds | −4.170 points/round | −11.34 to +3.00 |
| Paired round improvement over v3 | **+9.715 points/round** | **+2.97 to +16.46** |
| Candidate vs search, 400 full matches | 202 wins / 50.50% | 45.69–55.31% |
| V3 vs search, same 400 full matches | 181 wins / 45.25% | 40.61–49.89% |
| Paired external match-win improvement | +5.25 percentage points | −0.62 to +11.12 points |
| Direct native candidate vs v3, 2,000 rounds | +0.355 points/round | −3.87 to +4.58 |
| Direct native candidate vs v3, 300 full matches | 152 wins / 50.67% | 46.03–55.30% |

The candidate's mean external final-match margin is +82.125 points (+27.07 to
+137.18), versus v3 +11.750 (−43.37 to +66.87). Their paired difference is
+70.375 (+7.28 to +133.47). Higher average scores do not by themselves establish
more match wins. The final suite contains 13,315 external rounds and 5,828 native
rounds; all external runs had zero errors/fallbacks. Deck-prefix, seed and model
checks are recorded in `final/pairing-audit.json`. Score components are descriptive
outcome accounting, not causal estimates of feature importance.

## Reproduce training

Inference and tests use the standard library. Training used NumPy 2.2.6. Build
the pinned bridge with Rust, then use a fresh output directory:

```sh
cargo build --release --locked --manifest-path tools/dave_bridge/Cargo.toml
mkdir -p /tmp/tichu-reproduce
python3 -m tools.collect_search --source /tmp/tichu-reproduce/teacher.jsonl \
  --output /tmp/tichu-reproduce/teacher.jsonl.gz \
  --binary tools/dave_bridge/target/release/tichu-external-benchmark \
  --count 2048 --seed 21200000 --workers 8
python3 -m tichu.imitation extract /tmp/tichu-reproduce/teacher.jsonl.gz \
  --output /tmp/tichu-reproduce/features.npz --workers 8
python3 -m tichu.imitation train /tmp/tichu-reproduce/features.npz \
  --epochs 30 --output /tmp/tichu-reproduce/learned
```

Collection resumes missing deterministic deal indices after interruption. The
new corpus has 71,489 training decisions and 10,209 validation decisions; whole
deals, including all four seats, remain together. This is supervised search
distillation, not policy-gradient reinforcement learning.

## Run a candidate or a fixed suite

```sh
python3 main.py --bot scoring \
  --weights experiments/partnership/freeze/candidate.json
python3 main.py --bot partnership \
  --weights experiments/partnership/development/risk/risk0.4.json
python3 -m unittest discover -v
python3 -m tools.evaluate_partnership --stage validation \
  --model experiments/partnership/development/blends/blend0.75.json \
  --output /tmp/tichu-reproduce/validation --workers 8
# Reproduce the frozen final suite; do not use these observed seeds for selection:
python3 -m tools.evaluate_partnership --stage final \
  --model experiments/partnership/freeze/candidate.json \
  --output /tmp/tichu-reproduce/final --workers 8
```

Existing output directories are rejected to protect recorded evidence. The
experimental partnership models store their own temperature, tie-breaking seed
and score-gap limit; legacy v2 CLI sampling flags are a separate experiment.
