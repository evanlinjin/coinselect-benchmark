# Fixture format and adapter semantics

One fixture describes one coin-selection problem: a pool of candidate UTXOs, the unconfirmed
transactions some of them sit on, what is being funded, and the feerates in force. Both runners
read the same file. Regenerate with `python3 genfixtures.py`; `--check` fails if the checked-in
files are stale.

## Schema

```json
{
  "name": "shared_ancestry_50",
  "family": "shared_ancestry",
  "size": 50,
  "seed": 2261184397,
  "search_budget": 100000,

  "feerate_sat_per_vb": 10,
  "long_term_feerate_sat_per_vb": 10,
  "discard_feerate_sat_per_vb": 3,
  "dust_relay_feerate_sat_per_vb": 3,

  "target":  { "value": 6348000, "n_outputs": 1, "non_input_weight": 212 },
  "change":  { "output_weight": 172, "spend_weight": 232 },
  "max_weight": null,

  "candidates": [
    { "id": "c000", "value": 123456, "input_weight": 272,
      "input_type": "p2wpkh", "is_segwit": true, "residing_txid": "s00" }
  ],
  "ancestors": [
    { "txid": "s00", "weight": 1200, "fee": 300, "parents": [] }
  ]
}
```

| field | meaning |
| --- | --- |
| `feerate_sat_per_vb` vs `long_term_feerate_sat_per_vb` | Equal in every family except `high_feerate`. See that row below for why one family deliberately separates them. |
| `search_budget` | Node budget for both searches. Must be `100000`: that is Core's compile-time `TOTAL_TRIES`, and the Core runner refuses anything else rather than compare unequal budgets. |
| `feerate_sat_per_vb` | Target (effective) feerate. Integer, see [Weights](#weights-are-multiples-of-4). |
| `long_term_feerate_sat_per_vb` | Feerate at which spending the change output later is priced. |
| `discard_feerate_sat_per_vb` | Feerate below which change is dropped to fees; feeds `cost_of_change`. |
| `dust_relay_feerate_sat_per_vb` | Feerate the change output's dust threshold is derived from. |
| `target.value` | Sum of the recipient outputs' values, in satoshis. |
| `target.n_outputs` | Number of recipient outputs. |
| `target.non_input_weight` | Whole non-input weight of the child transaction: `nVersion` + `nLockTime` (32 WU), the output-count varint, the recipient outputs, and the 2 WU segwit marker and flag. Excludes the input-count varint. |
| `change.output_weight` | Weight of the change `TxOut`, excluding any output-count varint change. |
| `change.spend_weight` | Weight of the input that will spend the change output later. |
| `max_weight` | Cap on the **child** transaction's weight, or `null`. Ancestor weight never counts toward it. |
| `candidates[].id` | Stable identifier. Selections are reported as lists of these. |
| `candidates[].input_weight` | Full `txin` weight: outpoint, `nSequence`, `scriptSig` and its length, and the witness. For a legacy input this excludes the empty-witness byte (see below). |
| `candidates[].input_type` | Informational label (`p2wpkh`, `p2tr`, `p2sh_p2wpkh`, `p2pkh`). |
| `candidates[].is_segwit` | Whether spending this UTXO contributes a witness. |
| `candidates[].residing_txid` | The `ancestors` entry that created this UTXO, or `null` when it is confirmed. |
| `ancestors[].txid` | Identifier, referenced by `residing_txid` and by other ancestors' `parents`. |
| `ancestors[].weight` | Weight of the unconfirmed transaction. |
| `ancestors[].fee` | Fee it already pays. |
| `ancestors[].parents` | Direct parents. A parent not listed in `ancestors` is confirmed and ignored. |

**The ancestor list is the set that still requires bumping.** That is what coin-select's
`AncestorToBump` means, and deciding it is the caller's job, not the selection algorithm's: a
wallet works out which unconfirmed ancestors a miner would take anyway and passes only the rest.
A fixture must not list an ancestor whose package already clears the target feerate. Listing one
would credit the child with a surplus nobody is waiting on, and would make the two engines
disagree about the ancestor set rather than about coin selection.

Both `genfixtures.py --check` and the Core runner enforce this by building the mock block template
(the same determination `node::MiniMiner` makes) and rejecting the fixture if it mines anything.
Note that an ancestor can pay far above the target rate on its own and still belong here: what
matters is its whole ancestor package, which is exactly what the `subsidizing_ancestry` family is
built around.

`genfixtures.py --check` also enforces: unique ids and txids, an acyclic ancestor graph, every
`residing_txid` and `parents` entry resolving inside `ancestors`, and a pool that can cover the
target.

## Weights are multiples of 4

Core prices coins in **vbytes**; coin-select prices them in **weight units**. Left alone, that
difference alone would move the two engines' targets apart by a few satoshis per input and
muddy every comparison with rounding noise.

Every generated weight is therefore a multiple of 4, and every feerate is an integer number of
satoshis per vbyte. With both constraints, `CFeeRate::GetFee(vbytes)` and
`FeeRate::implied_fee(weight_units)` produce **exactly the same number of satoshis**, so any
difference in the results is a difference in the algorithms rather than in the arithmetic.

The listed input weights are real script types rounded up to the next multiple of 4 — which is
precisely what Core charges anyway, since it converts each input to vbytes with
`GetVirtualTransactionSize`:

| type | real weight | fixture weight |
| --- | --- | --- |
| `p2wpkh` | 271 | 272 |
| `p2tr` (keyspend) | 230 | 232 |
| `p2sh_p2wpkh` | 363 | 364 |
| `p2pkh` | 592 | 592 |

Both runners reject a fixture whose weights are not multiples of 4.

## The shared transaction model

`bench.py report` scores every selection — from either runner — with one implementation of this
model, so the quality columns are always comparable:

```
child weight = target.non_input_weight
             - 2                              if no selected input is segwit
             + 4 * varint_size(n_inputs)
             + sum(candidates[].input_weight)
             + n_legacy_inputs                if any selected input is segwit
             + change.output_weight           if the selection has change
             + 4 * (varint_size(n_outputs + 1) - varint_size(n_outputs))

child fee     = sum(selected values) - target.value - change value
ancestor union = transitive unconfirmed ancestors of the selection, each counted once
package fee    = child fee + fees already paid by the ancestor union
package weight = child weight + weight of the ancestor union
```

The verdict the report applies to both runners is `package fee >= feerate * ceil(package weight / 4)`:
does the transaction actually drag its whole ancestor union up to the target feerate?

## Adapter conversions

Every place a runner has to translate is listed here.

### coin-select (`rust-runner`)

| fixture | becomes |
| --- | --- |
| `target.value`, `target.n_outputs` | `TargetOutputs::{value_sum, n_outputs}` |
| `target.non_input_weight` | `TargetOutputs::weight_sum`, minus `TX_FIXED_FIELD_WEIGHT`, minus the output-count varint, minus 2. The crate adds all three back — the 2 only when a segwit input is selected — so a selection with at least one segwit input reproduces `non_input_weight` exactly. A wholly legacy selection lands 2 WU lighter, which is correct: such a transaction has no witness section. |
| `feerate_sat_per_vb` | `TargetFee::rate`, with `absolute: 0` and `replace: None` |
| `max_weight` | `Target::max_weight` |
| `change.*` | `DrainWeights { output_weight, spend_weight, n_outputs: 1 }` |
| each candidate | one `Input<u32>`, and therefore one single-input `InputGroup`. Address grouping is off: one fixture candidate is one candidate here and one `OutputGroup` on the Core side. |
| `residing_txid: null` | `u32::MAX`, which is outside the ancestor set, so `SelectionProblem::new` treats it as confirmed |
| each ancestor | one `AncestorToBump<u32>` |

### Bitcoin Core (`core-runner`)

| fixture | becomes |
| --- | --- |
| `target.non_input_weight` | `tx_noinputs_size = (non_input_weight + 4) / 4` vbytes. The `+ 4` is the input-count varint, which Core's own `tx_noinputs_size` carries (it assumes 1 vbyte) and the fixture field does not. Fixtures have at most 252 inputs, so 1 vbyte is exact. |
| `target.value` | `selection_target = value + effective_feerate.GetFee(tx_noinputs_size)` |
| `max_weight` | `m_max_tx_weight`, then `max_selection_weight = max_weight - tx_noinputs_size * 4`, as `ChooseSelectionResult` computes it. `null` means `MAX_STANDARD_TX_WEIGHT`. |
| `change.output_weight` / `spend_weight` | `change_output_size` / `change_spend_size`, in vbytes |
| feerates | `CFeeRate(sat_per_vb * 1000)` |
| each candidate | one `COutput` (`input_bytes = input_weight / 4`, `depth = 0` when unconfirmed else `1`) in its own `OutputGroup`. The outpoint is a fixed dummy txid with the candidate's index as the output number, which keeps `OutputSet` iteration in fixture order. |
| each ancestor | an entry in the fixture's "mempool", from which individual and combined bump fees are derived (below) |

Two things about Core's flow are deliberately not modelled, because both are about grouping
rather than about selection:

- **Address grouping** (`m_avoid_partial_spends`) is off: one fixture candidate is one
  `OutputGroup`, which is what makes a fixture candidate mean the same thing to both engines.
- **Output-type separation.** Core's `AttemptSelection` first runs the whole portfolio once per
  output type and only searches the combined pool if no single type can fund the transaction. The
  runner always searches the combined pool, i.e. Core's `allow_mixed_output_types` fallback. Only
  `wallet_mixed` has more than one type, and a per-type pass would just be the same search over a
  smaller pool.

Derived exactly as `wallet/spend.cpp` derives them: `m_change_fee`, `m_cost_of_change`,
`m_min_change_target` (via Core's own `GenerateChangeTarget` with a deterministic
`FastRandomContext`), and `min_viable_change = max(discard_fee_to_spend_change + 1, dust)` where
`dust` is `dust_relay_feerate.GetFee(change_output_size + change_spend_size)`.

### Ancestor bump fees

Given a correctly formed ancestor list (see above), the two engines arrive at the *same* final
figure — the harness confirms they agree on every selection in the matrix. What differs is when
each of them knows it:

- **coin-select** charges `max(0, feerate * union_weight - union_fee)` over the whole ancestor
  union, netted in one go and floored at zero, computed afresh for each selection *during* the
  search. Within the union an ancestor paying above the target rate offsets one paying below it.
- **Core** charges each UTXO, *during the search*, the individual bump fee of the transaction it
  sits on: `max(individual shortfall, ancestor-set shortfall)`, baked into its effective value
  before the search starts. Two coins sharing an ancestor are each charged for it in full. Only
  after a result has been chosen is the overlap refunded, as
  `SelectionResult::bump_fee_group_discount`. `node::MiniMiner` supplies both the individual
  figures and the combined one.

`core-runner/mini_miner_lite.h` ports that algorithm from the pinned Core source; `bench.py`
reimplements it independently and the report asserts the two agree on every selection. Three
things do not carry over from a real mempool, all forced by the fixture format:

1. The fixture's ancestor list *is* the mempool. Core would also pull in unrelated transactions
   sharing a cluster; a fixture has none.
2. Ancestor-feerate ties break on the fixture txid rather than on a real txid hash.
3. Nothing is conflicted, so there are no to-be-replaced transactions.

### Known residual fee-model gaps

Two differences survive the multiple-of-4 discipline. Both are constant, both are reported rather
than hidden, and neither depends on which coins get selected:

- **The empty witness of a legacy input.** A legacy input in a transaction that has a witness
  section still serialises a zero-length witness, 1 WU. coin-select charges it;
  `COutput::input_bytes` does not. A Core selection with legacy inputs can therefore land up to
  `feerate * ceil(n_legacy / 4)` satoshis under the target feerate. The report classifies a
  shortfall within that bound as this known gap and flags anything larger as a failure.
- **The input-count varint above 252 inputs.** Core prices it as a flat 1 vbyte — its own
  `SelectionResult::GetChange` comment says so — while the shared model charges
  `4 * varint_size(n_inputs)`. Past 252 selected inputs that is 2 vbytes short. Only the
  thousand-candidate fixtures select enough inputs to reach it.
- **The segwit marker on an all-legacy selection.** Core's `tx_noinputs_size` always includes it;
  coin-select adds it only when a segwit input is selected. Worth 2 WU, and only reachable by a
  selection containing no segwit input at all.

## Datasets

Seven families at sizes 20, 50, 100 and 200, plus a `smoke` fixture of 8 candidates for CI.

| family | what it exercises |
| --- | --- |
| `no_ancestry` | Control: every coin confirmed. Any difference here is pure search behaviour. |
| `private_ancestry` | Every third coin sits on an unconfirmed parent nothing else can reach, so the bump folds into the candidate and no de-duplication is needed. |
| `shared_ancestry` | A few unconfirmed parents host several coins each: the overlap Core discounts after the fact and coin-select nets during the search. |
| `nested_ancestry` | Chains three to four deep that share a common root — transitive *and* shared. |
| `subsidizing_ancestry` | A fat underpaying root spent by a child paying four times the target rate and by a sibling paying a tenth of it. Every package is still below target, so all three legitimately need bumping — but coin-select nets the rich child's surplus against its sibling's deficit while it searches, where Core charges each coin its own bump and refunds the overlap only afterwards. |
| `wallet_mixed` | Mixed script types and values, a third of the coins unconfirmed, and a `max_weight` cap tight enough to bite. |
| `high_feerate` | The `wallet_mixed` shape at 40 sat/vB against a 10 sat/vB long-term feerate. Puts Core's `CoinGrinder` inside the `> 3x long-term` gate its portfolio applies, and keeps Core's waste metric non-degenerate: at `feerate == long_term_feerate` every input's `fee - long_term_fee` is zero, so waste collapses to excess alone. |
| `adversarial_shared` | One fat, badly underpaying ancestor hosting a block of small coins. Charged the whole bump each, every one of them has negative effective value and Core drops them from the BnB pool; together they clear the target and pay the bump once. |
