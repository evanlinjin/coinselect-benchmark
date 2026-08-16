//! Fixture-driven runner for `bdk_coin_select`, pinned by `../../pins.json` to the
//! ancestor-aware branch built on the delta-aware branch-and-bound evaluator.
//!
//! Reads one fixture (see `../fixtures/README.md`), runs one track, and writes a JSON
//! result to stdout. The Bitcoin Core runner in `../core-runner` speaks the same
//! fixture in and result out, so `../bench.py` can score both with one formula.
//!
//! Tracks:
//! - `wallet`: `LowestFee` branch and bound (change is the metric's own decision),
//!   falling back to single random draw, mirroring how a wallet would drive this crate.
//!   The only track: the pinned revision has no changeless metric, so there is nothing
//!   left to run against Core's `SelectCoinsBnB` in isolation.

use std::time::{Duration, Instant};

use bdk_coin_select::{
    float::Ordf32, metrics::LowestFee, AncestorToBump, BnbMetric, CoinSelector, Drain, DrainWeights,
    FeeRate, Input, SelectionProblem, SelectionView, Target, TargetFee, TargetOutputs,
    TX_FIXED_FIELD_WEIGHT,
};
use serde::Serialize;

mod fixture;
use fixture::{varint_size, Fixture, CONFIRMED};

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
    max_n: Option<usize>,
    ban_policy: String,
    restarts: usize,
    cap_on_budget: bool,
    /// Offsets every sample's rng salt, so a policy can be measured over independent draws.
    sample_seed: u64,
    pool_probe: bool,
    epsilon_probe: bool,
    /// Overrides the fixture's round budget.
    budget: Option<usize>,
    /// Escalate the pool size across phases instead of fixing it; ignores `--restarts`.
    escalate: bool,
    /// How the pool is guaranteed to be able to fund the target: `greedy` or `random`.
    prefix: String,
}

fn parse_args() -> Args {
    let mut fixture = None;
    let mut track = "wallet".to_string();
    let mut repeat = 5usize;
    let mut warmup = 1usize;
    let mut deadline_us = None;
    let mut oracle = false;
    let mut seed_probe = false;
    let mut max_n = None;
    let mut ban_policy = "random".to_string();
    let mut restarts = 1usize;
    let mut cap_on_budget = false;
    let mut sample_seed = 0u64;
    let mut pool_probe = false;
    let mut epsilon_probe = false;
    let mut budget = None;
    let mut escalate = false;
    let mut prefix = "greedy".to_string();
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
            "--max-n" => max_n = Some(it.next().expect("--max-n needs a value").parse().unwrap()),
            "--ban-policy" => ban_policy = it.next().expect("--ban-policy needs a value"),
            "--cap-on-budget" => cap_on_budget = true,
            "--pool-probe" => pool_probe = true,
            "--epsilon-probe" => epsilon_probe = true,
            "--escalate" => escalate = true,
            "--prefix" => prefix = it.next().expect("--prefix needs a value"),
            "--budget" => budget = Some(it.next().expect("--budget needs a value").parse().unwrap()),
            "--sample-seed" => {
                sample_seed = it.next().expect("--sample-seed needs a value").parse().unwrap()
            }
            "--restarts" => {
                restarts = it.next().expect("--restarts needs a value").parse().unwrap()
            }
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
        max_n: max_n.filter(|n| *n > 0),
        ban_policy,
        restarts: restarts.max(1),
        cap_on_budget,
        sample_seed,
        pool_probe,
        epsilon_probe,
        budget,
        escalate,
        prefix,
    }
}

