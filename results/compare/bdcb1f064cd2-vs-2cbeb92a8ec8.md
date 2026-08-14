# `bdcb1f064cd2` vs `2cbeb92a8ec8`

- A: `bdcb1f064cd20ab4d864e6f040f0d45a6fd5e8fc` (features: selection-view)
- B: `2cbeb92a8ec852d6d199e2460e5e6c67df662447` (features: selection-view + lowest-fee-changeless)
- 99 fixture/track pairs, interleaved A/B per case, both pinned to core 22
- 2 warm-up and 9 measured runs each; speedup is the ratio of minimum samples

## Behaviour

- identical selections: **96/99**
- identical round counts: **76/99**
- identical solved/unsolved: **96/99**

| fixture | track | rounds A | rounds B | inputs A | inputs B | solved A | solved B |
|---|---|---|---|---|---|---|---|
| adversarial_shared_100 | kernel | 1405 | 1308 | 6 | 6 | True | True |
| adversarial_shared_20 | kernel | 2654 | 301 | 5 | 5 | True | True |
| adversarial_shared_200 | kernel | 5571 | 5377 | 7 | 7 | True | True |
| adversarial_shared_50 | kernel | 3355 | 219 | 4 | 4 | True | True |
| high_feerate_100 | kernel | 9321 | 3960 | 8 | 8 | True | True |
| high_feerate_20 | kernel | 2373 | 43 | 4 | 4 | True | True |
| high_feerate_50 | kernel | 1644 | 365 | 6 | 6 | True | True |
| nested_ancestry_100 | kernel | 4219 | 1757 | 8 | 8 | True | True |
| nested_ancestry_20 | kernel | 100000 | 200 | 0 | 13 | False | True |
| nested_ancestry_50 | kernel | 3582 | 1768 | 7 | 7 | True | True |
| no_ancestry_100 | kernel | 3211 | 2827 | 5 | 5 | True | True |
| no_ancestry_20 | kernel | 587 | 152 | 4 | 4 | True | True |
| no_ancestry_200 | kernel | 24216 | 24024 | 10 | 10 | True | True |
| no_ancestry_50 | kernel | 4222 | 3992 | 6 | 6 | True | True |
| private_ancestry_20 | kernel | 765 | 207 | 7 | 7 | True | True |
| private_ancestry_50 | kernel | 2721 | 2673 | 7 | 7 | True | True |
| shared_ancestry_20 | kernel | 9122 | 369 | 4 | 4 | True | True |
| smoke | kernel | 445 | 121 | 5 | 5 | True | True |
| subsidizing_ancestry_100 | kernel | 100000 | 100000 | 7 | 0 | True | False |
| subsidizing_ancestry_20 | kernel | 100000 | 886 | 0 | 11 | False | True |
| subsidizing_ancestry_50 | kernel | 100000 | 39775 | 7 | 7 | True | True |
| wallet_mixed_100 | kernel | 2915 | 2356 | 7 | 7 | True | True |
| wallet_mixed_20 | kernel | 527 | 31 | 4 | 4 | True | True |
| wallet_mixed_50 | kernel | 1455 | 610 | 4 | 4 | True | True |

## Speedup

| track | group | geomean | median | range |
|---|---|---|---|---|
| kernel | no ancestry | 1.42x | 1.10x | 0.97-3.47x |
| kernel | with ancestry | 4.05x | 2.37x | 1.17-510.71x |
| changeful | no ancestry | 1.01x | 1.01x | 1.00-1.03x |
| changeful | with ancestry | 1.40x | 1.32x | 1.02-1.96x |
| wallet | no ancestry | 1.01x | 1.00x | 0.99-1.02x |
| wallet | with ancestry | 1.35x | 1.32x | 0.72-1.93x |

## Per fixture

