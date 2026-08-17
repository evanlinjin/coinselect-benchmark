Draft, on top of the cheap-nodes PR. Three commits.

**This changes what every caller of `CoinSelector::bnb_solutions` gets**, hence `feat!`. The plain
dive remains available as `bnb_solutions_dive_only`.

## The problem

Depth-first search reaches complete selections immediately, then prunes against whatever its opening
dive found. On some inputs the dive stalls on a bad incumbent and never recovers. On
`subsidizing_ancestry_50` the incumbent sticks at **11,912 against a true optimum of 5,088** and does
not move across 40 million further nodes — every prune it makes for the rest of the search is against
an incumbent two and a half times worse than the answer.

The root cause is in the ordering, not the bound: candidates are sorted by value-per-weight, which
cannot see what a coin's unconfirmed ancestors cost to bump. A best-first priority queue does not
have this problem, because it orders by the bound, which *is* ancestry-aware — but it pays for that
with a frontier that grows without limit.

## What this does

**Iterative deepening on the bound.** Run the same depth-first traversal in passes under a rising
ceiling, so pass *k* visits the nodes a priority queue would expand before first popping that bound.
That recovers best-first's node ordering at depth-first's linear memory.

**Dive first, then deepen.** Deepening alone reaches complete selections late, which costs the large
pools that never exhaust — they spend their budget re-expanding instead of diving deep enough to find
a good complete selection. So: dive until the incumbent stops improving, then hand over to deepening
from the root, keeping the incumbent.

Note what that does *not* promise, because an earlier draft of this PR got it wrong. Against a dive
stopped at the same handover point the incumbent only improves, so the hybrid cannot be worse.
Against a dive that keeps spending the whole budget descending, it can be — the rounds spent
re-expanding are rounds the dive would have spent going deeper.

**Make it the default for `bnb_solutions` and `run_bnb`, when the problem has unconfirmed
ancestors.** The plain dive stays available as `bnb_solutions_dive_only`. Two tuned constants,
`DEFAULT_DEEPENING_EPS = 0.1` and `DEFAULT_DIVE_FLOOR_PER_CANDIDATE = 5`, both documented with the
sweep that chose them.

The ancestry gate is not a tuning choice. Deepening exists to escape a dive misled by a sort key that
cannot see what a coin's unconfirmed parents cost. With no ancestors there is no such blindness, the
dive does not stall, and re-expanding from the root is a straight loss: over 4,000 random
ancestor-free pools it measures worse on 54 and better on **1**, worst case +88%, concentrated in the
2,000-20,000 round band a wallet with a few dozen UTXOs actually sits in. All seven `no_ancestry`
benchmark fixtures are byte-identical to the plain dive.

## Measured

42 fixtures, 100,000-round budget, against the parent commit.

