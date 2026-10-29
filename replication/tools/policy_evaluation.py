"""Validated, versioned policy evaluations shared by both optimisation drivers.

Historical run roots are never overwritten. Each model/input context receives a
new v2_<digest> directory with a frozen executable and an input manifest.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

SCHEMA = 2
RESULT_FIELDS = [
    'key', 'tau_w', 'tau_k', 'tau_bq', 'tau_l', 'psi', 'ce2_newborn',
    'ce2_population', 'ce1_newborn', 'output_growth', 'consumption_growth',
    'top1_wealth_share', 'revenue', 'revenue_gap', 'revenue_relative_gap',
    'feasible', 'equilibrium_residual', 'aggregate_residual',
    'elapsed_seconds', 'result_directory', 'context_id',
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def atomic_json(path: Path, value) -> None:
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_kv(path: Path) -> dict[str, float]:
    values = {}
    for line in path.read_text(errors='replace').splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            numbers = [float(x.replace('D', 'E').replace('d', 'e')) for x in fields[1:]]
        except ValueError:
            continue
        values[fields[0]] = numbers[-1]
    return values


def signature(path: Path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


class PolicyEvaluator:
    def __init__(self, *, root: Path, executable: Path, benchmark: Path, run_root: Path,
                 threads: int, bounds, labor_bounds, budget_tolerance: float,
                 fixed_labor: bool = False, calibration_env=None):
        self.root = root.resolve()
        self.benchmark = benchmark.resolve()
        self.threads = threads
        self.bounds = bounds
        self.labor_bounds = labor_bounds
        self.budget_tolerance = float(budget_tolerance)
        self.fixed_labor = fixed_labor
        if not math.isfinite(self.budget_tolerance) or self.budget_tolerance <= 0:
            raise ValueError('budget tolerance must be finite and positive')
        if threads < 1 or not all(math.isfinite(x) for pair in (*bounds, labor_bounds) for x in pair):
            raise ValueError('invalid threads or non-finite bounds')
        if any(lo >= hi for lo, hi in (*bounds, labor_bounds)):
            raise ValueError('bounds must have positive width')
        self.benchmark_values = read_kv(self.benchmark / 'output.txt')
        for name in ['GBAR', 'YBAR', 'CBAR']:
            if not math.isfinite(self.benchmark_values[name]) or self.benchmark_values[name] <= 0:
                raise ValueError(f'invalid benchmark {name}')
        self.target_revenue = self.benchmark_values['GBAR']
        self.benchmark_output = self.benchmark_values['YBAR']
        self.benchmark_consumption = self.benchmark_values['CBAR']
        self.results = []
        self.eval_count = 0
        calibration_files = []
        if calibration_env is None:
            calibration_files = [self.root / 'calibration/runs/scf_2022/best.json',
                                 self.root / 'calibration/runs/business_financing_2022/best.json']
            scf, financing = [json.loads(p.read_text()) for p in calibration_files]
            p = scf['parameters']
            calibration_env = {
                'GKK_RHO_Z': '0.1',
                'GKK_SIGMA_Z_EPS': format(p['sigma_z_eps'], '.17g'),
                'GKK_X_HI': format(p['x_hi'], '.17g'),
                'GKK_P1_X': format(p['p1_x'], '.17g'),
                'GKK_P2_X': format(p['p2_x'], '.17g'),
                'GKK_THETA_MAX': format(financing['theta_max'], '.17g'),
            }
        self.calibration_env = dict(calibration_env)
        # Freeze the effective numerical environment. Candidate-control variables
        # inherited from the shell must never override the requested experiment.
        self.model_env = {k: v for k, v in os.environ.items()
                          if (k.startswith('GKK_') or k.startswith('OMP_'))
                          and not k.startswith('GKK_JOINT_')
                          and k not in {'GKK_RESULT_FOLDER', 'GKK_EVALUATOR_CHECK'}}
        self.model_env.update(self.calibration_env)
        self.model_env.update({
            'OMP_NUM_THREADS': str(threads), 'OMP_DYNAMIC': 'FALSE', 'OMP_NESTED': 'FALSE',
            'GKK_JOINT_BUDGET_TOL': format(self.budget_tolerance, '.17g'),
            'GKK_JOINT_FULL_OUTPUT': '0',
            'GKK_JOINT_FIXED_LABOR': '1' if fixed_labor else '0',
        })
        self.model_env.setdefault('GKK_DBN_TOL', '1e-7')
        self.model_env.setdefault('GKK_AGG_TOL', '1e-6')
        self.model_env.setdefault('GKK_DBN_MAX_ITER', '700')
        self.model_env.setdefault('GKK_BUDGET_MAX_ITER', '100')
        for key in ['GKK_DBN_TOL', 'GKK_AGG_TOL']:
            if not math.isfinite(float(self.model_env[key])) or float(self.model_env[key]) <= 0:
                raise ValueError(f'invalid {key}')
        for key in ['GKK_DBN_MAX_ITER', 'GKK_BUDGET_MAX_ITER']:
            if int(self.model_env[key]) < 1:
                raise ValueError(f'invalid {key}')

        executable = executable.resolve()
        source_files = sorted(set(self.root.glob('*.f90')) | set(self.root.glob('*.F90')))
        source_files += [p for p in [self.root / 'tools/policy_evaluation.py',
                         self.root / 'tools/optimize_joint_taxes.py',
                         self.root / 'experiments/joint_tax_fixed_labor/optimize_joint_taxes_fixed_labor.py',
                         self.root / 'experiments/joint_tax_fixed_labor/GKK_Main_fixed_labor.f90'] if p.exists()]
        bench_files = [self.benchmark / 'output.txt'] + sorted(
            p for p in (self.benchmark / 'Bench_Files').rglob('*') if p.is_file())
        if len(bench_files) < 2:
            raise ValueError('benchmark state files are missing')
        inputs = sorted(set([executable, *source_files, *bench_files, *calibration_files]))
        self.input_signatures = {p: signature(p) for p in inputs}
        files = {str(p): digest(p) for p in inputs}
        self.manifest = {
            'schema': SCHEMA, 'files': files, 'environment': self.model_env,
            'budget_tolerance': self.budget_tolerance, 'bounds': bounds,
            'labor_bounds': labor_bounds, 'fixed_labor': fixed_labor,
            'benchmark': str(self.benchmark),
        }
        self.context_id = identity(self.manifest)
        self.run_root = run_root.resolve() / ('v2_' + self.context_id[:12])
        relative = self.run_root.relative_to(self.root)
        if any(c.isspace() for c in str(relative)) or not all(c.isalnum() or c in '/_.-' for c in str(relative)):
            raise ValueError('Fortran result paths must use letters, digits, /, _, . or -')
        # The main's environment buffer is 256 characters. Leave space for an
        # attempt name and output subfolder rather than allowing silent truncation.
        if len(str(relative)) + 70 >= 256:
            raise ValueError('result path is too long for the Fortran environment buffer')
        self.run_root.mkdir(parents=True, exist_ok=True)
        manifest_file = self.run_root / 'manifest.json'
        if manifest_file.exists():
            if identity(json.loads(manifest_file.read_text())) != self.context_id:
                raise RuntimeError('run-context fingerprint collision or modified manifest')
        else:
            atomic_json(manifest_file, self.manifest)
        self.executable = self.run_root / 'evaluator.a'
        if not self.executable.exists():
            temp = self.run_root / ('evaluator.' + uuid.uuid4().hex + '.tmp')
            shutil.copy2(executable, temp)
            os.replace(temp, self.executable)
        if digest(self.executable) != files[str(executable)]:
            raise RuntimeError('frozen evaluator executable has changed')
        self.input_signatures[self.executable] = signature(self.executable)
        self._check_inputs()
        preflight = subprocess.run([str(self.executable)], cwd=self.root,
            env=self.environment({'GKK_EVALUATOR_CHECK': '1'}), capture_output=True, text=True, timeout=15)
        if preflight.returncode or 'GKK_POLICY_EVALUATOR_V2' not in preflight.stdout:
            raise RuntimeError('Executable lacks the repaired evaluator interface; rebuild before running')
        if fixed_labor and 'FIXED_LABOR_CAPABLE' not in preflight.stdout:
            raise RuntimeError('Fixed-labour evaluation requires the fixed-labour executable')

    def environment(self, extra=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('GKK_', 'OMP_'))}
        env.update(self.model_env)
        env.update(extra or {})
        return env

    def _check_inputs(self):
        if any(not p.exists() or signature(p) != value for p, value in self.input_signatures.items()):
            raise RuntimeError('Model or benchmark inputs changed during this search; start a new evaluator')
        current = [self.benchmark / 'output.txt'] + sorted(
            p for p in (self.benchmark / 'Bench_Files').rglob('*') if p.is_file())
        if any(p not in self.input_signatures for p in current):
            raise RuntimeError('Benchmark files changed during this search')

    def candidate_key(self, rates):
        if len(rates) != 3 or not all(math.isfinite(float(x)) for x in rates):
            raise ValueError('exactly three finite tax rates are required')
        return identity({'context': self.context_id, 'rates': [float(x).hex() for x in rates]})[:16]

    def is_feasible(self, row):
        try:
            numbers = [float(row[k]) for k in ['tau_w', 'tau_k', 'tau_bq', 'tau_l',
                       'ce2_newborn', 'ce2_population', 'revenue']]
            if not all(math.isfinite(x) for x in numbers):
                return False
            rates = numbers[:3]
            gap = abs(numbers[-1] - self.target_revenue) / abs(self.target_revenue)
            return (row.get('status') == 'ok' and row.get('context_id') == self.context_id
                    and row.get('equilibrium_converged') is True
                    and all(lo <= rate <= hi for rate, (lo, hi) in zip(rates, self.bounds))
                    and self.labor_bounds[0] <= numbers[3] <= self.labor_bounds[1]
                    and gap <= self.budget_tolerance)
        except (KeyError, TypeError, ValueError):
            return False

    def _result(self, folder, rates, elapsed):
        values = read_kv(folder / 'output_exp.txt')
        required = ['Evaluation_Schema', 'Equilibrium_Converged', 'Equilibrium_Residual',
                    'Aggregate_Residual', 'Equilibrium_Iterations', 'Budget_Tolerance',
                    'Revenue_Relative_Gap', 'Wealth_Tax_Above', 'Tau_K', 'Tau_BQ',
                    'GBAR', 'Psi', 'YBAR', 'CBAR', 'Wealth_Top_1%',
                    'CE2_NB(exp)', 'CE2_Pop(exp)', 'CE1_NB(exp)']
        if any(k not in values or not math.isfinite(values[k]) for k in required):
            raise ValueError('missing or non-finite evaluator output')
        if values['Evaluation_Schema'] != SCHEMA or values['Equilibrium_Converged'] != 1:
            raise ValueError('output does not certify a repaired, converged evaluation')
        if not 0 <= values['Equilibrium_Residual'] < float(self.model_env['GKK_DBN_TOL']):
            raise ValueError('distribution convergence tolerance not met')
        if not 0 <= values['Aggregate_Residual'] < float(self.model_env['GKK_AGG_TOL']):
            raise ValueError('aggregate convergence tolerance not met')
        if not 1 <= values['Equilibrium_Iterations'] <= int(self.model_env['GKK_DBN_MAX_ITER']):
            raise ValueError('invalid equilibrium iteration count')
        if values['Budget_Tolerance'] != self.budget_tolerance:
            raise ValueError('executable used a different budget tolerance')
        for key, rate in zip(['Wealth_Tax_Above', 'Tau_K', 'Tau_BQ'], rates):
            if not math.isclose(values[key], rate, rel_tol=0, abs_tol=1e-14):
                raise ValueError('executable evaluated different tax rates')
        if self.fixed_labor and not math.isclose(1-values['Psi'], self.benchmark_values['Average_Labor_Tax'],
                                                rel_tol=0, abs_tol=1e-10):
            raise ValueError('fixed-labour evaluation changed the labour tax')
        gap = abs(values['GBAR'] - self.target_revenue) / abs(self.target_revenue)
        if not math.isclose(gap, values['Revenue_Relative_Gap'], abs_tol=1e-12, rel_tol=1e-8):
            raise ValueError('executable used a different benchmark revenue')
        if not self.fixed_labor and gap > self.budget_tolerance:
            raise ValueError('final equilibrium violates the revenue tolerance')
        result = {
            'status': 'ok', 'schema': SCHEMA, 'context_id': self.context_id,
            'key': self.candidate_key(rates), 'tau_w': rates[0], 'tau_k': rates[1], 'tau_bq': rates[2],
            'tau_l': 1-values['Psi'], 'psi': values['Psi'], 'ce2_newborn': values['CE2_NB(exp)'],
            'ce2_population': values['CE2_Pop(exp)'], 'ce1_newborn': values['CE1_NB(exp)'],
            'output_growth': 100*(values['YBAR']/self.benchmark_output-1),
            'consumption_growth': 100*(values['CBAR']/self.benchmark_consumption-1),
            'top1_wealth_share': values['Wealth_Top_1%'], 'revenue': values['GBAR'],
            'revenue_gap': values['GBAR']-self.target_revenue, 'revenue_relative_gap': gap,
            'equilibrium_converged': True, 'equilibrium_residual': values['Equilibrium_Residual'],
            'aggregate_residual': values['Aggregate_Residual'], 'elapsed_seconds': elapsed,
            'result_directory': str(folder.relative_to(self.root)),
        }
        result['feasible'] = self.is_feasible(result)
        return result

    def _cached(self, path, rates):
        try:
            old = json.loads(path.read_text())
            if old.get('context_id') != self.context_id or old.get('key') != self.candidate_key(rates):
                return None
            folder = self.root / old['result_directory']
            if folder.parent.resolve() != path.parent.resolve():
                return None
            if digest(folder / 'output_exp.txt') != old.get('output_sha256'):
                return None
            # Reparse the raw result instead of trusting edited summary values.
            result = self._result(folder, rates, old['elapsed_seconds'])
            result['output_sha256'] = old['output_sha256']
            return result
        except (OSError, KeyError, ValueError, TypeError):
            return None

    def write_index(self):
        self._check_inputs()
        records = []
        for path in sorted(self.run_root.glob('*/result.json')):
            try:
                row = json.loads(path.read_text())
                rates = tuple(float(row[k]) for k in ['tau_w', 'tau_k', 'tau_bq'])
                valid = self._cached(path, rates)
                if valid is not None:
                    records.append(valid)
            except (OSError, KeyError, TypeError, ValueError):
                continue
        temp = self.run_root / ('index.' + uuid.uuid4().hex + '.tmp')
        with temp.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS)
            writer.writeheader()
            for row in sorted(records, key=lambda x: x['ce2_newborn'], reverse=True):
                writer.writerow({k: row[k] for k in RESULT_FIELDS})
        os.replace(temp, self.run_root / 'all_results.csv')

    def evaluate_rates(self, rates, *, force=False):
        rates = tuple(float(x) for x in rates)
        key = self.candidate_key(rates)
        self._check_inputs()
        if not force:
            for path in sorted(self.run_root.glob(key + '_*/result.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True):
                cached = self._cached(path, rates)
                if cached is not None:
                    self.results.append(cached)
                    print(f'[cache] {key}: CE2_NB={cached["ce2_newborn"]:.6f}%', flush=True)
                    return cached
        # A fresh directory per attempt prevents stale output from an interrupted
        # or failed process from being mistaken for a successful new evaluation.
        run_dir = self.run_root / (key + '_' + uuid.uuid4().hex[:8])
        run_dir.mkdir()
        (run_dir / 'Bench_Files').symlink_to(self.benchmark / 'Bench_Files', target_is_directory=True)
        env = self.environment({
            'GKK_RESULT_FOLDER': str(run_dir.relative_to(self.root)),
            **{k: format(v, '.17g') for k, v in zip(
                ['GKK_JOINT_TAUW', 'GKK_JOINT_TAUK', 'GKK_JOINT_TAUBQ'], rates)},
        })
        atomic_json(run_dir / 'request.json', {'context_id': self.context_id, 'rates': rates, 'environment': env_subset(env)})
        self.eval_count += 1
        print(f'[eval {self.eval_count}] W={rates[0]:.6%} K={rates[1]:.6%} BQ={rates[2]:.6%}', flush=True)
        start = time.monotonic()
        try:
            with (run_dir / 'run.log').open('w') as log:
                process = subprocess.Popen([str(self.executable)], cwd=self.root, env=env,
                                           stdout=log, stderr=subprocess.STDOUT, text=True)
                try:
                    while True:
                        try:
                            process.wait(timeout=30)
                            break
                        except subprocess.TimeoutExpired:
                            print(f'  still solving ({(time.monotonic()-start)/60:.1f} minutes)', flush=True)
                except BaseException:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise
            if process.returncode:
                raise RuntimeError(f'evaluator exited with code {process.returncode}')
            self._check_inputs()
            folder = run_dir / ('Joint_Tax_Fixed_Labor' if self.fixed_labor else 'Joint_Tax')
            result = self._result(folder, rates, time.monotonic()-start)
            result['output_sha256'] = digest(folder / 'output_exp.txt')
            atomic_json(run_dir / 'result.json', result)
        except Exception as exc:
            atomic_json(run_dir / 'failure.json', {
                'status': 'failed', 'context_id': self.context_id, 'key': key,
                'rates': rates, 'reason': str(exc), 'log': str((run_dir/'run.log').relative_to(self.root)),
            })
            raise RuntimeError(f'candidate failed: {exc}; inspect {run_dir / "run.log"}') from exc
        self.results.append(result)
        self.write_index()
        return result


def env_subset(env):
    return {k: v for k, v in env.items() if k.startswith(('GKK_', 'OMP_'))}
