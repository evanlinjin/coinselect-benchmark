# Plan: an ancestor-bump ceiling for `bdk_coin_select`

A design for adding an upper bound on the ancestor bump a descendant can still take on, mirroring
the floor `ancestor_bump_lower_bound` already tracks. Argued from measurements in this benchmark;
every number below has a fixture behind it in `results/`.

This is the piece both other plans turn out to need. [`DFS-PLAN.md`](DFS-PLAN.md) is blocked on it —
a depth-first search cannot tolerate the looseness the missing ceiling forces — and
[`SAMPLING-PLAN.md`](SAMPLING-PLAN.md) only papers over the same looseness by shrinking the pool.
Unlike either, this one helps the traversal that is shipped today.

## 1. Why — the bound is optimistic by construction, and only ancestry pays for it

`SelectionView` exposes two ancestor quantities:

```rust
ancestor_bump()              // what the current selection owes
ancestor_bump_lower_bound()  // the least any descendant of it could owe
```

The floor is `owed - private_reachable_surplus - shared_reachable_surplus`, saturating at zero: it
assumes a descendant picks up *every* overpaying ancestor still reachable. That is the correct
direction for admissibility — the bound must never exceed the true optimum — but it means the bound
credits surplus that no single descendant may actually be able to collect. `bound < best` then fires
rarely, and whole regions of the tree stay alive.

There is no ceiling. Nothing in the crate answers "how much *more* bump could a descendant drag in",
which is what a prune needs to rule a subtree out rather than in.

The cost is not spread evenly. It falls entirely on problems with unconfirmed ancestry:

| wallet track, DFS branch | fixtures failing |
| --- | --- |
| with ancestry | **8 of 8** (`shared_ancestry_100/200/500/1000/2000`, `nested_ancestry_50/200`, `subsidizing_ancestry_20`) |
| without ancestry | **0 of 9**, including `no_ancestry_2000` |

Two of those failures are at n=20 and n=50. Ancestry at every size, never size alone — which is the
signature of a bound problem rather than a scale one.

## 2. What this is *not*

**It is not that the DFS branch has a worse metric.** `LowestFee` is identical between
`experiment/bnb-dfs` (`2398ab2`) and the pinned revision, `bound_with_ancestors` included. The whole
diff is one added lookahead prune, and `e45bb58` lacks that prune too while still solving
`shared_ancestry_100` in 2,945 rounds where DFS fails at 100,000.

So the same bound succeeds under best-first and fails under depth-first. Best-first is *robust* to a
loose bound because ordering still steers it toward good nodes; depth-first commits to a subtree and
enumerates it. The looseness was always there — one traversal hides it and the other does not.

**It is not the kernel track's problem.** `2398ab2`'s `LowestFeeChangeless` is 81 lines against the
pinned revision's 154 and is missing the changeless window cut outright. Kernel-track DFS numbers say
nothing about traversal or about this bound; do not use them as evidence either way.

## 3. The quantity to add

Mirror the floor exactly:

```rust
/// Upper bound on the ancestor bump this branch or any descendant could owe.
pub fn ancestor_bump_upper_bound(&self) -> u64;
```

Where the floor subtracts the surplus reachable from undecided candidates, the ceiling adds the
*deficit* reachable from them — the bump that undecided candidates would bring if every one of them
were selected. The cache already holds the mirror-image state:

| already tracked, for the floor | the ceiling needs |
| --- | --- |
| `private_reachable_surplus` | `private_reachable_deficit` |
| `shared_reachable_surplus` | `shared_reachable_deficit` |
| `shared_reachable_refcounts` | reused unchanged |

`SelectionCache::ancestor_surplus` is `max(fee - weight * spwu, 0)`. The deficit is the same
expression with the sign flipped and the clamp on the other side: `max(weight * spwu - fee, 0)`.
Both are per-ancestor and both are already computed at exactly the sites the surplus is —
`add_reachable`/`sub_reachable` when a candidate becomes undecided or is decided, and the
select/deselect paths — so this is the same bookkeeping in the other direction, not a new traversal
of anything. It stays O(1) per node and needs no allocation beyond two `f64`s, because the refcount
vector that makes shared ancestors idempotent is already there.

