Branch and bound decides candidates one at a time in a fixed order, so no sort key it uses can
express *"this coin is cheap only because that other coin is already selected"*. Shared ancestry is
exactly that: the first coin off an unconfirmed parent pays the whole bump and every later one off
the same parent pays nothing, and a per-candidate key has to pick one of those two prices before it
knows which the coin will be.

This adds `CoinSelector::repair`, which corrects that after the fact.

## The problem, measured

Extending the [benchmark][bench]'s scale tier so every family runs at 20,000 candidates turned up
three fixtures Bitcoin Core still won. `tools/whyscale.py` decomposes the package-fee gap into the
only three things that can produce it:

| | `shared_ancestry_20000` | `nested_ancestry_20000` | `shared_ancestry_200000` |
| --- | --- | --- | --- |
| inputs, cs − core | −1 | −1 | 0 |
| child weight, cs − core | −272 | −272 | +172 |
| parents dragged in, cs − core | **+1** | 0 | **+1** |
| ancestor bump, cs − core | **+4,912** | **+3,087** | **+2,616** |
| package fee, cs − core | +5,480 | +3,050 | +3,597 |
| **share of gap that is bumping** | **90%** | **101%** | **73%** |

We take one fewer input and build a lighter child — worth about 680 sat — then give it all back and
more by dragging in a parent nobody else is paying for.

The control that isolates the mechanism is `private_ancestry_20000`: same shape, same size, but every
ancestor reachable from exactly one candidate. Both engines report an identical 218,289 bump over
identical 108 parents, and we win on child weight alone. So this is not "ancestry is hard" — it is
specifically **shared** ancestry, where what a coin costs depends on which other coins are selected.

And the search does not rescue it: on `shared_ancestry_20000` we run 370,432 rounds and return the
greedy seed unimproved. At this pool size the ordering *is* the answer.

## The change

Take a selected coin that is the only one paying for some ancestor, try replacing it with an
unselected coin that drags in nothing new, and keep the swap when the metric scores it better. Repeat
until nothing improves or the swap ceiling is reached.

Only improving swaps are kept, so **the score this leaves is never worse than the one it was
given**. It is a hill climb and stops at a local optimum, not a proof of anything.

**This is the one thing in the crate that deselects**, which is the part that needs care rather than
the swapping. Everything else — branch and bound, `select_srd` — only ever adds, so `run_bnb` has
always returned a superset of what the caller had selected, and that is how a required ("must spend")
input is expressed. `repair` therefore takes the protected set explicitly, and `run_bnb` passes the
selection it was handed. It also restores the caller's ban set first: the selector comes back
mid-traversal carrying every ban the exclusion frames on the path to that node applied, and those are
search state, not caller intent.

Gated on `has_shared_ancestors`, and then on whether *this selection* actually holds a coin that is
the sole payer for an ancestor. The first alone is not enough: it is a property of the problem and is
true as soon as one unconfirmed parent has two spendable outputs, which is the everyday shape of a
wallet that made a payment with change.

`run_bnb` runs it. `bnb_solutions` cannot — it is an iterator over improvements rather than a
finished answer — so callers driving that directly call `repair` themselves, which is what the
benchmark runner does.

## What it does

Across all 52 benchmark fixtures at a 100 ms budget it **improves 10 and worsens none**:

| fixture | before | after | |
| --- | --- | --- | --- |
| `wallet_mixed_200000` | 773,150 | **242,240** | −68.7% |
| `high_feerate_20000` | 2,717,840 | **1,246,960** | −54.1% |
| `wallet_mixed_20000` | 707,660 | **351,200** | −50.4% |
| `nested_ancestry_20000` | 1,386,060 | **1,224,980** | −11.6% |
| `shared_ancestry_200000` | 1,331,840 | **1,196,830** | −10.1% |
| `shared_ancestry_20000` | 1,232,220 | **1,107,760** | −10.1% |
| `shared_ancestry_500` | 89,990 | **82,120** | −8.8% |
| `shared_ancestry_1000` | 165,350 | **154,550** | −6.5% |
| `subsidizing_ancestry_20000` | 5,357,280 | **5,238,610** | −2.2% |
| `shared_ancestry_2000` | 301,090 | **296,360** | −1.6% |

All three fixtures Core held become wins with about 10% to spare, and coin-select now takes **every
fixture in the scale tier**. On the 42-fixture matrix at Core's own `TOTAL_TRIES` round budget it is
41 of 42 on fee against Core's 0 — the 42nd is a tie at an optimum the oracle proves by enumerating
all 2^20 subsets.

