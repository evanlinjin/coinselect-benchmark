# Strategies for beating Core everywhere

Every fixture Bitcoin Core still wins, why it wins it, and what could be done about it — ranked by
what the evidence supports rather than by how interesting the idea is.

[`FINDINGS.md`](FINDINGS.md) is what the pinned revision measures; [`EXPERIMENTS.md`](EXPERIMENTS.md)
logs what has been tried; this is the queue of what to try next.

## Where Core still wins

"Core no longer wins the fee column anywhere" is true of **one budget on one fixture set**, and both
qualifiers matter.

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
budget:

| fixture | coin-select | Bitcoin Core | |
| --- | --- | --- | --- |
| `shared_ancestry_20000` | 1,232,220 | **1,226,740** | Core by 0.45% |
| `shared_ancestry_200000` | 1,331,840 | **1,328,243** | Core by 0.27% |
| `nested_ancestry_20000` | 1,386,060 | **1,383,010** | Core by 0.22% |
| `private_ancestry_20000` | **462,039** | 462,780 | coin-select by 0.14% |
| `subsidizing_ancestry_20000` | **3,259,134** | 3,262,128 | coin-select by 0.09% |
| `wallet_mixed_20000` | **595,756** | 639,659 | coin-select by 6.9% |
| `adversarial_shared_20000` | **241,710** | 297,020 | coin-select by 19% |
| `high_feerate_20000` | **2,610,477** | 2,881,913 | coin-select by 9.4% |
| `no_ancestry_20000` | **244,000** | 277,300 | coin-select by 12% |

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

### 1. A local repair pass over the returned selection — *measured, closes every loss*

The failure is a one-coin error: one parent too many, one parentless coin too few. So try fixing it
after the fact. Take the answer, and for each selected coin holding a parent no other selected coin
shares, try replacing it with an unselected coin that adds no new ancestor. Keep swaps that lower the
fee; repeat until nothing improves.

Emulated in Python over about 4,000 swap evaluations:

| fixture | Core | coin-select | after repair | |
| --- | --- | --- | --- | --- |
| `shared_ancestry_20000` | 1,226,740 | 1,232,220 | **1,107,760** | −10.1% |
| `nested_ancestry_20000` | 1,383,010 | 1,386,060 | **1,224,980** | −11.6% |
| `shared_ancestry_200000` | 1,328,243 | 1,331,840 | **1,196,830** | −10.1% |

Every loss becomes a win with about 10% to spare, for work that is trivial next to the 370,000 rounds
the search already spends.

**The control that makes this trustworthy:** run the same pass with the swap budget set to zero and it
reproduces the engine's own package fee to the satoshi on both fixtures. The improvement is the swaps,
not the emulation being more permissive than the metric. (A first version had no feasibility
constraint and cheerfully reported *negative* fees; a second held the change output fixed and found
nothing, because almost every swap needs the change to absorb the difference.)

**What is still unproven.** The repair minimises the harness's package fee, which is what both engines
are scored on, but not exactly what `LowestFee` minimises — the metric also charges for spending the
change output later. An in-crate version has to hill-climb on the metric's own score, and the win may
be smaller there. That is the first thing to check before building it.

### 2. Gate the ancestry-aware ordering on density, not on pool size — *half-measured*

[PR #76][pr76] adds a second greedy seed keyed on `(value − own bump) / weight`. It closes 91% of the
gap at 200,000 candidates and changes **nothing** at 20,000, which is exactly where two of the three
losses are.

The reason is measured: what the key buys is the ratio of a parent's charge to the value gap between
adjacent coins in the order. That ratio is 28 at 200,000 and 2.5 at 20,000, and below about 3 nothing
crosses the prefix cutoff. Both quantities are cheap to compute before the search starts, so the seed
could be taken when the ratio says it will pay rather than always.

This does not fix the 20,000 losses on its own — at that density the key genuinely cannot reach them —
but it stops the seed being dead weight and makes the threshold explicit rather than accidental.

### 3. Re-key candidates as ancestry gets paid for — *previously rejected at n=50, untested at scale*

Once a coin on a shared parent is selected, every other coin on that parent becomes cheaper: the bump
is already paid. A dynamic key would drop those coins' charge to zero as the search descends.

This was measured on `subsidizing_ancestry_50` and rejected: re-keying only ever *reduces* a
candidate's charge, by at most its own bump, so it moves the order strictly less than the static key
did — and the static key moved nothing there, because ancestor bumps were three orders of magnitude
too small to reorder the top of a 50-coin sort.

**That argument does not carry to 20,000 candidates**, where the same charge is worth 2.5 positions
instead of 0.001, and where the whole gap is one shared parent. Worth re-measuring at scale before
being written off. It is also more expensive than it looks: the re-key is only needed when the
selected or banned ancestor set changes, but that is most nodes.

### 4. Select at the granularity of a cluster, not a coin — *unmeasured*

The cost being got wrong is per-*cluster*: a fat underpaying root and everything hanging off it. Coins
in a cluster are cheap together and expensive apart, and every representation in the crate is
per-candidate.

Selecting whole clusters, or scoring the marginal cost of the first coin from a cluster differently
from later ones, would express directly what no per-candidate key can. This is the most invasive idea
here and the only one that attacks the representation rather than working around it.

### 5. Take Core's ordering as one more seed — *cheap to try*

Core charges each coin its *full individual* bump inside effective value before searching. That
over-charges shared parents — two coins on one parent each pay for it in full — and the discount
comes back only after a result is chosen. It is wrong in the opposite direction from coin-select's key,
which charges nothing.

At scale, over-charging beats not charging. Since [PR #76][pr76] already established the pattern of
taking a second greedy prefix and keeping whichever scores better, adding Core's ordering as a third
costs one more greedy pass. A portfolio of seeds was ruled out on the *small* fixtures — every
value-based key produced the identical prefix — but that test was on `subsidizing_ancestry_50`, not at
20,000.

### 6. Spend the budget differently on huge pools — *diagnosis only*

On `shared_ancestry_20000` the search burns 370,432 rounds and improves on the seed exactly zero
times. Whatever those rounds are doing, it is not finding a better answer. Options, in increasing
order of ambition: stop early and hand the time to strategy 1; sample the pool (measured as equal or
worse now that deepening is in); or accept that the ordering is the whole algorithm at this size and
put the effort there.

## What is not worth trying again

- **Pool sampling.** Worth −10.28% against a plain dive; equal or worse now that deepening is the
  default, at every budget from 1 ms to 100 ms.
- **A portfolio of value-based greedy seeds on small pools.** Core's effective-value order, value
  descending, and two ancestry-adjusted variants all produce the *identical* prefix on the three hard
  small fixtures.
- **Handing back from deepening to the dive when deepening stalls.** Two versions, byte-identical
  results on all 42 fixtures.

[pr76]: https://github.com/bitcoindevkit/coin-select/pull/76
