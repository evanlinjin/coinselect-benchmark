# Draft PR bodies for the coin-select branches

Two changes, each on top of the last, neither pushed — the signing key is on a smartcard that needs a
physical touch. The measurements behind them are in [`../EXPERIMENTS.md`](../EXPERIMENTS.md).

| file | branch | head | base |
| --- | --- | --- | --- |
| [`pr-cheap-nodes.md`](pr-cheap-nodes.md) | `experiment/cheap-nodes` | `ba58982` | coin-select PR #76 (`e93d1f9`) |
| [`pr-deepen.md`](pr-deepen.md) | `experiment/deepen-on-bound` | `ecdbbc9` | `ba58982` |

To push and open them:

```sh
cd /home/evanlinjin/Git/coin-select-fast   && git push -u me experiment/cheap-nodes
cd /home/evanlinjin/Git/coin-select-deepen && git push -u me experiment/deepen-on-bound

gh pr create --repo bitcoindevkit/coin-select --draft --base master \
  --head evanlinjin:experiment/cheap-nodes \
  --title "perf: stop re-walking the decided prefix at every node" \
  --body-file pr/pr-cheap-nodes.md

gh pr create --repo bitcoindevkit/coin-select --draft --base master \
  --head evanlinjin:experiment/deepen-on-bound \
  --title "feat!: deepen on the bound by default" \
  --body-file pr/pr-deepen.md
```

Both commits are unsigned (`--no-gpg-sign`) for the same reason; re-sign before pushing if the
repository requires it.
