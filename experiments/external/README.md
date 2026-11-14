# Account-free external benchmark record

The completed independent-round test gives our frozen v2 **−18.67 points per
round** (paired 95% interval **−26.00 to −11.34**) against `eg:pimc20/hibs` across
2,000 rounds. All 1,000 paired deals completed with zero errors/fallbacks and
82,991 Python decision requests. Both legal-move agreement and independent final
score/card-conservation checks passed. `search-1000/score-components.json` is a
descriptive decomposition, not a causal ablation.

The separate full-match test completed **200 matches**, containing **2,268
rounds**. Our team won **49/200 (24.5%)**, paired 95% interval **18.5–30.5%**.
Our final-score margin averaged **−287.45** (−351.26 to −223.64). There were zero
errors/fallbacks across 95,174 Python decision requests. Both main tests completed
all predeclared pairs and every scoring/conservation audit. Total: **4,268 rounds**.

| Main outcome | Our result | Paired 95% interval |
| --- | ---: | ---: |
| Independent-round margin | −18.67 points | −26.00 to −11.34 |
| Full-match win rate | 49/200, 24.5% | 18.5–30.5% |
| Full-match final-score margin | −287.45 points | −351.26 to −223.64 |

The external configuration is clearly stronger in these tests. It is not an
equal-compute comparison; our policy is a fast planner, while its search explores
20 sampled deals per candidate and adds inference and endgame search. No claim
is made about its unpublished neural models, other budgets or human ladder play.

The [protocol and reproduction instructions](../../docs/local-benchmark.md) pin
Dave Orr's Rust engine, our unchanged v2 model and the sample sizes before the
main runs. Both teams play under the unmodified external referee. These are local
matches, not games against an online service or the author's unpublished neural
model. No account was created and no online game was played.

## Main runs

| Folder | External opponent | Base seed | Fixed sample |
| --- | --- | ---: | ---: |
| `search-1000` | `eg:pimc20/hibs` | 14000000 | 1,000 paired deals / 2,000 rounds |
| `matches-100` | `eg:pimc20/hibs` | 15000000 | 100 paired seeds / 200 games to 1,000 |

Each manifest records the Git revision, model checksum, adapter checksum,
compiled-binary checksum, exact command and completion status. `pairs.jsonl.gz`
retains individual outcomes, both seatings, deals, action histories, terminal
hands/captured cards and calls. Full hands appear only in post-round audit data;
agents receive only their own view. `summary.json` is written only after all
expected pairs and independent scoring/conservation checks pass.

Margin intervals use independent pair averages, not individual rounds as if
they were independent. Match-win intervals use paired win indicators. The seeds
are mapped through the pinned external arena's `mix` function; they are not our
Python deck shuffler's seeds. Match lengths may differ between swapped seatings.
No parameters or policies were changed based on these main outcomes.

## Development and validation runs — excluded from strength estimates

- `pilot`: first attempted bridge run stopped on a Dragon play-strength mapping
  error (external uses 15, our policy uses 16). Its partial failures are retained.
- `pilot-fixed`: encoding corrected; 20 rounds with `pimc20` completed. Earlier
  logging format records scores/results but not the later complete audit state.
- `pilot-audited`: same 20 rounds, now with independent scoring and complete logs.
- `pilot-single-worker`: identical actions, scores and request counts to
  `pilot-audited` with one worker instead of four. Only timings differ.
- `pilot-search-full`: 20 rounds with the richer search configuration. Selection
  of this configuration is based on its feature coverage, not its pilot score.
- `match-smoke`: four full matches on seed 11010000 to check match rollover,
  persistent subprocesses and scoring. Too small for a strength claim.

All round pilots reuse seed 11000000. They are repeated engineering checks, not
independent samples and not part of the main results. The no-fallback adapter,
legal-move comparison and 30-second Python response deadline apply throughout.

## Validation

75 tests in the separately checked-out external engine and 73 tests in our
repository passed locally. Direct and wrapped cheating oracle configurations
were rejected before playing. The CI workflow builds the pinned bridge and
runs a small compatibility test. [Run 43604832988](https://github.com/gumbrich/tichu/actions/runs/43604832988)
passed, including the Python matrix and external adapter job on Linux.
