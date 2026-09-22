#!/usr/bin/env bash
# Catch cloud-init-only failures locally. user-data runs as root under `set -u`
# with a minimal environment -- no HOME, no PYTHONPATH -- which is how two
# separate Graviton runs died after the instance was already billing.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0

for f in deploy/*.sh; do
  bash -n "$f" || { echo "FAIL syntax: $f"; fail=1; }
done

# Every $VAR expansion must tolerate an empty environment.
for f in deploy/setup_stock.sh deploy/setup_cool.sh deploy/run_all.sh; do
  out=$(env -i bash -c "set -euo pipefail; source <(sed -n '1,/^[^#]*\$/p' $f) 2>&1" 2>&1 | grep -i "unbound variable" || true)
  [ -n "$out" ] && { echo "FAIL unbound in $f: $out"; fail=1; }
done

# The specific expansions that bit us, checked directly.
env -i bash -c 'set -u; VENV="${STOCK_VENV:-${HOME:-/root}/stock-venv}"; echo "$VENV"' >/dev/null \
  || { echo "FAIL: HOME default missing in setup_stock.sh pattern"; fail=1; }
env -i bash -c 'set -u; export PYTHONPATH="${PYTHONPATH:-}"; echo ok' >/dev/null \
  || { echo "FAIL: PYTHONPATH guard missing"; fail=1; }

grep -q 'export HOME=' deploy/run_all.sh    || { echo "FAIL: run_all.sh does not pin HOME"; fail=1; }
grep -q '^unset PYTHONPATH' deploy/run_all.sh || { echo "FAIL: run_all.sh does not clear PYTHONPATH before the baseline"; fail=1; }

# The headless-wheel trap: opencv-python links libGL, which a server does not have.
# Cost one deploy; caught here from now on.
grep -q 'opencv-python-headless' deploy/setup_stock.sh \
  || { echo "FAIL: setup_stock.sh must use the headless wheel"; fail=1; }
grep -q 'opencv-python-headless' deploy/webapp-userdata.sh \
  || { echo "FAIL: webapp-userdata.sh must use the headless wheel (libGL is absent on servers)"; fail=1; }
grep -q "import cv2; print('cv2 import OK'" deploy/webapp-userdata.sh \
  || { echo "FAIL: webapp-userdata.sh must verify cv2 imports before starting the service"; fail=1; }

[ $fail -eq 0 ] && echo "deploy scripts OK (syntax + empty-environment + headless-wheel safety)"
exit $fail
