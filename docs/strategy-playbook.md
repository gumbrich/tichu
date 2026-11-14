# Tichu strategy: what we can currently justify

14 November 2026. This is the short playbook; the [experiment record](partnership-improvement.md)
contains settings, confidence intervals, raw-game locations and unsuccessful tests.
Screening results are provisional, not established improvements.

## Announcing Small and Grand

- Judge control and weak combinations together. A pile of high cards can still
  leave several awkward groups without a way to regain the lead.
- Grand uses the first eight cards. Small remains available until you play your
  first card; passing does not use that opportunity. Delaying can reveal useful
  information, while an early call can guide partner support and alert opponents.
- A call needs **the caller** to finish first. A partner's first place does not
  make your call successful. Supporting an announced partner normally takes
  priority over making your own competing call.
- The isolated expected bonus is `stake × (2p − 1)`: the break-even success rate
  is 50% for both calls. Changes to passing, opponent defense and match-winning
  chances mean that this calculation alone is not a bidding policy.
- Our 20-setting screen did not select more aggressive thresholds. Success rates
  from human databases or another bot cannot simply be copied to our bot.

See [the official rules](https://www.riograndegames.com/wp-content/uploads/2013/02/Tichu-Rules.pdf)
and [Aaron Fuegi's strategy discussion](https://scv.bu.edu/~aarondf/Games/Tichu/tichu_strategy.html).

## Playing as a partnership

- Help the likely finisher keep or regain control. Passing over a partner's good
  trick can preserve your own control cards. Sometimes overtaking prevents an
  opponent finishing or opens a better combination type; “never overtake” is too rigid.
- Treat the Dog as a way to transfer the lead. Its value depends on which partner
  needs that lead and on the combinations sacrificed to keep or pass it.
- Agree on passing conventions before relying on their information. Coordinating
  low opponent gifts can reduce duplicate ranks reaching the same opponent. Power
  concentration and Greek-style conventions make different assumptions.
- An ordinary voluntary pass is not proof that a higher card is absent. A partner
  may be preserving a combination or deliberately letting you keep the trick.
- Watch an opposing caller's remaining cards: changing combination type can deny
  an immediate finish. Include possible bombs when judging whether a lead is safe.
- First place alone is not the scoring objective. Bank valuable tricks and aim
  for the partnership's double victory. Winning with the Dragon keeps the lead
  but gives its trick away, so card points and initiative have different values.

The [BGA discussion](https://forum.boardgamearena.com/viewtopic.php?p=245590) and
[BGG convention debate](https://boardgamegeek.com/thread/2184755/greek-partner-passing-convention)
contain useful ideas and real disagreements. Our blanket Dog/power-passing bundles
did not lead the screen; the results favor testing flexible policies over slogans.

## Randomness

Keep proven finishes deterministic. Exact-tie variation and a small, bounded
temperature are worth testing; broader noise had worse means in our first screen.
None of those initial intervals established a benefit. The pinned search opponent
does not learn our tendencies across matches, so these games do not demonstrate
that we “confused” it. Random deals, hidden information, training exploration and
deployment randomness are different issues.
Equal bot scores also do not prove equal strategic value: the current evaluator
cannot represent every distinction. Tie variation may avoid a bad fixed ordering;
that would be different evidence from successfully exploiting an adaptive opponent.
For example, with `22 44 888`, playing `22 888` leaves fours while `44 888` leaves
twos. A constructed position gives these actions identical feature vectors, and
the fixed ordering keeps the twos. This is a concrete representation gap, not a
proof that random play or either action is optimal in every partnership situation.

The later isolated test on the stronger learned model found a tie-randomization
effect of **−7.81 points/round**, with a paired 95% interval of **−19.22 to +3.59**
over 256 paired deals. It did not establish a benefit or conclusive harm. The
selected finalist is deterministic; the diagnostic did not select that finalist.

## Evidence standard

Evaluate team points and complete matches, not just first finishes or successful
calls. Use swapped seats and held-out deal seeds. A win over Dave Orr's pinned
search configuration would not establish superiority to AlphaTichu, the Reddit
author's unpublished trained model, or strong human partnerships.
