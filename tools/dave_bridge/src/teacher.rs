//! Replay training logs and export only the acting teacher's public view.
use std::io::{BufRead, Write};
use serde_json::{json, Value};
use tichu_engine::{engine::{Action, GameState}, types::*};

pub fn export() {
    let input = std::io::stdin();
    let mut output = std::io::BufWriter::new(std::io::stdout());
    for line in input.lock().lines() {
        let record: Value = serde_json::from_str(&line.expect("training input")).expect("pair JSON");
        assert!(record.get("error").is_none());
        for game in record["games"].as_array().expect("games") {
            let our_team = game["our_team"].as_u64().unwrap() as usize;
            for round in game["rounds"].as_array().expect("rounds") {
                let deck: Vec<Card> = serde_json::from_value(round["deck"].clone()).expect("deck");
                let actions: Vec<Action> = serde_json::from_value(round["actions"].clone()).expect("actions");
                let mut state = GameState::new(Settings::default());
                state.start_round(deck);
                for action in actions {
                    let seat = match &action {
                        Action::Play { seat, .. } | Action::PassTurn { seat } => Some(*seat),
                        _ => None,
                    };
                    if let Some(seat) = seat.filter(|s| record["teacher_all"] == true || s % 2 != our_team) {
                        let plays = state.legal_plays(seat);
                        let label = match &action {
                            Action::Play { cards, phoenix_as, .. } => Some(plays.iter().position(|p|
                                p.card_set() == CardSet::from_cards(cards) && p.phoenix_as == *phoenix_as
                            ).expect("teacher play missing from legal set")),
                            _ => None,
                        };
                        let request = json!({"id": 0, "kind": "play", "view": state.view(seat),
                            "plays": plays, "can_pass": state.can_pass(seat)});
                        writeln!(output, "{}", json!({"pair": record["pair"], "seed": record["seed"],
                            "swapped": game["swapped"], "request": request, "label": label})).unwrap();
                    }
                    state.apply(&action).expect("training replay rejected action");
                }
                assert_eq!(serde_json::to_value(state.last_result().unwrap()).unwrap(), round["result"],
                           "training replay score mismatch");
            }
        }
    }
    output.flush().unwrap();
}

pub fn collect(count: usize, seed: u64, workers: usize, start: usize) {
    use rand::{SeedableRng, rngs::StdRng};
    use std::sync::{Mutex, atomic::{AtomicUsize, Ordering}};
    use tichu_engine::{arena::mix, bot::Bot, bots, sim::play_round};
    let next = AtomicUsize::new(0);
    let output = Mutex::new(std::io::stdout());
    assert!(count > 0 && workers > 0);
    std::thread::scope(|scope| {
        for _ in 0..workers.min(count) {
            scope.spawn(|| loop {
                let index = next.fetch_add(1, Ordering::Relaxed);
                if index >= count { break; }
                let i = start.checked_add(index).expect("teacher index overflow");
                let mut players: [Box<dyn Bot>; 4] = [0,1,2,3].map(|s|
                    bots::by_name("eg:pimc20/hibs", mix(seed, i as u64, s+1)).unwrap());
                assert!(players.iter().all(|p| !p.cheats()));
                let mut state = GameState::new(Settings::default());
                let result = play_round(&mut state, &mut players,
                    &mut StdRng::seed_from_u64(mix(seed, i as u64, 0)), None).expect("teacher self-play");
                let record = json!({"pair": i, "seed": seed, "teacher_all": true,
                    "external_revision": super::REV, "opponent": "eg:pimc20/hibs",
                    "games": [{"our_team": 0, "swapped": false, "rounds": [{
                        "deck": state.deck, "actions": state.log, "result": result,
                        "scores": state.scores, "final_players": state.players}]}]});
                let mut out = output.lock().unwrap();
                writeln!(out, "{record}").unwrap(); out.flush().unwrap();
            });
        }
    });
}
