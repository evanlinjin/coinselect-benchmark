# Plan: iterative deepening on the bound for `bdk_coin_select`

Written to be handed to someone with no prior context. Everything needed to build, measure and
falsify the idea is here or reachable from here.

## 0. Orientation — what these repositories are

**`bdk_coin_select`** is a Rust coin-selection crate. Given a set of candidate UTXOs and a target,
it runs branch and bound to minimise a metric's score. The metric in play is `LowestFee`, which
minimises long-term fee: the fee this transaction pays, plus the cost of eventually spending the
change output it creates. The crate also understands **unconfirmed ancestors**: selecting a coin
whose parent transaction is unconfirmed and underpaying obliges the child to bump that parent, and
the bump is netted across the *union* of ancestors the selection drags in, so two coins on one
parent pay for it once.

- Repository: `https://github.com/evanlinjin/coin-select.git`
- **Base this work on rev `9c40ae23aa9386d4dd3e5ac4491e2645f6e3f396`**, branch
  `feat/dfs-remove-changeless`, which is [PR #73][pr73] against `bitcoindevkit/coin-select`. That
  revision searches depth-first; an earlier revision searched from a priority queue, and the
  difference between the two is the entire subject of this plan.
- Files that matter: `src/bnb.rs` (the traversal), `src/metrics/lowest_fee.rs` (the metric and its
  bound), `src/selection_view.rs` (cached aggregate queries the bound uses),
  `src/coin_selector.rs` (`run_bnb`, `bnb_solutions`, candidate ordering).

**`coinselect-benchmark`** is the harness that measures it against Bitcoin Core's wallet on 42
fixtures. It is where every number in this plan comes from. `python3 bench.py setup && python3
bench.py run && python3 bench.py report` builds both engines, runs the matrix and writes
`results/SUMMARY.md`; `python3 bench.py compare-revs --a <rev> --b <rev>` A/Bs two coin-select
revisions on the same fixtures. `FINDINGS.md` finding 3 is the problem this plan attacks.

## 1. The problem, stated as measurements

Depth-first branch and bound solved the memory problem outright — peak RSS is flat at 2.6–3.5 MB
from 8 candidates to 2000, where the priority-queue traversal reached **20 GB** on a 500-candidate
problem given a wall-clock budget. That is why PR #73 exists and it is not in question.

What it lost is node ordering. A queue expands the globally most promising open node; a dive expands
whatever is under its feet. The cost shows up only when the dive starts in the wrong place:

| fixture | best-first nodes | depth-first nodes | ratio |
| --- | --- | --- | --- |
| `no_ancestry_20` / `_50` / `_100` / `_200` | 13 / 1,191 / 2,212 / 8,127 | identical | **1.0x** |
| `adversarial_shared_100` / `_200` | 486 / 2,480 | identical | **1.0x** |
| `nested_ancestry_100` | 46 | 5,945 | 129x |
| `nested_ancestry_200` | 23,217 | 3,145,352 | 136x |
| `subsidizing_ancestry_50` | **55,737, tree exhausted** | 36,561,920 in 10 s, **not exhausted** | ≥656x |

**The sharpest case is `subsidizing_ancestry_50`: fifty candidates.** Best-first proves the optimum
in 55,737 nodes. Depth-first starts from the greedy incumbent (score 13,370), improves once to
11,912, and then does not improve again across 40 million further nodes — its answer is byte-identical
at 100 ms, 1 s and 10 s, so it is stuck rather than starved. The optimum scores **5,088** (the child
pays 4,508 sat against depth-first's 11,332).

Two things have already been ruled out, and re-deriving them would be waste:

- **The bound is not wrong.** Cut that fixture's pool to 20 candidates keeping the optimal five and
  depth-first finds the optimum and exhausts, agreeing with a brute-force oracle.
- **The branching order cannot be fixed with a better key.** Sorting by
  `(value - the candidate's own ancestor bump) / weight` instead of `value / weight` costs +0.81% in
  total fee and does not move this fixture at all. Ancestor bumps are three orders of magnitude too
  small to reorder the top of a value-per-weight sort: demoting the coin the optimum avoids would
  take 1,063,000 sat of charge and its parent owes 6,144. `FINDINGS.md` finding 3 has the detail.

What is left is **node expansion order**, and that is what this plan buys back.

## 2. What to build

Iterative deepening branch and bound — the same trick as IDA\*, applied to the crate's admissible
lower bound instead of a heuristic distance.

Minimising a score. `bound(node)` is an admissible lower bound on the score of every complete
selection in that node's subtree. `best` is the incumbent: the best complete score found so far.

Today `descend()` keeps a child when `bound < best`. Add a **threshold `T`** and keep a child only
when `bound <= T` as well. Run the dive to completion under that threshold, then raise `T` and run
it again from the root.

```
T := bound(root)
loop:
    next_T := None
    run the existing depth-first traversal, but prune a child when bound > T,
      recording next_T := min(next_T, bound) for every child pruned that way
    if best is Some and best <= T: stop            -- incumbent proven optimal
    if next_T is None:             stop            -- whole tree explored
    T := next_T
    reset to the root, keeping `best`
```

**Why the stopping rule is sound.** A pass with threshold `T` visits every node whose bound is
`<= T`, except those pruned for being no better than the incumbent — and those cannot contain
anything better than the incumbent, by admissibility. Suppose a complete selection exists with score
`s < best <= T`. Admissibility means every node on its path has bound `<= s`, so no node on that path
was pruned by either rule, so the selection was visited and scored, so it would be the incumbent.
Contradiction. Therefore `best <= T` at the end of a pass proves `best` optimal.

**Why the threshold schedule is a speed knob and never a correctness knob.** Raising `T` further
than `next_T` only ever *adds* nodes to a pass; it never skips one. So any schedule that is
monotonically increasing is correct, and the stopping rule above holds unchanged. This matters
because it means the float problem in §4 can be solved by tuning without endangering the answer.

**Why it recovers best-first's ordering.** Pass `k` visits exactly the nodes with bound `<= T_k`,
which is precisely the set a priority queue expands before it first pops a node of that bound. The
passes reconstruct best-first's expansion order in linear memory, paying for it by re-expanding the
cheap nodes once per pass.

## 3. What it should buy, with a number to check against

On `subsidizing_ancestry_50` the set of nodes with bound below the optimum is what best-first
expanded: **55,737**. Iterative deepening must visit that set once per pass, so the target is
55,737 x (number of passes), against depth-first's current 36.5M-and-still-wrong.

**That is the headline acceptance test: this fixture must reach a child fee of 4,508 and report the
tree exhausted, inside a few hundred thousand nodes.** If it takes ten million, the idea has failed
in the form built and §7 applies.

Peak RSS must stay flat — 2.6–3.5 MB across the matrix. Any growth with candidate count means the
stack is being retained per pass and the entire point has been lost.

## 4. The risk that decides this: how many passes

`Ordf32` wraps `f32`, and bounds are computed from continuous quantities. If nearly every node has a
distinct bound, `next_T` advances by one node per pass and the search becomes quadratic. This is the
one thing that can kill the design, and it should be measured *before* the implementation is
polished:

> Instrument the existing traversal to dump the bound of every node it visits on
> `subsidizing_ancestry_50`, then count distinct values and plot how many nodes fall below each. If
> the distinct-bound count is within an order of magnitude of the node count, go straight to the
> relaxed schedule below rather than building the strict one first.

Do not put the instrumentation's environment lookup inside the node loop. A previous experiment in
this repository did exactly that and inflated a per-round measurement thirtyfold; hoist it into a
`OnceLock`.

There is a branch in the same repository, `fix/exact-integer-fee-math` (`532ef50`, *"score and bound
branch and bound in exact satoshis"*), which replaces the float score and bound with integer
satoshis. That changes this risk's character completely — integer bounds are coarse and collide, so
`next_T` would advance in useful jumps. It is **not** the base for this work and should not be merged
into it, but if stage 1 says the float spread is fatal, rebasing this idea onto that branch is a
better move than abandoning it. Check with the repository owner before switching base.

**The relaxed schedule.** `T_{k+1} = max(next_T, T_k * (1 + eps))`, with `eps` around `1e-3`. This
caps the pass count at `log_{1+eps}(range)` — a few thousand at worst, and in practice tens — and by
§2 it cannot break the answer. As `eps` grows the search degenerates smoothly into today's plain
depth-first, which is a useful property: the knob has a known behaviour at both ends.

Keep the incumbent across passes. Never reset `best`. Later passes are far cheaper than their
node-count-under-`T` suggests, because incumbent pruning does most of the work the second time
through.

## 5. Where the code goes

All of this lives in `src/bnb.rs`. The traversal is an `Iterator` whose `next()` expands one node —
that is what the harness counts as a round.

- `BnbIter` gains two fields: `threshold: Option<Ordf32>` and `next_threshold: Option<Ordf32>`.
- `is_promising(&self, bound)` currently returns `best > bound`. It gains the threshold test.
  **Record `next_threshold` only for children rejected by the threshold, not by the incumbent** — a
  child that is no better than the incumbent can never become interesting, and folding it into the
  schedule wastes passes.
- `descend()` already computes `inc_bound` and `exc_bound` and already descends into the better
  child first (`include_first = inc <= exc`). That is the local half of "use the bound as a hint"
  and it is done; leave it alone. Only the two `is_promising` calls change.
- `backtrack_to_next_branch()` returning `false` currently means the tree is exhausted. It now means
  *the pass* is over. That is where the stopping rules are evaluated and where the next pass starts.
- A new `reset_to_root()` unwinds every frame with the existing `undo_include` / `undo_exclude`
  paths and clears the stack. Do not rebuild the `CoinSelector` or the `SelectionCache` — unwinding
  in place is what keeps memory flat, and the undo paths are already exercised by backtracking.
- `new()` calls `bound_is_promising()` once and sets `exhausted` if the root is hopeless. That check
  must stay against the incumbent only; the initial threshold is derived from the root bound, so it
  cannot reject the root.
- `seed_greedy_incumbent()` yields the greedy prefix as the iterator's first item. Keep it exactly
  as is: it is what makes the search anytime, and it seeds `best` for the first pass.

Nothing outside `bnb.rs` should need to change. `run_bnb` takes `max_rounds` and stops there; rounds
now span passes, which is the intended meaning — a caller's budget is a total amount of work.

## 6. Correctness strategy

**The control run is the first commit, and it is not optional.** Build the change so that iterative
deepening can be disabled, then confirm the disabled build is **byte-identical to the pinned
revision on all 42 fixtures** — same selection, same score, same round count, same `exhausted` flag.
Only then turn it on. Without this control every later difference is unattributable. (A recent
ordering experiment in this repository did exactly this and the control caught nothing, which is how
its +0.81% result could be trusted as ordering rather than accident.)

Then:

- `cargo test --all-features` and `--no-default-features`, both green. Note that
  `cargo check --all-targets` does **not** compile doctests, and this crate's `src/lib.rs` example
  uses parts of the public API; run the real test command.
- Every fixture that reports `exhausted` must return the same selection it returns today. Iterative
  deepening changes the order nodes are visited in, never which selections are legal.
- Where an exhausted result differs, that is a bound bug being exposed, not a traversal difference —
  stop and investigate. One such disagreement is already known and unexplained: on
  `no_ancestry_1000` the two traversals both report exhausted and differ by one sat (30,463 against
  30,462). f32 in the bound is the suspicion. Do not let this plan's changes hide it.
- Run the harness's oracle: `python3 bench.py run --oracle` brute-forces every fixture with at most
  20 candidates and says whether the search found the true optimum of its own objective.

## 7. How to know it is working, and what to do when it is not

Measure at **equal wall clock, not equal rounds**. A round means something different in each
traversal, and comparing round budgets across this change has already produced one wrong conclusion
in this repository. Use `bench.py run --deadline-us <n>` with the round cap lifted.

Score with the harness's shared fee model rather than the crate's own reported score — the crate
reports `None` on some paths, which silently changes which fixtures a total covers.

Four outcomes, and what each means:

1. **`subsidizing_ancestry_50` exhausts at a child fee of 4,508 in a few hundred thousand nodes, no
   fixture regresses, RSS stays flat.** The design works. Report pass counts per fixture.
2. **It gets the right answer but takes tens of millions of nodes.** The pass count is the problem;
   go to the relaxed schedule in §4 and re-measure before concluding anything.
3. **It fixes the ancestry fixtures but regresses the `1.0x` families** (`no_ancestry_*`,
   `adversarial_shared_*`, which already match best-first node for node). Re-expansion overhead is
   being paid where there was nothing to buy. Gate the whole mechanism behind
   `problem.has_shared_ancestors()`, which the crate already computes — the 1.0x families either
   have no ancestors or already start from an optimal incumbent.
4. **Neither schedule brings the pass count down.** The fallback is **limited discrepancy search**:
   dive as today, but explore only paths that take the *worse* child at most `k` times, for
   `k = 0, 1, 2, ...`. It is also linear-memory, it reuses `descend()`'s existing better-child
   choice directly, and it targets the same failure — an optimum that differs from the greedy dive
   in a handful of decisions. Write it up before building it.

## 8. The bar this has to clear, which is higher than plain depth-first

**Pool sampling already solves this problem**, without touching the crate: retry the search on
randomly sampled candidate subsets when the budget runs out and keep the best answer. Measured
against this same pinned revision over 42 fixtures and three seeds, it is worth **-10.28%** total
package fee at a 100,000-round budget, and on `subsidizing_ancestry_50` it recovers **exactly** the
optimum best-first proves — package fee 47,520 down to 24,500, on every seed. `SAMPLING-PLAN.md` §11
has the numbers.

So iterative deepening is not competing with today's depth-first. It has to be better than sampling,
or complementary to it, and the comparison must be made explicitly:

| arm | what to run |
| --- | --- |
| depth-first (control) | pinned revision, wall-clock budget |
| depth-first + sampling | `bench.py run --escalate`, same budget |
| depth-first + iterative deepening | this work, same budget |
| both | this work with `--escalate`, same budget |

One harness footgun to know about: **`--escalate` alone does nothing.** The sampling path is gated on
`--max-n` being set; `bench.py` passes `--max-n 1 --escalate --cap-on-budget`. Running `--escalate`
by itself measures the plain search against itself and reports +0.00% at every budget, which has
already been reported once as a real result and was not one.

If iterative deepening wins outright, it is the better answer, because it needs no randomness, no
seeds and no reproducibility machinery, and it *proves* optimality where sampling only finds. If it
matches, prefer it for the same reason. If it loses, say so plainly and keep sampling.

## 9. Staging

Each stage is a commit that can be measured on its own.

1. **Instrument and count distinct bounds** on `subsidizing_ancestry_50` and two fixtures from the
   1.0x families. This decides strict versus relaxed schedule before any design is committed to.
   Throwaway commit; do not merge.
2. **Threshold plumbing, disabled.** Fields, `is_promising` change, `reset_to_root()`, all behind a
   switch that is off. Prove byte-identical results on 42 fixtures. This is the control from §6.
3. **The pass loop, strict schedule.** Turn it on. Measure the four outcomes in §7.
4. **The relaxed schedule** with `eps` exposed internally, if stage 3 says the pass count needs it.
   Sweep `eps` over at least three values and report the sweep, not just the winner.
5. **Gate on `has_shared_ancestors()`** if stage 3 or 4 regressed the 1.0x families.
6. **The full comparison in §8**, four arms, wall-clock budgets at 10 ms, 100 ms and 1000 ms.

## 10. Expected outcome, and how to know this plan was wrong

Success looks like `subsidizing_ancestry_50` and `subsidizing_ancestry_100` reaching best-first's
answers and proving them, no regression on the fixtures that already match best-first node for node,
peak RSS unchanged at three megabytes, and a pass count in the tens rather than the thousands.

The plan is wrong if the distinct-bound count in stage 1 is close to the node count *and* the relaxed
schedule cannot bring the pass count down without degenerating into plain depth-first. That would
mean the bound's values are too finely spread for threshold-based deepening to reconstruct an
ordering, and the honest conclusion would be that node ordering in this problem is worth real memory
— in which case the interesting question becomes a bounded frontier (keep the best `k` open nodes,
discard the rest) rather than no frontier at all.

Two smaller ways it could be wrong, both cheap to check early: the re-expansion might cost more per
node than expected because `bound()` is not as cheap as assumed — profile one pass before building
the loop; and `reset_to_root()` might not be as cheap as unwinding suggests if the `SelectionCache`
does work per undo that is fine once per backtrack but not once per pass.

[pr73]: https://github.com/bitcoindevkit/coin-select/pull/73

## 11. Stage 1 measured — the schedule question is settled, and §3's target number is not obtainable this way

Run with the throwaway instrumentation described in §9 stage 1: a histogram of every bound the
traversal computes, keyed on `f32` bits, with the env lookup hoisted into a `OnceLock`. The probe
build with the probe disabled is byte-identical to the pinned revision on all 42 fixtures, so the
numbers below are the pinned traversal's own behaviour.

| fixture | nodes | bound evals | distinct bounds | distinct / evals |
| --- | --- | --- | --- | --- |
| `subsidizing_ancestry_50` | 20,000,000 (capped) | 46,658,548 | **980** | 0.002% |
| `nested_ancestry_100` | 5,945 (exhausted) | 12,225 | 1,389 | 11.4% |
| `no_ancestry_100` | 2,212 (exhausted) | 4,535 | 555 | 12.2% |
| `adversarial_shared_100` | 486 (exhausted) | 1,034 | 262 | 25.3% |

**The quadratic fear in §4 is unfounded.** Distinct bounds are few in absolute terms — hundreds, not
millions — so the strict schedule terminates in a bounded number of passes. That was the one risk
identified as able to kill the design, and it does not.

**But the strict schedule is still not viable, for a different reason.** Simulating the pass
structure from each histogram — total nodes visited across all passes, including the final one that
proves optimality — against what the traversal costs today:

| fixture | today | strict schedule | `eps = 0.1` |
| --- | --- | --- | --- |
| `no_ancestry_100` | 2,212 | 428,658 (**194x worse**) | 3,156 (1.4x) |
| `adversarial_shared_100` | 486 | 43,552 (**90x worse**) | 706 (1.5x) |
| `nested_ancestry_100` | 5,945 | 991 | 111 |

The fixtures that already match best-first node for node are exactly the ones the strict schedule
ruins, because they pay for re-expansion and buy nothing. **§9's staging is therefore wrong: build
the relaxed schedule first, not the strict one.** §7's outcome 3 is not a contingency to check for,
it is the expected result, and the gate on `has_shared_ancestors()` should be assumed necessary
until measured otherwise.

`eps` around `0.1` holds the overhead on those fixtures to about 1.5x while collapsing the pass count
to single digits. Sweep it, but start there rather than at `1e-3`.

### What this method cannot answer, and why

§3 sets the acceptance target from best-first's expansion count on `subsidizing_ancestry_50`: 55,737
nodes, on the reasoning that a queue expands exactly the nodes whose bound is below the optimum. The
histogram says only **141 of 46.6 million bound evaluations** on that fixture are at or below the
optimum's score of 5,088.

Both are right, and the gap between them *is the bug*. The histogram is drawn from where depth-first
goes, and depth-first never reaches the region containing the optimum — that is the entire finding in
`FINDINGS.md` finding 3. So a depth-first-derived histogram cannot estimate iterative deepening's
work on the one fixture that matters, and the 6,159-node estimate the simulation produces for it
should be ignored as an artefact of sampling the wrong part of the tree.

**To get a real target, port the same instrumentation to the best-first revision**
(`91f5cfeb1163f87a27059adbbe1de6af8afbb08b`, PR #70) and histogram the bounds of the 55,737 nodes it
expands. That is the population iterative deepening has to traverse, and its distinct-bound count is
the pass count that matters. Do this before trusting any estimate for that fixture.

## 12. Implemented — it works, with one caveat the plan did not anticipate

Built on `experiment/iterative-deepening` (`7a0c0d3`), a single commit on top of `9c40ae2`. The
disabled build is byte-identical to the pinned revision on all 42 fixtures; `cargo test` is green on
`--all-features` and `--no-default-features` (64 tests).

### The headline test passes, by a wide margin

`subsidizing_ancestry_50`, wall clock, round cap lifted:

| arm | nodes | passes | exhausted | fee the child pays | wall |
| --- | --- | --- | --- | --- | --- |
| plain dive | 40,000,000 | — | no | 11,332 | 11,370 ms |
| deepening, `eps=0.1` | **64,544** | 8 | **yes** | **4,508** | **21 ms** |
| deepening, `eps=0.5` | 69,821 | 2 | yes | 4,508 | 24 ms |

That is 1.16x best-first's 55,737 nodes, at 3.5 MB instead of a frontier. §3's acceptance test asked
for a few hundred thousand nodes; it took sixty-five thousand.

At a 1000 ms budget across the matrix, `eps=0.1`: exhausted rises **31 -> 34 of 42**, peak RSS stays
**3.5 MB**, and five fixtures improve sharply — `shared_ancestry_200` -41.9%, `subsidizing_ancestry_100`
-37.2%, `nested_ancestry_200` -25.6%, `subsidizing_ancestry_200` -15.7%, `subsidizing_ancestry_50`
-60.2%.

Correctness held everywhere it could be checked: on the **32 fixtures where both traversals report
the tree exhausted, the scores agree 32 out of 32**, and the brute-force oracle confirms the optimum
on all 9 fixtures small enough to enumerate.

### The caveat: on its own it is a net regression

| | total fee the child pays |
| --- | --- |
| plain dive | 1,149,139 |
| deepening `eps=0.1`, replacing the dive | 1,194,554 (**+3.95%**) |

Two fixtures pay for all of it: `wallet_mixed_1000` (+39%) and `wallet_mixed_2000` (+70%). Both are
large pools that **never exhaust under any arm**. Deepening spends its budget re-expanding the
low-bound region and never dives deep enough to reach a good complete selection, so its incumbent
stays near the greedy seed. This is the anytime weakness of iterative deepening, and it is not
fixable by tuning: `eps` large enough to protect those two (4.0) is large enough to lose
`subsidizing_ancestry_50` entirely.

### The fix is to add it to the dive rather than substitute it for the dive

The incumbent only ever improves, so a search that dives first and then deepens *cannot* do worse
than the dive alone. Measured by splitting a 1000 ms budget in half and keeping the better answer:

| | total fee the child pays | improved | regressed |
| --- | --- | --- | --- |
| plain dive, whole clock | 1,149,139 | — | — |
| half dive + half deepening | **1,103,777 (-3.95%)** | 6 | 1 (+0.2%) |

The single regression is `wallet_mixed_1000` at +0.2%, and it is an artefact of the measurement
rather than the design: the two arms were run separately with half a budget each, so the dive lost
half its clock. **An in-crate hybrid that carries the incumbent from the dive into the deepening
passes cannot regress at all**, and that is the form to build.

### What the plan got wrong

1. **§9's staging is backwards**, as §11 already recorded: the strict schedule is unusable and the
   relaxed one is mandatory.
2. **§3's node target was derived from the wrong quantity.** It reasoned that iterative deepening
   must visit best-first's 55,737 nodes once per pass, predicting 55,737 x passes. The real figure is
   64,544 across all 8 passes *in total*, because the early passes are tiny — the cost is dominated
   by the last pass, not multiplied by the pass count.
3. **The plan never considered that deepening could lose.** It framed the risk entirely as
   re-expansion overhead on fixtures that had nothing to gain, and §7's outcome 3 proposed gating on
   `has_shared_ancestors()`. That gate would not have helped: `wallet_mixed_1000` and `_2000` both
   have shared ancestors. The real discriminator is whether the tree is exhaustible within the
   budget, which is not known in advance — hence the hybrid.
4. **§5 said nothing outside `bnb.rs` should need to change.** One public entry point was needed on
   `CoinSelector` so the old behaviour stays the default and the control run is possible at all.
