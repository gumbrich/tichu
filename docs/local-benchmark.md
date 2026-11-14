# Local external benchmark

This records the original frozen-v2 benchmark. The subsequent
[scoring-policy experiment](scoring-improvement.md) trains and verifies v3 on
separate deals while preserving this reference opponent and the v2 checkpoint.

## Fixed protocol — 14 November 2026

No account is required. Dave Orr's public [Tichu-ai](https://github.com/dave-orr/Tichu-ai)
is pinned to `ede1c2948eff1bcbc27bafd8c8af385253475b59` (25 October 2026).
It has no explicit license at this revision. We reference it as a separate
dependency; we do not vendor its source or publish its binary.

Our participant is the unchanged deterministic competitive-v2 policy and model
SHA-256 `f791544998479c02946dcd9e4b1b5df89d6fa78d72d09b5338a14fec2ffe277e`.
No training or policy tuning occurs during this experiment.

Primary opponent: **`eg:pimc20/hibs`**. It samples 20 hidden deals per candidate,
uses h2 rollout policies, weighs deals by observed play, searches bombs/wishes/
Dragon gifts, and adds the exact two-player endgame solver. This is a bundled
search configuration, not the unpublished trained neural model. Thinking time
is not equalized, and this is not necessarily the project's strongest setting.

Before starting, freeze **1,000 paired deals**, base seed **14000000**. Each pair
uses `mix(seed, pair_index, 0)` from the external arena and is played twice,
swapping teams. Primary outcome: our mean round point margin and a normal
approximation 95% interval across pair averages. Pilot seed 11000000 (ten pairs)
is excluded. No stopping based on scores or discarding unfavorable deals. Any
rule/transport failure invalidates the aggregate until investigated.

Secondary fixed test: **100 paired match seeds**, base seed **15000000**, two
games to 1,000 per seed (200 full matches). Use the same frozen participants.
Report wins and a 95% interval across paired win indicators. Both seatings share
the deck stream, although match lengths can differ. Do not tune or stop based on
outcomes. Human ladder strength remains a separate future measurement.

## Referee and adapter

The unmodified external Rust simulator referees both teams. Only its `PlayerView`,
legal choices and decision kind enter our Python subprocess. No opponent hands or
deck enter either bot. Oracle configurations are rejected. Full deals and action
logs are saved **after** rounds for audit, never sent to playing agents.

Every play/bomb request compares the external legal list to our generator with
the external wish convention. Our original move ordering preserves frozen tie
breaking. Cards, Phoenix readings, Dragon strength (external 15, ours 16), exchange
recipients and public history are translated explicitly. Errors and 30-second
Python response timeouts stop the run. There is no fallback policy.

Differences from our normal referee:

- External bombs are wish-exempt on ordinary turns too. History inference must
  not treat an exempt bomb as evidence that the player lacks the wished rank.
- Bomb windows occur after plays/bombs and before trick collection, not after
  intermediate passes. Terminal plays can end the round immediately.
- Small Tichu is available only during play, before one's first card and before
  anyone goes out. The simulator offers calls initially and before own turns;
  it cannot combine a call with an interrupt bomb. Our adapter preserves v2's
  own-turn call behavior rather than adding earlier calls. Its separate call
  callback also means play is evaluated again after a successful declaration,
  unlike our native combined call/play decision.
- Grand decisions are simultaneous. Our terminal game exposes them sequentially;
  our frozen v2 always declines Grand.

Results describe this external referee, not identical rules between engines.
Our normal game's rules and policy remain intact. Python independently recomputes
round scores from captured cards, remaining hands, finishing order and calls,
and checks conservation of all 56 cards.

## Run and test

Requires Python 3.10+ and Rust. No model download, GPU, account or API key is needed.

```sh
cargo build --release --locked --manifest-path tools/dave_bridge/Cargo.toml
python3 -m unittest discover -v
python3 -m tichu.external benchmark --opponent eg:pimc20/hibs \
  --pairs 1000 --seed 14000000 --workers 4 --output experiments/external/reproduction
```

Use a new output folder. It receives a manifest (source/model/binary identities),
compressed raw paired results with complete logs, stderr and summary. Failed runs
retain partial uncompressed records and have no strength summary. Worker counts
do not alter seeds. For a quick pilot use `--pairs 10 --seed 11000000`.
For full matches use `--mode games` with a fresh seed and fixed sample size; each
pair then comprises two games to 1,000. Match intervals cluster by seed pair.

Test the external repository separately at its pinned revision with
`cargo test --release`. Building our bridge does not run dependency tests.
We installed Rust in temporary folders without changing shell settings for this
session; a normal Rust installation works with the commands above.

## Verification

- External Rust suite: 75 tests passed locally.
- Our suite: 62 existing tests and 11 adapter tests passed.
- The initial pilot caught a Dragon strength encoding mismatch and stopped.
  It is retained as failed development evidence, excluded from strength results.
- Corrected 20-round pilots passed legality, transport, scoring and conservation
  checks. Pilot results are not strength claims.
- The standard-search pilot reproduced identical actions, scores and request
  counts with one worker and four workers (timings excluded).
- [GitHub Actions run 43604832988](https://github.com/gumbrich/tichu/actions/runs/43604832988)
  passed the Python matrix and new Rust adapter compatibility job on Linux.

## Completed results

Our team scored **−18.67 points per round** (paired 95% interval −26.00 to −11.34)
over the 2,000 independent test rounds. It won **49/200 full matches (24.5%)**
(paired 95% interval 18.5–30.5%), with mean final margin −287.45 points. The two
tests completed 4,268 rounds with zero errors/fallbacks and 178,165 Python decision
requests. Every recorded round passed independent scoring and card conservation.

See [the complete experiment record](../experiments/external/README.md) for raw
results and [strategic findings](strategic-findings.md) for the measured gaps.
