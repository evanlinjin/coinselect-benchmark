# Patches applied to the pinned Bitcoin Core tree

`bench.py setup` re-checks out the pinned revision with `git checkout --force` and then applies
everything here, so the patched tree is reproducible and the patches cannot silently accumulate.

Coin selection itself is never patched. Anything that would change which coins Core picks does
not belong in this directory.

## `core-bench-hooks.patch`

`SelectCoinsBnB` is the only algorithm in `wallet/coinselection.cpp` that records neither the
number of nodes it evaluated nor whether it finished the tree. `CoinGrinder` calls
`SetSelectionsEvaluated` and `SetAlgoCompleted`; `SelectCoinsBnB` calls neither, and
`SelectionResult::m_selections_evaluated` has no default initialiser, so reading it on a BnB
result yields whatever was on the stack.

Issue #67 asks for "selections/nodes evaluated" and "whether the search exhausted the tree or hit
its budget" for both engines, so the harness needs those numbers. The patch:

- hoists the existing `curr_try` loop counter out of the `for` statement so it survives the loop,
- publishes it, and whether the loop ended before `TOTAL_TRIES`, in two globals,
- resets both at function entry, so the early `util::Error` return taken when the pool cannot
  reach the target reports this call (0 nodes) rather than leaving the previous call's numbers in
  place.

Both globals are set on every path that runs the search, including the `util::Error` returns that
discard the `SelectionResult` entirely — which is how the harness can report a node count for a
search that found nothing.

### The deadline hook

The same patch adds an optional wall-clock deadline, used by `--deadline-us`.

Core's searches stop on a node count; coin-select's stop on a round count. Those are not the same
unit, so comparing "100,000 of each" says something about how much work each engine needs but
nothing about which does better under a fixed latency budget — which is the constraint a wallet
actually has. The hook lets the harness give both engines the same number of microseconds instead.

It is a `std::chrono::steady_clock::time_point` global, default-constructed to zero, and a
`BenchDeadlineHit` helper polled every 256 nodes. `SelectCoinsBnB` breaks out of its DFS loop and
reports itself as not having completed; `CoinGrinder` reuses its existing `curr_try >= TOTAL_TRIES`
exit, which already records the result as non-optimal.

**This one does change a termination condition** — that is its whole purpose — so be precise about
what it does and does not touch:

- With no deadline set (the default, and every `bench.py run` that omits `--deadline-us`) the
  globals are zero and the search behaves exactly as unpatched: same nodes, same order.
- With a deadline set, the search visits the same nodes in the same order and simply stops earlier.
  No bound, ordering, pruning rule or scoring is altered.

Polling every 256 nodes rather than every node is deliberate: a `steady_clock` read costs several
times what visiting a node does, so a per-node check would distort the measurement it exists to
enable. The cost is up to 255 nodes of overshoot past the deadline, which at ~6 ns per node is
under two microseconds.
