#!/usr/bin/env python3
"""Three-tax follow-up runs for the thesis: the estate tax at the joint package, and the
welfare decomposition of removing it.

    phase estate  wealth tax 7%, capital-income tax -50%, estate tax 10%, 20%, 30%, 40%.
                  The estate-tax-0 point already exists in
                  experiments/policy_reoptimization_2022/runs/thesis and is reused when the
                  evaluator context is identical; otherwise it is solved again here.
    phase decomp  the same points with GKK_JOINT_FULL_OUTPUT=1 for 7%/-50% with estate tax
                  40% and 0, so the executable also writes CE_Decomposition.txt (GKKOC Table
                  X: consumption, leisure and bequest components, each split into a level
                  and a distribution part).  --with-separate adds the wealth-tax candidate
                  (3.062%, capital-income tax 0) with estate tax 40% and 0.
    phase all     estate, then decomp.

Evaluator settings copy the "thesis" evaluator of
experiments/policy_reoptimization_2022/reoptimize.py, so results are directly comparable
with the joint grid and Figure 1: executable
experiments/model_spec_sensitivity_2022/variants/control/build/eval.a (built from the live
sources), reported calibration, saved benchmark calibration/runs/business_financing_2022/
rn_reform, labour tax as the residual, budget tolerance 1e-4, 4 threads per solve,
GKK_DBN_MAX_ITER 2000, headline convergence standard (enforced by tools/policy_evaluation.py).

Full output does not change the equilibrium: the flag only makes the executable write extra
files.  The decomposition runs go to their own run folder; every run's request.json records
GKK_JOINT_FULL_OUTPUT=1.  Their CE2 must match the non-full-output values (checked in the
summary).

    python3 experiments/three_tax_2022/run_three_tax.py --check-only      # plan only, solves nothing
    python3 experiments/three_tax_2022/run_three_tax.py --phase all       # about 3-4 hours
    python3 experiments/three_tax_2022/run_three_tax.py --summary-only    # rebuild results.md

Outputs: experiments/three_tax_2022/runs/{estate,decomp}/ and results.json / results.md.
Re-running resumes from the evaluator cache.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from policy_evaluation import PolicyEvaluator, atomic_json  # noqa: E402

SENS = ROOT / "experiments" / "model_spec_sensitivity_2022"
EXE = SENS / "variants" / "control" / "build" / "eval.a"
THESIS_BENCH = ROOT / "calibration" / "runs" / "business_financing_2022" / "rn_reform"
HEADLINE = ROOT / "calibration" / "runs" / "headline_revalidation_2022" / "validated_headline.json"
REOPT = ROOT / "experiments" / "policy_reoptimization_2022"
RUNS = HERE / "runs"
LOCK = RUNS / "driver.lock"
OTHER_LOCKS = [REOPT / "runs" / "driver.lock", SENS / "recal" / "driver.lock", SENS / "runs" / "driver.lock"]

WIDE = ((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0))
LABOR_BOUNDS = (0.0, 0.60)
BUDGET_TOLERANCE = 1.0e-4
THREADS = 4
DBN_MAX_ITER = 2000
JOINT_W, JOINT_K = 0.07, -0.50
ESTATE = (0.10, 0.20, 0.30, 0.40)
OWT_W = 0.030618034
DECOMP = [(JOINT_W, JOINT_K, 0.40), (JOINT_W, JOINT_K, 0.0)]
SEPARATE = [(OWT_W, 0.0, 0.40), (OWT_W, 0.0, 0.0)]


class FullOutputEvaluator(PolicyEvaluator):
    """The same evaluator, but the executable also writes full output and CE_Decomposition.txt."""

    def environment(self, extra=None):
        env = super().environment(extra)
        env["GKK_JOINT_FULL_OUTPUT"] = "1"
        return env


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_build() -> None:
    """eval.a must still match the live sources it was built from (as reoptimize.py requires)."""
    record = json.loads((SENS / "variants" / "provenance.json").read_text())["control"]
    for name, digest in record["live_sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise SystemExit(f"{name} changed since variants/control was built; rebuild it first")
    for exe, digest in record["executables_sha256"].items():
        if sha(SENS / "variants" / "control" / "build" / exe) != digest:
            raise SystemExit(f"variants/control/build/{exe} does not match provenance.json")


def make(cls, run_root: Path) -> PolicyEvaluator:
    return cls(root=ROOT, executable=EXE, benchmark=THESIS_BENCH, run_root=run_root, threads=THREADS,
               bounds=WIDE, labor_bounds=LABOR_BOUNDS, budget_tolerance=BUDGET_TOLERANCE,
               fixed_labor=False, calibration_env=None)


def reopt_estate0(context_id: str) -> dict | None:
    """The existing 7%/-50%/estate-0 point, if it was solved in the same evaluator context."""
    path = REOPT / "runs" / "grid_points.json"
    if not path.exists():
        return None
    for p in json.loads(path.read_text()):
        if (p.get("status") == "ok" and p["calibration"] == "thesis" and p["group"] == "grid_bq0"
                and abs(p["tau_w"] - JOINT_W) < 1e-12 and abs(p["tau_k"] - JOINT_K) < 1e-12
                and p.get("context_id") == context_id):
            return p
    return None


def run_batch(ev: PolicyEvaluator, todo, max_parallel: int, out: str, group: str) -> None:
    def run(rates):
        try:
            return rates, {"status": "ok", **ev.evaluate_rates(rates)}
        except Exception as exc:  # one failure must not stop the batch
            return rates, {"status": "failed", "error": str(exc)}

    print(f"{out}: {len(todo)} points, {max_parallel} at a time", flush=True)
    records = []
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        for rates, r in pool.map(run, todo):
            records.append({"group": group, "rates": list(rates), **r})
            print(f"[{group}] w={rates[0]:.4f} k={rates[1]:+.3f} bq={rates[2]:.2f}: "
                  + (f"CE2 {r['ce2_newborn']:.4f}" if r["status"] == "ok" else f"FAILED {r['error']}"), flush=True)
    ev.write_index()
    atomic_json(RUNS / out, records)


# ----------------------------------------------------------------------------- summary
def parse_decomposition(path: Path) -> dict:
    """{'CE2': {'total': [NB, Pop], 'c': [...], 'cl': ..., ...}, 'CE1': {...}} from CE_Decomposition.txt."""
    out: dict = {"CE1": {}, "CE2": {}}
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"\s*(CE[12])(?:_(\w+))?\s+([-+0-9.EeDd]+)\s+([-+0-9.EeDd]+)", line)
        if m and not line.strip().endswith("Test"):
            name = m.group(2) or "total"
            vals = [float(x.replace("D", "E").replace("d", "e")) for x in (m.group(3), m.group(4))]
            out[m.group(1)].setdefault(name, vals)
    return out


def load(name: str) -> list:
    path = RUNS / name
    return json.loads(path.read_text()) if path.exists() else []


def summarise() -> None:
    estate, decomp = load("estate_points.json"), load("decomp_points.json")
    headline = json.loads(HEADLINE.read_text())["points"]
    ok = [p for p in estate if p["status"] == "ok"]
    context = ok[0]["context_id"] if ok else None
    e0 = reopt_estate0(context) if context else None
    series = sorted(ok + ([{**e0, "source": "reoptimisation grid (same context)"}] if e0 else []),
                    key=lambda p: p["tau_bq"])
    lines = ["# Three-tax follow-up: estate tax at the joint package and welfare decomposition", "",
             "Reported calibration, saved benchmark, labour tax residual; wealth tax 7%, capital-income tax -50%.", "",
             "| Estate tax | Newborn CE2 | Population CE2 | Labour tax | Output | Top 1% | Source |",
             "|---:|---:|---:|---:|---:|---:|---|"]
    for p in series:
        lines.append(f"| {100*p['tau_bq']:.0f}% | {p['ce2_newborn']:.3f} | {p['ce2_population']:.3f} | "
                     f"{100*p['tau_l']:.2f}% | {p['output_growth']:+.2f}% | {100*p['top1_wealth_share']:.2f}% | "
                     f"{p.get('source', 'this run')} |")
    for p in estate:
        if p["status"] != "ok":
            lines.append(f"| {100*p['rates'][2]:.0f}% | FAILED: {p.get('error', '')[:80]} | | | | | |")
    checks = []
    p40 = next((p for p in ok if abs(p["tau_bq"] - 0.40) < 1e-12), None)
    if p40:
        checks.append(f"estate 40% here {p40['ce2_newborn']:.4f} vs headline s5_4 {headline['s5_4']['ce2_newborn']:.4f}")
    if ok and not e0:
        checks.append("estate-0 point not reused: evaluator context differs from the re-optimisation runs")
    ces = [p["ce2_newborn"] for p in series]
    if len(ces) > 1:
        checks.append("newborn CE2 falls monotonically with the estate tax: "
                      + ("yes" if all(a > b for a, b in zip(ces, ces[1:])) else "NO"))
    lines += ["", "## Checks", "", *[f"- {c}" for c in checks], "", "## Welfare decomposition (CE2, newborn and population)", ""]
    decomp_out = {}
    reference = {(round(p["tau_w"], 6), round(p["tau_k"], 6), round(p["tau_bq"], 6)): p["ce2_newborn"]
                 for p in series}
    for p in decomp:
        if p["status"] != "ok":
            lines.append(f"- {p['rates']}: FAILED {p.get('error', '')[:120]}")
            continue
        f = ROOT / p["result_directory"] / "CE_Decomposition.txt"
        if not f.exists():
            lines.append(f"- {p['rates']}: CE_Decomposition.txt missing in {p['result_directory']}")
            continue
        d = parse_decomposition(f)
        key = f"{100*p['tau_w']:.3f}/{100*p['tau_k']:.0f}/{100*p['tau_bq']:.0f}"
        decomp_out[key] = {"rates": p["rates"], "ce2_newborn": p["ce2_newborn"], "decomposition": d,
                           "file": str(f.relative_to(ROOT))}
        ref = reference.get((round(p["tau_w"], 6), round(p["tau_k"], 6), round(p["tau_bq"], 6)))
        if ref is not None:
            lines.append(f"- {key}: full-output CE2 {p['ce2_newborn']:.4f} vs standard run {ref:.4f}")
        lines += ["", f"**{key}** (wealth / capital-income / estate tax, %)", "",
                  "| Component | Newborn | Population |", "|---|---:|---:|"]
        for comp in ("total", "c", "cl", "cd", "h", "hl", "hd", "b", "ch", "chl", "chd"):
            if comp in d["CE2"]:
                nb, pop = d["CE2"][comp]
                lines.append(f"| CE2_{comp} | {nb:.3f} | {pop:.3f} |")
    lines += ["", "c = consumption, h = leisure (hours), b = bequests, ch = consumption and leisure together;",
              "l = level (aggregate) part, d = distribution part (GKKOC Section VI.C, Table X).", ""]
    (HERE / "results.md").write_text("\n".join(lines) + "\n")
    atomic_json(HERE / "results.json", {"estate_series": series, "estate_runs": estate,
                                        "decomposition": decomp_out, "checks": checks})
    print("\n".join(lines))


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=["estate", "decomp", "all"], default="all")
    ap.add_argument("--with-separate", action="store_true",
                    help="also decompose the wealth-tax candidate with estate tax 40%% and 0 (2 more solves)")
    ap.add_argument("--max-parallel", type=int, default=2, help="2 was the most efficient on this Mac")
    ap.add_argument("--check-only", action="store_true", help="print the plan; solve nothing")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()
    if args.summary_only:
        summarise()
        return 0
    for path in (EXE, THESIS_BENCH / "output.txt", HEADLINE, SENS / "variants" / "provenance.json"):
        if not path.exists():
            raise SystemExit(f"missing input: {path}")
    check_build()
    estate_jobs = [(JOINT_W, JOINT_K, bq) for bq in ESTATE]
    decomp_jobs = DECOMP + (SEPARATE if args.with_separate else [])
    if args.check_only:
        if args.phase in ("estate", "all"):
            print("estate:", ", ".join(f"{100*b:.0f}%" for _, _, b in estate_jobs),
                  "at 7% / -50% (+ estate 0 if the evaluator context differs)")
        if args.phase in ("decomp", "all"):
            print("decomp (full output):", "; ".join(f"{100*w:.3f}/{100*k:.0f}/{100*b:.0f}" for w, k, b in decomp_jobs))
        n = (len(estate_jobs) if args.phase in ("estate", "all") else 0) + \
            (len(decomp_jobs) if args.phase in ("decomp", "all") else 0)
        print(f"{n} solves, {args.max_parallel} at a time, about 1 hour per pair.  Build check passed.  "
              "Check only: nothing was run.")
        return 0
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["GKK_DBN_MAX_ITER"] = str(DBN_MAX_ITER)  # the evaluator inherits GKK_*
    RUNS.mkdir(parents=True, exist_ok=True)
    for lock in (LOCK, *OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                os.kill(pid, 0)
                raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass  # stale lock from a stopped run
    LOCK.write_text(str(os.getpid()))
    try:
        if args.phase in ("estate", "all"):
            ev = make(PolicyEvaluator, RUNS / "estate")
            todo = list(estate_jobs)
            if reopt_estate0(ev.context_id) is None:
                print("evaluator context differs from the re-optimisation runs: solving estate 0 here too", flush=True)
                todo.append((JOINT_W, JOINT_K, 0.0))
            run_batch(ev, todo, args.max_parallel, "estate_points.json", "estate")
        if args.phase in ("decomp", "all"):
            ev = make(FullOutputEvaluator, RUNS / "decomp")
            run_batch(ev, decomp_jobs, args.max_parallel, "decomp_points.json", "decomp")
        summarise()
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
