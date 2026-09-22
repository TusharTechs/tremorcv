#!/usr/bin/env bash
# Run ON the COOL AMI instance. Uses COOL's own Python venv -- do NOT pip install
# opencv-python here, that would silently replace COOL with a stock wheel.
set -euo pipefail

COOL_VENV=${COOL_VENV:-/opt/cool/venvs/python_3.12/bin/activate}
[ -f "$COOL_VENV" ] || { echo "COOL venv not found at $COOL_VENV"; ls /opt/cool/venvs || true; exit 1; }

# shellcheck disable=SC1090
source "$COOL_VENV"
python - <<'PY'
import cv2, sys
print("OpenCV:", cv2.__version__)
print("cv2 from:", cv2.__file__)
assert "/opt/cool" in cv2.__file__, "cv2 is NOT the COOL build -- refusing to benchmark"
print("COOL build confirmed")
PY

pip install --quiet --no-input numpy matplotlib
echo "ready. run:  source $COOL_VENV && python run_bench.py --label graviton-cool"
