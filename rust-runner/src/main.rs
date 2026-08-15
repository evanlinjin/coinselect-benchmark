//! Fixture-driven runner for `bdk_coin_select`, pinned by `../../pins.json` to the
//! ancestor-aware branch built on the delta-aware branch-and-bound evaluator.
//!
//! Reads one fixture (see `../fixtures/README.md`), runs one track, and writes a JSON
//! result to stdout. The Bitcoin Core runner in `../core-runner` speaks the same
//! fixture in and result out, so `../bench.py` can score both with one formula.
//!
//! Tracks:
//! - `kernel`: `Changeless<LowestFee>` branch and bound, no change output allowed.
//!   Isolates traversal and pruning against Core's `SelectCoinsBnB`.
//! - `changeful`: bare `LowestFee` branch and bound, no single-random-draw fallback. The
//!   counterpart to Core's `CoinGrinder`: both may create change, both are deterministic
//!   searches under the same budget.
//! - `wallet`: `LowestFee` branch and bound (change is the metric's own decision),
//!   falling back to single random draw, mirroring how a wallet would drive this crate.

use std::time::{Duration, Instant};

use bdk_coin_select::{
    float::Ordf32, metrics::LowestFee, AncestorToBump, BnbMetric, CoinSelector, Drain, DrainWeights,
    FeeRate, Input, SelectionProblem, Target, TargetFee, TargetOutputs, TX_FIXED_FIELD_WEIGHT,
};
#[cfg(not(feature = "lowest-fee-changeless"))]
use bdk_coin_select::metrics::Changeless;
#[cfg(feature = "lowest-fee-changeless")]
use bdk_coin_select::metrics::LowestFeeChangeless;
use serde::Serialize;

mod fixture;
use fixture::{varint_size, Fixture, CONFIRMED};

/// Hands a `&CoinSelector` to a [`BnbMetric`] in whichever form the pinned revision wants.
///
/// Before PR #53 the metric methods take `&CoinSelector` directly; after it they take a
/// `&SelectionView` obtained from `compute_view()`. Only the call form differs, so one macro
/// keeps a single runner source building against either side of that change.
#[cfg(not(feature = "selection-view"))]
macro_rules! view {
    ($cs:expr) => {
        $cs
    };
}
#[cfg(feature = "selection-view")]
macro_rules! view {
    ($cs:expr) => {
        &$cs.compute_view()
    };
}

/// Largest candidate count we are willing to brute force (2^20 subsets).
const ORACLE_MAX_CANDIDATES: usize = 20;

#[derive(Serialize)]
struct Timing {
    repeats: usize,
    warmup: usize,
    wall_ns_min: u128,
    wall_ns_median: u128,
    wall_ns_max: u128,
}

#[derive(Serialize)]
struct Native {
    /// The metric's own score for the selection it returned.
    score: Option<f32>,
    drain_value: u64,
    /// Child transaction weight, change output included when the metric chose one.
    child_weight: u64,
    /// Child fee: selected value minus target value minus change value.
    child_fee: i64,
    /// What this selection owes so its whole ancestor union reaches the target feerate.
    ancestor_bump: u64,
    /// Least bump any descendant of this selection could owe (the branch-and-bound credit).
    ancestor_bump_lower_bound: u64,
    excess: i64,
    implied_feerate_sat_per_vb: Option<f32>,
}

#[derive(Serialize)]
struct Oracle {
    ran: bool,
    /// Exhaustive optimum of the same objective the track's metric minimises.
    best_score: Option<f32>,
    best_selected: Vec<String>,
    subsets_evaluated: u64,
}

#[derive(Serialize)]
struct Output {
    runner: &'static str,
    fixture: String,
    family: String,
    size: usize,
    track: String,
    objective: &'static str,
    algorithm: String,
    ok: bool,
    error: Option<String>,
    selected: Vec<String>,
    /// Branch-and-bound rounds, i.e. nodes popped from the priority queue.
    rounds: usize,
    /// True when the search finished the tree; false when it stopped at `search_budget`.
    exhausted: bool,
    budget: usize,
    /// Wall-clock budget the search was given, when it was given one instead of a round budget.
    deadline_us: Option<u64>,
    timing: Timing,
    peak_rss_kb: Option<u64>,
    native: Option<Native>,
    oracle: Oracle,
}

