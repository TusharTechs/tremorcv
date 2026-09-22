#!/usr/bin/env bash
# Stock OpenCV 5.0.0 baseline, in its own venv on the SAME instance.
# Same silicon, same kernel, same clip -- the library is the only variable.
set -euo pipefail

VENV="${STOCK_VENV:-$HOME/stock-venv}"
python3 -m venv "$VENV"
# shellcheck disable=SC1090
source "$VENV/bin/activate"
pip install --quiet --upgrade pip

# headless: the server AMI has no libGL, and the full wheel would fail to import.
# Only highgui differs; every imgproc/core function we benchmark is identical, and
# we use no GUI. Recorded in provenance so the comparison is auditable.
pip install --quiet --no-input "opencv-python-headless==5.0.0.93" numpy

python - <<'PY'
import sys, cv2
print("python :", sys.version.split()[0])
print("OpenCV :", cv2.__version__)
print("cv2    :", cv2.__file__)
if "/opt/cool" in cv2.__file__:
    sys.exit("FATAL: this venv resolved to the COOL build, not stock")
print("OK - stock baseline ready")
PY
