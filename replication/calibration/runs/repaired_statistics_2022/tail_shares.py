"""Repaired (fractional-bin) top wealth shares from a saved DBN, ported from
GKK_Stats.f90 PERCENTILE_BIN_WEIGHTS; tot_a_by_grid = agrid * pr_a (GKK_Stats.f90:197)."""
import sys, numpy as np
from pathlib import Path
DIMS = (81, 201, 9, 5, 5, 3)   # MaxAge, na, nz, nlambda, ne, nx  (parameters.f90)

def weights(mass, lower, upper):
    total = mass.sum(); lo, hi = lower*total, upper*total
    frac = np.zeros_like(mass); before = 0.0
    if lower == upper: return frac
    for i, m in enumerate(mass):
        after = before + m
        if m > 0:
            if before >= lo and (after <= hi or upper == 1.0): frac[i] = 1.0
            else: frac[i] = max(0.0, min(m, min(after, hi) - max(before, lo))) / m
        before = after
    return frac

def shares(dbn_path, agrid_path):
    agrid = np.array(Path(agrid_path).read_text().split(), dtype=float)
    dbn = np.fromfile(dbn_path, sep=' ')
    assert dbn.size == np.prod(DIMS), (dbn.size, DIMS)
    assert agrid.size == DIMS[1], agrid.size
    pr_a = dbn.reshape(DIMS, order='F').sum(axis=(0, 2, 3, 4, 5))
    tot = agrid * pr_a
    return {k: float((weights(pr_a, lo, 1.0) * tot).sum() / tot.sum())
            for k, lo in [('top1', .99), ('top01', .999), ('top001', .9999)]}

if __name__ == '__main__':
    print(shares(sys.argv[1], sys.argv[2]))