| fixture | track | n | rounds | A (ms) | B (ms) | speedup |
|---|---|---|---|---|---|---|
| adversarial_shared_100 | changeful | 100 | 490 | 0.52 | 0.33 | 1.56x |
| adversarial_shared_100 | kernel | 100 | 1405->1308 | 1.49 | 0.94 | 1.58x |
| adversarial_shared_100 | wallet | 100 | 490 | 0.51 | 0.34 | 1.49x |
| adversarial_shared_20 | changeful | 20 | 49 | 0.04 | 0.03 | 1.15x |
| adversarial_shared_20 | kernel | 20 | 2654->301 | 1.89 | 0.20 | 9.25x |
| adversarial_shared_20 | wallet | 20 | 49 | 0.04 | 0.03 | 1.12x |
| adversarial_shared_200 | changeful | 200 | 2499 | 3.30 | 1.81 | 1.82x |
| adversarial_shared_200 | kernel | 200 | 5571->5377 | 7.47 | 4.05 | 1.84x |
| adversarial_shared_200 | wallet | 200 | 2499 | 3.31 | 1.84 | 1.80x |
| adversarial_shared_50 | changeful | 50 | 21 | 0.02 | 0.01 | 1.30x |
| adversarial_shared_50 | kernel | 50 | 3355->219 | 2.56 | 0.15 | 16.88x |
| adversarial_shared_50 | wallet | 50 | 21 | 0.02 | 0.01 | 1.32x |
| high_feerate_100 | changeful | 100 | 1558 | 1.81 | 1.06 | 1.70x |
| high_feerate_100 | kernel | 100 | 9321->3960 | 8.89 | 2.87 | 3.10x |
| high_feerate_100 | wallet | 100 | 1558 | 1.80 | 1.06 | 1.71x |
| high_feerate_20 | changeful | 20 | 14 | 0.01 | 0.01 | 1.12x |
| high_feerate_20 | kernel | 20 | 2373->43 | 1.46 | 0.03 | 52.84x |
| high_feerate_20 | wallet | 20 | 14 | 0.01 | 0.01 | 1.09x |
| high_feerate_200 | changeful | 200 | 3821 | 5.72 | 2.91 | 1.96x |
| high_feerate_200 | kernel | 200 | 3821 | 5.66 | 2.93 | 1.93x |
| high_feerate_200 | wallet | 200 | 3821 | 5.69 | 2.94 | 1.93x |
| high_feerate_50 | changeful | 50 | 52 | 0.05 | 0.03 | 1.32x |
| high_feerate_50 | kernel | 50 | 1644->365 | 1.27 | 0.25 | 4.98x |
| high_feerate_50 | wallet | 50 | 52 | 0.05 | 0.03 | 1.31x |
| nested_ancestry_100 | changeful | 100 | 46 | 0.06 | 0.03 | 1.86x |
| nested_ancestry_100 | kernel | 100 | 4219->1757 | 3.82 | 1.28 | 2.98x |
| nested_ancestry_100 | wallet | 100 | 46 | 0.06 | 0.03 | 1.87x |
| nested_ancestry_20 | changeful | 20 | 2 | 0.00 | 0.00 | 1.17x |
| nested_ancestry_20 | kernel | 20 | 100000->200 | 72.25 | 0.14 | 510.71x |
| nested_ancestry_20 | wallet | 20 | 2 | 0.00 | 0.00 | 1.13x |
| nested_ancestry_200 | changeful | 200 | 23466 | 43.75 | 24.76 | 1.77x |
| nested_ancestry_200 | kernel | 200 | 23466 | 44.32 | 24.36 | 1.82x |
| nested_ancestry_200 | wallet | 200 | 23466 | 44.07 | 24.88 | 1.77x |
| nested_ancestry_50 | changeful | 50 | 162 | 0.15 | 0.11 | 1.38x |
| nested_ancestry_50 | kernel | 50 | 3582->1768 | 3.04 | 1.28 | 2.37x |
| nested_ancestry_50 | wallet | 50 | 162 | 0.15 | 0.11 | 1.36x |
| no_ancestry_100 | changeful | 100 | 2222 | 1.68 | 1.64 | 1.03x |
| no_ancestry_100 | kernel | 100 | 3211->2827 | 2.48 | 2.14 | 1.16x |
| no_ancestry_100 | wallet | 100 | 2222 | 1.66 | 1.62 | 1.02x |
| no_ancestry_20 | changeful | 20 | 14 | 0.01 | 0.01 | 1.01x |
| no_ancestry_20 | kernel | 20 | 587->152 | 0.34 | 0.10 | 3.47x |
| no_ancestry_20 | wallet | 20 | 14 | 0.01 | 0.01 | 1.00x |
| no_ancestry_200 | changeful | 200 | 8127 | 6.69 | 6.69 | 1.00x |
| no_ancestry_200 | kernel | 200 | 24216->24024 | 21.63 | 22.25 | 0.97x |
| no_ancestry_200 | wallet | 200 | 8127 | 6.58 | 6.62 | 0.99x |
| no_ancestry_50 | changeful | 50 | 1195 | 0.83 | 0.83 | 1.00x |
| no_ancestry_50 | kernel | 50 | 4222->3992 | 3.18 | 3.03 | 1.05x |
| no_ancestry_50 | wallet | 50 | 1195 | 0.83 | 0.82 | 1.01x |
| private_ancestry_100 | changeful | 100 | 468 | 0.39 | 0.28 | 1.38x |
| private_ancestry_100 | kernel | 100 | 468 | 0.39 | 0.29 | 1.37x |
| private_ancestry_100 | wallet | 100 | 468 | 0.39 | 0.28 | 1.38x |
| private_ancestry_20 | changeful | 20 | 17 | 0.01 | 0.01 | 1.17x |
| private_ancestry_20 | kernel | 20 | 765->207 | 0.44 | 0.11 | 3.89x |
| private_ancestry_20 | wallet | 20 | 17 | 0.01 | 0.01 | 1.16x |
| private_ancestry_200 | changeful | 200 | 24577 | 37.41 | 20.15 | 1.86x |
| private_ancestry_200 | kernel | 200 | 24577 | 37.43 | 19.28 | 1.94x |
| private_ancestry_200 | wallet | 200 | 24577 | 37.66 | 19.74 | 1.91x |
| private_ancestry_50 | changeful | 50 | 841 | 0.65 | 0.51 | 1.29x |
| private_ancestry_50 | kernel | 50 | 2721->2673 | 2.26 | 1.71 | 1.32x |
| private_ancestry_50 | wallet | 50 | 841 | 0.65 | 0.50 | 1.31x |
| shared_ancestry_100 | changeful | 100 | 2945 | 3.49 | 2.20 | 1.59x |
| shared_ancestry_100 | kernel | 100 | 2945 | 3.52 | 2.17 | 1.62x |
| shared_ancestry_100 | wallet | 100 | 2945 | 3.51 | 2.18 | 1.61x |
| shared_ancestry_20 | changeful | 20 | 26 | 0.02 | 0.02 | 1.10x |
| shared_ancestry_20 | kernel | 20 | 9122->369 | 5.33 | 0.25 | 21.71x |
| shared_ancestry_20 | wallet | 20 | 26 | 0.02 | 0.02 | 1.11x |
| shared_ancestry_200 | changeful | 200 | 100000 | 211.82 | 143.70 | 1.47x |
| shared_ancestry_200 | kernel | 200 | 100000 | 212.97 | 142.08 | 1.50x |
| shared_ancestry_200 | wallet | 200 | 100000 | 213.29 | 143.48 | 1.49x |
| shared_ancestry_50 | changeful | 50 | 237 | 0.20 | 0.16 | 1.20x |
| shared_ancestry_50 | kernel | 50 | 237 | 0.20 | 0.17 | 1.18x |
| shared_ancestry_50 | wallet | 50 | 237 | 0.20 | 0.16 | 1.21x |
| smoke | changeful | 8 | 35 | 0.02 | 0.02 | 1.02x |
| smoke | kernel | 8 | 445->121 | 0.19 | 0.05 | 3.53x |
| smoke | wallet | 8 | 35 | 0.02 | 0.02 | 1.03x |
| subsidizing_ancestry_100 | changeful | 100 | 100000 | 164.71 | 132.46 | 1.24x |
| subsidizing_ancestry_100 | kernel | 100 | 100000 | 165.73 | 141.52 | 1.17x |
| subsidizing_ancestry_100 | wallet | 100 | 100000 | 167.37 | 130.89 | 1.28x |
| subsidizing_ancestry_20 | changeful | 20 | 104 | 0.06 | 0.05 | 1.16x |
| subsidizing_ancestry_20 | kernel | 20 | 100000->886 | 57.16 | 0.63 | 90.55x |
| subsidizing_ancestry_20 | wallet | 20 | 104 | 0.06 | 0.05 | 1.15x |
| subsidizing_ancestry_200 | changeful | 200 | 100000 | 173.97 | 121.39 | 1.43x |
| subsidizing_ancestry_200 | kernel | 200 | 100000 | 165.75 | 127.42 | 1.30x |
| subsidizing_ancestry_200 | wallet | 200 | 100000 | 175.23 | 120.13 | 1.46x |
| subsidizing_ancestry_50 | changeful | 50 | 55738 | 37.33 | 34.94 | 1.07x |
| subsidizing_ancestry_50 | kernel | 50 | 100000->39775 | 122.99 | 43.82 | 2.81x |
| subsidizing_ancestry_50 | wallet | 50 | 55738 | 37.26 | 34.76 | 1.07x |
| wallet_mixed_100 | changeful | 100 | 2006 | 1.97 | 1.49 | 1.32x |
| wallet_mixed_100 | kernel | 100 | 2915->2356 | 2.84 | 1.79 | 1.59x |
| wallet_mixed_100 | wallet | 100 | 2006 | 1.97 | 1.47 | 1.34x |
| wallet_mixed_20 | changeful | 20 | 5 | 0.01 | 0.00 | 1.79x |
| wallet_mixed_20 | kernel | 20 | 527->31 | 0.35 | 0.03 | 9.93x |
| wallet_mixed_20 | wallet | 20 | 5 | 0.00 | 0.01 | 0.72x |
| wallet_mixed_200 | changeful | 200 | 1107 | 1.55 | 0.81 | 1.91x |
| wallet_mixed_200 | kernel | 200 | 1107 | 1.54 | 0.81 | 1.91x |
| wallet_mixed_200 | wallet | 200 | 1107 | 1.55 | 0.80 | 1.92x |
| wallet_mixed_50 | changeful | 50 | 55 | 0.04 | 0.04 | 1.25x |
| wallet_mixed_50 | kernel | 50 | 1455->610 | 1.15 | 0.44 | 2.59x |
| wallet_mixed_50 | wallet | 50 | 55 | 0.04 | 0.04 | 1.24x |