**Total package fee −6.63%.** Seven fixtures improved by 1.8% to 48.4%; three regressed by 0.6% to
3.0% (see [what it costs](#what-it-costs)).

| fixture | dive only | deepened | Bitcoin Core | |
| --- | --- | --- | --- | --- |
| `subsidizing_ancestry_50` | 47,520 | **24,500** | 29,690 | −48.4% |
| `shared_ancestry_200` | 42,680 | **23,197** | 46,550 | −45.7% |
| `subsidizing_ancestry_100` | 81,050 | **51,591** | 58,460 | −36.4% |
| `nested_ancestry_200` | 37,940 | **24,275** | 32,980 | −36.0% |
| `high_feerate_200` | 72,579 | **66,591** | 101,680 | −8.3% |
| `shared_ancestry_100` | 16,588 | **15,638** | 18,220 | −5.7% |
| `subsidizing_ancestry_200` | 75,880 | **74,494** | 100,240 | −1.8% |

Against Bitcoin Core's wallet coin selection, fixtures where coin-select's package fee wins go from
**38 of 42 to 41 of 42**. The 42nd is not a loss: on `high_feerate_20` the brute-force oracle
enumerates all 2^20 subsets, and coin-select returns the exact optimum with the tree exhausted. Core
lands on a different selection with the same fee. It is a tie at a proven optimum.

An existing test asserting an exact round count is **unchanged at 62,453**: its fixture has no
unconfirmed ancestors, so the gate switches deepening off for it. Deepening would reach the same
exact-value solution there in 2,970 rounds — but the gate is set by what happens under a *budget*,
not by round count at exhaustion.

## The two constants

Both are tuned to one benchmark and this should be weighed as such.

`DEFAULT_DEEPENING_EPS = 0.1`, the relative step between thresholds. A strict schedule — one pass per
distinct bound — costs up to **194x more nodes** on the fixtures that already match a priority queue
node for node, because they pay for re-expansion and buy nothing. 0.1 holds that near 1.5x while
collapsing the pass count to single digits.

**A trap worth knowing about:** `eps = 0.4` looks better on any "time to get ahead of Core" metric —
40 of 42 instead of 38. It gets there by giving up on the hard fixtures entirely, so it never arrives
late, it just loses on fee (`subsidizing_ancestry_50` 44,990 against Core's 29,690). Timing metrics
alone will select for quitting early.

`DEFAULT_DIVE_FLOOR_PER_CANDIDATE = 5`, how long the opening dive is protected before the stall rule
can fire. The dive needs a floor at all because the greedy incumbent is set before the first node,
which leaves the stall rule with nothing to measure against. Swept over 0, 5, 20, 50 and 200, at a
round budget and at 3 ms / 10 ms / 100 ms / 1000 ms:

| floor | 3 ms | 10 ms | 100 ms | 1000 ms |
| --- | --- | --- | --- | --- |
| 5 | **1,366,290** | **1,343,644** | 1,281,788 | 1,261,319 |
| 50 | 1,401,745 | 1,347,429 | **1,281,111** | **1,260,201** |

5 wins where budgets are tight (2.59% at 3 ms) and loses by under 0.1% where they are loose. Floor 0
— handing over before the dive completes a single selection — costs 10.7%, so the floor is doing real
work; it just does not need to be large. That the right value is small follows from what the dive is
for: it has to reach one complete selection, which is one root-to-leaf path.

This was 200 in the earlier draft, measured when a node cost several times more. The floor is counted
in **nodes**, so the parent commit making nodes cheaper turned the same floor into a longer dive in
wall clock, and the tuning had to move with it. Whether a node-counted floor is the right unit at all
is a fair question to raise on this PR.

## What it costs

The wins and losses split on pool size with no overlap: everything from n=50 to n=200 improves, and
`wallet_mixed_500` / `_1000` / `_2000` regress by 3.0% / 0.6% / 0.8%.

Those three are not budget starvation. Given ten times the budget the dive keeps improving
(`wallet_mixed_1000`: 56,633 -> 56,162 -> 56,140) while deepening sits at 56,950 at every budget from
100,000 rounds to a full second. Deepening plateaus and the dive does not: on a pool that large no
pass can complete, so re-expansion buys nothing while a dive is still descending into unexplored
parts of the tree.

I tried twice to fix it by handing back to the dive when deepening stops improving — once with the
existing stall rule, once with a tighter one — and both produced **byte-identical results on all 42
fixtures**. The rule never fires. Both were reverted rather than shipped.

A pool-size gate would score better here. I have not added one: it would be a constant fitted to ten
data points from one benchmark, in a library that runs on wallets this benchmark has never seen. The
trade is stated so it can be argued with.

## What it does not fix

Three fixtures — `subsidizing_ancestry_50`, `subsidizing_ancestry_100`, `nested_ancestry_200` — now
overtake Core on fee by 17–35%, but need roughly 5–10x Core's wall clock to get there. Two things
were tried and did not help, both worth recording:

- **Pool sampling**, which was worth −10.28% against the plain dive, is now equal or worse on all
  four of these. Deepening subsumes what it was buying.
- **A portfolio of greedy seeds** (Core's effective-value order, value descending, ancestry-adjusted
  variants) produces the **identical prefix** to today's key on all three. The answer on those
  fixtures is not a prefix of any candidate ranking, so no static seed can reach it.

## Test plan

`cargo test`, `cargo test --release`, `cargo clippy --all-features`, `--no-default-features` build:
all pass.

`tests/ancestor.rs` gains `deepening_escapes_a_dive_that_the_candidate_order_misleads`, which pins
the *reason* for the default rather than any round count: two groups, each a fat underpaying root
spent by one overpaying tip and one underpaying one, so coins on the same root share its bump and
what a coin costs depends on what else is selected. The dive commits to spreading across both roots;
deepening comes out 12.6% better at 600 rounds. The test asserts the size of the win, not the round
count, so a change that keeps deepening on but makes it converge later cannot pass silently.

A `deepening_stats` module of process-global atomics was in an earlier draft for harness
instrumentation. It has been removed: `AtomicU64` does not exist on `no_std` targets without 64-bit
atomics, and nothing read it.
