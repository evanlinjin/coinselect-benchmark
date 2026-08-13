# `b2f98ab852e0` vs `bdcb1f064cd2`

- A: `b2f98ab852e0425494d53f7260c4aa82f6c0830d` (features: none)
- B: `bdcb1f064cd20ab4d864e6f040f0d45a6fd5e8fc` (features: ['selection-view'])
- 99 fixture/track pairs, interleaved A/B per case, both pinned to core 22
- 2 warm-up and 9 measured runs each; speedup is the ratio of minimum samples

## Behaviour

- identical selections: **99/99**
- identical round counts: **95/99**
- identical solved/unsolved: **99/99**

| fixture | track | rounds A | rounds B | inputs A | inputs B | solved A | solved B |
|---|---|---|---|---|---|---|---|
| no_ancestry_100 | kernel | 2827 | 3211 | 5 | 5 | True | True |
| no_ancestry_20 | kernel | 152 | 587 | 4 | 4 | True | True |
| no_ancestry_200 | kernel | 24024 | 24216 | 10 | 10 | True | True |
| no_ancestry_50 | kernel | 3992 | 4222 | 6 | 6 | True | True |

## Speedup

| track | group | geomean | median | range |
|---|---|---|---|---|
| kernel | no ancestry | 1.36x | 1.73x | 0.49-2.34x |
| kernel | with ancestry | 2.79x | 2.73x | 1.78-4.25x |
| changeful | no ancestry | 2.32x | 2.27x | 1.94-2.91x |
| changeful | with ancestry | 2.14x | 2.30x | 0.70-4.69x |
| wallet | no ancestry | 2.10x | 2.07x | 1.60-2.85x |
| wallet | with ancestry | 2.32x | 2.32x | 1.13-4.46x |

## Per fixture

