#!/usr/bin/env bash
# Stock OpenCV baseline, in its own venv on the SAME instance.
# Same silicon, same kernel, same clip -- the library is the only variable.
set -euo pipefail

# CRITICAL: COOL's activate exports PYTHONPATH pointing at its own cv2, and
# Python's `deactivate` restores PATH and VIRTUAL_ENV but does NOT unset
# PYTHONPATH. Without this the "stock" venv silently imports COOL's library and
# the comparison measures COOL against itself. Observed: both labels returned
# 4.14.0-pre from /opt/cool and differed by 0.4%.
unset PYTHONPATH
unset LD_LIBRARY_PATH

VENV="${STOCK_VENV:-$HOME/stock-venv}"
rm -rf "$VENV"
python3 -m venv "$VENV"
# shellcheck disable=SC1090
source "$VENV/bin/activate"
pip install --quiet --upgrade pip

# headless: the server AMI has no libGL and the full wheel would fail to import.
# Only highgui differs; every imgproc/core function benchmarked is identical.
pip install --quiet --no-input "opencv-python-headless==5.0.0.93" numpy

python - <<'PY'
import sys, os, cv2
real = os.path.realpath(cv2.__file__)
print("python :", sys.version.split()[0])
print("OpenCV :", cv2.__version__)
print("cv2    :", real)
print("PYTHONPATH:", repr(os.environ.get("PYTHONPATH", "")))
if "/opt/cool" in real:
    sys.exit("FATAL: stock venv resolved to the COOL build - isolation failed")
if not cv2.__version__.startswith("5."):
    sys.exit(f"FATAL: expected OpenCV 5.x baseline, got {cv2.__version__}")
print("OK - stock baseline isolated and verified")
PY
