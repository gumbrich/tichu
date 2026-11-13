# What self-play taught our Tichu bots

## Move randomization follow-up

**13 November 2026.** An additional 13,571 simulated rounds tested six randomized
settings against frozen v2 and v1. Higher temperatures lost ground during tuning.
The best randomized setting, exact tie-breaking, won **144/300 final matches
(48.0%, paired 95% interval 45.1–50.9%)** against deterministic v2. Its separate
round score margin was **+0.46** (−1.11 to +2.03). Neither shows a reliable gain,
so the default remains deterministic. Balanced mixed strategies can be useful
under hidden information; these tests cover added sampling noise on fixed
heuristics, not learning a mixed strategy or confusing adaptive humans.
See [the randomization findings](randomization-findings.md) for the temperature
curve, controls, limits and reproduction commands.

## Competitive policy update

**11 November 2026 · v2 · `competitive_weights.json`**

The new default team beat our frozen v1 trained team in **211 of 300 full matches
(70.3%)**, with an approximate paired 95% interval of **66.2–74.5%**. The round
score advantage was **+15.5 points** (11.2–19.8) over 2,000 separate test rounds.
This clears the promotion gate in both settings. Against the original greedy
bots, v2 won **287/300 matches (95.7%)**. All comparisons use two bots per team;
v2's results with an unfamiliar human partner remain unknown.

### What the new experiments teach

**Prove a finish when possible.** A good hand partition does not guarantee that
you keep the lead. The new bot searches small hands for a sequence where every
non-final play is unanswerable, even by the partner, under conservative bounds
on the unseen cards. It accounts for bombs, Phoenix, card counts and outstanding
wishes. A Dragon is not automatically secure while someone might hold a bomb;
the Dog cannot retain your lead. Removing this proof search cost **2.4 points per
round** (95% interval 1.0–3.8) against v1, with other parameters held fixed.

**Retest intuitive scoring rules.** Bonus scores for secure plays, possible enemy
finishes and trick points sounded useful, but their combined incremental effect
was **−2.7 points per round** (−5.9 to +0.5). This does not establish a benefit,
and the point estimate favors removing them. The no-bonus variant scored +18.2
against v1 on these rounds. It is a candidate for a *fresh* selection and test
cycle; choosing it using these final outcomes would spend the test set. The
shipped policy remains the validation-selected checkpoint that won 70.3% of full
matches. Its overall improvement includes retuned existing play weights; these
experiments do not isolate tuning as a separate causal effect.

**Separate known absence from a voluntary pass.** Ignoring a compulsory,
playable singleton wish can prove that a rank is absent; an optional pass cannot.
The bot records structured public history and uses only that strict deduction.
Disabling the history deduction changed **zero recorded scores in 2,000 rounds**.
It is useful correctness infrastructure, but this run provides no measured
strength benefit for it. Current public cards, hand sizes and known sent gifts
still inform bounds when that history feature is disabled.

**A stronger local opponent is the right next test.** The earlier 90.8% win rate
was against our weakest bot. The new gate compares against the frozen trained
policy, preserving a clear chain of evidence. Neither result establishes a win
against AlphaTichu master or a human ladder rating. See the
[AlphaTichu comparison](alphatichu-comparison.md) for its imitation/self-play
approach, failed search experiments and the missing master-model artifacts.

### Results and reproducibility

| Opponent and setting | v2 win rate | 95% interval | Score margin |
| --- | ---: | ---: | ---: |
| Frozen v1, 2,000 rounds | 55.3% | 53.6–57.0% | +15.5 / round |
| Untuned planner, 2,000 rounds | 58.2% | 56.3–60.0% | +25.6 / round |
| Original greedy bots, 2,000 rounds | 70.3% | 68.4–72.2% | +66.1 / round |
| Frozen v1, 300 full matches | **70.3%** | **66.2–74.5%** | +242.2 / match |
| Original greedy bots, 300 full matches | **95.7%** | **93.4–97.9%** | +647.1 / match |

Evolutionary policy search evaluated 6,400 training rounds, followed by 3,600
validation rounds. The final tests and feature removals covered 19,031 rounds,
including 600 full matches; an earlier pilot added 1,000 rounds. That is
**30,031 simulated rounds** in this iteration, with separate seed ranges for
training, selection and final evaluation. This is CPU policy optimization,
not neural-network training. All simulations completed with legality,
termination, card-conservation and score-conservation checks.

Confidence intervals use independent deal-pair means, with both team assignments
played for every seed. Feature-removal effects use differences on the same pairs
and cannot be summed. Typical mean v2 decision time in these tests was about
0.9–1.3 ms on the development machine. The
[competitive experiment record](../experiments/competitive/README.md) contains
all candidates, outcomes, seeds, checkpoint hashes and reproduction commands.

Play v2 with `python3 main.py`; retain v1 with `python3 main.py --bot trained`.
Next priorities are a fresh test of the simpler no-bonus candidate, calibrated
calls and mixed partners, and a reproducible external master opponent. Hidden-hand
search and neural RL should be evaluated as experiments, not assumed upgrades.

## First self-play policy results

**11 November 2026 · v1 experiments · frozen policy `trained_weights.json`**

The first self-play bot is substantially stronger than our original greedy bot. Two trained
partners won **109 of 120 full matches (90.8%)** against the original bots.
One trained player with an unchanged original-bot partner won **93 of 120
matches (77.5%)**. This is evidence of local improvement, not a prediction of
human ladder strength.

## The five practical findings

