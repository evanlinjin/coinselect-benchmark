# `b2f98ab852e0` vs `bdcb1f064cd2`

- A: `b2f98ab852e0425494d53f7260c4aa82f6c0830d` (features: no-default-features)
- B: `bdcb1f064cd20ab4d864e6f040f0d45a6fd5e8fc` (features: default)
- 3 fixture/track pairs, interleaved A/B per case, both pinned to core 22
- 2 warm-up and 9 measured runs each; speedup is the ratio of minimum samples

## Behaviour

- identical selections: **3/3**
- identical round counts: **3/3**
- identical solved/unsolved: **3/3**

## Speedup

| track | group | geomean | median | range |
|---|---|---|---|---|
| kernel | with ancestry | 2.01x | 2.01x | 2.01-2.01x |
| changeful | with ancestry | 1.16x | 1.16x | 1.16-1.16x |
| wallet | with ancestry | 1.11x | 1.11x | 1.11-1.11x |

## Per fixture

| fixture | track | n | rounds | A (ms) | B (ms) | speedup |
|---|---|---|---|---|---|---|
| smoke | changeful | 8 | 35 | 0.02 | 0.02 | 1.16x |
| smoke | kernel | 8 | 445 | 0.38 | 0.19 | 2.01x |
| smoke | wallet | 8 | 35 | 0.02 | 0.02 | 1.11x |
