# Draft PR bodies for the coin-select branches

Three changes, each on top of the last, all pushed to `evanlinjin/coin-select`. The measurements behind them are in [`../EXPERIMENTS.md`](../EXPERIMENTS.md) and
[`../STRATEGIES.md`](../STRATEGIES.md).

| file | branch | head | base |
| --- | --- | --- | --- |
| [`pr-cheap-nodes.md`](pr-cheap-nodes.md) | `experiment/cheap-nodes` | `ba58982` | coin-select PR #76 (`e93d1f9`) |
| [`pr-deepen.md`](pr-deepen.md) | `experiment/deepen-on-bound` | `ecdbbc9` | `ba58982` |
| [`pr-repair.md`](pr-repair.md) | `experiment/repair-pass` | `887c4da` | `ecdbbc9` |

`../pins.json` pins `experiment/repair-pass`, so the matrix in `../results/SUMMARY.md` is the evidence
for all three.

To open them:

```sh
gh pr create --repo bitcoindevkit/coin-select --draft --base master \
  --head evanlinjin:experiment/cheap-nodes \
  --title "perf: stop re-walking the decided prefix at every node" \
  --body-file pr/pr-cheap-nodes.md

gh pr create --repo bitcoindevkit/coin-select --draft --base master \
  --head evanlinjin:experiment/deepen-on-bound \
  --title "feat!: deepen on the bound by default" \
  --body-file pr/pr-deepen.md

gh pr create --repo bitcoindevkit/coin-select --draft --base master \
  --head evanlinjin:experiment/repair-pass \
  --title "feat: repair a finished selection where ancestry is shared" \
  --body-file pr/pr-repair.md
```

Each PR's `--base master` is what GitHub needs to open them; review them in stack order, since each
branch contains the ones below it.

The commits are unsigned (`--no-gpg-sign`), because the signing key is on a smartcard that needs a
physical touch; re-sign if the repository requires it.