**Saturation matters.** The floor clamps at zero because a bump is never negative. The ceiling has
no such natural cap, so it must saturate rather than wrap, and it must stay an upper bound under the
same `ancestor_fee_precision_slack` the floor already carries. Round the ceiling *up* wherever the
floor rounds down.

## 4. What it buys

Three call sites, in descending order of confidence:

1. **`LowestFeeChangeless::overshot_the_changeless_window`.** This is Bitcoin Core's defining
   `SelectCoinsBnB` cut, and the crate currently disables it whenever `problem().has_ancestors()`,
   with a comment saying exactly why: a later-dragged ancestor raises the bump and lowers the excess,
   so the excess is not monotone. A ceiling makes it monotone again — bound the excess drop by the
   most bump a descendant could still take on, and the window test applies. This is the one with a
   named, already-documented gap in the source.
2. **`LowestFee::bound_with_ancestors`, funded path.** It currently credits
   `ancestor_bump() - ancestor_bump_lower_bound()` as reachable surplus. With a ceiling the same
   expression can be tightened from the other end for branches where the bump can only grow.
3. **Depth-first traversal.** Not a call site so much as a precondition: [`DFS-PLAN.md`](DFS-PLAN.md)
   §3 predicted that without a structural cut "depth-first explores far more nodes than the queue
   does, not fewer", and the measurement is that it explores three to four orders of magnitude more.
   That prediction has been confirmed; this is the cut it was asking for.

## 5. Correctness strategy

The failure mode is a ceiling that is too low, which prunes a subtree containing the optimum and is
silent — the caller cannot distinguish it from infeasibility.

- **Assert the sandwich on every node.** `lower_bound <= ancestor_bump() <= upper_bound` must hold
  for the current selection, and for every descendant reached. A debug assertion at each
  `select`/`deselect` costs nothing in release and catches sign errors immediately.
- **Brute-force the ceiling on small fixtures.** For candidate counts up to 20, enumerate every
  subset, compute the true maximum bump over all supersets of each prefix, and assert the ceiling is
  at least that. `bench.py run --oracle` already enumerates these eight fixtures for scores; this is
  the same loop with a different accumulator.
- **Differential against the current traversal.** Every fixture must return the same *score* before
  and after. Different selections at equal score are fine; a different score is not, and a lost
  solution is a hard failure regardless of what it does to node counts.
- **Proptest the monotonicity claim directly**, since the window cut depends on it: for a random
  problem and a random prefix, no descendant's excess may fall below `excess - (ceiling - bump)`.

## 6. Staging

1. `ancestor_bump_upper_bound` plus the sandwich assertion and the brute-force oracle. No call site
   yet, so no behaviour change — this stage should be a strict no-op on every fixture, and
   `bench.py compare-revs` should report identical selections and identical round counts. If it does
   not, the bookkeeping is wrong.
2. Enable the changeless window cut for problems with ancestors. Expect kernel-track round counts to
   fall on the ancestry families and nothing to be lost.
3. Tighten `bound_with_ancestors`' funded path.
4. Only then revisit depth-first, with the cut it needs in place.

## 7. How to know if it is working, and when to stop

The cheap decisive test needs no DFS at all. Two kernel-track fixtures burn the whole 100,000-round
budget at sizes where their siblings finish, and both have ancestry:

| fixture | n | rounds | result |
| --- | --- | --- | --- |
| `subsidizing_ancestry_50` | 50 | **100,000** | solved, budget exhausted |
| `subsidizing_ancestry_100` | 100 | **100,000** | solved, budget exhausted |
| `shared_ancestry_200` | 200 | 100,000 | **no solution** |
| `no_ancestry_200` (control) | 200 | 24,024 | solved, tree exhausted |

`subsidizing_ancestry_50` is the sharpest target in the matrix: fifty candidates, and the search
still cannot finish the tree. Nothing about fifty candidates is hard; the ancestry accounting is what
keeps the branch alive. Stage 2 should bring those two round counts down by an order of magnitude,
and `shared_ancestry_200` should convert.

