# Robustness experiments from GKKOC Section 7 / Appendix E.5

## 1. Welfare and misallocation (`misallocation_link.py`; saved data only)

- **Method:**
  - GKKOC report a 0.92 correlation between welfare gain and the change in
    misallocation across their robustness economies. Misallocation is the Hsieh–Klenow
    measure, (TFP* − TFP)/TFP*, in output units.
  - The code's `TFP_Star.txt` is in Q/K units, so misallocation here is
    1 − (TFP_Q/TFP*)^α with α = 0.4. The saved benchmark gives 0.150, against GKKOC's
    0.16.
  - The sample is 118 validated, revenue-feasible policies against 8 benchmarks;
    fixed-labour runs are excluded.
  - `misallocation_link_sample.json` lists these 118 evaluations as model-relative
    paths, each result with its benchmark folder. The script reads this list by
    default, so every copy of the model reproduces the reported sample.
  - `--rescan --out DIR` instead uses every validated evaluation in the copy and
    writes to a separate folder; it does not reproduce the thesis sample.
- **Results** (`misallocation_link.md`, `misallocation_link.json`):

  | Group | Policies | corr(CE2, misallocation reduction) | corr(CE2, ΔK) |
  |---|---:|---:|---:|
  | all | 118 | 0.83 | 0.06 |
  | estate tax 40% | 61 | **0.93** | −0.25 |
  | estate tax zero or near-zero (below 0.5%) | 52 | 0.66 | 0.59 |

  - **Regression** of CE2 on the misallocation reduction and ΔK, per benchmark: each
    1 pp reduction in misallocation goes with about +5 pp newborn CE2 (5.27 thesis,
    4.71 re-cal; R² 0.80 and 0.74). Capital adds only 0.07–0.14 per % of K.
  - **OWT vs OKIT:** OKIT raises K by ~39% but cuts misallocation by only 1.6 pp. OWT
    raises K by ~2% but cuts misallocation by 2.3 pp, and OWT has the higher welfare.
    This is GKKOC's mechanism.
  - **Removing the estate tax works differently:** 7%/−50%/0 has a slightly smaller
    TFP gain than 7%/−50%/40% (+14.3% vs +15.1%) but more capital (+25.5% vs +17.9%),
    and higher welfare. So the estate-tax gain is accumulation, not reallocation.

## 2–3. Wealth tax on top, and looser constraints (`tier1.py`)

**ontop (GKKOC E.10 vi–ix).** τ_w 2% and 3.062% added to τ_k 25% and τ_b 40%, under the
thesis calibration and saved benchmark.

- **wasted:** labour tax fixed (fixed-labour evaluator). The surplus revenue buys
  nothing valued.
- **rebated:** labour tax lowered to keep revenue at the benchmark.
- GKKOC: −9.9 / 0.0 (2%) and −14.2 / −1.0 (3.03%).

**looser (GKKOC E.10 i).** θ_max is re-fitted (regula falsi) so debt/output is 2.5; every
other parameter stays at the thesis calibration. Then:

- the OWT sweep τ_w {1.5, 2, 2.5, 3.062, 3.5}%;
- the OKIT sweep τ_k {−5, −10, −13.6, −20}%;
- the joint points 7/−50/40, 7/−50/0 and 6/−50/0.

The baseline is the fresh thesis benchmark. The 7/−50/0 point is evaluated against it
here; the other baseline points come from `model_spec_sensitivity_2022`. GKKOC: OWT
2.34%, CE2 4.2.

```bash
nohup caffeinate -i python3 experiments/robustness_gkkoc_2022/tier1.py \
  > experiments/robustness_gkkoc_2022/run.log 2>&1 &
```

- 17 evaluations plus about 4–7 θ solves; ~9–11 h.
- `--check-only` prints the plan; `--summary-only` rebuilds `tier1_results.md`.
- Resumable; outputs go only to `runs/`.
