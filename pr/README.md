# Draft PR bodies for the coin-select branches

Three changes, each on top of the last, none pushed — the signing key is on a smartcard that needs a
physical touch. The measurements behind them are in [`../EXPERIMENTS.md`](../EXPERIMENTS.md) and
[`../STRATEGIES.md`](../STRATEGIES.md).

| file | branch | head | base |
| --- | --- | --- | --- |
| [`pr-cheap-nodes.md`](pr-cheap-nodes.md) | `experiment/cheap-nodes` | `ba58982` | coin-select PR #76 (`e93d1f9`) |
| [`pr-deepen.md`](pr-deepen.md) | `experiment/deepen-on-bound` | `ecdbbc9` | `ba58982` |
| [`pr-repair.md`](pr-repair.md) | `experiment/repair-pass` | `2bc0562` | `ecdbbc9` |

`../pins.json` points at `experiment/repair-pass` through the local clone rather than GitHub, because
that branch is not pushed. Repoint it at `https://github.com/evanlinjin/coin-select.git` once it is.

To push and open them:

```sh
cd /home/evanlinjin/Git/coin-select-fast   && git push -u me experiment/cheap-nodes
cd /home/evanlinjin/Git/coin-select-deepen && git push -u me experiment/deepen-on-bound
cd /home/evanlinjin/Git/coin-select-repair && git push -u me experiment/repair-pass

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

All three commits are unsigned (`--no-gpg-sign`) for the same reason; re-sign before pushing if the
repository requires it.
