# Next phase: a search-ready Tichu engine

Status: design proposal, following verified gameplay completion. The current
rules are the reference implementation; this document does not claim a search
engine or a hidden-information agent has already been built.

## Existing foundation

`Card` and `Combination` are immutable values. `classify()` returns all legal
interpretations of a selected set of cards. `legal_plays(hand, top)` handles
comparison and the Phoenix's contextual single value. `Round.available_plays()`
adds phase, actor and wish constraints. Round commands validate legality before
changing cards, resolve tricks, and score rounds. Match owns the target and totals.
There is no terminal I/O in these rules modules.

Keep these rules and regression tests as the correctness oracle during the engine
work. Avoid a separate bot-specific implementation of wishes, tricks or scoring.

## State representation

Introduce a frozen, versioned `GameState`, separate from frontend/session state:

| Component | Proposed contents |
| --- | --- |
| Cards | Stable IDs 0–55; four 13-bit suit masks plus four special bits |
| Deal | Explicit shuffled order/deck cursor, dealer/round number, Grand pending seats |
| Hands | Four 56-bit masks; no inferred ownership |
| Exchange | Private committed gifts per sender, commitment bitmask; reveal barrier |
| Turn | Phase enum, ordinary actor, bomb response queue/cursor |
| Trick | Ordered plays/card mask, last combination, last player, passed-seat mask |
| Special obligations | Wish rank, Dragon choice owner, post-collection continuation |
| Finish | Finish order, remaining/last player, round terminal reason |
| Scores | Captured card masks, declaration enum per seat, has-played mask, team totals |
| Match | Target, completed-round results, terminal winner/tie status |

The Phoenix single's strength can be represented as twice-rank integers, avoiding
floating-point keys. Its wildcard rank is part of the action, never inferred by a
search routine. An immutable state must fully determine the next transition;
there must be no hidden random generator or global rule state in `step`.

Separate `GameState` (authoritative information) from `Observation` (one seat's
knowledge). An observation includes that seat's hand, private sent/received gifts
when legitimately known, public counts/calls/plays/finish order/scores, current
wish, actor and phase. It must exclude other hands, unrevealed gifts, remaining
deck identities and RNG state. Bots receive observations, never the full state.
The current CLI bot only reads its own hand/legal plays and public facts, but
passing it Round is not a sufficient boundary for untrusted or learned agents.

## Actions and transition interface

Proposed interface (not yet implemented):

```python
initial_state(deck_order, names, target=1000) -> GameState
legal_actions(state, actor) -> tuple[Action, ...]
step(state, action) -> Transition  # next immutable state + public/private events
observe(state, seat) -> Observation
is_terminal(state) -> bool
utility(state, team) -> float
serialize(state) -> bytes
deserialize(data) -> GameState
```

Use tagged actions: `DecideGrand`, `CallTichu`, `CommitExchange`, `Play`,
`Pass`, `Bomb`, `DeclineBomb`, `GiveDragon`, and `AdvanceRound` (explicit chance
input/deck). `Play` contains selected card IDs, Phoenix interpretation and optional
wish. `Bomb` uses the response-window actor and deliberately does not inherit
ordinary-turn wish restrictions. Invalid actions return a structured rule error
and cannot partially mutate state.

Keep both declarations and exchange commitments as explicit decisions, not just
card-play actions. Calls can arrive before the caller's first play outside their
ordinary turn; a session coordinator must order these events before a card play
is committed. Give that ordering a defined contract for network clients and AI
rollouts. Simultaneous exchanges are a commit/reveal phase, not four visible
hand changes. Do not generate actions using hidden information from another seat.

## Legal-move generation

The existing exhaustive subset generator is a slow, clear reference. Replace the
production path with rank counts and suit masks:

1. Generate singles, same-rank subsets, triples and distinct-rank full houses.
2. Enumerate consecutive rank intervals for pair runs and straights; expand suit
   choices only when their identities affect the hand left behind.
3. Enumerate a separate Phoenix substitution path with explicit interpretations.
4. Generate four-of-kind and same-suit runs as bombs; preserve bomb type/length.
5. Filter against the table, then apply ordinary-turn wishes or bomb-window policy.

Do not coalesce actions merely because their rank/strength matches: spending a
different suit can preserve or destroy a later straight-flush bomb. Preserve all
Phoenix alternatives and different wish choices. Exchange action counts are also
large; lazy iteration or policy priors may help without silently deleting choices.

Acceptance: the optimized and reference generators produce identical action sets
on the targeted edge cases and thousands of seeded hands/table states. Benchmark
cold/warm generation and complete rollouts separately before choosing a cache.

## Trick resolution and scoring

Retain the current phase sequence as a single authoritative reducer:

```text
Grand decisions -> exchange commitments -> ordinary lead
ordinary play/pass -> ordered bomb window -> ordinary response or collection
bomb -> new ordered bomb window
Dog -> partner/next-active lead
Dragon collection -> opponent choice -> winner/next-active lead
second teammate out -> immediate double victory
third player out -> immediate collection (Dragon choice if needed) -> scoring
```

Score from card ownership plus declarations, once per round. Ordinary rounds
conserve 100 card points before call adjustments. Double victories yield 200–0
before calls. Remaining tricks move to the first finisher; the remaining hand
moves to opponents. Preserve the distinction when the last player receives the
final Dragon trick and subsequently transfers it. Tied target scores continue.

## Search and AI

First expose an agent protocol `choose_action(observation, legal_actions, budget)`
and an evaluation harness with deterministic seeds. Keep a legal random policy
and the current simple bot as reproducible baselines. Measure win rate, score
difference, illegal-action count, actions/second and latency, using paired deals
and seat/team rotations. Report sample size and uncertainty.

Tichu has hidden cards and teammates. Perfect-information minimax on actual
opponent hands would be a cheating benchmark, not a deployable agent. Start with
sampled hidden hands consistent with public history, exchanges and observations;
then compare determinization rollouts with information-set search. Belief models
must consider wish/pass constraints without assuming an optional pass proves
that a card is absent. Team rewards and individual Tichu commitments coexist.

## Milestones and acceptance gates

1. **Immutable state, actions and replay.** Port one phase at a time behind the
   existing tests. Add serialization/versioning, clone/hash equality, deterministic
   replay, invalid-action immutability and observation non-leakage tests. Replaying
   a complete match must produce identical hands, events and final scores.
2. **Fast move generation.** Differential tests against the current generator;
   preserve exact suit selections and Phoenix/wish alternatives. Publish a fixed
   benchmark corpus, latency percentiles and rollout throughput before/after.
3. **Agent boundary and baseline tournament.** Observation-only policy interface,
   action/time budgets, randomized/heuristic agents, paired seeded evaluation,
   zero invalid actions and reproducible results.
4. **Hidden-information search.** Belief-consistent sampling, then a bounded
   rollout/information-set search agent. Demonstrate a measured improvement over
   baselines under the same time budget without privileged information.
5. **Client adapters.** A GUI or multiplayer server uses the same action reducer.
   Add authoritative sequencing, per-seat event redaction, reconnection/replay and
   bomb-window deadlines as session concerns, not separate game rules.

Start with milestone 1. Optimize only after the immutable API and replay contract
are stable; keep the playable CLI throughout the transition.
