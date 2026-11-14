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
