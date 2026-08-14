# `e45bb58efef5` vs `2398ab2bd3a3`

- A: `e45bb58efef5752356d3299cfd545ca8059df4fb` (features: selection-view + lowest-fee-changeless)
- B: `2398ab2bd3a3539c11b7d4d11281bf013854ee29` (features: selection-view + lowest-fee-changeless)
- 126 fixture/track pairs, interleaved A/B per case, both pinned to core 22
- 0 warm-up and 1 measured runs each; speedup is the ratio of minimum samples

## Behaviour

- identical selections: **71/126**
- identical round counts: **42/126**
- identical solved/unsolved: **100/126**

| fixture | track | rounds A | rounds B | inputs A | inputs B | solved A | solved B |
|---|---|---|---|---|---|---|---|
| adversarial_shared_100 | changeful | 490 | 3902 | 4 | 4 | True | True |
| adversarial_shared_100 | kernel | 1405 | 100000 | 6 | 8 | True | True |
| adversarial_shared_100 | wallet | 490 | 3902 | 4 | 4 | True | True |
| adversarial_shared_20 | changeful | 49 | 93 | 2 | 2 | True | True |
| adversarial_shared_20 | kernel | 301 | 2955 | 5 | 5 | True | True |
| adversarial_shared_20 | wallet | 49 | 93 | 2 | 2 | True | True |
| adversarial_shared_200 | changeful | 2499 | 8086 | 6 | 6 | True | True |
| adversarial_shared_200 | kernel | 5571 | 100000 | 7 | 10 | True | True |
| adversarial_shared_200 | wallet | 2499 | 8086 | 6 | 6 | True | True |
| adversarial_shared_50 | changeful | 21 | 327 | 2 | 2 | True | True |
| adversarial_shared_50 | kernel | 3355 | 6725 | 4 | 4 | True | True |
| adversarial_shared_50 | wallet | 21 | 327 | 2 | 2 | True | True |
| high_feerate_100 | changeful | 1558 | 2436 | 7 | 7 | True | True |
| high_feerate_100 | kernel | 9321 | 29609 | 8 | 8 | True | True |
| high_feerate_100 | wallet | 1558 | 2436 | 7 | 7 | True | True |
| high_feerate_20 | changeful | 14 | 41 | 2 | 2 | True | True |
| high_feerate_20 | kernel | 43 | 118 | 4 | 4 | True | True |
| high_feerate_20 | wallet | 14 | 41 | 2 | 2 | True | True |
| high_feerate_200 | changeful | 3821 | 100000 | 15 | 17 | True | True |
| high_feerate_200 | kernel | 3821 | 100000 | 15 | 18 | True | True |
| high_feerate_200 | wallet | 3821 | 100000 | 15 | 17 | True | True |
| high_feerate_50 | changeful | 52 | 290 | 4 | 4 | True | True |
| high_feerate_50 | kernel | 1644 | 81328 | 6 | 6 | True | True |
| high_feerate_50 | wallet | 52 | 290 | 4 | 4 | True | True |
| nested_ancestry_100 | changeful | 46 | 5984 | 5 | 5 | True | True |
| nested_ancestry_100 | kernel | 4219 | 100000 | 8 | 9 | True | True |
| nested_ancestry_100 | wallet | 46 | 5984 | 5 | 5 | True | True |
| nested_ancestry_20 | kernel | 200 | 100000 | 13 | 0 | True | False |
| nested_ancestry_200 | changeful | 23466 | 100000 | 17 | 0 | True | False |
| nested_ancestry_200 | kernel | 23466 | 100000 | 17 | 0 | True | False |
| nested_ancestry_200 | wallet | 23466 | 100000 | 17 | 91 | True | True |
| nested_ancestry_50 | changeful | 162 | 100000 | 4 | 0 | True | False |
| nested_ancestry_50 | kernel | 3582 | 100000 | 7 | 0 | True | False |
| nested_ancestry_50 | wallet | 162 | 100000 | 4 | 14 | True | True |
| no_ancestry_100 | changeful | 2222 | 5436 | 4 | 4 | True | True |
| no_ancestry_100 | kernel | 3211 | 100000 | 5 | 0 | True | False |
| no_ancestry_100 | wallet | 2222 | 5436 | 4 | 4 | True | True |
| no_ancestry_1000 | changeful | 100000 | 100000 | 0 | 45 | False | True |
| no_ancestry_1000 | wallet | 100000 | 100000 | 439 | 45 | True | True |
| no_ancestry_20 | changeful | 14 | 163 | 2 | 2 | True | True |
| no_ancestry_20 | kernel | 152 | 409 | 4 | 4 | True | True |
| no_ancestry_20 | wallet | 14 | 163 | 2 | 2 | True | True |
| no_ancestry_200 | changeful | 8127 | 19208 | 9 | 9 | True | True |
| no_ancestry_200 | kernel | 24216 | 36025 | 10 | 10 | True | True |
| no_ancestry_200 | wallet | 8127 | 19208 | 9 | 9 | True | True |
| no_ancestry_2000 | changeful | 100000 | 100000 | 0 | 84 | False | True |
| no_ancestry_2000 | wallet | 100000 | 100000 | 793 | 84 | True | True |
| no_ancestry_50 | changeful | 1195 | 2307 | 4 | 4 | True | True |
| no_ancestry_50 | kernel | 4222 | 38000 | 6 | 6 | True | True |
| no_ancestry_50 | wallet | 1195 | 2307 | 4 | 4 | True | True |
| no_ancestry_500 | changeful | 100000 | 100000 | 0 | 24 | False | True |
| no_ancestry_500 | wallet | 100000 | 100000 | 260 | 24 | True | True |
| private_ancestry_100 | changeful | 468 | 953 | 6 | 6 | True | True |
| private_ancestry_100 | kernel | 468 | 20174 | 6 | 6 | True | True |
| private_ancestry_100 | wallet | 468 | 953 | 6 | 6 | True | True |
| private_ancestry_20 | changeful | 17 | 134 | 2 | 2 | True | True |
| private_ancestry_20 | kernel | 207 | 2721 | 7 | 7 | True | True |
| private_ancestry_20 | wallet | 17 | 134 | 2 | 2 | True | True |
| private_ancestry_200 | changeful | 24577 | 41381 | 16 | 16 | True | True |
| private_ancestry_200 | kernel | 24577 | 100000 | 16 | 0 | True | False |
| private_ancestry_200 | wallet | 24577 | 41381 | 16 | 16 | True | True |
| private_ancestry_50 | changeful | 841 | 3505 | 3 | 3 | True | True |
| private_ancestry_50 | kernel | 2721 | 100000 | 7 | 0 | True | False |
| private_ancestry_50 | wallet | 841 | 3505 | 3 | 3 | True | True |
| shared_ancestry_100 | changeful | 2945 | 100000 | 11 | 0 | True | False |
| shared_ancestry_100 | kernel | 2945 | 100000 | 11 | 0 | True | False |
| shared_ancestry_100 | wallet | 2945 | 100000 | 11 | 28 | True | True |
| shared_ancestry_20 | changeful | 26 | 607 | 2 | 2 | True | True |
| shared_ancestry_20 | kernel | 369 | 1913 | 4 | 4 | True | True |
| shared_ancestry_20 | wallet | 26 | 607 | 2 | 2 | True | True |
| smoke | changeful | 35 | 44 | 2 | 2 | True | True |
| smoke | kernel | 121 | 254 | 5 | 5 | True | True |
| smoke | wallet | 35 | 44 | 2 | 2 | True | True |
| subsidizing_ancestry_100 | changeful | 100000 | 100000 | 7 | 8 | True | True |
| subsidizing_ancestry_100 | kernel | 100000 | 100000 | 7 | 10 | True | True |
| subsidizing_ancestry_100 | wallet | 100000 | 100000 | 7 | 8 | True | True |
| subsidizing_ancestry_20 | changeful | 104 | 100000 | 1 | 0 | True | False |
| subsidizing_ancestry_20 | kernel | 886 | 100000 | 11 | 0 | True | False |
| subsidizing_ancestry_20 | wallet | 104 | 100000 | 1 | 17 | True | True |
| subsidizing_ancestry_200 | changeful | 100000 | 100000 | 8 | 12 | True | True |
| subsidizing_ancestry_200 | kernel | 100000 | 100000 | 0 | 12 | False | True |
| subsidizing_ancestry_200 | wallet | 100000 | 100000 | 8 | 12 | True | True |
| subsidizing_ancestry_50 | changeful | 55738 | 100000 | 5 | 6 | True | True |
| subsidizing_ancestry_50 | kernel | 100000 | 100000 | 7 | 8 | True | True |
| subsidizing_ancestry_50 | wallet | 55738 | 100000 | 5 | 6 | True | True |
| wallet_mixed_100 | changeful | 2006 | 2500 | 6 | 6 | True | True |
| wallet_mixed_100 | kernel | 2915 | 30099 | 7 | 7 | True | True |
| wallet_mixed_100 | wallet | 2006 | 2500 | 6 | 6 | True | True |
| wallet_mixed_1000 | changeful | 100000 | 100000 | 0 | 78 | False | True |
| wallet_mixed_1000 | kernel | 100000 | 100000 | 0 | 79 | False | True |
| wallet_mixed_1000 | wallet | 100000 | 100000 | 0 | 78 | False | True |
| wallet_mixed_20 | changeful | 5 | 275 | 2 | 2 | True | True |
| wallet_mixed_20 | kernel | 31 | 1059 | 4 | 4 | True | True |
| wallet_mixed_20 | wallet | 5 | 275 | 2 | 2 | True | True |
| wallet_mixed_200 | changeful | 1107 | 17363 | 10 | 10 | True | True |
| wallet_mixed_200 | kernel | 1107 | 100000 | 10 | 0 | True | False |
| wallet_mixed_200 | wallet | 1107 | 17363 | 10 | 10 | True | True |
| wallet_mixed_2000 | changeful | 100000 | 100000 | 0 | 129 | False | True |
| wallet_mixed_2000 | kernel | 100000 | 100000 | 0 | 130 | False | True |
| wallet_mixed_2000 | wallet | 100000 | 100000 | 0 | 129 | False | True |
| wallet_mixed_50 | changeful | 55 | 756 | 2 | 2 | True | True |
| wallet_mixed_50 | kernel | 1455 | 100000 | 4 | 0 | True | False |
| wallet_mixed_50 | wallet | 55 | 756 | 2 | 2 | True | True |
| wallet_mixed_500 | changeful | 100000 | 100000 | 0 | 28 | False | True |
| wallet_mixed_500 | wallet | 100000 | 100000 | 0 | 28 | False | True |

