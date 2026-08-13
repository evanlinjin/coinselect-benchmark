# Findings

A snapshot of what the checked-in fixtures show. Regenerate with `python3 bench.py all --oracle`;
`results/SUMMARY.md` is the machine-written report and `results/results.csv` the full matrix.

- Bitcoin Core `9be056a8a72b624dae9623b2f7bded92c2a21c91` (v31.1)
- coin-select `b2f98ab852e0425494d53f7260c4aa82f6c0830d` (PR #64 head)
- 29 fixtures (7 families x 4 sizes, plus the smoke fixture), both tracks, 100,000-node budget
- Recorded on Linux 7.1.7 x86-64, 24 cores, GCC 15.2.0 / rustc 1.97.1

Read these as observations about two engines that answer different questions. On the `kernel`
track coin-select minimises fee *by definition*, so "coin-select's package is cheaper" restates
its objective; the load-bearing comparisons there are search effort and the oracle checks.

## 1. The two engines charge for ancestors differently, and it changes the answer

This is the substantive result, and it is not a search-efficiency question.

coin-select charges `max(0, feerate x union_weight - union_fee)`: it nets the whole ancestor union
in one go, so an ancestor paying above the target rate subsidises one paying below it. Core runs
`node::MiniMiner`, which builds a mock block template and asks what the miner would *not* already
have taken: an ancestor that clears the target feerate on its own gets mined, and its surplus is
then unavailable to subsidise anything.

In the `subsidizing_ancestry` family (and in the `smoke` fixture, built the same way) this splits
the two engines apart completely. coin-select charges a bump of **0** where Core charges a real
one, and in **6 of 58 runs** its selection does not leave enough child fee to cover what Core's
mini-miner says the still-unmined ancestors need:

| fixture | track | child surplus over its own feerate | union bump (what coin-select charges) | combined bump (what Core's mini-miner charges) |
| --- | --- | --- | --- | --- |
| `smoke` | kernel | 520 | 0 | 3600 |
| `subsidizing_ancestry_20` | kernel | 3 | 0 | 2826 |
| `subsidizing_ancestry_20` | wallet | 0 | 0 | 5004 |
| `subsidizing_ancestry_100` | kernel | 127 | 0 | 4140 |
| `subsidizing_ancestry_200` | kernel | 8 | 0 | 3537 |
| `subsidizing_ancestry_200` | wallet | 0 | 0 | 3537 |

Both views are internally consistent. coin-select's transaction does reach the target feerate *as
a package* — the harness verifies that for every selection, and it holds. But a miner selecting by
ancestor-set score does not evaluate the package as a whole: it takes the overpaying ancestor on
its own and then judges what is left. Under that rule these packages are underfunded, and the
transaction will not confirm as quickly as the target feerate implies.

The asymmetry is one-directional across the whole matrix: on the 13 selections where the two
figures differ, Core's combined bump is always the **larger** one. coin-select never charges more
for ancestry than Core does, and sometimes charges materially less.

Worth raising on PR #64. The branch's own docs anticipate the opposite direction — "deficits are
computed against the full ancestor set and may **over**estimate what Bitcoin Core would charge" —
and this is the case where the union netting underestimates instead.

## 2. Core discounts shared ancestry too late to act on it

Core charges each UTXO the full individual bump fee of the transaction it sits on *during* the
search, and refunds the overlap only once a result has been chosen (`bump_fee_group_discount`).
The search therefore optimises a waste figure it later revises.

The exhaustive oracle catches the consequence. Of the 8 fixtures small enough to brute force,
`SelectCoinsBnB` fails to find the least-waste in-window selection on **3** — `nested_ancestry_20`,
`shared_ancestry_20` and `subsidizing_ancestry_20` — and all three have a non-empty ancestor union.
It finds the optimum on every fixture without one. On `shared_ancestry_20` the gap is large: waste
5544 for the selection it returned against 2046 for the best in-window selection, and the better
answer uses 9 inputs where Core took 4.

The `adversarial_shared` family shows the extreme form. One fat underpaying ancestor hosts a block
of small coins; charged the whole bump each, every one of them has negative effective value and
Core drops them from the BnB pool before the search starts. coin-select's union accounting sees
that taking several of them pays the bump once, and finds packages costing 4648 against Core's
7342 at n=100.

## 3. Search effort: opposite shapes

| | coin-select | Bitcoin Core |
| --- | --- | --- |
| kernel, median wall clock | 6399 us | 691 us |
| kernel, budget exhausted | 2 of 29 fixtures | **21 of 29** |
| kernel, median cost per node | ~2180 ns/round | ~7 ns/node |
| wallet, median wall clock | 425 us | 1375 us |
| wallet, budget exhausted | 1 of 29 fixtures | **18 of 29** |

Core's depth-first search is roughly 300x cheaper per node, and spends that speed running out its
100,000-node budget on essentially every fixture with 50 or more candidates. coin-select's
priority-queue search with the `LowestFee` bound prunes hard enough to exhaust the tree in a few
thousand rounds on 27 of 29 fixtures, but each round costs about a microsecond — it clones a
selector, evaluates a bound, and pushes onto a heap.

Neither number is a verdict on its own. Core finishing "fast" usually means it stopped early with
whatever it had; coin-select finishing "slow" usually means it proved it had the best answer.

## 4. coin-select's branch and bound can blow its budget on 20 candidates

`nested_ancestry_20` — twenty candidates, nine unconfirmed ancestors in a shared, three-deep
graph — exhausts 100,000 rounds and returns **no solution** on the kernel track, while the
exhaustive oracle confirms a changeless solution exists. Core solves the same fixture in 966
nodes.

The likely cause is visible in the branch's own source: `Changeless::change_unavoidable` gives up
its prune outright when `problem.has_ancestors()`, and `LowestFee::bound` swaps to the relaxed
`bound_with_ancestors`, which never returns `None`. Both are deliberate and both are sound — but
together they remove nearly all pruning from `Changeless<LowestFee>` exactly when ancestry is
present. `shared_ancestry_200` hits the same wall on both tracks (620 ms, budget exhausted).

This is the sharpest actionable result for the branch: the ancestor-aware path is not merely
slower per node, it can fail to answer a twenty-coin problem.

## 5. Outcomes, scored on both objectives

Scoring each engine's selection on *both* metrics — the harness computes Core's waste formula for
coin-select's selections and package fee for Core's — the picture is balanced rather than
one-sided:

| track | coin-select cheaper package | lower waste: coin-select | lower waste: Core | tie |
| --- | --- | --- | --- | --- |
| kernel | 24 of 26 | 11 | 13 | 2 |
| wallet | 28 of 29 | 9 | 19 | 1 |

Each engine wins its own objective most of the time, which is what should happen. The notable part
is that coin-select's selections also beat Core on Core's own waste metric in 11 of 26 kernel
fixtures and 9 of 29 wallet fixtures, without optimising for it — the ancestor-aware effective
values it searches with are simply better informed.

Read the fee column with care. Core's portfolio minimises waste, and its knapsack and
single-random-draw paths deliberately aim for a privacy-friendly change amount rather than the
smallest fee, so it is not trying to win that column. The one fixture Core wins outright,
`shared_ancestry_200`, is the one where coin-select hit its round budget and fell back to a much
worse selection (189690 against 46550).

The harness's reimplementation of Core's waste formula agrees with the waste Core itself reports
on all 57 of its own selections, which is what makes the cross-scoring trustworthy.

## Verification

Every selection from both engines was re-derived from the fixture: each package reaches the target
feerate once its ancestor union is counted, each stays inside `max_weight`, and each runner's own
bump-fee figures match the harness's independent reimplementation of Core's mini-miner. The two
exceptions are both `wallet_mixed_50`, 10 satoshis short, which is the documented legacy-input
empty-witness gap in Core's fee model and not a selection error.
