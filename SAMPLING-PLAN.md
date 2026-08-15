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
4. Repeat from 2 with a fresh sample until the round budget is spent.
5. Return the best scoring selection across the failed full search and every sample.

`max_n` and the sample count are both derived from the round budget rather than asked of the caller
(§3, §5). Measured on the wallet track: **11 of 42 fixtures improve, none regress**, total long-term
fee falls 5.4%, and median wall clock stays at or below the uncapped search.

## 2. Why it works, and why the trigger matters more than the pool size

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
impl<'a> CoinSelector<'a> {
    /// Run `run_bnb`, and if it runs out of rounds, retry on sampled subsets of the pool.
    ///
    /// Returns the best selection found across the failed full search and every sample. Only
    /// returns `Err` if none of them found a solution.
    pub fn run_bnb_sampled<M: BnbMetric>(
        &self,
        metric: M,
        max_rounds: usize,
        rng: impl FnMut() -> u64,
    ) -> Result<CoinSelector<'a>, NoBnbSolution>;
}
```

**No tuning parameters.** Pool size and sample count are both derived from `max_rounds` at runtime
(§5), which is a budget the caller already passes to `run_bnb`. That is not merely tidier — the
measurements say neither can be a caller constant:

- **Sample count cannot be derived from pool size.** The quantity linking them is rounds-to-exhaust,
  and at a fixed pool of 50 it ranges from 224 rounds (`shared_ancestry_1000`) to over 2,000,000
  (`subsidizing_ancestry_200`). Four orders of magnitude at one pool size, because cost depends on
  bound quality under ancestry rather than on `n`. Any closed-form `samples = f(max_n)` is wrong by
  ~10,000x on some input.
- **Pool size carries a constraint the caller cannot evaluate.** It must exceed the greedy prefix
  length or every sample is the identical pool — `wallet_mixed_2000` at `max_n=50` has a mean
  pairwise overlap of 1.000 and never improves. `greedy_len` is computed inside the callee, so
  exposing `max_n` asks the caller for a number only the callee can validate.
- **The best fixed pool size moves with the budget.** At 100,000 rounds a pool of 50 beats a pool of
  100 by 7.1 points; at 1,000,000 rounds they are within 0.3. A caller who hard-codes one is
  hard-coding an assumption about the other.

Three things this shape still commits to:

- **`rng` is the caller's.** The crate is `no_std` and has no entropy source; `select_srd` already
  takes `impl FnMut() -> u64` and this matches it. It also keeps the result reproducible, which
  matters for a wallet that wants to explain its own selection.
- **Sampling is opt-in and named.** A caller who wants a deterministic exhaustive answer keeps
  `run_bnb`. Nothing about existing behaviour changes.
- **The failed full search's result is not discarded**, it competes as one more sample. Without
  this the fallback could return something worse than what the caller already had.

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
The funding prefix, by contrast, is drawn **per sample**: it is jittered rather than strictly greedy
(§7), which costs one short pass per sample and both improves the fee and removes a fixed point.

**Keeping a funding prefix is load-bearing, not an optimisation.** It is what guarantees the
sampled pool can still fund the target. Without it a random cut can leave a pool that cannot reach
the value target at all, which converts a slow answer into no answer — a strictly worse failure than
the one being fixed. What the prefix must *not* be is a uniformly random funding set, which is 4-10x
larger and defeats the cap entirely (§7).

Per sample the work is one `Bitset` of bans plus a partial Fisher-Yates over the non-kept indices;
draw only the `n - max_n` positions actually needed rather than shuffling the whole vector.

### `max_n` must have headroom above the prefix

`no_ancestry_2000` and `shared_ancestry_2000` never improve at `max_n` of 25-50 because their greedy
prefixes are 82 and 91 inputs: everything outside gets banned, the pool *is* the prefix, and there is
nothing to search over. So `max_n` cannot be a constant chosen without reference to the problem.

This is the same diversity failure as §6, reached from the other direction: those fixtures'
samples have a mean pairwise overlap of **1.000** — every sample is the identical pool — so the 50
draws collapse to one no matter how good the sampler is. Headroom is not a tuning nicety, it is what
gives sampling anything to sample.

The derived schedule in §5 handles this without a rule: it probes upward from 25 and keeps the
largest size a sample can still exhaust, so a wallet holding 2000 dust UTXOs with a 94-input greedy
prefix lands on a pool of 100 or 200 rather than a degenerate 50. That is why `wallet_mixed_2000` and
`shared_ancestry_2000` improve under the derived schedule (-4.3% and -2.2%) and not at all under a
fixed `max_n=50`.

## 5. Budget: how both parameters get derived

**Sample count is not a parameter.** Draw samples until the round budget is spent, with a per-sample
cap of `budget / 20` so no single sample can eat the phase. That adapts to the four-orders-of-
magnitude spread in rounds-to-exhaust that no formula can predict.

**Pool size is not a parameter either.** Probe upward — 25, 50, 100, 200 — while a single sample
still exhausts inside a fraction of the budget, then spend everything left sampling at the largest
size that did. Rounds needed grows roughly tenfold per +25 candidates, so all the probes below the
largest affordable size together cost a fraction of it (`shared_ancestry_500`: 21 + 964 + 6,983 +
33,845 = 41,813 rounds against 33,845 for a pool of 100 alone, 1.24x; `wallet_mixed_500`, 1.09x),
and each probe's answer competes as a sample regardless, so none is wasted.

The stopping rule is load-bearing. Escalating blindly and splitting the budget geometrically across
every size up to the candidate count scores **-7.8%** against a hand-tuned constant's -10.2%,
because a pool too large to exhaust contributes nothing and still consumes whatever it is given.
Stopping at the largest exhaustible size turns that into **-10.6%**.

Measured against hand-tuned constants, three seeds, ten budget-limited fixtures:

| | derived (no parameters) | best constant | second constant |
| --- | --- | --- | --- |
| 100,000-round budget | **-10.6%**, 632 ms | -10.2% (`n=50, k=50`), 717 ms | -3.2% (`n=100, k=30`) |
| 1,000,000-round budget | **-4.7%**, 5814 ms | -4.2% (`n=50, k=50`), 6775 ms | -3.9% (`n=100, k=30`) |

The derived schedule beats the best hand-tuned constant at both budgets *and* is faster, because it
stops paying for pools it cannot finish. Note also that the two constants swap places between the
two budgets, which is the case against exposing either as a caller parameter.

Over the full 42-fixture wallet track it improves **11 fixtures, regresses 0**, cuts total long-term
fee by **5.4%**, and leaves median wall clock slightly *below* the uncapped baseline — against 8
improved and -3.9% for the tuned two-parameter version.

**Sampling is a tight-budget feature.** Its mean gain falls from -10.6% at 100,000 rounds to -4.7%
at 1,000,000, because a larger budget lets the full search exhaust on more fixtures and the fallback
stops triggering at all. That is the behaviour to want, and another reason the budget is the right
and only knob.

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

**Ancestry-aware sampling was measured and lost. Sample uniformly.** Random banning can drop the
second coin sharing an already-bumped ancestor, which looks like something worth fixing. Two biased
policies were tried against uniform over five draw seeds (finding 7): keeping whole ancestor
clusters and preferring clusters the greedy prefix already draws from (-6.0%), and preferring
candidates that drag in nothing new (-6.2%), against uniform's **-7.4%**.

The mechanism is the part worth carrying into any future attempt. Biasing collapses the mean
pairwise overlap between samples from 0.23 to 0.96 on `shared_ancestry_200`, and shrinks the
candidates any sample ever sees from 200 to 85 — fifty samples become approximately one.
**Sampling's value is cross-draw diversity, not per-cut quality**, so any heuristic that constrains
which candidates can survive is paying in the currency the whole design runs on.

The one variant that is not disqualified is *unbiased* cluster granularity — keep siblings together,
but give every cluster an equal chance of being dropped. It matches uniform's diversity (mean
Jaccard 0.594 against 0.593) and its quality (-11.4% against -10.9%), and wins clearly on one
fixture (`subsidizing_ancestry_200`, -15.6% against -10.3%). Ship uniform; treat this as an optional
refinement to revisit only with a fixture set that has more shared-ancestry structure than this one.

## 7. Privacy: the prefix is a fixed point, and it should be jittered

Keeping the *strict* greedy prefix puts the same candidates in every sample of every transaction.
That is a deterministic fixed point in an otherwise randomized procedure, and it deserves checking.

**Randomize it, but not naively.** Replacing the greedy prefix with a uniformly random funding set
destroys the method: random coins are worse value-per-weight, so a random funding set needs 80-530
candidates where greedy needs 10-47. The pool blows past `max_n`, no sample can exhaust, and every
fixture falls back to exactly the uncapped answer — `+0.0%` on all ten budget-limited fixtures.

What works is jittering *within* the greedy ordering: take each next coin uniformly from the best
four remaining by value-per-weight rather than always the very best. The funding set stays the same
size, so pools stay at `max_n`, but its membership varies per sample.

| prefix | mean fee | pool size | fixtures improved | total fee |
| --- | --- | --- | --- | --- |
| strict greedy | -10.5% | `max_n` | 11 of 42 | -5.4% |
| **jittered (top-4)** | **-12.6%** | `max_n` | **11 of 42** | **-6.5%** |
| uniform random | +0.0% | 80-530 | 0 of 42 | +0.0% |

**Jittering is free — it improves the fee.** Loosening the prefix lets samples reach selections the
strict prefix crowded out: `wallet_mixed_500` goes from -23.2% to -31.0%, `wallet_mixed_1000` from
-8.7% to -13.5%. Make it the default.

### But the prefix is not what concentrates selections

Measuring per-coin selection frequency over twelve independent draws says the fixed point is mostly
not the sampler's doing:

| fixture | tx size | coins in **all 12** txs, strict | jittered |
| --- | --- | --- | --- |
| `shared_ancestry_500` | 23 | 18 | **13** |
| `wallet_mixed_500` | 27 | 23 | 21 |
| `wallet_mixed_1000` | 47 | 42 | 42 |

Jittering helps where there is slack between the prefix length and the transaction size, and not at
all where there is none. That is the real constraint: when a transaction needs 47 inputs and
`LowestFee` is minimizing fee, the answer *is* "the 47 best coins by value-per-weight", whatever the
sampler does. The overlap between consecutive transactions is a property of the objective, not of
pool construction, and no change to this design fixes it. A wallet that wants uncorrelated
selections has to be willing to spend worse coins, which costs fee — a policy decision belonging
above this layer, not a sampler tweak.

### Buying entropy on the exhausting cases does not work

Sampling only fires when the search runs out of budget, so the 30 of 42 fixtures that exhaust get
none of it — they return one proven-optimal selection, every time. The obvious repair is to return a
random selection from among those scoring within some epsilon of the optimum, paying a bounded fee
for entropy. Measured on all 30, it does not pay:

| tolerance | fixtures gaining any alternative | mean entropy |
| --- | --- | --- |
| exact ties (free) | 9 of 30 | 0.52 bits |
| +0.1% | **0 of 30** | 0.52 bits |
| +1% | **0 of 30** | 0.52 bits |
| +5% | 6 of 30 | 1.02 bits |

**Nothing lives between the optimum and +1%.** The reason is structural: for a selection with
change, `LowestFee`'s score is `implied_fee(weight) + spend_fee`, which depends on the selection's
*weight*, not on which coins are in it. The score is therefore quantized in steps of roughly one
input's fee — about 680 sat at 10 sat/vb — and that step is larger than 1% of nearly every optimum
here. Only at 5%, costing 146-3279 sat, does the next quantum come into range, and even then on just
six fixtures.

So the exchange rate is bad: about one bit for five percent of the fee. What is worth taking is the
free part — 9 of 30 fixtures have more than one selection at *exactly* the optimum (up to 7 on
`wallet_mixed_100`), and picking among those costs nothing. It is also cheap to find: the 1-swap
neighbourhood of the optimum matched exhaustive enumeration exactly on all nine fixtures small
enough to brute force, so an implementation needs `O(n * inputs)` rescoring rather than a modified
search. But 0.52 bits is a rounding error, not a privacy feature.

The conclusion is the same one the previous section reaches from the other direction: under a
fee-minimizing objective, selection entropy and fee are directly opposed, and the price is bad. A
wallet that wants uncorrelated selections needs a different objective, not better tie-breaking
inside this one. (Measured on the wallet track, where change absorbs the value slack. A changeless
score varies with coin *values* rather than only weight, so its near-optimal set may be denser —
untested.)

### Sampling is still a large privacy improvement over what it replaces

The comparison that matters is against today's behaviour, which is a fully deterministic search:
one selection, always, for a given UTXO set and target.

| | distinct selections in 12 draws | candidates ever used |
| --- | --- | --- |
| today (deterministic) | 1 | 44 |
| sampled | **11.3** | **68** |

So the feature moves selection from "identical every time" to "almost always different", and widens
the set of coins that can appear by half. The greedy fixed point removes some of that gain; jittering
gives part of it back at negative cost.

## 8. Correctness strategy

The failure mode to hunt is a sampled pool that cannot fund the target, because it is silent — the
caller sees `Err` and cannot tell "infeasible" from "the sampler cut badly".

- **Assert every sampled pool is fundable.** A debug assertion that the kept set still meets the
  target, on every sample. If this ever fires, the prefix-keeping invariant is broken.
- **Never worse than the input.** The returned selection must score at least as well as the failed
  full search's own result. This is what makes the fallback safe to enable by default in a wallet,
  and it is cheap to assert.
- **Determinism.** Same `rng` seed, same pool, same answer. Property-test it; a fallback a wallet
  cannot reproduce is a fallback it cannot explain to a user. The derived schedule must be
  deterministic too: the probe sequence depends only on `max_rounds` and the problem.
- **Differential against the full search on small pools.** Where `n <= max_n`, sampling must be a
  no-op returning exactly `run_bnb`'s answer. This is the regression test for the trigger logic, and
  it is the one that would have caught the unconditional-capping regression.
- **Diversity, as a debug-only statistic.** Mean pairwise overlap between samples predicted every
  quality result in §6 and §4, in both directions: overlap 0.96 explained why biased sampling lost,
  and overlap 1.000 explained which fixtures never improve. It is the cheapest early warning that a
  change to the sampler has quietly broken it, and much easier to attribute than a fee delta.

## 9. Staging

1. `sample_pool` plus the fundability and no-op assertions. No API surface yet.
2. `run_bnb_sampled` sampling at one fixed internal size, drawing until the budget is spent. Expect
   the trigger logic to be exercised and no fixture to regress.
3. The upward probe of §5, which is where the parameters disappear and where the large-pool fixtures
   start improving.
4. The metric gating in §6, and the jittered prefix from §7.

Measure after each stage with `bench.py run --tracks wallet --escalate` followed by `bench.py
report`, which verifies every selection is a valid package before scoring it. Watch four numbers:
fixtures regressed, wall clock, solutions lost, and the cross-draw overlap statistic. **A stage that
regresses any fixture is a regression regardless of its mean** — the whole claim of this design is
that it is free when it does not help.

## 10. Expected outcome, and how to know if it is wrong

Success looks like: no fixture regressed, the eleven budget-limited fixtures improved by roughly what
finding 7 reports, wall clock at or below the unsampled search, and small pools bit-identical to
`run_bnb`.

Two things would falsify the design, and both are already partly measured:

**If the upward probe does not beat a fixed internal pool size**, the escalation machinery is
unjustified and stage 2 is the whole feature. Current evidence says it does beat it — -10.6% against
-10.2% at a 100,000-round budget and -4.7% against -4.2% at 1,000,000, faster in both cases, and 11
fixtures improved against 8 — but the margin over the *best* constant is small, and the honest
reading is that escalation mostly buys robustness across problem shapes rather than raw quality. If
a future fixture set shows one constant dominating everywhere, take the constant.

**If sampling several pools does not beat searching one smaller pool**, the randomness, seeding and
reproducibility machinery can all be deleted. This one is settled: the deterministic cut is measured
as `worst`, which takes the best candidates by value-per-weight and returns **-0.3%** against
uniform sampling's -7.4%. The ordering across every policy tried follows cross-draw diversity rather
than the plausibility of any single cut, so if a change ever makes sampling stop working, check the
overlap statistic before anything else.
