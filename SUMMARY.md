# Beating Core on all three axes

A running log of one question: can `bdk_coin_select` beat Bitcoin Core's wallet coin selection on
**every** fixture, on **solution fee**, on **work to find the answer**, and on **wall clock**?

**Not [`results/SUMMARY.md`](results/SUMMARY.md)**, which unluckily shares a name. That one is
written by `bench.py report` and overwritten on every run; delete it and it comes back. This one is
hand-maintained and cumulative, and deleting it loses work.

| | `results/SUMMARY.md` | this file |
| --- | --- | --- |
| written by | `bench.py report` | hand |
| subject | what the **pinned** revision measured | what is being **tried** to move it |
| contents | the 42-fixture matrix, cross-scores, oracle checks | profiles, hypotheses, sweeps, dead ends |

[`FINDINGS.md`](FINDINGS.md) sits between them: prose conclusions about the pinned revision.

Reproduce any row with `python3 bench.py all --oracle`; the per-arm numbers come from the
instrumentation described under [Method](#method).

**Where the work lives.** Two draft PRs in the fork, stacked — each based on the branch below it, so
each diff is only its own commits:

| PR | branch | head | based on |
| --- | --- | --- | --- |
| [evanlinjin#4][pr4] | `experiment/cheap-nodes` | `ba58982` | the branch behind [#76][pr76] |
| [evanlinjin#5][pr5] | `experiment/deepen-on-bound` | `ecdbbc9` | `experiment/cheap-nodes` |

Both have been through a full code review (see [what review changed](#what-review-changed)); the
heads above are post-review. Bodies are checked in under [`pr/`](pr/).

## The axes

| axis | what it measures |
| --- | --- |
| **fee** | package fee of the returned selection, harness fee model, both engines scored identically |
| **work** | rounds spent before coin-select is ahead of Core, against the nodes Core spent |
| **wall clock** | when coin-select first holds an answer better than Core's finished one, against how long Core took |

The wall-clock axis took three tries to state correctly, which is itself the finding. "How long did
the search run" is nearly meaningless here: `no_ancestry_2000` reaches its answer in **0.25 ms** and
then spends another **218 ms** failing to prove anything better exists. Under a round budget that
number is just the budget.

Reporting time-to-answer instead is better but still wrong, because it rewards an arm for arriving
quickly at something bad. The question that survives is the one a wallet would ask: **from a standing
start, when am I ahead of Core?**

## Scoreboard

| arm | fee | work to get ahead | wall clock to get ahead |
| --- | --- | --- | --- |
| [#76][pr76], the current pin | 38 / 42 | 31 / 31 | 37 / 42 |
| \+ cheap nodes (attempt 1) | 38 / 42 | 31 / 31 | 37 / 42 |
| \+ deepening (attempt 2) | **41 / 42** | **31 / 31** | **38 / 42** |

Work is out of 31 rather than 42 because Core reports no node count on the other eleven — it answered
them with `KnapsackSolver` or a single random draw, neither of which counts nodes.

**Fee is won.** The one fixture coin-select does not beat Core on is `high_feerate_20`, where the
brute-force oracle enumerates all 2^20 subsets and coin-select returns the exact optimum with the
tree exhausted. Core lands on a different selection with the same fee. That is a tie at a proven
optimum, and nothing can beat it.

Total package fee across all 42 fixtures fell **−6.63%**: seven fixtures improved by 1.8% to 48.4%,
and three regressed by 0.6% to 3.0%. That trade is discussed under
[what deepening costs](#what-deepening-costs-and-where).

What is left:

- **wall clock** — three fixtures (`subsidizing_ancestry_50`, `subsidizing_ancestry_100`,
  `nested_ancestry_200`) now overtake Core on fee by 17–35%, but need roughly 5–10x Core's wall clock
  to get there.

### The work axis was measured wrong at first, and it mattered

Comparing *final* round count against Core's node count made `high_feerate_200` look like a bad loss:
92,201 rounds against 329 nodes. But the two searches were not answering the same question — Core
stopped at 101,680 and coin-select carried on to 66,591, a 35% better fee, exhausting the tree.

Measured like for like, the fixture is not close:

| `high_feerate_200` | | |
| --- | --- | --- |
| Core, `CoinGrinder` | 101,680 | 329 nodes, 1.88 ms |
| coin-select, first answer beating that | 81,737 | **200 rounds, 0.068 ms** |
| coin-select, final | 66,591 | 79,399 rounds, tree exhausted |

It passes Core in **fewer rounds and 28x less wall clock**, then spends the rest of the budget getting
much further ahead. Charging it for the work it did *after* winning is the wrong comparison, and once
it is fixed the axis is a clean sweep.

### Why `ran` is not in that table any more

The obvious wall-clock axis — total time the search spent — compares coin-select given 100,000
*rounds* against Core given 100,000 *nodes*. Those are different amounts of work in different units,
so the number says as much about budget policy as about either engine. Worse, it rewards quitting:
the arm that gives up soonest wins it.

The axis that survived contact with the data is **when does coin-select first hold an answer better
than Core's finished one**, measured from a standing start against how long Core took. That needed
new instrumentation (see [Method](#method)) and it is the number reported above.

---

## Attempt 1 — make a node cost the same at any pool size

**Status: works, no behaviour change, kept.** [evanlinjin#4][pr4], head `ba58982`.

### What the profile said

`perf` on `wallet_mixed_2000`, which spends its whole budget:

| | share of runtime |
| --- | --- |
| `LowestFee::bound` | 58.5% |
| `BnbIter::exclusion_plan` | 16.7% |
| `Map::nth` (called by `exclusion_plan`) | 16.7% |

**Over 90% of the search was walking the candidate order.** Both costs turn out to be the same
mistake made in two places: iterating from the front of the order when everything at the front is
already decided.

The visible symptom was per-round cost growing with the pool, where Core's is flat:

| candidates | 50 | 200 | 500 | 1,000 | 2,000 |
| --- | --- | --- | --- | --- | --- |
| µs per round | 0.24 | 0.34 | 0.48 | 0.97 | 2.19 |

### The two fixes

**`exclusion_plan` re-walked the order.** It resumed scanning with
`self.selector.candidates().skip(cursor + 1)`. `candidates()` returns a `Map`, which has no `nth`
override, so `Skip` advances it one element at a time — O(cursor) at every node. Replaced with
`candidates_from(cursor)`, which slices the order and iterates from there.

**`unselected()` always started at the front.** Every metric query for "the best still-undecided
candidate" filtered through the decided prefix first. `best_undecided_value_pwu` is the clearest
case: it is *written* to scan only the run of candidates tying on the first undecided key, with a
comment saying the point is to be independent of pool size — and then reaching that first undecided
candidate cost O(depth) anyway.

The fix is to tell the view what the search already knows. Branch and bound decides candidates in
cursor order, so at a node with cursor *c*, positions `0..c` are all decided — included by an
inclusion frame or banned by an exclusion one. `SelectionView` now carries `decided_before` and
starts its scan there; `BnbIter` passes its cursor. A `debug_assert` checks the promise on every
view, and the debug test suite exercises it.

This is deliberately *not* a general `CoinSelector` cursor. Keeping it in the view means the claim
lives where it is true — inside the search that maintains the invariant — instead of becoming an
invariant every future caller of `select`/`ban`/`deselect` has to preserve.

### Measured

42 fixtures, 100,000-round budget, 5 runs after 2 warm-ups, median.

| fixture | before | after | |
| --- | --- | --- | --- |
| `no_ancestry_2000` | 257.2 ms | 20.9 ms | **12.3x** |
| `wallet_mixed_2000` | 212.5 ms | 22.9 ms | **9.3x** |
| `shared_ancestry_2000` | 120.3 ms | 23.5 ms | 5.1x |
| `no_ancestry_1000` | 100.8 ms | 20.7 ms | 4.9x |
| `wallet_mixed_1000` | 108.1 ms | 22.0 ms | 4.9x |
| `no_ancestry_500` | 70.7 ms | 20.7 ms | 3.4x |
| `wallet_mixed_500` | 53.4 ms | 21.2 ms | 2.5x |
| `shared_ancestry_1000` | 56.4 ms | 23.4 ms | 2.4x |

Geometric mean **1.59x** across all 42, median 1.43x, best 12.3x.

**Nothing else moved: identical selections and identical round counts on all 42 fixtures.** That is
the property that makes this cheap to review — it is a pure cost reduction, not a change of answer.

The design goal is visible in the shape of the result rather than the size of it. Every
budget-limited fixture now finishes 100,000 rounds in 21–25 ms regardless of pool size, where before
it ran from 28 ms to 257 ms. **Per-node cost is flat in the pool.**

### What it did not fix

**No axis moved.** Every fixture that beat Core still beat Core, and none that lost started winning.
A 12x speedup that changes no verdict is a useful thing to have measured: it says the remaining
losses are not speed, and it stopped the next attempt from being another optimisation.

It did change the next attempt, though, in a way worth recording — see attempt 2's dive floor.

### A dead end worth recording

The first hypothesis was the greedy fill inside `LowestFee::bound`, which re-derives a funded
selection from scratch at every node — genuinely O(pool) work. Stubbing the loop out (unsound, purely
to price it) showed it is worth **5.3x on `no_ancestry_2000` and 1.0x on everything else**: every
ancestry fixture takes the `bound_with_ancestors` path, which never runs that loop. Worth pricing
before building, and worth not building.

---

## Attempt 2 — iterative deepening, on by default

**Status: works, wins the fee axis, kept.** [evanlinjin#5][pr5], head `ecdbbc9`: [PR #74][pr74]'s
two commits rebased onto attempt 1, plus making the hybrid the default.

The three genuine fee losses are the same failure three times: depth-first dives on an ancestry-blind
sort, stalls on a bad incumbent, and prunes against it for the rest of the budget. On
`subsidizing_ancestry_50` the incumbent sticks at 11,912 against an optimum of 5,088 and does not
move across 40 million further rounds.

### The thing that had to change first

[PR #74][pr74] as it stood did **nothing at all** — byte-identical results at 100k, 1M and 10M
rounds. The hybrid was an opt-in method (`bnb_solutions_hybrid`) and `bnb_solutions` still built the
plain iterator, so no caller ever reached it. Making it the default is the change; the traversal was
already written.

### Measured

| fixture | n | dive only | deepened | Core | |
| --- | --- | --- | --- | --- | --- |
| `subsidizing_ancestry_50` | 50 | 47,520 | **24,500** | 29,690 | −48.4% |
| `shared_ancestry_200` | 200 | 42,680 | **23,197** | 46,550 | −45.7% |
| `subsidizing_ancestry_100` | 100 | 81,050 | **51,591** | 58,460 | −36.4% |
| `nested_ancestry_200` | 200 | 37,940 | **24,275** | 32,980 | −36.0% |
| `high_feerate_200` | 200 | 72,579 | **66,591** | 101,680 | −8.3% |
| `shared_ancestry_100` | 100 | 16,588 | **15,638** | 18,220 | −5.7% |
| `subsidizing_ancestry_200` | 200 | 75,880 | **74,494** | 100,240 | −1.8% |

**−6.63% total.**

### Attempt 1 invalidated this attempt's tuning constant

`DEFAULT_DIVE_FLOOR_PER_CANDIDATE` was 200, tuned when a node cost several times more. The floor is
counted in **nodes**, so making nodes cheaper turned the same floor into a much longer dive in wall
clock. Re-swept over 0, 5, 20, 50 and 200:

| floor | 3 ms | 10 ms | 100 ms | 1000 ms |
| --- | --- | --- | --- | --- |
| 5 | **1,366,290** | **1,343,644** | 1,281,788 | 1,261,319 |
| 50 | 1,401,745 | 1,347,429 | **1,281,111** | **1,260,201** |

5 wins where budgets are tight (2.59% at 3 ms) and loses by under 0.1% where they are loose. Floor 0
costs 10.7%, so the floor is doing real work — it just does not need to be large, which follows from
what the dive is for: reaching *one* complete selection is one root-to-leaf path.

Whether a node-counted floor is the right unit at all is now an open question, and is flagged on the
PR.

### What deepening costs, and where

The wins and the losses split on pool size with no overlap at all:

| | n | effect |
| --- | --- | --- |
| seven fixtures | 50 – 200 | −1.8% to **−48.4%** |
| `wallet_mixed_500` | 500 | +3.0% |
| `wallet_mixed_1000` | 1,000 | +0.6% |
| `wallet_mixed_2000` | 2,000 | +0.8% |

The three losses are not budget starvation. Given ten times the budget the dive keeps improving
(`wallet_mixed_1000`: 56,633 → 56,162 → 56,140) while deepening sits at 56,950 at every budget from
100,000 rounds to a full second. **Deepening plateaus and the dive does not.** On a pool that large no
pass can complete, so re-expansion from the root buys nothing while a dive is still descending into
parts of the tree nothing has looked at.

Two attempts to fix this by handing back to the dive when deepening stops improving — once with the
existing stall rule, once with a tighter one — produced **byte-identical results on all 42 fixtures**.
The rule never fires, because by the time deepening starts, `last_improvement` is already large enough
that the doubling rule cannot trip inside the budget. Both were reverted rather than shipped: a
mechanism that provably changes nothing on the whole benchmark is complexity with no evidence behind
it.

So the trade stands as measured, and the honest version of it is that a pool-size gate would score
better here and is not worth having. It would be a constant fitted to ten data points from one
benchmark, in a library that runs on wallets this benchmark has never seen.

### The trap in the timing metric

`eps = 0.4` scores **better** on "ahead of Core sooner" — 40 of 42 against 38. It gets there by giving
up on the hard fixtures, so it never arrives late, it just loses on fee (`subsidizing_ancestry_50`
44,990 against Core's 29,690). **A timing metric alone selects for quitting.** This is why the
scoreboard reports fee and timing together and neither is allowed to move alone.

### Two things that did not help

- **Pool sampling**, worth −10.28% against the plain dive in earlier work, is now equal or worse on
  all four hard fixtures at every budget from 1 ms to 100 ms. Deepening subsumes what it was buying.
- **A portfolio of greedy seeds** — Core's effective-value order, value descending, and two
  ancestry-adjusted variants — produces the **identical prefix** to today's key on all three hard
  fixtures. Only "lightest input first" differs, and it is far worse. This is
  [`FINDINGS.md`](FINDINGS.md) finding 3 confirmed from another direction: the answer there is not a
  prefix of *any* candidate ranking, so no static seed, however clever, can reach it.

---

## What review changed

Both branches went through a full code review before this was written up. Neither had a soundness
bug — the reviewer traced the `decided_before` invariant by induction over the frame stack and the
deepening termination argument over the threshold schedule, and independently reproduced attempt 1's
speedups. What review caught was worse than a bug in one case and cheaper in the others.

**The default was regressing every pool without unconfirmed ancestors, and I had claimed it could
not.** The commit said the hybrid "cannot return a worse selection than the dive alone would have",
which is true only against a dive *stopped at the handover point* — not against one that keeps
spending the same budget descending. Over 4,000 randomly generated ancestor-free pools the reviewer
measured the hybrid worse on 54 and better on **1**, worst case +88%, concentrated in the 2,000 to
20,000 round band that a wallet with a few dozen UTXOs actually sits in. The 42-fixture benchmark
could not see it, because the wins are all in the ancestry families.

Fixed by gating deepening on `problem.has_ancestors()`. That is not a tuning choice: deepening exists
to escape a dive misled by an ancestry-blind sort key, and with no ancestors there is nothing to
escape. All seven `no_ancestry` fixtures are now byte-identical to the plain dive again, and the
in-tree test asserting an exact round count went back to its original 62,453 on its own — that
fixture has no ancestors, so the gate correctly switched deepening off for it.

**The default was only half applied.** `run_bnb` — the method the docs tell callers to prefer — still
built the old iterator. The benchmark only saw the change because the harness reimplements `run_bnb`
on top of `bnb_solutions`, and the crate's own criterion benches, which call `run_bnb`, were measuring
the old code. Both entry points now share one constructor.

**`AtomicU64` broke `#![no_std]` targets without 64-bit atomics** — thumbv6m, riscv32imc and friends —
in a crate whose `Cargo.toml` says "No dependencies! Please do not add any please!". The module it
lived in existed only for benchmark instrumentation that nothing reads any more. Deleted.

Also taken: `min_input_weight` on `CoinSelector` was silently getting the slow full-order scan even
when reached through a view, on the bound's hot path whenever `max_weight` is set — a latent hole in
attempt 1's flat-cost claim. `candidates_from` narrowed to `pub(crate)`. Two rustdoc warnings, an
unreachable clamp, a dead `reset_to_root`, a `debug_assert` on `eps`, five public entry points
collapsed to three, and a CHANGELOG entry so the escape hatch is discoverable.

And the review asked for the one thing the work most needed: an in-tree test for the *reason*
deepening is the default, instead of leaving the entire justification in an external benchmark.
Writing it took three tries, and the failures were informative. A pool where each baited coin has its
own parent is too easy — the dive solves it. What reproduces the pathology is the fixture generator's
actual shape: coins sharing a **fat underpaying root**, so what a coin costs depends on which others
are already selected, which is precisely what a per-candidate sort key cannot see.

---

## What is left

**Three fixtures overtake Core late.** `subsidizing_ancestry_50`, `subsidizing_ancestry_100` and
`nested_ancestry_200` end 17–35% ahead on fee but need roughly 5–10x Core's wall clock to get there.
Both levers tried against them failed (above), and the failure mode is understood rather than
mysterious: the answer is a property of the selected *set*, so nothing that ranks coins individually
can shortcut to it. What is left is making the deepening passes reach it sooner.

## Method

`tools/scoreboard.py` runs both engines on all 42 fixtures and scores each axis per fixture. Two
pieces of runner instrumentation were added for it:

- `best_round` — the round that produced the returned selection. Under a budget, `rounds` is just
  the budget; this is the number that answers "how much work did finding the answer take".
- `best_ns` — wall clock to that round. Read only on an improvement, which is rare, so it does not
  distort the measurement the way a per-round clock read would.

Both are now in `results/results.csv`.

**On comparing `work` across engines.** Core counts depth-first nodes and coin-select counts
branch-and-bound iterator rounds. These are not the same unit and the comparison is rough; it is
reported because the goal asks for it, not because the units line up.

The three scripts live in `tools/`, run from the repository root, and take runner paths as arguments
so any two arms can be compared:

```sh
python3 tools/scoreboard.py --label "my arm" --runner path/to/coinselect-bench-runner
python3 tools/beat.py "before=path/to/runner-a" "after=path/to/runner-b"
python3 tools/seeds.py subsidizing_ancestry_50        # emulate greedy prefixes under other keys
```

`tools/seeds.py` is the one that is not a scoreboard: it emulates the greedy prefix under a set of
candidate sort keys in Python, which is how a seed portfolio was ruled out in minutes rather than
built and measured.

[pr4]: https://github.com/evanlinjin/coin-select/pull/4
[pr5]: https://github.com/evanlinjin/coin-select/pull/5
[pr73]: https://github.com/bitcoindevkit/coin-select/pull/73
[pr74]: https://github.com/bitcoindevkit/coin-select/pull/74
[pr75]: https://github.com/bitcoindevkit/coin-select/pull/75
[pr76]: https://github.com/bitcoindevkit/coin-select/pull/76