The wider bar is the eleven kernel-track fixtures that return no solution, and here the honest
scope has to be stated: **only 8 of the 11 have ancestry.** `no_ancestry_500`, `no_ancestry_1000`
and `no_ancestry_2000` fail with no unconfirmed parents at all, so no ancestor bound of any quality
will touch them — those are the pure traversal failure that [`DFS-PLAN.md`](DFS-PLAN.md) exists for.
A ceiling that converts all eight ancestry cases and none of the three others has done everything it
can, and the remaining three are the honest measure of how much of the problem is left over for
traversal work.

Success at every stage is any conversion without a single fixture losing a solution or scoring
worse.

## 8. Why this before the other two plans

Sampling is the better *product* change today — it is measured at -6.5% total package fee, no
regressions, and it needs nothing from the crate. But it treats the symptom: it shrinks the pool
until the loose bound stops mattering. Depth-first fixes the memory ceiling — 3.6 MB against 554 MB
at a one-second budget — but is unusable until something prunes for it.

A tighter ancestor bound is the only one of the three that improves the search that ships today,
and both other plans get easier behind it.

## 9. Implemented — what it did, and where this plan was wrong

Built on `experiment/bnb-greedy-seed` as `feat/ancestor-bump-ceiling`: `076e628` (the ceiling, a
strict no-op) and `8026867` (the window cut enabled with ancestors). `cargo test --all-features`
and `--no-default-features` both green.

### What it bought

The §7 headline prediction holds. `subsidizing_ancestry_50` — fifty candidates the search could not
finish — converts from burning its budget to **exhausting the tree in 66,922 rounds**. Other
kernel-track round counts fall sharply, with every score unchanged:

| fixture | before | after |
| --- | --- | --- |
| `subsidizing_ancestry_50` | 100,000, budget hit | **66,922, exhausted** |
| `adversarial_shared_50` | 3,353 | **217** |
| `high_feerate_50` | 1,641 | 499 |
| `nested_ancestry_100` | 4,218 | 1,756 |
| `high_feerate_100` | 9,320 | 4,972 |

### What it did not buy, and this is the important half

**Zero of the eleven no-solution kernel fixtures converted.** Not one. The gain is entirely on
fixtures that already solved. `shared_ancestry_200`, which §7 predicted would convert, does not.

**And it is a complete no-op on the wallet track** — 42 of 42 fixtures return byte-identical
selections and scores, because `LowestFee` never consults the ceiling. Everything above is
kernel-track only.

So the honest verdict is that a bump ceiling is a real but *narrow* win: it makes the changeless
search finish trees it could not finish, and it does not rescue a single case that was failing.
Whatever is defeating the eleven is not ancestor-bound looseness.

### Five things this plan got wrong

Recorded because they were found by building it, and the next person should not re-derive them:

1. **§4.2 (stage 3) is unsound as written.** `bound_with_ancestors` returns an admissible *lower*
   bound on the fee; an upper bound on the bump cannot raise it. The branches where a ceiling could
   plausibly tighten it are exactly those where `ancestor_bump_lower_bound() == ancestor_bump()`,
   so the surplus term is already zero and there is nothing to tighten. Stage 3 was not attempted
   and probably does not exist.
2. **§3's state model gets the granularity wrong.** `private_reachable_surplus` nets per *candidate
   group*, not per ancestor, because a candidate's private ancestors arrive all-or-nothing. The
   deficit must keep that granularity. The implementation folds both directions into one
   `Imbalance { surplus, deficit }` updated at each existing site so they cannot drift, which is
   better than the six mirrored edit sites §3 implies.
3. **§3 underestimates the float slack.** `ancestor_fee_precision_slack` is **0** below 2^24 sats,
   but `implied_fee_wu` is an f32 product plus a ceil, so `ancestor_bump` can sit ~3 sats above the
   exact f64 value even there. "Round up by one" is not enough; the implementation adds a
   documented 4-sat constant and clamps with `.max(ancestor_bump())`.
4. **§6 stage 1's `compare-revs` check is unnecessary.** Stage 1 is provably a no-op: the new
   surplus term is bit-identical to the old `ancestor_surplus` because IEEE negation is exact.
5. **§7's control was already corrected once** (an earlier draft invented an 8,127-round figure for
   `no_ancestry_200`; it is 24,024 and exhausts). The surviving prediction was half right:
   `subsidizing_ancestry_50` converts, `subsidizing_ancestry_100` and `shared_ancestry_200` do not.
