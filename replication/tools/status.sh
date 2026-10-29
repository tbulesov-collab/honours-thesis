#!/usr/bin/env bash
# Show the state of every GKK result in this tree: what is running, how far the
# optimal-wealth-tax grid has got, and the headline numbers next to the paper.
#
#   bash tools/status.sh
#
# Read-only. Starts nothing.

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
M="Revision/Model_2.1_Local"

echo
echo "=================== RUNNING ==================="
n=$(ps -eo command | grep -c "[r]un_mac.sh optw")
r=$(ps -eo command | grep -c "[r]eproduce_rn_reform.sh")
b=$(ps -eo command | grep -c "[C]ompiled_Files_Baseline/GKK_Main.a")
echo "  optw runs      : $n   (must never exceed 1)"
echo "  RN reform runs : $r"
echo "  model binaries : $b"
if [ "$n" -gt 1 ]; then
  echo "  *** MORE THAN ONE optw RUNNING - they overwrite each other."
  echo "  *** stop with:  pkill -f run_mac.sh"
fi
[ "$b" -eq 0 ] && echo "  nothing is running"

echo
echo "============= OWT GRID PROGRESS ==============="
S="$M/Opt_Tax_W/Stats_by_tau_w.txt"
if [ -f "$S" ]; then
  done=$(awk 'NR>1 && NF>5' "$S" | wc -l | tr -d ' ')
  uniq=$(awk 'NR>1 && NF>5 {print $2}' "$S" | sort -u | wc -l | tr -d ' ')
  echo "  rows written : $done      unique tau_w : $uniq of 12"
  [ "$done" -gt "$uniq" ] && echo "  *** duplicate rows: two runs wrote to this file"
  awk 'NR>1 && NF>5 {printf "    tau_w=%5.2f%%  tau_L=%6.2f%%  CE2_NB=%8.4f  K=%7.4f\n", 100*$2, 100*(1-$3), $27, $5}' "$S"
else
  echo "  no grid file yet"
fi

echo
echo "============ OKIT GRID PROGRESS ==============="
K="$M/Stats_by_tau_k_2.txt"
[ -f "$K" ] || K="$M/Opt_Tax_K/Stats_by_tau_k_2.txt"
if [ -f "$K" ]; then
  done=$(awk 'NR>1 && NF>5' "$K" | wc -l | tr -d ' ')
  echo "  rows written : $done"
  awk 'NR>1 && NF>5 {printf "    tau_k=%6.2f%%  tau_L=%6.2f%%  CE2_NB=%8.4f  K=%7.4f\n", 100*$1, 100*(1-$3), $27, $5}' "$K"
else
  echo "  no OKIT grid file yet (run: bash tools/start_okit.sh)"
fi

echo
echo "=========== HEADLINE RESULTS vs PAPER ========="
printf "  %-26s %12s %12s\n" "" "model" "paper"

get() { awk -v k="$2" '$1==k {print $2; exit}' "$1" 2>/dev/null; }

bench="$M/output.txt"
if [ -f "$bench" ]; then
  v=$(get "$bench" "Wealth_Top_1%");    [ -n "$v" ] && printf "  %-26s %12.4f %12s\n" "benchmark top 1% share" "$v" "0.36"
  v=$(get "$bench" "Wealth_Output");    [ -n "$v" ] && printf "  %-26s %12.4f %12s\n" "benchmark K/Y" "$v" "3.00"
fi

rn="$M/Tax_Reform/output_exp.txt"
if [ -f "$rn" ]; then
  v=$(get "$rn" "Wealth_Tax_Above");    [ -n "$v" ] && printf "  %-26s %12.4f %12s\n" "RN reform tau_a (%)" "$(echo "$v" | awk '{print 100*$1}')" "1.19357"
  v=$(get "$rn" "CE1_NB(exp)");         [ -n "$v" ] && printf "  %-26s %12.4f %12s\n" "RN reform CE1" "$v" "6.8"
  v=$(get "$rn" "CE2_NB(exp)");         [ -n "$v" ] && printf "  %-26s %12.4f %12s\n" "RN reform CE2" "$v" "7.2"
fi

opt="$M/Opt_Tax_W/stat_opt_tau_w.txt"
if [ -f "$opt" ]; then
  awk '{printf "  %-26s %12.4f %12s\n", "OWT tau_a (%)",  100*$2,       "3.03"
        printf "  %-26s %12.4f %12s\n", "OWT tau_L (%)",  100*(1-$3),   "15.4"
        printf "  %-26s %12.4f %12s\n", "OWT CE2",        $27,          "8.7"}' "$opt"
fi

echo
echo "  full RN tables:  python3 tools/compare_to_paper.py"
echo
