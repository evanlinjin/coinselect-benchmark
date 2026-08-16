# Findings

What the checked-in fixtures show, from a full run of this harness. Regenerate with
`python3 bench.py all --oracle --warmup 2 --repeat 9`; `results/SUMMARY.md` is the machine-written
report and `results/results.csv` the full matrix behind everything below.

- Bitcoin Core `9be056a8a72b624dae9623b2f7bded92c2a21c91` (v31.1), coin-selection algorithms
  unmodified apart from the benchmark hooks in `patches/` (a node counter and an optional
  wall-clock deadline, neither active in this run's default node-budget mode)
- coin-select `9c40ae23aa9386d4dd3e5ac4491e2645f6e3f396` ([PR #73][pr73]) — depth-first branch and
  bound, ancestor-aware selection, the changeless metrics removed
- 42 fixtures: 8 families x 20/50/100/200, three shapes also at 500/1000/2000, plus the smoke
  fixture; one track, 100,000-round budget
- 2 warm-up runs and 9 measured runs per case, median reported
- Linux 7.1.7 x86-64, 24 cores, GCC 15.2.0 `-O3` / rustc 1.97.1 `--release`

The two engines answer different questions — Core minimises waste across a portfolio and
deliberately aims for a privacy-friendly change amount, coin-select minimises long-term fee — so
every quality comparison below is scored by the harness from the fixture, with one fee model,
applied to both engines' selections.

[`ARCHIVED-FINDINGS.md`](ARCHIVED-FINDINGS.md) holds results this harness measured but can no longer
reproduce, with the commit and pins to reproduce them from history.

## 1. The two engines agree on what ancestry costs

Both fixture adapters are handed the same ancestor set — the transactions that still need bumping at
the target feerate, which is what coin-select's `AncestorToBump` means and what Core's
`node::MiniMiner` leaves unmined. Given that set, **coin-select's union bump and Core's
post-discount combined bump are identical on all 84 runs in the matrix**, and every selection from
both engines reaches the target feerate once its ancestor union is counted.

That is a positive result: netting weight and fee across the ancestor union reproduces Core's
`combined bump = summed individual bumps - bump_fee_group_discount` exactly, without a
post-selection correction step.

Both `genfixtures.py --check` and the Core runner enforce that the ancestor set really is the one
still requiring a bump, so this is a measurement rather than an assumption.

## 2. Depth-first ends the memory problem outright

| | coin-select | Bitcoin Core |
| --- | --- | --- |
| median wall clock | 1075 us | 1179 us |
| budget exhausted | 16 of 42 | 35 of 42 |
| returned no solution | **0 of 42** | 0 of 42 |
| peak RSS | **2.6 - 3.5 MB** | ~19 MB (process baseline) |

Peak RSS is flat at three megabytes across the whole matrix, from the 8-candidate smoke fixture to
2000 candidates. The previous best-first traversal ran from 2.9 MB to 23 MB at the same round cap,
and given a wall-clock budget instead its frontier reached **20 GB on a 500-candidate problem** — it
kept every shallow node alive, because a search over a bound that rises with depth never finishes a
level and so never discards one. Depth-first carries one path, so there is no frontier to grow.
This was the motivating problem for [`DFS-PLAN.md`](DFS-PLAN.md), and it is solved.

Core's figure is process baseline rather than search cost — its search also carries one path. The
two are not comparable; what matters is that coin-select's is no longer unbounded.

## 3. On large pools depth-first is a large win, on one family a large loss

Wallet-track package fee against the previous best-first revision ([PR #70][pr70]), same fixtures,
same 100,000-round budget:

| | package fee |
| --- | --- |
| total across the matrix | **-5.94%** |
| unchanged | 32 of 42 |
| cheaper | 3 |
| dearer | 7 |

The three improvements are the large pools, and they are not marginal:

| fixture | best-first | depth-first | |
| --- | --- | --- | --- |
| `wallet_mixed_500` | 42050 | **19960** | -52.5% |
| `wallet_mixed_2000` | 196970 | **97653** | -50.4% |
| `wallet_mixed_1000` | 97230 | **56633** | -41.8% |

**Five of the seven regressions are the budget, not the search.** Give both engines an equal *wall
clock* with the round cap lifted and they converge:

| fixture | converges at | |
| --- | --- | --- |
| `high_feerate_200` | 100 ms | identical, both exhausted |
| `shared_ancestry_100` | 100 ms | identical, both exhausted |
| `no_ancestry_500` | 1 s | identical at 16226, both exhausted |
| `no_ancestry_1000` | 1 s | 30462 against best-first's 30463 — depth-first one sat *cheaper* |
| `nested_ancestry_200` | 2 s | identical, after 3,145,352 rounds against best-first's 23,217 |

A depth-first round is a much cheaper unit than a queue pop, so a matrix giving each 100,000 hands
depth-first several times less work. **Round counts are not comparable across this repin.**
(`no_ancestry_1000` is a separate small puzzle: both traversals report the tree exhausted and they
disagree by one sat, so one of the two bounds is unsound at the margin. Unresolved; f32 in the bound
is the suspicion.)

**Two do not converge at any budget tried, and both are `subsidizing_ancestry`:**

| | best-first | depth-first | |
| --- | --- | --- | --- |
| **`subsidizing_ancestry_50`** — 50 candidates, 0.131 BTC target, 10 sat/vB | | | |
| fee the child pays | 4508 | 11332 | **2.51x** |
| package fee | 24500 | 47520 | 1.94x |
| inputs / change | 5 / 370545 | 6 / 4747 | |
| search | exhausted in **55,737 rounds** | 36.6M rounds in 10 s, **not exhausted** | |
| **`subsidizing_ancestry_100`** — neither exhausts | | | |
| fee the child pays | 18925 | 30140 | **1.59x** |
| package fee | 31493 | 81050 | 2.57x |

Best-first proves the optimum on `_50` in under sixty thousand rounds; depth-first does six hundred
times that work and is still short. This is not budget starvation — its answer is byte-identical at
100 ms, 1 s and 10 s, so it is stuck rather than slow. In absolute terms the wallet pays 6824 sat
more on a 0.131 BTC send, two and a half times the fee. It is the clearest open problem in this
matrix, and a regression a reviewer should weigh against the large-pool wins.

[`ANCESTOR-BOUND-PLAN.md`](ANCESTOR-BOUND-PLAN.md) named `subsidizing_ancestry_50` and `_100` as its
sharpest targets, and **the ceiling it proposes has already been built and measured — it does not
fix them.** It was a byte-identical no-op on all 42 wallet fixtures under both traversals, because
`LowestFee` never consults it: its only call site was the changeless window cut, which went with the
changeless metrics. It converted `_50` on the retired kernel track only. Wiring it into `LowestFee`
instead is unsound as described — an upper bound on the bump cannot raise a lower bound on the fee,
and the branches where it could tighten are the ones whose surplus term is already zero. See that
plan's §9 and §10. **These two fixtures have no fix in hand**, and what defeats depth-first here is
not ancestor-bound looseness.

## 4. Outcomes against Core

| | coin-select | Bitcoin Core |
| --- | --- | --- |
| cheaper package | **38 of 42** | 3 of 42 |
| lower waste | 16 of 42 | **23 of 42** |

Each engine wins its own objective more often than not, which is what should happen. Read the fee
column with care: Core's portfolio minimises waste, and its knapsack and single-random-draw paths
deliberately aim for a privacy-friendly change amount rather than the smallest fee, so it is not
trying to win that column.

The harness's reimplementation of Core's waste formula agrees with the waste Core itself reports on
every one of its own selections, which is what makes the cross-scoring trustworthy.

## 5. Capping the pool still helps, but the headroom has shrunk

When the search runs out of budget, retrying it on randomly sampled subsets of the candidates and
keeping the best answer — `bench.py run --escalate` — was worth **-6.5%** total package fee against
the best-first traversal, improving 11 fixtures and regressing none.

Against depth-first the headroom is smaller, because depth-first already solves the large pools that
sampling was rescuing. The design, the measurements behind it, and the things that do *not* work are
in [`SAMPLING-PLAN.md`](SAMPLING-PLAN.md); its numbers were taken against best-first and are
labelled as such. **Re-measuring it against this pin has not been done** and is the obvious next
step.

## What this does not answer

Nothing here measures address-grouped selection, Core's per-output-type pass, or behaviour on a
mempool containing transactions outside the fixture's ancestor set.

Since [PR #73][pr73] removes the changeless metrics there is no changeless pairing left, so this
harness no longer isolates Core's `SelectCoinsBnB`. What that costs is recorded in
[`ARCHIVED-FINDINGS.md`](ARCHIVED-FINDINGS.md): run alone, Core's branch and bound cannot see a
selection whose coins share an unconfirmed parent, and the wallet track hides it because the rest of
Core's portfolio recovers.

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

[pr73]: https://github.com/bitcoindevkit/coin-select/pull/73
[pr70]: https://github.com/bitcoindevkit/coin-select/pull/70
