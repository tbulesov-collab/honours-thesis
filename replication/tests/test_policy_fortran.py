"""Compile the actual policy-control routines against cheap numerical stubs."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('gfortran'), 'gfortran unavailable')
class FortranPolicyTests(unittest.TestCase):
    def run_program(self, source):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'test.f90').write_text(source)
            subprocess.run(['gfortran','-ffree-line-length-none','test.f90','-o','test'],
                           cwd=path,check=True,capture_output=True,text=True)
            subprocess.run([str(path/'test')],cwd=path,check=True,capture_output=True,text=True)

    def test_brent_winner_is_reevaluated_to_restore_state(self):
        text = (ROOT/'Opt_Tax_Functions.f90').read_text()
        routine = re.search(r'SUBROUTINE Find_Opt_Tax\(.*?END SUBROUTINE Find_Opt_Tax',text,re.S).group()
        self.run_program('''module stub
integer, parameter :: dp=kind(1d0)
real(dp) :: psi, brent_tol=1d-8
contains
'''+routine+'''
real(dp) function EQ_WELFARE_GIVEN_TauK(x)
real(dp), intent(in) :: x
psi=10*x
EQ_WELFARE_GIVEN_TauK=x*x
end function
real(dp) function EQ_WELFARE_GIVEN_TauW(x)
real(dp), intent(in) :: x
psi=20*x
EQ_WELFARE_GIVEN_TauW=x*x
end function
real(dp) function brent(a,b,c,func,tol,xmin)
real(dp), intent(in) :: a,b,c,tol
real(dp), intent(out) :: xmin
interface
  real(dp) function func(x)
  import dp
  real(dp), intent(in) :: x
  end function
end interface
brent=func(.8_dp) ! last trial leaves the wrong state
xmin=.2_dp       ! best tax differs from last trial
end function
end module
program test
use stub
real(dp) :: tax
call Find_Opt_Tax(.true.,tax,0._dp,1._dp)
if(abs(tax-.2_dp)>1d-12.or.abs(psi-2._dp)>1d-12) error stop 'stale capital-tax state'
call Find_Opt_Tax(.false.,tax,0._dp,1._dp)
if(abs(tax-.2_dp)>1d-12.or.abs(psi-4._dp)>1d-12) error stop 'stale wealth-tax state'
end program
''')

    def test_state_reset_restores_benchmark_but_preserves_policy(self):
        text = (ROOT/'Opt_Tax_Functions.f90').read_text()
        routine = re.search(r'SUBROUTINE RESET_POLICY_STATE\(\).*?END SUBROUTINE RESET_POLICY_STATE',text,re.S).group()
        assignments = re.findall(r'^\s*(\w+)\s*=\s*(\w+)\s*$', routine, re.M)
        pairs=[(a.lower(),b.lower()) for a,b in assignments if b!='0']
        names=sorted({v for pair in pairs for v in pair})
        setup='\n'.join(f'{a}=9._dp\n{b}=2._dp' for a,b in pairs)
        checks='\n'.join(f"if({a}/={b}) error stop 'state reset failed'" for a,b in pairs)
        self.run_program('''module stub
integer, parameter :: dp=kind(1d0)
integer :: solving_bench
real(dp) :: tauK, tauW_at, tau_bq
real(dp) :: '''+', '.join(names)+'\ncontains\n'+routine+'''
end module
program test
use stub
'''+setup+'''
tauK=-.14_dp
tauW_at=.03_dp
tau_bq=.4_dp
call RESET_POLICY_STATE()
'''+checks+'''
if(tauK/=-.14_dp.or.tauW_at/=.03_dp.or.tau_bq/=.4_dp) error stop 'tax policy changed'
if(solving_bench/=0) error stop 'wrong benchmark flag'
end program
''')

    def test_final_revenue_recheck_repeats_budget_solve(self):
        text = (ROOT/'Opt_Tax_Functions.f90').read_text()
        configure = re.search(r'SUBROUTINE CONFIGURE_POLICY_BUDGET\(\).*?END SUBROUTINE CONFIGURE_POLICY_BUDGET',text,re.S).group()
        solve = re.search(r'SUBROUTINE SOLVE_POLICY_BUDGET\(\).*?END SUBROUTINE SOLVE_POLICY_BUDGET',text,re.S).group()
        self.run_program('''module stub
integer, parameter :: dp=kind(1d0)
real(dp) :: GBAR=0, GBAR_bench=2, GBAR_exp=0, policy_budget_tolerance
integer :: policy_budget_max_iter, calls=0
contains
'''+configure+'\n'+solve+'''
subroutine FIND_DBN_EQ()
calls=calls+1
end subroutine
subroutine GOVNT_BUDGET_OPT()
GBAR=GBAR_bench
end subroutine
subroutine GOVNT_BUDGET(flag)
logical, intent(in) :: flag
! The final revenue calculation disagrees with the provisional budget on trial 1.
if(calls==1) GBAR=GBAR_bench*(1+2*policy_budget_tolerance)
end subroutine
end module
program test
use stub
call SOLVE_POLICY_BUDGET()
if(calls/=2.or.GBAR_exp/=GBAR_bench) error stop 'accepted stale revenue'
end program
''')


if __name__ == '__main__':
    unittest.main()
