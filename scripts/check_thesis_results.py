#!/usr/bin/env python3
"""Check current thesis result coverage and arithmetic from portable saved evidence.

Read-only by default. Does not import a model driver, compile Fortran, solve a
model, download data, read omitted equilibrium arrays, or require the manuscript.
Use --manuscript PATH to additionally check that every table/figure label is mapped.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "replication"
ROB = "experiments/robustness_gkkoc_2022/"
SENS = "experiments/model_spec_sensitivity_2022/"
GRID = "experiments/grid_accuracy_2022/"
BASE = "calibration/runs/business_financing_2022/rn_reform"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def path(name, base=REP):
    p = Path(name)
    require(not p.is_absolute() and ".." not in p.parts, f"Nonportable path: {name}")
    p = base / p
    require(p.is_file() and not p.is_symlink(), f"Missing regular file: {p.relative_to(ROOT)}")
    require(p.resolve().is_relative_to(base), f"Path escapes package: {name}")
    return p


def load(name):
    return json.loads(path(name).read_text())


def close(a, b, label, tol=1e-9):
    require(math.isfinite(a) and math.isfinite(b) and
            math.isclose(a, b, rel_tol=tol, abs_tol=tol), f"{label}: {a} != {b}")


def displayed(values, expected, label, digits=2):
    got = [f"{v:.{digits}f}" for v in values]
    want = [f"{v:.{digits}f}" for v in expected]
    require(got == want, f"{label}: displayed {got}, expected {want}")


def report(name):
    """Preserve repeated rows (notably the nine Mean_Return_by_z observations)."""
    rows = {}
    for line in path(name).read_text().splitlines():
        fields = line.split()
        if len(fields) == 2:
            try:
                value = float(fields[1].replace("D", "E").replace("d", "e"))
            except ValueError:
                continue
            rows.setdefault(fields[0], []).append(value)
    return rows


def scalar(rows, key):
    require(key in rows and len(rows[key]) == 1, f"Expected one {key}")
    value = rows[key][0]
    require(math.isfinite(value), f"Nonfinite {key}")
    return value


def same_numbers(actual, expected, label):
    """Compare nested saved/rebuilt numeric records without ignoring extra fields."""
    if isinstance(expected, dict):
        require(actual.keys() == expected.keys(), label + ": different fields")
        for key in expected:
            same_numbers(actual[key], expected[key], label + ":" + str(key))
    elif isinstance(expected, list):
        require(len(actual) == len(expected), label + ": different lengths")
        for i, (a, b) in enumerate(zip(actual, expected)):
            same_numbers(a, b, label + f"[{i}]")
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        close(actual, expected, label)
    else:
        require(actual == expected, label + ": values differ")


def benchmark_moments(folder):
    raw, ent = report(folder + "/output.txt"), report(folder + "/Entrepreneur_10_50.txt")
    return {"top1": scalar(raw, "Wealth_Top_1%"),
            "ent_top1": scalar(ent, "Top_01_Entrepreneur_50") / 100,
            "ent_wealth": scalar(ent, "Entreprenur_50_A_Share") / 100,
            "ent_pop": scalar(ent, "Profits/Before_Tax_Income>50%") / 100,
            "top01": scalar(raw, "Wealth_Top_0.1%"),
            "debt_output": scalar(raw, "Debt_Output")}


def policy(record):
    """Match a compact policy record to its raw report and recorded tolerances."""
    require(record.get("feasible") is True and record.get("equilibrium_converged", True),
            "Policy is not marked feasible/converged")
    name = record["result_directory"] + "/output_exp.txt"
    p = path(name)
    if "output_sha256" in record:
        require(hashlib.sha256(p.read_bytes()).hexdigest() == record["output_sha256"],
                f"Policy report hash differs: {name}")
    raw = report(name)
    for key, raw_key in [("ce2_newborn", "CE2_NB(exp)"), ("ce2_population", "CE2_Pop(exp)"),
                         ("tau_l", "Average_Labor_Tax"), ("tau_w", "Wealth_Tax_Above"),
                         ("tau_k", "Tau_K"), ("tau_bq", "Tau_BQ"),
                         ("top1_wealth_share", "Wealth_Top_1%")]:
        if key in record:
            close(record[key], scalar(raw, raw_key), name + ": " + key)
    for key, limit in [("equilibrium_residual", 1e-7), ("aggregate_residual", 1e-6),
                       ("revenue_relative_gap", 1e-4)]:
        if key in record:
            require(0 <= record[key] <= limit, f"{name}: {key} exceeds recorded tolerance")
    return raw


def check_calibration():
    text = path("parameters.f90").read_text()
    for name, want in {"MaxAge": 81, "RetAge": 45, "alpha": .4, "mu": .9,
                       "DepRate": .05, "rho_lambda": .5, "rho_e": .9,
                       "sigma_e_eps": .2}.items():
        match = re.search(r"\b" + name + r"\s*=\s*([0-9.]+)", text, re.I)
        require(match is not None, "Missing parameter " + name)
        close(float(match[1]), want, name)
    main = path("GKK_Main.f90").read_text()
    for name, want in {"beta": .9593, "sigma_lambda_eps": .309, "gamma": .445,
                       "sigma": 4, "bq_0": .30, "chi_u": .20, "rho_z": .10,
                       "tauC": .075}.items():
        match = re.search(r"^\s*" + name + r"\s*=\s*([0-9.]+)", main, re.I | re.M)
        require(match is not None, "Missing baseline default " + name)
        close(float(match[1]), want, "baseline default " + name)
    scf = load("calibration/runs/scf_2022/best.json")["parameters"]
    financing = load("calibration/runs/business_financing_2022/best.json")
    displayed([scf[k] for k in ("sigma_z_eps", "p1_x", "p2_x")],
              [.2783, .0503, .0329], "calibrated entrepreneurial parameters", 4)
    displayed([scf["x_hi"], financing["theta_max"]], [1.46, 2.95], "calibrated scale/credit")
    for k, v in scf.items():
        close(v, financing["scf_parameters"][k], "same staged parameter " + k)
    rows = list(csv.DictReader(path("calibration/business_financing_2022.csv").open()))
    vals = {r["component"]: float(r["value"]) for r in rows}
    target = (vals["nonfinancial_business_total_liabilities"] +
              vals["nonfinancial_stock_issuance"] / vals["capitalization_rate"]) / vals["nominal_GDP"]
    close(target, financing["target"], "frozen financing arithmetic", 1e-8)
    audited = {r["definition_id"]: r for r in csv.DictReader(
        path("calibration/scf_2022_definition_moments_audited.csv").open())}
    expected = {"active_manager_paper_proxy": [13.09, 44.96, 3.44, 64.39],
                "business_majority_model_flow": [6.71, 24.33, 3.62, 39.77],
                "active_manager_and_business_majority": [4.03, 21.12, 5.24, 33.51],
                "business_majority_total_scf_income": [5.85, 20.51, 3.51, 34.33]}
    for key, want in expected.items():
        r = audited[key]
        pop, wealth, top = [float(r[k]) for k in ("entrepreneur_population_share",
                          "entrepreneur_wealth_share", "entrepreneur_share_top1")]
        displayed([100*pop, 100*wealth, wealth/pop, 100*top], want, key)
    repair = load("calibration/runs/repaired_statistics_2022/summary.json")["states"]["financing"]
    displayed([100*repair[k] for k in ("entrepreneur_population_share", "entrepreneur_wealth_share",
               "entrepreneurs_in_top1_share", "top1_wealth_share", "top01_wealth_share")],
              [6.13, 32.23, 54.77, 35.47, 22.15], "repaired benchmark distribution")
    raw = report(BASE + "/output.txt")
    displayed([scalar(raw, "Debt_Output"), scalar(raw, "Wealth_Output"),
               scalar(raw, "Mean_Labor_25_60"), 100*scalar(raw, "Total_Bequest_Wealth")],
              [1.56, 3.01, .40, 1.18], "benchmark aggregates")
    rec = load(SENS + "recal_results.json")
    for arm, want in [("control", [.2752, 1.39, .0496, .0345, 2.99]),
                      ("productivity", [.2863, 1.36, .0495, .0346, 3.02])]:
        ps = rec["arms"][arm]["financing"]["parameters"]
        for key, value, digits in zip(("sigma_z_eps", "x_hi", "p1_x", "p2_x", "theta_max"),
                                      want, (4, 2, 4, 4, 2)):
            displayed([ps[key]], [value], arm + ":" + key, digits)
    return {"financing_target": target, "SCF_definitions_checked": 4,
            "scope": "Constants, derived moments and saved calibration values; no SCF estimation or recalibration."}


def check_rn_and_separate():
    b, r = report(BASE + "/output.txt"), report(BASE + "/Tax_Reform/output_exp.txt")
    keys = ("KBAR", "QBAR", "TFP_Q", "NBAR", "YBAR", "CBAR", "wage")
    changes = [100*(scalar(r, k)/scalar(b, k)-1) for k in keys]
    displayed(changes, [16.69, 22.26, 4.77, 1.14, 9.11, 9.41, 7.88], "revenue-neutral table")
    displayed([100*scalar(r, "Wealth_Tax_Above")], [1.19], "revenue-neutral wealth tax")
    points = load("calibration/runs/headline_revalidation_2022/validated_headline.json")["points"]
    for name, want in [("owt", [15.38, 5.76, 7.64, 8.49, 4.18, 44.48]),
                       ("okit", [31.25, 15.50, 13.73, 5.05, 4.46, 46.51])]:
        p = points[name]; policy(p)
        displayed([100*p["tau_l"], p["output_growth"], p["consumption_growth"],
                   p["ce2_newborn"], p["ce2_population"], 100*p["top1_wealth_share"]], want, name)
    return {"RN_percentage_changes": dict(zip(keys, changes)), "separate_policies_checked": 2,
            "scope": "Current model column and saved policies; published comparison column is an external input."}


def check_estate():
    separate = load("calibration/runs/estate_tax_grid_2022/grid_results.json")["points"]
    want = [[12.21,5.73,15.74,8.89,10.17,48.28],[11.37,5.38,15.64,8.14,9.58,47.39],
            [10.49,5.01,15.55,7.36,8.96,46.45],[9.55,4.62,15.46,6.59,8.33,45.49],
            [8.49,4.18,15.38,5.76,7.64,44.48],[7.34,3.70,15.31,4.91,6.92,43.43],
            [6.08,3.18,15.24,4.05,6.18,42.35]]
    require(len(separate) == 7, "Separate estate sweep must contain seven points")
    for i, (item, expected) in enumerate(zip(separate, want)):
        r = item["result"]; policy(r); close(r["tau_bq"], i/10, "estate rate")
        displayed([r["ce2_newborn"], r["ce2_population"], 100*r["tau_l"],
                   r["output_growth"], r["consumption_growth"], 100*r["top1_wealth_share"]],
                  expected, "separate estate row " + str(i))
    data = load("experiments/three_tax_2022/results.json")
    want_joint = [[23.54,11.74,11.09,19.36,60.15],[22.71,11.42,11.15,18.73,59.35],
                  [21.84,11.08,11.21,18.09,58.52],[20.89,10.72,11.29,17.42,57.64],
                  [19.86,10.33,11.37,16.72,56.71]]
    require(len(data["estate_series"]) == 5, "Joint estate sweep must contain five points")
    for i, (r, want) in enumerate(zip(data["estate_series"], want_joint)):
        policy(r); close(r["tau_bq"], i/10, "joint estate rate")
        displayed([r["ce2_newborn"], r["ce2_population"], 100*r["tau_l"],
                   r["output_growth"], 100*r["top1_wealth_share"]], want, "joint estate row " + str(i))
    ds = []
    for name, want in [("7.000/-50/40", [19.86,10.33,15.74,3.57,-4.66]),
                       ("7.000/-50/0", [23.54,11.74,17.87,4.81,-5.20])]:
        entry = data["decomposition"][name]
        d = entry["decomposition"]["CE2"]; ds.append(d)
        raw_components = {}
        for line in path(entry["file"]).read_text().splitlines():
            fields = line.split()
            if fields and fields[0] in {"CE2", "CE2_chl", "CE2_chd", "CE2_ch"}:
                try: raw_components[fields[0]] = [float(x.replace("D", "E")) for x in fields[1:3]]
                except ValueError: pass  # Column heading, not a numeric observation.
        for component in ("total", "chl", "chd", "ch"):
            key = "CE2" if component == "total" else "CE2_" + component
            for i in (0, 1): close(d[component][i], raw_components[key][i], "raw welfare component")
        displayed([*d["total"], d["chl"][0], *d["chd"]], want, "decomposition " + name)
        for i in (0, 1):
            close((1+d["chl"][i]/100)*(1+d["chd"][i]/100), 1+d["ch"][i]/100,
                  "multiplicative consumption-leisure decomposition")
    level = math.log((1+ds[1]["chl"][0]/100)/(1+ds[0]["chl"][0]/100))
    dist = math.log((1+ds[1]["chd"][0]/100)/(1+ds[0]["chd"][0]/100))
    require(abs(level/(level+dist)-.6) < .01, "Level share should round to about 60%")
    r0, r40 = [policy(data["estate_series"][i]) for i in (0, 4)]
    wage_gain = 100*(scalar(r0,"wage_AT")/scalar(r40,"wage_AT")-1)
    require(len(r0["Mean_Return_by_z"]) == len(r40["Mean_Return_by_z"]) == 9,
            "Need nine ability-specific return observations")
    top_returns = [r40["Mean_Return_by_z"][8], r0["Mean_Return_by_z"][8]]
    displayed([wage_gain, *top_returns], [2.58,14.53,14.29], "new household mechanism paragraph")
    comparison = load("validation/saved_comparison.json")
    selected = {r["id"]: r["record"] for r in comparison["records"]}
    break_even = [100*selected[k]["tau_w"]/abs(selected[k]["tau_k"])
                  for k in ("joint_estate_40", "joint_subsidy_80", "joint_subsidy_95")]
    displayed(break_even, [14, 10, 9.5], "break-even return arithmetic", 1)
    return {"separate_estate_rows": 7, "joint_estate_rows": 5, "level_share": level/(level+dist),
            "after_tax_wage_gain_percent": wage_gain, "top_ability_pretax_returns_percent": top_returns,
            "break_even_returns_percent": break_even,
            "return_definition": "Raw Mean_Return_by_z ninth row; stationary wealth-weighted return, not a fixed-composition causal effect."}


def check_grid_accuracy():
    expected = {301: [8.13,5.07,19.34,22.97], 401: [8.04,5.14,19.16,22.78]}
    names = ("owt", "okit", "joint_bq40", "joint_bq0")
    result = {}
    for na, want in expected.items():
        d = load(GRID + f"results_na{na}.json")
        points = load(GRID + f"runs/na{na}/points.json")
        prov = load(GRID + f"variants/na{na}/provenance.json")
        require(prov["na"] == na and prov["fine_na"] == 4*(na-1)+1, "Wrong fine-grid dimensions")
        require(prov["files_changed_vs_control"] == ["parameters.f90"], "Unexpected grid source changes")
        for filename, sha in prov["sources_sha256"].items():
            f = path(GRID + f"variants/na{na}/src/" + filename)
            require(hashlib.sha256(f.read_bytes()).hexdigest() == sha, f"Grid source hash: {filename}")
        values, differences = [], []
        for name in names:
            p = points[name]; policy(p)
            row = d["rows"][name]
            close(row["fine"], p["ce2_newborn"], "grid summary vs policy")
            close(row["difference"], row["fine"]-row["standard"], "grid difference")
            values.append(row["fine"]); differences.append(row["difference"])
        displayed(values, want, f"{na}-node table")
        c = d["checks"]
        close(max(map(abs,differences)), c["max_abs_difference_pp"], "grid maximum change")
        close(values[0]-values[1], c["fine_grid_gaps_pp"]["owt_minus_okit"], "grid separate gap")
        close(values[3]-values[2], c["fine_grid_gaps_pp"]["estate_removal_gain"], "grid estate gain")
        require(c["all_within_0.15pp"] == all(abs(x)<.15 for x in differences), "Wrong threshold flag")
        require(values[0]>values[1] and min(values[2:])>max(values[:2]) and values[3]>values[2],
                "Four-policy ranking changed")
        result[str(na)] = {"newborn_CE2": values, "max_change_pp": max(map(abs,differences)),
                           "all_within_0.15pp": c["all_within_0.15pp"],
                           "gaps_pp": c["fine_grid_gaps_pp"]}
    ext = load(GRID + "results_extended.json")
    expected_extended = {201: [28.61,30.91,30.85], 301: [28.08,30.33,30.25],
                         401: [27.91,30.15,30.07]}
    rates = {"w8_s80": (.08,-.8,0), "w9_s95": (.09,-.95,0), "w10_s95": (.1,-.95,0)}
    extended = {}
    for na, want in expected_extended.items():
        key = str(na)
        points = load(GRID + f"runs/na{na}/points_extended.json")
        prov = load(GRID + f"variants/na{na}_guard/provenance.json")
        require(prov["na"] == na and prov["fine_na"] == 4*(na-1)+1,
                "Wrong extended-grid dimensions")
        require(prov["files_changed_vs_grid_build"] == ["GKK_Main.f90"],
                "Unexpected extended-grid source changes")
        patch = prov["patch"]
        require(patch == {"file":"GKK_Main.f90", "old":"(tauK.lt.-0.50_dp).or.(tauK.gt.0.50_dp)",
                          "new":"(tauK.lt.-0.95_dp).or.(tauK.gt.0.50_dp)", "count":1},
                "Unexpected subsidy-limit patch")
        for filename, sha in prov["sources_sha256"].items():
            original = path(GRID + f"variants/na{na}/src/" + filename).read_bytes()
            guarded = path(GRID + f"variants/na{na}_guard/src/" + filename).read_bytes()
            require(hashlib.sha256(guarded).hexdigest() == sha, "Guard source hash: " + filename)
            if filename == patch["file"]:
                require(original.count(patch["old"].encode()) == 1, "Guard patch is not unique")
                original = original.replace(patch["old"].encode(), patch["new"].encode())
            require(original == guarded, "Extended build changes more than its input limit: " + filename)
        values = []
        for name, tax_rates in rates.items():
            record = points[name]
            policy(record)
            same_numbers(record, ext["points"][key][name], "extended raw record " + name)
            for rate, value in zip(("tau_w","tau_k","tau_bq"), tax_rates):
                close(record[rate], value, "extended tax " + rate)
            close(record["ce2_newborn"], ext["newborn_ce2"][name][key], "extended CE2")
            values.append(record["ce2_newborn"])
        displayed(values, want, f"{na}-node extended rows")
        gap = values[1] - values[2]
        close(gap, ext["checks"]["w9_minus_w10_pp"][key], "9% minus 10%")
        require(abs(gap) < .15 and ext["checks"]["w9_w10_tied"][key], "95% slice tie changed")
        base_joint = ext["newborn_ce2"]["joint_bq0"][key]
        if na == 201:
            close(base_joint, load(SENS + "flat/results.json")["columns"]["centre"]["ce2"]["joint_bq0"],
                  "extended fresh-control 50% anchor")
        else:
            close(base_joint, load(GRID + f"runs/na{na}/points.json")["joint_bq0"]["ce2_newborn"],
                  "extended common 50% anchor")
        require(min(values[1:]) > values[0] > base_joint and
                ext["checks"]["welfare_rises_with_subsidy"][key], "Extended welfare ordering changed")
        extended[key] = {"newborn_CE2":values, "9_minus_10_pp":gap}
    moves = []
    for name in rates:
        row = ext["newborn_ce2"][name]
        change = row["401"] - row["201"]
        close(change, ext["checks"]["move_201_to_401_pp"][name], "extended grid change")
        require(row["201"] > row["301"] > row["401"], "Extended CE2 not decreasing with refinement")
        moves.append(-change)
    displayed(moves, [.70,.76,.78], "extended grid decreases")
    result["extended"] = extended
    result["extended_max_change_pp"] = max(moves)
    result["scope"] = "Seven policies, including nine extended-grid solves, reconciled to saved reports. No fresh solves or error-bound certification."
    return result


def check_policy_grids():
    fine = load("calibration/runs/okit_fine_grid_2022/grid_results.json")["points"]
    fine = sorted((p["result"] for p in fine), key=lambda p: p["tau_k"], reverse=True)
    require(len(fine)==10, "Need ten capital-tax fine-grid points")
    for p in fine: policy(p)
    displayed([p["ce2_newborn"] for p in fine],
              [5.045,5.056,5.062,5.062,5.059,5.051,5.039,5.028,5.014,4.996], "fine capital-tax table", 3)
    all_points = []
    for name in ["experiments/policy_reoptimization_2022/runs/grid_points.json",
                 "experiments/policy_reoptimization_2022/runs/edge_points.json",
                 ROB+"runs/partB_all.json", ROB+"runs/partD_all.json"]:
        d = load(name)
        all_points.extend(d.values() if isinstance(d,dict) else d)
    wanted = {(.07,-.5):23.54,(.07,-.6):25.37,(.07,-.7):26.96,(.07,-.8):28.30,
              (.08,-.5):23.18,(.08,-.6):25.28,(.08,-.7):27.12,(.08,-.8):28.71,(.08,-.9):30.09,(.08,-.95):30.70,
              (.09,-.5):22.50,(.09,-.8):28.71,(.09,-.9):30.29,(.09,-.95):31.01,
              (.1,-.5):21.53,(.1,-.8):28.36,(.1,-.9):30.13,(.1,-.95):30.95}
    for (tw,tk), want in wanted.items():
        matches = [p for p in all_points if p.get("status")=="ok" and p.get("calibration","thesis")=="thesis"
                   and abs(p["tau_w"]-tw)<1e-10 and abs(p["tau_k"]-tk)<1e-10 and p["tau_bq"]==0]
        require(matches, f"Missing extended-grid point {tw}/{tk}")
        p = matches[-1]; policy(p); displayed([p["ce2_newborn"]],[want],f"extended {tw}/{tk}")
    rec = load(SENS+"recal_results.json")["arms"]["control"]["policies"]["okit"]
    policy(rec); displayed([rec["ce2_newborn"]],[4.269],"recalibrated reported subsidy",3)
    search = load("experiments/policy_reoptimization_2022/results.json")["grid_points"]
    for rate,want in [(-.22,4.058),(-.18,4.188),(-.10,4.265),(-.06,4.181)]:
        matches=[p for p in search if p.get("calibration")=="recal" and abs(p["tau_w"])<1e-12
                 and abs(p["tau_k"]-rate)<1e-10 and abs(p["tau_bq"]-.4)<1e-10]
        require(matches, f"Missing recalibrated sweep {rate}")
        policy(matches[0]); displayed([matches[0]["ce2_newborn"]],[want],f"recalibrated {rate}",3)
    return {"fine_capital_grid_points":10,"extended_joint_table_points":len(wanted),"recalibrated_sweep_points":5}


def check_marginal_returns():
    saved = load("experiments/marginal_returns_2022/results.json")
    expected = {"benchmark":[2.58,1.94,12.31], "separate_wealth":[3.84,.77,12.79],
                "separate_subsidy":[1.96,2.23,13.49], "joint_estate_40":[4.30,-.55,12.13],
                "joint_estate_zero":[3.79,-1.32,11.66], "joint_subsidy_80":[3.51,-1.69,11.49],
                "joint_subsidy_95":[3.58,-2.02,11.24]}
    constrained_min = {"benchmark":[100.,100.], "separate_wealth":[99.9,99.7],
                       "separate_subsidy":[99.9,99.8], "joint_estate_40":[99.6,92.5],
                       "joint_estate_zero":[99.7,94.5], "joint_subsidy_80":[99.5,90.7],
                       "joint_subsidy_95":[99.3,88.3]}

    def read_run(folder, rates, experiment):
        suffix = "/Joint_Tax" if experiment else ""
        root = folder + suffix
        out = report(root + ("/output_exp.txt" if experiment else "/output.txt"))
        mg = path(root + ("/Mg_Return_W_Pct_Exp.txt" if experiment else "/Mg_Return_W_Pct_Bench.txt"))
        lines = [line.split()[1:] for line in mg.read_text().splitlines() if line.split()[:1] == ["Before_Tax"]]
        require(len(lines) == 1 and len(lines[0]) >= 5, "Expected five before-tax percentiles")
        # The Fortran report appends two unused zero slots after its five labelled percentiles.
        require(all(float(x) == 0 for x in lines[0][5:]), "Unexpected extra marginal-return fields")
        before = dict(zip(("p10","p50","p90","p95","p99"), map(float, lines[0][:5])))
        tw, tk, _ = rates
        after = {k:(1-tk)*v-100*tw for k,v in before.items()}
        close(after["p10"], scalar(out,"R_AT"), "lowest after-tax marginal return", 1e-7)
        close(before["p10"], scalar(out,"R"), "lowest before-tax marginal return", 1e-7)
        con = path(root + ("/Constrained_firms_stats_exp.txt" if experiment else "/Constrained_firms_stats.txt"))
        by_z = {}; total = None
        for line in con.read_text().splitlines():
            fields = line.split()
            if len(fields) >= 4 and fields[0].isdigit():
                by_z[fields[0]] = dict(zip(("all_states","fast_lane","normal"), map(float,fields[1:4])))
            elif fields[:1] == ["Total"]:
                total = float(fields[1])
        require(set(by_z) == set(map(str,range(1,10))) and total is not None, "Missing constraint shares")
        ast = path(root + ("/Asset_Stats_exp.txt" if experiment else "/Asset_Stats_bench.txt"))
        mean = {"pre_tax":{}, "after_tax":{}}
        for line in ast.read_text().splitlines():
            m = re.match(r"\s*Mean_Return_z\s+(\d+)(_AT)?\s+(\S+)", line)
            if m:
                mean["after_tax" if m[2] else "pre_tax"][m[1]] = 100*float(m[3])
        require(all(set(v) == set(map(str,range(1,10))) for v in mean.values()), "Missing mean returns")
        return {"rates":rates, "r":scalar(out,"R"), "r_after_tax":scalar(out,"R_AT"),
                "marginal_return_wealth_weighted":{"before_tax":before,"after_tax":after},
                "constrained_share_pct":{"by_ability":by_z,"total":total},
                "mean_return_by_ability_pct":mean}

    for name, item in saved.items():
        if name == "benchmark":
            continue
        require(len(item["sources"]) == 4, "Missing marginal-return source list")
        for source in item["sources"]: path(source)
        folder = str(Path(item["sources"][0]).parent.parent)
        record = load(folder + "/result.json")
        policy(record)
        same_numbers([record[k] for k in ("tau_w","tau_k","tau_bq")], item["rates"], "marginal tax rates")
        actual = read_run(folder, item["rates"], True)
        same_numbers(actual, {k:v for k,v in item.items() if k != "sources"}, "marginal reports " + name)
        benchmark = read_run(folder, [0.,.25,.4], False)
        same_numbers(benchmark, {k:v for k,v in saved["benchmark"].items() if k != "sources"},
                     "shared marginal benchmark " + name)
    for name, want in expected.items():
        row = saved[name]; after = row["marginal_return_wealth_weighted"]["after_tax"]
        displayed([row["r"],after["p50"],after["p90"]], want, "marginal table " + name)
        minima = [min(row["constrained_share_pct"]["by_ability"][str(z)][s] for z in range(5,10))
                  for s in ("fast_lane","normal")]
        displayed(minima, constrained_min[name], "constraint table " + name, 1)
    require(len(saved) == 8, "Expected benchmark and seven marginal-return policies")
    return {"table_rows_checked":len(expected), "saved_policy_runs_checked":len(saved)-1,
            "detailed_reports_checked":6*(len(saved)-1),
            "scope":"Rebuilds returns and constraints from saved detailed reports; after-tax marginal returns include both tax wedges."}


def check_parameter_direction():
    import numpy as np
    saved = load(SENS + "flat/results.json")
    names = ("sigma_z_eps","x_hi","p1_x","p2_x")
    moment_names = ("top1","ent_top1","ent_wealth")
    initial = np.array([.277,1.5,.05,.03])
    steps = np.array([.015,.1,.005,.003])
    solves = []
    for filename in sorted((REP / SENS / "recal/control/solves").glob("*/result.json")):
        rel = str(filename.relative_to(REP)); rec = load(rel)
        same_numbers(benchmark_moments(str(filename.parent.relative_to(REP))), rec["moments"], "Jacobian raw moments")
        solves.append(rec)

    def at(vector):
        hits = [r for r in solves if np.allclose([r["parameters"][k] for k in names],vector,rtol=0,atol=1e-12)
                and abs(r["parameters"]["theta_max"]-2.8) < 1e-12]
        require(len(hits) == 1, "Missing/ambiguous Jacobian finite-difference solve")
        return np.array([hits[0]["moments"][k] for k in moment_names])

    base = at(initial); cols = []
    for j in range(4):
        trial = initial.copy(); trial[j] += steps[j]
        cols.append((at(trial)-base)/steps[j])
    jacobian = np.column_stack(cols)*initial[np.newaxis,:]
    _, singular, vt = np.linalg.svd(jacobian)
    direction = vt[-1]/np.abs(vt[-1]).max()
    if direction[1] < 0: direction = -direction
    same_numbers(jacobian.tolist(), saved["direction"]["scaled_jacobian"], "recomputed Jacobian")
    same_numbers(singular.tolist(), saved["direction"]["singular_values"], "recomputed singular values")
    same_numbers(direction.tolist(), saved["direction"]["direction"], "recomputed null direction")
    require(np.max(np.abs(jacobian@direction)) < 1e-12, "Direction is not locally undetected")
    displayed(singular.tolist(), [1.11,.15,.01], "Jacobian singular values")
    close(saved["step"],.1,"parameter perturbation size")
    centre = saved["columns"]["centre"]
    params = load("calibration/runs/scf_2022/best.json")["parameters"]
    for key in names: close(centre["parameters"][key],params[key],"central parameter " + key)
    close(centre["parameters"]["theta_max"],load("calibration/runs/business_financing_2022/best.json")["theta_max"],"central credit parameter")
    same_numbers(benchmark_moments(SENS+"runs/control/benchmark"),centre["moments"],"central raw moments")
    fixed = load(SENS+"results.json")["table"]["control"]["policies"]
    expected = {"minus":[8.18,4.87,18.43,22.27,3.31,3.83],
                "centre":[8.39,4.95,19.77,23.44,3.44,3.67],
                "plus":[8.45,4.99,20.27,23.87,3.46,3.60]}
    rates = {name:tuple(fixed[name][k] for k in ("tau_w","tau_k","tau_bq"))
             for name in ("owt","okit","s5_1","s5_3","s5_4")}
    rates["joint_bq0"] = (.07,-.5,0.)
    max_moment_shift = 0.; max_welfare_shift = 0.
    for side, sign in (("minus",-1),("centre",0),("plus",1)):
        col = saved["columns"][side]
        if sign:
            for j,key in enumerate(names):
                close(col["parameters"][key],centre["parameters"][key]*(1+sign*.1*direction[j]), "perturbed " + key)
            fin = load(SENS+f"flat/{side}/financing.json")
            same_numbers(col["parameters"],fin["parameters"],"financing parameters")
            same_numbers(col["moments"],benchmark_moments(fin["benchmark"]),"perturbed raw moments")
            close(fin["target"],1.5628872107,"financing target")
            close(fin["gap"],col["moments"]["debt_output"]-fin["target"],"financing gap")
            require(abs(fin["gap"]) <= .001, "Perturbed financing target not met")
            roots = [SENS+f"flat/{side}/policies"]
        else:
            roots = [SENS+"runs/control/policies", ROB+"runs/baseline"]
        records = [load(str(f.relative_to(REP))) for root in roots
                   for f in sorted((REP/root).glob("v2_*/*/result.json"))]
        for name,tax_rates in rates.items():
            hits = [r for r in records if r.get("status") == "ok" and
                    all(abs(r[k]-v)<1e-12 for k,v in zip(("tau_w","tau_k","tau_bq"),tax_rates)) and
                    abs(r["ce2_newborn"]-col["ce2"][name])<1e-9]
            require(hits, "Missing parameter-direction policy " + side + ":" + name)
            policy(hits[0])
            close(hits[0]["ce2_newborn"],col["ce2"][name],"parameter-direction raw CE2")
        ce = col["ce2"]; checks = saved["checks"][side]
        lead, estate = ce["owt"]-ce["okit"], ce["joint_bq0"]-ce["s5_4"]
        close(lead,checks["wealth_tax_lead_pp"],"direction wealth lead")
        close(estate,checks["estate_removal_gain_pp"],"direction estate gain")
        require(lead > 0 and estate > 0 and min(ce[n] for n in rates if n not in ("owt","okit")) > max(ce["owt"],ce["okit"]),
                "Parameter-direction ranking claim failed")
        require(all(checks[k] is True for k in ("wealth_tax_beats_subsidy","joint_beats_separate","estate_removal_raises_welfare")),
                "Incorrect direction ranking flags")
        require(checks["joint_order"] == sorted(("s5_1","s5_3","s5_4"),key=lambda n:-ce[n]), "Wrong joint ordering")
        displayed([ce[n] for n in ("owt","okit","s5_4","joint_bq0")]+[lead,estate],expected[side],"direction table " + side)
        max_moment_shift = max(max_moment_shift,*(100*abs(col["moments"][k]-centre["moments"][k]) for k in moment_names))
        max_welfare_shift = max(max_welfare_shift,*(abs(ce[k]-centre["ce2"][k]) for k in rates if k not in ("owt","okit")))
    require(max_moment_shift < .61 and max_welfare_shift < 1.35, "Direction sensitivity exceeds reported bounds")
    minus = saved["columns"]["minus"]["ce2"]
    displayed([minus["s5_1"]-minus["s5_4"]],[.25],"negative-side joint reordering")
    require(minus["s5_1"]-minus["s5_4"] > .15,"Negative-side reordering is only a tie")
    return {"singular_values":singular.tolist(), "policy_evaluations_checked":18,
            "max_target_moment_shift_pp":max_moment_shift,"max_joint_welfare_shift_pp":max_welfare_shift,
            "scope":"Rebuilds the local Jacobian and checks both perturbations against saved benchmark/policy reports; no new solves or claim about the untested weak direction."}


def check_robustness():
    rows = load("experiments/table15_estate_2022/results.json")["rows"]
    out = {}
    for key, want in [("theta_2800",[3.28,19.93,23.58,3.66]),("theta_2952",[3.44,19.86,23.54,3.67]),
                      ("recal_alt",[3.04,17.05,20.83,3.78])]:
        r=rows[key]
        close(r["separate_gap"],r["owt_ce2"]-r["okit_ce2"],key+" gap")
        close(r["estate_removal_gain"],r["ce2_bq0"]-r["ce2_bq40"],key+" estate")
        values=[r["separate_gap"],r["ce2_bq40"],r["ce2_bq0"],r["estate_removal_gain"]]
        displayed(values,want,key);out[key]=values
    rec=load(SENS+"recal_results.json")["arms"]["control"]["policies"]
    grid=load("experiments/policy_reoptimization_2022/runs/grid_points.json")
    pair={round(p["tau_bq"],1):p for p in grid if p.get("calibration")=="recal" and abs(p["tau_w"]-.07)<1e-12 and abs(p["tau_k"]+.5)<1e-12}
    values=[rec["owt"]["ce2_newborn"]-rec["okit"]["ce2_newborn"],pair[.4]["ce2_newborn"],pair[0]["ce2_newborn"],pair[0]["ce2_newborn"]-pair[.4]["ce2_newborn"]]
    displayed(values,[2.97,16.88,20.59,3.71],"recalibrated reference");out["recal_control"]=values
    for key,file,owt,okit,want in [
        ("constant", "c6_policies.json", "owt_0.030618", "okit_-0.2", [2.89,18.62,22.19,3.57]),
        ("markup", "c7_policies.json", "owt_0.025", "okit_-0.3", [1.37,18.43,21.25,2.82])]:
        d=load(ROB+"runs/"+file)
        ps=[d[k] for k in (owt,okit,"joint_7_50_40","joint_7_50_0")]
        for p in ps: policy(p)
        a,b,c,e=[p["ce2_newborn"] for p in ps];values=[a-b,c,e,e-c]
        displayed(values,want,key);out[key]=values
    d=load(ROB+"runs/looser_policies.json");partb=load(ROB+"runs/partB_all.json")
    ps=[d["owt_0.025"],partb["okit_0.05"],d["joint_7_50_40"],d["joint_7_50_0"]]
    for p in ps: policy(p)
    a,b,c,e=[p["ce2_newborn"] for p in ps];values=[a-b,c,e,e-c]
    displayed(values,[3.27,10.08,13.83,3.75],"loose credit");out["loose_credit"]=values
    return out


def check_other_claims():
    table = load(SENS + "results.json")["table"]
    control = table["control"]["policies"]
    effects = [p["ce2_newborn"]-control[name]["ce2_newborn"]
               for name,p in table["productivity"]["policies"].items()]
    displayed([min(effects),max(effects)],[.19,.21],"productivity implementation sensitivity")
    timing = [table["timing"]["policies"][name]["ce2_newborn"]-control[name]["ce2_newborn"]
              for name in ("owt","okit")]
    displayed(timing,[-.01,.01],"retirement timing sensitivity")
    side = load(ROB+"runs/side.json")
    base = report(BASE+"/output.txt")
    for name,want in [("ontop_2_wasted",-10.07),("ontop_owt_wasted",-14.37),
                      ("ontop_2_rebated",.12),("ontop_owt_rebated",-1.03)]:
        record = side[name]
        raw = report(record["result_directory"]+"/output_exp.txt")
        # Fixed-labour spending cases deliberately do not impose G=G0.
        close(scalar(raw,"CE2_NB(exp)"),record["ce2_newborn"],name)
        displayed([record["ce2_newborn"]],[want],name)
        if name.endswith("rebated"):
            policy(record)
            want_quantities = [14.79,-15.21,2.69] if name=="ontop_2_rebated" else [11.87,-22.63,4.20]
            displayed([100*record["tau_l"],100*(scalar(raw,"KBAR")/scalar(base,"KBAR")-1),
                       100*(scalar(raw,"TFP_Q")/scalar(base,"TFP_Q")-1)],want_quantities,name+" quantities")
    data = load(ROB+"misallocation_link.json")
    points = data["policies"]
    samples = {"all": points,
               "estate tax 40%": [p for p in points if abs(p["tau_bq"]-.4)<1e-8],
               "estate tax zero or near-zero": [p for p in points if p["tau_bq"]<.005],
               "separate taxes, estate tax 40%": [p for p in points if abs(p["tau_bq"]-.4)<1e-8 and
                                                  (abs(p["tau_w"])<1e-8 or abs(p["tau_k"])<1e-8)],
               "joint packages (wealth tax and subsidy)": [p for p in points if p["tau_w"]>0 and p["tau_k"]<0]}
    correlations = {}
    for name, rows in samples.items():
        xs=[p["ce2_newborn"] for p in rows]; ys=[-p["misalloc_change"] for p in rows]
        mx,my=sum(xs)/len(xs),sum(ys)/len(ys)
        corr=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/math.sqrt(
            sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
        require(len(rows)==data["summary"][name]["n"],"Correlation sample count differs: "+name)
        close(corr,data["summary"][name]["corr_ce2_misalloc_reduction"],"Correlation "+name)
        correlations[name]={"n":len(rows),"correlation":corr}
    require(len(points)==118,"Expected 118 misallocation observations")
    return {"productivity_effect_range_pp":[min(effects),max(effects)],"timing_effects_pp":timing,
            "on_top_cases":4,"correlations":correlations,
            "scope":"Recomputes saved-summary arithmetic; correlations are descriptive, not causal identification."}


def external_check(command):
    env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"}
    done=subprocess.run([sys.executable,*command],cwd=ROOT,env=env,text=True,capture_output=True)
    require(done.returncode==0, " ".join(command)+":\n"+done.stdout+done.stderr)
    return {"command":["python3",*command],"output":done.stdout.strip(),"model_executed":False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manuscript",type=Path,help="Optional local .tex: check table/figure label coverage only")
    ap.add_argument("--json-output",type=Path,help="Optional explicit destination for the check report")
    args=ap.parse_args()
    mapping=json.loads((ROOT/"THESIS_RESULT_MAP.json").read_text())
    checks={"calibration":check_calibration,"rn_and_separate":check_rn_and_separate,
            "estate_and_household":check_estate,"asset_grid":check_grid_accuracy,
            "policy_grids":check_policy_grids,"robustness":check_robustness,
            "marginal_returns":check_marginal_returns,"parameter_direction":check_parameter_direction,
            "other_claims":check_other_claims,
            "saved_joint_table":lambda:external_check(["scripts/check_saved_policy_tables.py"]),
            "figure_data":lambda:external_check(["scripts/thesis_figures/make_thesis_figures.py","--check-data"]),
            "estate_incidence":lambda:external_check(["scripts/thesis_figures/estate_incidence.py","--model-root","replication","--check-data"]),
            "estate_figure":lambda:external_check(["scripts/thesis_figures/estate_comparison.py","--check-data"])}
    results={};errors=[]
    try:
        labels=[x["label"] for x in mapping["results"]]
        require(len(labels)==len(set(labels)),"Duplicate result-map labels")
        require(sum(x.startswith("tab:") for x in labels)==20,"Expected 20 mapped thesis tables")
        require(sum(x.startswith("fig:") for x in labels)==5,"Expected five mapped thesis figures")
        for row in mapping["results"]:
            require(row["checks"] and set(row["checks"])<=checks.keys(),"Unknown check for "+row["label"])
            for name in row["inputs"]+row["code"]: path(name,ROOT)
        if args.manuscript:
            found=set(re.findall(r"\\label\{((?:tab|fig):[^}]+)\}",args.manuscript.read_text()))
            mapped=set(x for x in labels if x.startswith(("tab:","fig:")))
            require(found==mapped,f"Manuscript/result-map mismatch: unmapped={sorted(found-mapped)}, stale={sorted(mapped-found)}")
    except (ValueError,OSError,KeyError) as exc: errors.append("coverage: "+str(exc))
    for name,fn in checks.items():
        try: results[name]={"ok":True,"details":fn()}
        except (ValueError,OSError,KeyError,TypeError,IndexError) as exc:
            results[name]={"ok":False,"error":str(exc)};errors.append(name+": "+str(exc))
    output={"schema_version":1,"ok":not errors,
            "scope":"Saved-result arithmetic and coverage. No model solve, raw-data reconstruction, or fresh-clone numerical certification.",
            "mapped_tables":sum(x["label"].startswith("tab:") for x in mapping["results"]),
            "mapped_figures":sum(x["label"].startswith("fig:") for x in mapping["results"]),
            "checks":results,"errors":errors}
    encoded=json.dumps(output,indent=2,allow_nan=False)+"\n"
    if args.json_output:
        args.json_output.write_text(encoded)
    print(encoded)
    return 0 if output["ok"] else 1


if __name__=="__main__":
    sys.exit(main())
