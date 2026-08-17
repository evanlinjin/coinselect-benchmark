# Strategies for beating Core everywhere

Every fixture Bitcoin Core still wins, why it wins it, and what could be done about it — ranked by
what the evidence supports rather than by how interesting the idea is.

[`FINDINGS.md`](FINDINGS.md) is what the pinned revision measures; [`EXPERIMENTS.md`](EXPERIMENTS.md)
logs what has been tried; this is the queue of what to try next.

**Status.** All six strategies below have now been measured. One survives and is built
([`pr/pr-repair.md`](pr/pr-repair.md)); three are rejected on evidence; one is rejected on cost; one
turned out not to be a separate change at all. The measurements are kept whether or not they
supported the idea — a rejected strategy with a number attached is worth more than an untried one.

## Where Core still wins

"Core no longer wins the fee column anywhere" was true of **one budget on one fixture set**, and both
qualifiers mattered.

### It changes with the budget

The 42-fixture matrix, coin-select's package fee against Core's, at a wall-clock budget instead of a
round budget:

| budget | coin-select wins | fixtures Core takes |
| --- | --- | --- |
| 1 ms | 37 / 42 | `nested_ancestry_200`, `shared_ancestry_100`, `subsidizing_ancestry_100`, `subsidizing_ancestry_50` |
| 3 ms | 39 / 42 | `nested_ancestry_200`, `subsidizing_ancestry_50` |
| 10 ms | 40 / 42 | `subsidizing_ancestry_50` |
| 100 ms | **41 / 42** | — |
| 1000 ms | **41 / 42** | — |
| 100,000 rounds | **41 / 42** | — |

(The 42nd is `high_feerate_20`, a tie at an optimum the oracle proves by enumerating all 2^20
subsets. It is not winnable.)

Core's answers do not improve with more time here — it is not exhausting anything either. What
changes is that coin-select needs somewhere between 10 ms and 100 ms to overtake it on the ancestry
fixtures, and under that it is still climbing.

### It changes with the pool

The scale tier now runs **every family at 20,000 candidates**, which is new — it previously covered
three of eight, and the two shapes that stress the search hardest were not among them. At a 100 ms
budget, before the repair pass below:

| fixture | coin-select | Bitcoin Core | |
| --- | --- | --- | --- |
| `shared_ancestry_20000` | 1,232,220 | **1,226,740** | Core by 0.45% |
| `shared_ancestry_200000` | 1,331,840 | **1,328,243** | Core by 0.27% |
| `nested_ancestry_20000` | 1,386,060 | **1,383,010** | Core by 0.22% |
| `private_ancestry_20000` | **519,320** | 520,061 | coin-select by 0.14% |
| `subsidizing_ancestry_20000` | **5,357,280** | 5,379,600 | coin-select by 0.42% |
| `wallet_mixed_20000` | **707,660** | 756,450 | coin-select by 6.9% |
| `adversarial_shared_20000` | **241,710** | 297,020 | coin-select by 19% |

**At 20,000 candidates the margins collapse.** On the small fixtures coin-select wins ancestry
families by 30–50%; here every ancestry family is inside half a percent in one direction or the
other. Whatever separates the engines at this size is not the search.

## Why it loses, measured

The three losses decompose identically. `tools/whyscale.py` splits the gap into the only three things
that can produce it — inputs taken, child weight, ancestor bumping:

| | `shared_ancestry_20000` | `nested_ancestry_20000` | `shared_ancestry_200000` |
| --- | --- | --- | --- |
| inputs, cs − core | −1 | −1 | 0 |
| child weight, cs − core | −272 | −272 | +172 |
| parents dragged in, cs − core | **+1** | 0 | **+1** |
| ancestor bump, cs − core | **+4,912** | **+3,087** | **+2,616** |
| package fee, cs − core | +5,480 | +3,050 | +3,597 |
| **share of gap that is bumping** | **90%** | **101%** | **73%** |

coin-select takes *one fewer input* and builds a *lighter child* — worth about 680 sat — and then
gives it all back and more by dragging in an ancestor nobody else is paying for. It is buying a
marginally better coin by value-per-weight and paying for a parent to get it.

**The control that isolates the mechanism.** `private_ancestry_20000` has the same shape at the same
size, but every ancestor belongs to exactly one candidate. Bump: **218,289 for both engines**, parents
dragged in: **108 for both**. With nothing shared there is nothing set-dependent to get wrong, and
coin-select wins on child weight alone.

So the losses are not "ancestry is hard". They are specifically **shared** ancestry: what a coin costs
depends on which other coins are already selected, and a sort key over individual coins cannot
express that.

