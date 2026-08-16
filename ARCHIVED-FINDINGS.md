# Archived findings

Results this harness measured but can no longer reproduce, because the code they were measured on
is gone. They are kept because the measurement was sound when it was taken and the conclusion still
stands — not because the current matrix backs them.

Everything here is reproducible from git history. Each entry names the harness commit and the two
pinned revisions it ran against; check that commit out and `python3 bench.py all --oracle` will
reproduce it.

---

## Core cannot act on the shared-ancestry discount during the search, and it costs real solutions

Measured at harness commit `07e1682`, against Bitcoin Core
`9be056a8a72b624dae9623b2f7bded92c2a21c91` (v31.1) and coin-select
`91f5cfeb1163f87a27059adbbe1de6af8afbb08b` ([PR #70][pr70]).

**Why it is archived rather than current.** This was the `kernel` track: Core's `SelectCoinsBnB` run
in isolation against coin-select's `LowestFeeChangeless`. [PR #73][pr73] removes the changeless
metrics from the crate, so there is nothing left to run on the coin-select side and the track has
been retired. The `wallet` track still shows the *outcome* as a fee difference, but only the
isolated changeless pairing shows the *mechanism*: Core's full portfolio recovers with
`KnapsackSolver` or single random draw, which hides the fact that its branch and bound could not see
the selection at all.

This is the sharpest evidence in the repository that ancestor-aware effective values are worth
having, and it is the direct answer to [issue #67][issue67]. That is why it is preserved rather than
dropped.

### The finding

Core charges each UTXO the full individual bump fee of the transaction it sits on, baked into its
effective value *before* the search starts. Two coins on the same unconfirmed parent are each
charged for that parent in full. The overlap comes back only once a result has been chosen, as
`bump_fee_group_discount` — too late for the search to have used it.

The `smoke` fixture shows the sharpest form. `SelectCoinsBnB` gives up after 62 nodes with **no
solution**, while coin-select returns a five-input selection that the exhaustive oracle confirms is
the least-waste one available — waste 24460, matching the oracle exactly:

| | |
| --- | --- |
| Core's `selection_target` | 300540 |
| effective value the search sees | 298000 — below the target, so the branch is pruned |
| shared-ancestry discount for that set | 2700 (`c000` and `c002` both pay for parent `sh`) |
| effective value after the discount | 300700 — inside the window, waste 24460 |

Core is not choosing a worse selection here; it is structurally unable to see this one.

Across the eight fixtures small enough to brute force, `SelectCoinsBnB` fails to reach the
least-waste in-window selection on four, and every one of them has a non-empty ancestor union. It
finds the optimum on every fixture without one. **coin-select reaches the optimum of its own
objective on every one of the eight.**

| fixture | waste Core returned | best in-window waste | inputs Core took | inputs in the optimum |
| --- | --- | --- | --- | --- |
| `smoke` | no solution | 24460 | 0 | 5 |
| `shared_ancestry_20` | 5544 | 2046 | 4 | 9 |
| `subsidizing_ancestry_20` | 25270 | 24675 | 10 | 16 |
| `nested_ancestry_20` | 16609 | 16024 | 12 | 11 |

`shared_ancestry_20` is the largest gap: Core leaves 63% of the achievable waste on the table,
because during the search each of those nine coins looked like it had to pay for the shared ancestor
by itself.

The `adversarial_shared` family is the same effect at scale. One fat underpaying ancestor hosts a
block of small coins; charged the whole bump each, every one of them has negative effective value
and Core drops them from the BnB pool before the search starts. coin-select's union accounting sees
that taking several of them pays the bump once, and finds packages costing 4648 against Core's 7342
at n=100.

(The oracle enumerates every subset, including coins Core's positive-effective-value filter drops,
so "Core missed it" covers both the search and that filter. Both are part of how Core answers.)

### What would restore it to the live matrix

A changeless objective on the coin-select side, of any kind — the pairing needs both engines
constrained to changeless selections for the comparison to isolate the search rather than the change
decision. If one returns, reinstating the `kernel` track is a small change to `bench.py`, both
runners and `README.md`; the fixtures already carry everything it needs.

[pr70]: https://github.com/bitcoindevkit/coin-select/pull/70
[pr73]: https://github.com/bitcoindevkit/coin-select/pull/73
[issue67]: https://github.com/bitcoindevkit/coin-select/issues/67
