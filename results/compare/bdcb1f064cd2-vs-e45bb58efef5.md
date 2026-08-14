# `bdcb1f064cd2` vs `e45bb58efef5`

- A: `bdcb1f064cd20ab4d864e6f040f0d45a6fd5e8fc` (features: selection-view)
- B: `e45bb58efef5752356d3299cfd545ca8059df4fb` (features: selection-view + lowest-fee-changeless)
- 99 fixture/track pairs, interleaved A/B per case, both pinned to core 22
- 2 warm-up and 9 measured runs each; speedup is the ratio of minimum samples

## Behaviour

- identical selections: **97/99**
- identical round counts: **90/99**
- identical solved/unsolved: **97/99**

| fixture | track | rounds A | rounds B | inputs A | inputs B | solved A | solved B |
|---|---|---|---|---|---|---|---|
| adversarial_shared_20 | kernel | 2654 | 301 | 5 | 5 | True | True |
| high_feerate_20 | kernel | 2373 | 43 | 4 | 4 | True | True |
| nested_ancestry_20 | kernel | 100000 | 200 | 0 | 13 | False | True |
| no_ancestry_20 | kernel | 587 | 152 | 4 | 4 | True | True |
| private_ancestry_20 | kernel | 765 | 207 | 7 | 7 | True | True |
| shared_ancestry_20 | kernel | 9122 | 369 | 4 | 4 | True | True |
| smoke | kernel | 445 | 121 | 5 | 5 | True | True |
| subsidizing_ancestry_20 | kernel | 100000 | 886 | 0 | 11 | False | True |
| wallet_mixed_20 | kernel | 527 | 31 | 4 | 4 | True | True |

## Speedup

| track | group | geomean | median | range |
|---|---|---|---|---|
| kernel | no ancestry | 1.37x | 1.02x | 0.99-3.46x |
| kernel | with ancestry | 2.25x | 1.00x | 0.98-476.56x |
| changeful | no ancestry | 1.02x | 1.01x | 1.00-1.06x |
| changeful | with ancestry | 1.04x | 0.99x | 0.59-1.63x |
| wallet | no ancestry | 0.88x | 0.99x | 0.59-1.01x |
| wallet | with ancestry | 0.97x | 0.99x | 0.60-1.68x |

## Per fixture

