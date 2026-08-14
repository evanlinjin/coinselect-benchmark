# `e45bb58efef5` vs `fb5a0219d3ad`

- A: `e45bb58efef5752356d3299cfd545ca8059df4fb` (features: selection-view + lowest-fee-changeless)
- B: `fb5a0219d3ad1d34e48cae6678dbec66595c8a7e` (features: selection-view + lowest-fee-changeless)
- 126 fixture/track pairs, interleaved A/B per case, both pinned to core 22
- 0 warm-up and 1 measured runs each; speedup is the ratio of minimum samples

## Behaviour

- identical selections: **122/126**
- identical round counts: **72/126**
- identical solved/unsolved: **126/126**

| fixture | track | rounds A | rounds B | inputs A | inputs B | solved A | solved B |
|---|---|---|---|---|---|---|---|
| adversarial_shared_20 | kernel | 301 | 284 | 5 | 5 | True | True |
| adversarial_shared_200 | changeful | 2499 | 2497 | 6 | 6 | True | True |
| adversarial_shared_200 | kernel | 5571 | 5569 | 7 | 7 | True | True |
| adversarial_shared_200 | wallet | 2499 | 2497 | 6 | 6 | True | True |
| adversarial_shared_50 | kernel | 3355 | 3353 | 4 | 4 | True | True |
| high_feerate_100 | kernel | 9321 | 9320 | 8 | 8 | True | True |
| high_feerate_20 | kernel | 43 | 32 | 4 | 4 | True | True |
| high_feerate_50 | kernel | 1644 | 1641 | 6 | 6 | True | True |
| nested_ancestry_100 | changeful | 46 | 45 | 5 | 5 | True | True |
| nested_ancestry_100 | kernel | 4219 | 4218 | 8 | 8 | True | True |
| nested_ancestry_100 | wallet | 46 | 45 | 5 | 5 | True | True |
| nested_ancestry_20 | kernel | 200 | 30 | 13 | 13 | True | True |
| nested_ancestry_200 | changeful | 23466 | 23216 | 17 | 17 | True | True |
| nested_ancestry_200 | kernel | 23466 | 23216 | 17 | 17 | True | True |
| nested_ancestry_200 | wallet | 23466 | 23216 | 17 | 17 | True | True |
| nested_ancestry_50 | changeful | 162 | 93 | 4 | 4 | True | True |
| nested_ancestry_50 | kernel | 3582 | 3456 | 7 | 7 | True | True |
| nested_ancestry_50 | wallet | 162 | 93 | 4 | 4 | True | True |
| no_ancestry_100 | kernel | 3211 | 2827 | 5 | 5 | True | True |
| no_ancestry_200 | kernel | 24216 | 24024 | 10 | 10 | True | True |
| no_ancestry_50 | kernel | 4222 | 3992 | 6 | 6 | True | True |
| private_ancestry_100 | changeful | 468 | 466 | 6 | 6 | True | True |
| private_ancestry_100 | kernel | 468 | 466 | 6 | 6 | True | True |
| private_ancestry_100 | wallet | 468 | 466 | 6 | 6 | True | True |
| private_ancestry_20 | kernel | 207 | 182 | 7 | 7 | True | True |
| private_ancestry_200 | changeful | 24577 | 24505 | 16 | 16 | True | True |
| private_ancestry_200 | kernel | 24577 | 24505 | 16 | 16 | True | True |
| private_ancestry_200 | wallet | 24577 | 24505 | 16 | 16 | True | True |
| private_ancestry_50 | changeful | 841 | 840 | 3 | 3 | True | True |
| private_ancestry_50 | kernel | 2721 | 2705 | 7 | 7 | True | True |
| private_ancestry_50 | wallet | 841 | 840 | 3 | 3 | True | True |
| shared_ancestry_100 | changeful | 2945 | 2943 | 11 | 11 | True | True |
| shared_ancestry_100 | kernel | 2945 | 2943 | 11 | 11 | True | True |
| shared_ancestry_100 | wallet | 2945 | 2943 | 11 | 11 | True | True |
| shared_ancestry_20 | changeful | 26 | 22 | 2 | 2 | True | True |
| shared_ancestry_20 | kernel | 369 | 225 | 4 | 4 | True | True |
| shared_ancestry_20 | wallet | 26 | 22 | 2 | 2 | True | True |
| shared_ancestry_50 | changeful | 237 | 229 | 5 | 5 | True | True |
| shared_ancestry_50 | kernel | 237 | 229 | 5 | 5 | True | True |
| shared_ancestry_50 | wallet | 237 | 229 | 5 | 5 | True | True |
| smoke | changeful | 35 | 22 | 2 | 2 | True | True |
| smoke | kernel | 121 | 42 | 5 | 5 | True | True |
| smoke | wallet | 35 | 22 | 2 | 2 | True | True |
| subsidizing_ancestry_20 | changeful | 104 | 17 | 1 | 1 | True | True |
| subsidizing_ancestry_20 | kernel | 886 | 137 | 11 | 11 | True | True |
| subsidizing_ancestry_20 | wallet | 104 | 17 | 1 | 1 | True | True |
| subsidizing_ancestry_50 | changeful | 55738 | 55736 | 5 | 5 | True | True |
| subsidizing_ancestry_50 | wallet | 55738 | 55736 | 5 | 5 | True | True |
| wallet_mixed_100 | changeful | 2006 | 2001 | 6 | 6 | True | True |
| wallet_mixed_100 | kernel | 2915 | 2909 | 7 | 7 | True | True |
| wallet_mixed_100 | wallet | 2006 | 2001 | 6 | 6 | True | True |
| wallet_mixed_50 | changeful | 55 | 54 | 2 | 2 | True | True |
| wallet_mixed_50 | kernel | 1455 | 1446 | 4 | 4 | True | True |
| wallet_mixed_50 | wallet | 55 | 54 | 2 | 2 | True | True |

