# Tichu

A playable four-player Tichu terminal game, continued from Johannes Knoerzer's
January 2021 Python prototype. Standard-library Python **3.10 or newer** is the
only requirement; no NumPy, package installation, or external service is needed.

## Run

From this repository directory:

```sh
python3 main.py                         # You (Alice) and three self-play-trained bots
python3 main.py --humans 4              # Four humans sharing a terminal
python3 main.py --humans 2 --seed 42     # Two human seats, two bots, repeatable deal
python3 main.py --demo --seed 7          # Automated match, round summaries only
python3 main.py --bot baseline           # Original weak bot, for comparison
python3 main.py --bot strategic          # Untuned hand-planning bot
python3 main.py --bot trained            # Frozen first self-play checkpoint (v1)
python3 main.py --bot competitive        # Public-history tactics and finish proofs (v2)
python3 main.py --random-ties --bot-seed 42 # Optional randomization of equal-score choices
python3 main.py --demo --target 100      # Short demonstration match
python3 -m unittest discover -v         # Rules, terminal and whole-game tests
```

Seats 1→2→3→4 proceed to the right. Alice and Charlie are partners; Bob and Eve
are partners. Human-controlled seats are the first `--humans` seats (0–4).
The default bot is `competitive` (v2); `trained` preserves the earlier v1 policy.
Its weights were selected by a reproducible self-play tournament, using separate
training, validation and test deals. The default match
target is 1000. Equal scores at/above the target continue into
another round. `--seed` makes the deals reproducible for the same actions.

## Playing

1. View your first eight cards and decide whether to call **Grand Tichu**.
   Answer `yes` or `no` to take the final six cards. Other calls are public.
2. Enter three **different card numbers**, in the recipient order shown, to
   exchange one card with each other seat. Input order matters here. Selections
   are committed without revealing received cards until all four players commit.
3. The holder of Mah Jong starts; they need not play Mah Jong first.
4. On your ordinary turn, enter the card numbers to play, separated by spaces
   (for example `2 5 7`), or `pass`. `moves` lists currently legal selections.
   Card numbers refer to the currently displayed hand and change as it changes.
   Ambiguous Phoenix combinations prompt you to choose their interpretation.
5. Playing Mah Jong prompts for a wish: 2–14, or 0 for none. J=11, Q=12, K=13,
   A=14. Play a real card of the wished rank whenever a legal ordinary play can
   include it; the game enforces this, including necessary Phoenix combinations
   and bombs. A wish survives until fulfilled.
6. A **bomb response** prompt allows an interrupt, even outside your ordinary
   turn. Enter the bomb's card numbers, `moves`, or press Enter to decline.
   Response opportunities follow seat order after each play/pass. There is also
   a response window after the final pass, before collection. Impossible bomb
   responses are declined automatically. Counterbombs open a new window.
7. The Dragon's winner chooses an opposing seat to receive the trick; its winner
   retains the lead (or the next active seat leads if the winner is out).
8. Round scoring, unfinished-hand transfers, double victories, declaration
   bonuses/penalties, new rounds and match victory are automatic.

At decision prompts, `tichu` calls Small Tichu for the current human, and
`tichu 3` calls it for human seat 3. This also allows a human to announce while
another human has the prompt. Calls are accepted before that player's first
play, including before the exchange. A player can make only one declaration;
a Grand Tichu caller cannot add Small Tichu. `q` quits; EOF/Ctrl-C exit cleanly.
There is no save/resume yet.

The Dog can only lead and immediately passes the lead to the partner (or next
active seat beyond an out partner). It cannot be bombed. Bombs cannot seize an
empty table's lead, although the rightful leader can lead a bomb. During an
interrupt window, the wish does not restrict the bomb; an ordinary-turn bomb
must satisfy a playable wish. These distinct opportunities are intentional.

For shared-terminal play, handoff prompts and screen clearing help avoid casual
peeking. This is trusted local play: terminal scrollback is not a privacy
boundary. There is no online multiplayer or graphical interface.

## Verification and structure

The tests cover all combination families, contextual Phoenix singles, wildcard
ambiguity, wishes, bomb priority and final-pass interrupts, Dragon gifting, Dog
leads, players going out, calls, exchanges, score transfers and match rollover.
They also compare the faster move generator against exhaustive enumeration, test
private-information isolation and policy checkpoints, and run 40 seeded randomized
rounds with 56-card conservation and score
invariants after every action, reproducible bot matches, and a scripted
four-human game. GitHub Actions runs the suite on Python 3.10 and 3.13.

- `main.py`: import-safe terminal entry point; retains Card/Deck/Player/Round imports.
- `tichu/cards.py`: immutable cards; original suit/rank conventions; shuffled deck.
- `tichu/combinations.py`: pure classification, fast complete legal plays, and an exhaustive test oracle.
- `tichu/game.py`: Player, Round and Match; validation, phases, tricks and scores.
- `tichu/cli.py`: terminal prompts and bot selection.
- `tichu/agents.py`: immutable player observations, decisions, hand planning and policies.
- `tichu/selfplay.py`: paired tournaments, self-play optimization and held-out benchmarks.
- `tichu/trained_weights.json`: frozen v1 checkpoint, retained for comparisons.
- `tichu/tactics.py`: conservative counterplay bounds and proven finishing sequences.
- `tichu/competitive.py`: tactical policy training, evaluation and promotion gate.
- `tichu/competitive_weights.json`: the selected, human-readable v2 checkpoint.
- [Gameplay audit](docs/gameplay-audit.md): original gaps and replacement decisions.
- [Engine design](docs/engine-design.md): next-phase interfaces and milestones.