struct Args {
    fixture: String,
    track: String,
    repeat: usize,
    warmup: usize,
    /// Wall-clock budget for the search. `None` stops on the fixture's round budget instead.
    deadline_us: Option<u64>,
    oracle: bool,
    seed_probe: bool,
}

fn parse_args() -> Args {
    let mut fixture = None;
    let mut track = "kernel".to_string();
    let mut repeat = 5usize;
    let mut warmup = 1usize;
    let mut deadline_us = None;
    let mut oracle = false;
    let mut seed_probe = false;
    let mut it = std::env::args().skip(1);
    while let Some(arg) = it.next() {
        match arg.as_str() {
            "--fixture" => fixture = it.next(),
            "--track" => track = it.next().expect("--track needs a value"),
            "--repeat" => repeat = it.next().expect("--repeat needs a value").parse().unwrap(),
            "--warmup" => warmup = it.next().expect("--warmup needs a value").parse().unwrap(),
            "--deadline-us" => {
                deadline_us = Some(it.next().expect("--deadline-us needs a value").parse().unwrap())
            }
            "--oracle" => oracle = true,
            "--seed-probe" => seed_probe = true,
            other => panic!("unknown argument {other}"),
        }
    }
    Args {
        fixture: fixture.expect("--fixture is required"),
        track,
        repeat: repeat.max(1),
        warmup,
        deadline_us: deadline_us.filter(|us| *us > 0),
        oracle,
        seed_probe,
    }
}

/// Reproduce `BnbIter::seed_greedy_incumbent` and report whether it would actually seed.
///
/// The seed is only adopted when the metric *scores* the greedy prefix, and each metric refuses a
/// different prefix: `LowestFeeChangeless` refuses one whose excess is large enough that
/// `LowestFee` would want change, `LowestFee` refuses nothing once funded. This prints which, so
/// the "greedy incumbent" claim can be checked per fixture instead of assumed.
fn seed_probe(f: &Fixture, base: &CoinSelector<'_>) {
    let mut greedy = base.clone();
    greedy.sort_candidates_by_descending_value_pwu();
    let funded = greedy.select_until_target_met().is_ok();
    let view = greedy.compute_view();
    let mut lf = lowest_fee(f);
    let mut cl = changeless_metric(f);
    let (changeless, lowest, drain, excess) = if funded {
        (
            cl.score(&view).map(|s| s.0),
            lf.score(&view).map(|s| s.0),
            lf.drain(&view).value,
            greedy.excess(Drain::NONE),
        )
    } else {
        (None, None, 0, 0)
    };
    // The mirror image: select the *worst* value-per-weight candidates first. Descending order
    // overshoots by whatever the last big coin brings, which is what makes it changeful; ascending
    // order overshoots by at most the smallest coin still needed, which is the only greedy prefix
    // with any chance of landing inside the changeless window.
    let mut tail = base.clone();
    tail.sort_candidates_by_descending_value_pwu();
    let n = f.candidates.len();
    for i in (0..n).rev() {
        if tail.is_funded() {
            break;
        }
        tail.select(i);
    }
    let tail_view = tail.compute_view();
    let tail_changeless = if tail.is_funded() {
        cl.score(&tail_view).map(|s| s.0)
    } else {
        None
    };

    let out = serde_json::json!({
        "fixture": f.name,
        "tail_greedy_inputs": tail.selected_indices().len(),
        "tail_greedy_excess": tail.excess(Drain::NONE),
        "tail_changeless_seeds": tail_changeless.is_some(),
        "candidates": f.candidates.len(),
        "greedy_funded": funded,
        "greedy_inputs": greedy.selected_indices().len(),
        "greedy_excess": excess,
        "lowest_fee_drain_value": drain,
        "lowest_fee_seeds": lowest.is_some(),
        "lowest_fee_seed_score": lowest,
        "changeless_seeds": changeless.is_some(),
        "changeless_seed_score": changeless,
    });
    println!("{}", serde_json::to_string(&out).unwrap());
}

