#!/usr/bin/env bash
# Verify the COOL environment. Installs NOTHING by design.
#
# The benchmark needs only cv2 + numpy, both of which the COOL AMI already ships.
# Running `pip install` inside /opt/cool would be actively harmful: the directory is
# likely root-owned, and forcing a numpy version risks an ABI mismatch with the cv2
# that COOL was built against -- breaking the exact thing we are measuring.
set -euo pipefail

COOL_VENV="${COOL_VENV:-}"
if [ -z "$COOL_VENV" ]; then
  for v in 3.12 3.11 3.10; do
    cand="/opt/cool/venvs/python_$v/bin/activate"
    [ -f "$cand" ] && COOL_VENV="$cand" && break
  done
fi
if [ -z "$COOL_VENV" ]; then
  echo "FATAL: no COOL venv found under /opt/cool/venvs" >&2
  ls -la /opt/cool/venvs 2>/dev/null || echo "  (/opt/cool/venvs does not exist)" >&2
  exit 1
fi
echo "COOL venv: $COOL_VENV"

# COOL's activate prepends to $PYTHONPATH and $LD_LIBRARY_PATH without defaults.
# Under `set -u` that is fatal ("PYTHONPATH: unbound variable"), which killed a run
# before it measured anything. Define them empty rather than weakening -u.
export PYTHONPATH="${PYTHONPATH:-}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"

# shellcheck disable=SC1090
source "$COOL_VENV"
python - <<'PY'
import sys
import cv2
print("python :", sys.version.split()[0])
print("OpenCV :", cv2.__version__)
print("cv2    :", cv2.__file__)
if "/opt/cool" not in cv2.__file__:
    sys.exit("FATAL: cv2 is NOT the COOL build - refusing to benchmark under this label")
try:
    import numpy
    print("numpy  :", numpy.__version__)
except ImportError:
    sys.exit("FATAL: numpy missing from the COOL venv; benchmark cannot run")
print("OK - COOL environment verified, nothing installed")
PY
echo "$COOL_VENV" > /tmp/tremor_cool_venv
