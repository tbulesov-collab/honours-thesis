"""Distinguish retained result summaries from reusable benchmark solver state.

The released compact runs deliberately omit the large Bench_Files arrays. A
done.json/result.json record alone cannot support a subsequent policy solve.
This checks presence, not numerical convergence or the identity of a build;
the caller remains responsible for those checks.
"""
from pathlib import Path


BENCHMARK_STATE_FILES = (
    "DBN", "value", "bq_value", "cons", "hours", "aprime", "Income_AT",
    "v_pr", "v_pr_nb", "GBAR", "YBAR", "R", "P", "wage", "QBAR", "NBAR",
    "EBAR", "psi", "tauK", "tauW_bt", "tauW_at", "tauPL", "SSC_Payments",
    "K_P", "K_C", "L_P", "L_C", "YBAR_P", "YBAR_C",
)


def complete_benchmark(folder: Path) -> bool:
    """Require output and the full state written by Write_Benchmark_Results."""
    paths = [folder / "output.txt", *[folder / "Bench_Files" / n
                                    for n in BENCHMARK_STATE_FILES]]
    return all(path.is_file() and path.stat().st_size > 0 for path in paths)
