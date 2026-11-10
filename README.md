# Tichu

A playable four-player Tichu terminal game, continued from Johannes Knoerzer's
January 2021 Python prototype. Standard-library Python **3.10 or newer** is the
only requirement; no NumPy, package installation, or external service is needed.

## Run

From this repository directory:

```sh
python3 main.py                         # You (Alice) and three simple bots
python3 main.py --humans 4              # Four humans sharing a terminal
python3 main.py --humans 2 --seed 42     # Two human seats, two bots, repeatable deal
python3 main.py --demo --seed 7          # Automated match, round summaries only
python3 main.py --demo --target 100      # Short demonstration match
python3 -m unittest discover -v         # Rules, terminal and whole-game tests
```

Seats 1→2→3→4 proceed to the right. Alice and Charlie are partners; Bob and Eve
are partners. Human-controlled seats are the first `--humans` seats (0–4).
The default match target is 1000. Equal scores at/above the target continue into
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
They also run 40 seeded randomized rounds with 56-card conservation and score
invariants after every action, reproducible bot matches, and a scripted
four-human game. GitHub Actions runs the suite on Python 3.10 and 3.13.

- `main.py`: import-safe terminal entry point; retains Card/Deck/Player/Round imports.
- `tichu/cards.py`: immutable cards; original suit/rank conventions; shuffled deck.
- `tichu/combinations.py`: pure classification, comparison and exhaustive legal plays.
- `tichu/game.py`: Player, Round and Match; validation, phases, tricks and scores.
- `tichu/cli.py`: terminal prompts and deterministic baseline bots.
- [Gameplay audit](docs/gameplay-audit.md): original gaps and replacement decisions.
- [Engine design](docs/engine-design.md): next-phase interfaces and milestones.

Bots use their own available plays and public table information, never opponent
card identities. They are deliberately weak: they use a simple shedding policy,
do not call Tichu, and do not search or model teammates. The generator enumerates
hand subsets and caches classifications; it favors correctness over search speed.
The mutable Round object is trusted in-process state, not a network security API.

Rules reference: [Fata Morgana's official English rules and FAQ](https://fatamorgana.ch/fatamorgana/tichu/english-rules).
The implementation is for four-player Nanking Tichu only. The source page's
points list accidentally omits the minus sign on Phoenix; its Phoenix section
and stated 100-point deck total establish the intended **−25** value.
