# Plan: depth-first branch and bound for `bdk_coin_select`

A design for replacing the priority-queue traversal in `src/bnb.rs` with an in-place depth-first
search, on top of the ancestor-aware selection work. Written against evidence from this benchmark;
every claim below has a fixture behind it in `results/`.

## 1. Why — the search order is the defect

The current search is best-first over a min-heap keyed on `BnbMetric::bound`. For both shipped
metrics that bound **increases monotonically with depth**: `LowestFee`'s fee floor grows as inputs
are added, and `LowestFeeChangeless` takes `max(funding_bound, selected_value - target_value)`,
whose second term grows with every inclusion.

A min-heap over a cost that rises with depth always pops the shallowest node available. The search
therefore expands every 1-input prefix, then every 2-input prefix, and so on — uniform-cost search
in all but name, with a branching factor equal to the candidate count. That is the whole failure:

- Solutions in this matrix are **shallow**: 1, 2, 4, 10, 11, 13, 23 and 28 inputs across the
  fixtures measured. They are not hard to reach; they are 13 levels down a tree the search never
  descends.
- At 500+ candidates the search exhausts 100,000 rounds without reaching *any* funded selection,
  on `no_ancestry` as readily as on the ancestry families. At 1,000,000 rounds seven of nine large
  fixtures still return nothing, at up to 15.8 s.
- A greedy prefix — which is exactly what a DFS leftmost descent constructs — reaches the **same
  score and same input count** as the full search on every fixture where both produce an answer.

Two things follow, and the second is easy to get wrong:

**Traversal is the fix.** Depth-first reaches a funded leaf in as many expansions as the solution
has inputs.

**Pruning is a separate problem, and seeding an incumbent does not solve it.** Both prune sites in
`BnbIter` are gated on `best` being `Some`, so nothing is pruned before the first solution. That
looks like the cause, but it is not: seeding `best` with a greedy solution up front changes round
counts by under 0.5% and leaves every failure a failure. Shallow nodes have small bounds, so they
pass `bound < best` regardless of how good the incumbent is. Do not expect an incumbent alone to
buy anything; it is worth doing for anytime behaviour, not for pruning.

## 2. Core structure

Replace `BinaryHeap<Branch>` with an explicit stack of decisions over one mutable selection.

```
struct Step { index: usize, included: bool, cache_undo: … }
struct DfsIter<'a, M> {
    selector: CoinSelector<'a>,   // mutated in place
    cache: SelectionCache,        // mutated in place
    stack: Vec<Step>,
    best: Option<Ordf32>,
    metric: M,
}
```

Each iteration either descends (take the next undecided candidate, inclusion branch first),
or backtracks (pop to the most recent inclusion and flip it to exclusion).

`SelectionCache` already exposes incremental `add`/`sub`, so descent and backtrack are O(1) rather
than the clone-per-push the queue requires. This removes the two costs the current design pays:

- **Memory**: O(depth) rather than O(frontier), and this is the most urgent of the three. Peak RSS
  reaches 293 MB at the default round cap, but the cap is what is holding it there — given a
  130-second budget the frontier reaches **20 GB on a 500-candidate problem**, because a
  best-first search over a depth-increasing bound never finishes a level and so never discards
  one. A wallet that hits this fails hard rather than slowly. A stack is bounded by the candidate
  count: kilobytes.
- **Per node**: the current search spends 530–1400 ns per round, dominated by cloning a
  `CoinSelector` plus its cache on every push. An in-place step should reach tens of nanoseconds.

Keep inclusion-first ordering with candidates sorted by descending value-per-weight, which is what
`requires_ordering_by_descending_value_pwu` already arranges. That makes the leftmost descent the
greedy prefix, i.e. a good solution within a few dozen expansions.

## 3. Pruning

Three prunes, applied at each node before descending:

1. **Bound against incumbent** — `bound(node) >= best` cuts the subtree. Unchanged in meaning from
   today, but now it fires from the first descent because an incumbent exists almost immediately.
2. **Monotone upper bound on value.** This is the prune the current design lacks. For a changeless
   objective the score is `selected_value - target_value`, which only grows down an inclusion
   branch, so once it exceeds `best` no descendant can improve and the subtree is dead. This is the
   structural cut that keeps a depth-first search's node counts small; without it, depth-first
   explores far more nodes than the queue does, not fewer.
3. **Weight cap** — `!is_within_max_weight(NONE)` already hard-prunes and is monotone; keep it.

Preserve the existing exclusion-branch de-duplication, including its requirement that candidates
match on `drags_in` as well as value and weight. Two coins of equal value and weight are *not*
interchangeable when one drags in an unconfirmed ancestor that still needs bumping, and collapsing
them is a silent correctness bug rather than a performance one.

## 4. Budget and anytime behaviour

Keep `max_rounds` counting node expansions and keep the improving-solutions iterator contract —
yield only selections that beat the incumbent.

The important change is what happens at the cap. Today a search that exhausts its budget without
finding anything returns `NoBnbSolution::RoundLimit`, and the caller falls back to single random
draw, which in this matrix produced a package costing 189690 against a reachable 46550. A
depth-first search has a funded selection within its first few dozen expansions, so the budget
should return the best found rather than nothing. That alone converts every scale failure in this
matrix into a usable answer.

Consider also exposing a wall-clock deadline as an alternative to the round cap. A round budget is
not comparable across engines and is not what a wallet constrains; `bench.py --deadline-us` exists
to measure that framing.

## 5. What must not change

- `BnbMetric` stays as-is: `score`, `bound`, `drain` over `&SelectionView`. The rewrite is
  traversal only, so existing metrics keep working and the changeless-specific bound is unaffected.