**And the search does not rescue it.** On `shared_ancestry_20000` coin-select runs 370,432 rounds and
returns *the greedy seed, unimproved*. At this pool size the ordering is the entire answer.

---

## Strategies

### 1. A local repair pass over the returned selection — *measured, built*

The failure is a one-coin error: one parent too many, one parentless coin too few. So fix it after
the fact. Take the answer, and for each selected coin holding a parent no other selected coin shares,
try replacing it with an unselected coin that adds no new ancestor. Keep swaps the metric scores
better; repeat until nothing improves.

Built as `CoinSelector::repair`, run by `run_bnb` by default and gated on `has_shared_ancestors`.
Across all 52 fixtures at a 100 ms budget it **improves 10 and worsens none**:

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

Every one of the three scale losses becomes a win with about 10% to spare. It cannot score worse by
construction — only improving swaps are kept — though review showed that is a claim about the score
and not about the result: it deselects, which nothing else in the crate does, and it had to be taught
not to evict an input the caller required. Beyond that, `tools/randomsweep.py` checks that
against pools the fixture set does not contain, since the last review of this stack found a
regression the 42 fixtures could not see: **2,800 randomly seeded pools, no regression, every
repaired selection passing the verifier**. A first version of that check ran under a wall-clock
deadline and reported five regressions, all of which vanished on a round budget — one of them on a
pool with no shared ancestry, where the pass returns immediately. Under a deadline the two arms
search different numbers of rounds, so it was measuring the scheduler.

**The precondition this had, and how it was discharged.** The Python emulation minimised the
harness's package fee, which is what both engines are scored on but *not* what `LowestFee` minimises
— the metric also charges for spending the change output later. The in-crate version hill-climbs on
the metric's own score, and lands on the same three answers to the satoshi. The emulation was not
being more permissive than the metric.

**What it cost to make cheap.** The first version rebuilt the replacement set and the view on every
accepted swap: 264 ms on 200,000 candidates, more than the search it was meant to be a cheap addition
to. Doing the pool-sized work once brought that to 15 ms, and partitioning the replacement list
instead of fully sorting it — only its first few hundred entries are ever read — to 12 ms, against a
113 ms search. At 20,000 candidates it is 1.1 ms against 100 ms. Answers byte-identical throughout.

**Its swap budget is a ceiling, not a target.** 1,000, 20,000 and 100,000 swaps return byte-identical
selections on every scale fixture, and the most any fixture actually took was 892.

### 2. Gate the ancestry-aware ordering on density, not on pool size — *rejected on cost*