/// Peak resident set size of this process, in KiB. `None` where /proc is unavailable.
fn peak_rss_kb() -> Option<u64> {
    let status = std::fs::read_to_string("/proc/self/status").ok()?;
    for line in status.lines() {
        if let Some(rest) = line.strip_prefix("VmHWM:") {
            return rest.split_whitespace().next()?.parse().ok();
        }
    }
    None
}

fn feerate(sat_per_vb: f64) -> FeeRate {
    FeeRate::from_sat_per_vb(sat_per_vb as f32)
}

/// Build the crate's problem from the fixture.
///
/// Every candidate is its own input group: the fixture disables address grouping so one
/// fixture candidate maps to one Core `OutputGroup` on the other side.
fn build_problem(f: &Fixture) -> SelectionProblem {
    let n_outputs = f.target.n_outputs;
    // The fixture states the whole non-input weight, segwit marker included. This crate adds
    // `TX_FIXED_FIELD_WEIGHT`, the output-count varint, and (when a segwit input is selected)
    // the 2 WU marker itself, so back all three out of the stated total.
    let weight_sum = f
        .target
        .non_input_weight
        .checked_sub(TX_FIXED_FIELD_WEIGHT + 4 * varint_size(n_outputs) + 2)
        .expect("target.non_input_weight is too small to describe a transaction");

    let target = Target {
        fee: TargetFee {
            rate: feerate(f.feerate_sat_per_vb),
            absolute: 0,
            replace: None,
        },
        outputs: TargetOutputs {
            value_sum: f.target.value,
            weight_sum,
            n_outputs,
        },
        max_weight: f.max_weight,
    };

    let txid_index = f.txid_index();
    let inputs: Vec<Input<u32>> = f
        .candidates
        .iter()
        .map(|c| Input {
            value: c.value,
            weight: c.input_weight,
            is_segwit: c.is_segwit,
            residing_txid: match c.residing_txid.as_deref() {
                None => CONFIRMED,
                Some(txid) => *txid_index.get(txid).unwrap_or_else(|| {
                    panic!("candidate {} resides on unknown txid {txid}", c.id)
                }),
            },
        })
        .collect();

    let ancestors: Vec<AncestorToBump<u32>> = f
        .ancestors
        .iter()
        .map(|a| AncestorToBump {
            txid: txid_index[a.txid.as_str()],
            weight: a.weight,
            fee: a.fee,
            parents: a.parents.iter().map(|p| txid_index[p.as_str()]).collect(),
        })
        .collect();

    SelectionProblem::new(target, inputs, ancestors)
}

fn drain_weights(f: &Fixture) -> DrainWeights {
    DrainWeights {
        output_weight: f.change.output_weight,
        spend_weight: f.change.spend_weight,
        n_outputs: 1,
    }
}

/// The kernel track's metric: minimise fee over changeless selections.
///
/// Earlier revisions express this by wrapping `LowestFee` in the generic `Changeless<M>`
/// constraint; later ones replace that with a dedicated `LowestFeeChangeless` carrying a
/// changeless-specific bound. Same objective either way, so the track compares like with like.
#[cfg(not(feature = "lowest-fee-changeless"))]
fn changeless_metric(f: &Fixture) -> Changeless<LowestFee> {
    Changeless(lowest_fee(f))
}
#[cfg(feature = "lowest-fee-changeless")]
fn changeless_metric(f: &Fixture) -> LowestFeeChangeless {
    LowestFeeChangeless::from(lowest_fee(f))
}

fn lowest_fee(f: &Fixture) -> LowestFee {
    LowestFee {
        long_term_feerate: feerate(f.long_term_feerate_sat_per_vb),
        dust_relay_feerate: feerate(f.dust_relay_feerate_sat_per_vb),
        drain_weights: drain_weights(f),
    }
}

struct Search<'a> {
    selection: Option<CoinSelector<'a>>,
    score: Option<Ordf32>,
    rounds: usize,
    exhausted: bool,
}

