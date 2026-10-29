"""Exercise the production Fortran cutoff-bin routine and cache schema guards."""
from pathlib import Path
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('gfortran'), 'gfortran unavailable')
class PercentileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        source = (ROOT/'GKK_Stats.f90').read_text()
        routine = re.search(r'FUNCTION PERCENTILE_BIN_WEIGHTS\(.*?END FUNCTION PERCENTILE_BIN_WEIGHTS',
                            source, re.S).group()
        (cls.folder/'percentiles.f90').write_text('module percentiles\n'
            'integer,parameter :: dp=kind(1d0)\ncontains\n'+routine+'\nend module\n')
        subprocess.run(['gfortran','-fcheck=all','-c','percentiles.f90'],
                       cwd=cls.folder,check=True,capture_output=True,text=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self, body, succeeds=True):
        (self.folder/'test.f90').write_text('program test\nuse percentiles\n'
            'use, intrinsic :: ieee_arithmetic\nimplicit none\n'
            'real(dp) :: m(3), w(3), v(3), a(3), b(3), c(3)\n'+body+'\nend program\n')
        subprocess.run(['gfortran','-fcheck=all','test.f90','percentiles.o','-o','test'],
                       cwd=self.folder,check=True,capture_output=True,text=True)
        result = subprocess.run([str(self.folder/'test')],capture_output=True,text=True)
        if succeeds:
            self.assertEqual(result.returncode,0,result.stderr)
        else:
            self.assertNotEqual(result.returncode,0)

    def test_top_one_percent_splits_cutoff_and_corrects_conditional_share(self):
        self.run_case('''
m=[.985_dp,.010_dp,.005_dp]
w=PERCENTILE_BIN_WEIGHTS(m,.99_dp,1._dp)
v=[0._dp,.004_dp,.005_dp] ! entrepreneur mass by wealth bin
if(maxval(abs(w-[0._dp,.5_dp,1._dp]))>1d-12) error stop 'cutoff'
if(abs(sum(w*m)-.01_dp)>1d-14) error stop 'tail mass'
if(abs(sum(w*v)/sum(w*m)-.7_dp)>1d-12) error stop 'entrepreneur share'
''')

    def test_complementary_bins_partition_every_state(self):
        self.run_case('''
m=[.94_dp,.055_dp,.005_dp]
a=PERCENTILE_BIN_WEIGHTS(m,0._dp,.9_dp)
b=PERCENTILE_BIN_WEIGHTS(m,.9_dp,.99_dp)
c=PERCENTILE_BIN_WEIGHTS(m,.99_dp,1._dp)
if(maxval(abs(a+b+c-1._dp))>1d-12) error stop 'partition'
if(abs(sum(a*m)-.9_dp)>1d-12.or.abs(sum(b*m)-.09_dp)>1d-12) error stop 'mass'
v=[1._dp,10._dp,100._dp]
if(abs(sum((a+b+c)*m*v)-sum(m*v))>1d-12) error stop 'wealth conservation'
''')

    def test_both_endpoints_in_same_bin_and_zero_mass_bins(self):
        self.run_case('''
m=[0._dp,2._dp,0._dp]
w=PERCENTILE_BIN_WEIGHTS(m,.4_dp,.6_dp)
if(maxval(abs(w-[0._dp,.2_dp,0._dp]))>1d-12) error stop 'same bin'
''')

    def test_extreme_tails_have_requested_mass_and_wealth(self):
        self.run_case('''
m=[.98_dp,.01_dp,.01_dp]
v=[1._dp,10._dp,100._dp]
w=PERCENTILE_BIN_WEIGHTS(m,.999_dp,1._dp)
if(abs(sum(w*m)-.001_dp)>1d-14) error stop 'top .1 mass'
if(abs(sum(w*m*v)-.1_dp)>1d-12) error stop 'top .1 wealth'
w=PERCENTILE_BIN_WEIGHTS(m,.9999_dp,1._dp)
if(abs(sum(w*m)-.0001_dp)>1d-14) error stop 'top .01 mass'
''')

    def test_scale_invariance_and_exact_cutoff(self):
        self.run_case('''
m=[.8_dp,.1_dp,.1_dp]
w=PERCENTILE_BIN_WEIGHTS(m,.9_dp,1._dp)
a=PERCENTILE_BIN_WEIGHTS(17._dp*m,.9_dp,1._dp)
if(maxval(abs(w-a))>1d-12) error stop 'scale'
if(maxval(abs(w-[0._dp,0._dp,1._dp]))>1d-12) error stop 'exact boundary'
w=PERCENTILE_BIN_WEIGHTS(m,.1_dp,.1_dp)
if(any(w/=0._dp)) error stop 'empty interval'
''')

    def test_tiny_positive_mass_inside_tail_is_not_lost(self):
        self.run_case('''
m=[.995_dp,.005_dp,1d-18]
w=PERCENTILE_BIN_WEIGHTS(m,.99_dp,1._dp)
if(w(3)/=1._dp) error stop 'tiny tail bin dropped'
w=PERCENTILE_BIN_WEIGHTS(m,1._dp,1._dp)
if(any(w/=0._dp)) error stop 'empty interval at one'
''')

    def test_invalid_distributions_and_bounds_fail(self):
        for body in [
            'm=0._dp\nw=PERCENTILE_BIN_WEIGHTS(m,0._dp,1._dp)',
            'm=[1._dp,-.1_dp,.1_dp]\nw=PERCENTILE_BIN_WEIGHTS(m,0._dp,1._dp)',
            'm=1._dp\nm(2)=ieee_value(0._dp,ieee_quiet_nan)\nw=PERCENTILE_BIN_WEIGHTS(m,0._dp,1._dp)',
            'm=1._dp\nw=PERCENTILE_BIN_WEIGHTS(m,.9_dp,.1_dp)',
        ]:
            with self.subTest(body=body):
                self.run_case(body,succeeds=False)


def load_script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CalibrationSchemaTests(unittest.TestCase):
    def test_scf_rejects_old_statistics(self):
        scf=load_script('recalibrate_scf')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'output.txt').write_text('Wealth_Top_1% .36\n')
            with self.assertRaisesRegex(ValueError,'old percentile'):
                scf.read_moments(folder)

    def test_scf_reads_new_statistics(self):
        scf=load_script('recalibrate_scf')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'output.txt').write_text('Statistics_Schema 3\nWealth_Top_1% .36\n')
            (folder/'Entrepreneur_10_50.txt').write_text(
                'Top_01_Entrepreneur_50 54.77\nEntreprenur_50_A_Share 32.23\n')
            result=scf.read_moments(folder)
            self.assertAlmostEqual(result[1],.5477)

    def test_financing_does_not_reuse_legacy_theta_28_shortcut(self):
        fin=load_script('recalibrate_financing_2022')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            bench=folder/'legacy';bench.mkdir()
            (bench/'output.txt').write_text('Debt_Output 1.5\n')
            summary=folder/'best.json'
            params=dict(sigma_z_eps=.277,x_hi=1.5,p1_x=.05,p2_x=.03)
            summary.write_text(json.dumps(dict(run_directory=str(bench),parameters=params)))
            with patch.object(fin,'SCF_BEST',summary),patch.object(fin,'RUN_ROOT',folder/'runs'), \
                 patch.object(fin,'ROOT',folder), \
                 patch.object(fin.subprocess,'run',side_effect=RuntimeError('fresh solve requested')):
                with self.assertRaisesRegex(RuntimeError,'fresh solve requested'):
                    fin.evaluate(2.8,params,1)


if __name__=='__main__':
    unittest.main()
