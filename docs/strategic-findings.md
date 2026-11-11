# What self-play taught our Tichu bots

**11 November 2026 · local experiments · frozen policy `trained_weights.json`**

The new bot is substantially stronger than our original greedy bot. Two trained
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

To play now: `python3 main.py`. To compare: `python3 main.py --bot baseline`.
