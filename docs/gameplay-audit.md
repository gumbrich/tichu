# Gameplay completion audit

Base: `2eaab0d` on `main`. Work is on `codex/complete-tichu-gameplay`.

## What prevented play

The repository consisted of README.md and a 930-line main.py. It had no tests
or dependency setup. Incomplete syntax (`if(len()`) prevented parsing. Further
failures included Python 2 assumptions about input and division inside range,
undefined straight-play placeholders/variables, and immediate execution on import.

Card, Deck, Player and Round were useful domain concepts, but prompts, legality,
hand removal and point accumulation were interleaved. Combination paths duplicated
large sections and sometimes removed a different number of cards than requested.
Passing and active-player bookkeeping could skip a player when another finished.
The team scores controlling the outer loop were not properly accumulated/reset.

## Implemented behavior

| Area | Completion |
| --- | --- |
| Runtime | Python 3.10+, no third-party dependencies; import-safe entry point |
| Cards | Original suit/rank identifiers, immutable identity, point values |
| Combinations | Singles, pairs, triples, pair sequences, full houses, straights, both bomb types |
| Phoenix | Contextual singles and explicit wildcard interpretations; no bombs/special substitutions |
| Setup | Eight-card Grand decision, remaining six cards, atomic three-way exchange |
| Play order | Mah Jong owner opens; finished seats skipped without excluding others |
| Wishes | Real rank enforcement, persistent wishes, ordinary versus interrupt distinction |
| Dog | Lead transfer, including an out partner; never a trick to bomb |
| Dragon | Gift selection after winning, normal capture after bombing, final-trick gifting |
| Bombs | Ordered interrupt windows after plays/passes, counterbombs, own-trick bombs, final-pass window |
| Declarations | Small and Grand deadlines, individual success/failure, one call per player |
| Round end | Immediate double victory or third finisher; remaining hand/trick transfers |
| Match | Cumulative teams, 1000-point default, ties, independent state for each round |
| Interface | 0–4 humans, legal hints, input validation, hotseat handoff, seeded demos and bots |
| Verification | Unit scenarios, randomized invariants, full matches, scripted terminal game, CI |

The unparseable monolith is replaced by a small package while preserving the
language, terminal entry point, domain concepts, names and card numbering.
The old internal methods and indexed combination arrays were not a working API
and are not compatibility promises. Player/team seat IDs are now consistently
zero-based internally and one-based only in terminal prompts. Git history retains
the original implementation; there is no second competing legacy rule path.

## Deliberate decisions

- Explicit bomb windows model the publisher's priority sequence without timing
  races. A window is different from an ordinary turn, even for the next seat.
- The final third-player finish closes immediately; there is no post-finish bomb
  window. A necessary Dragon decision still happens before scoring.
- A double victory ends immediately and replaces card scoring with 200–0;
  declarations are still scored separately.
- No-wish Mah Jong is allowed. A new wish in a Mah Jong straight applies to
  subsequent play; the same play does not immediately satisfy its own new wish.
- A same-suit straight is always a bomb. Four equal cards plus Phoenix is not a
  full house. Phoenix cannot stand for Mah Jong, Dog or Dragon.
- Only four-player Nanking is supported. Online concurrency, durable saves,
  graphical UI and strong AI remain future work.

Validation performed locally: rule suite and integration tests; default-terminal
smoke test covering Grand decision, rejected duplicate exchange, valid exchange,
move hints and clean quit; full seeded bot match. CI configuration is supplied
but a remote GitHub Actions result is not claimed until the branch is pushed/run.
