# Does move randomization help our Tichu bot

**13 November 2026. Simple move randomization did not demonstrate an improvement.**
Across 13,571 simulated rounds in tuning and final evaluation, random tie-breaking
was the best randomized setting. It then won **144/300 full matches (48.0%)**
against frozen deterministic v2, with an approximate paired 95% interval of
**45.1–50.9%**. The promotion gate failed, so deterministic v2 remained the default
at the end of this experiment. The later [scoring update](scoring-improvement.md)
promotes deterministic v3; the sampling experiment and controls here still use frozen v2.
This does not establish that every possible randomized strategy is worse.

## Measured results

Tuning used 200 deal pairs (400 rounds) per setting against each opponent. These
numbers are selection evidence, not independently validated improvements:

| Sampling setting | Margin vs deterministic v2 | Margin vs frozen v1 |
| --- | ---: | ---: |
| Deterministic control | 0.0 | +17.6 |
| Exact ties only | −1.6 | +16.0 |
| Temperature 0.1 | −10.1 | +10.0 |
| Temperature 0.5 | −9.1 | +11.3 |
| Temperature 1 | −10.8 | +8.2 |
| Temperature 3 | −23.2 | +2.6 |
| Temperature 1, maximum score gap 1 | −11.2 | +3.0 |

Margins are points per round. Random tie-breaking ranked highest among the six
randomized candidates, although the deterministic control ranked higher still.
We froze that randomized candidate before examining the final test deals:

| Final test of random tie-breaking | Result | Approximate paired 95% interval |
| --- | ---: | ---: |
| Score margin vs v2, 2,000 rounds | +0.46 / round | −1.11 to +2.03 |
| Win rate vs v2, 300 full matches | 48.0% | 45.1–50.9% |
| Score margin vs v2, those matches | −10.6 / match | −30.1 to +8.9 |
| Score margin vs older v1, 2,000 rounds | +14.0 / round | +9.7 to +18.2 |

The first two rows show no reliable advantage over v2. The last row confirms
that the candidate remains stronger than the older bot; it does not establish
that adding randomness helped. The larger-temperature settings lost ground in
tuning and were not selected for final tests. We did not isolate the cause of
those losses or test every possible temperature.

Each deal was played with team assignments swapped. Intervals use pair means,
not individual games as independent observations. Policy randomness uses separate
seeded streams for each seat; one policy-stream realization is used per deal/seat.
The interval therefore reflects combined deal and sampling variability, not an
exhaustive average over every random seed on each deal.

## Why the idea is plausible

Randomizing can make a strategy harder to exploit. The useful target is a balanced
mix of good actions, not maximum unpredictability. Poker research provides a
concrete example: Pluribus learns action probabilities through self-play and regret
minimization. It does not simply add noise to an otherwise fixed greedy policy.
Its developers explain why action frequencies matter under hidden information.
[Primary source](https://ai.meta.com/blog/pluribus-first-ai-to-beat-pros-in-6-player-poker/)

Tichu has a random deal and private cards; after the deal, its state transitions
follow deterministic rules for the chosen actions. Hidden information does not
mean a game is mathematically unsolvable: a solution can specify probabilities
that optimize expected results, rather than promise a win on every deal. Exact
large-scale solving is a separate practical challenge, especially with partners
who hold different private information.

A deterministic bot is also not fully predictable to its opponents, because they
do not see its hand. Mixing actions can reduce what its behavior reveals. An
opponent need not learn during the match to exploit a known predictable policy;
it could already have a suitable counterstrategy. Conversely, unpredictability
alone does not make an inferior move good.

## What this experiment tests

This is **inference-time randomization of the frozen v2 heuristics**. It does not
retrain the weights, learn an equilibrium, or test exploration during training.
The opponent pool consists of frozen heuristic policies, not human opponents or
an adversary trained specifically to exploit deterministic v2. Therefore these
results measure local playing strength, not resistance to exploitation or the
ability to confuse humans.

The six settings are random tie-breaking, temperatures 0.1/0.5/1/3, and temperature
1 restricted to actions within one score unit of the best. All are compared with
the deterministic control against frozen v2 and v1. The best randomized setting
is selected on tuning deals, then frozen for separate final rounds and matches.
This finite grid cannot rule out other temperatures or learned mixed strategies.

## How temperature works here

For an eligible action intent with heuristic score `s`, probability is proportional
to `exp((s - best_score) / temperature)`. Larger temperatures allow more low-scoring
moves. These are our heuristic score units, not calibrated win probabilities or
LLM logits; a temperature of 1 has no universal strength meaning.

The implementation groups equivalent move intents so a pair is not more likely
merely because it has many suit realizations. It samples intents using their best
concrete score, then chooses uniformly among the best concrete realizations of the
selected intent. Actual card identities remain part of legality and hand planning.

- Temperature zero preserves the existing deterministic policy exactly.
- `--random-ties` at zero temperature samples only exact best-score ties.
- `--max-score-gap` can exclude moves too far below the heuristic best.
- Immediate finishes and proven uninterrupted finishing sequences stay protected.
- Exchange, declarations, wishes and Dragon allocation retain their existing rules.
  Randomness affects ordinary play/pass selection and optional bomb decisions.
- Each seat has a separate policy random generator. Its stream is separate from
  the deal shuffler; both can be seeded for reproducibility.

## Try it and reproduce the experiment

Sampling remains an explicit option for frozen v2:

```sh
python3 main.py --bot competitive --random-ties --bot-seed 42 --seed 7
python3 main.py --bot competitive --temperature 0.5 --max-score-gap 1 --bot-seed 42 --seed 7
python3 main.py --bot competitive --demo --temperature 0.5 --bot-seed 42 --seed 7
python3 -m tichu.randomization --output experiments/randomization-repeat \
  --tuning-pairs 200 --test-pairs 1000 --match-pairs 150 --workers 4
python3 -m unittest discover -v
```

Changing `--bot-seed` changes choices; changing `--seed` changes deals. To reproduce
an entire run, retain both seeds and the same human actions. These controls
currently apply to the competitive bot only.

The [experiment record](../experiments/randomization/README.md) contains every
configuration and outcome. A better next test of strategic unpredictability would
learn the move distribution jointly with the policy, evaluate against opponents
trained to exploit it, and include mixed human/bot partners. That is a different
experiment from increasing this temperature knob.
