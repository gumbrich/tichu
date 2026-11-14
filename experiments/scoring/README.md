# Scoring and search-policy learning experiments

The frozen selection is `selected.json` (SHA-256
`b7883435e25b66f84baaf84383465848bcdbb7157e4b0d1b522acd82df73f5dd`).
It is a 50/50 blend of standardized frozen-planner and learned move scores.
The learned coefficients come from supervised search-policy distillation,
not neural reinforcement learning. Final tests use a model snapshot and never
feed back into this selection.

## Final result

The promotion gate passed and this exact checkpoint is shipped as
`tichu/scoring_weights.json` (v3, default). Frozen v2 remains unchanged.

| Test | New policy | Frozen-v2 comparison |
| --- | ---: | ---: |
| Native direct round margin vs v2, 2,000 rounds | +25.545 [21.339, 29.751] | opponent |
| Native direct full matches vs v2 | 213/300 wins, 71.0% [66.4%, 75.6%] | opponent |
| External search round margin, 2,000 rounds per policy | +2.215 [−5.110, 9.540] | −21.910 [−28.997, −14.823] |
| External search full matches, 200 per policy | 89 wins, 44.5% [38.0%, 51.0%] | 59 wins, 29.5% [23.1%, 35.9%] |

The matched external improvement is **+24.125 points/round [17.112, 31.138]**
and **+15.0 percentage points of match wins [7.3, 22.7]**. The new policy has not
demonstrated superiority over the search opponent. The final suite contains
14,416 rounds in total, including rounds within full matches; 8,620 use the
external referee, with zero adapter errors or fallback moves.

All four diagnostic component-benefit intervals include zero. Even removal of
the entire learned ranker is inconclusive on the smaller 128-pair diagnostic set
(full minus removal −0.469 [−21.268, 20.330]). These checks do not isolate the cause
of the combined policy's gain and did not trigger retuning. Exact outcomes are in
[`final/comparison.json`](final/comparison.json),
[`final/match-win-change.json`](final/match-win-change.json),
[`final/score-components.json`](final/score-components.json), and
[`diagnostics/component-benefits.json`](diagnostics/component-benefits.json).

## Validation, used for selection

External columns compare each candidate's margin against `eg:pimc20/hibs`
with frozen v2 on the same 256 paired deals. Native columns are direct play
against v2 on 128 paired deals. Brackets are approximate paired 95% intervals.
These are selection results, not final performance estimates.

| Candidate | External gain over v2, points/round | Native margin vs v2, points/round |
| --- | ---: | ---: |
| finish-only | +0.02 [-4.39, +4.43] | -0.23 [-3.17, +2.70] |
| search-00 | +1.25 [-14.13, +16.63] | -6.95 [-20.81, +6.91] |
| search-03 | -22.91 [-39.96, -5.86] | -16.13 [-30.35, -1.91] |
| small-and-grand | -0.02 [-6.78, +6.74] | +1.60 [-3.81, +7.01] |
| blend-50 | +17.07 [+3.15, +30.99] | +21.17 [+9.65, +32.69] |

Only `blend-50` had positive means in both checks. Its selection was committed
before using final seeds. The last random candidate's external run continued
to completion after its negative native result had already excluded it.

## Record map

| Directory | Purpose | Base seed / size |
| --- | --- | --- |
| `screen-corrected` | 16 heuristic settings | 16002000 / 64 paired deals each |
| `corrected-baseline` | frozen-v2 screen comparator | 16002000 / 64 pairs |
| `call-screen` | four call-only settings | 16002000 / 64 pairs each |
| `teacher` | independently seeded search-bot self-play and public-view features | 16200000 / 512 rounds |
| `distilled` | 30 training epochs, best grouped-validation checkpoint | optimizer seed 16281 |
| `learned-screen` | pure learned scores and 25% / 50% blends | 16002000 / 64 pairs each |
| `validation`, `call-validation`, `learned-validation` | five finalists | external 17000000 / 256 pairs; native 17100000 / 128 pairs |
| `validation-baseline` | frozen-v2 external comparator | 17000000 / 256 pairs |
| `final` | frozen final round/match comparisons and promotion checks | sizes and seeds in `manifest.json` |
| `diagnostics` | component removals; never used to retune | 19200000 / 128 pairs each |

`screen` contains an interrupted development run before Dragon/interrupt fixes;
its unfinished manifest is marked accordingly. `pilot`, `native-initial-screen`,
`imitation-smoke` and `frozen-regression` are engineering checks, not final strength
claims. The frozen regression reproduced all moves, calls and scores of the
previous 20-round run. `screen-baseline` belongs to the interrupted screen.

External records retain model and binary hashes, pinned opponent revision, exact
post-game decks/actions, independently audited scores, errors and fallback counts.
The teacher contains 19,905 nontrivial decisions / 109,208 distinct feature options;
17,475 decisions train the model and 2,430 from separate whole deals validate it.
Inference never receives an opponent's private hand. Full raw teacher logs exist
for referee replay, not as model inputs.

See [the protocol and reproduction commands](../../docs/scoring-improvement.md)
and [strategic findings](../../docs/strategic-findings.md). A known-seed rerun
reproduces an experiment; it is not another fresh estimate. The teacher is the
same search configuration used in the external benchmark, so the opponent is
familiar even though evaluation deals are unseen.
