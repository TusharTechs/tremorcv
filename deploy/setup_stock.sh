#!/usr/bin/env bash
# Baseline on the SAME Graviton instance: stock OpenCV 5.0.0, separate venv so the
# two builds never contaminate each other. This is the apples-to-apples comparison.
set -euo pipefail
python3 -m venv ~/stock-venv
source ~/stock-venv/bin/activate
pip install --quiet --no-input "opencv-python==5.0.0.*" numpy matplotlib
python -c "import cv2; assert '/opt/cool' not in cv2.__file__; print('stock OpenCV', cv2.__version__)"
echo "ready. run:  source ~/stock-venv/bin/activate && python run_bench.py --label graviton-stock"
