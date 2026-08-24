# Benchmark

## v0.4 resource and cost framework

`artifactor benchmark plan --profile small|medium|large|stress` is read-only. `benchmark run` records real native wall/CPU time, process RSS, cache state, executor, exit status, and repeat identity. Small and medium local runs default to three repeats; large/stress runners must be explicitly provisioned. `benchmark summarize` reports medians and ranges.

Rate-card calculations are labeled estimates. Observed cost is omitted unless an authorized billing artifact is supplied. Executor cost comparisons require scientific parity first.

Measured for v0.2.0 on 2026-08-06 with Python 3.12.1 on a 32-logical-CPU Windows workstation, using 80 samples, 500 RNA features, and 150 protein features:

| Budget | Wall time | Observed peak RSS | Permutations | Bootstrap iterations |
|---|---:|---:|---:|---:|
| quick | 3.81 s | 215 MiB | 99 | 20 |
| standard | 9.35 s | 243 MiB | 199 | 50 |

The standalone reports were 4.54 MiB. Recorded report stages were 0.52 seconds (quick) and 0.26 seconds (standard), below the initial 10-second and 15-MiB targets. The pipeline performs a final lightweight report pass after provenance is finalized so source checksums match delivered files.

This compact benchmark demonstrates relative overhead, not a universal performance claim. Run `python scripts/benchmark.py` on the target machine for locally relevant values. Standard production defaults support 999 permutations and 100 bootstrap iterations.

## v0.3.0 targeted-NGS

Measured on 2026-08-07 using the default 384 samples, 800 targets, and 200 loci, each of the four fixed-seed scenarios completed in 7.0–7.8 seconds including simulation, analysis, and offline report construction. This is below the five-minute pipeline and 15-second report release targets. Local outputs and resource telemetry are retained under `benchmark/ngs_v030_audit`; performance varies by hardware.