Every selection in that run is re-derived from the fixture by the harness: each package reaches the
target feerate once its ancestor union is counted, each stays inside `max_weight`, and each runner's
own bump figures match an independent recomputation.

**And the fixtures are not the only evidence.** The last review of this stack found a regression on
thousands of randomly generated pools that the fixture set could not see, so the same check was run
here: every ancestry family regenerated at every small size under 100 different seeds, the pass off
and on, under a fixed round budget. **2,800 pools, no regression, and every repaired selection passes
the verifier.**

That check needed a control of its own. A first version ran under a wall-clock deadline and reported
five regressions in 700 pools — all five vanished on a round budget, and one of them was on a pool
with no shared ancestry at all, where the pass returns immediately without looking at anything. Under
a deadline the two arms search different numbers of rounds, so it was measuring the scheduler.

## What review changed

The branch was reviewed before this was written up, and the review found the same *class* of problem
as the last one in this stack: a regression the 42 fixtures cannot see, because every fixture starts
from an empty selection.

**`run_bnb` was dropping caller-preselected inputs.** On a four-coin pool where the required input is
the sole payer for its parent, `run_bnb` returned a cheaper selection without it — silently. The
claim above originally read "the *selection* this leaves is never worse", which was true of the score
and false of the result: a lower score reached by evicting an input the caller required is worse, not
better. Fixed by passing the protected set, and by the regression test in `tests/ancestor.rs`.

The gate did not confine the damage either. `has_shared_ancestors` is a problem-level predicate while
the outgoing set is built from `drags_in`, which includes *private* ancestors — so one shared parent
anywhere in the pool exposed every privately-parented required coin.

**The search's transient bans were truncating the replacement pool**, so how much of it the pass
could see depended on where the last improvement happened to be found. Not a wrong answer, but it
made the measured benefit partly an artifact: the fixtures showing the largest gains are the ones
that return the ban-free greedy seed.

Also taken: an early-out for a selection holding no sole payer; the head-sizing comment claimed a
bound that is not true, since a swapped-in coin joins the selection and can be swapped out later;
`REPAIR_REPLACEMENTS_PER_PASS` made private, since nothing takes it as an argument; and the
round-trip test now says what it actually establishes.

Every fee figure above is unchanged by the fixes.

## Cost

Everything that scales with the pool happens once, before the loop. Getting there took three goes:

| version | 200,000 candidates, 1,000 swaps | answers |
| --- | --- | --- |
| rebuild replacement set + view per accepted swap | 264 ms | — |
| pool-sized work hoisted out of the loop | — | byte-identical |
| partition the replacement list instead of sorting it | 49.6 ms | byte-identical |
| skip taken replacements instead of compacting the list | **8.7 ms** | byte-identical |

The first was more expensive than the search it was meant to be a cheap addition to. The last was
found by review: `free.retain` per accepted swap was pool-sized work back inside the loop, which is
exactly what hoisting it out was for. It does not show on the benchmark's fixtures, which take few
swaps — on those the pass is **12 ms against a 113 ms search at 200,000 candidates and 1.1 ms against
100 ms at 20,000** — and it is 5.7× on a pool built so the swaps actually land.

## The constant

`DEFAULT_REPAIR_SWAPS = 1_000` — a ceiling on the cost, not a target. 1,000, 20,000 and 100,000
return byte-identical selections on every scale fixture, and the most any fixture actually took was
892. Public so a caller driving `bnb_solutions` can match what `run_bnb` does.

## What this is not

It does not help where the loss is not a one-swap error. At a 1 ms budget it closes
`nested_ancestry_200` and `shared_ancestry_100`, and takes no swap at all on
`subsidizing_ancestry_50`, where we are 51% behind — that is a search-time problem, not an ordering
one.

Four other approaches to the same three losses were measured and rejected, recorded in the
benchmark's [`STRATEGIES.md`][strategies]: re-keying candidates dynamically as ancestry gets paid for
and adding Core's effective-value ordering as a seed both produce the *identical* prefix at 20,000
candidates; cluster-granularity selection has no measured headroom, since 100× more swaps of this
pass find nothing further; and gating PR #76's seed on density would save under a millisecond of a
100 ms budget.

[bench]: https://github.com/evanlinjin/coinselect-benchmark
[strategies]: https://github.com/evanlinjin/coinselect-benchmark/blob/master/STRATEGIES.md
