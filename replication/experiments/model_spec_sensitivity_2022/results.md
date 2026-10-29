# Model-specification sensitivity (financing calibration, parameters fixed)

Each variant is compared with its own benchmark solved from scratch.  `saved_benchmark` is the published headline (saved benchmark).

## Benchmark moments

| Variant | Ent. pop. | Ent. wealth | Ent. in top 1% | Top 1% | Top 0.1% | Debt/Y | K | Y |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| saved_benchmark | 6.13% | 32.23% | 61.58% | 35.47% | 22.60% | 1.5630 | 4.0506 | 1.3453 |
| control | 6.13% | 32.32% | 54.75% | 35.58% | 22.12% | 1.5649 | 4.0598 | 1.3461 |
| productivity | 6.09% | 31.41% | 53.59% | 34.75% | 21.51% | 1.5461 | 4.0515 | 1.3422 |
| timing | 6.13% | 32.27% | 54.60% | 35.59% | 22.12% | 1.5644 | 4.0570 | 1.3456 |
| both | 6.09% | 31.41% | 53.60% | 34.76% | 21.51% | 1.5456 | 4.0488 | 1.3417 |

## Policies (relative to each variant's own benchmark)

| Variant | Policy | Newborn CE2 | Population CE2 | Labour tax | Output | Top 1% | Max iter |
|---|---|---:|---:|---:|---:|---:|---:|
| saved_benchmark | okit | 5.052% | 4.458% | 31.25% | +15.50% | 46.51% | 700 |
| saved_benchmark | owt | 8.491% | 4.180% | 15.38% | +5.76% | 44.48% | 700 |
| saved_benchmark | s5_1 | 19.429% | 9.896% | 14.34% | +16.85% | 55.64% | 700 |
| saved_benchmark | s5_3 | 19.828% | 10.240% | 11.04% | +16.41% | 56.78% | 700 |
| saved_benchmark | s5_4 | 19.865% | 10.334% | 11.37% | +16.72% | 56.71% | 700 |
| control | benchmark_anchor | 0.000% | 0.000% | 22.40% | +0.00% | 35.58% | 700 |
| control | okit | 4.951% | 4.400% | 31.28% | +15.41% | 46.53% | 2000 |
| control | owt | 8.391% | 4.127% | 15.42% | +5.68% | 44.49% | 700 |
| control | s5_1 | 19.330% | 9.848% | 14.37% | +16.76% | 55.66% | 2000 |
| control | s5_3 | 19.729% | 10.193% | 11.07% | +16.33% | 56.80% | 2000 |
| control | s5_4 | 19.766% | 10.286% | 11.41% | +16.63% | 56.72% | 2000 |
| productivity | okit | 5.142% | 4.464% | 31.19% | +15.63% | 46.08% | 2000 |
| productivity | owt | 8.596% | 4.108% | 15.25% | +6.01% | 44.16% | 700 |
| productivity | s5_1 | 19.534% | 9.767% | 14.20% | +17.14% | 55.43% | 2000 |
| productivity | s5_3 | 19.919% | 10.082% | 10.88% | +16.74% | 56.65% | 2000 |
| productivity | s5_4 | 19.958% | 10.176% | 11.22% | +17.04% | 56.57% | 2000 |
| timing | okit | 4.960% | 4.405% | 31.28% | +15.42% | 46.54% | 2000 |
| timing | owt | 8.385% | 4.120% | 15.42% | +5.68% | 44.51% | 700 |
| both | okit | 5.150% | 4.469% | 31.19% | +15.64% | 46.09% | 2000 |
| both | owt | 8.589% | 4.100% | 15.26% | +6.01% | 44.17% | 700 |

## Effects relative to the control (newborn CE2, percentage points)

- productivity, owt: +0.205
- productivity, okit: +0.191
- productivity, s5_1: +0.204
- productivity, s5_3: +0.190
- productivity, s5_4: +0.191
- timing, owt: -0.006
- timing, okit: +0.009
- both, owt: +0.198
- both, okit: +0.199
