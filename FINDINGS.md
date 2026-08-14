# Findings

What the checked-in fixtures show, from a full run of this harness. Regenerate with
`python3 bench.py all --oracle --warmup 2 --repeat 9`; `results/SUMMARY.md` is the machine-written
report and `results/results.csv` the full matrix behind everything below.

- Bitcoin Core `9be056a8a72b624dae9623b2f7bded92c2a21c91` (v31.1), coin-selection algorithms
  unmodified apart from the benchmark hooks in `patches/` (a node counter and an optional
  wall-clock deadline, neither active in this run's default node-budget mode)
- coin-select `91f5cfeb1163f87a27059adbbe1de6af8afbb08b` ([PR #70][branch]) — ancestor-aware
  selection, Bitcoin Core's incumbent-free prunes, and a greedy incumbent seeded before the search
- 42 fixtures: 8 families x 20/50/100/200, three shapes also at 500/1000/2000, plus the smoke
  fixture; three tracks, 100,000-node budget
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
post-discount combined bump are identical on all 252 runs in the matrix**, and every selection
from both engines reaches the target feerate once its ancestor union is counted.

That is a positive result: netting weight and fee across the ancestor union reproduces Core's
`combined bump = summed individual bumps - bump_fee_group_discount` exactly, without a
post-selection correction step.

Both `genfixtures.py --check` and the Core runner enforce that the ancestor set really is the
one still requiring a bump, so this is a measurement rather than an assumption; see
[the fixture schema](fixtures/README.md#schema) for what that means and why it matters.

## 2. Core cannot act on the discount during the search, and it costs real solutions

Core charges each UTXO the full individual bump fee of the transaction it sits on, baked into its
effective value *before* the search starts. Two coins on the same unconfirmed parent are each
charged for that parent in full. The overlap comes back only once a result has been chosen, as
`bump_fee_group_discount` — too late for the search to have used it.

The `smoke` fixture shows the sharpest form. `SelectCoinsBnB` gives up after 62 nodes with **no
solution**, while coin-select returns a five-input selection that the exhaustive oracle confirms
is the least-waste one available — waste 24460, matching the oracle exactly:

| | |
| --- | --- |
| Core's `selection_target` | 300540 |
| effective value the search sees | 298000 — below the target, so the branch is pruned |
| shared-ancestry discount for that set | 2700 (`c000` and `c002` both pay for parent `sh`) |
| effective value after the discount | 300700 — inside the window, waste 24460 |

Core is not choosing a worse selection here; it is structurally unable to see this one.

Across the eight fixtures small enough to brute force, `SelectCoinsBnB` fails to reach the
least-waste in-window selection on four, and every one of them has a non-empty ancestor union. It
finds the optimum on every fixture without one. **coin-select reaches the optimum of its own
objective on every one of the eight.**

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
| kernel, median wall clock | 3300 us | 722 us |
| kernel, budget exhausted | 13 of 42 | **32 of 42** |
| kernel, returned no solution | **11 of 42** | 1 of 42 |
| kernel, median cost per node | ~530-1280 ns/round | **~6 ns/node** |
| wallet, median wall clock | 1821 us | 1517 us |
| wallet, budget exhausted | 12 of 42 | 25 of 42 |
| wallet, returned no solution | **0 of 42** | 0 of 42 |

Those counts are dominated by the thousand-candidate fixtures added below; restricted to the
20-200 range coin-select exhausts the budget on 4 of 33 and fails on 2, against Core's 23 and 1.

Core's depth-first search is roughly 100-200x cheaper per node and spends that speed running out
its 100,000-node budget on essentially every fixture with 50 or more candidates. coin-select's
priority-queue search prunes hard enough to exhaust the tree in a few thousand rounds on nearly
every fixture, at roughly half a microsecond to a microsecond and a quarter per round.

Per-node cost splits cleanly by whether ancestry is present (kernel track, ns/round):

| n | no ancestry | with ancestry |
| --- | --- | --- |
| 50 | 530 | 597 |
| 100 | 531 | 871 |
| 200 | 651 | 1281 |

Neither number is a verdict on its own. Core finishing "fast" usually means it stopped early with
whatever it had; coin-select finishing "slow" usually means it proved it had the best answer.

**Memory is the clearest cost.** Core's depth-first search carries one path, so its peak RSS is
flat process baseline (~19 MB) on every fixture. coin-select's priority queue holds a selection
cache per live branch — running aggregates plus per-ancestor refcount arrays — and peak RSS runs
from 2.6 MB up to **286 MB**. That is the price of making per-node evaluation O(1): state that used
to be recomputed on demand is now carried, per branch, for every branch in the queue.

## 4. What still exhausts the budget — size, under either metric

At wallet scale (20-200 candidates) four kernel-track fixtures hit the 100,000-round cap and two
return nothing, both 200-candidate dense-ancestry cases.

**Every remaining failure is the changeless metric.** Bare `LowestFee` now solves all 42 fixtures
on both tracks that use it, including every 2000-candidate case: a greedy incumbent is seeded
before the search, and a greedy prefix is itself a valid `LowestFee` solution. The eleven failures
left are all `LowestFeeChangeless` on the kernel track — `no_ancestry_500/1000/2000`,
`shared_ancestry_200/500/1000/2000`, `subsidizing_ancestry_200`, `wallet_mixed_500/1000/2000`.

That split is not incidental. A greedy prefix taken in descending value-per-weight overshoots the
target, so `LowestFee` wants a change output and the changeless metric rejects it — at every prefix
length. The changeless objective has no cheap greedy seed, so on a large pool it starts with no
incumbent and never finds one. Seeding fixes exactly the metric it can seed.

What the seed recovers is visible on the wallet track, which previously fell back to single random
draw: on `no_ancestry_500` that fallback returned a **260-input** selection where the seeded search
returns **23 inputs** scoring 17190.

### Time does not buy its way out

Giving the search a wall-clock budget instead of a round budget, with the round cap lifted, shows
how far from the boundary these cases are:

| fixture (kernel) | 1 second | 21 seconds |
| --- | --- | --- |
| `no_ancestry_500` | solved, 175,357 rounds | solved, same |
| `wallet_mixed_500` | no solution | **solved**, 727,006 rounds |
| `shared_ancestry_500` | no solution | no solution, 3.2M rounds |
| `no_ancestry_2000` | no solution | no solution, **20.6M rounds** |
| `shared_ancestry_2000` | no solution | no solution, 1.2M rounds |

One more fixture converts between one second and twenty-one. The rest do not, and
`no_ancestry_2000` gets through twenty million expansions without reaching a funded selection —
about a thousand times the default budget. This is not a case of the budget being set slightly too
low; the search is not converging on these inputs at all.

Extending the budget to **130 seconds** confirms it, and turns up something more serious than slow:

| fixture (kernel) | result | rounds | peak RSS |
| --- | --- | --- | --- |
| `shared_ancestry_500` | no solution | 18.6M | **17.0 GB** |
| `no_ancestry_2000` | no solution | 120.9M | **9.0 GB** |
| `shared_ancestry_2000` | no solution | 7.5M | **20.4 GB** |

120 million expansions on `no_ancestry_2000` — 1,200x the default budget — still with no funded
selection. Across 100,000 rounds, 1,000,000 rounds, 21 seconds and 130 seconds, exactly one
fixture ever converted.

**The memory ceiling is the harder limit.** Twenty gigabytes on a 500-candidate problem is not a
slow search, it is one that would exhaust any real machine before it gave up. It follows directly
from the traversal: the queue holds a selector and its selection cache per live branch, and a
best-first search over a bound that rises with depth keeps every shallow node alive, because it
never finishes a level. The earlier figures understated this — 88 MB, then 293 MB at the default
cap, looked like a tunable cost. Given room to run it is unbounded in the candidate count.

The default round cap is therefore doing double duty as a memory guard. It is worth keeping that
in mind before replacing it with a wall-clock budget: a time budget alone does not bound the
frontier.

`bench.py compare-revs` is the tool for attributing any further improvement — `results/compare/`
holds the runs that tracked this one.

## 5. Outcomes, scored on both objectives

Scoring each engine's selection on *both* metrics — the harness computes Core's waste formula for
coin-select's selections and package fee for Core's:

| track | coin-select cheaper package | lower waste: coin-select | lower waste: Core |
| --- | --- | --- | --- |
| kernel | 26 of 30 | 15 of 30 | 12 of 30 |
| changeful | 20 of 42 | 18 of 42 | 4 of 42 |
| wallet | 41 of 42 | 18 of 42 | 21 of 42 |

Each engine wins its own objective more often than not, which is what should happen. The part
worth noting is that coin-select's selections also beat Core on Core's own waste metric about half
the time without optimising for it — the ancestor-aware effective values it searches with are
simply better informed.

Read the fee column with care. Core's portfolio minimises waste, and its knapsack and
single-random-draw paths deliberately aim for a privacy-friendly change amount rather than the
smallest fee, so it is not trying to win that column. The median Core-to-coin-select package-fee
ratio is 1.32x on the kernel track, 1.00x on `changeful` (they tie on half the fixtures) and 1.47x
on `wallet`.

The harness's reimplementation of Core's waste formula agrees with the waste Core itself reports
on every one of its own selections, which is what makes the cross-scoring trustworthy.

## 6. The change-producing pair: `LowestFee` vs `CoinGrinder`

The kernel track pairs the two changeless searches. Core's counterpart to *bare* `LowestFee` is
`CoinGrinder`, and the `changeful` track pairs them. The result inverts the kernel track.

| | coin-select (`LowestFee`) | Bitcoin Core (`CoinGrinder`) |
| --- | --- | --- |
| median wall clock | 2008 us | **8.2 us** |
| median nodes | ~500 | **~24** |
| budget exhausted | 12 of 42 | **8 of 42** |
| returned no solution | **0 of 42** | **0 of 42** |
| lower waste | **18** of 42 | 4 of 42 |
| cheaper package | **20** of 42 | 5 of 42 |

`CoinGrinder` is two orders of magnitude faster and never fails — its objective is
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

The two engines have opposite failure shapes, and that is the durable observation here: on the
changeless pair coin-select explores far fewer nodes but each is expensive, while on the
change-producing pair Core explores far fewer nodes *and* they are cheap. The changeless and
change-producing metrics on the coin-select side now behave comparably to each other, which was not
true when the changeless case was expressed as a constraint wrapped around `LowestFee`.

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

[branch]: https://github.com/bitcoindevkit/coin-select/pull/70
