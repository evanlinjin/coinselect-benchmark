Draft, on top of #76 (which is on top of #75, on #73). One commit.

**Identical selections and identical round counts on all 42 benchmark fixtures.** This is a pure cost
reduction, not a change of answer — which is the property that should make it cheap to review.

## The problem

Branch and bound decides candidates in cursor order, so at a node with cursor *c*, every candidate at
position `0..c` in the candidate order is already decided — selected by an inclusion frame, or banned
by an exclusion one. Two hot paths ignored that and walked the decided prefix at every node.

`perf` on `wallet_mixed_2000`, which spends its whole budget:

| | share of runtime |
| --- | --- |
| `LowestFee::bound` | 58.5% |
| `BnbIter::exclusion_plan` | 16.7% |
| `Map::nth`, called by `exclusion_plan` | 16.7% |

**Over 90% of the search was walking the candidate order.** The visible symptom is a per-node cost
that grows with the pool:

| candidates | 50 | 200 | 500 | 1,000 | 2,000 |
| --- | --- | --- | --- | --- | --- |
| µs per round | 0.24 | 0.34 | 0.48 | 0.97 | 2.19 |

## The two fixes

**`exclusion_plan` re-walked the order.** It resumed with `candidates().skip(cursor + 1)`.
`candidates()` returns a `Map`, which has no `nth` override, so `Skip` advances it one element at a
time — O(cursor) per node. Added `candidates_from(from)`, which slices the order and iterates from
there.

**`unselected()` always started at the front.** Every metric query about still-undecided candidates
filtered through the decided prefix first. `best_undecided_value_pwu` is the clearest case: it is
*written* to scan only the run of candidates tying on the first undecided key, with a comment saying
the point is to make the query independent of pool size — and then reaching that first undecided
candidate cost O(depth) anyway.

`SelectionView` now carries `decided_before` and starts its scan there; `BnbIter` passes its cursor.
A `debug_assert` on every view construction checks the promise, and the debug test suite exercises
it.

This is deliberately **not** a general cursor on `CoinSelector`. Keeping it on the view means the
claim lives inside the search that maintains the invariant, rather than becoming something every
future caller of `select` / `ban` / `deselect` has to preserve. `decided_before` of 0 is always
correct, so nothing outside branch and bound has to know it exists.

## Measured

42 fixtures, 100,000-round budget, 5 runs after 2 warm-ups, median.

| fixture | before | after | |
| --- | --- | --- | --- |
| `no_ancestry_2000` | 257.2 ms | 20.9 ms | **12.3x** |
| `wallet_mixed_2000` | 212.5 ms | 22.9 ms | **9.3x** |
| `shared_ancestry_2000` | 120.3 ms | 23.5 ms | 5.1x |
| `no_ancestry_1000` | 100.8 ms | 20.7 ms | 4.9x |
| `wallet_mixed_1000` | 108.1 ms | 22.0 ms | 4.9x |
| `no_ancestry_500` | 70.7 ms | 20.7 ms | 3.4x |
| `wallet_mixed_500` | 53.4 ms | 21.2 ms | 2.5x |
| `shared_ancestry_1000` | 56.4 ms | 23.4 ms | 2.4x |

Geometric mean **1.59x** across all 42, median 1.43x.

The intended result shows in the shape more than the size: every budget-limited fixture now finishes
100,000 rounds in **21–25 ms regardless of pool size**, where before it ran from 28 ms to 257 ms.
Per-node cost is flat in the pool.

## A dead end, recorded so nobody repeats it

The first hypothesis was the greedy fill inside `LowestFee::bound`, which re-derives a funded
selection from scratch at every node — genuinely O(pool) work, and the obvious thing to attack.
Stubbing the loop out (unsound, purely to price it) showed it is worth **5.3x on `no_ancestry_2000`
and 1.0x on everything else**: every fixture with unconfirmed ancestors takes the
`bound_with_ancestors` path, which never runs that loop. Worth pricing before building.

## Test plan

`cargo test`, `cargo test --release`, `cargo clippy --all-features` and a `--no-default-features`
build all pass. The debug suite exercises the new `debug_assert`. Behavioural equivalence is checked
directly: [coinselect-benchmark](https://github.com/evanlinjin/coinselect-benchmark) compares
selections and round counts against the parent commit on all 42 fixtures and finds no difference.
