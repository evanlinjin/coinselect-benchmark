# Patches applied to the pinned Bitcoin Core tree

`bench.py setup` re-checks out the pinned revision with `git checkout --force` and then applies
everything here, so the patched tree is reproducible and the patches cannot silently accumulate.

Coin selection itself is never patched. Anything that would change which coins Core picks does
not belong in this directory.

## `core-bnb-instrumentation.patch`

`SelectCoinsBnB` is the only algorithm in `wallet/coinselection.cpp` that records neither the
number of nodes it evaluated nor whether it finished the tree. `CoinGrinder` calls
`SetSelectionsEvaluated` and `SetAlgoCompleted`; `SelectCoinsBnB` calls neither, and
`SelectionResult::m_selections_evaluated` has no default initialiser, so reading it on a BnB
result yields whatever was on the stack.

Issue #67 asks for "selections/nodes evaluated" and "whether the search exhausted the tree or hit
its budget" for both engines, so the harness needs those numbers. The patch:

- hoists the existing `curr_try` loop counter out of the `for` statement so it survives the loop,
- publishes it, and whether the loop ended before `TOTAL_TRIES`, in two globals.

The globals are written on every exit path, including the `util::Error` returns that discard the
`SelectionResult` entirely — which is how the harness can report a node count for searches that
found nothing.

No condition, bound, ordering or budget is touched. The search visits exactly the same nodes in
exactly the same order as the unpatched revision.
