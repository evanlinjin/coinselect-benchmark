# Findings

What the checked-in fixtures show, from a full run of this harness. Regenerate with
`python3 bench.py all --oracle --warmup 2 --repeat 9`; `results/SUMMARY.md` is the machine-written
report and `results/results.csv` the full matrix behind everything below.

- Bitcoin Core `9be056a8a72b624dae9623b2f7bded92c2a21c91` (v31.1), coin-selection algorithms
  unmodified apart from the node-count instrumentation in `patches/`
- coin-select `bdcb1f064cd20ab4d864e6f040f0d45a6fd5e8fc`
  ([`feature/ancestor-aware-with-view`][branch]) — ancestor-aware selection on the delta-aware
  branch-and-bound evaluator
- 33 fixtures (8 families x 4 sizes, plus the smoke fixture), three tracks, 100,000-node budget
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
post-discount combined bump are identical on all 198 runs in the matrix**, and every selection
from both engines reaches the target feerate once its ancestor union is counted.

That is a positive result: netting weight and fee across the ancestor union reproduces Core's
`combined bump = summed individual bumps - bump_fee_group_discount` exactly, without a
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
solution**, while coin-select returns a five-input selection that the exhaustive oracle confirms is
the least-waste one available — waste 24460, matching the oracle exactly:

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

## 3. Search effort: opposite shapes

| | coin-select | Bitcoin Core |
| --- | --- | --- |
| kernel, median wall clock | 2310 us | 599 us |
| kernel, budget exhausted | 6 of 33 | **23 of 33** |
| kernel, returned no solution | **4 of 33** | 1 of 33 |
| kernel, median cost per node | ~530-1400 ns/round | **~6 ns/node** |
| wallet, median wall clock | **547 us** | 1197 us |
| wallet, budget exhausted | 3 of 33 | 19 of 33 |

Core's depth-first search is roughly 100-200x cheaper per node and spends that speed running out
its 100,000-node budget on essentially every fixture with 50 or more candidates. coin-select's
priority-queue search prunes hard enough to exhaust the tree in a few thousand rounds on most
fixtures, at roughly half a microsecond to a microsecond and a half per round.

Per-node cost still splits cleanly by whether ancestry is present (kernel track, ns/round):

| n | no ancestry | with ancestry |
| --- | --- | --- |
| 50 | 535 | 645 |
| 100 | 534 | 1006 |
| 200 | 714 | 1390 |

Neither number is a verdict on its own. Core finishing "fast" usually means it stopped early with
whatever it had; coin-select finishing "slow" usually means it proved it had the best answer.

**Memory is the clearest cost.** Core's depth-first search carries one path, so its peak RSS is
flat process baseline (~19 MB) on every fixture. coin-select's priority queue holds a selection
cache per live branch — running aggregates plus per-ancestor refcount arrays — and peak RSS runs
from 2.6 MB up to **87 MB**. That is the price of making per-node evaluation O(1): state that used
to be recomputed on demand is now carried, per branch, for every branch in the queue.

## 4. coin-select's branch and bound can blow its budget on 20 candidates

`subsidizing_ancestry_20` — twenty candidates, six unconfirmed ancestors — burns all 100,000
rounds in 45 ms and returns **no solution**, while the oracle confirms an eleven-input changeless
solution exists and Core answers in **52 nodes and under 10 microseconds**. `nested_ancestry_20`
fails the same way (55 ms, oracle finds a thirteen-input solution, Core answers in 966 nodes).

Six kernel-track fixtures exhaust the budget and four return nothing. The cause is visible in the
branch's own source: `LowestFee::bound` swaps to the relaxed `bound_with_ancestors`, which never
returns `None`, and `Changeless` has no prune of its own to compensate. Together they remove most
of the pruning from `Changeless<LowestFee>` exactly when ancestry is present.

That is the sharpest actionable result: on the ancestor-aware path the search is not merely slower
per node, it can fail to answer a twenty-coin problem that Core answers in microseconds. It is a
bound problem, not a throughput problem — a faster node visit makes the failure arrive sooner, not
go away.

