# Benchmark

Measured on 2026-08-05 with Python 3.12.1 on a 32-logical-CPU Windows workstation, using 80 samples, 500 RNA features, and 150 protein features:

| Budget | Wall time | Observed peak RSS | Permutations | Bootstrap iterations |
|---|---:|---:|---:|---:|
| quick | 3.54 s | 211 MiB | 99 | 20 |
| standard | 9.42 s | 239 MiB | 199 | 50 |

This compact benchmark demonstrates relative overhead, not a universal performance claim. Run `python scripts/benchmark.py` on the target machine for locally relevant values. Standard production defaults support 999 permutations and 100 bootstrap iterations.
