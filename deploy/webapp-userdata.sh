#!/bin/bash
# Stand up the TREMOR demo endpoint as a systemd service on :80.
exec > >(tee /var/log/tremor-web.log > /dev/console) 2>&1
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip curl git

cd /opt
# git clone, not a tarball: deploy/update.sh pulls in place so a UI change costs one
# systemd restart (~2s) instead of a full instance replacement (~3 min of downtime).
apt-get install -y -qq git
git clone --depth 50 https://github.com/TusharTechs/tremorcv.git tremor
cd tremor

python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
# requirements.txt pins opencv-python (the full wheel), which links libGL for its GUI
# module. A headless server has no libGL, so `import cv2` raises ImportError, uvicorn
# exits, and systemd's Restart=always turns it into a crash loop that looks like a
# slow startup. Install the headless wheel instead -- identical imgproc/core, no GUI.
grep -v '^opencv-python==' requirements.txt > /tmp/req-headless.txt
echo "opencv-python-headless==5.0.0.93" >> /tmp/req-headless.txt
.venv/bin/pip install -q -r /tmp/req-headless.txt

# Prove cv2 imports BEFORE handing it to systemd, so a failure is visible here
# rather than as an opaque restart loop.
.venv/bin/python -c "import cv2; print('cv2 import OK', cv2.__version__)" || {
  echo "FATAL: cv2 will not import; not starting the service"
  .venv/bin/python -c "import cv2" 2>&1 | tail -5
  exit 1
}


cat > /etc/systemd/system/tremor.service <<'SVC'
[Unit]
Description=TREMOR demo endpoint
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/tremor
Environment=TREMOR_MAX_UPLOAD_MB=100
ExecStart=/opt/tremor/.venv/bin/uvicorn webapp.server:app --host 0.0.0.0 --port 80 --workers 1
Restart=always
RestartSec=5
# Bound the blast radius of a public endpoint that runs CV on uploads -- but do NOT
# use ProtectSystem=strict here: it makes /opt/tremor read-only, and Python needs to
# write __pycache__ and matplotlib/numpy need a writable config dir. That silently
# prevented the service from serving at all.
MemoryMax=1700M
CPUQuota=180%
NoNewPrivileges=true
Environment=MPLCONFIGDIR=/tmp/mpl
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=multi-user.target
SVC

mkdir -p /opt/tremor/results
systemctl daemon-reload
systemctl enable --now tremor.service

# Wait for it to actually serve, then prove it -- the previous deploy reported
# READY while the unit was still "activating" and never checked again.
for i in $(seq 1 30); do
  if curl -s -m 5 http://127.0.0.1/api/health | grep -q '"ok":true'; then
    echo "=== HEALTH OK after ${i}0s ==="
    curl -s -m 5 http://127.0.0.1/api/health
    echo
    echo "=== WEBAPP READY ==="
    exit 0
  fi
  sleep 10
done

echo "=== WEBAPP FAILED TO SERVE - diagnostics ==="
systemctl status tremor.service --no-pager -l | head -20
echo "--- journal ---"
journalctl -u tremor.service --no-pager -n 40
echo "--- listening sockets ---"
ss -lntp 2>/dev/null | head
echo "--- can python import the app? ---"
cd /opt/tremor && ./.venv/bin/python -c "import webapp.server; print('import OK')" 2>&1 | tail -20
