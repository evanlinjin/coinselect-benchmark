# Draft PR bodies for the coin-select branches

Three changes, each on top of the last, all pushed to `evanlinjin/coin-select` and open upstream. The
measurements behind them are in [`../EXPERIMENTS.md`](../EXPERIMENTS.md) and
[`../STRATEGIES.md`](../STRATEGIES.md).

| PR | file | branch | head | sits on |
| --- | --- | --- | --- | --- |
| [#77](https://github.com/bitcoindevkit/coin-select/pull/77) | [`pr-cheap-nodes.md`](pr-cheap-nodes.md) | `experiment/cheap-nodes` | `ba58982` | [#76](https://github.com/bitcoindevkit/coin-select/pull/76) (`e93d1f9`) |
| [#78](https://github.com/bitcoindevkit/coin-select/pull/78) | [`pr-deepen.md`](pr-deepen.md) | `experiment/deepen-on-bound` | `ecdbbc9` | #77 (`ba58982`) |
| [#79](https://github.com/bitcoindevkit/coin-select/pull/79) | [`pr-repair.md`](pr-repair.md) | `experiment/repair-pass` | `887c4da` | #78 (`ecdbbc9`) |

All three are open as drafts. GitHub will not take a base branch that only exists in the fork, so
each is based on `master` and its diff includes everything below it — review in stack order, and take
each PR's change as the commits above its parent.

`../pins.json` pins `experiment/repair-pass`, so the matrix in `../results/SUMMARY.md` is the evidence
for all three.

They were opened with:

```sh
gh pr create --repo bitcoindevkit/coin-select --draft --base master \
  --head evanlinjin:experiment/repair-pass \
  --title "feat: repair a finished selection where ancestry is shared" \
  --body-file pr/pr-repair.md
```

Editing a body afterwards is `gh pr edit <n> --repo bitcoindevkit/coin-select --body-file <file>`.

The commits are unsigned (`--no-gpg-sign`), because the signing key is on a smartcard that needs a
physical touch; re-sign if the repository requires it.
