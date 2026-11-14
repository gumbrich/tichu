# Partnership, declarations and stochastic play

14 November 2026. New branch `codex/partnership-and-bidding`. Frozen v3 is
`experiments/partnership/v3.json`, SHA-256
`b7883435e25b66f84baaf84383465848bcdbb7157e4b0d1b522acd82df73f5dd`.
The opponent remains Dave Orr's pinned `eg:pimc20/hibs` configuration. Previous
experiments are spent evidence; none of their evaluation seeds select this policy.

## Research hypotheses, not rules

- [Aaron Fuegi's strategy guide](https://scv.bu.edu/~aarondf/Games/Tichu/tichu_strategy.html)
  emphasizes balancing weak combinations with ways to regain control, assisting
  a declared partner, and using the Dog as a partnership resource. It also argues
  that beginners undercall. Its reported historical success rates are observational
  and need not transfer to our policy or this opponent.
- [BGA's strategy discussion](https://forum.boardgamearena.com/viewtopic.php?p=245590)
  distinguishes keeping control cards from spending them over a teammate, suggests
  coordinated opponent passes, and discusses waiting to declare until the first
  actual play. These are hypotheses with exceptions, not guaranteed optimal moves.
- [BGG's Greek passing-convention discussion](https://boardgamegeek.com/thread/2184755/greek-partner-passing-convention)
  contains explicit disagreement about concentrating power and passing the Dog
  to a Grand caller. We will compare variants, not assume consensus. No inference
  about a partner's hidden hand is justified unless both agents use the convention.
- [Tichu Tips & Tricks](https://www.spotlightongames.com/analysis/tichu.html)
  discusses delayed calls and conditional pre-exchange declarations. Early calls
  can improve partner support while also informing opponents.
- [This BGA thread](https://forum.boardgamearena.com/viewtopic.php?t=47953)
  discusses changing risk when far behind near match end. Maximizing expected
  round points and maximizing match-winning probability are different objectives.

The official [rules](https://www.riograndegames.com/wp-content/uploads/2013/02/Tichu-Rules.pdf)
remain authoritative. Some strategy pages overstate heuristics or confuse Dragon
gifting with transferring the lead. The Dragon winner keeps the lead. Do not turn
"never overtake partner" into an unconditional rule or treat voluntary passes as
proof that a card is absent. No secret messages or shared private hands enter play.

## Fixed experiment sequence

1. On 64 paired screening deals at 21000000, test Grand thresholds
   2.4/2.8/3.2/3.6/4.2 crossed with Small adjustments 0/−0.4/−0.8/−1.2.
   Keep v3's learned play policy fixed and run v3 on the same deals.
2. Test explicit partnership/exchange/wish alternatives and bounded randomization
   on separate development deals starting 21100000. Randomize only legal choices;
   preserve proven finishes and use independent, reproducible policy randomness.
   A fixed search bot does not automatically become confused by added noise.
3. Freeze up to three finalists for validation: 256 paired external rounds at
   22000000 and 100 paired external full matches at 22100000. Check direct native
   play against v3 on 256 paired rounds at 22200000. Select by external validation
   match win rate among positive native-round candidates. Record every result.
4. Only after selection, freeze code/model for final tests: 1,000 paired external
   rounds at 23000000 and 200 paired external full matches at 24000000. Test native
   play against v3 on 1,000 paired rounds at 25000000 and 150 paired matches at
   25100000. The target is an external full-match win-rate 95% interval entirely
   above 50%, with a positive external round-margin interval and native improvement.

If development/validation fails, keep v3 as default and develop a new family before
using final seeds. Do not repeatedly reuse a final set until a candidate wins.
Track round scoring, call frequency/success, doubles, errors, latency and complete
matches. Training-time exploration and deployment randomness are separate questions.

### Recorded partnership screen (before results)

At 21100000, 96 paired deals per variant, keep v3 bidding and test: unchanged
control; team Dog/power passing; Greek and concentration conventions; parity
assignment alone; delayed Small alone; gentle multi-card Mahjong wishes alone;
team+parity+delay+gentle combined; random exact ties; and temperature 0.03/0.10/0.25
with maximum score loss 0.25 in the normalized blend. Twelve candidates total.
The team policy keeps Dog with the partnership and gives the declared partner its
best power card. This bundle must earn its place empirically. Temperature changes
only ordinary uncertain choices, after forced/proven finish checks. Random draws
are reproducible from the acting seat's observation and a fixed policy seed.
Match-score risk is available for a later match-only test; it is zero here.

### Larger teacher corpus (before collection)

Collect 2,048 additional search self-play rounds at seed 21200000, independent of
all screens and final tests. Fit the existing linear action ranker for 30 epochs,
selecting epoch only by grouped held-out imitation loss. Compare blends 0.25,
0.50 and 0.75 on 128 paired external development deals at 21300000 against v3.
No final seeds or match outcomes enter the supervised training objective. This
is a larger supervised search-distillation experiment, not a claim of RL.

## Strategic interpretation

**Calls are team decisions with individual first-out requirements.** A teammate
finishing first defeats your declaration even if the team wins the round. For a
call considered in isolation, expected bonus is `stake × (2p − 1)`: both Small
and Grand break even at 50% success, not 75% or 80%. That calculation does not
account for changed gifts, opponents' defensive play, card points or match score.
A high observed success rate can reflect missed profitable calls; a higher call
rate can also throw away points. We measure total outcomes under each policy.
Grand uses only the initial eight cards; Small can wait until before the first
card is played. The external simulator does not expose an equivalent pre-exchange
Small decision, so these experiments do not establish the value of early Small.

**Choose a role, but do not blindly obey slogans.** Help a declared partner take
first place, retain ways to feed them the lead, and avoid consuming their control
merely to shed one small card. Without a declaration, the hand with useful groups
and ways to regain the lead usually deserves support. Sometimes taking control
from a partner prevents an opponent finishing or opens a better shape. A voluntary
pass does not prove the player lacks a higher card. Shared passing conventions
only convey information when both partners really follow them; none of our agents
receives private partner cards or secret signals.

**Randomness is not automatically deception.** Tichu combines random deals with
hidden information. Once hands and actions are fixed, rule transitions are
deterministic. Imperfect information can make mixed strategies useful against
exploiting opponents, but this does not prove a particular softmax temperature
helps. The pinned opponent does not adapt a persistent model of our tendencies
across matches. These tests measure the result of move variation, not whether a
bot became confused. Training exploration, varied opponents and deployment
randomness are separate choices. Keep proven finishes deterministic and compare
small bounded temperatures on independent match seeds.

## Bidding-screen result

All 20 combinations completed: 2,560 rounds, plus 128 baseline rounds, with zero
adapter errors or fallback actions. The unchanged v3 thresholds led this small
screen. Its mean was +3.59 points/round against search. Lowering only the Small
threshold by 0.4 changed the paired mean by −3.28 (95% interval −9.33 to +2.77).
Lowering only the Grand threshold from 4.2 to 2.8 changed it by −12.66
(−35.96 to +10.64); Grand successes changed from 1/1 to 10/23. These intervals
do not establish harm, but the screen provides no reason to select more aggressive
thresholds. Retain v3 bidding for the partnership and larger-corpus experiments.
This does not establish that the current thresholds are optimal.

### Resumable collection check

The initial four-worker training collector was interrupted after 220 completed
deals solely to increase collection parallelism to twelve workers. Every completed
deal is retained. The new optional start index regenerates exactly the same deal
from its original seed/index; deal 1 was compared against the original collector
and matched all actions, cards and scores exactly. Missing indices are collected
without changing the predeclared 2,048-deal training set or inspecting outcomes for
selection. `tools.collect_search` checks provenance, completeness and scoring before
writing a sorted compressed corpus.

### Combination and match-risk screens (declared before results)

After the three larger-corpus blends finish the 21300000 screen, choose the
highest mean and compare its unmodified version, parity+delayed Small, and those
two plus the best positive-temperature setting from the completed 21100000 screen.
Omit the temperature combination if no tested temperature has a positive paired
mean gain. Use 128 paired rounds at 21310000 for each. Keep original exchange
planning and wishes: the broad team-passing bundles have not earned selection.
The highest-mean combination then gets a full-match development comparison of
risk weights 0/0.4/0.8, each on 32 paired matches at 21400000. Risk uses only public
match scores and becomes active near the target. These are selection samples,
not the reserved validation or final sets. Up to three finalists from these
screens enter the previously declared validation suite.

The native Mahjong wrapper was corrected before native validation so disabled
extensions preserve even a proof-selected Mahjong play's original wish. External
play uses its separate wish callback, so the ongoing external screen is unchanged.

The scripted development runner includes frozen v3 as the control in the blend
screen. If all larger-corpus blends trail it, v3 supplies the base for subsequent
combinations. Match-risk variants rank by match win rate, breaking ties by final
score margin; the chosen setting still requires independent validation.

Before the 21310000 deals are used, add one fourth combination when the completed
tie-only screen has positive mean gain: parity+delay+random exact ties. It led the
initial randomness screen (+9.32 points/round, interval −12.67 to +31.32), so it
deserves a fresh-deal comparison with positive-temperature sampling. This is a
development hypothesis generated from the earlier screen, not confirmatory evidence.
