from __future__ import annotations

from pathlib import Path

import pandas as pd


def _exists_any(paths: list[Path]) -> bool:
    return any(p.exists() for p in paths)


def _missing_any(paths: list[Path]) -> list[str]:
    if _exists_any(paths):
        return []
    return [str(p) for p in paths]


def build_paper_item_registry(model_dir: Path) -> pd.DataFrame:
    # Full set from MATLAB section headers. "exists" checks only minimum key inputs.
    w_candidates = [
        model_dir / "Opt_Tax_W" / "Wide_Grid" / "Stats_by_tau_w.txt",
        model_dir / "Opt_Tax_W" / "Stats_by_tau_w.txt",
    ]
    k_candidates = [
        model_dir / "Opt_Tax_K" / "Wide_Grid" / "Stats_by_tau_k.txt",
        model_dir / "Opt_Tax_K" / "Stats_by_tau_k.txt",
        model_dir / "Opt_Tax_K" / "Stats_by_tau_k_2.txt",
    ]

    items = [
        ("Figure 1.A", [[model_dir / "Simul" / "panel_Pareto"]], "generated_if_available"),
        ("Figure 1.B", [[
            model_dir.parent / "Model_2.1_Match_Return_Lambda" / "Simul" / "panel_Pareto",
            Path("Revision") / "Model_2.1_Match_Return_Lambda" / "Simul" / "panel_Pareto",
        ]], "not_generated"),
        ("Figure 2", [w_candidates, k_candidates], "generated_if_available"),
        ("Figure 3", [w_candidates, k_candidates], "generated_if_available"),
        ("Figure C.1", [[
            model_dir.parent / "Model_2.1_mu80" / "Simul" / "panel_Pareto",
            Path("Revision") / "Model_2.1_mu80" / "Simul" / "panel_Pareto",
        ]], "not_generated"),
        ("Figure C.2", [model_dir / "Entrepreneur_by_age.txt", model_dir / "Tax_Reform" / "Entrepreneur_by_age.txt"], "generated_if_available"),
        ("Figure C.3.A", [Path("Figures_._Tables") / "Fagereng_Figure" / "Fagereng_IGM_data.csv"], "generated_if_available"),
        ("Figure C.4", [w_candidates, k_candidates], "generated_if_available"),
        ("Table I", [], "not_automatable_yet"),
        ("Table II", [model_dir / "output.txt"], "not_automatable_yet"),
        ("Table III", [model_dir / "output.txt"], "generated"),
        ("Table IV", [model_dir / "Tax_Reform" / "Simul" / "Asset_Return_Panel" / "Return_Stats_exp.txt"], "generated"),
        ("Table V", [model_dir / "output.txt", model_dir / "Tax_Reform" / "output_exp.txt"], "generated"),
        ("Table VI", [model_dir / "Tax_Reform" / "output_exp.txt"], "generated"),
        ("Table VII", [model_dir / "Tax_Reform" / "draft_group_CE.txt"], "generated"),
        ("Table VIII", [model_dir / "Opt_Tax_W" / "output.txt", model_dir / "Opt_Tax_K" / "output.txt"], "not_generated"),
        ("Table IX", [model_dir / "Opt_Tax_W" / "output.txt"], "not_generated"),
        ("Table X", [model_dir / "Tax_Reform" / "CE_Decomposition.txt"], "generated"),
        ("Table XI", [model_dir / "Transition_OTK_tL" / "CE_Transition.txt", model_dir / "Transition_OTW_tL" / "CE_Transition.txt"], "not_generated"),
        ("Table XII", [], "not_generated"),
        ("Table B.1", [], "not_automatable_yet"),
        ("Table B.2", [model_dir / "Simul" / "panela_bench"], "not_generated"),
        ("Table B.3", [model_dir / "Tax_Reform" / "draft_group_CE.txt", model_dir / "Tax_Reform" / "draft_group_fpos_welfare.txt"], "generated"),
        ("Table B.4", [model_dir / "Transition_OTW_tL" / "draft_group_CE.txt"], "not_generated"),
        ("Table E.5", [], "not_generated"),
        ("Table E.6", [], "not_generated"),
        ("Table E.7", [], "not_generated"),
        ("Table E.8", [], "not_generated"),
        ("Table E.9", [], "not_generated"),
        ("Table E.10", [], "not_generated"),
        ("Table E.11", [], "not_generated"),
    ]

    rows = []
    for name, deps, mode in items:
        normalized: list[list[Path]] = []
        for d in deps:
            if isinstance(d, list):
                normalized.append(d)
            else:
                normalized.append([d])
        missing: list[str] = []
        all_ok = True
        for dep_group in normalized:
            dep_missing = _missing_any(dep_group)
            if dep_missing:
                all_ok = False
                missing.extend(dep_missing)
        rows.append(
            {
                "item": name,
                "mode": mode,
                "all_inputs_available": all_ok,
                "missing_inputs": " | ".join(missing),
            }
        )
    return pd.DataFrame(rows)
