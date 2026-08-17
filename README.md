# coinselect-benchmark

An apples-to-apples benchmark of ancestor-aware coin selection: [`bdk_coin_select`][coin-select]
— ancestor-aware selection ([PR #64][pr64]) on the delta-aware branch-and-bound evaluator
([PR #53][pr53]), searched depth-first ([PR #73][pr73]), with ancestor sets stored sparsely
([PR #75][pr75]) and a second ancestry-aware greedy seed ([PR #76][pr76]) — against
[Bitcoin Core][core]'s wallet coin selection.

The last two are pinned for what they do past the checked-in fixtures: neither changes a single row
of the 42-fixture matrix, and both matter at 200,000 candidates (see [`FINDINGS.md`](FINDINGS.md)
#6). `pins.json` says why each was chosen.

Grew out of [bitcoindevkit/coin-select#67][issue67], which asked for both searches run on the same
changeless objective. The pinned revision has no changeless metric left, so what remains is the
wallet comparison.

```
python3 bench.py all --oracle
```

That clones and builds both pinned revisions, runs every fixture on both engines, and writes
`results/results.csv`, `results/results.json` and `results/SUMMARY.md`. On a 24-core machine the
whole thing takes about a minute — most of it building Core.

Prerequisites: a C++20 compiler, CMake 3.22+, a Rust toolchain, `git`, and Python 3.9+ (stdlib
only). No Bitcoin Core dependencies beyond what the coin-selection primitives need.

## Why it is built this way

The two implementations do not optimise the same thing, so comparing their own reported numbers
would be meaningless. Instead:

- **Both runners emit only what they did**: which candidate ids they selected, how long it took,
  how many nodes they evaluated, and whether they finished the tree or hit the budget.
- **`bench.py report` scores those selections**, from the fixture, with one implementation of one
  fee model. Both columns of every quality comparison come from the same code.
- **Nothing is taken on trust.** Every quantity in the shared model is cross-checked against at
  least one engine's own computation of it, and a mismatch is reported as a failure:

  | shared model | checked against |
  | --- | --- |
  | child weight | `SelectionView::weight` |
  | child fee | `SelectionView::fee` |
  | ancestor union bump | `SelectionView::ancestor_bump` |
  | individual and combined bump fees | the Core runner's port of `node::MiniMiner` |
  | waste | `SelectionResult::RecalculateWaste` |
  | selected input weight | `SelectionResult::GetWeight` |

  On top of that, every selection is checked against the fixture's ancestor union: does this
  package actually reach the target feerate, and does it stay inside `max_weight`? `report` writes
  the report either way but exits non-zero when something failed, so CI does not need to parse it.
  Pass `--no-strict` to look at a run that has known problems.

## The track

### `wallet` — what a wallet would actually build

| | |
| --- | --- |
| Bitcoin Core | The full portfolio from `wallet/spend.cpp`'s `ChooseSelectionResult`: BnB, `KnapsackSolver`, `CoinGrinder` (only above 3x the long-term feerate), single random draw; then the shared-ancestry bump discount; then least waste wins |
| coin-select | `LowestFee` branch and bound with change at the metric's discretion, falling back to single random draw |

Different objectives — Core minimises waste and deliberately targets a privacy-friendly
change amount; coin-select minimises long-term fee — which the report says on every table.

This is the only track, and every result in [`SAMPLING-PLAN.md`](SAMPLING-PLAN.md) comes from it.
A second `kernel` track used to isolate Core's `SelectCoinsBnB` against coin-select's changeless
metric; the pinned revision removes `Changeless` and `LowestFeeChangeless`, so there is no
changeless objective left to run against it and the track is gone.

Core's portfolio only reaches for `CoinGrinder` above 3x the long-term feerate, so the
`high_feerate` fixture family exists to exercise that gate. At `feerate == long_term_feerate` Core's
waste also degenerates — `coin.fee - coin.long_term_fee` is zero for every input, leaving only
excess — which is the second reason that family is there.

## Layout

| path | what it is |
| --- | --- |
| `bench.py` | The only entry point: `setup`, `run`, `report`, `all`, `smoke`. Also holds the shared fee model and an independent port of Core's bump-fee algorithm. |
| `pins.json` | The two pinned revisions, with a note on why each was chosen. |
| `genfixtures.py` | Regenerates `fixtures/`. Deterministic; `--check` fails if the checked-in files are stale. |
| `fixtures/` | The datasets, plus [`fixtures/README.md`](fixtures/README.md) — the schema and **every semantic conversion either adapter makes**. |
| `fixtures/scale/` | Generated on demand by `genfixtures.py --scale`, not checked in: 20,000 and 200,000 candidates, 30 MB a file and deterministic from their seed. |
| `rust-runner/` | The coin-select runner. |
| `core-runner/` | The Bitcoin Core runner, including a port of `node::MiniMiner`'s bump-fee calculation. |
| `patches/` | One patch to Core adding benchmark hooks — a node counter and an optional wall-clock deadline — explained in [`patches/README.md`](patches/README.md). No bound, ordering or scoring rule is ever patched. |
| `results/` | Generated. `SUMMARY.md` is the readable report, `results.csv` the full matrix, and `compare/` holds revision A/B runs. |
| `FINDINGS.md` | A snapshot of what the current results show, with the revisions they came from. |
| `SUMMARY.md` | The other half: what is being tried to move those results, and what it measured. Hand-maintained — not the generated `results/SUMMARY.md`. |
| `pr/` | Draft PR bodies for the branches `SUMMARY.md` measures, kept with the numbers they cite. |
| `tools/` | The scoreboards `SUMMARY.md` is built from: `scoreboard.py`, `beat.py`, `seeds.py`. |
| `ARCHIVED-FINDINGS.md` | Results this harness measured but can no longer reproduce, with the commit and pins to reproduce them from history. |
| `ANCESTOR-BOUND-PLAN.md` | A design for an ancestor-bump ceiling — the prune both other plans turn out to need. |
| `DFS-PLAN.md` | A design for replacing the priority-queue traversal with depth-first search, argued from those results. |
| `SAMPLING-PLAN.md` | A design for retrying a budget-limited search on randomly sampled subsets of the pool. |
| `ITERATIVE-DEEPENING-PLAN.md` | A design for recovering best-first's node ordering at depth-first memory, by deepening on the bound. |

## Commands

```sh
python3 bench.py setup                      # clone + build both pinned revisions
python3 bench.py run --oracle               # run the matrix into results/raw/
python3 bench.py run --fixtures 'shared_*'  # one family
python3 bench.py report                     # score results/raw/ (exits non-zero on a problem)
python3 bench.py run --deadline-us 5000     # equal-time instead of equal-rounds (see below)
python3 bench.py run --escalate             # coin-select only: sample the pool when the full
                                            # search runs out of budget (see FINDINGS.md #6)
python3 bench.py smoke                      # the CI-sized fixture, end to end
python3 genfixtures.py                      # regenerate fixtures/
python3 genfixtures.py --scale              # write the 20k/200k tier into fixtures/scale/
python3 bench.py scale                      # run it (see FINDINGS.md #6)

# A/B two coin-select revisions on the same fixtures
python3 bench.py compare-revs --a <rev> --b 'https://github.com/you/coin-select.git#<rev>'
```

`compare-revs` builds the runner against each revision, runs them **interleaved per fixture** and
pinned to one core so drifting background load moves both together, and compares minimum samples
rather than medians — background load can only ever add time, so the fastest observed run is the
closest thing to an uncontended measurement. It reports behaviour first (identical selections,
round counts, solved/unsolved) and speed second, because a speedup that changed the answers is not
a speedup. Output lands in `results/compare/`.

**How far back `compare-revs` reaches is bounded by the runner, not by the harness.** The runner
reads its aggregates from `SelectionView` — so revisions before PR #53, which take `&CoinSelector`
in `BnbMetric`, will not build — and it now consumes `drags_in` as `&[u32]`, so revisions before
[PR #75][pr75], where it was a `Bitset`, will not build either. Reaching further back than the
current pin means checking out a runner from this repository's history alongside it.

`bench.py scale` runs pools an order of magnitude past the checked-in matrix — 20,000 and 200,000
candidates. Neither engine exhausts anything at that size, so what it measures is memory, setup cost
and answer quality rather than optimality. The tier caps `max_weight` at `MAX_STANDARD_TX_WEIGHT` and
targets what roughly 400 inputs can fund: at 200,000 candidates the usual "45% of the pool" target
needs a transaction six times the standardness limit, which Core correctly refuses to build and
coin-select will happily build if nothing tells it not to (see FINDINGS.md #6).

`--oracle` brute forces every fixture with at most 20 candidates against coin-select's own
objective, so a disagreement can be attributed rather than merely observed: it says whether the
search found the best answer to the question it was asking. Core has no oracle here — its wallet
portfolio has no single objective to enumerate, and its results may carry change.

## Reproducibility

- Both revisions are pinned by commit in `pins.json`; `bench.py setup` checks out exactly those
  and re-applies patches from scratch every time, so it is idempotent.
- `rust-runner/Cargo.toml` pins the same coin-select revision; setup refuses to build if the two
  pins have drifted apart. The runner reads every aggregate — weight, fee, excess, ancestor bump —
  from the `SelectionView` the metric is handed, rather than from `CoinSelector`.
- Fixtures are deterministic from a per-fixture seed and are checked in.
- Core is built at `-O3` with assertions on (it refuses to compile with `NDEBUG`); the Rust runner
  at `--release` with `codegen-units = 1`. Compiler versions, host and the applied patch list are
  recorded in `results/environment.json` on every setup.
- Timing is one warm-up run and five measured runs per case by default (`--warmup`, `--repeat`);
  the median is reported, and only the search itself is inside the timed region — fixture parsing
  and problem construction are not.
- Peak RSS is process-wide and read before the oracle runs. It tracks the search for the
  coin-select runner (2.7 MB to 3.6 MB across the matrix: the depth-first search keeps one stack
  frame per decision, not a queue entry per live node); the Core runner sits at a flat ~19 MB of
  process baseline on every fixture, so its figure says nothing about the search and the two are
  not comparable.

## Known limits

- **Neither engine's objective is the other's.** Core minimises waste across its portfolio;
  coin-select minimises long-term fee. Making them literally identical would mean writing a
  Core-waste `BnbMetric`, bound included, for coin-select — that bound would be this harness's
  code, so the comparison would end up measuring a bound written here rather than the crate's,
  which is a worse answer than an honest gap. What fills it instead: the report scores both
  selections on **both** objectives, and `--oracle` says whether coin-select reached the optimum
  of the question it was actually asking.
- **The default budgets are not the same unit.** Core's `TOTAL_TRIES` counts depth-first nodes;
  coin-select's `max_rounds` counts branch-and-bound iterator rounds. Both are 100,000, so the default matrix
  says how much work each engine needs rather than which wins under a fixed latency budget. Pass
  `--deadline-us` to give both the same wall-clock budget instead — that is the framing closest to
  what a wallet actually constrains, and it sidesteps the unit mismatch entirely.
- **The fixture ancestor graph is the whole mempool.** A real `MiniMiner` also pulls in unrelated
  transactions that share a cluster, which can change what gets "mined" and therefore what a bump
  costs.
- **Two constant fee-model gaps survive**, both documented and both reported rather than hidden:
  the empty witness a legacy input serialises, and the segwit marker on an all-legacy selection.
  See [`fixtures/README.md`](fixtures/README.md#known-residual-fee-model-gaps).
- Address grouping (`m_avoid_partial_spends`) is off by construction: one fixture candidate is one
  `OutputGroup`. Grouped selection is not measured, and neither is Core's per-output-type pass —
  the runner always searches the combined pool.

[coin-select]: https://github.com/bitcoindevkit/coin-select
[pr64]: https://github.com/bitcoindevkit/coin-select/pull/64
[pr53]: https://github.com/bitcoindevkit/coin-select/pull/53
[pr73]: https://github.com/bitcoindevkit/coin-select/pull/73
[pr75]: https://github.com/bitcoindevkit/coin-select/pull/75
[pr76]: https://github.com/bitcoindevkit/coin-select/pull/76
[issue67]: https://github.com/bitcoindevkit/coin-select/issues/67
[core]: https://github.com/bitcoin/bitcoin
