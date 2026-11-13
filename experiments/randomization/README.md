# Move randomization experiment record

13 November 2026. Implementation `521829f` on `codex/stochastic-bots`.
Python 3.13.7, local CPU, four worker processes. Frozen parent checkpoint:
`tichu/competitive_weights.json`, SHA-256
`f791544998479c02946dcd9e4b1b5df89d6fa78d72d09b5338a14fec2ffe277e`.
No weights were changed or trained during this experiment.

## Protocol

Six randomized settings were compared against two frozen opponents: v2 and v1.
The deterministic control used the same tuning deals. Selection maximized the
mean score margin, with equal weight for each opponent, **among randomized
candidates**. The best was exact tie-breaking; it still ranked below the
nonrandomized control in tuning. It was then frozen for the final tests.

Promotion required both a positive lower 95% bound on round score margin against
v2 and a lower full-match win-rate bound above 50%. The gate failed. The default
bot and its checkpoint remain unchanged; new sampling controls are opt-in.

| Phase | Budget | Deal seeds |
| --- | --- | --- |
| Tuning, including deterministic control | 7 settings × 2 opponents × 200 pairs × 2 sides = 5,600 rounds | 9000000–9000199 |
| Final rounds | 1 selected setting × 2 opponents × 1,000 pairs × 2 sides = 4,000 rounds | 10000000–10000999 |
| Final full matches against v2 | 150 pairs × 2 sides = 300 matches, 3,971 rounds | 11000000–11000149 |
| Total | **13,571 rounds** | Disjoint selection/final ranges |

Opponents share deals within each phase. The two team assignments of a seed are
one statistical cluster. Approximate 95% intervals are based on independent pair
means; round ties count as half wins. Full matches continue through tied target
scores. No results were used to retune a candidate after final testing began.

Each seat receives a separate policy PRNG, seeded from the first eight SHA-256
bytes of `policy:819:<deal-seed>:<seat>`, interpreted big-endian. This never consumes
the game's deal RNG. Absolute seats retain the same sampling stream across team
swaps. Identical stochastic policies therefore cancel exactly under the paired
control. Agents do not receive opponents' hands or authoritative game state.

The generic arena records terminal scores, declarations, first finishes, double
victories and timings. Every round checks legality, termination, unique ownership
of all 56 cards and score conservation. All recorded rounds passed. The 62-test
suite additionally checks softmax frequencies, suit-multiplicity grouping,
protected finishes, independent/reproducible random streams, unchanged zero-
temperature behavior and terminal reproduction with separate deal/bot seeds.

## Files

- `tuning-*.json`: every configuration's raw paired outcomes against each opponent.
- `selection.json`: ranking, settings, tuning summaries and paired differences
  from the deterministic control on the same tuning deals.
- `rounds-v-v2.json`, `rounds-v-v1.json`, `matches-v-v2.json`: final raw outcomes.
- `summary.json`: selected settings, checkpoint hash, seed derivation, final
  confidence intervals and the failed promotion gate.

## Reproduction

```sh
python3 -m tichu.randomization --output experiments/randomization-repeat \
  --tuning-pairs 200 --test-pairs 1000 --match-pairs 150 --workers 4
python3 -m unittest discover -v
python3 main.py --demo --random-ties --bot-seed 42 --seed 7
```

The commands reproduce this frozen experiment. A new tuning or adversarial-
learning campaign needs fresh final-test seeds. Timings can vary by machine;
policy/deal seeds and score outcomes are the reproducibility target.

See [randomization findings](../../docs/randomization-findings.md) for conclusions
and the distinction between temperature noise and a learned mixed strategy.
