# `7e965cf` vs `01bce2c`

- A: `7e965cf` (features: selection-view + lowest-fee-changeless)
- B: `01bce2c` (features: selection-view + lowest-fee-changeless)
- 126 fixture/track pairs, interleaved A/B per case, both pinned to core 22
- 0 warm-up and 1 measured runs each; speedup is the ratio of minimum samples

## Behaviour

- identical selections: **96/126**
- identical round counts: **54/126**
- identical solved/unsolved: **113/126**

| fixture | track | rounds A | rounds B | inputs A | inputs B | solved A | solved B |
|---|---|---|---|---|---|---|---|
| adversarial_shared_100 | changeful | 490 | 486 | 4 | 4 | True | True |
| adversarial_shared_100 | wallet | 490 | 486 | 4 | 4 | True | True |
| adversarial_shared_20 | kernel | 301 | 284 | 5 | 5 | True | True |
| adversarial_shared_200 | changeful | 2499 | 2480 | 6 | 6 | True | True |
| adversarial_shared_200 | kernel | 5571 | 5569 | 7 | 7 | True | True |
| adversarial_shared_200 | wallet | 2499 | 2480 | 6 | 6 | True | True |
| adversarial_shared_50 | changeful | 21 | 19 | 2 | 2 | True | True |
| adversarial_shared_50 | kernel | 3355 | 3353 | 4 | 4 | True | True |
| adversarial_shared_50 | wallet | 21 | 19 | 2 | 2 | True | True |
| high_feerate_100 | changeful | 1558 | 1559 | 7 | 7 | True | True |
| high_feerate_100 | kernel | 9321 | 9320 | 8 | 8 | True | True |
| high_feerate_100 | wallet | 1558 | 1559 | 7 | 7 | True | True |
| high_feerate_20 | changeful | 14 | 15 | 2 | 2 | True | True |
| high_feerate_20 | kernel | 43 | 32 | 4 | 4 | True | True |
| high_feerate_20 | wallet | 14 | 15 | 2 | 2 | True | True |
| high_feerate_200 | changeful | 3821 | 3822 | 15 | 15 | True | True |
| high_feerate_200 | wallet | 3821 | 3822 | 15 | 15 | True | True |
| high_feerate_50 | changeful | 52 | 53 | 4 | 4 | True | True |
| high_feerate_50 | kernel | 1644 | 1641 | 6 | 6 | True | True |
| high_feerate_50 | wallet | 52 | 53 | 4 | 4 | True | True |
| nested_ancestry_100 | kernel | 4219 | 4218 | 8 | 8 | True | True |
| nested_ancestry_20 | kernel | 200 | 30 | 13 | 13 | True | True |
| nested_ancestry_200 | changeful | 23466 | 23217 | 17 | 17 | True | True |
| nested_ancestry_200 | kernel | 23466 | 23216 | 17 | 17 | True | True |
| nested_ancestry_200 | wallet | 23466 | 23217 | 17 | 17 | True | True |
| nested_ancestry_50 | changeful | 162 | 94 | 4 | 4 | True | True |
| nested_ancestry_50 | kernel | 3582 | 3456 | 7 | 7 | True | True |
| nested_ancestry_50 | wallet | 162 | 94 | 4 | 4 | True | True |
| no_ancestry_100 | changeful | 2222 | 2212 | 4 | 4 | True | True |
| no_ancestry_100 | kernel | 3211 | 2827 | 5 | 5 | True | True |
| no_ancestry_100 | wallet | 2222 | 2212 | 4 | 4 | True | True |
| no_ancestry_1000 | changeful | 100000 | 100000 | 0 | 43 | False | True |
| no_ancestry_1000 | wallet | 100000 | 100000 | 439 | 43 | True | True |
| no_ancestry_20 | changeful | 14 | 13 | 2 | 2 | True | True |
| no_ancestry_20 | wallet | 14 | 13 | 2 | 2 | True | True |
| no_ancestry_200 | kernel | 24216 | 24024 | 10 | 10 | True | True |
| no_ancestry_2000 | changeful | 100000 | 100000 | 0 | 82 | False | True |
| no_ancestry_2000 | wallet | 100000 | 100000 | 793 | 82 | True | True |
| no_ancestry_50 | changeful | 1195 | 1191 | 4 | 4 | True | True |
| no_ancestry_50 | kernel | 4222 | 3992 | 6 | 6 | True | True |
| no_ancestry_50 | wallet | 1195 | 1191 | 4 | 4 | True | True |
| no_ancestry_500 | changeful | 100000 | 100000 | 0 | 23 | False | True |
| no_ancestry_500 | wallet | 100000 | 100000 | 260 | 23 | True | True |
| private_ancestry_100 | changeful | 468 | 467 | 6 | 6 | True | True |
| private_ancestry_100 | kernel | 468 | 466 | 6 | 6 | True | True |
| private_ancestry_100 | wallet | 468 | 467 | 6 | 6 | True | True |
| private_ancestry_20 | kernel | 207 | 182 | 7 | 7 | True | True |
| private_ancestry_200 | changeful | 24577 | 24506 | 16 | 16 | True | True |
| private_ancestry_200 | kernel | 24577 | 24505 | 16 | 16 | True | True |
| private_ancestry_200 | wallet | 24577 | 24506 | 16 | 16 | True | True |
| private_ancestry_50 | changeful | 841 | 839 | 3 | 3 | True | True |
| private_ancestry_50 | kernel | 2721 | 2705 | 7 | 7 | True | True |
| private_ancestry_50 | wallet | 841 | 839 | 3 | 3 | True | True |
| shared_ancestry_100 | changeful | 2945 | 2943 | 11 | 11 | True | True |
| shared_ancestry_100 | kernel | 2945 | 2943 | 11 | 11 | True | True |
| shared_ancestry_100 | wallet | 2945 | 2943 | 11 | 11 | True | True |
| shared_ancestry_1000 | changeful | 100000 | 100000 | 0 | 44 | False | True |
| shared_ancestry_1000 | wallet | 100000 | 100000 | 432 | 44 | True | True |
| shared_ancestry_20 | changeful | 26 | 20 | 2 | 2 | True | True |
| shared_ancestry_20 | kernel | 369 | 225 | 4 | 4 | True | True |
| shared_ancestry_20 | wallet | 26 | 20 | 2 | 2 | True | True |
| shared_ancestry_200 | changeful | 100000 | 100000 | 0 | 10 | False | True |
| shared_ancestry_200 | wallet | 100000 | 100000 | 109 | 10 | True | True |
| shared_ancestry_2000 | changeful | 100000 | 100000 | 0 | 91 | False | True |
| shared_ancestry_2000 | wallet | 100000 | 100000 | 826 | 91 | True | True |
| shared_ancestry_50 | changeful | 237 | 230 | 5 | 5 | True | True |
| shared_ancestry_50 | kernel | 237 | 229 | 5 | 5 | True | True |
| shared_ancestry_50 | wallet | 237 | 230 | 5 | 5 | True | True |
| shared_ancestry_500 | changeful | 100000 | 100000 | 0 | 20 | False | True |
| shared_ancestry_500 | wallet | 100000 | 100000 | 203 | 20 | True | True |
| smoke | changeful | 35 | 23 | 2 | 2 | True | True |
| smoke | kernel | 121 | 42 | 5 | 5 | True | True |
| smoke | wallet | 35 | 23 | 2 | 2 | True | True |
| subsidizing_ancestry_20 | changeful | 104 | 18 | 1 | 1 | True | True |
| subsidizing_ancestry_20 | kernel | 886 | 137 | 11 | 11 | True | True |
| subsidizing_ancestry_20 | wallet | 104 | 18 | 1 | 1 | True | True |
| subsidizing_ancestry_50 | changeful | 55738 | 55737 | 5 | 5 | True | True |
| subsidizing_ancestry_50 | wallet | 55738 | 55737 | 5 | 5 | True | True |
| wallet_mixed_100 | changeful | 2006 | 2002 | 6 | 6 | True | True |
| wallet_mixed_100 | kernel | 2915 | 2909 | 7 | 7 | True | True |
| wallet_mixed_100 | wallet | 2006 | 2002 | 6 | 6 | True | True |
| wallet_mixed_1000 | changeful | 100000 | 100000 | 0 | 47 | False | True |
| wallet_mixed_1000 | wallet | 100000 | 100000 | 0 | 47 | False | True |
| wallet_mixed_200 | changeful | 1107 | 1108 | 10 | 10 | True | True |
| wallet_mixed_200 | wallet | 1107 | 1108 | 10 | 10 | True | True |
| wallet_mixed_2000 | changeful | 100000 | 100000 | 0 | 94 | False | True |
| wallet_mixed_2000 | wallet | 100000 | 100000 | 0 | 94 | False | True |
| wallet_mixed_50 | changeful | 55 | 54 | 2 | 2 | True | True |
| wallet_mixed_50 | kernel | 1455 | 1446 | 4 | 4 | True | True |
| wallet_mixed_50 | wallet | 55 | 54 | 2 | 2 | True | True |
| wallet_mixed_500 | changeful | 100000 | 100000 | 0 | 25 | False | True |
| wallet_mixed_500 | wallet | 100000 | 100000 | 0 | 25 | False | True |

