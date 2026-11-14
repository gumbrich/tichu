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