- `run_bnb` and `bnb_solutions` signatures.
- The ancestor accounting. `ancestor_bump` over the union, the private/shared split, and the
  `AncestorToBump` contract are all validated against Bitcoin Core's post-discount combined bump on
  every run in this matrix and must stay bit-identical.

## 6. Correctness strategy

Treat "the search returns no solution" as the failure mode to hunt, because it is silent — a caller
cannot distinguish "infeasible" from "my pruning was wrong". Concretely:

- **Exhaustive oracle on small fixtures.** For candidate counts up to about 20, enumerate all
  subsets, score each with the metric under test, and assert the search finds a solution whenever
  one exists and matches the optimum's score. `bench.py run --oracle` does this for eight fixtures
  and catches exactly this class of bug: a search that misses a *one-input* solution at depth 1 is
  unambiguously a bad prune, not an ordering artefact, and no amount of budget will hide it.
- **Proptest against brute force**, as `tests/ancestor.rs` already does, extended to assert
  existence as well as optimality.
- **Differential test against the current traversal.** On every fixture, both searches must return
  the same score. Different selections at equal score are fine; different scores are not.
- **Regression test for the dedup rule** — a fixture with two equal-value equal-weight candidates
  where only one drags in an ancestor, asserting both remain reachable.

## 7. Staging

1. In-place DFS with only the existing bound-vs-incumbent prune. Expect correct answers and a large
   drop in memory; node counts may rise. Gate on the oracle and differential tests before looking
   at any timing.
2. Add the monotone value prune. This is where node counts should fall below the current traversal.
3. Return best-found at the budget cap.
4. Optimise the step: incremental cache add/sub on the hot path, no allocation per node.

Measure after each stage with `bench.py compare-revs --a <before> --b <after>`, which runs both
revisions interleaved on identical fixtures and reports behaviour before speed. Watch three
numbers: solutions lost, round counts, and peak RSS. **A stage that loses a solution is a
regression regardless of what it does to timings** — that is the one bar to hold.

## 8. Expected outcome, and how to know if it is wrong

Success looks like: no solution lost on any fixture, node counts at or below the current traversal
once the value prune is in, peak RSS in single-digit megabytes, and the 500–2000 candidate fixtures
returning answers instead of nothing.

The plan is wrong if stage 2 does not bring node counts down. That would mean the monotone value
prune is not doing the structural cutting this diagnosis assumes, and the remaining gap is bound
quality rather than search order — in which case the effort belongs in the metric's `bound`, not
in the traversal.

## 9. Measured: what an actual DFS attempt did

An in-place DFS exists on coin-select's `experiment/bnb-dfs` branch (`2398ab2`). Benchmarked against
the pinned best-first revision and against best-first with pool sampling
([`SAMPLING-PLAN.md`](SAMPLING-PLAN.md)), wallet track, all 42 fixtures, scored by the harness's
shared fee model:

| arm | total package fee | vs best-first | improved | regressed | fell back to SRD | peak RSS |
| --- | --- | --- | --- | --- | --- | --- |
| best-first (pinned) | 1,480,114 | — | — | — | 0 | 286 MB |
| **DFS** (`2398ab2`) | 4,202,996 | **+184%** | 3 | 15 | **8** | **3.6 MB** |
| best-first + sampling | 1,374,136 | **-7.2%** | 8 | 3 | 0 | 286 MB |

**The memory prediction was right, emphatically.** DFS peaks at 3.6 MB where both best-first arms
reach 286 MB — a factor of 80, and it is flat in the candidate count rather than growing with it.
Sampling does nothing for this, because it bounds the pool and not the frontier.

**Where DFS reaches the large fixtures, it is much better than either alternative**, on fee and on
time at once:

| fixture | best-first | DFS | best-first + sampling |
| --- | --- | --- | --- |
| `wallet_mixed_1000` | 97,230 | **56,633** | 85,910 |
| `wallet_mixed_2000` | 196,970 | **97,653** | 188,760 |
| `wallet_mixed_2000` wall clock | 1,065 ms | **400 ms** | 1,687 ms |

**But its ancestor handling is broken, and that dominates the total.** On eight fixtures the DFS
search returns nothing and the wallet falls back to single random draw, which is what the +184%
is: `shared_ancestry_2000` costs 1,614,450 against best-first's 301,090. Every failure is a
dense-ancestry family — `shared_ancestry_*`, `nested_ancestry_200`, `subsidizing_ancestry_*`.

The failures are not all unsoundness. Given 500,000,000 rounds and 30 seconds instead of the default
budget, `nested_ancestry_20` solves and exhausts at 131,250 rounds where best-first needs **30**, and
`no_ancestry_100` at 8,380,234 rounds against best-first's 2,827. So on those the tree is explored
correctly and the traversal is simply thousands of times more expensive. `shared_ancestry_100` and
`private_ancestry_50` still return nothing after 95-180 million rounds, which is a different problem.

### What this says about the plan

Stage 2 of §7 — the monotone value prune — is the stage this attempt is missing, and §8's
falsification test reads on it directly: node counts must come *down*, and here they went up by
three to four orders of magnitude on the fixtures that regressed. The bound, not the traversal, is
where the remaining work is; the ordering change alone buys memory and costs search efficiency.

The two designs are complementary rather than competing, which is what
[`SAMPLING-PLAN.md`](SAMPLING-PLAN.md) claims and this measures: sampling is the safe win available
today (-7.2%, no fallbacks, three regressions of at most 1.6%), DFS is the only thing that fixes the
memory ceiling, and neither substitutes for the other.
