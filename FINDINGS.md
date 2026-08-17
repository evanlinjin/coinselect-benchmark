# Findings

What the checked-in fixtures show, from a full run of this harness. Regenerate with
`python3 bench.py all --oracle --warmup 2 --repeat 9`; `results/SUMMARY.md` is the machine-written
report and `results/results.csv` the full matrix behind everything below.

- Bitcoin Core `9be056a8a72b624dae9623b2f7bded92c2a21c91` (v31.1), coin-selection algorithms
  unmodified apart from the benchmark hooks in `patches/` (a node counter and an optional
  wall-clock deadline, neither active in this run's default node-budget mode)
- coin-select `ecdbbc93cf8e029f3716f4f8b0b6c42aa965dcd0` ([evanlinjin#5][ev5]) — iterative deepening
  on the bound, on by default where a problem has unconfirmed ancestors, on top of
  [evanlinjin#4][ev4]'s flat per-node cost, [PR #76][pr76]'s ancestry-aware second greedy seed,
  [PR #75][pr75]'s sparsely stored ancestor sets, and [PR #73][pr73]'s depth-first branch and bound
  with the changeless metrics removed.

  **The last two are unmerged drafts, and pinning them is deliberate**: this matrix is the evidence
  for them, so it is run against them. #75 and #76 move no row of it at all — all 84 are identical
  across the #73, #75 and #76 pins in every column but wall clock — and what they buy shows up only
  in finding 6. evanlinjin#4 likewise changes no answer, only the cost of reaching it. evanlinjin#5
  is the one that moves results, and finding 3 is the diagnosis it came from
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

[`STRATEGIES.md`](STRATEGIES.md) lists every fixture Core still wins — none on this matrix at this
budget, three on the 20,000-candidate tier — with the decomposition of each and what to try.

[`EXPERIMENTS.md`](EXPERIMENTS.md) is the other half of the picture: this file says what the **pinned**
revision does, that one logs what is being tried to move it. Two of those attempts are now open as
stacked draft PRs and change several conclusions below — each is cross-referenced where it lands.

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
| budget exhausted | 13 of 42 | 35 of 42 |
| returned no solution | **0 of 42** | 0 of 42 |
| peak RSS | **2.7 - 3.4 MB** | ~19 MB (process baseline) |

(Median wall clock is 695 us against 1,413 us, but that column does not reproduce — see the note
under "At a glance" in `results/SUMMARY.md` — so it is not the point being made here.)

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
plan's §9 and §10. What defeats depth-first here is not ancestor-bound looseness — and the thing
that does fix both fixtures is pool sampling, which is finding 5.

### What does defeat it, measured

Three measurements on `subsidizing_ancestry_50`, in order.

**The bound is sound.** Cut the pool to 20 candidates keeping the optimal five, and depth-first
finds that optimum and exhausts the tree, agreeing with the brute-force oracle — 14,443 rounds
against best-first's 765. It is not pruning the answer away.

**The tree explodes with the pool, for depth-first only.** Same fixture, pool grown from 20 to 50
with the optimal five always present. Both traversals return a child fee of 4508 wherever they
exhaust:

| candidates | best-first | depth-first |
| --- | --- | --- |
| 20 | 93 | 557 |
| 25 | 223 | 3,389 |
| 30 | 411 | 6,073 |
| 35 | 4,248 | 492,419 |
| 40 | 6,518 | 1,096,424 |
| 45 | 37,683 | 37.4M, **not exhausted** (fee 11194) |
| 50 | 55,737 | 36.5M, **not exhausted** (fee 11332) |

Best-first grows 600x across that range; depth-first grows 67,000x and breaks between 40 and 45.

**The incumbent stalls.** Depth-first starts from the greedy seed, which scores exactly 13,370 here
(`--seed-probe` confirms it), improves once to 11,912 before 100,000 rounds, and then does not
improve again across 40M more. Every prune it makes is against an incumbent 2.3x worse than the
optimum's 5088, and the set of nodes whose bound beats 11,912 is enormous. Best-first is not smarter
about the bound — it pops in bound order, so it walks the optimal region first and is pruning
against a near-final incumbent almost immediately.

So the lever is **incumbent quality and dive order**, not the bound. Restricting the pool confirms
it from the other side, and finding 5 shows it is not a curiosity: sampling recovers this fixture's
optimum exactly.

### An ancestry-aware branching order does not fix it

The obvious repair is to stop branching in an ancestry-blind order: sort by
`(value - the candidate's own ancestor bump) / weight` instead of `value / weight`. Measured, on a
patched crate whose control run is byte-identical to the pin on all 42 fixtures:

| | rounds | total fee the child pays |
| --- | --- | --- |
| `value / weight` (the pin) | — | 1,149,154 |
| `(value - own bump) / weight` | mostly *more* | 1,158,448 (**+0.81%**) |

Every fixture that exhausts returns the same selection under both orders, so the bound stays
admissible; two budget-limited fixtures get worse. On `subsidizing_ancestry_50` nothing moves at
all: 7.18M rounds becomes 7.25M, and the answer is unchanged.

**The reason is worth recording, because it generalises.** The new key does reorder candidates — 17
of 50 change rank, some by 425% — but every one of those changes happens far down the order, among
small coins whose bump is comparable to their value. The top is untouched:

| rank | coin | value | own bump |
| --- | --- | --- | --- |
| 0 | `c036` | 4,809,618 | 0 |
| 1 | `c044` | 4,678,368 | 6,144 |
| 2 | `c009` | 4,674,449 | 3,636 |
| 3 | `c035` | 3,615,368 | 138 |

To demote `c044` below `c035` the key would have to charge it 1,063,000 sat. Its parent owes 6,144.
**Ancestor bumps are three orders of magnitude too small to reorder the top of a value-per-weight
sort**, which is where the greedy prefix and the first dive come from.

That also disposes of the dynamic version — re-keying a candidate whenever a shared parent gets paid
for. Re-keying only ever *reduces* a candidate's charge, by at most its own bump, so it moves the
order strictly less than the static key does. The largest bump anywhere in this fixture is 21,258.

The conclusion is not that the order should be ancestry-aware *here*. It is that **no per-candidate
key can express this fixture**: the optimum is "avoid `c044` and `c009`", which is a property of the
set, not a ranking of coins. (Finding 6 qualifies this, and only for one regime. On a
200,000-candidate pool the same key recovers 91% of what coin-select loses to Core — [PR #76][pr76]
adopts it there as a second greedy seed — because the bump is finally large relative to the value
gaps between adjacent coins rather than three orders of magnitude too small. At 20,000 candidates it
is already back to changing nothing. The key is worth what ancestry costs relative to what the
ordering is otherwise sorting on.) Only the bound sees sets. Note also that the depth-first traversal already
consults the bound where it cheaply can — `descend()` evaluates both children and takes the better
one — so the remaining gap is node *expansion* order, which is what best-first buys with its
frontier. Iterative deepening on the bound is the standard way to buy it back at depth-first memory.

**That has since been tested, it works, and it is in this pin.** Deepening turns this fixture's
47,520 into 24,500 — past Core's 29,690 — and is worth -6.63% of total package fee across the
matrix. The diagnosis above is what it was built from, so it is kept in full even though the
numbers quoted in it describe the traversal before the fix: the 11,912-against-5,088 stall is why
[evanlinjin#5][ev5] exists. [`EXPERIMENTS.md`](EXPERIMENTS.md) attempt 2 has the measurements, and
what it costs on the three large mixed pools where it loses.

## 4. Outcomes against Core

| | coin-select | Bitcoin Core |
| --- | --- | --- |
| cheaper package | **41 of 42** | 0 of 42 |
| lower waste | 19 of 42 | **20 of 42** |

**Core no longer wins the fee column anywhere**, and the fixture coin-select does not win is not a
loss: on `high_feerate_20` the oracle enumerates all 2^20 subsets and coin-select returns the best
one with the tree exhausted, while Core reaches a different selection costing exactly the same. It
is a tie at a proven optimum.

At the [#76][pr76] pin this read 38 to 3. The three Core took — `nested_ancestry_200`,
`subsidizing_ancestry_100` and `subsidizing_ancestry_50` — are the three finding 3 diagnoses, and
[evanlinjin#5][ev5] is what turned them over.

Each engine wins its own objective more often than not, which is what should happen. Read the fee
column with care: Core's portfolio minimises waste, and its knapsack and single-random-draw paths
deliberately aim for a privacy-friendly change amount rather than the smallest fee, so it is not
trying to win that column.

The harness's reimplementation of Core's waste formula agrees with the waste Core itself reports on
every one of its own selections, which is what makes the cross-scoring trustworthy.

## 5. Capping the pool helps depth-first *more* than it helped best-first

> **Superseded by the pin.** These numbers were measured before deepening
> ([evanlinjin#5][ev5]) was in it. Re-measured with deepening on, sampling is equal or worse at every
> budget from 1 ms to 100 ms on the four fixtures it used to rescue — including
> `subsidizing_ancestry_50`, whose exact optimum it was previously the only thing to recover.
> Deepening reaches the same answers by searching rather than by re-rolling, so `--escalate` has
> nothing left to add on this track. The finding is kept because it was true of the traversal it was
> measured against, and because the mechanism is the interesting part: what sampling bought was never
> randomness, it was escaping a bad incumbent.


When the search runs out of budget, retrying it on randomly sampled subsets of the candidates and
keeping the best answer — `bench.py run --escalate` — was worth around -5.4% total against the
best-first traversal. The expectation recorded here was that depth-first would leave it less to do,
having already solved the large pools sampling was rescuing. Re-measured against this pin, over 42
fixtures and three sample seeds, that is wrong:

| budget | package fee | fee the child pays | improved | regressed |
| --- | --- | --- | --- | --- |
| 100,000 rounds | **-10.28%** | -6.43% | 12 | 1 |
| 1,000,000 rounds | **-11.07%** | -7.08% | 9 | 0 |
| 10 ms | -5.91% | -3.81% | 10 | 3 |
| 100 ms | -6.30% | -3.67% | 8 | 7 |
| 1000 ms | -7.90% | -4.78% | 7 | 2 |

Finding 3 explains why: depth-first prunes against whatever incumbent its dive order found, and a
smaller pool is a cheap way to reach a better one. **It closes finding 3's open problem.**
`subsidizing_ancestry_50` goes from 47,520 to **24,500** — best-first's exhausted, oracle-confirmed
optimum, on all three seeds — and `subsidizing_ancestry_100` from 81,050 to 31,180, better than
best-first reaches in ten seconds. The two fixtures depth-first cannot solve are the two sampling
helps most.

The cost is visible at 100 ms, where seven fixtures regress: a wall-clock budget has to be split so
the fallback can run at all, so a fixture that would have exhausted in 60 ms of 100 ms does not
exhaust in 50 ms and gets sampled when it should not have been. Under a round budget, where the
trigger is exact, that falls to one fixture and then none.

The design, the measurements behind it, and the things that do *not* work are in
[`SAMPLING-PLAN.md`](SAMPLING-PLAN.md) — §11 for this re-measurement, everything before it taken
against best-first and labelled as such.

## 6. At twenty and two hundred thousand candidates, both engines still answer

The checked-in matrix stops at 2000. `python3 genfixtures.py --scale && python3 bench.py scale` adds
a tier an order of magnitude past it — 20,000 and 200,000 candidates for the three large families.
Those fixtures are **not checked in**: one is 30 MB and they are deterministic from their seed, so
regenerating costs less than storing them.

The scale tier caps `max_weight` at `MAX_STANDARD_TX_WEIGHT` (400,000 weight units) and sets a target
around 400 inputs can fund. That is not cosmetic — see the correction below. A 100 ms wall-clock
budget per search:

| fixture | | fee the child pays | nodes | peak RSS |
| --- | --- | --- | --- | --- |
| `no_ancestry_20000` | coin-select | **243,750** | 11,008 | **7.0 MB** |
| | Bitcoin Core | 277,300 | — | 32.0 MB |
| `no_ancestry_200000` | coin-select | **245,790** | 8,192 | **49.6 MB** |
| | Bitcoin Core | 248,060 | — | 276.5 MB |
| `shared_ancestry_20000` | coin-select | 1,079,551 | 17,408 | **7.7 MB** |
| | Bitcoin Core | **1,075,299** | 100,000 | 140.4 MB |
| `shared_ancestry_200000` | coin-select | 1,172,027 | 4,864 | **58.2 MB** |
| | Bitcoin Core | **1,169,084** | 100,000 | 293.1 MB |
| `wallet_mixed_20000` | coin-select | **595,756** | 22,784 | **7.9 MB** |
| | Bitcoin Core | 639,659 | 100,000 | 173.1 MB |
| `wallet_mixed_200000` | coin-select | **636,093** | 4,352 | **57.6 MB** |
| | Bitcoin Core | 655,534 | 100,000 | 294.3 MB |

coin-select is cheaper on four of six and uses **4 to 22 times less memory throughout**. Both engines
return an answer on every fixture, inside half a second including parsing a 30 MB file.

The two Core wins are both `shared_ancestry`, which is the family built to punish exactly the thing
coin-select is supposed to be good at. Worth a look, and not something the smaller sizes show.

**Those two columns already include [PR #76][pr76]**, which is in this pin and which the rest of this
finding is the argument for: on `shared_ancestry_200000` it is what takes the child fee from 1,201,193
to the 1,172,027 above, and on `wallet_mixed_200000` from 638,866 to 636,093. Core's remaining lead on
`shared_ancestry_200000` is **0.25%**, down from 2.7%.

### Correction: Core's earlier "no solution" was Core being right

An earlier version of this finding reported that Core returned no solution on two of the three
200,000-candidate pools while coin-select answered all six, and read that as a win. **It was a
broken comparison, and the fault was in the fixtures.**

Those fixtures set no `max_weight`, and `core-runner/main.cpp` falls back to Core's
`MAX_STANDARD_TX_WEIGHT` when a fixture does not set one. The target was the usual 45% of the pool,
which at 200,000 candidates needs about 8,800 inputs and **2.4M weight units — six times the
400,000-unit standardness limit.** No standard transaction can fund it, so Core correctly declined.
coin-select answered only because nothing had told it the limit existed: its selections there were
transactions no node would relay. Raising `max_weight` to 20M makes Core answer that same fixture in
292 ms with 30,444 inputs, via `KnapsackSolver`.

Two things to take from it. **A target of 45% of the pool stops being a sensible benchmark once the
pool is large** — a wallet with 200,000 UTXOs does not spend half its balance in one transaction, and
the scale tier now targets what 400 inputs can fund. And **an engine returning nothing is not
automatically the engine losing**; it may be the only one enforcing a rule. `max_weight` is optional
in `SelectionProblem`, so a caller who omits it gets no protection from coin-select — which is worth
knowing independently of this benchmark.

### What Core picks that coin-select will not

The two `shared_ancestry` losses are worth understanding, because they are not what they look like.

**coin-select's answer is the greedy seed, unimproved.** Its returned score equals
`lowest_fee_seed_score` exactly on both fixtures, at every budget from 100 ms to 10 s. The search
contributes nothing: 118,784 nodes of a tree over 200,000 candidates never beat the greedy prefix,
and the answer is byte-identical at a hundred times the clock. **At this scale the ordering is the
whole algorithm.**

**Core's advantage is entirely that it touches fewer unconfirmed parents.**

| `shared_ancestry_200000` | inputs | with no unconfirmed parent | parents touched | union bump | child fee |
| --- | --- | --- | --- | --- | --- |
| coin-select | 360 | 134 | 226 | 955,403 | 1,201,193 |
| Bitcoin Core | 360 | **141** | **219** | **923,621** | **1,169,084** |

The bump difference is 31,782 sat and the fee difference is 32,109 — so **99% of Core's win is that
it dragged in seven fewer parents.** Core gets there structurally rather than cleverly: it charges
each coin its own bump inside the effective value *before* the search, so coins with unconfirmed
parents look worse and it drifts away from them. coin-select's greedy prefix sorts on raw
value-per-weight and cannot see ancestry at all.

**This is finding 3's mechanism with the magnitudes inverted.** Finding 3 measured an ancestry-aware
branching key on a 50-candidate fixture and found it useless, because demoting the offending coin
would have taken 1,063,000 sat of charge against a parent that owed 6,144. Here the pool is 200,000
near-identical coins: adjacent ones in the order differ by a median 148 sat while a parent costs a
median 4,221 sat to bump. The ancestry-blind order is wrong by roughly **twenty-eight positions** per
parent-laden coin, and unlike at n=50 there is no search to recover from it.

So the key that failed there works here — [PR #76][pr76] takes a second greedy prefix under it and
keeps whichever of the two the metric scores better:

| `shared_ancestry_200000`, greedy prefix under | child fee | union bump | parents |
| --- | --- | --- | --- |
| `value / weight` alone — [PR #75][pr75] | 1,201,193 | 955,403 | 226 |
| `(value - own bump) / weight` ([PR #76][pr76]) | **1,172,027** | 926,237 | 220 |
| Bitcoin Core, for reference | 1,169,084 | 923,621 | 219 |

That closes **91% of the gap** for a change to one sort key, and it is a measurement of the crate,
not a model: an emulation of the greedy prefix in Python predicted 1,172,027 to the satoshi before
the change was written, and the in-crate implementation returns exactly that.

### Why the same key is worth nothing at 20,000 candidates

At 20,000 candidates [PR #76][pr76] is byte-identical to [PR #75][pr75] on every fixture, while Core still
wins `shared_ancestry_20000` by 0.4%. That is not a second mechanism — it is the same one, one extra
unconfirmed parent:

| `shared_ancestry_20000` | inputs | with no unconfirmed parent | parents touched | union bump | child fee |
| --- | --- | --- | --- | --- | --- |
| coin-select | 357 | 146 | **204** | 835,801 | 1,079,551 |
| Bitcoin Core | 358 | 148 | **203** | 830,889 | **1,075,299** |

One parent is worth 4,912 sat against a 680 sat saving from coin-select's one fewer input. Net 4,252
— the entire gap, again fully accounted for.

What the reprice cannot do is find it, and the reason is measurable. What the key buys is the ratio
of a parent's charge to the gap between adjacent coins in the order:

| | median solo bump | median neighbour gap | positions a parent moves a coin | coins crossing the prefix cutoff |
| --- | --- | --- | --- | --- |
| 20,000 candidates | 4,185 sat | 1,656 sat | 2.5 | **0** (still 0 at top-1,000) |
| 200,000 candidates | 4,221 sat | 148 sat | 28.4 | 6 |

Ten times the coins drawn from the same value distribution means the top of the order is ten times
denser — the top 1,000 spans 4,998,053..2,792,317 sat at 20,000 candidates and 4,999,816..4,770,018
at 200,000. The same ~4,200 sat charge therefore reorders ten times further. Below that threshold the
reprice shifts parent-laden coins around without moving any of them across the cutoff, and the prefix
comes out the same set of coins.

**The qualification finding 3 needs:** "no per-candidate key can express this" is true of the fixture
it was measured on and false in general — but only just. A static ancestry-aware key is worth exactly
as much as the ancestor bump is worth relative to the value gaps between adjacent coins: negligible
on 50 coins that differ by millions of sats, still negligible on 20,000 that differ by thousands,
decisive on 200,000 that differ by hundreds. It is a fix for one regime, not for ancestry blindness.

### What the ancestry-aware seed costs elsewhere

Across the 42-fixture matrix at four budget regimes, [PR #76][pr76] against [PR #75][pr75]:

| regime | total package fee |
| --- | --- |
| 100,000 rounds | +0.000% — all 42 selections identical |
| 10 ms | −0.041% |
| 100 ms | +0.000% — all 42 selections identical |
| 1 s | +0.008% |

The nonzero regimes are deadline noise rather than the change, and the worst-looking entry is the
proof. `wallet_mixed_200` appears to regress **+6.3%** at 10 ms — but that fixture exhausts in 17,345
rounds and 9.8 ms, right at the deadline. Both arms exhaust to the identical selection given a
millisecond more, and it is *#75* that got the anomaly: truncated mid-search, it returned a
selection the harness happens to score better on package fee while scoring worse on the metric the
search is actually minimising. The two moves at 1 s are `no_ancestry_2000` (+0.007%) and
`wallet_mixed_2000` (+0.103%), both with a union bump of zero, and `no_ancestry_2000` has no
ancestors at all — the second pass is skipped outright on it.

Where the extra pass is not free it is a few milliseconds: `shared_ancestry_2000` 121 -> 124 ms and
`subsidizing_ancestry_50` 27 -> 32 ms at 100,000 rounds, both with identical round counts and
identical scores. On a pool small enough for that to matter, the search was going to fix the ordering
anyway.

### Getting here needed the ancestor sets stored sparsely

This tier was unrunnable before [PR #75][pr75], which is in this pin. `drags_in` and
`shared_drags_in` were one dense `Bitset` per candidate over every ancestor — candidates x ancestors
bits — while a candidate actually drags in **mean 0.42 to 0.60 entries and never more than two**.
The sets were 0.002% full.

| 200,000 candidates, 26,666 ancestors | peak RSS | search setup |
| --- | --- | --- |
| dense `Bitset` per candidate | 1,332 MB | 464 ms |
| flat indices + offsets ([PR #75][pr75]) | **58 MB** | **54 ms** |

**The time mattered more than the memory.** Iterating a dense bitset costs O(ancestors) per candidate
however few bits are set, so building the selection cache — a full pass over every candidate's
ancestor set — was O(candidates x ancestors) in time as well as space: 5.3 billion bit positions
where the entries number 84,000.

That is also the answer to a puzzle an earlier version of this finding recorded as unexplained.
`wallet_mixed_200000` returned **no solution with zero nodes** at a 100 ms budget, despite a target
fundable by 8,798 inputs at 2.6M weight units against a 20.9M cap. Setup took 464 ms, so the deadline
expired before the first node: the search, the bound and the single-random-draw fallback were all
fine and none of them ran. The dense build returns the same 9,217 inputs given a full second.

**A structure whose construction scales worse than the search shows up as a search failure**, and on
a wall-clock budget it shows up as "no solution" rather than as a slow answer. Core's two
no-solutions above are worth reading with that in mind rather than as a statement about its
algorithms.

A `BTreeSet` per candidate would fix the asymptotics too, but for sets of nought to two entries it
pays an allocation per non-empty set — around 100,000 of them here — and a pointer chase per read.
Every use of these sets in the crate is a full walk of one candidate's entries and none of them
mutate after construction, so a flat layout is both smaller and faster. `Bitset` is still right where
it is used over *candidates*: the selected and banned sets are dense and membership-tested constantly.

### One thing that does not survive the trip

**The dive floor in the iterative-deepening branch ([PR #74][pr74]) goes inert.** It is 200 x
candidates, which is 4M nodes at 20,000 candidates — more than a 100 ms budget reaches — so the
hybrid never hands over and matches the plain dive exactly. Scaling the floor on candidate count is
right at small pools and wrong at large ones. Pool sampling still pays at 20,000: it exhausts
`wallet_mixed_20000` and `shared_ancestry_20000` in a few thousand nodes where the full search
cannot.

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
[pr74]: https://github.com/bitcoindevkit/coin-select/pull/74
[pr75]: https://github.com/bitcoindevkit/coin-select/pull/75
[pr76]: https://github.com/bitcoindevkit/coin-select/pull/76
[ev4]: https://github.com/evanlinjin/coin-select/pull/4
[ev5]: https://github.com/evanlinjin/coin-select/pull/5