## Speedup

| track | group | geomean | median | range |
|---|---|---|---|---|
| kernel | no ancestry | 1.44x | 1.45x | 1.25-1.61x |
| kernel | with ancestry | 1.15x | 0.99x | 0.70-6.24x |
| changeful | no ancestry | 0.96x | 0.96x | 0.92-0.98x |
| changeful | with ancestry | 1.05x | 0.99x | 0.66-4.10x |
| wallet | no ancestry | 1.00x | 0.96x | 0.94-1.34x |
| wallet | with ancestry | 1.02x | 0.97x | 0.71-2.92x |

## Per fixture

| fixture | track | n | rounds | A (ms) | B (ms) | speedup |
|---|---|---|---|---|---|---|
| adversarial_shared_100 | changeful | 100 | 490 | 0.68 | 0.69 | 0.98x |
| adversarial_shared_100 | kernel | 100 | 1405 | 1.93 | 1.94 | 0.99x |
| adversarial_shared_100 | wallet | 100 | 490 | 0.66 | 0.69 | 0.95x |
| adversarial_shared_20 | changeful | 20 | 49 | 0.06 | 0.06 | 1.02x |
| adversarial_shared_20 | kernel | 20 | 301->284 | 0.33 | 0.31 | 1.06x |
| adversarial_shared_20 | wallet | 20 | 49 | 0.06 | 0.06 | 0.95x |
| adversarial_shared_200 | changeful | 200 | 2499->2497 | 4.13 | 4.19 | 0.99x |
| adversarial_shared_200 | kernel | 200 | 5571->5569 | 9.47 | 9.61 | 0.98x |
| adversarial_shared_200 | wallet | 200 | 2499->2497 | 4.21 | 4.20 | 1.00x |
| adversarial_shared_50 | changeful | 50 | 21 | 0.04 | 0.04 | 0.95x |
| adversarial_shared_50 | kernel | 50 | 3355->3353 | 3.31 | 3.33 | 0.99x |
| adversarial_shared_50 | wallet | 50 | 21 | 0.04 | 0.04 | 0.99x |
| high_feerate_100 | changeful | 100 | 1558 | 2.32 | 2.36 | 0.98x |
| high_feerate_100 | kernel | 100 | 9321->9320 | 11.89 | 11.96 | 0.99x |
| high_feerate_100 | wallet | 100 | 1558 | 2.32 | 2.38 | 0.97x |
| high_feerate_20 | changeful | 20 | 14 | 0.02 | 0.03 | 0.87x |
| high_feerate_20 | kernel | 20 | 43->32 | 0.06 | 0.05 | 1.27x |
| high_feerate_20 | wallet | 20 | 14 | 0.02 | 0.03 | 0.87x |
| high_feerate_200 | changeful | 200 | 3821 | 7.24 | 7.28 | 0.99x |
| high_feerate_200 | kernel | 200 | 3821 | 7.46 | 7.51 | 0.99x |
| high_feerate_200 | wallet | 200 | 3821 | 7.10 | 7.36 | 0.96x |
| high_feerate_50 | changeful | 50 | 52 | 0.08 | 0.08 | 0.91x |
| high_feerate_50 | kernel | 50 | 1644->1641 | 1.62 | 1.70 | 0.95x |
| high_feerate_50 | wallet | 50 | 52 | 0.07 | 0.08 | 0.90x |
| nested_ancestry_100 | changeful | 100 | 46->45 | 0.10 | 0.10 | 1.03x |
| nested_ancestry_100 | kernel | 100 | 4219->4218 | 5.17 | 5.38 | 0.96x |
| nested_ancestry_100 | wallet | 100 | 46->45 | 0.11 | 0.10 | 1.12x |
| nested_ancestry_20 | changeful | 20 | 2 | 0.01 | 0.01 | 0.91x |
| nested_ancestry_20 | kernel | 20 | 200->30 | 0.22 | 0.04 | 5.62x |
| nested_ancestry_20 | wallet | 20 | 2 | 0.01 | 0.01 | 0.85x |
| nested_ancestry_200 | changeful | 200 | 23466->23216 | 58.75 | 56.16 | 1.05x |
| nested_ancestry_200 | kernel | 200 | 23466->23216 | 59.04 | 55.99 | 1.05x |
| nested_ancestry_200 | wallet | 200 | 23466->23216 | 57.00 | 54.82 | 1.04x |
| nested_ancestry_50 | changeful | 50 | 162->93 | 0.32 | 0.25 | 1.26x |
| nested_ancestry_50 | kernel | 50 | 3582->3456 | 3.98 | 3.94 | 1.01x |
| nested_ancestry_50 | wallet | 50 | 162->93 | 0.22 | 0.13 | 1.65x |
| no_ancestry_100 | changeful | 100 | 2222 | 2.17 | 2.35 | 0.92x |
| no_ancestry_100 | kernel | 100 | 3211->2827 | 3.14 | 2.11 | 1.49x |
| no_ancestry_100 | wallet | 100 | 2222 | 2.11 | 2.22 | 0.95x |
| no_ancestry_1000 | changeful | 1000 | 100000 | 143.63 | 150.86 | 0.95x |
| no_ancestry_1000 | kernel | 1000 | 100000 | 145.85 | 90.51 | 1.61x |
| no_ancestry_1000 | wallet | 1000 | 100000 | 146.43 | 153.32 | 0.96x |
| no_ancestry_20 | changeful | 20 | 14 | 0.03 | 0.03 | 0.98x |
| no_ancestry_20 | kernel | 20 | 152 | 0.22 | 0.18 | 1.25x |
| no_ancestry_20 | wallet | 20 | 14 | 0.03 | 0.02 | 1.34x |
| no_ancestry_200 | changeful | 200 | 8127 | 8.54 | 8.93 | 0.96x |
| no_ancestry_200 | kernel | 200 | 24216->24024 | 28.21 | 20.14 | 1.40x |
| no_ancestry_200 | wallet | 200 | 8127 | 8.29 | 8.85 | 0.94x |
| no_ancestry_2000 | changeful | 2000 | 100000 | 155.86 | 161.56 | 0.96x |
| no_ancestry_2000 | kernel | 2000 | 100000 | 157.96 | 100.28 | 1.58x |
| no_ancestry_2000 | wallet | 2000 | 100000 | 163.55 | 169.78 | 0.96x |
| no_ancestry_50 | changeful | 50 | 1195 | 1.42 | 1.47 | 0.97x |
| no_ancestry_50 | kernel | 50 | 4222->3992 | 4.09 | 3.06 | 1.34x |
| no_ancestry_50 | wallet | 50 | 1195 | 1.29 | 1.37 | 0.94x |
| no_ancestry_500 | changeful | 500 | 100000 | 130.79 | 135.00 | 0.97x |
| no_ancestry_500 | kernel | 500 | 100000 | 130.29 | 89.72 | 1.45x |
| no_ancestry_500 | wallet | 500 | 100000 | 136.98 | 142.24 | 0.96x |
| private_ancestry_100 | changeful | 100 | 468->466 | 0.58 | 0.55 | 1.05x |
| private_ancestry_100 | kernel | 100 | 468->466 | 0.56 | 0.74 | 0.76x |
| private_ancestry_100 | wallet | 100 | 468->466 | 0.55 | 0.56 | 0.97x |
| private_ancestry_20 | changeful | 20 | 17 | 0.06 | 0.04 | 1.64x |
| private_ancestry_20 | kernel | 20 | 207->182 | 0.30 | 0.17 | 1.78x |
| private_ancestry_20 | wallet | 20 | 17 | 0.02 | 0.03 | 0.95x |
| private_ancestry_200 | changeful | 200 | 24577->24505 | 46.52 | 47.97 | 0.97x |
| private_ancestry_200 | kernel | 200 | 24577->24505 | 47.21 | 47.71 | 0.99x |
| private_ancestry_200 | wallet | 200 | 24577->24505 | 45.94 | 47.35 | 0.97x |
| private_ancestry_50 | changeful | 50 | 841->840 | 1.00 | 0.94 | 1.06x |
| private_ancestry_50 | kernel | 50 | 2721->2705 | 3.21 | 3.07 | 1.05x |
| private_ancestry_50 | wallet | 50 | 841->840 | 0.98 | 1.23 | 0.80x |
| shared_ancestry_100 | changeful | 100 | 2945->2943 | 4.68 | 4.75 | 0.98x |
| shared_ancestry_100 | kernel | 100 | 2945->2943 | 4.48 | 4.56 | 0.98x |
| shared_ancestry_100 | wallet | 100 | 2945->2943 | 4.41 | 4.76 | 0.93x |
| shared_ancestry_1000 | changeful | 1000 | 100000 | 966.34 | 972.29 | 0.99x |
| shared_ancestry_1000 | kernel | 1000 | 100000 | 970.75 | 976.44 | 0.99x |
| shared_ancestry_1000 | wallet | 1000 | 100000 | 973.59 | 975.66 | 1.00x |
| shared_ancestry_20 | changeful | 20 | 26->22 | 0.04 | 0.03 | 1.30x |
| shared_ancestry_20 | kernel | 20 | 369->225 | 0.40 | 0.24 | 1.66x |
| shared_ancestry_20 | wallet | 20 | 26->22 | 0.04 | 0.03 | 1.27x |
| shared_ancestry_200 | changeful | 200 | 100000 | 224.36 | 229.83 | 0.98x |
| shared_ancestry_200 | kernel | 200 | 100000 | 223.81 | 229.85 | 0.97x |
| shared_ancestry_200 | wallet | 200 | 100000 | 250.67 | 256.09 | 0.98x |
| shared_ancestry_2000 | changeful | 2000 | 100000 | 1757.56 | 1745.36 | 1.01x |
| shared_ancestry_2000 | kernel | 2000 | 100000 | 1762.13 | 1749.58 | 1.01x |
| shared_ancestry_2000 | wallet | 2000 | 100000 | 1771.22 | 1760.42 | 1.01x |
| shared_ancestry_50 | changeful | 50 | 237->229 | 0.39 | 0.42 | 0.92x |
| shared_ancestry_50 | kernel | 50 | 237->229 | 0.30 | 0.42 | 0.70x |
| shared_ancestry_50 | wallet | 50 | 237->229 | 0.40 | 0.41 | 0.98x |
| shared_ancestry_500 | changeful | 500 | 100000 | 587.98 | 588.27 | 1.00x |
| shared_ancestry_500 | kernel | 500 | 100000 | 587.05 | 591.06 | 0.99x |
| shared_ancestry_500 | wallet | 500 | 100000 | 588.27 | 592.51 | 0.99x |
| smoke | changeful | 8 | 35->22 | 0.04 | 0.04 | 0.95x |
| smoke | kernel | 8 | 121->42 | 0.14 | 0.08 | 1.89x |
| smoke | wallet | 8 | 35->22 | 0.04 | 0.03 | 1.40x |
| subsidizing_ancestry_100 | changeful | 100 | 100000 | 168.87 | 173.99 | 0.97x |
| subsidizing_ancestry_100 | kernel | 100 | 100000 | 170.92 | 176.21 | 0.97x |
| subsidizing_ancestry_100 | wallet | 100 | 100000 | 169.38 | 175.58 | 0.96x |
| subsidizing_ancestry_20 | changeful | 20 | 104->17 | 0.14 | 0.04 | 4.10x |
| subsidizing_ancestry_20 | kernel | 20 | 886->137 | 1.03 | 0.16 | 6.24x |
| subsidizing_ancestry_20 | wallet | 20 | 104->17 | 0.10 | 0.03 | 2.92x |
| subsidizing_ancestry_200 | changeful | 200 | 100000 | 214.88 | 222.25 | 0.97x |
| subsidizing_ancestry_200 | kernel | 200 | 100000 | 207.32 | 215.63 | 0.96x |
| subsidizing_ancestry_200 | wallet | 200 | 100000 | 216.57 | 220.75 | 0.98x |
| subsidizing_ancestry_50 | changeful | 50 | 55738->55736 | 44.59 | 47.97 | 0.93x |
| subsidizing_ancestry_50 | kernel | 50 | 100000 | 127.96 | 131.04 | 0.98x |
| subsidizing_ancestry_50 | wallet | 50 | 55738->55736 | 45.11 | 46.77 | 0.96x |
| wallet_mixed_100 | changeful | 100 | 2006->2001 | 2.55 | 2.90 | 0.88x |
| wallet_mixed_100 | kernel | 100 | 2915->2909 | 3.69 | 3.77 | 0.98x |
| wallet_mixed_100 | wallet | 100 | 2006->2001 | 2.66 | 2.75 | 0.97x |
| wallet_mixed_1000 | changeful | 1000 | 100000 | 987.86 | 989.36 | 1.00x |
| wallet_mixed_1000 | kernel | 1000 | 100000 | 985.13 | 991.70 | 0.99x |
| wallet_mixed_1000 | wallet | 1000 | 100000 | 987.51 | 993.49 | 0.99x |
| wallet_mixed_20 | changeful | 20 | 5 | 0.02 | 0.02 | 1.40x |
| wallet_mixed_20 | kernel | 20 | 31 | 0.07 | 0.07 | 0.98x |
| wallet_mixed_20 | wallet | 20 | 5 | 0.02 | 0.02 | 0.71x |
| wallet_mixed_200 | changeful | 200 | 1107 | 1.95 | 2.10 | 0.93x |
| wallet_mixed_200 | kernel | 200 | 1107 | 2.06 | 2.02 | 1.02x |
| wallet_mixed_200 | wallet | 200 | 1107 | 2.08 | 2.14 | 0.97x |
| wallet_mixed_2000 | changeful | 2000 | 100000 | 1791.94 | 1783.46 | 1.00x |
| wallet_mixed_2000 | kernel | 2000 | 100000 | 1795.27 | 1792.89 | 1.00x |
| wallet_mixed_2000 | wallet | 2000 | 100000 | 1807.19 | 1828.82 | 0.99x |
| wallet_mixed_50 | changeful | 50 | 55->54 | 0.07 | 0.11 | 0.66x |
| wallet_mixed_50 | kernel | 50 | 1455->1446 | 1.71 | 1.60 | 1.07x |
| wallet_mixed_50 | wallet | 50 | 55->54 | 0.11 | 0.12 | 0.93x |
| wallet_mixed_500 | changeful | 500 | 100000 | 609.29 | 593.58 | 1.03x |
| wallet_mixed_500 | kernel | 500 | 100000 | 601.15 | 603.58 | 1.00x |
| wallet_mixed_500 | wallet | 500 | 100000 | 585.37 | 590.12 | 0.99x |
