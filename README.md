# coinselect-benchmark

An apples-to-apples benchmark of ancestor-aware coin selection: [`bdk_coin_select`][coin-select]
(the ancestor-aware branch, [PR #64][pr64]) against [Bitcoin Core][core]'s wallet coin selection.

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
- **Nothing is taken on trust.** The report re-derives each runner's own bump-fee figures and
  fails loudly if they disagree, and it checks every selection against the fixture's ancestor
  union: does this package actually reach the target feerate?

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
| `results/` | Generated. `SUMMARY.md` is the readable report; `results.csv` is the full matrix. |
| `FINDINGS.md` | A snapshot of what the current results show, with the revisions they came from. |

## Commands

```sh
python3 bench.py setup                      # clone + build both pinned revisions
python3 bench.py run --oracle               # run the matrix into results/raw/
python3 bench.py run --fixtures 'shared_*'  # one family
python3 bench.py run --tracks kernel        # one track
python3 bench.py report                     # score results/raw/
python3 bench.py smoke                      # the CI-sized fixture, end to end
python3 genfixtures.py                      # regenerate fixtures/
```

`--oracle` brute forces every fixture with at most 20 candidates against **each engine's own**
objective, so a disagreement can be attributed rather than merely observed: it says whether a
runner found the best answer to the question it was asking.

## Reproducibility

- Both revisions are pinned by commit in `pins.json`; `bench.py setup` checks out exactly those
  and re-applies patches from scratch every time, so it is idempotent.
- `rust-runner/Cargo.toml` pins the same coin-select revision; setup refuses to build if the two
  pins have drifted apart.
- Fixtures are deterministic from a per-fixture seed and are checked in.
- Core is built at `-O3` with assertions on (it refuses to compile with `NDEBUG`); the Rust runner
  at `--release` with `codegen-units = 1`. Compiler versions, host and the applied patch list are
  recorded in `results/environment.json` on every setup.
- Timing is one warm-up run and five measured runs per case by default (`--warmup`, `--repeat`);
  the median is reported, and only the search itself is inside the timed region — fixture parsing
  and problem construction are not.
- Peak RSS is process-wide, so it is a ceiling rather than a measurement of the search.

## Known limits

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
  `OutputGroup`. Grouped selection is not measured.

[coin-select]: https://github.com/bitcoindevkit/coin-select
[pr64]: https://github.com/bitcoindevkit/coin-select/pull/64
[issue67]: https://github.com/bitcoindevkit/coin-select/issues/67
[core]: https://github.com/bitcoin/bitcoin
