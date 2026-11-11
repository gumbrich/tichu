# AlphaTichu comparison and competitive plan

**11 November 2026.** AlphaTichu is a credible, substantially more developed
opponent. Our local improvements do not establish that we can beat its master
model. A direct comparison needs its trained weights or an agreed testing API;
neither was available in the public repository inspected for this work.

## How their AI works

The [Reddit announcement](https://www.reddit.com/r/tichu/comments/1vkgeam/i_trained_an_ai_on_24_million_bsw_games_and_i/)
links to the [source repository](https://github.com/ainze/tichu) and a
[technical report](https://github.com/ainze/tichu/blob/bd044222b89dd1db269e3a19940b7aeb460afafa/AlphaTichu.pdf).
The report describes:

- **Human imitation first.** Approximately 2.4 million BrettSpielWelt games,
  replay-validated against its rules engine. Player-skill conditioning steers the
  same network toward stronger human examples.
- **A compact neural policy.** A residual network selects among 1,809 action
  intents, with a resolver choosing concrete cards. Play, wishes and Dragon
  assignment share a trunk; exchange and the two declarations have separate
  networks. The v7 representation includes public history and the legal mask.
- **Co-training with safeguards.** Play, exchange and declaration policies improve
  together through self-play, constrained toward a frozen reference. Promotion
  uses paired deals and a held-out opponent. A privileged critic used during
  training is distinct from giving a playing agent access to opponents' cards.

The report's +8.26 points per round is a gain over its own previous champion,
with a reported 95% interval of +7.18 to +9.44 across 81,920 seat-swapped
observations. It is not directly comparable to
our gain over a weaker heuristic bot. Its 99% top-five imitation agreement is
also not a win rate. The author explicitly leaves superhuman strength unverified.
These are the author's experimental results, not measurements reproduced here.

## Lessons that affect our approach

Their unsuccessful search experiments are especially relevant. A determinized
planner can combine decisions that require different hidden knowledge into one
unrealizable strategy. More search can also reinforce a weak continuation policy.
Their report does not justify adding generic Monte Carlo search and expecting a
win; it motivates a carefully controlled information-set experiment.

Our implemented alternative is narrower: preserve exact own-hand planning, keep
public evidence, and prove a finishing sequence only when **every** intervening
play is unanswerable under a conservative upper bound on all other hands.
This can miss winning lines, but it does not select a different plan for each
imagined hidden deal. This is our engineering choice, not a method attributed to
AlphaTichu or a proof of superior overall play.

The [behavior-sensitivity study](https://github.com/ainze/tichu/blob/bd044222b89dd1db269e3a19940b7aeb460afafa/docs/notes/2026-09-27-behavior-sensitivity-results/verdict.md)
finds losses from shifting either way away from its existing opponent-pass
behavior; it gives no simple “make them pass” exploit. Its
[retired partner-bomb guard](https://github.com/ainze/tichu/blob/bd044222b89dd1db269e3a19940b7aeb460afafa/docs/notes/2026-09-27-partner-trick-guard-retired.md)
also warns against treating an intuitive teamwork rule as a universal improvement.
We measure our changes against our frozen trained bot, then remove individual
features to test what actually helped.

## What is and is not available for a match

Source audit pinned to commit `bd044222b89dd1db269e3a19940b7aeb460afafa`:

- The repository contains the engine, training code, serving code and a simple
  `RuleAgent`. That easy rule bot is not the trained master.
- No trained `.pt`/`.bin` artifacts were found among tracked files. The GitHub
  releases endpoint returned an empty list at inspection time.
- The [v7 serving configuration](https://github.com/ainze/tichu/blob/bd044222b89dd1db269e3a19940b7aeb460afafa/configs/serve_cotrain_v7_iter15360.yaml)
  points to local model paths. Public source alone therefore does not reproduce
  the served champion.
- The report describes historical serving failures and subsequent repairs.
  Those incidents are not evidence of a current exploitable live-service defect.

The cached Reddit page exposed the announcement, not a complete comment tree.
The technical assessment uses the linked source and report; it does not claim
that all commenters' independent AIs were inspected.

## Milestones toward a defensible win

1. **Pass our local gate.** Improve against the frozen v1 policy on untouched
   rounds and full matches; record uncertainty, failures, seeds and checkpoint
   hashes. Keep the old checkpoint available.
2. **Obtain a reproducible master opponent.** With the author's cooperation,
   use the four compatible model artifacts or a stable evaluation endpoint.
   Pin the model, feature and action versions; fail loudly if inference fails.
   Do not silently fall back to an easier bot.
3. **Verify rules and observations.** Replay shared fixtures for wish obligations,
   Phoenix, interrupt bombs, Dragon allocation, exchange privacy and scoring.
   Confirm that each agent receives only its permitted information.
4. **Run a fixed, paired benchmark.** Predeclare the deal count, primary team
   points-per-round metric, match-win gate, compute limits and confidence method.
   Rotate teams/seats and evaluate unfamiliar partners. Do not tune on final
   test deals or compare win rates from unrelated opponent pools.
5. **Expand learning only where evidence supports it.** Calibrate declarations,
   learn public-history beliefs, then test information-set search against the
   same frozen opponents. Supervised learning from appropriately available
   human games is a promising larger project, not a completed deliverable here.

OnlineTichu remains a later integration project described in the
[online-agent plan](online-agent-plan.md). No account, live match or ranking
attempt was started. Local results establish progress against local opponents;
they cannot yet answer whether we beat AlphaTichu master or strong humans.
