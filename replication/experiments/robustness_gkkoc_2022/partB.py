#!/usr/bin/env python3
"""Part B: tighten the two boundary results.

  B3  Subsidies beyond the -50% input limit.  The best package found sits at the limit
      (7% wealth tax, -50% subsidy, no estate tax: newborn CE2 23.54 under the thesis
      calibration, saved benchmark).  Evaluated here with the same calibration and
      benchmark, estate tax 0:
          tau_k {-60, -70, -80}% x tau_w {7, 8}%
      plus 7%/-50%/0 as a consistency check: it must reproduce 23.539 within 0.01 pp.
      Executable: variant_partb/guard (only the input check relaxed, make_partb.py).
      Points that fail are retried once with variant_partb/guard_rb (also with the
      bounded interest-rate search); its own consistency check is then added.
  B4  OKIT near zero under the looser constraints.  The best tested subsidy was the
      smallest (-5%), so tau_k {-2.5, 0, +5}% (tau_w 0, tau_b 40%) are evaluated with the
      bounded build already validated in the OKIT follow-up (same context, same cache).

Runs --max-parallel at a time (default 2), ~5 h.  Outputs only under
experiments/robustness_gkkoc_2022/runs/; summary in partB_results.md.  Re-running
resumes from the caches.

    python3 experiments/robustness_gkkoc_2022/partB.py --check-only
    python3 experiments/robustness_gkkoc_2022/partB.py
    python3 experiments/robustness_gkkoc_2022/partB.py --summary-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tier1 as t1                                          # noqa: E402
from tier1 import ROOT, RUNS, rc                            # noqa: E402

PB_DIR = HERE / "variant_partb"
EXE = {name: PB_DIR / name / "build" / "eval.a" for name in ("guard", "guard_rb")}
REOPT = ROOT / "experiments" / "policy_reoptimization_2022" / "runs"
CHECK = ("check_7_50_0", (0.07, -0.50, 0.0))
CHECK_CE2, CHECK_TOL = 23.5385, 0.01        # policy_reoptimization_2022 thesis grid
B3 = [(f"b3_{round(100*w)}_{round(-100*k)}_0", (w, k, 0.0))
      for k in (-0.60, -0.70, -0.80) for w in (0.07, 0.08)]
B4 = [(f"okit_{k:g}", (0.0, k, 0.40)) for k in (-0.025, 0.0, 0.05)]


def check_inputs(need_theta: bool = True) -> dict:
    prov_file = PB_DIR / "provenance.json"
    if not prov_file.exists() or not all(p.exists() for p in EXE.values()):
        raise SystemExit("part-B builds missing: run make_partb.py first")
    prov = json.loads(prov_file.read_text())
    if any(rc.sha(ROOT / n) != h for n, h in prov["live_sources_sha256"].items()):
        raise SystemExit("live sources changed since make_partb.py; rebuild")
    for name, exe in EXE.items():
        if rc.sha(exe) != prov[name]["eval_sha256"]:
            raise SystemExit(f"{name} executable changed since make_partb.py; rebuild")
    rb_prov = json.loads((t1.RB_DIR / "provenance.json").read_text())
    if rc.sha(t1.RB_EVAL) != rb_prov["eval_sha256"]:
        raise SystemExit("bounded (rbracket) build changed; rebuild with make_rbracket.py")
    theta = RUNS / "looser_theta.json"
    if need_theta and not theta.exists():
        raise SystemExit("looser_theta.json missing (run tier1.py first)")
    return json.loads(theta.read_text())


# ------------------------------------------------------------------------- summary

def summarise() -> None:
    load = lambda n: json.loads((RUNS / n).read_text()) if (RUNS / n).exists() else {}  # noqa: E731
    b3, b4, rbk = load("partB_b3.json"), load("partB_b4.json"), load("looser_rbracket.json")
    lines = ["# Part B: beyond the boundary results", ""]

    # B3 -----------------------------------------------------------------------------
    edge = {}
    for f in ("grid_points.json", "edge_points.json"):
        if (REOPT / f).exists():
            for p in json.loads((REOPT / f).read_text()):
                if p["calibration"] == "thesis" and p["status"] == "ok" and p["rates"][2] == 0.0 \
                        and abs(p["rates"][1] + 0.50) < 1e-9:
                    edge[(round(p["rates"][0], 4), -0.50)] = p
    pts = dict(edge)
    for name, rates in B3:
        r = b3.get(name + "_rb") if b3.get(name, {}).get("status") != "ok" else b3.get(name)
        if r and r.get("status") == "ok":
            pts[(round(rates[0], 4), rates[1])] = {**r, "build": "guard_rb" if name + "_rb" in b3
                                                   and b3[name].get("status") != "ok" else "guard"}
    lines += ["## B3: subsidies beyond −50% (thesis calibration, saved benchmark, estate tax 0)", "",
              "Newborn CE2 (%).  −50% column from the re-optimisation grid/edge sweep (original "
              "build); beyond −50% from the guard-relaxed build.", ""]
    ks = [-0.50, -0.60, -0.70, -0.80]
    ws = sorted({w for w, _ in pts if w >= 0.05})
    best = max(pts.values(), key=lambda p: p["ce2_newborn"]) if pts else None
    lines += ["| τ_w \\ τ_k | " + " | ".join(f"{100*k:+.0f}%" for k in ks) + " |", "|---|" + "---:|" * len(ks)]
    for w in ws:
        cells = []
        for k in ks:
            p = pts.get((w, k))
            v = "—" if p is None else f"{p['ce2_newborn']:.2f}"
            cells.append(f"**{v}**" if p is not None and p is best else v)
        lines.append(f"| {100*w:.1f}% | " + " | ".join(cells) + " |")
    if best:
        lines += ["", f"Best: τ_w {100*best['tau_w']:.1f}%, τ_k {100*best['tau_k']:+.0f}%, estate 0: newborn CE2 "
                  f"{best['ce2_newborn']:.2f} (population {best['ce2_population']:.2f}, labour tax "
                  f"{100*best['tau_l']:.2f}%, output {best['output_growth']:+.2f}%, top 1% "
                  f"{100*best['top1_wealth_share']:.2f}%).  At −50% the best is 23.54."]
    checks = {k: v for k, v in b3.items() if k.startswith("check_")}
    for k, v in checks.items():
        ok = v.get("status") == "ok" and abs(v["ce2_newborn"] - CHECK_CE2) <= CHECK_TOL
        lines.append(f"Consistency check {k}: "
                     + (f"{v['ce2_newborn']:.3f} vs {CHECK_CE2} → **{'passed' if ok else 'NOT passed'}**"
                        if v.get("status") == "ok" else "FAILED"))
    failed = [n for n, _ in B3 if b3.get(n, {}).get("status") == "failed"]
    if failed:
        lines.append("Retried with guard_rb: " + ", ".join(
            f"{n} → {b3.get(n + '_rb', {}).get('status', 'pending')}" for n in failed))
    lines.append("")

    # B4 -----------------------------------------------------------------------------
    okit = {}
    for n, r in list(rbk.items()) + list(b4.items()):
        if n.startswith("okit_") and r.get("status") == "ok":
            okit[round(r["tau_k"], 6)] = r
    looser = load("looser_policies.json")
    owt = [r for n, r in looser.items() if n.startswith("owt_") and r.get("status") == "ok"]
    lines += ["## B4: capital-income tax near zero under looser constraints (bounded build)", "",
              "| τ_k | " + " | ".join(f"{100*k:+.1f}%" for k in sorted(okit)) + " |",
              "|---|" + "---:|" * len(okit),
              "| Newborn CE2 | " + " | ".join(f"{okit[k]['ce2_newborn']:.2f}" for k in sorted(okit)) + " |",
              "| Labour tax | " + " | ".join(f"{100*okit[k]['tau_l']:.1f}%" for k in sorted(okit)) + " |", ""]
    if okit and owt:
        bk = max(okit.values(), key=lambda r: r["ce2_newborn"])
        bw = max(owt, key=lambda r: r["ce2_newborn"])
        lines.append(f"Best capital-income tax {100*bk['tau_k']:+.1f}% (CE2 {bk['ce2_newborn']:.2f}); best wealth "
                     f"tax {100*bw['tau_w']:.2f}% (CE2 {bw['ce2_newborn']:.2f}); wealth-tax advantage "
                     f"{bw['ce2_newborn'] - bk['ce2_newborn']:.2f} pp (baseline 3.44).")
        edge_k = min(okit) if bk is okit[min(okit)] else max(okit) if bk is okit[max(okit)] else None
        if edge_k is not None:
            lines.append(f"The best capital-income tax is at the edge of the tested range ({100*edge_k:+.1f}%).")
    (HERE / "partB_results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ----------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--dbn-max-iter", type=int, default=2000)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise()
        return 0
    theta = check_inputs()
    if args.check_only:
        print("B3 (thesis calibration, saved benchmark, guard build):")
        for name, rates in [CHECK, *B3]:
            print(f"  {name:16s} {rates}")
        print(f"B4 (looser benchmark {theta['benchmark']}, bounded build):")
        for name, rates in B4:
            print(f"  {name:16s} {rates}")
        print("Check only: nothing was run.")
        return 0
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)
    for lock in (t1.LOCK, *t1.OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                os.kill(pid, 0)
                raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass
    t1.LOCK.write_text(str(os.getpid()))
    try:
        guard = t1.evaluator(t1.SAVED_BENCH, RUNS / "partB_guard", args.threads, exe=EXE["guard"])
        looser_rb = t1.evaluator(ROOT / theta["benchmark"], RUNS / "looser_rbracket", args.threads,
                                 env=rc.param_env(theta["parameters"]), exe=t1.RB_EVAL)
        jobs = [(n, guard, r) for n, r in [CHECK, *B3]] + [(n, looser_rb, r) for n, r in B4]
        # B3 and B4 share one queue; results go to separate files by name.
        t1.run_jobs([j for j in jobs if not j[0].startswith("okit_")] +
                    [j for j in jobs if j[0].startswith("okit_")], args.max_parallel, "partB_all.json")
        allr = json.loads((RUNS / "partB_all.json").read_text())
        b3 = {n: r for n, r in allr.items() if not n.startswith("okit_")}
        b4 = {n: r for n, r in allr.items() if n.startswith("okit_")}
        t1.atomic_json(RUNS / "partB_b3.json", b3)
        t1.atomic_json(RUNS / "partB_b4.json", b4)
        failed = [(n, r) for n, r in B3 if b3.get(n, {}).get("status") != "ok"]
        if failed:
            guard_rb = t1.evaluator(t1.SAVED_BENCH, RUNS / "partB_guard_rb", args.threads, exe=EXE["guard_rb"])
            retry = [(n + "_rb", guard_rb, r) for n, r in failed] + [(CHECK[0] + "_rb", guard_rb, CHECK[1])]
            t1.run_jobs(retry, args.max_parallel, "partB_retry.json")
            b3.update(json.loads((RUNS / "partB_retry.json").read_text()))
            t1.atomic_json(RUNS / "partB_b3.json", b3)
        summarise()
    finally:
        t1.LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
