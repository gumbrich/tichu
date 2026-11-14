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

## Evidence standard

Evaluate team points and complete matches, not just first finishes or successful
calls. Use swapped seats and held-out deal seeds. A win over Dave Orr's pinned
search configuration would not establish superiority to AlphaTichu, the Reddit
author's unpublished trained model, or strong human partnerships.
