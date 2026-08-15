# Plan: pool sampling as a fallback in `bdk_coin_select`

A design for making "when the search runs out of budget, retry on random subsets of the pool" a
first-class part of the crate. Argued from finding 7 in [`FINDINGS.md`](FINDINGS.md); every number
below has a fixture behind it in `results/`.

This is complementary to [`DFS-PLAN.md`](DFS-PLAN.md), not an alternative. Sampling bounds the
**pool**; depth-first bounds the **frontier**. The 20 GB frontier in finding 4 is not something
sampling fixes, and the "budget spent without reaching a funded leaf" problem is not something
depth-first alone fixes on a 2000-candidate pool. They compose: a depth-first search over a sampled
pool is cheaper than either.

## 1. What is being proposed

Today `run_bnb` returns `Err(NoBnbSolution::RoundLimit)` when the budget runs out, and on a large
pool that is the common case. The caller's options are to give up or to fall back to something much
worse — in this matrix single random draw returned a 260-input selection where a real search
returns 23.

Instead, when the budget runs out:

1. Take the greedy prefix. Keep every candidate in it.
2. Ban candidates from the rest, uniformly at random, until at most `max_n` remain.
3. Run the same branch and bound on that pool.
4. Repeat from 2 with a fresh sample, sharing one round budget across samples.
5. Return the best scoring selection across the failed full search and every sample.

Measured on the wallet track at `max_n = 50` over 50 samples: 8 of 42 fixtures improve, by up to
34.3% of the long-term fee, **none regress**, and the worst-case slowdown is 1.6x.

## 2. Why it works, and why the trigger matters more than `max_n`

The failure this addresses is not that the tree is large. It is that a best-first search over a
depth-increasing bound expands every shallow prefix before descending, so on a 500+ candidate pool
the budget is gone before any funded leaf is reached, and the search returns its greedy seed
unimproved. Shrinking the pool to 50 does not make the search smarter; it makes the level it is
stuck on small enough to finish.

**Only cap a search that was going to fail.** Applying the cut unconditionally regresses 5 fixtures
by up to 6.1%, and the split has no exceptions in this matrix:

| the full search | capping does |
| --- | --- |
| exhausted the tree | **harm** — it already held the optimum, and the cut discards candidates the optimum needs |
| ran out of budget | **help** — it was returning nothing better than its greedy seed |

Candidate count is the wrong proxy: `subsidizing_ancestry_100` runs out of budget at n=100 while
`wallet_mixed_200` exhausts at n=200. The search already knows which case it is in — that is exactly
what `NoBnbSolution::RoundLimit` versus a returned solution distinguishes — so the trigger is free
and exact. Do not add a candidate-count threshold; it would misclassify both of those.

## 3. API

Keep the existing entry points untouched and add one that is explicit about being a fallback.

```rust
/// How to retry a branch and bound that runs out of budget.
#[derive(Debug, Clone, Copy)]
pub struct PoolSampling {
    /// Largest pool a retry may search. Must leave headroom above the greedy prefix length.
    pub max_n: usize,
    /// How many independent samples to draw. They share `max_rounds` between them.
    pub samples: usize,
}

impl<'a> CoinSelector<'a> {
    /// Run `run_bnb`, and if it runs out of rounds, retry on sampled subsets of the pool.
    ///
    /// Returns the best selection found across the failed full search and every sample. Only
    /// returns `Err` if none of them found a solution.
    pub fn run_bnb_sampled<M: BnbMetric>(
        &self,
        metric: M,
        max_rounds: usize,
        sampling: PoolSampling,
        rng: impl FnMut() -> u64,
    ) -> Result<CoinSelector<'a>, NoBnbSolution>;
}
```

Four things this shape is deliberately committing to:

- **`rng` is the caller's.** The crate is `no_std` and has no entropy source; `select_srd` already
  takes `impl FnMut() -> u64` and this matches it. It also keeps the result reproducible, which
  matters for a wallet that wants to explain its own selection.
- **Sampling is opt-in and named.** A caller who wants a deterministic exhaustive answer keeps
  `run_bnb`. Nothing about existing behaviour changes.
- **The failed full search's result is not discarded**, it competes as one more sample. Without
  this the fallback could return something worse than what the caller already had.
- **`max_rounds` is the total**, not per sample. See §5.

## 4. Building a sample

```rust
fn sample_pool<'a>(
    base: &CoinSelector<'a>,      // already sorted by descending value-pwu
    keep: &Bitset,                // indices the greedy prefix uses
    max_n: usize,
    rng: &mut impl FnMut() -> u64,
) -> CoinSelector<'a>
```

Sort once, outside the sample loop — `sort_candidates_by_descending_value_pwu` does not change
candidate indices, only iteration order, so a `Bitset` of kept indices stays valid across samples.
Compute the greedy prefix once as well; it is the same set for every sample, because the prefix is
the top of the value-pwu order and sampling only ever removes candidates below it.

**Keeping the greedy prefix is load-bearing, not an optimisation.** It is what guarantees the
sampled pool can still fund the target. Without it a random cut can leave a pool that cannot reach
the value target at all, which converts a slow answer into no answer — a strictly worse failure than
the one being fixed.

Per sample the work is one `Bitset` of bans plus a partial Fisher-Yates over the non-kept indices;
draw only the `n - max_n` positions actually needed rather than shuffling the whole vector.

### `max_n` must have headroom above the prefix

