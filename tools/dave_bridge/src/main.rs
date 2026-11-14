//! Our subprocess adapter and benchmark harness; the dependency remains unmodified.
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex, atomic::{AtomicBool, AtomicUsize, Ordering}};
use std::time::{Duration, Instant};
use rand::{SeedableRng, rngs::StdRng};
use serde_json::{json, Value};
use tichu_engine::{arena::mix, bot::Bot, bots, engine::GameState,
    sim::play_round, types::*, view::PlayerView};

const REV: &str = "ede1c2948eff1bcbc27bafd8c8af385253475b59";

#[derive(Default)]
struct Metrics { requests: usize, max_ms: f64 }

struct PythonBot {
    child: Child,
    input: ChildStdin,
    output: mpsc::Receiver<String>,
    sequence: usize,
    metrics: Arc<Mutex<Metrics>>,
}

impl PythonBot {
    fn new(python: &str, root: &str, metrics: Arc<Mutex<Metrics>>, policy: &str, model: &str) -> Self {
        let mut command = Command::new(python);
        command.args(["-m", "tichu.external", "serve", "--candidate", policy]);
        if !model.is_empty() { command.args(["--model", model]); }
        let mut child = command
            .current_dir(root).stdin(Stdio::piped()).stdout(Stdio::piped())
            .stderr(Stdio::inherit()).spawn().expect("start Python bot");
        let input = child.stdin.take().unwrap();
        let stdout = child.stdout.take().unwrap();
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines() {
                match line {
                    Ok(line) => { if tx.send(line).is_err() { break; } },
                    Err(_) => break,
                }
            }
        });
        Self { child, input, output: rx, sequence: 0, metrics }
    }

    fn ask(&mut self, kind: &str, view: &PlayerView, plays: &[Combo], can_pass: bool) -> Value {
        self.sequence += 1;
        let request = json!({"id": self.sequence, "kind": kind, "view": view,
                             "plays": plays, "can_pass": can_pass});
        let start = Instant::now();
        writeln!(self.input, "{request}").expect("write Python request");
        self.input.flush().expect("flush Python request");
        let line = self.output.recv_timeout(Duration::from_secs(30))
            .expect("Python bot died or exceeded 30 seconds; no fallback");
        let reply: Value = serde_json::from_str(&line).expect("parse Python response");
        assert_eq!(reply["id"].as_u64(), Some(self.sequence as u64), "response sequence");
        assert!(reply.get("error").is_none(), "Python decision failed: {reply}; request={request}");
        assert!(reply.get("value").is_some(), "missing response value");
        let mut metrics = self.metrics.lock().unwrap();
        metrics.requests += 1;
        metrics.max_ms = metrics.max_ms.max(start.elapsed().as_secs_f64() * 1000.0);
        reply["value"].clone()
    }

    fn index(&mut self, kind: &str, v: &PlayerView, plays: &[Combo], can_pass: bool) -> Option<usize> {
        let result = self.ask(kind, v, plays, can_pass);
        if result.is_null() {
            assert!(can_pass, "mandatory play declined");
            None
        } else {
            let i = result.as_u64().expect("index must be a nonnegative integer") as usize;
            assert!(i < plays.len(), "index out of range");
            Some(i)
        }
    }
}

