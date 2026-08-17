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

Only improving swaps are kept, so **the selection this leaves is never worse than the one it was
given**. It is a hill climb and stops at a local optimum, not a proof of anything.

Gated on `has_shared_ancestors`: with each ancestor reachable from one candidate there is nothing
set-dependent for the order to have got wrong, and the pass would be a pure cost.

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

## Cost

Everything that scales with the pool happens once, before the loop. Getting there took two goes:

| version | 200,000 candidates | answers |
| --- | --- | --- |
| rebuild replacement set + view per accepted swap | 264 ms | — |
| pool-sized work hoisted out of the loop | 15 ms | byte-identical |
| partition the replacement list instead of sorting it | **12 ms** | byte-identical |

The first was more expensive than the search it was meant to be a cheap addition to. The last one is
because only the head of the replacement list is ever read — a pass looks at 40 of it, and the front
advances only as swaps consume entries — so sorting 200,000 entries to read a few hundred was 3 ms
wasted.

As it stands: **12 ms against a 113 ms search at 200,000 candidates, 1.1 ms against 100 ms at
20,000**, and zero where the gate declines.

## The two constants

`REPAIR_REPLACEMENTS_PER_PASS = 40` — replacements considered per pass, read best-value first, so the
tail is coins that cannot cover what the swap gives up anyway.

`DEFAULT_REPAIR_SWAPS = 1_000` — a ceiling on the cost, not a target. 1,000, 20,000 and 100,000
return byte-identical selections on every scale fixture, and the most any fixture actually took was
892.

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