/// Reproduce `BnbIter::seed_greedy_incumbent` and report whether it would actually seed.
///
/// The seed is only adopted when the metric *scores* the greedy prefix, and `LowestFee` refuses
/// nothing once the prefix is funded. This prints the prefix and what the metric made of it, so
/// the "greedy incumbent" claim can be checked per fixture instead of assumed.
fn seed_probe(f: &Fixture, base: &CoinSelector<'_>) {
    let mut greedy = base.clone();
    greedy.sort_candidates_by_descending_value_pwu();
    let funded = greedy.select_until_target_met().is_ok();
    let view = greedy.compute_view();
    let mut lf = lowest_fee(f);
    let (lowest, drain, excess) = if funded {
        (
            lf.score(&view).map(|s| s.0),
            lf.drain(&view).value,
            view.excess(Drain::NONE),
        )
    } else {
        (None, 0, 0)
    };

    // Cluster structure decides whether an ancestry-aware cut can differ from a uniform one at all:
    // if every candidate is its own cluster there is no shared ancestor to preserve.
    let cluster = ancestor_clusters(base.problem());
    let mut sizes: std::collections::HashMap<usize, usize> = Default::default();
    for &c in &cluster {
        *sizes.entry(c).or_default() += 1;
    }
    let with_ancestry = (0..base.problem().len())
        .filter(|&i| !base.problem().drags_in(i).is_empty())
        .count();

    let out = serde_json::json!({
        "fixture": f.name,
        "candidates_with_ancestry": with_ancestry,
        "clusters": sizes.len(),
        "largest_cluster": sizes.values().copied().max().unwrap_or(0),
        "multi_candidate_clusters": sizes.values().filter(|&&s| s > 1).count(),
        "candidates": f.candidates.len(),
        "greedy_funded": funded,
        "greedy_inputs": greedy.selected_indices().len(),
        "greedy_excess": excess,
        "lowest_fee_drain_value": drain,
        "lowest_fee_seeds": lowest.is_some(),
        "lowest_fee_seed_score": lowest,
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

fn lowest_fee(f: &Fixture) -> LowestFee {
    LowestFee {
        long_term_feerate: feerate(f.long_term_feerate_sat_per_vb),
        dust_relay_feerate: feerate(f.dust_relay_feerate_sat_per_vb),
        drain_weights: drain_weights(f),
    }
}

/// Group candidates that can reach each other through a shared unconfirmed ancestor.
///
/// Union-find over candidates, joined by every ancestor two of them both drag in. A candidate with
/// no ancestry, or one whose ancestors nobody else reaches, is its own cluster. Selecting a second
/// candidate from a cluster costs nothing extra for the ancestors already paid for by the first,
/// which is the structure a coin-level random cut is blind to.
fn ancestor_clusters(problem: &SelectionProblem) -> Vec<usize> {
    fn find(parent: &mut [usize], mut i: usize) -> usize {
        while parent[i] != i {
            parent[i] = parent[parent[i]];
            i = parent[i];
        }
        i
    }
    let n = problem.len();
    let mut parent: Vec<usize> = (0..n).collect();
    let mut first_seen: std::collections::HashMap<usize, usize> = Default::default();
    for i in 0..n {
        for ancestor in problem.drags_in(i).iter() {
            match first_seen.get(&ancestor) {
                None => {
                    first_seen.insert(ancestor, i);
                }
                Some(&j) => {
                    let (a, b) = (find(&mut parent, i), find(&mut parent, j));
                    if a != b {
                        parent[a] = b;
                    }
                }
            }
        }
    }
    (0..n).map(|i| find(&mut parent, i)).collect()
}


/// How many *distinct* selections score within a given epsilon of the optimum.
///
/// The question this answers: on a fixture whose search exhausts, returning a random near-optimal
/// selection instead of the unique optimum would buy selection entropy at a stated fee cost. That
/// is only worth building if the near-optimal set is actually populated.
///
/// Two views, because neither alone is enough. Brute force is exact but caps at 20 candidates.
/// The 1-swap neighbourhood of the optimum (drop one selected coin and/or add one unselected coin)
/// is a *lower bound* on the count at any size, and it is also the cheapest neighbourhood a real
/// implementation could search, so it doubles as a feasibility estimate.
fn epsilon_probe(f: &Fixture, base: &CoinSelector<'_>, budget: usize) {
    const EPS: [f32; 4] = [0.0, 0.001, 0.01, 0.05];
    let mut metric = lowest_fee(f);
    let result = search(base, metric, budget, None);
    let Some(best) = result.score.map(|s| s.0) else {
        println!("{}", serde_json::json!({"fixture": f.name, "solved": false}));
        return;
    };
    let n = f.candidates.len();

    let mut score_of = |sel: &CoinSelector<'_>| metric.score(&sel.compute_view()).map(|s| s.0);

    // 1-swap neighbourhood: keep, drop-one, add-one, and swap-one-for-one.
    let opt = result.selection.expect("scored, so present");
    let selected: Vec<usize> = opt.selected_indices().iter().collect();
    let unselected: Vec<usize> = (0..n).filter(|i| !opt.is_selected(*i)).collect();
    let mut neighbours = vec![best];
    for &i in &selected {
        let mut cs = opt.clone();
        cs.deselect(i);
        if let Some(v) = score_of(&cs) {
            neighbours.push(v);
        }
        for &j in &unselected {
            let mut cs2 = cs.clone();
            cs2.select(j);
            if let Some(v) = score_of(&cs2) {
                neighbours.push(v);
            }
        }
    }
    for &j in &unselected {
        let mut cs = opt.clone();
        cs.select(j);
        if let Some(v) = score_of(&cs) {
            neighbours.push(v);
        }
    }

    // Exhaustive, where it is affordable.
    let mut exhaustive: Option<Vec<f32>> = None;
    if n <= ORACLE_MAX_CANDIDATES {
        let mut all = Vec::new();
        for mask in 0u32..(1u32 << n) {
            let mut cs = base.clone();
            for i in 0..n {
                if mask >> i & 1 == 1 {
                    cs.select(i);
                }
            }
            if let Some(v) = score_of(&cs) {
                all.push(v);
            }
        }
        exhaustive = Some(all);
    }

    let count_within = |xs: &[f32], eps: f32| -> usize {
        let cut = best * (1.0 + eps);
        let mut seen: Vec<f32> = xs.iter().copied().filter(|v| *v <= cut).collect();
        seen.sort_by(|a, b| a.partial_cmp(b).unwrap());
        seen.len()
    };

    let mut out = serde_json::Map::new();
    out.insert("fixture".into(), f.name.clone().into());
    out.insert("candidates".into(), n.into());
    out.insert("solved".into(), true.into());
    out.insert("exhausted".into(), result.exhausted.into());
    out.insert("optimum".into(), best.into());
    out.insert("inputs".into(), selected.len().into());
    for eps in EPS {
        let key = format!("swap_within_{}", eps);
        out.insert(key, count_within(&neighbours, eps).into());
        if let Some(all) = &exhaustive {
            out.insert(format!("all_within_{}", eps), count_within(all, eps).into());
        }
    }
    println!("{}", serde_json::to_string(&serde_json::Value::Object(out)).unwrap());
}

/// Shrink the search pool to at most `max_n` candidates by banning the rest.
///
/// Every candidate the greedy prefix uses is kept, which is what keeps the reduced pool able to
/// fund the target at all — without that guarantee a random cut can leave a pool that cannot reach
/// the value target, turning a slow answer into no answer.
///
/// The remainder is ordered by a per-policy key and the lowest keys are banned. All four policies
/// break ties randomly, seeded from the fixture and the draw, so a run is reproducible:
///
/// - `random`: uniform. The baseline every ancestry-aware policy has to beat.
/// - `worst`: drop the lowest value-per-weight candidates first. Deterministic.
/// - `cluster`: keep or drop whole ancestor clusters together, preferring clusters the greedy
///   prefix already draws from. A coin-level cut can drop the second coin sharing an ancestor,
///   losing the discount that made the first one worth taking; this cannot.
/// - `shared`: prefer candidates that drag in nothing the greedy prefix has not already paid for,
///   then candidates with no ancestry, and drop candidates dragging in fresh ancestors first.
///
/// If the greedy prefix alone already needs `max_n` or more inputs, everything outside it is
/// banned and the search looks for a better subset of the greedy selection.
fn cap_pool<'a>(
    f: &Fixture,
    base: &CoinSelector<'a>,
    max_n: usize,
    policy: &str,
    prefix: &str,
    salt: u64,
) -> CoinSelector<'a> {
    let n = f.candidates.len();
    let mut cs = base.clone();
    cs.sort_candidates_by_descending_value_pwu();
    if n <= max_n {
        return cs;
    }

    // `--prefix random` pins nothing: draw a uniform pool and extend it only as far as fundability
    // demands. The greedy prefix guarantees the pool can fund the target, but it is a
    // *deterministic* guarantee — those candidates sit in every sample of every transaction, so
    // they are disproportionately available to be selected. Drawing first and repairing on demand
    // keeps the guarantee without the fixed point.
    if prefix == "random" {
        let mut order: Vec<usize> = (0..n).collect();
        let mut rng = seeded_rng(f.seed ^ salt.wrapping_mul(0x9E37_79B9_7F4A_7C15));
        for i in (1..order.len()).rev() {
            order.swap(i, (rng() % (i as u64 + 1)) as usize);
        }
        // How far down the shuffled order fundability actually reaches. Taking a prefix at least
        // this long is enough, because it contains the funding set itself. One `SelectionView`,
        // updated in place: `add` is the incremental form of selecting, so the whole walk costs
        // what recomputing the aggregates once used to.
        let scratch = cs.clone();
        let mut view = scratch.compute_view();
        let mut need = n;
        for (k, &i) in order.iter().enumerate() {
            view.add(i);
            if view.is_funded() {
                need = k + 1;
                break;
            }
        }
        let take = max_n.max(need);
        if take >= n {
            return cs;
        }
        for &i in order.iter().skip(take) {
            cs.ban(i);
        }
        return cs;
    }

    // `--prefix jittered`: a randomized greedy funding set. Take the next coin uniformly from the
    // best `JITTER_K` remaining by value-per-weight rather than always the very best. The set stays
    // about as small as the strict greedy prefix — which is what keeps the pool inside `max_n` —
    // but its membership varies per sample, so no candidate is pinned into every pool.
    let keep: Vec<usize> = if prefix.starts_with("jittered") {
        const JITTER_K: usize = 4;
        let mut rng = seeded_rng(f.seed ^ salt.wrapping_mul(0x51_7C_C1_B7_27_22_0A_95));
        let chosen = cs.clone();
        // Again one view carried across the loop; the picks are tracked here because a view's
        // hypothetical `add` deliberately leaves the selector's own selected set alone.
        let mut view = chosen.compute_view();
        let mut picked = Vec::new();
        let mut avail: Vec<usize> = cs.candidates().map(|(i, _)| i).collect();
        while !view.is_funded() && !avail.is_empty() {
            let k = JITTER_K.min(avail.len());
            let i = avail.remove((rng() % k as u64) as usize);
            view.add(i);
            picked.push(i);
        }
        picked
    } else {
        let mut greedy = cs.clone();
        let _ = greedy.select_until_target_met();
        greedy.selected_indices().iter().collect()
    };

    // Descending value-per-weight order, so a candidate's position here is its pwu rank.
    let rest: Vec<usize> = cs
        .candidates()
        .map(|(i, _)| i)
        .filter(|i| !keep.contains(i))
        .collect();
    let mut rng = seeded_rng(f.seed ^ salt.wrapping_mul(0x9E37_79B9_7F4A_7C15));
    let problem = base.problem();

    // Sorted ascending; the lowest keys are banned. Rank first, random tiebreak second.
    let mut keyed: Vec<(u64, u64, usize)> = match policy {
        "random" => rest.iter().map(|&i| (0, rng(), i)).collect(),
        // `rest` is in descending value-per-weight order, so a high rank is a poor candidate and
        // must sort low to be banned first.
        "worst" => rest
            .iter()
            .enumerate()
            .map(|(rank, &i)| (u64::MAX - rank as u64, 0, i))
            .collect(),
        // `cluster` pins any cluster the greedy prefix draws from; `cluster-soft` gives every
        // cluster an equal chance instead. Both keep siblings together; only the first one biases
        // *which* clusters survive.
        "cluster" | "cluster-soft" => {
            let cluster = ancestor_clusters(problem);
            let mut cluster_key: std::collections::HashMap<usize, u64> = Default::default();
            for &i in &rest {
                cluster_key.entry(cluster[i]).or_insert_with(&mut rng);
            }
            if policy == "cluster" {
                for &i in &keep {
                    cluster_key.insert(cluster[i], u64::MAX);
                }
            }
            rest.iter()
                .map(|&i| (cluster_key[&cluster[i]], rng(), i))
                .collect()
        }
        "shared" => {
            let mut covered = std::collections::HashSet::new();
            for &i in &keep {
                covered.extend(problem.drags_in(i).iter());
            }
            rest.iter()
                .map(|&i| {
                    let drags_in = problem.drags_in(i);
                    let tier = match drags_in.is_empty() {
                        true => 1,
                        false => match drags_in.iter().all(|a| covered.contains(&a)) {
                            true => 2,
                            false => 0,
                        },
                    };
                    (tier, rng(), i)
                })
                .collect()
        }
        other => panic!("unknown --ban-policy {other}"),
    };
    keyed.sort_unstable();

    for &(_, _, i) in keyed.iter().take(n - max_n) {
        cs.ban(i);
    }

    // The load-bearing invariant: whatever the policy banned, the greedy prefix survived, so the
    // reduced pool can still reach the value target. A cut that breaks this turns a slow answer
    // into no answer, and would do it silently.
    let mut check = cs.clone();
    assert!(
        check.select_until_target_met().is_ok(),
        "{} pool of {max_n} under `{policy}` cannot fund the target",
        f.name,
    );
    cs
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

fn native(view: &SelectionView<'_>, drain: Drain, score: Option<Ordf32>) -> Native {
    let target = view.target();
    Native {
        score: score.map(|s| s.0),
        drain_value: drain.value,
        child_weight: view.weight(target.outputs, drain.weights),
        child_fee: view.fee(target.value(), drain.value),
        ancestor_bump: view.ancestor_bump(),
        ancestor_bump_lower_bound: view.ancestor_bump_lower_bound(),
        excess: view.excess(drain),
        implied_feerate_sat_per_vb: view
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
        if let Some(score) = metric.score(&cs.compute_view()) {
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
    let budget = args.budget.unwrap_or(f.search_budget);

    if args.seed_probe {
        seed_probe(&f, &base);
        return;
    }

    if args.epsilon_probe {
        epsilon_probe(&f, &base, args.budget.unwrap_or(f.search_budget));
        return;
    }

    // Dump the pool each draw would search, so cross-draw diversity can be measured per policy.
    if let (Some(max_n), true) = (args.max_n, args.pool_probe) {
        let pools: Vec<Vec<usize>> = (0..args.restarts)
            .map(|draw| {
                let pool = cap_pool(&f, &base, max_n, &args.ban_policy, &args.prefix, draw as u64);
                (0..f.candidates.len())
                    .filter(|i| !pool.banned().contains(*i))
                    .collect()
            })
            .collect();
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({
                "fixture": f.name, "policy": args.ban_policy, "pools": pools,
            }))
            .unwrap()
        );
        return;
    }

    let (objective, algorithm) = match args.track.as_str() {
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
        // Pool capping is inside the timed region: it is work the wallet would be doing. With
        // `--restarts`, each draw is an independent sample of the pool and the best answer across
        // draws wins — a capped search is cheap enough to run many times.
        //
        // `--cap-on-budget` uses the full search's own budget signal as the trigger: if it
        // exhausted the tree it already holds the optimum and capping could only throw candidates
        // the optimum needs away, so keep it. Only a search that ran out of budget gets capped.
        let mut prior = None;
        let mut max_n = args.max_n;
        if args.cap_on_budget {
            // Under a wall-clock budget the full search must not be allowed to spend all of it, or
            // the sampling phase it is supposed to trigger never runs. Give it half.
            let probe_deadline = match args.deadline_us {
                Some(us) => Some(start + Duration::from_micros(us / 2)),
                None => deadline,
            };
            let r = search(&base, lowest_fee(&f), budget, probe_deadline);
            if r.exhausted {
                max_n = None;
            }
            prior = Some(r);
        }
        let mut result = match max_n {
            None => match prior {
                Some(r) => r,
                None => search(&base, lowest_fee(&f), budget, deadline),
            },
            Some(max_n) => {
                // The budget-exhausted full search, when there was one, is just another draw: its
                // answer competes with the capped ones rather than being discarded.
                let mut best: Option<Search> = prior;
                let mut spent = 0usize;

                // One phase of sampling at a fixed pool size, spending at most `phase_budget`
                // rounds. Draws until that runs out rather than taking a draw count, because how
                // many rounds a pool needs varies by four orders of magnitude across fixtures at
                // the same size — a caller cannot predict it and neither can a formula.
                macro_rules! sample_phase {
                    ($max_n:expr, $phase_budget:expr, $per_draw:expr, $salt:expr) => {{
                        let phase_budget: usize = $phase_budget;
                        let mut used = 0usize;
                        let mut draw = 0u64;
                        while used < phase_budget {
                            let per = $per_draw.min(phase_budget - used).max(1);
                            let pool = cap_pool(&f, &base, $max_n, &args.ban_policy, &args.prefix, $salt + draw);
                            let r = search(&pool, lowest_fee(&f), per, deadline);
                            used += r.rounds.max(1);
                            let better = match (&best, &r.score) {
                                (_, None) => false,
                                (None, Some(_)) => true,
                                (Some(b), Some(s)) => b.score.map_or(true, |bs| *s < bs),
                            };
                            if better || best.is_none() {
                                best = Some(r);
                            }
                            draw += 1;
                            if f.candidates.len() <= $max_n
                                || deadline.map_or(false, |d| Instant::now() >= d)
                            {
                                break;
                            }
                        }
                        spent += used;
                    }};
                }

                let salt_base = args.sample_seed * 1_000_003;
                match args.escalate {
                    // Fixed pool size, `--restarts` draws, one budget between them.
                    false => {
                        let draws = match f.candidates.len() <= max_n {
                            true => 1,
                            false => args.restarts.max(1),
                        };
                        sample_phase!(max_n, budget, (budget / draws).max(1), salt_base);
                    }
                    // No pool size and no draw count: probe upward for the largest pool a single
                    // sample can still exhaust, then spend everything left sampling at that size.
                    //
                    // Rounds needed grows roughly tenfold per +25 candidates, so every probe below
                    // the largest affordable size together costs a fraction of that size alone —
                    // and each probe's answer competes as a sample regardless, so none is wasted.
                    // Escalating blindly is what does not work: a pool too large to exhaust
                    // contributes nothing but consumes whatever it is given.
                    true => {
                        let probe_cap = (budget / 8).max(1);
                        let mut m = 25;
                        let mut affordable = 25;
                        while m < f.candidates.len() && spent < budget / 2 {
                            let pool =
                                cap_pool(&f, &base, m, &args.ban_policy, &args.prefix, salt_base + m as u64);
                            let r = search(&pool, lowest_fee(&f), probe_cap, deadline);
                            spent += r.rounds;
                            let exhausted = r.exhausted;
                            let better = match (&best, &r.score) {
                                (_, None) => false,
                                (None, Some(_)) => true,
                                (Some(b), Some(s)) => b.score.map_or(true, |bs| *s < bs),
                            };
                            if better || best.is_none() {
                                best = Some(r);
                            }
                            if !exhausted {
                                break;
                            }
                            affordable = m;
                            m *= 2;
                        }
                        let left = budget.saturating_sub(spent);
                        // A diversity floor: no single draw may eat the whole remaining phase.
                        sample_phase!(affordable, left, (left / 20).max(1), salt_base + 7919);
                    }
                }
                let mut out = best.expect("at least one draw runs");
                out.rounds = spent;
                out
            }
        };
        // Fall back to single random draw exactly as a wallet would: only when branch and bound
        // came back empty.
        let mut srd_drain = None;
        if result.selection.is_none() {
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

    let oracle = run_oracle(&f, &problem, lowest_fee(&f), args.oracle);

    let (ok, error, selected, native_out) = match &result.selection {
        Some(cs) => {
            // One view for both the metric's change decision and the native figures.
            let cs_view = cs.compute_view();
            let drain = match srd_drain {
                Some(drain) => drain,
                None => lowest_fee(&f).drain(&cs_view),
            };
            (
                true,
                None,
                selected_ids(&f, cs),
                Some(native(&cs_view, drain, result.score)),
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