## Speedup

| track | group | geomean | median | range |
|---|---|---|---|---|
| kernel | no ancestry | 0.88x | 1.25x | 0.12-2.22x |
| kernel | with ancestry | 0.51x | 0.74x | 0.01-9.72x |
| changeful | no ancestry | 0.71x | 0.80x | 0.28-1.22x |
| changeful | with ancestry | 0.61x | 0.73x | 0.01-4.18x |
| wallet | no ancestry | 0.83x | 0.92x | 0.44-1.65x |
| wallet | with ancestry | 0.63x | 0.93x | 0.01-4.09x |

## Per fixture

| fixture | track | n | rounds | A (ms) | B (ms) | speedup |
|---|---|---|---|---|---|---|
| adversarial_shared_100 | changeful | 100 | 490->3902 | 0.62 | 2.34 | 0.26x |
| adversarial_shared_100 | kernel | 100 | 1405->100000 | 1.66 | 31.00 | 0.05x |
| adversarial_shared_100 | wallet | 100 | 490->3902 | 0.60 | 2.32 | 0.26x |
| adversarial_shared_20 | changeful | 20 | 49->93 | 0.06 | 0.05 | 1.21x |
| adversarial_shared_20 | kernel | 20 | 301->2955 | 0.29 | 0.92 | 0.31x |
| adversarial_shared_20 | wallet | 20 | 49->93 | 0.15 | 0.05 | 3.20x |
| adversarial_shared_200 | changeful | 200 | 2499->8086 | 3.76 | 7.27 | 0.52x |
| adversarial_shared_200 | kernel | 200 | 5571->100000 | 8.55 | 56.46 | 0.15x |
| adversarial_shared_200 | wallet | 200 | 2499->8086 | 3.79 | 7.30 | 0.52x |
| adversarial_shared_50 | changeful | 50 | 21->327 | 0.03 | 0.24 | 0.14x |
| adversarial_shared_50 | kernel | 50 | 3355->6725 | 3.14 | 2.22 | 1.41x |
| adversarial_shared_50 | wallet | 50 | 21->327 | 0.06 | 0.17 | 0.34x |
| high_feerate_100 | changeful | 100 | 1558->2436 | 2.33 | 1.66 | 1.41x |
| high_feerate_100 | kernel | 100 | 9321->29609 | 10.24 | 10.89 | 0.94x |
| high_feerate_100 | wallet | 100 | 1558->2436 | 2.00 | 1.66 | 1.20x |
| high_feerate_20 | changeful | 20 | 14->41 | 0.02 | 0.03 | 0.73x |
| high_feerate_20 | kernel | 20 | 43->118 | 0.06 | 0.04 | 1.31x |
| high_feerate_20 | wallet | 20 | 14->41 | 0.02 | 0.03 | 0.73x |
| high_feerate_200 | changeful | 200 | 3821->100000 | 6.68 | 126.84 | 0.05x |
| high_feerate_200 | kernel | 200 | 3821->100000 | 6.51 | 123.60 | 0.05x |
| high_feerate_200 | wallet | 200 | 3821->100000 | 6.86 | 126.67 | 0.05x |
| high_feerate_50 | changeful | 50 | 52->290 | 0.11 | 0.26 | 0.42x |
| high_feerate_50 | kernel | 50 | 1644->81328 | 1.52 | 20.43 | 0.07x |
| high_feerate_50 | wallet | 50 | 52->290 | 0.11 | 0.15 | 0.71x |
| nested_ancestry_100 | changeful | 100 | 46->5984 | 0.15 | 3.63 | 0.04x |
| nested_ancestry_100 | kernel | 100 | 4219->100000 | 4.88 | 28.42 | 0.17x |
| nested_ancestry_100 | wallet | 100 | 46->5984 | 0.14 | 3.71 | 0.04x |
| nested_ancestry_20 | changeful | 20 | 2 | 0.02 | 0.01 | 1.27x |
| nested_ancestry_20 | kernel | 20 | 200->100000 | 0.33 | 27.37 | 0.01x |
| nested_ancestry_20 | wallet | 20 | 2 | 0.02 | 0.01 | 1.39x |
| nested_ancestry_200 | changeful | 200 | 23466->100000 | 50.56 | 69.89 | 0.72x |
| nested_ancestry_200 | kernel | 200 | 23466->100000 | 50.80 | 68.83 | 0.74x |
| nested_ancestry_200 | wallet | 200 | 23466->100000 | 50.53 | 69.82 | 0.72x |
| nested_ancestry_50 | changeful | 50 | 162->100000 | 0.27 | 32.68 | 0.01x |
| nested_ancestry_50 | kernel | 50 | 3582->100000 | 3.85 | 32.26 | 0.12x |
| nested_ancestry_50 | wallet | 50 | 162->100000 | 0.26 | 32.97 | 0.01x |
| no_ancestry_100 | changeful | 100 | 2222->5436 | 2.04 | 2.57 | 0.80x |
| no_ancestry_100 | kernel | 100 | 3211->100000 | 2.88 | 23.14 | 0.12x |
| no_ancestry_100 | wallet | 100 | 2222->5436 | 2.28 | 2.35 | 0.97x |
| no_ancestry_1000 | changeful | 1000 | 100000 | 129.31 | 142.21 | 0.91x |
| no_ancestry_1000 | kernel | 1000 | 100000 | 131.69 | 80.31 | 1.64x |
| no_ancestry_1000 | wallet | 1000 | 100000 | 131.06 | 143.08 | 0.92x |
| no_ancestry_20 | changeful | 20 | 14->163 | 0.02 | 0.07 | 0.28x |
| no_ancestry_20 | kernel | 20 | 152->409 | 0.16 | 0.12 | 1.25x |
| no_ancestry_20 | wallet | 20 | 14->163 | 0.03 | 0.07 | 0.47x |
| no_ancestry_200 | changeful | 200 | 8127->19208 | 7.72 | 9.67 | 0.80x |
| no_ancestry_200 | kernel | 200 | 24216->36025 | 25.27 | 15.29 | 1.65x |
| no_ancestry_200 | wallet | 200 | 8127->19208 | 7.62 | 11.27 | 0.68x |
| no_ancestry_2000 | changeful | 2000 | 100000 | 136.78 | 331.57 | 0.41x |
| no_ancestry_2000 | kernel | 2000 | 100000 | 137.26 | 130.81 | 1.05x |
| no_ancestry_2000 | wallet | 2000 | 100000 | 144.47 | 331.67 | 0.44x |
| no_ancestry_50 | changeful | 50 | 1195->2307 | 1.06 | 0.96 | 1.11x |
| no_ancestry_50 | kernel | 50 | 4222->38000 | 3.62 | 8.70 | 0.42x |
| no_ancestry_50 | wallet | 50 | 1195->2307 | 1.33 | 0.81 | 1.65x |
| no_ancestry_500 | changeful | 500 | 100000 | 112.98 | 92.69 | 1.22x |
| no_ancestry_500 | kernel | 500 | 100000 | 115.38 | 52.07 | 2.22x |
| no_ancestry_500 | wallet | 500 | 100000 | 120.01 | 89.30 | 1.34x |
| private_ancestry_100 | changeful | 100 | 468->953 | 0.48 | 0.72 | 0.66x |
| private_ancestry_100 | kernel | 100 | 468->20174 | 0.49 | 5.87 | 0.08x |
| private_ancestry_100 | wallet | 100 | 468->953 | 0.47 | 0.51 | 0.93x |
| private_ancestry_20 | changeful | 20 | 17->134 | 0.04 | 0.06 | 0.63x |
| private_ancestry_20 | kernel | 20 | 207->2721 | 0.29 | 1.09 | 0.27x |
| private_ancestry_20 | wallet | 20 | 17->134 | 0.04 | 0.10 | 0.37x |
| private_ancestry_200 | changeful | 200 | 24577->41381 | 41.91 | 37.51 | 1.12x |
| private_ancestry_200 | kernel | 200 | 24577->100000 | 41.74 | 34.21 | 1.22x |
| private_ancestry_200 | wallet | 200 | 24577->41381 | 41.55 | 37.52 | 1.11x |
| private_ancestry_50 | changeful | 50 | 841->3505 | 0.84 | 1.58 | 0.53x |
| private_ancestry_50 | kernel | 50 | 2721->100000 | 2.59 | 21.04 | 0.12x |
| private_ancestry_50 | wallet | 50 | 841->3505 | 0.81 | 1.51 | 0.54x |
| shared_ancestry_100 | changeful | 100 | 2945->100000 | 3.90 | 39.48 | 0.10x |
| shared_ancestry_100 | kernel | 100 | 2945->100000 | 4.01 | 39.95 | 0.10x |
| shared_ancestry_100 | wallet | 100 | 2945->100000 | 3.95 | 40.40 | 0.10x |
| shared_ancestry_1000 | changeful | 1000 | 100000 | 851.79 | 247.50 | 3.44x |
| shared_ancestry_1000 | kernel | 1000 | 100000 | 855.76 | 266.85 | 3.21x |
| shared_ancestry_1000 | wallet | 1000 | 100000 | 858.48 | 251.06 | 3.42x |
| shared_ancestry_20 | changeful | 20 | 26->607 | 0.07 | 0.36 | 0.19x |
| shared_ancestry_20 | kernel | 20 | 369->1913 | 0.59 | 0.65 | 0.91x |
| shared_ancestry_20 | wallet | 20 | 26->607 | 0.06 | 0.21 | 0.27x |
| shared_ancestry_200 | changeful | 200 | 100000 | 196.35 | 66.26 | 2.96x |
| shared_ancestry_200 | kernel | 200 | 100000 | 197.98 | 65.38 | 3.03x |
| shared_ancestry_200 | wallet | 200 | 100000 | 231.29 | 66.65 | 3.47x |
| shared_ancestry_2000 | changeful | 2000 | 100000 | 1543.60 | 461.08 | 3.35x |
| shared_ancestry_2000 | kernel | 2000 | 100000 | 1542.19 | 459.76 | 3.35x |
| shared_ancestry_2000 | wallet | 2000 | 100000 | 1552.14 | 468.87 | 3.31x |
| shared_ancestry_50 | changeful | 50 | 237 | 0.36 | 0.13 | 2.79x |
| shared_ancestry_50 | kernel | 50 | 237 | 0.40 | 0.22 | 1.82x |
| shared_ancestry_50 | wallet | 50 | 237 | 0.36 | 0.21 | 1.65x |
| shared_ancestry_500 | changeful | 500 | 100000 | 516.23 | 129.70 | 3.98x |
| shared_ancestry_500 | kernel | 500 | 100000 | 518.92 | 131.78 | 3.94x |
| shared_ancestry_500 | wallet | 500 | 100000 | 514.87 | 129.38 | 3.98x |
| smoke | changeful | 8 | 35->44 | 0.06 | 0.02 | 2.44x |
| smoke | kernel | 8 | 121->254 | 0.13 | 0.12 | 1.13x |
| smoke | wallet | 8 | 35->44 | 0.04 | 0.03 | 1.40x |
| subsidizing_ancestry_100 | changeful | 100 | 100000 | 152.64 | 36.50 | 4.18x |
| subsidizing_ancestry_100 | kernel | 100 | 100000 | 151.39 | 27.44 | 5.52x |
| subsidizing_ancestry_100 | wallet | 100 | 100000 | 149.14 | 36.43 | 4.09x |
| subsidizing_ancestry_20 | changeful | 20 | 104->100000 | 0.15 | 24.04 | 0.01x |
| subsidizing_ancestry_20 | kernel | 20 | 886->100000 | 1.02 | 24.24 | 0.04x |
| subsidizing_ancestry_20 | wallet | 20 | 104->100000 | 0.15 | 24.63 | 0.01x |
| subsidizing_ancestry_200 | changeful | 200 | 100000 | 189.29 | 50.95 | 3.72x |
| subsidizing_ancestry_200 | kernel | 200 | 100000 | 180.41 | 53.77 | 3.36x |
| subsidizing_ancestry_200 | wallet | 200 | 100000 | 188.62 | 54.44 | 3.46x |
| subsidizing_ancestry_50 | changeful | 50 | 55738->100000 | 40.13 | 33.15 | 1.21x |
| subsidizing_ancestry_50 | kernel | 50 | 100000 | 110.86 | 26.13 | 4.24x |
| subsidizing_ancestry_50 | wallet | 50 | 55738->100000 | 40.11 | 32.71 | 1.23x |
| wallet_mixed_100 | changeful | 100 | 2006->2500 | 2.71 | 1.80 | 1.51x |
| wallet_mixed_100 | kernel | 100 | 2915->30099 | 3.60 | 10.40 | 0.35x |
| wallet_mixed_100 | wallet | 100 | 2006->2500 | 2.32 | 1.44 | 1.61x |
| wallet_mixed_1000 | changeful | 1000 | 100000 | 864.86 | 272.67 | 3.17x |
| wallet_mixed_1000 | kernel | 1000 | 100000 | 864.57 | 98.01 | 8.82x |
| wallet_mixed_1000 | wallet | 1000 | 100000 | 863.75 | 271.66 | 3.18x |
| wallet_mixed_20 | changeful | 20 | 5->275 | 0.02 | 0.17 | 0.13x |
| wallet_mixed_20 | kernel | 20 | 31->1059 | 0.07 | 0.66 | 0.11x |
| wallet_mixed_20 | wallet | 20 | 5->275 | 0.02 | 0.10 | 0.21x |
| wallet_mixed_200 | changeful | 200 | 1107->17363 | 2.06 | 14.04 | 0.15x |
| wallet_mixed_200 | kernel | 200 | 1107->100000 | 1.75 | 40.80 | 0.04x |
| wallet_mixed_200 | wallet | 200 | 1107->17363 | 1.79 | 14.21 | 0.13x |
| wallet_mixed_2000 | changeful | 2000 | 100000 | 1570.15 | 501.95 | 3.13x |
| wallet_mixed_2000 | kernel | 2000 | 100000 | 1573.51 | 161.93 | 9.72x |
| wallet_mixed_2000 | wallet | 2000 | 100000 | 1579.47 | 501.28 | 3.15x |
| wallet_mixed_50 | changeful | 50 | 55->756 | 0.11 | 0.34 | 0.33x |
| wallet_mixed_50 | kernel | 50 | 1455->100000 | 1.57 | 24.23 | 0.06x |
| wallet_mixed_50 | wallet | 50 | 55->756 | 0.11 | 0.52 | 0.20x |
| wallet_mixed_500 | changeful | 500 | 100000 | 519.50 | 158.02 | 3.29x |
| wallet_mixed_500 | kernel | 500 | 100000 | 516.49 | 56.38 | 9.16x |
| wallet_mixed_500 | wallet | 500 | 100000 | 516.46 | 160.76 | 3.21x |
