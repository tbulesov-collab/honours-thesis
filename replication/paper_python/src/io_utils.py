from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


_NUMERIC_LINE = re.compile(r"^\s*([^\n]+?)\s+([-+0-9.EDed]+)\s*$")


def parse_key_value_file(path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    if not path.exists():
        return out

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = _NUMERIC_LINE.match(raw)
        if not m:
            continue
        key = m.group(1).strip()
        val = m.group(2).replace("D", "E").replace("d", "e")
        try:
            out[key] = float(val)
        except ValueError:
            continue
    return out


def read_numeric_matrix(path: Path) -> np.ndarray:
    if not path.exists():
        return np.empty((0, 0))
    return np.loadtxt(path)


def save_table(df: pd.DataFrame, csv_path: Path, xlsx_path: Path | None = None) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    if xlsx_path is not None:
        try:
            df.to_excel(xlsx_path, index=False)
        except Exception:
            # Excel export is optional if openpyxl is unavailable.
            pass


def parse_named_numeric_rows(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["name"])

    records: list[dict[str, float | str]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        nums: list[float] = []
        ok = True
        for tok in parts[1:]:
            tok2 = tok.replace("D", "E").replace("d", "e")
            try:
                nums.append(float(tok2))
            except ValueError:
                ok = False
                break
        if not ok or not nums:
            continue
        row: dict[str, float | str] = {"name": name}
        for i, v in enumerate(nums, start=1):
            row[f"v{i}"] = v
        records.append(row)
    return pd.DataFrame(records)