| fixture | track | n | rounds | A (ms) | B (ms) | speedup |
|---|---|---|---|---|---|---|
| adversarial_shared_100 | changeful | 100 | 490 | 1.20 | 0.51 | 2.34x |
| adversarial_shared_100 | kernel | 100 | 1405 | 3.67 | 1.49 | 2.47x |
| adversarial_shared_100 | wallet | 100 | 490 | 1.20 | 0.51 | 2.35x |
| adversarial_shared_20 | changeful | 20 | 49 | 0.05 | 0.04 | 1.33x |
| adversarial_shared_20 | kernel | 20 | 2654 | 4.08 | 1.86 | 2.19x |
| adversarial_shared_20 | wallet | 20 | 49 | 0.08 | 0.04 | 1.89x |
| adversarial_shared_200 | changeful | 200 | 2499 | 9.95 | 3.30 | 3.01x |
| adversarial_shared_200 | kernel | 200 | 5571 | 22.75 | 7.52 | 3.03x |
| adversarial_shared_200 | wallet | 200 | 2499 | 9.99 | 3.33 | 3.00x |
| adversarial_shared_50 | changeful | 50 | 21 | 0.03 | 0.03 | 1.00x |
| adversarial_shared_50 | kernel | 50 | 3355 | 6.22 | 2.57 | 2.42x |
| adversarial_shared_50 | wallet | 50 | 21 | 0.05 | 0.03 | 1.63x |
| high_feerate_100 | changeful | 100 | 1558 | 4.34 | 1.82 | 2.39x |
| high_feerate_100 | kernel | 100 | 9321 | 29.00 | 8.91 | 3.25x |
| high_feerate_100 | wallet | 100 | 1558 | 4.35 | 1.81 | 2.40x |
| high_feerate_20 | changeful | 20 | 14 | 0.02 | 0.02 | 1.33x |
| high_feerate_20 | kernel | 20 | 2373 | 3.28 | 1.46 | 2.24x |
| high_feerate_20 | wallet | 20 | 14 | 0.01 | 0.01 | 1.38x |
| high_feerate_200 | changeful | 200 | 3821 | 24.24 | 5.76 | 4.21x |
| high_feerate_200 | kernel | 200 | 3821 | 24.28 | 5.72 | 4.25x |
| high_feerate_200 | wallet | 200 | 3821 | 24.06 | 5.74 | 4.19x |
| high_feerate_50 | changeful | 50 | 52 | 0.08 | 0.07 | 1.07x |
| high_feerate_50 | kernel | 50 | 1644 | 3.34 | 1.27 | 2.64x |
| high_feerate_50 | wallet | 50 | 52 | 0.08 | 0.05 | 1.74x |
| nested_ancestry_100 | changeful | 100 | 46 | 0.14 | 0.06 | 2.30x |
| nested_ancestry_100 | kernel | 100 | 4219 | 15.91 | 3.84 | 4.14x |
| nested_ancestry_100 | wallet | 100 | 46 | 0.14 | 0.06 | 2.32x |
| nested_ancestry_20 | changeful | 20 | 2 | 0.01 | 0.00 | 2.90x |
| nested_ancestry_20 | kernel | 20 | 100000 | 208.67 | 76.35 | 2.73x |
| nested_ancestry_20 | wallet | 20 | 2 | 0.01 | 0.00 | 2.97x |
| nested_ancestry_200 | changeful | 200 | 23466 | 168.51 | 44.36 | 3.80x |
| nested_ancestry_200 | kernel | 200 | 23466 | 169.25 | 44.51 | 3.80x |
| nested_ancestry_200 | wallet | 200 | 23466 | 168.38 | 44.31 | 3.80x |
| nested_ancestry_50 | changeful | 50 | 162 | 0.33 | 0.16 | 2.11x |
| nested_ancestry_50 | kernel | 50 | 3582 | 10.55 | 3.23 | 3.27x |
| nested_ancestry_50 | wallet | 50 | 162 | 0.33 | 0.16 | 2.08x |
| no_ancestry_100 | changeful | 100 | 2222 | 3.73 | 1.76 | 2.12x |
| no_ancestry_100 | kernel | 100 | 2827->3211 | 4.24 | 2.50 | 1.70x |
| no_ancestry_100 | wallet | 100 | 2222 | 3.72 | 1.74 | 2.13x |
| no_ancestry_20 | changeful | 20 | 14 | 0.02 | 0.01 | 2.42x |
| no_ancestry_20 | kernel | 20 | 152->587 | 0.18 | 0.37 | 0.49x |
| no_ancestry_20 | wallet | 20 | 14 | 0.01 | 0.01 | 1.60x |
| no_ancestry_200 | changeful | 200 | 8127 | 19.83 | 6.81 | 2.91x |
| no_ancestry_200 | kernel | 200 | 24024->24216 | 53.56 | 22.93 | 2.34x |
| no_ancestry_200 | wallet | 200 | 8127 | 19.31 | 6.77 | 2.85x |
| no_ancestry_50 | changeful | 50 | 1195 | 1.67 | 0.86 | 1.94x |
| no_ancestry_50 | kernel | 50 | 3992->4222 | 5.60 | 3.20 | 1.75x |
| no_ancestry_50 | wallet | 50 | 1195 | 1.66 | 0.83 | 2.01x |
| private_ancestry_100 | changeful | 100 | 468 | 0.87 | 0.39 | 2.23x |
| private_ancestry_100 | kernel | 100 | 468 | 0.88 | 0.39 | 2.26x |
| private_ancestry_100 | wallet | 100 | 468 | 0.88 | 0.39 | 2.26x |
| private_ancestry_20 | changeful | 20 | 17 | 0.02 | 0.02 | 1.12x |
| private_ancestry_20 | kernel | 20 | 765 | 0.86 | 0.45 | 1.92x |
| private_ancestry_20 | wallet | 20 | 17 | 0.01 | 0.01 | 1.13x |
| private_ancestry_200 | changeful | 200 | 24577 | 96.01 | 38.32 | 2.51x |
| private_ancestry_200 | kernel | 200 | 24577 | 96.36 | 38.72 | 2.49x |
| private_ancestry_200 | wallet | 200 | 24577 | 94.91 | 37.20 | 2.55x |
| private_ancestry_50 | changeful | 50 | 841 | 1.24 | 0.65 | 1.89x |
| private_ancestry_50 | kernel | 50 | 2721 | 4.40 | 2.28 | 1.93x |
| private_ancestry_50 | wallet | 50 | 841 | 1.22 | 0.64 | 1.92x |
| shared_ancestry_100 | changeful | 100 | 2945 | 9.55 | 3.49 | 2.74x |
| shared_ancestry_100 | kernel | 100 | 2945 | 9.65 | 3.50 | 2.76x |
| shared_ancestry_100 | wallet | 100 | 2945 | 9.46 | 3.55 | 2.67x |
| shared_ancestry_20 | changeful | 20 | 26 | 0.04 | 0.03 | 1.30x |
| shared_ancestry_20 | kernel | 20 | 9122 | 14.79 | 5.15 | 2.87x |
| shared_ancestry_20 | wallet | 20 | 26 | 0.02 | 0.02 | 1.28x |
| shared_ancestry_200 | changeful | 200 | 100000 | 755.91 | 216.59 | 3.49x |
| shared_ancestry_200 | kernel | 200 | 100000 | 749.85 | 218.11 | 3.44x |
| shared_ancestry_200 | wallet | 200 | 100000 | 744.78 | 216.98 | 3.43x |
| shared_ancestry_50 | changeful | 50 | 237 | 0.34 | 0.20 | 1.71x |
| shared_ancestry_50 | kernel | 50 | 237 | 0.34 | 0.19 | 1.78x |
| shared_ancestry_50 | wallet | 50 | 237 | 0.34 | 0.20 | 1.74x |
| smoke | changeful | 8 | 35 | 0.02 | 0.03 | 0.70x |
| smoke | kernel | 8 | 445 | 0.38 | 0.19 | 2.00x |
| smoke | wallet | 8 | 35 | 0.04 | 0.02 | 1.86x |
| subsidizing_ancestry_100 | changeful | 100 | 100000 | 453.35 | 171.42 | 2.64x |
| subsidizing_ancestry_100 | kernel | 100 | 100000 | 454.48 | 167.97 | 2.71x |
| subsidizing_ancestry_100 | wallet | 100 | 100000 | 453.02 | 168.02 | 2.70x |
| subsidizing_ancestry_20 | changeful | 20 | 104 | 0.10 | 0.06 | 1.74x |
| subsidizing_ancestry_20 | kernel | 20 | 100000 | 209.07 | 58.63 | 3.57x |
| subsidizing_ancestry_20 | wallet | 20 | 104 | 0.10 | 0.06 | 1.68x |
| subsidizing_ancestry_200 | changeful | 200 | 100000 | 621.69 | 171.06 | 3.63x |
| subsidizing_ancestry_200 | kernel | 200 | 100000 | 624.46 | 163.10 | 3.83x |
| subsidizing_ancestry_200 | wallet | 200 | 100000 | 627.37 | 170.86 | 3.67x |
| subsidizing_ancestry_50 | changeful | 50 | 55738 | 170.59 | 36.34 | 4.69x |
| subsidizing_ancestry_50 | kernel | 50 | 100000 | 315.10 | 120.48 | 2.62x |
| subsidizing_ancestry_50 | wallet | 50 | 55738 | 170.53 | 38.26 | 4.46x |
| wallet_mixed_100 | changeful | 100 | 2006 | 7.04 | 1.96 | 3.60x |
| wallet_mixed_100 | kernel | 100 | 2915 | 10.61 | 2.79 | 3.81x |
| wallet_mixed_100 | wallet | 100 | 2006 | 7.04 | 1.98 | 3.56x |
| wallet_mixed_20 | changeful | 20 | 5 | 0.01 | 0.00 | 1.98x |
| wallet_mixed_20 | kernel | 20 | 527 | 0.73 | 0.35 | 2.07x |
| wallet_mixed_20 | wallet | 20 | 5 | 0.01 | 0.00 | 2.09x |
| wallet_mixed_200 | changeful | 200 | 1107 | 6.38 | 1.52 | 4.19x |
| wallet_mixed_200 | kernel | 200 | 1107 | 6.40 | 1.53 | 4.18x |
| wallet_mixed_200 | wallet | 200 | 1107 | 6.36 | 1.53 | 4.15x |
| wallet_mixed_50 | changeful | 50 | 55 | 0.09 | 0.07 | 1.26x |
| wallet_mixed_50 | kernel | 50 | 1455 | 3.35 | 1.13 | 2.96x |
| wallet_mixed_50 | wallet | 50 | 55 | 0.09 | 0.07 | 1.25x |