## 5. Outcomes, scored on both objectives

Scoring each engine's selection on *both* metrics — the harness computes Core's waste formula for
coin-select's selections and package fee for Core's:

| track | coin-select cheaper package | lower waste: coin-select | lower waste: Core |
| --- | --- | --- | --- |
| kernel | 25 of 28 | 13 of 28 | 12 of 28 |
| changeful | 15 of 32 | 15 of 32 | 0 of 32 |
| wallet | 31 of 33 | 14 of 33 | 16 of 33 |

Each engine wins its own objective more often than not, which is what should happen. The part
worth noting is that coin-select's selections also beat Core on Core's own waste metric about half
the time without optimising for it — the ancestor-aware effective values it searches with are
simply better informed.

Read the fee column with care. Core's portfolio minimises waste, and its knapsack and
single-random-draw paths deliberately aim for a privacy-friendly change amount rather than the
smallest fee, so it is not trying to win that column. The median Core-to-coin-select package-fee
ratio is 1.36x on the kernel track, 1.00x on `changeful` (they tie on half the fixtures) and 1.53x
on `wallet`.

The harness's reimplementation of Core's waste formula agrees with the waste Core itself reports
on every one of its own selections, which is what makes the cross-scoring trustworthy.

## 6. The change-producing pair: `LowestFee` vs `CoinGrinder`

`Changeless<LowestFee>` exists in the kernel track only to match Core's changeless
`SelectCoinsBnB`. Core's counterpart to *bare* `LowestFee` is `CoinGrinder`, and the `changeful`
track pairs them. The result inverts the kernel track.

| | coin-select (`LowestFee`) | Bitcoin Core (`CoinGrinder`) |
| --- | --- | --- |
| median wall clock | 441 us | **4.0 us** |
| median nodes | ~500 | **~24** |
| budget exhausted | 3 of 33 | **0 of 33** |
| returned no solution | 1 of 33 | **0 of 33** |
| lower waste | **15** of 32 | 0 of 32 |
| cheaper package | **15** of 32 | 1 of 32 |

`CoinGrinder` is ~100x faster, never exhausts its budget, and never fails — its objective is
minimum *selected input weight*, which is monotone as inputs are added and so bounds beautifully.
Node counts run 2 to 1582 against coin-select's 2 to 100000.

It also loses on quality every time the two disagree: 15-0 on Core's own waste metric, 15-1 on
package fee, the rest ties. Minimum weight is not minimum fee — `CoinGrinder` must fund
`target + change_target` and is indifferent to how far it overshoots, so it lands on much larger
packages. On `high_feerate_50` that is waste 38710 against 11854 and package fee 43640 against
17200, and this is inside the `> 3x long-term feerate` gate where Core actually reaches for it.

Read it as an objective difference, not a verdict: `CoinGrinder` is one member of a portfolio, and
`ChooseSelectionResult` picks the least-waste result across all four. Run alone it is being asked
a question it was not designed to answer alone — which is exactly the kernel-track caveat, pointed
the other way.

Two things worth carrying away. First, the two engines have opposite failure shapes: on the
changeless pair coin-select explores far fewer nodes but each is expensive, while on the
change-producing pair Core explores far fewer nodes *and* they are cheap. Second, bare `LowestFee`
is markedly healthier than `Changeless<LowestFee>` — 3 budget exhaustions against 6, one failure
against four. `Changeless<M>` constrains the same objective to a strict subset of selections while
delegating to the *unconstrained* inner bound, so it narrows the solution set without tightening
anything. Unless you specifically need a changeless transaction, bare `LowestFee` is both
better-scoring and better-behaved.

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

`bench.py compare-revs` A/Bs two coin-select revisions on these same fixtures if you want to
attribute a change to a particular commit; past runs are kept in `results/compare/`.

[branch]: https://github.com/evanlinjin/coin-select/tree/feature/ancestor-aware-with-view
