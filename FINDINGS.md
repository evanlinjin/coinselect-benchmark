# Findings

What the checked-in fixtures show, from a full run of this harness. Regenerate with
`python3 bench.py all --oracle --warmup 2 --repeat 9`; `results/SUMMARY.md` is the machine-written
report and `results/results.csv` the full matrix behind everything below.

- Bitcoin Core `9be056a8a72b624dae9623b2f7bded92c2a21c91` (v31.1), coin-selection algorithms
  unmodified apart from the node-count instrumentation in `patches/`
- coin-select `b2f98ab852e0425494d53f7260c4aa82f6c0830d` (PR #64 head)
- 29 fixtures (7 families x 4 sizes, plus the smoke fixture), both tracks, 100,000-node budget
- 2 warm-up runs and 9 measured runs per case, median reported
- Linux 7.1.7 x86-64, 24 cores, GCC 15.2.0 `-O3` / rustc 1.97.1 `--release`

Read these as observations about two engines answering different questions. On the `kernel` track
coin-select minimises fee *by definition*, so "coin-select's package is cheaper" restates its
objective rather than reporting a result; the load-bearing comparisons are search effort and the
oracle checks.

## 1. The two engines agree on what ancestry costs

Both fixture adapters are handed the same ancestor set — the transactions that still need bumping
at the target feerate, which is what coin-select's `AncestorToBump` means and what Core's
`node::MiniMiner` leaves unmined. Given that set, **coin-select's union bump and Core's
post-discount combined bump are identical on all 116 runs in the matrix**, and every selection
from both engines reaches the target feerate once its ancestor union is counted.

That is a positive result for PR #64: netting weight and fee across the ancestor union reproduces
Core's `combined bump = summed individual bumps - bump_fee_group_discount` exactly, without a
post-selection correction step.

It is worth being precise about what the ancestor list may contain, because getting this wrong
inverts the result. An ancestor whose package already clears the target feerate is not an
"ancestor to bump" — a miner takes it anyway — and feeding one to `SelectionProblem::new` credits
the child with a surplus nobody is waiting on, which makes coin-select undercharge. Both
`genfixtures.py --check` and the Core runner reject a fixture that lists one. An ancestor paying
far above the target rate on its own can still belong in the set if its package does not, which is
exactly what the `subsidizing_ancestry` family is built from.

## 2. Core cannot act on the discount during the search, and it costs real solutions

Core charges each UTXO the full individual bump fee of the transaction it sits on, baked into its
effective value *before* the search starts. Two coins on the same unconfirmed parent are each
charged for that parent in full. The overlap comes back only once a result has been chosen, as
`bump_fee_group_discount` — too late for the search to have used it.

The `smoke` fixture shows the sharpest form. `SelectCoinsBnB` gives up after 62 nodes with **no
solution**, while both coin-select and the exhaustive oracle return the same five-input selection
`{c000, c002, c004, c006, c007}`:

| | |
| --- | --- |
| Core's `selection_target` | 300540 |
| effective value the search sees | 298000 — below the target, so the branch is pruned |
| shared-ancestry discount for that set | 2700 (`c000` and `c002` both pay for parent `sh`) |
| effective value after the discount | 300700 — inside the window, waste 24460 |

Core is not choosing a worse selection here; it is structurally unable to see this one.

Across the eight fixtures small enough to brute force, `SelectCoinsBnB` fails to reach the
least-waste in-window selection on four, and every one of them has a non-empty ancestor union. It
finds the optimum on every fixture without one.

| fixture | waste Core returned | best in-window waste | inputs Core took | inputs in the optimum |
| --- | --- | --- | --- | --- |
| `smoke` | no solution | 24460 | 0 | 5 |
| `shared_ancestry_20` | 5544 | 2046 | 4 | 9 |
| `subsidizing_ancestry_20` | 25270 | 24675 | 10 | 16 |
| `nested_ancestry_20` | 16609 | 16024 | 12 | 11 |

`shared_ancestry_20` is the largest gap: Core leaves 63% of the achievable waste on the table,
because during the search each of those nine coins looked like it had to pay for the shared
ancestor by itself.

The `adversarial_shared` family is the same effect at scale. One fat underpaying ancestor hosts a
block of small coins; charged the whole bump each, every one of them has negative effective value
and Core drops them from the BnB pool before the search starts. coin-select's union accounting
sees that taking several of them pays the bump once, and finds packages costing 4648 against
Core's 7342 at n=100.

(The oracle enumerates every subset, including coins Core's positive-effective-value filter drops,
so "Core missed it" covers both the search and that filter. Both are part of how Core answers.)

## 3. coin-select pays for that in search cost, sometimes past its budget

| | coin-select | Bitcoin Core |
| --- | --- | --- |
| kernel, median wall clock | ~7000-8000 us | ~530-660 us |
| kernel, budget exhausted | **6 of 29** fixtures | 21 of 29 |
| kernel, returned no solution | **4 of 29** | 1 of 29 |
| kernel, median cost per node | ~1900 ns/round | ~7 ns/node |
| wallet, median wall clock | ~870-990 us | ~1150-1410 us |
| wallet, budget exhausted | 3 of 29 fixtures | 18 of 29 |

Wall-clock medians move about 15% between runs on this machine; the counts, the selections and
every derived figure are byte-identical run to run. Treat the times as orders of magnitude and the
counts as exact.

Core's depth-first search is roughly 280x cheaper per node and spends that speed running out its
100,000-node budget on essentially every fixture with 50 or more candidates. coin-select's
priority-queue search prunes hard enough to exhaust the tree in a few thousand rounds on most
fixtures, but each round costs about two microseconds — it clones a selector, evaluates a bound,
and pushes onto a heap.

The failures matter more than the medians. On `subsidizing_ancestry_20` — twenty candidates, six
unconfirmed ancestors — `Changeless<LowestFee>` burns all 100,000 rounds — about 180 ms — and returns
**no solution**, while the oracle confirms an eleven-input changeless solution exists and Core
answers in **52 nodes and a couple of microseconds**. `nested_ancestry_20` fails the same way, and
`shared_ancestry_200` and `subsidizing_ancestry_200` exhaust the budget after more than half a
second each.

The cause is visible in the branch's own source. `Changeless::change_unavoidable` gives up its
prune outright when `problem.has_ancestors()`, and `LowestFee::bound` swaps to the relaxed
`bound_with_ancestors`, which never returns `None`. Both are deliberate and both are sound — but
together they remove most of the pruning from `Changeless<LowestFee>` exactly when ancestry is
present. That is the sharpest actionable result for the branch: on the ancestor-aware path the
search is not merely slower per node, it can fail to answer a twenty-coin problem that Core
answers in microseconds.

Memory differs in kind as well as degree. Core's depth-first search carries one path, so its peak
RSS is flat process baseline (~17 MB) on every fixture. coin-select's priority queue holds a
`CoinSelector` per live branch, and peak RSS runs from 2.7 MB up to 28 MB.

## 4. Outcomes, scored on both objectives

Scoring each engine's selection on *both* metrics — the harness computes Core's waste formula for
coin-select's selections and package fee for Core's:

| track | coin-select cheaper package | lower waste: coin-select | lower waste: Core |
| --- | --- | --- | --- |
| kernel | 22 of 24 | 10 of 24 | 12 of 24 |
| wallet | 28 of 29 | 11 of 29 | 16 of 29 |

Each engine wins its own objective more often than not, which is what should happen. The part
worth noting is that coin-select's selections also beat Core on Core's own waste metric in 10 of
24 scoreable kernel fixtures and 11 of 29 wallet fixtures without optimising for it — the
ancestor-aware effective values it searches with are simply better informed.

Read the fee column with care. Core's portfolio minimises waste, and its knapsack and
single-random-draw paths deliberately aim for a privacy-friendly change amount rather than the
smallest fee, so it is not trying to win that column. The median Core-to-coin-select package-fee
ratio is 1.36x on the kernel track and 1.72x on the wallet track. The one fixture Core wins
outright is `shared_ancestry_200`, where coin-select hit its round budget and fell back.

The harness's reimplementation of Core's waste formula agrees with the waste Core itself reports
on every one of its own selections, which is what makes the cross-scoring trustworthy.

## Reading list for PR #64

1. **The bump arithmetic is right** (finding 1) — and the API contract that makes it right is that
   `AncestorToBump` receives only ancestors that still require bumping. That is load-bearing and
   currently only stated in prose; a caller that passes its whole unconfirmed ancestor graph will
   silently undercharge.
2. **The ancestor-aware search can run out of budget on twenty coins** (finding 3). Restoring some
   pruning to `Changeless<LowestFee>` when ancestors are present is where the headroom is.
3. **The in-search union is worth having** (finding 2): it finds selections Core's post-hoc
   discount structurally cannot reach.

## 6. Combining with the delta-aware branch (PR #53)

`bench.py compare-revs` A/Bs two coin-select revisions on these fixtures. Run against PR #64 head
versus [`feature/ancestor-aware-with-view`][withview], which rebases [PR #53][pr53]'s delta-aware
`SelectionView` onto it and extends the cache with ancestor aggregates:

| track | group | geomean | median | range |
| --- | --- | --- | --- | --- |
| kernel | no ancestry | 1.35x | 1.71x | 0.51-2.23x |
| kernel | **with ancestry** | **2.33x** | 2.31x | 1.43-3.79x |
| wallet | no ancestry | 2.08x | 2.02x | 1.56-2.95x |
| wallet | with ancestry | 1.84x | 1.76x | 0.71-3.92x |

**Selections are identical on all 58 fixture/track pairs**, as is solved/unsolved. On the cases
that actually hurt — n=200 and the budget-capped ones — it is consistently 2.3-3.3x:
`shared_ancestry_200` 751 to 255 ms, `subsidizing_ancestry_200` 635 to 195 ms,
`nested_ancestry_200` 172 to 53 ms. The ancestor share of per-node cost drops from 60-62% to
13-58%; at n=100 the ancestor path goes from 2531 to 999 ns/round.

Two things worth attention:

- **`Changeless::change_unavoidable` is gone**, on the stated grounds that the prune "is not
  generally sound". All four round-count differences are `no_ancestry` on the kernel track and all
  are upward — 152 to 587 on `no_ancestry_20`, +1% to +14% elsewhere — which is exactly where that
  prune used to be active, since #64 had already disabled it under ancestry. If the soundness
  concern holds this is a bug fix rather than a regression, but it implies #64's version was
  unsound for `!has_ancestors()`, and it is why `no_ancestry_20` ends up a net slowdown (0.51x)
  despite cheaper nodes.
- **Per-branch overhead grew.** The three cases that got slower have *identical* round counts, so
  it is pure setup cost: `SelectionCache` carries two `Vec<u32>` refcount arrays sized by ancestor
  count and is cloned per queued branch, so branch cloning went from O(n/64) words to
  O(n_ancestors) plus two allocations. It pays off whenever evaluation dominates and loses on
  searches of a few dozen nodes.

None of the nine budget-capped fixtures stops capping, and `nested_ancestry_20`,
`subsidizing_ancestry_20` and `subsidizing_ancestry_200` still return no solution on the kernel
track. This is a constant factor, not a pruning fix: finding 3's ordering stands, fix the bound
first and take this second.

Full output in `results/compare/`.

[pr53]: https://github.com/bitcoindevkit/coin-select/pull/53
[withview]: https://github.com/evanlinjin/coin-select/tree/feature/ancestor-aware-with-view

## What this does not answer

The kernel track puts both engines on the same problem and the same budget, but not on literally
the same objective — see the first entry under "Known limits" in the README for why that was left
alone rather than papered over with a hand-written metric. So "coin-select needs fewer nodes"
means "fewer nodes to answer its own question", not "strictly better pruning on identical input".
The oracle columns are what make that meaningful: both engines are checked against the optimum of
the question they were actually asking.

Nothing here measures address-grouped selection, Core's per-output-type pass, or behaviour on a
mempool containing transactions outside the fixture's ancestor set.

## Verification

Every selection from both engines was re-derived from the fixture and cross-checked against that
engine's own numbers: child weight against `CoinSelector::weight`, child fee against
`CoinSelector::fee`, the union bump against `CoinSelector::ancestor_bump`, the individual and
combined bump fees against an independent port of `node::MiniMiner`, waste against
`SelectionResult::RecalculateWaste`, and input weight against `SelectionResult::GetWeight`. Every
package reaches the target feerate once its ancestor union is counted, and every selection stays
inside `max_weight`. `bench.py report` exits non-zero if any of that fails; this run exits 0.
