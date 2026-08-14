# `bdcb1f064cd2` vs `e45bb58efef5`

- A: `bdcb1f064cd20ab4d864e6f040f0d45a6fd5e8fc` (features: selection-view)
- B: `e45bb58efef5752356d3299cfd545ca8059df4fb` (features: selection-view + lowest-fee-changeless)
- 3 fixture/track pairs, interleaved A/B per case, both pinned to core 22
- 2 warm-up and 9 measured runs each; speedup is the ratio of minimum samples

## Behaviour

- identical selections: **3/3**
- identical round counts: **2/3**
- identical solved/unsolved: **3/3**

| fixture | track | rounds A | rounds B | inputs A | inputs B | solved A | solved B |
|---|---|---|---|---|---|---|---|
| smoke | kernel | 445 | 121 | 5 | 5 | True | True |

## Speedup

| track | group | geomean | median | range |
|---|---|---|---|---|
| kernel | with ancestry | 3.40x | 3.40x | 3.40-3.40x |
| changeful | with ancestry | 0.57x | 0.57x | 0.57-0.57x |
| wallet | with ancestry | 0.99x | 0.99x | 0.99-0.99x |

## Per fixture

| fixture | track | n | rounds | A (ms) | B (ms) | speedup |
|---|---|---|---|---|---|---|
| smoke | changeful | 8 | 35 | 0.02 | 0.03 | 0.57x |
| smoke | kernel | 8 | 445->121 | 0.19 | 0.05 | 3.40x |
| smoke | wallet | 8 | 35 | 0.02 | 0.02 | 0.99x |