## Stronger bots and self-play

The policies combine exact hand partitioning with partnership support,
control-card preservation, bomb timing, structured exchanges and Small Tichu calls.
Only a player's own cards and public information cross the agent boundary. Agents
never receive the authoritative Round object or opponents' private hands.
The competitive policy also tracks public play history, tests possible enemy
finishes, and finds uninterrupted finishing sequences that work against every
hand consistent with its conservative card bounds. Ordinary passes do not prove
card absence. Bombs, Phoenix and wish obligations remain part of these checks.
Two competitive bots won **211 of 300 full matches (70.3%)** against two frozen
v1 bots, with an approximate paired 95% interval of **66.2–74.5%**. On 2,000
separate test rounds the score advantage was **+15.5 points per round**
(11.2–19.8). Both results passed the predeclared promotion gate. This is a local
benchmark; a match against AlphaTichu master has not been possible without its
trained artifacts or an evaluation endpoint.

The training method is **evolutionary policy search**, using completed self-play
rounds and final team score as feedback. It tunes interpretable weights rather
than training a neural network. It requires no GPU or third-party libraries.
Training, validation and held-out test deals are separate; each evaluation deal
is played with team assignments swapped. The original bot and the v1 trained
checkpoint are frozen as comparison opponents.

```sh
# Reproduce v1 training:
python3 -m tichu.selfplay train --output experiments/retrain \
  --generations 6 --population 12 --deals 36 --workers 2 --seed 1729

# Play with a newly trained checkpoint:
python3 main.py --bot trained --weights experiments/retrain/weights.json

# A smaller benchmark on fresh deals (200 rounds = 100 paired deals):
python3 -m tichu.selfplay evaluate --candidate trained --opponent baseline \
  --pairs 100 --seed-start 3000000 --workers 2 --output experiments/evaluation.json

# Reproduce the full frozen-policy evaluation and ablations:
python3 -m tichu.selfplay suite --pairs 200 --matches 60 --workers 2 \
  --output experiments/rebenchmark

# Reproduce v2 training and its final benchmark (a longer CPU run):
python3 -m tichu.competitive train --output experiments/retrain-v2 \
  --generations 5 --population 10 --deals 64 --workers 4 --seed 819
python3 -m tichu.competitive suite --model experiments/retrain-v2/weights.json \
  --pairs 1000 --matches 150 --workers 4 --output experiments/rebenchmark-v2
python3 main.py --bot competitive --weights experiments/retrain-v2/weights.json

# Quick comparison of the shipped v2 and frozen v1 on new deals:
python3 -m tichu.selfplay evaluate --candidate competitive --opponent trained \
  --pairs 100 --seed-start 8000000 --workers 2 --output experiments/v2-check.json
```

See [Strategic findings](docs/strategic-findings.md) for measured strength,
feature-removal experiments, practical tactics and limits, and
[the experiment record](experiments/selfplay/README.md) for seeds and raw evidence.
The [competitive experiment record](experiments/competitive/README.md) covers v2.
The [local external benchmark](docs/local-benchmark.md) connects this frozen bot
to Dave Orr's October 2026 Rust search engine without an account. It uses paired
deals, an independently checked legal-action boundary and a separate score audit.
Build its optional Rust adapter with
`cargo build --release --locked --manifest-path tools/dave_bridge/Cargo.toml`.
Our terminal game and normal tests still require only Python.
The [AlphaTichu comparison](docs/alphatichu-comparison.md) explains the other
project's approach, its available artifacts and the requirements for a fair match.
The [randomization experiment](docs/randomization-findings.md) tests an LLM-like
temperature control. Sampling is opt-in: `--temperature 0.5`, `--random-ties`,
and `--max-score-gap 1` control the move distribution; `--bot-seed` controls
sampling separately from the deal seed. Temperature zero is the default, and
guaranteed finishes remain protected even at high temperatures.
The policy does not yet perform hidden-hand game-tree search, infer opponents'
strategies, call Grand Tichu, or adapt to the overall match score. Improvement over
our baseline is not proof of human ladder strength. Online integration remains
[a later phase](docs/online-agent-plan.md).

The mutable Round object remains trusted in-process state. The observation/action
boundary is suitable for local agent experiments; it is not yet an authenticated
network protocol or a full immutable replay engine.

Rules reference: [Fata Morgana's official English rules and FAQ](https://fatamorgana.ch/fatamorgana/tichu/english-rules).
The implementation is for four-player Nanking Tichu only. The source page's
points list accidentally omits the minus sign on Phoenix; its Phoenix section
and stated 100-point deck total establish the intended **−25** value.