/// One branch-and-bound search, counting rounds and recording why it stopped.
///
/// Mirrors `CoinSelector::run_bnb` (take `budget` rounds, then probe whether the queue
/// still has work) but keeps the round count and the exhausted/budget-hit distinction,
/// which `run_bnb` only surfaces on failure.
fn search<'a, M: BnbMetric + Copy>(
    cs: &CoinSelector<'a>,
    metric: M,
    budget: usize,
    deadline: Option<Instant>,
) -> Search<'a> {
    let mut iter = cs.bnb_solutions(metric);
    let mut rounds = 0;
    let mut best = None;
    let mut exhausted = true;
    let mut deadline_hit = false;
    for _ in 0..budget {
        // Polled every 256 rounds, matching the Core patch: an `Instant::now()` costs a
        // meaningful fraction of a round, so checking every round would distort the measurement.
        if let Some(deadline) = deadline {
            if rounds & 0xff == 0 && Instant::now() >= deadline {
                deadline_hit = true;
                break;
            }
        }
        match iter.next() {
            Some(solution) => {
                rounds += 1;
                if let Some(found) = solution {
                    best = Some(found);
                }
            }
            None => break,
        }
    }
    if deadline_hit || (rounds == budget && iter.next().is_some()) {
        exhausted = false;
    }
    let (selection, score) = match best {
        Some((cs, score)) => (Some(cs), Some(score)),
        None => (None, None),
    };
    Search {
        selection,
        score,
        rounds,
        exhausted,
    }
}