`no_ancestry_2000` and `shared_ancestry_2000` never improve at `max_n` of 25-50 because their greedy
prefixes are 82 and 91 inputs: everything outside gets banned, the pool *is* the prefix, and there is
nothing to search over. So `max_n` cannot be a constant chosen without reference to the problem.

Size it as `max(max_n, greedy_len * 2)` — or reject a `PoolSampling` whose `max_n` leaves no
headroom, which is more honest than silently searching a pool with no freedom in it. Whichever is
chosen, document it: a caller passing `max_n: 50` to a wallet holding 2000 dust UTXOs should not
silently get a no-op.

## 5. Budget

Samples share one round budget: `max_rounds / samples` each. This is the difference between an
honest measurement and a flattering one — giving each sample a fresh full budget produced better
numbers (10 fixtures improved, best -41.3%) at up to 9x the baseline wall clock, which is not a fair
comparison against a search that got one budget.

Under a shared budget the tuning is a clear inverted U:

| arm | mean | best | worst |
| --- | --- | --- | --- |
| `max_n=30, samples=50` | -5.6% | -26.0% | +0.0% |
| **`max_n=50, samples=50`** | **-7.2%** | **-34.3%** | **+0.0%** |
| `max_n=100, samples=5` | -5.2% | -36.0% | +0.0% |
| `max_n=100, samples=50` | -3.2% | -26.6% | +0.0% |

`max_n=100` gets worse as samples increase: 2,000 rounds cannot exhaust a 100-candidate pool, so each
sample degrades back to returning its own greedy seed and the extra samples buy nothing. **The pool
must be small enough that a sample finishes**, which is the single constraint tying `max_n` and
`samples` together. `max_n = 50, samples = 50` is the recommended default.

Stop early when a sample exhausts its subtree *and* fails to improve on the incumbent several times
running — but measure before adding that, since the per-sample cost at `max_n=50` is around 0.1 ms
and a stopping rule that saves 0.5 ms while losing a 30% fee improvement is a bad trade.

## 6. Interaction with the metrics

Everything above is measured on `LowestFee`. Two things need checking before it is offered for
`LowestFeeChangeless`:

- **The changeless metric may not tolerate sampling at all.** Its solutions are near-exact matches;
  removing 95% of the pool removes most of the combinations that could land inside a ~600-sat window.
  Sampling may simply find nothing, which is no worse than today's nothing, but the crate should not
  advertise a fallback that does not work.
- **The greedy prefix is not a valid changeless selection** (finding 4: 0 of 42 fixtures), so the
  "keep the prefix, guarantee feasibility" argument gives feasibility for funding but not for the
  metric. A changeless sample can return `None` where `LowestFee` would not.

Until both are measured, gate sampling to metrics that can seed a greedy incumbent, or document it
as best-effort and let the `Err` case stand.

**Ancestry is the other open question.** Random banning can drop the second coin sharing an
already-bumped ancestor, losing the discount that made the first one worth taking, and
`sort_candidates_by_descending_value_pwu` does not account for drag-in cost. The ancestry families
still improved here (`shared_ancestry_200` is the single largest win at -34.3%), so this is not
disqualifying — but an ancestry-aware sampler that biases toward coins sharing an already-kept
ancestor is the obvious next experiment, and it should be measured against uniform sampling rather
than assumed better.

## 7. Correctness strategy

The failure mode to hunt is a sampled pool that cannot fund the target, because it is silent — the
caller sees `Err` and cannot tell "infeasible" from "the sampler cut badly".

- **Assert every sampled pool is fundable.** A debug assertion that the kept set still meets the
  target, on every sample. If this ever fires, the prefix-keeping invariant is broken.
- **Never worse than the input.** The returned selection must score at least as well as the failed
  full search's own result. This is what makes the fallback safe to enable by default in a wallet,
  and it is cheap to assert.
- **Determinism.** Same `rng` seed, same pool, same answer. Property-test it; a fallback a wallet
  cannot reproduce is a fallback it cannot explain to a user.
- **Differential against the full search on small pools.** Where `n <= max_n`, sampling must be a
  no-op returning exactly `run_bnb`'s answer. This is the regression test for the trigger logic, and
  it is the one that would have caught the unconditional-capping regression.

## 8. Staging

1. `sample_pool` plus the fundability and no-op assertions. No API surface yet.
2. `run_bnb_sampled` with `samples = 1`. Expect the trigger logic to be exercised and no fixture to
   regress.
3. Shared budget across `samples > 1`. This is where the quality arrives.
4. `max_n` headroom rule, and the metric gating in §6.

Measure after each stage with `bench.py run --tracks wallet --max-n 50 --restarts 50` followed by
`bench.py report`, which verifies every selection is a valid package before scoring it. Watch three
numbers: fixtures regressed, wall clock, and solutions lost. **A stage that regresses any fixture is
a regression regardless of its mean** — the whole claim of this design is that it is free when it
does not help.

## 9. Expected outcome, and how to know if it is wrong

Success looks like: no fixture regressed, the eight budget-limited fixtures improved by roughly what
finding 7 reports, wall clock within 2x of the unsampled search, and small pools bit-identical to
`run_bnb`.

The plan is wrong if step 3 does not beat step 2 by a wide margin. That would mean the win is coming
from searching a smaller pool rather than from sampling several of them — in which case the honest
version is a single deterministic cut (take the best `max_n` by value-pwu), and all the machinery
for randomness, seeding and reproducibility can be deleted. The `max_n=100, samples=5` row hints the
margin is real but not enormous, so this is worth checking rather than assuming.
