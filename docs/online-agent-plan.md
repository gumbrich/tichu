# Later phase: an Online Tichu agent

Status, 11 November 2026: **planning only**. No account has been registered, no
messages sent to the operator, and no online games played by this project.

The site exposes [account registration](https://www.onlinetichu.com/Site/Account/Login)
and a [rating ladder](https://www.onlinetichu.com/Site/Profiles/Top). The public pages
checked did not establish a policy permitting automated ranked players. Resolve
that with the operator before choosing an account/mode for automated competition;
the existence of registration and rankings does not settle it.

## What is ready

- Complete local four-player game rules and a reproducible benchmark suite.
- A fast legal-action generator checked against exhaustive enumeration.
- An observation-only bot interface, explicit decisions and a trained policy.
- Public-history card bounds and guaranteed endgame finishes in the v2 policy.
- Paired-deal evaluation, full matches, and an experiment with one trained player
  supported by an unchanged baseline partner.

The v2 team won 211/300 full matches against the frozen v1 team; the mixed-partner
experiment above belongs to v1 and has not been repeated for v2. These results
establish local improvement. They do not
establish a human rating or predict a place on the site's ladder. The main team
benchmark uses two trained partners. An online agent with an unfamiliar human
partner faces a different coordination problem.

## Integration sequence

1. **Establish the supported mode.** Confirm the site's bot/automation policy and
   available integration mechanism. Use an identified bot account if appropriate.
   Registration and any required account confirmations are a later user action.
2. **Map site rules and events.** Verify dealing/call deadlines, exchange ordering,
   legal combination interpretation, wish enforcement, bomb priority/time windows,
   Dragon gifting, scoring and end-of-match ties against the local engine. Do not
   assume the site's timing conventions equal our explicit bomb-response phases.
3. **Build a read-only observer first.** Convert visible state into `Observation`.
   Keep exact card identifiers, seat orientation and event sequence IDs. Detect
   incomplete or contradictory state and pause decisions rather than guessing.
   Replays should reproduce every public transition before actions are enabled.
4. **Add a narrow action adapter.** Translate `Decision` into one supported site
   action at a time. Confirm the resulting public state, handle rejected/stale
   actions, and make reconnect/retry idempotent. Keep credentials and browser
   control outside the policy. Use only information available to the agent's seat.
5. **Test in an approved private/unranked setting.** Exercise disconnects, latency,
   wish choices, last-pass bombs and final Dragon gifts. Measure illegal-action
   rate (target zero), timeouts, decision latency and scoring disagreements.
6. **Evaluate a ranked pilot only when appropriate.** Use the agreed site mode,
   log policy version and every outcome, and report match results with uncertainty.
   Evaluate mixed/unknown partners; keep opponent adaptation separate from hidden
   card inference. Increase playing volume only after the adapter is reliable.

## Engine improvements before serious ladder ambitions

The current policy already uses conservative bounds from public cards, sent gifts
and compulsory-wish evidence. A future belief model can sample unseen hands within
those bounds, but search must earn its place through a controlled experiment.
The [AlphaTichu comparison](alphatichu-comparison.md) records failed determinized
search approaches and the risk of combining plans that require different hidden
knowledge. Do not let simulation inspect actual opponent hands. Optional passes
are not proof that an opponent lacks a card.

Also add match-score-aware risk, calibrated Grand Tichu decisions, earlier Small
Tichu announcements before exchanges, opponent/partner adaptation, and an immutable
state/replay format. Keep the current trained policy as a fast rollout policy and
explicitly logged latency fallback. Serving failures must be visible; a healthy
connection is not proof that the intended model made a decision. A deep RL
experiment can use this stronger policy and reproducible
arena as its baseline; it should earn promotion through held-out results.

## External benchmark access check on 14 November 2026

The [external benchmark audit](external-benchmark.md) now prioritizes Dave Orr's
recent local Rust search bots. The [local adapter and protocol](local-benchmark.md)
require no account and leave online registration for later. AlphaTichu's live
lobby requires login; a master service address or model export is still needed
for a controlled neural-opponent batch. The ETH online demo omits straight bombs
and out-of-turn bombs, so it is a variant test only. No online matches have been
played. Local external-engine results must not be described as online ladder wins.