impl Drop for PythonBot {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Bot for PythonBot {
    fn name(&self) -> String { "competitive-v2".into() }
    fn grand_tichu(&mut self, v: &PlayerView) -> bool {
        self.ask("grand", v, &[], false).as_bool().expect("grand bool")
    }
    fn small_tichu(&mut self, v: &PlayerView) -> bool {
        self.ask("small", v, &[], false).as_bool().expect("small bool")
    }
    fn pass_cards(&mut self, v: &PlayerView) -> PassInfo {
        serde_json::from_value(self.ask("exchange", v, &[], false)).expect("pass cards")
    }
    fn play(&mut self, v: &PlayerView, plays: &[Combo], can_pass: bool) -> Option<usize> {
        self.index("play", v, plays, can_pass)
    }
    fn bomb(&mut self, v: &PlayerView, bombs: &[Combo]) -> Option<usize> {
        self.index("bomb", v, bombs, true)
    }
    fn wish(&mut self, v: &PlayerView) -> Option<Rank> {
        serde_json::from_value(self.ask("wish", v, &[], false)).expect("wish rank")
    }
    fn dragon_recipient(&mut self, v: &PlayerView) -> Seat {
        self.ask("dragon", v, &[], false).as_u64().expect("dragon seat") as usize
    }
}

fn play_pair(pair: usize, seed: u64, spec: &str, mode: &str, python: &str, root: &str, policy: &str, model: &str) -> Value {
    let mut games = Vec::new();
    for swapped in [false, true] {
        let our_team = swapped as usize;
        let bot_seed = mix(seed, pair as u64, 1 + swapped as u64);
        let metrics = Arc::new(Mutex::new(Metrics::default()));
        let mut players: [Box<dyn Bot>; 4] = [0, 1, 2, 3].map(|seat| {
            if seat % 2 == our_team {
                Box::new(PythonBot::new(python, root, metrics.clone(), policy, model)) as Box<dyn Bot>
            } else if let Some(other) = spec.strip_prefix("python:") {
                Box::new(PythonBot::new(python, root, metrics.clone(), other, "")) as Box<dyn Bot>
            } else {
                let b = bots::by_name(spec, mix(bot_seed, seat as u64, 1)).expect("unknown external bot");
                assert!(!b.cheats(), "oracle bots are forbidden in this benchmark");
                b
            }
        });
        let mut rng = StdRng::seed_from_u64(mix(seed, pair as u64, 0));
        let mut state = GameState::new(Settings::default());
        let mut rounds = Vec::new();
        loop {
            let result = play_round(&mut state, &mut players, &mut rng, None)
                .expect("external engine rejected an action; no fallback");
            // Full deal/state is written only AFTER the round, never to a bot.
            rounds.push(json!({"result": result, "scores": state.scores,
                "deck": state.deck, "actions": state.log, "final_players": state.players}));
            if mode == "rounds" || state.phase == Phase::GameEnd { break; }
            assert!(state.round_number < 200, "match exceeded round cap");
        }
        let m = metrics.lock().unwrap();
        games.push(json!({"swapped": swapped, "our_team": our_team,
            "scores": state.scores, "our_margin": state.scores[our_team]-state.scores[1-our_team],
            "our_win": state.scores[our_team] > state.scores[1-our_team],
            "rounds": rounds, "requests": m.requests, "max_request_ms": m.max_ms}));
    }
    json!({"pair": pair, "seed": seed, "deck_seed": mix(seed, pair as u64, 0),
           "external_revision": REV, "opponent": spec, "mode": mode, "games": games})
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert!(args.len() == 8 || args.len() == 10,
        "usage: bridge OPPONENT PAIRS SEED WORKERS rounds|games PYTHON REPO_ROOT [POLICY MODEL]");
    run(&args);
}

fn run(args: &[String]) {
    let spec = &args[1];
    assert!(!spec.contains("oracle"), "oracle opponents, including wrapped oracles, are forbidden");
    let count: usize = args[2].parse().expect("pairs");
    let seed: u64 = args[3].parse().expect("seed");
    let threads: usize = args[4].parse().expect("workers");
    let mode = &args[5];
    assert!(count > 0 && threads > 0 && ["rounds", "games"].contains(&mode.as_str()));
    if !spec.starts_with("python:") {
        let candidate = bots::by_name(spec, 0).expect("unknown opponent");
        assert!(!candidate.cheats(), "oracle opponent forbidden");
    }
    let policy = args.get(8).map(String::as_str).unwrap_or("competitive");
    let model = args.get(9).map(String::as_str).unwrap_or("");
    let next = AtomicUsize::new(0);
    let failed = AtomicBool::new(false);
    let output = Mutex::new(std::io::stdout());
    std::thread::scope(|scope| {
        for _ in 0..threads.min(count) {
            scope.spawn(|| loop {
                if failed.load(Ordering::Relaxed) { break; }
                let i = next.fetch_add(1, Ordering::Relaxed);
                if i >= count { break; }
                let result = std::panic::catch_unwind(|| play_pair(i, seed, spec, mode, &args[6], &args[7], policy, model));
                let record = match result {
                    Ok(record) => record,
                    Err(error) => {
                        failed.store(true, Ordering::Relaxed);
                        let message = error.downcast_ref::<String>().cloned()
                            .or_else(|| error.downcast_ref::<&str>().map(|s| s.to_string()))
                            .unwrap_or_else(|| "unknown panic".into());
                        json!({"pair": i, "error": message})
                    }
                };
                let mut out = output.lock().unwrap();
                writeln!(out, "{record}").unwrap();
                out.flush().unwrap();
            });
        }
    });
    if failed.load(Ordering::Relaxed) { std::process::exit(1); }
}
