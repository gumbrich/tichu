# Scoring and declaration improvement cycle

14 November 2026. Work on `codex/scoring-and-calls`; frozen v2 and the external
opponent remain unchanged. Previous benchmark seeds 14000000/15000000 are spent
evaluation data and will not be used to select this policy.

## Experiments

The experimental `scoring` policy adds point/control estimates, declaration
defense, protection of a partner's unresolved call, stronger equivalent finishing
plays, and an eight-card Grand Tichu threshold. It inherits the existing hand
partitioning and conservative finish proofs. This is a new policy family and
parameter-selection experiment, not neural RL or proof of optimal Tichu play.

Control estimates use only unseen-card counts and our own sent cards. Singleton
answer probabilities use hypergeometric tails, pairs/triples and bombs use union
bounds, and longer shapes use a documented heuristic. These estimate possible
answers, not calibrated winning probabilities. No actual hidden hands enter the
policy. Grand decisions see only the initial eight cards and already public calls.

Sixteen initial parameter configurations are screened against the unchanged
`eg:pimc20/hibs` opponent on 64 paired deals, base seed 16001000. Eight vary specific
features; eight randomly vary play/call parameters with PRNG seed 16381. Keep all
results, including losing candidates. Pilot seed 16000000 is excluded.

The first screen was interrupted during development to fix Dragon point valuation,
Dragon gifting and partner-call protection during native bomb windows. Its
completed and partial runs remain under `screen`; unfinished manifests are marked
interrupted. The corrected complete screen uses base seed **16002000** and folder
`screen-corrected`. No final evaluation seeds were used or inspected.

Validate the top three on 256 paired deals, base seed 17000000, alongside frozen
v2. Also check the three finalists against v2 in our native referee on 128 paired
validation deals starting at 17100000. Select by external validation mean among
candidates with a positive native validation margin, never by a final-test outcome. If this family
fails, record it and develop another candidate before spending the final seeds.

Once selected, freeze code and model, then run 1,000 paired external deals (base
seed 18000000), comparing candidate and v2 against the same external bot and deals.
Run 100 paired match seeds (base seed 18100000) per policy. Require the paired
improvement interval to exclude zero and verify direct native-engine play against
v2 on new seeds starting 19000000. A global default promotion additionally requires
a positive native round margin and full-match advantage with uncertainty excluding
zero/50%. If not met, keep the candidate opt-in and report the limitation.

Do not claim that a threshold is calibrated merely because it was tuned: report
held-out call frequency, success rate and point contribution. Feature removals use
separate diagnostic deals and do not change the frozen final candidate.

## Search-policy distillation experiment

In parallel with screening, generate 512 fresh rounds of external-search-bot
self-play, base seed 16200000. Replay these rounds through the pinned referee to
export only each acting seat's `PlayerView`, legal choices and chosen move.
No private opponent hand enters the feature encoder. Learn a linear softmax move
ranker with Adam (NumPy during training; standard-library inference). Keep entire
deals together: indices divisible by eight form the imitation validation split.
This is supervised imitation of search decisions, not neural RL, and prediction
accuracy alone is not evidence of playing strength.

After training, compare this candidate on the same separate arena validation
deals as the heuristic finalists. It must pass the same fresh final-test and
native-engine gates before promotion. Its calls, exchanges and bombs remain the
tested scoring-policy components, with a conservative Grand threshold until
arena validation supports a different setting. Teacher training examples do not
use any previous benchmark's final-test deals.

Screen learned move scores alone and at 50% / 25% influence, with the remaining
influence coming from the frozen tactical planner. Normalize each policy's legal
choice scores within the decision before blending, to avoid arbitrary score units.
These three settings use the spent 64-pair screening deals; validate only their
screen winner on the separate arena validation set. Non-play preferences retain
frozen weights plus the structural corrections, with Grand threshold 4.2.

The initial screen also motivates a separate call-only diagnostic: keep the
structural corrections and zero additional point/initiative/defense weights,
then compare Grand thresholds 3.0, 3.6 and 4.2; a fourth candidate adds king
control 0.25 and Small threshold adjustment -0.2. Use the same spent screening
deals (16002000), select its best on screening only, and add it to the separate
256-pair external / 128-pair native validation. This isolates calls from the
point-weight changes instead of concluding that calls caused a combined
policy's regression. Final seeds remain untouched.