## Speedup

| track | group | geomean | median | range |
|---|---|---|---|---|
| kernel | no ancestry | 1.47x | 1.48x | 1.24-1.62x |
| kernel | with ancestry | 1.11x | 0.99x | 0.61-5.04x |
| changeful | no ancestry | 1.22x | 1.31x | 0.68-1.50x |
| changeful | with ancestry | 1.07x | 1.00x | 0.76-2.06x |
| wallet | no ancestry | 1.54x | 1.55x | 1.24-1.97x |
| wallet | with ancestry | 1.09x | 1.02x | 0.73-3.38x |

## Per fixture

| fixture | track | n | rounds | A (ms) | B (ms) | speedup |
|---|---|---|---|---|---|---|
| adversarial_shared_100 | changeful | 100 | 490->486 | 0.58 | 0.49 | 1.17x |
| adversarial_shared_100 | kernel | 100 | 1405 | 1.68 | 1.76 | 0.96x |
| adversarial_shared_100 | wallet | 100 | 490->486 | 0.58 | 0.49 | 1.20x |
| adversarial_shared_20 | changeful | 20 | 49 | 0.05 | 0.04 | 1.25x |
| adversarial_shared_20 | kernel | 20 | 301->284 | 0.29 | 0.27 | 1.07x |
| adversarial_shared_20 | wallet | 20 | 49 | 0.05 | 0.04 | 1.27x |
| adversarial_shared_200 | changeful | 200 | 2499->2480 | 3.63 | 2.93 | 1.24x |
| adversarial_shared_200 | kernel | 200 | 5571->5569 | 8.38 | 8.63 | 0.97x |
| adversarial_shared_200 | wallet | 200 | 2499->2480 | 3.60 | 2.91 | 1.24x |
| adversarial_shared_50 | changeful | 50 | 21->19 | 0.03 | 0.03 | 1.19x |
| adversarial_shared_50 | kernel | 50 | 3355->3353 | 2.80 | 3.09 | 0.91x |
| adversarial_shared_50 | wallet | 50 | 21->19 | 0.03 | 0.03 | 1.03x |
| high_feerate_100 | changeful | 100 | 1558->1559 | 2.02 | 1.78 | 1.14x |
| high_feerate_100 | kernel | 100 | 9321->9320 | 10.24 | 10.82 | 0.95x |
| high_feerate_100 | wallet | 100 | 1558->1559 | 2.02 | 1.85 | 1.09x |
| high_feerate_20 | changeful | 20 | 14->15 | 0.02 | 0.03 | 0.94x |
| high_feerate_20 | kernel | 20 | 43->32 | 0.05 | 0.05 | 1.11x |
| high_feerate_20 | wallet | 20 | 14->15 | 0.02 | 0.02 | 1.03x |
| high_feerate_200 | changeful | 200 | 3821->3822 | 6.43 | 6.49 | 0.99x |
| high_feerate_200 | kernel | 200 | 3821 | 6.55 | 6.62 | 0.99x |
| high_feerate_200 | wallet | 200 | 3821->3822 | 6.41 | 6.68 | 0.96x |
| high_feerate_50 | changeful | 50 | 52->53 | 0.07 | 0.08 | 0.84x |
| high_feerate_50 | kernel | 50 | 1644->1641 | 1.46 | 1.53 | 0.95x |
| high_feerate_50 | wallet | 50 | 52->53 | 0.07 | 0.08 | 0.90x |
| nested_ancestry_100 | changeful | 100 | 46 | 0.09 | 0.10 | 0.90x |
| nested_ancestry_100 | kernel | 100 | 4219->4218 | 4.70 | 4.73 | 0.99x |
| nested_ancestry_100 | wallet | 100 | 46 | 0.09 | 0.09 | 0.94x |
| nested_ancestry_20 | changeful | 20 | 2 | 0.01 | 0.01 | 0.76x |
| nested_ancestry_20 | kernel | 20 | 200->30 | 0.20 | 0.04 | 5.04x |
| nested_ancestry_20 | wallet | 20 | 2 | 0.01 | 0.01 | 0.79x |
| nested_ancestry_200 | changeful | 200 | 23466->23217 | 49.91 | 50.23 | 0.99x |
| nested_ancestry_200 | kernel | 200 | 23466->23216 | 51.77 | 48.95 | 1.06x |
| nested_ancestry_200 | wallet | 200 | 23466->23217 | 50.50 | 49.22 | 1.03x |
| nested_ancestry_50 | changeful | 50 | 162->94 | 0.33 | 0.19 | 1.72x |
| nested_ancestry_50 | kernel | 50 | 3582->3456 | 3.46 | 3.48 | 0.99x |
| nested_ancestry_50 | wallet | 50 | 162->94 | 0.26 | 0.20 | 1.30x |
| no_ancestry_100 | changeful | 100 | 2222->2212 | 1.87 | 1.46 | 1.28x |
| no_ancestry_100 | kernel | 100 | 3211->2827 | 2.71 | 1.83 | 1.48x |
| no_ancestry_100 | wallet | 100 | 2222->2212 | 2.23 | 1.44 | 1.55x |
| no_ancestry_1000 | changeful | 1000 | 100000 | 127.27 | 91.44 | 1.39x |
| no_ancestry_1000 | kernel | 1000 | 100000 | 128.74 | 79.28 | 1.62x |
| no_ancestry_1000 | wallet | 1000 | 100000 | 129.89 | 83.84 | 1.55x |
| no_ancestry_20 | changeful | 20 | 14->13 | 0.02 | 0.03 | 0.68x |
| no_ancestry_20 | kernel | 20 | 152 | 0.15 | 0.12 | 1.24x |
| no_ancestry_20 | wallet | 20 | 14->13 | 0.03 | 0.02 | 1.97x |
| no_ancestry_200 | changeful | 200 | 8127 | 7.50 | 5.97 | 1.26x |
| no_ancestry_200 | kernel | 200 | 24216->24024 | 25.47 | 17.17 | 1.48x |
| no_ancestry_200 | wallet | 200 | 8127 | 7.47 | 6.01 | 1.24x |
| no_ancestry_2000 | changeful | 2000 | 100000 | 137.73 | 92.00 | 1.50x |
| no_ancestry_2000 | kernel | 2000 | 100000 | 139.59 | 87.61 | 1.59x |
| no_ancestry_2000 | wallet | 2000 | 100000 | 144.02 | 92.18 | 1.56x |
| no_ancestry_50 | changeful | 50 | 1195->1191 | 1.00 | 0.76 | 1.31x |
| no_ancestry_50 | kernel | 50 | 4222->3992 | 3.84 | 2.67 | 1.44x |
| no_ancestry_50 | wallet | 50 | 1195->1191 | 1.15 | 0.77 | 1.49x |
| no_ancestry_500 | changeful | 500 | 100000 | 113.06 | 81.82 | 1.38x |
| no_ancestry_500 | kernel | 500 | 100000 | 113.03 | 78.70 | 1.44x |
| no_ancestry_500 | wallet | 500 | 100000 | 121.63 | 81.24 | 1.50x |
| private_ancestry_100 | changeful | 100 | 468->467 | 0.48 | 0.48 | 1.00x |
| private_ancestry_100 | kernel | 100 | 468->466 | 0.63 | 0.78 | 0.80x |
| private_ancestry_100 | wallet | 100 | 468->467 | 0.75 | 0.78 | 0.96x |
| private_ancestry_20 | changeful | 20 | 17 | 0.04 | 0.03 | 1.13x |
| private_ancestry_20 | kernel | 20 | 207->182 | 0.23 | 0.15 | 1.53x |
| private_ancestry_20 | wallet | 20 | 17 | 0.03 | 0.02 | 1.80x |
| private_ancestry_200 | changeful | 200 | 24577->24506 | 40.46 | 42.73 | 0.95x |
| private_ancestry_200 | kernel | 200 | 24577->24505 | 41.41 | 42.32 | 0.98x |
| private_ancestry_200 | wallet | 200 | 24577->24506 | 40.77 | 42.90 | 0.95x |
| private_ancestry_50 | changeful | 50 | 841->839 | 0.78 | 0.61 | 1.28x |
| private_ancestry_50 | kernel | 50 | 2721->2705 | 2.62 | 3.16 | 0.83x |
| private_ancestry_50 | wallet | 50 | 841->839 | 0.92 | 0.62 | 1.50x |
| shared_ancestry_100 | changeful | 100 | 2945->2943 | 4.39 | 3.78 | 1.16x |
| shared_ancestry_100 | kernel | 100 | 2945->2943 | 4.39 | 3.99 | 1.10x |
| shared_ancestry_100 | wallet | 100 | 2945->2943 | 4.21 | 3.85 | 1.10x |
| shared_ancestry_1000 | changeful | 1000 | 100000 | 846.28 | 861.33 | 0.98x |
| shared_ancestry_1000 | kernel | 1000 | 100000 | 849.27 | 854.93 | 0.99x |
| shared_ancestry_1000 | wallet | 1000 | 100000 | 855.66 | 859.48 | 1.00x |
| shared_ancestry_20 | changeful | 20 | 26->20 | 0.06 | 0.04 | 1.32x |
| shared_ancestry_20 | kernel | 20 | 369->225 | 0.58 | 0.31 | 1.88x |
| shared_ancestry_20 | wallet | 20 | 26->20 | 0.06 | 0.04 | 1.39x |
| shared_ancestry_200 | changeful | 200 | 100000 | 197.57 | 202.97 | 0.97x |
| shared_ancestry_200 | kernel | 200 | 100000 | 197.25 | 203.49 | 0.97x |
| shared_ancestry_200 | wallet | 200 | 100000 | 223.10 | 203.48 | 1.10x |
| shared_ancestry_2000 | changeful | 2000 | 100000 | 1541.07 | 1547.31 | 1.00x |
| shared_ancestry_2000 | kernel | 2000 | 100000 | 1542.19 | 1539.05 | 1.00x |
| shared_ancestry_2000 | wallet | 2000 | 100000 | 1550.00 | 1545.88 | 1.00x |
| shared_ancestry_50 | changeful | 50 | 237->230 | 0.30 | 0.22 | 1.35x |
| shared_ancestry_50 | kernel | 50 | 237->229 | 0.27 | 0.44 | 0.61x |
| shared_ancestry_50 | wallet | 50 | 237->230 | 0.30 | 0.38 | 0.80x |
| shared_ancestry_500 | changeful | 500 | 100000 | 523.26 | 525.04 | 1.00x |
| shared_ancestry_500 | kernel | 500 | 100000 | 523.84 | 524.75 | 1.00x |
| shared_ancestry_500 | wallet | 500 | 100000 | 527.10 | 524.18 | 1.01x |
| smoke | changeful | 8 | 35->23 | 0.04 | 0.03 | 1.20x |
| smoke | kernel | 8 | 121->42 | 0.13 | 0.08 | 1.62x |
| smoke | wallet | 8 | 35->23 | 0.04 | 0.05 | 0.73x |
| subsidizing_ancestry_100 | changeful | 100 | 100000 | 148.45 | 155.44 | 0.96x |
| subsidizing_ancestry_100 | kernel | 100 | 100000 | 150.76 | 156.72 | 0.96x |
| subsidizing_ancestry_100 | wallet | 100 | 100000 | 147.72 | 153.45 | 0.96x |
| subsidizing_ancestry_20 | changeful | 20 | 104->18 | 0.09 | 0.04 | 2.06x |
| subsidizing_ancestry_20 | kernel | 20 | 886->137 | 1.04 | 0.23 | 4.57x |
| subsidizing_ancestry_20 | wallet | 20 | 104->18 | 0.15 | 0.04 | 3.38x |
| subsidizing_ancestry_200 | changeful | 200 | 100000 | 190.85 | 185.58 | 1.03x |
| subsidizing_ancestry_200 | kernel | 200 | 100000 | 182.46 | 186.98 | 0.98x |
| subsidizing_ancestry_200 | wallet | 200 | 100000 | 189.53 | 186.92 | 1.01x |
| subsidizing_ancestry_50 | changeful | 50 | 55738->55737 | 39.36 | 41.28 | 0.95x |
| subsidizing_ancestry_50 | kernel | 50 | 100000 | 110.52 | 113.76 | 0.97x |
| subsidizing_ancestry_50 | wallet | 50 | 55738->55737 | 39.96 | 41.30 | 0.97x |
| wallet_mixed_100 | changeful | 100 | 2006->2002 | 2.33 | 2.33 | 1.00x |
| wallet_mixed_100 | kernel | 100 | 2915->2909 | 3.47 | 3.54 | 0.98x |
| wallet_mixed_100 | wallet | 100 | 2006->2002 | 2.37 | 2.32 | 1.02x |
| wallet_mixed_1000 | changeful | 1000 | 100000 | 863.13 | 874.22 | 0.99x |
| wallet_mixed_1000 | kernel | 1000 | 100000 | 867.33 | 869.71 | 1.00x |
| wallet_mixed_1000 | wallet | 1000 | 100000 | 866.25 | 866.19 | 1.00x |
| wallet_mixed_20 | changeful | 20 | 5 | 0.02 | 0.02 | 0.97x |
| wallet_mixed_20 | kernel | 20 | 31 | 0.07 | 0.08 | 0.86x |
| wallet_mixed_20 | wallet | 20 | 5 | 0.01 | 0.01 | 1.06x |
| wallet_mixed_200 | changeful | 200 | 1107->1108 | 1.74 | 1.88 | 0.92x |
| wallet_mixed_200 | kernel | 200 | 1107 | 2.14 | 1.79 | 1.19x |
| wallet_mixed_200 | wallet | 200 | 1107->1108 | 2.13 | 1.76 | 1.21x |
| wallet_mixed_2000 | changeful | 2000 | 100000 | 1562.71 | 1572.61 | 0.99x |
| wallet_mixed_2000 | kernel | 2000 | 100000 | 1563.15 | 1581.26 | 0.99x |
| wallet_mixed_2000 | wallet | 2000 | 100000 | 1573.13 | 1565.79 | 1.00x |
| wallet_mixed_50 | changeful | 50 | 55->54 | 0.07 | 0.09 | 0.83x |
| wallet_mixed_50 | kernel | 50 | 1455->1446 | 1.40 | 1.40 | 1.00x |
| wallet_mixed_50 | wallet | 50 | 55->54 | 0.06 | 0.05 | 1.18x |
| wallet_mixed_500 | changeful | 500 | 100000 | 511.73 | 520.35 | 0.98x |
| wallet_mixed_500 | kernel | 500 | 100000 | 514.59 | 524.84 | 0.98x |
| wallet_mixed_500 | wallet | 500 | 100000 | 516.50 | 519.21 | 0.99x |
