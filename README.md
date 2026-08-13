# coinselect-benchmark

An apples-to-apples benchmark of ancestor-aware coin selection: [`bdk_coin_select`][coin-select]
on the [`feature/ancestor-aware-with-view`][branch] branch — ancestor-aware selection
([PR #64][pr64]) on the delta-aware branch-and-bound evaluator ([PR #53][pr53]) — against
[Bitcoin Core][core]'s wallet coin selection.

Answers [bitcoindevkit/coin-select#67][issue67].

```
python3 bench.py all --oracle
```

That clones and builds both pinned revisions, runs every fixture on both engines and both tracks,
and writes `results/results.csv`, `results/results.json` and `results/SUMMARY.md`. On a 24-core
machine the whole thing takes about a minute — most of it building Core.

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
  | child weight | `CoinSelector::weight` |
  | child fee | `CoinSelector::fee` |
  | ancestor union bump | `CoinSelector::ancestor_bump` |
  | individual and combined bump fees | the Core runner's port of `node::MiniMiner` |
  | waste | `SelectionResult::RecalculateWaste` |
  | selected input weight | `SelectionResult::GetWeight` |

  On top of that, every selection is checked against the fixture's ancestor union: does this
  package actually reach the target feerate, and does it stay inside `max_weight`? `report` writes
  the report either way but exits non-zero when something failed, so CI does not need to parse it.
  Pass `--no-strict` to look at a run that has known problems.

## The two tracks

### `kernel` — search behaviour

Both engines run a changeless branch and bound over the same candidates, target, effective
feerate, weight cap and 100,000-node budget:

| | |
| --- | --- |
| Bitcoin Core | `SelectCoinsBnB`: depth-first, least waste among selections whose effective value lands in `[target, target + cost_of_change]` |
| coin-select | `Changeless<LowestFee>`: priority-queue branch and bound, minimising the child transaction's fee over all changeless selections |

The objectives are related but **not identical**, so this track compares traversal and pruning —
node counts, wall clock, whether the tree was exhausted — and reports solution quality only
through the shared metrics. coin-select minimises fee by construction, so "coin-select found a
cheaper selection" on this track is a restatement of its objective, not a result.

### `changeful` — the same, for searches that may create change

| | |
| --- | --- |
| Bitcoin Core | `CoinGrinder`: depth-first, minimising **selected input weight** subject to funding the target plus a change target |
| coin-select | bare `LowestFee`: priority-queue branch and bound, minimising long-term fee, change at the metric's own discretion |

The counterpart to `kernel` for the change-producing case. Objectives differ again — weight versus
long-term fee — so the same rules apply: node counts and wall clock compared directly, quality only
through the shared metrics.

Note Core's portfolio only reaches for `CoinGrinder` above 3x the long-term feerate, so the
`high_feerate` fixture family exists to exercise it inside that gate. At `feerate ==
long_term_feerate` Core's waste also degenerates — `coin.fee - coin.long_term_fee` is zero for
every input, leaving only excess — which is the second reason that family is there.

### `wallet` — what a wallet would actually build

| | |
| --- | --- |
| Bitcoin Core | The full portfolio from `wallet/spend.cpp`'s `ChooseSelectionResult`: BnB, `KnapsackSolver`, `CoinGrinder` (only above 3x the long-term feerate), single random draw; then the shared-ancestry bump discount; then least waste wins |
| coin-select | `LowestFee` branch and bound with change at the metric's discretion, falling back to single random draw |

Different objectives again — Core minimises waste and deliberately targets a privacy-friendly
change amount; coin-select minimises long-term fee — which the report says on every table.

## Layout

| path | what it is |
| --- | --- |
| `bench.py` | The only entry point: `setup`, `run`, `report`, `all`, `smoke`. Also holds the shared fee model and an independent port of Core's bump-fee algorithm. |
| `pins.json` | The two pinned revisions, with a note on why each was chosen. |
| `genfixtures.py` | Regenerates `fixtures/`. Deterministic; `--check` fails if the checked-in files are stale. |
| `fixtures/` | The datasets, plus [`fixtures/README.md`](fixtures/README.md) — the schema and **every semantic conversion either adapter makes**. |
| `rust-runner/` | The coin-select runner. |
| `core-runner/` | The Bitcoin Core runner, including a port of `node::MiniMiner`'s bump-fee calculation. |
| `patches/` | One instrumentation-only patch to Core, explained in [`patches/README.md`](patches/README.md). Coin selection itself is never patched. |
| `results/` | Generated. `SUMMARY.md` is the readable report, `results.csv` the full matrix, and `compare/` holds revision A/B runs. |
| `FINDINGS.md` | A snapshot of what the current results show, with the revisions they came from. |

## Commands

```sh
python3 bench.py setup                      # clone + build both pinned revisions
python3 bench.py run --oracle               # run the matrix into results/raw/
python3 bench.py run --fixtures 'shared_*'  # one family
python3 bench.py run --tracks kernel        # one track (kernel, changeful, wallet)
python3 bench.py report                     # score results/raw/ (exits non-zero on a problem)
python3 bench.py smoke                      # the CI-sized fixture, end to end
python3 genfixtures.py                      # regenerate fixtures/

# A/B two coin-select revisions on the same fixtures
python3 bench.py compare-revs --a <rev> --b 'https://github.com/you/coin-select.git#<rev>'
```

`compare-revs` builds the runner against each revision, runs them **interleaved per fixture** and
pinned to one core so drifting background load moves both together, and compares minimum samples
rather than medians — background load can only ever add time, so the fastest observed run is the
closest thing to an uncontended measurement. It reports behaviour first (identical selections,
round counts, solved/unsolved) and speed second, because a speedup that changed the answers is not
a speedup. Revisions either side of coin-select PR #53 have different `BnbMetric` signatures; the
runner carries a `selection-view` feature for that and `compare-revs` picks the right one by
trying both. Output lands in `results/compare/`.

`--oracle` brute forces every fixture with at most 20 candidates against **each engine's own**
objective, so a disagreement can be attributed rather than merely observed: it says whether a
runner found the best answer to the question it was asking. Core's oracle enumerates every subset,
including coins Core's own positive-effective-value filter drops before the search — so "Core
missed it" can mean either the search or that filter.

## Reproducibility

- Both revisions are pinned by commit in `pins.json`; `bench.py setup` checks out exactly those
  and re-applies patches from scratch every time, so it is idempotent.
- `rust-runner/Cargo.toml` pins the same coin-select revision; setup refuses to build if the two
  pins have drifted apart. The runner's `selection-view` feature is on by default because the
  pinned revision takes `&SelectionView` in `BnbMetric`; build with `--no-default-features` for a
  revision from before that change.
- Fixtures are deterministic from a per-fixture seed and are checked in.
- Core is built at `-O3` with assertions on (it refuses to compile with `NDEBUG`); the Rust runner
  at `--release` with `codegen-units = 1`. Compiler versions, host and the applied patch list are
  recorded in `results/environment.json` on every setup.
- Timing is one warm-up run and five measured runs per case by default (`--warmup`, `--repeat`);
  the median is reported, and only the search itself is inside the timed region — fixture parsing
  and problem construction are not.
- Peak RSS is process-wide and read before the oracle runs. It tracks the search for the
  coin-select runner (2.9 MB to 23 MB across the matrix, since the priority queue holds a branch
  per live node); the Core runner sits at a flat ~17 MB of process baseline on every fixture, so
  its figure says nothing about the search and the two are not comparable.

## Known limits

- **The kernel track shares a constraint, not an objective.** Issue #67 asks for both searches to
  run "the same changeless objective". They share the changeless constraint, the candidates, the
  target, the feerate, the weight cap and the budget — but each still minimises its own score.
  Making them literally identical would mean writing a Core-waste `BnbMetric`, bound included, for
  coin-select. That bound would be this harness's code, so the track would end up measuring a
  bound written here rather than the crate's, which is a worse answer than an honest gap. What
  fills it instead: the report scores both selections on **both** objectives, and `--oracle` says
  whether each engine reached the optimum of the question it was actually asking.
- **The budgets are not the same unit.** Core's `TOTAL_TRIES` counts depth-first nodes;
  coin-select's `max_rounds` counts priority-queue pops. Both are 100,000. Comparing them is a
  statement about how much work each engine needs, not about how fast a node is.
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
[branch]: https://github.com/evanlinjin/coin-select/tree/feature/ancestor-aware-with-view
[pr64]: https://github.com/bitcoindevkit/coin-select/pull/64
[pr53]: https://github.com/bitcoindevkit/coin-select/pull/53
[issue67]: https://github.com/bitcoindevkit/coin-select/issues/67
[core]: https://github.com/bitcoin/bitcoin