**1. Plan the whole hand, not just the next large play.** A six-card play is not
necessarily better than a pair if it leaves five awkward singletons. The bot
searches exact partitions of its own hand into legal combinations, preserving
suit identity and Phoenix alternatives. Removing that planning from action and
exchange evaluation reduced its advantage by **48.8 points per round** (95%
interval: 32.3–65.4). This was the largest measured effect. A minimum-play plan
is still only a plan: it does not guarantee the intervening leads.

**2. Do not spend good cards just to beat your partner.** Passing behind a partner
who is still playing can preserve control cards and support their finish. Take
exceptions seriously: going out immediately, a compulsory wish, or an opponent
about to finish can outweigh cooperation. Removing partnership-aware play reduced
the advantage by **23.0 points per round** (12.5–33.4). The exchange policy still
supported the partner in this ablation, so this is specifically evidence about
in-play cooperation, not the value of all teamwork combined.

**3. Exchange cards as part of a hand plan.** Simply giving away the three lowest
cards can dismantle a pair sequence or straight. The new bot considers which
three cards to send, the structure left behind, the strength sent to opponents,
and a useful card for its partner. Reverting to the original exchange policy
cost **21.9 points per round** (6.0–37.8). “Always give the partner your highest
card” is too simple; the cost to the remaining hand also matters.

**4. A Tichu call needs evidence; it is not the source of most of this improvement.**
The bot uses its hand structure and control resources to decide Small Tichu,
and does not call against an existing partner declaration. It made 29 of 43 calls
in the held-out round test against the original bots. But disabling calls changed
the score advantage by only **1.8 points per round** (−2.0 to +5.5): this experiment
does **not** establish a reliable incremental benefit from calls. Grand Tichu
remains disabled. Calibrating calls against stronger opponents is future work.

**5. Learning the balance helps; the latest checkpoint is not automatically best.**
Evolutionary self-play tuned the relative importance of shedding, preserving
control, partnership support, bombs, exchanges and declaration thresholds. The
selected model came from generation 3, not the final generation. Against the same
original-bot test deals, tuning improved the untuned planning policy by **22.5
points per round** (9.7–35.4). Individual learned weights are not universal rules;
these results apply to this policy family and opponent set.

Bomb timing and emergency blocking are part of the policy, but we did not isolate
their individual contributions. There is not enough evidence here to prescribe a
universal bomb threshold or claim that a specific wish strategy is optimal.

## Measured strength

Every deal was played twice with team assignments exchanged. Round tests use
200 deal pairs (400 rounds); match tests use 60 deal pairs (120 matches to 1000).
Intervals below are approximate 95% intervals computed over independent deal pairs.
Round ties count as half a win; full matches continue through tied target scores.

| Test | Win rate | 95% interval | Mean score margin |
| --- | ---: | ---: | ---: |
| Untuned planning team vs original bots, rounds | 57.5% | 53.1–61.9% | +27.8 / round |
| Trained team vs original bots, rounds | 65.4% | 60.5–70.2% | +50.3 / round |
| Trained team vs original bots, full matches | **90.8%** | 85.9–95.8% | +494.9 / match |
| One trained player + original partner vs original bots, full matches | **77.5%** | 70.3–84.7% | +349.4 / match |
| Trained team vs untuned planning team, rounds | 57.1% | 52.5–61.8% | +14.7 / round |
| Trained team vs untuned planning team, full matches | 56.7% | 49.1–64.2% | +85.2 / match |

The final line is **not conclusive evidence of a full-match advantage** over the
untuned planning team: its win-rate interval includes 50%. The large 90.8% result
is against the original, deliberately weak baseline, which was preserved and
checked against its historical seeded match results.

## How it learned

The method combines exact own-hand planning with **evolutionary policy search**:
perturb interpretable weights, play completed games, select by team score, and
repeat against a league of the original bot, the untuned planner and a previous
champion. This is reward-driven self-play optimization, not a trained neural
network or a claim that deep RL was compared and beaten.

The run evaluated 72 candidates across six generations: **5,184 training rounds**,
then **1,120 validation rounds** for checkpoint selection. Final evaluation and
feature-removal experiments covered **7,684 additional rounds**, including the
rounds inside full matches. Training, validation and final test seeds were separate.
The pilot's 160 rounds were exploratory and are not included in those totals.

Agents receive immutable observations with their own cards and public facts, never
opponents' hands or the undealt deck. The production move generator agreed exactly
with exhaustive enumeration on the test corpus. A separate 100-hand cold-cache
benchmark measured **4.8× faster generation**. Typical mean decision time was about
1 ms in the trained-team benchmarks on the development machine; it is not a
real-time service guarantee. No neural libraries or GPU were needed.

## Limits and the next strength step

The policy has no hidden-hand search, no learned opponent model, no Grand Tichu,
and no match-score-aware risk. Its calls occur at its own decision opportunities;
it does not yet signal Small Tichu before the exchange. Its “control” feature counts
high cards and bomb options, not guaranteed future trick wins. Some feature removals
interact, so their effects should not be added together.

For the next engine, keep this policy as the fast baseline and rollout policy.
Add public-history-consistent hidden-hand sampling and bounded search, then test
against diverse policies and unfamiliar partners. A single improved agent did
help a weak partner here, but human coordination remains untested.

The [experiment record](../experiments/selfplay/README.md) contains raw outcomes,
parameters, seeds and reproduction commands. The [online-agent plan](online-agent-plan.md)
covers the later site integration; no online account or ladder play was started.

To reproduce the v1 policy: `python3 main.py --bot trained`. To compare: `python3 main.py --bot baseline`.
