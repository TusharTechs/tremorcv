#!/bin/bash
# Stand up the TREMOR demo endpoint as a systemd service on :80.
exec > >(tee /var/log/tremor-web.log > /dev/console) 2>&1
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip curl

cd /opt
curl -sL https://github.com/TusharTechs/tremorcv/archive/refs/heads/main.tar.gz | tar xz
mv tremorcv-main tremor && cd tremor

python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

.venv/bin/python -c "import cv2; print('OpenCV', cv2.__version__)"

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
# a public endpoint running CV on uploads: bound the blast radius
MemoryMax=1600M
CPUQuota=180%
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/tremor/results /tmp

[Install]
WantedBy=multi-user.target
SVC

mkdir -p /opt/tremor/results
systemctl daemon-reload
systemctl enable --now tremor.service
sleep 8
systemctl is-active tremor.service
curl -s -m 10 http://127.0.0.1/api/health && echo "  <- health OK"
echo "=== WEBAPP READY ==="
