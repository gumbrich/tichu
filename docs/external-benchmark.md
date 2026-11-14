# External engine benchmark access and protocol

**14 November 2026.** The immediate target is now Dave Orr's local Rust engine,
which requires no account. Its adapter, pinned opponent and fixed evaluation
protocol are described in [the local benchmark](local-benchmark.md). AlphaTichu
remains a later neural-opponent target: its live lobby redirects to login and the
public repository lacks the master model. No online matches have been played.

## Available targets

| Target | Verified access | Benchmark suitability |
| --- | --- | --- |
| [Dave Orr Tichu-ai](https://github.com/dave-orr/Tichu-ai) | Pinned October 2026 Rust source; local search bots and arena run without an account. No explicit license found. | Current local target; unmodified external referee, legal-list checks and independent score audit. |
| [AlphaTichu](https://tichu.inzelabs.com/) | Live game page, login and signup load. The match lobby requires authentication. | Later neural target, subject to verifying master selection, private bot matches and model identity after login. |
| [ETH Tichu AI demo](https://tichu-ai.netlify.app/) | Setup UI loads with human/AI seat selectors. It explicitly says straight bombs and out-of-order bombs are not implemented. Actual backend gameplay was not tested. | Secondary variant benchmark only; cannot silently present it as full-rule Tichu. |
| [OnlineTichu](https://www.onlinetichu.com/) | Login/registration page loads. The linked Policy page is a privacy policy. | Later field testing; a fixed-version AI opponent or public bot API was not established from these pages. |

The ETH demo also describes multiple humans joining the same website by choosing
different seats. Its session isolation needs checking before using it for a batch.
The OnlineTichu privacy page does not settle automated-play support. Account access,
a suitable bot/private-table mode and a stable opponent are separate requirements.

## AlphaTichu access details

The [source repository](https://github.com/ainze/tichu) is still at
`bd044222b89dd1db269e3a19940b7aeb460afafa`. Its tracked tree contains no
`.pt`, `.bin`, `.onnx` or `.safetensors` model artifacts, and the
[releases endpoint](https://api.github.com/repos/ainze/tichu/releases) returned an
empty list on this check. Its easy rule agent is not a substitute for master.

The [inference contract](https://github.com/ainze/tichu/blob/bd044222b89dd1db269e3a19940b7aeb460afafa/documentation/INFERENCE_API.md)
documents `POST /act` for play/exchange/wish/Dragon decisions, `POST /call` for
Small/Grand Tichu, and health/metrics endpoints. It describes a service at a
placeholder host, not a publicly accessible master inference address. Website
login does not establish access to this separate inference service.

`/act` can report `fallback_used: true`, meaning a random legal fallback replaced
the model. The documented `/call` error behavior can return a declined call.
A benchmark must record inference failures and confirm that all intended networks
are active. A healthy website/database or an agent roster is insufficient proof
that master is making every decision.

The API document includes older feature-version notes. The current codec and
export must be checked directly before implementing the adapter, especially for
public history. Sending an older state shape with empty history could weaken the
opponent while appearing operational.

## Later AlphaTichu access

If pursuing the live AlphaTichu target, create an account at
[AlphaTichu signup](https://tichu.inzelabs.com/signup), then sign in. Passwords
and email verification should stay in the site's own flow, not this chat.
After login, inspect the available difficulty, private-table and seat controls.
A small private pilot can establish integration feasibility; it cannot establish
relative strength.

For a controlled batch, the best option is an agreed master inference endpoint
with a model identifier, or compatible exported model files for local execution.
No message requesting access has been sent to the author.

## Proposed later AlphaTichu benchmark

1. **Freeze the participants.** Use our deterministic v2 checkpoint, SHA-256
   `f791544998479c02946dcd9e4b1b5df89d6fa78d72d09b5338a14fec2ffe277e`, with
   inference behavior from `b29d2e1`. Pin the external model and its feature/action
   versions. Record any version change and stop pooling across it.
2. **Verify rules before measuring strength.** Exercise exchange privacy, both
   calls, Phoenix interpretations, compulsory wishes, bomb timing, final-pass
   interrupts, Dragon gifting, double victories and round/match scoring. Our
   engine offers bomb windows after passes; AlphaTichu's public API instructions
   say to poll after plays, not passes. Agree on and test one authoritative rule
   protocol instead of silently mixing the two conventions.
3. **Run a 20-round compatibility pilot.** Validate every translated action,
   public-state update, score and disconnect path. Give each bot only its own
   cards and legitimate public information. Reject silent fallback substitutions;
   report failed games rather than selectively deleting unfavorable outcomes.
4. **Team benchmark.** Prefer two copies of ours against two copies of theirs.
   Play 1,000 fixed deals twice with team assignments exchanged: 2,000 rounds.
   Reserve fresh seeds 12000000–12000999 if our arena owns the deals. Use mean
   team score difference as the primary measure and paired uncertainty estimates.
5. **Full matches.** Use 200 fresh match seeds, each with team assignments swapped:
   400 matches to 1,000 points. Reserve seeds 13000000–13000199 if our arena owns
   dealing. Report wins, score margins and 95% intervals clustered by match-seed
   pair. Do not tune or stop early based on the running win rate.
6. **Mixed-partner benchmark.** Separately test one of ours with a fixed external
   partner against two external bots, rotating our seat. This is closer to the
   later single-agent online setting and must not be conflated with team results.

If the website cannot replay seeds, record an explicitly **unpaired live test**
with a fixed sample size, fixed difficulty, seat rotations, match logs and the
observed model/version information. Such a test can be informative, but it lacks
paired-deal control. Browser-only access is also much slower than a local model
or direct inference service for thousands of decisions.

Record the actual partner/opponent identities, call rates, double victories,
latency, timeouts, rejected actions and inference fallbacks alongside score.
Keep every raw outcome. A handful of live games is a smoke test, not a solid
benchmark or evidence of human ladder strength.
