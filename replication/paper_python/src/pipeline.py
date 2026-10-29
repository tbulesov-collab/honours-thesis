from __future__ import annotations

from pathlib import Path

import pandas as pd

from .figures import write_available_figures, write_extra_figures
from .registry import build_paper_item_registry
from .tables import write_all_tables


def _missing_inputs(model_dir: Path) -> pd.DataFrame:
    checks = [
        ("benchmark_output", model_dir / "output.txt"),
        ("tax_reform_output", model_dir / "Tax_Reform" / "output_exp.txt"),
        ("group_welfare", model_dir / "Tax_Reform" / "draft_group_CE.txt"),
        ("pareto_panel_benchmark", model_dir / "Simul" / "panel_Pareto"),
        ("opt_tax_wide_grid_w", model_dir / "Opt_Tax_W" / "Wide_Grid" / "Stats_by_tau_w.txt"),
        ("opt_tax_wide_grid_k", model_dir / "Opt_Tax_K" / "Wide_Grid" / "Stats_by_tau_k.txt"),
    ]
    return pd.DataFrame(
        [{"input_name": name, "path": str(path), "exists": path.exists()} for name, path in checks]
    )


def run_pipeline(model_dir: Path, out_dir: Path) -> None:
    tables_dir = out_dir / "tables"
    pipeline_dir = out_dir / "_pipeline"

    tables_dir.mkdir(parents=True, exist_ok=True)
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    missing_df = _missing_inputs(model_dir)
    missing_df.to_csv(pipeline_dir / "missing_inputs_report.csv", index=False)

    tables_written = write_all_tables(model_dir=model_dir, out_dir=tables_dir)
    figures_written = write_available_figures(run_dir=out_dir)
    figures_written.extend(write_extra_figures(model_dir=model_dir, out_dir=out_dir))

    registry = build_paper_item_registry(model_dir=model_dir)
    registry.to_csv(pipeline_dir / "paper_items_status.csv", index=False)

    summary = pd.DataFrame(
        [{"kind": "table", "path": str(p)} for p in tables_written]
        + [{"kind": "figure", "path": str(p)} for p in figures_written]
    )
    summary.to_csv(pipeline_dir / "pipeline_outputs.csv", index=False)

    print(f"Model directory: {model_dir}")
    print(f"Tables written: {len(tables_written)}")
    print(f"Figures written: {len(figures_written)}")
    missing_count = int((~missing_df['exists']).sum())
    print(f"Missing inputs recorded: {missing_count}")
    ready_items = int(registry["all_inputs_available"].sum())
    print(f"Paper items with available inputs: {ready_items}/{len(registry)}")