[PR #76][pr76] adds a second greedy seed keyed on `(value − own bump) / weight`. It closes 91% of the
gap at 200,000 candidates and changes nothing at 20,000, so the idea was to take it only when a
computable ratio — a parent's charge over the value gap between adjacent coins, 28 at 200,000 and 2.5
at 20,000 — says it will pay.

Measuring what the gate would buy killed it. The seed's cost is the sort it does:

| | with the seed | without it | the seed costs |
| --- | --- | --- | --- |
| `shared_ancestry_20000` | 3.57 ms | 3.71 ms | *under the noise floor* |
| `nested_ancestry_20000` | 3.97 ms | 2.70 ms | ~1 ms |
| `shared_ancestry_200000` | 57.85 ms | 38.66 ms | ~19 ms |
| `wallet_mixed_200000` | 53.95 ms | 37.09 ms | ~17 ms |

(`no_ancestry_20000` moves 2.06 → 3.04 ms with a seed that returns immediately on it, which is the
noise floor for these numbers.)

So the gate would save **under a millisecond of a 100 ms budget** at the size where the seed is
inert, and its whole cost sits at the size where it is not. Against that, a mis-tuned threshold
costs real fee: with the repair pass already in place, removing the seed still costs 63% on
`wallet_mixed_200000`. Under a millisecond of saving is not worth a knob that can lose that.

### 3. Re-key candidates as ancestry gets paid for — *rejected, identical prefix*

Once a coin on a shared parent is selected, every other coin on that parent becomes cheaper: the bump
is already paid. A dynamic key would drop those coins' charge to zero as the search descends. This
was rejected at n=50 on an argument that did not obviously carry to 20,000 candidates, where the same
charge is worth 2.5 positions rather than 0.001, so it was re-measured there.

It produces the **identical prefix** to the static `(value − own bump) / weight` key — which is
PR #76's key, already in the crate. On `nested_ancestry_20000` both land on 4,907,127 against the
plain key's 4,916,838; on `shared_ancestry_20000` every key tested lands on the same 3,545,953.

The n=50 argument holds after all, and for the reason given then: re-keying only ever *reduces* a
candidate's charge, by at most its own bump, so it can only move the order less than the static key
already does. The strategy is a strictly weaker version of something shipped.

### 4. Select at the granularity of a cluster, not a coin — *rejected, no measured headroom*

The cost being got wrong is per-*cluster*: a fat underpaying root and everything hanging off it.
Coins in a cluster are cheap together and expensive apart, and every representation in the crate is
per-candidate. Selecting whole clusters would express directly what no per-candidate key can. It is
by far the most invasive idea here — it attacks the representation rather than working around it — so
it needs headroom to justify itself.

There is none to find. The repair pass converges long before its budget:

| fixture | 0 swaps | 1,000 | 4,000 | 20,000 | 100,000 |
| --- | --- | --- | --- | --- | --- |
| `shared_ancestry_20000` | 1,232,220 | 1,107,760 | 1,107,760 | 1,107,760 | 1,107,760 |
| `nested_ancestry_20000` | 1,386,060 | 1,224,980 | 1,224,980 | 1,224,980 | 1,224,980 |
| `wallet_mixed_20000` | 707,660 | 351,200 | 351,200 | 351,200 | 351,200 |

A hundredfold more search of the same neighbourhood finds nothing. That is not proof of optimality —
it is a local optimum under one move type, and a cluster-granularity search explores moves this
cannot reach. But rewriting the crate's representation on the strength of an unmeasured hope is the
wrong order to do things in, and the cheap thing to try first is a *different move type* in the
existing pass (drop-without-replacement, two-for-one), not a new representation.

### 5. Take Core's ordering as one more seed — *rejected, identical prefix*

Core charges each coin its *full individual* bump inside effective value before searching. That
over-charges shared parents — two coins on one parent each pay for it in full — where coin-select's
key charges nothing, so it is wrong in the opposite direction, and at scale over-charging was the
better error. A portfolio of seeds had been ruled out on the *small* fixtures, so this was re-run at
20,000.

Same answer as at 50. Core's effective-value order, value descending, value-per-weight and both
ancestry-adjusted variants all produce the **identical prefix** on both hard scale fixtures. There is
nothing to add to the portfolio, because every value-based key is the same key here.

### 6. Spend the budget differently on huge pools — *answered by strategy 1, not a separate change*

On `shared_ancestry_20000` the search burns 370,432 rounds and improves on the seed exactly zero
times, so the question was whether that time is better spent elsewhere.

It is, and the repair pass is where — but it does not need the budget, which is why this is not a
separate change. Repair reaches the same answer from a 10 ms search as from a 100 ms one, and closes
two of the four fixtures Core takes at a 1 ms budget:

| fixture | budget | Core | coin-select | + repair |
| --- | --- | --- | --- | --- |
| `nested_ancestry_200` | 1 ms | 32,980 | 37,940 | **29,580** |
| `shared_ancestry_100` | 1 ms | 18,220 | 21,040 | **17,900** |
| `subsidizing_ancestry_100` | 1 ms | 58,460 | 81,050 | 81,050 |
| `subsidizing_ancestry_50` | 1 ms | 29,690 | 44,990 | 44,990 |

The two it does not close are not one-swap errors — coin-select is 51% behind on
`subsidizing_ancestry_50` at 1 ms, and repair takes no swap at all. Those need search time, and
reallocating away from the search is exactly the wrong move for them.

## What is not worth trying again

- **Pool sampling.** Worth −10.28% against a plain dive; equal or worse now that deepening is the
  default, at every budget from 1 ms to 100 ms.
- **A portfolio of value-based greedy seeds.** Every value-based key — Core's effective value, value
  descending, value per weight, and two ancestry-adjusted variants — produces the *identical* prefix,
  on the small fixtures and at 20,000 alike. See strategies 3 and 5.
- **Handing back from deepening to the dive when deepening stalls.** Two versions, byte-identical
  results on all 42 fixtures.

## What is left

Nothing in this list. The open questions the measurements raised are:

- **A different move type in the repair pass.** It is a hill climb over one-for-one swaps where the
  incoming coin drags in nothing new. Drop-without-replacement and two-for-one are untested and
  cheap to add to the existing pass, unlike strategy 4.
- **The two fixtures repair cannot touch at 1 ms.** `subsidizing_ancestry_50` and
  `subsidizing_ancestry_100` are behind by 51% and 39% at that budget, which is a search problem, not
  an ordering one — the only remaining loss whose mechanism is not understood.

[pr76]: https://github.com/bitcoindevkit/coin-select/pull/76
