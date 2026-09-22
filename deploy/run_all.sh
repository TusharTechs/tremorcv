#!/usr/bin/env bash
# One shot: both benchmarks + results tarball. Keeps paid instance time to minutes.
#   ./deploy/run_all.sh c8g.2xlarge
set -euo pipefail
INSTANCE="${1:?usage: ./deploy/run_all.sh <instance-type>   e.g. c8g.2xlarge}"
cd "$(dirname "$0")/.."

echo "=============== 1/3  COOL ==============="
./deploy/setup_cool.sh
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
PY

python run_bench.py --label graviton-cool --instance "$INSTANCE"
deactivate 2>/dev/null || true

echo; echo "=============== 2/3  stock baseline ==============="
./deploy/setup_stock.sh
# shellcheck disable=SC1090
source "$HOME/stock-venv/bin/activate"
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
