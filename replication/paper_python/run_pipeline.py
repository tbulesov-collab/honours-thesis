from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from src.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paper figures and tables from model outputs.")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("Revision") / "Model_2.1_Local",
        help="Directory containing model output files.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("paper_python") / "outputs",
        help="Base output directory. Each run is saved in a timestamped subfolder.",
    )
    args = parser.parse_args()

    base_out = args.out_dir
    run_name = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = base_out / run_name

    run_pipeline(model_dir=args.model_dir, out_dir=run_dir)

    # Write a plain-text pointer to the most recent run.
    latest_file = base_out / "latest.txt"
    latest_file.write_text(run_name + "\n", encoding="utf-8")
    print(f"Run folder   : {run_dir}")
    print(f"Latest pointer: {latest_file} -> {run_name}")


if __name__ == "__main__":
    main()

