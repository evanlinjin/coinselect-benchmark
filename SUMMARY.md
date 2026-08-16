# Beating Core on all three axes

A running log of one question: can `bdk_coin_select` beat Bitcoin Core's wallet coin selection on
**every** fixture, on **solution fee**, on **work to find the answer**, and on **wall clock**?

Not to be confused with [`results/SUMMARY.md`](results/SUMMARY.md), which is machine-written by
`bench.py report` and rewritten on every run. This file is hand-maintained and cumulative:
[`FINDINGS.md`](FINDINGS.md) says what the current pin does, this says what is being tried to move it.

Reproduce any row with `python3 bench.py all --oracle`; the per-arm numbers come from the
instrumentation described under [Method](#method).

**Where the work lives.** Two local branches, each building on the last, neither pushed yet — the
signing key is on a smartcard that needs a physical touch:

| branch | head | what it is |
| --- | --- | --- |
| `experiment/cheap-nodes` | `daad7cc` | attempt 1, on top of [#76][pr76] |
| `experiment/deepen-on-bound` | `ae654f3` | attempt 2, on top of attempt 1 |

## The axes

| axis | what it measures |
| --- | --- |
| **fee** | package fee of the returned selection, harness fee model, both engines scored identically |
| **work** | rounds spent to *reach* the returned answer, against Core's node count |
| **wall clock** | when coin-select first holds an answer better than Core's finished one, against how long Core took |

The wall-clock axis took three tries to state correctly, which is itself the finding. "How long did
the search run" is nearly meaningless here: `no_ancestry_2000` reaches its answer in **0.25 ms** and
then spends another **218 ms** failing to prove anything better exists. Under a round budget that
number is just the budget.

Reporting time-to-answer instead is better but still wrong, because it rewards an arm for arriving
quickly at something bad. The question that survives is the one a wallet would ask: **from a standing
start, when am I ahead of Core?**

## Scoreboard

| arm | fee | work | ahead of Core sooner than Core finished |
| --- | --- | --- | --- |
| [#76][pr76], the current pin | 38 / 42 | 41 / 42 | 37 / 42 |
| \+ cheap nodes (attempt 1) | 38 / 42 | 41 / 42 | 37 / 42 |
| \+ deepening (attempt 2) | **41 / 42** | 41 / 42 | **38 / 42** |

**Fee is won.** The one fixture coin-select does not beat Core on is `high_feerate_20`, where the
brute-force oracle enumerates all 2^20 subsets and coin-select returns the exact optimum with the
tree exhausted. Core lands on a different selection with the same fee. That is a tie at a proven
optimum, and nothing can beat it.

Total package fee across all 42 fixtures fell **−6.51%**, six fixtures improved, zero regressed.

What is left:

- **work** — `high_feerate_200` only: 92,201 rounds to reach its answer against Core's 329 nodes.
- **wall clock** — three fixtures (`subsidizing_ancestry_50`, `subsidizing_ancestry_100`,
  `nested_ancestry_200`) now overtake Core on fee by 17–35%, but need roughly 5–10x Core's wall clock
  to get there.

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

**Status: works, no behaviour change, kept.** Branch `experiment/cheap-nodes`, commit `daad7cc`.

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

**Status: works, wins the fee axis, kept.** Branch `experiment/deepen-on-bound`, head `ae654f3`:
[PR #74][pr74]'s two commits rebased onto attempt 1, plus making the hybrid the default.

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

| fixture | dive only | deepened | Core | |
| --- | --- | --- | --- | --- |
| `subsidizing_ancestry_50` | 47,520 | **24,500** | 29,690 | −48.4% |
| `shared_ancestry_200` | 42,680 | **23,197** | 46,550 | −45.7% |
| `subsidizing_ancestry_100` | 81,050 | **51,591** | 58,460 | −36.4% |
| `nested_ancestry_200` | 37,940 | **24,750** | 32,980 | −34.8% |
| `high_feerate_200` | 72,579 | **68,112** | 101,680 | −6.2% |
| `shared_ancestry_100` | 16,588 | **15,638** | 18,220 | −5.7% |

**−6.51% total, six improved, none regressed.** An existing test asserting an exact round count went
**62,453 → 2,970** for the same optimal exact-value solution.

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

## What is left

**`high_feerate_200`, the work axis.** 92,201 rounds to reach its answer against Core's 329 nodes.
Core solves it with `CoinGrinder`, which the fixture family exists to exercise; this is the one
fixture where Core's portfolio has an algorithm that fits the shape of the problem and coin-select
has one general search.

**Three fixtures overtake Core late.** `subsidizing_ancestry_50`, `subsidizing_ancestry_100` and
`nested_ancestry_200` end 17–35% ahead on fee but need roughly 5–10x Core's wall clock to get there.
Both levers tried against them failed (above), and the failure mode is understood rather than
mysterious: the answer is a property of the selected *set*, so nothing that ranks coins individually
can shortcut to it. What is left is making the deepening passes reach it sooner.

## Method



`tools/scoreboard.py` runs both engines on all 42 fixtures and scores the four axes per fixture. Two
pieces of runner instrumentation were added for it:

- `best_round` — the round that produced the returned selection. Under a budget, `rounds` is just
  the budget; this is the number that answers "how much work did finding the answer take".
- `best_ns` — wall clock to that round. Read only on an improvement, which is rare, so it does not
  distort the measurement the way a per-round clock read would.

Both are now in `results/results.csv`.

**On comparing `work` across engines.** Core counts depth-first nodes and coin-select counts
branch-and-bound iterator rounds. These are not the same unit and the comparison is rough; it is
reported because the goal asks for it, not because the units line up.

[pr73]: https://github.com/bitcoindevkit/coin-select/pull/73
[pr74]: https://github.com/bitcoindevkit/coin-select/pull/74
[pr75]: https://github.com/bitcoindevkit/coin-select/pull/75
[pr76]: https://github.com/bitcoindevkit/coin-select/pull/76

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