| fixture | track | n | rounds | A (ms) | B (ms) | speedup |
|---|---|---|---|---|---|---|
| adversarial_shared_100 | changeful | 100 | 490 | 0.51 | 0.52 | 0.98x |
| adversarial_shared_100 | kernel | 100 | 1405 | 1.48 | 1.51 | 0.98x |
| adversarial_shared_100 | wallet | 100 | 490 | 0.51 | 0.53 | 0.98x |
| adversarial_shared_20 | changeful | 20 | 49 | 0.04 | 0.04 | 0.99x |
| adversarial_shared_20 | kernel | 20 | 2654->301 | 1.89 | 0.23 | 8.30x |
| adversarial_shared_20 | wallet | 20 | 49 | 0.06 | 0.04 | 1.61x |
| adversarial_shared_200 | changeful | 200 | 2499 | 3.36 | 3.36 | 1.00x |
| adversarial_shared_200 | kernel | 200 | 5571 | 7.47 | 7.61 | 0.98x |
| adversarial_shared_200 | wallet | 200 | 2499 | 3.33 | 3.38 | 0.99x |
| adversarial_shared_50 | changeful | 50 | 21 | 0.03 | 0.02 | 1.57x |
| adversarial_shared_50 | kernel | 50 | 3355 | 2.59 | 2.56 | 1.01x |
| adversarial_shared_50 | wallet | 50 | 21 | 0.02 | 0.03 | 0.60x |
| high_feerate_100 | changeful | 100 | 1558 | 1.80 | 1.82 | 0.99x |
| high_feerate_100 | kernel | 100 | 9321 | 8.94 | 8.97 | 1.00x |
| high_feerate_100 | wallet | 100 | 1558 | 1.82 | 1.83 | 0.99x |
| high_feerate_20 | changeful | 20 | 14 | 0.01 | 0.02 | 0.59x |
| high_feerate_20 | kernel | 20 | 2373->43 | 1.49 | 0.05 | 29.48x |
| high_feerate_20 | wallet | 20 | 14 | 0.01 | 0.02 | 0.60x |
| high_feerate_200 | changeful | 200 | 3821 | 5.79 | 5.85 | 0.99x |
| high_feerate_200 | kernel | 200 | 3821 | 5.76 | 5.81 | 0.99x |
| high_feerate_200 | wallet | 200 | 3821 | 5.80 | 5.85 | 0.99x |
| high_feerate_50 | changeful | 50 | 52 | 0.05 | 0.05 | 0.98x |
| high_feerate_50 | kernel | 50 | 1644 | 1.26 | 1.28 | 0.99x |
| high_feerate_50 | wallet | 50 | 52 | 0.05 | 0.05 | 1.01x |
| nested_ancestry_100 | changeful | 100 | 46 | 0.06 | 0.06 | 1.02x |
| nested_ancestry_100 | kernel | 100 | 4219 | 3.92 | 3.93 | 1.00x |
| nested_ancestry_100 | wallet | 100 | 46 | 0.06 | 0.06 | 1.02x |
| nested_ancestry_20 | changeful | 20 | 2 | 0.00 | 0.00 | 1.62x |
| nested_ancestry_20 | kernel | 20 | 100000->200 | 71.40 | 0.15 | 476.56x |
| nested_ancestry_20 | wallet | 20 | 2 | 0.00 | 0.00 | 0.64x |
| nested_ancestry_200 | changeful | 200 | 23466 | 44.53 | 44.65 | 1.00x |
| nested_ancestry_200 | kernel | 200 | 23466 | 44.38 | 44.39 | 1.00x |
| nested_ancestry_200 | wallet | 200 | 23466 | 44.32 | 45.02 | 0.98x |
| nested_ancestry_50 | changeful | 50 | 162 | 0.15 | 0.15 | 1.00x |
| nested_ancestry_50 | kernel | 50 | 3582 | 3.05 | 3.08 | 0.99x |
| nested_ancestry_50 | wallet | 50 | 162 | 0.15 | 0.15 | 0.99x |
| no_ancestry_100 | changeful | 100 | 2222 | 1.64 | 1.63 | 1.01x |
| no_ancestry_100 | kernel | 100 | 3211 | 2.46 | 2.41 | 1.02x |
| no_ancestry_100 | wallet | 100 | 2222 | 1.66 | 1.64 | 1.01x |
| no_ancestry_20 | changeful | 20 | 14 | 0.01 | 0.01 | 1.00x |
| no_ancestry_20 | kernel | 20 | 587->152 | 0.34 | 0.10 | 3.46x |
| no_ancestry_20 | wallet | 20 | 14 | 0.01 | 0.01 | 0.59x |
| no_ancestry_200 | changeful | 200 | 8127 | 6.81 | 6.65 | 1.02x |
| no_ancestry_200 | kernel | 200 | 24216 | 21.07 | 21.20 | 0.99x |
| no_ancestry_200 | wallet | 200 | 8127 | 6.63 | 6.69 | 0.99x |
| no_ancestry_50 | changeful | 50 | 1195 | 0.88 | 0.83 | 1.06x |
| no_ancestry_50 | kernel | 50 | 4222 | 3.23 | 3.18 | 1.02x |
| no_ancestry_50 | wallet | 50 | 1195 | 0.84 | 0.84 | 1.00x |
| private_ancestry_100 | changeful | 100 | 468 | 0.40 | 0.41 | 0.98x |
| private_ancestry_100 | kernel | 100 | 468 | 0.40 | 0.40 | 1.00x |
| private_ancestry_100 | wallet | 100 | 468 | 0.39 | 0.40 | 0.98x |
| private_ancestry_20 | changeful | 20 | 17 | 0.02 | 0.01 | 1.62x |
| private_ancestry_20 | kernel | 20 | 765->207 | 0.45 | 0.13 | 3.53x |
| private_ancestry_20 | wallet | 20 | 17 | 0.02 | 0.01 | 1.64x |
| private_ancestry_200 | changeful | 200 | 24577 | 37.17 | 38.08 | 0.98x |
| private_ancestry_200 | kernel | 200 | 24577 | 37.18 | 37.99 | 0.98x |
| private_ancestry_200 | wallet | 200 | 24577 | 37.22 | 37.70 | 0.99x |
| private_ancestry_50 | changeful | 50 | 841 | 0.65 | 0.66 | 0.99x |
| private_ancestry_50 | kernel | 50 | 2721 | 2.26 | 2.30 | 0.98x |
| private_ancestry_50 | wallet | 50 | 841 | 0.65 | 0.70 | 0.93x |
| shared_ancestry_100 | changeful | 100 | 2945 | 3.52 | 3.53 | 0.99x |
| shared_ancestry_100 | kernel | 100 | 2945 | 3.54 | 3.56 | 0.99x |
| shared_ancestry_100 | wallet | 100 | 2945 | 3.51 | 3.57 | 0.98x |
| shared_ancestry_20 | changeful | 20 | 26 | 0.03 | 0.03 | 1.00x |
| shared_ancestry_20 | kernel | 20 | 9122->369 | 5.19 | 0.27 | 19.13x |
| shared_ancestry_20 | wallet | 20 | 26 | 0.02 | 0.03 | 0.61x |
| shared_ancestry_200 | changeful | 200 | 100000 | 210.66 | 212.47 | 0.99x |
| shared_ancestry_200 | kernel | 200 | 100000 | 212.23 | 214.27 | 0.99x |
| shared_ancestry_200 | wallet | 200 | 100000 | 211.13 | 214.69 | 0.98x |
| shared_ancestry_50 | changeful | 50 | 237 | 0.19 | 0.20 | 0.98x |
| shared_ancestry_50 | kernel | 50 | 237 | 0.20 | 0.20 | 0.98x |
| shared_ancestry_50 | wallet | 50 | 237 | 0.19 | 0.19 | 1.00x |
| smoke | changeful | 8 | 35 | 0.02 | 0.02 | 0.99x |
| smoke | kernel | 8 | 445->121 | 0.19 | 0.06 | 3.34x |
| smoke | wallet | 8 | 35 | 0.03 | 0.02 | 1.68x |
| subsidizing_ancestry_100 | changeful | 100 | 100000 | 164.56 | 164.24 | 1.00x |
| subsidizing_ancestry_100 | kernel | 100 | 100000 | 164.71 | 165.40 | 1.00x |
| subsidizing_ancestry_100 | wallet | 100 | 100000 | 165.91 | 166.28 | 1.00x |
| subsidizing_ancestry_20 | changeful | 20 | 104 | 0.06 | 0.06 | 0.98x |
| subsidizing_ancestry_20 | kernel | 20 | 100000->886 | 60.84 | 0.76 | 80.48x |
| subsidizing_ancestry_20 | wallet | 20 | 104 | 0.06 | 0.06 | 1.00x |
| subsidizing_ancestry_200 | changeful | 200 | 100000 | 173.95 | 173.92 | 1.00x |
| subsidizing_ancestry_200 | kernel | 200 | 100000 | 166.53 | 165.17 | 1.01x |
| subsidizing_ancestry_200 | wallet | 200 | 100000 | 171.76 | 174.16 | 0.99x |
| subsidizing_ancestry_50 | changeful | 50 | 55738 | 36.48 | 36.73 | 0.99x |
| subsidizing_ancestry_50 | kernel | 50 | 100000 | 118.06 | 119.15 | 0.99x |
| subsidizing_ancestry_50 | wallet | 50 | 55738 | 36.54 | 36.60 | 1.00x |
| wallet_mixed_100 | changeful | 100 | 2006 | 1.96 | 2.06 | 0.95x |
| wallet_mixed_100 | kernel | 100 | 2915 | 2.77 | 2.81 | 0.99x |
| wallet_mixed_100 | wallet | 100 | 2006 | 1.96 | 2.02 | 0.97x |
| wallet_mixed_20 | changeful | 20 | 5 | 0.01 | 0.00 | 1.63x |
| wallet_mixed_20 | kernel | 20 | 527->31 | 0.35 | 0.04 | 9.43x |
| wallet_mixed_20 | wallet | 20 | 5 | 0.00 | 0.00 | 1.01x |
| wallet_mixed_200 | changeful | 200 | 1107 | 1.51 | 1.55 | 0.98x |
| wallet_mixed_200 | kernel | 200 | 1107 | 1.54 | 1.54 | 1.00x |
| wallet_mixed_200 | wallet | 200 | 1107 | 1.54 | 1.55 | 0.99x |
| wallet_mixed_50 | changeful | 50 | 55 | 0.04 | 0.05 | 0.99x |
| wallet_mixed_50 | kernel | 50 | 1455 | 1.17 | 1.19 | 0.98x |
| wallet_mixed_50 | wallet | 50 | 55 | 0.04 | 0.05 | 0.97x |