/// Deterministic uniform `u64` source, seeded from the fixture. Only the single-random-draw
/// fallback uses it, and only when branch and bound found nothing.
fn seeded_rng(seed: u64) -> impl FnMut() -> u64 {
    // splitmix64
    let mut state = seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
    move || {
        state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
}

fn selected_ids(f: &Fixture, cs: &CoinSelector<'_>) -> Vec<String> {
    cs.selected_indices()
        .iter()
        .map(|i| f.candidates[i].id.clone())
        .collect()
}

fn native(cs: &CoinSelector<'_>, drain: Drain, score: Option<Ordf32>) -> Native {
    let target = cs.target();
    Native {
        score: score.map(|s| s.0),
        drain_value: drain.value,
        child_weight: cs.weight(target.outputs, drain.weights),
        child_fee: cs.fee(target.value(), drain.value),
        ancestor_bump: cs.ancestor_bump(),
        ancestor_bump_lower_bound: cs.ancestor_bump_lower_bound(),
        excess: cs.excess(drain),
        implied_feerate_sat_per_vb: cs
            .implied_feerate(target.outputs, drain)
            .map(|r| r.as_sat_vb()),
    }
}

/// Exhaustive optimum over every subset, for fixtures small enough to enumerate.
///
/// This is what makes a "different selection" report meaningful: it says which runner (if
/// either) actually found the best answer under this crate's objective, rather than only
/// that the two disagreed.
fn run_oracle<M: BnbMetric + Copy>(
    f: &Fixture,
    problem: &SelectionProblem,
    mut metric: M,
    enabled: bool,
) -> Oracle {
    let n = problem.len();
    if !enabled || n > ORACLE_MAX_CANDIDATES {
        return Oracle {
            ran: false,
            best_score: None,
            best_selected: Vec::new(),
            subsets_evaluated: 0,
        };
    }
    let base = CoinSelector::new(problem);
    let mut best: Option<(Ordf32, u32)> = None;
    for mask in 0u32..(1u32 << n) {
        let mut cs = base.clone();
        for i in 0..n {
            if mask >> i & 1 == 1 {
                cs.select(i);
            }
        }
        if let Some(score) = metric.score(view!(&cs)) {
            if best.map_or(true, |(b, _)| score < b) {
                best = Some((score, mask));
            }
        }
    }
    let best_selected = best
        .map(|(_, mask)| {
            (0..n)
                .filter(|i| mask >> i & 1 == 1)
                .map(|i| f.candidates[i].id.clone())
                .collect()
        })
        .unwrap_or_default();
    Oracle {
        ran: true,
        best_score: best.map(|(s, _)| s.0),
        best_selected,
        subsets_evaluated: 1u64 << n,
    }
}

fn median(mut samples: Vec<u128>) -> u128 {
    samples.sort_unstable();
    samples[samples.len() / 2]
}

fn main() {
    let args = parse_args();
    let f = Fixture::load(&args.fixture);
    let problem = build_problem(&f);
    let base = CoinSelector::new(&problem);
    let budget = f.search_budget;

    if args.seed_probe {
        seed_probe(&f, &base);
        return;
    }

    let (objective, algorithm) = match args.track.as_str() {
        "kernel" => (
            "minimise child fee, changeless (Changeless<LowestFee>)",
            "bnb/changeless-lowest-fee",
        ),
        "changeful" => (
            "minimise long-term fee, change at the metric's discretion (LowestFee)",
            "bnb/lowest-fee",
        ),
        "wallet" => (
            "minimise long-term fee, change at the metric's discretion (LowestFee)",
            "bnb/lowest-fee+srd-fallback",
        ),
        other => panic!("unknown track {other}"),
    };

    // Timed region: everything the track would do to produce a selection, and nothing else.
    // Fixture parsing and problem construction sit outside it. The single-random-draw fallback is
    // inside, because Core times its whole portfolio (single random draw included) and a
    // wallet-track number that excluded the path the answer actually came from would not be
    // comparable.
    let mut samples = Vec::with_capacity(args.repeat);
    let mut last: Option<(Search, Option<Drain>)> = None;
    for i in 0..(args.warmup + args.repeat) {
        let start = Instant::now();
        let deadline = args.deadline_us.map(|us| start + Duration::from_micros(us));
        let mut result = match args.track.as_str() {
            "kernel" => search(&base, changeless_metric(&f), budget, deadline),
            _ => search(&base, lowest_fee(&f), budget, deadline),
        };
        // Fall back to single random draw exactly as a wallet would: wallet track only, and only
        // when branch and bound came back empty.
        let mut srd_drain = None;
        if args.track == "wallet" && result.selection.is_none() {
            let mut cs = base.clone();
            if let Ok(drain) = cs.select_srd(
                drain_weights(&f),
                bdk_coin_select::CHANGE_LOWER,
                seeded_rng(f.seed),
            ) {
                srd_drain = Some(drain);
                result.selection = Some(cs);
            }
        }
        let elapsed = start.elapsed().as_nanos();
        if i >= args.warmup {
            samples.push(elapsed);
        }
        last = Some((result, srd_drain));
    }
    let (result, srd_drain) = last.expect("at least one repeat runs");
    // Read the high-water mark before the oracle runs: brute forcing allocates, and the number
    // is supposed to describe the search.
    let peak_rss = peak_rss_kb();
    let algorithm = match srd_drain {
        Some(_) => "srd".to_string(),
        None => algorithm.to_string(),
    };

    let oracle = match args.track.as_str() {
        "kernel" => run_oracle(&f, &problem, changeless_metric(&f), args.oracle),
        _ => run_oracle(&f, &problem, lowest_fee(&f), args.oracle),
    };

    let (ok, error, selected, native_out) = match &result.selection {
        Some(cs) => {
            let drain = match srd_drain {
                Some(drain) => drain,
                None if args.track == "kernel" => Drain::NONE,
                None => lowest_fee(&f).drain(view!(cs)),
            };
            (
                true,
                None,
                selected_ids(&f, cs),
                Some(native(cs, drain, result.score)),
            )
        }
        None => (
            false,
            Some(match result.exhausted {
                true => "no solution: search exhausted the tree".to_string(),
                false => format!("no solution within {budget} rounds"),
            }),
            Vec::new(),
            None,
        ),
    };

    let out = Output {
        runner: "coin-select",
        fixture: f.name.clone(),
        family: f.family.clone(),
        size: f.candidates.len(),
        track: args.track.clone(),
        objective,
        algorithm,
        ok,
        error,
        selected,
        rounds: result.rounds,
        exhausted: result.exhausted,
        budget,
        deadline_us: args.deadline_us,
        timing: Timing {
            repeats: args.repeat,
            warmup: args.warmup,
            wall_ns_min: *samples.iter().min().unwrap(),
            wall_ns_max: *samples.iter().max().unwrap(),
            wall_ns_median: median(samples),
        },
        peak_rss_kb: peak_rss,
        native: native_out,
        oracle,
    };
    println!("{}", serde_json::to_string(&out).expect("result serialises"));
}
