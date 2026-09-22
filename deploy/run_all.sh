#!/usr/bin/env bash
# One shot: both benchmarks + results tarball. Keeps paid instance time to minutes.
#   ./deploy/run_all.sh c8g.2xlarge
set -euo pipefail
# cloud-init gives user-data a minimal env (no HOME). Pin it before anything
# that expands $HOME under set -u.
export HOME="${HOME:-/root}"
INSTANCE="${1:?usage: ./deploy/run_all.sh <instance-type>   e.g. c8g.2xlarge}"
cd "$(dirname "$0")/.."

echo "=============== 1/3  COOL ==============="
./deploy/setup_cool.sh

# COOL's activate prepends to $PYTHONPATH and $LD_LIBRARY_PATH without defaults.
# Under `set -u` that is fatal ("PYTHONPATH: unbound variable"), which killed a run
# before it measured anything. Define them empty rather than weakening -u.
export PYTHONPATH="${PYTHONPATH:-}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"

# shellcheck disable=SC1090
source "$(cat /tmp/tremor_cool_venv)"

# Abort BEFORE collecting data if provenance cannot substantiate the label.
# All three must hold: Arm silicon, a Graviton EC2 instance, COOL SDK present.
python - <<'PY'
import sys; sys.path.insert(0, ".")
from bench.core import provenance
p = provenance()
print("provenance:", p["cool_verification_parts"], "instance:", p["ec2_instance_type"] or "?")
if not p["cool_verified"]:
    sys.exit("FATAL: cool_verified is False. Refusing to write results labelled "
             "'graviton-cool'. Fix the environment or relabel the run.")
print("COOL provenance verified")
if not p["opencv5_requirement_met"]:
    print(f"WARNING: COOL ships OpenCV {p['opencv_version']}, not 5.x. The "
          f"competition requires OpenCV 5 for the substantive analysis - see "
          f"docs/THRESHOLDS.md. Continuing; the version is recorded in the "
          f"result file.")
PY

python run_bench.py --label graviton-cool --instance "$INSTANCE"
deactivate 2>/dev/null || true

echo; echo "=============== 2/3  stock baseline ==============="
./deploy/setup_stock.sh

# setup_stock.sh unsets PYTHONPATH in ITS OWN process; this parent shell still
# carries COOL's, because we sourced COOL's activate above. Without clearing it
# here the baseline would import COOL through PYTHONPATH even from a clean venv --
# the exact leak that made the first run a COOL-vs-COOL comparison.
unset PYTHONPATH
unset LD_LIBRARY_PATH

# shellcheck disable=SC1090
source "$HOME/stock-venv/bin/activate"

# Gate the BASELINE as well. The first run produced a void comparison because
# only the COOL leg was checked: COOL's PYTHONPATH leaked through `deactivate`
# and the "stock" leg measured COOL, reporting cool_verified=True under the old
# isdir() check. Both legs must now prove which library they loaded.
python - <<'PY'
import sys; sys.path.insert(0, ".")
from bench.core import provenance
p = provenance()
print("baseline provenance:", p["cool_verification_parts"],
      "opencv:", p["opencv_version"])
if p["cool_verification_parts"]["cv2_loaded_from_cool"]:
    sys.exit("FATAL: baseline loaded the COOL build. Refusing to write results "
             "labelled 'graviton-stock' - the comparison would be COOL vs COOL.")
if not p["opencv5_requirement_met"]:
    sys.exit(f"FATAL: baseline is OpenCV {p['opencv_version']}, expected 5.x")
print("baseline verified as stock OpenCV 5")
PY

python run_bench.py --label graviton-stock --instance "$INSTANCE"

echo; echo "=============== 3/3  report ==============="
# Explicit order: stock is the BASELINE, COOL is measured against it.
# compare.py globs alphabetically otherwise, which would make 'graviton-cool'
# the baseline and invert every speedup.
python compare.py results/graviton-stock.json results/graviton-cool.json \
  | tee results/report.md
tar czf /tmp/tremor-results.tgz results/
echo
echo "Done. Pull the results from your laptop with:"
echo "  scp -i <key.pem> ubuntu@<ip>:/tmp/tremor-results.tgz ."
echo
echo "THEN TERMINATE THE INSTANCE."
