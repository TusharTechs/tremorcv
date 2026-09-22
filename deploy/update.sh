#!/usr/bin/env bash
# Update the running demo endpoint in place: pull, reinstall only if dependencies
# changed, restart. Downtime is one systemd restart (~2s) instead of the ~3 minutes
# an instance replacement costs -- which matters during judging, when a 404 at the
# wrong moment is indistinguishable from a broken submission.
set -euo pipefail
export HOME="${HOME:-/root}"
cd /opt/tremor

BEFORE=$(git rev-parse HEAD 2>/dev/null || echo none)
REQ_BEFORE=$(sha1sum requirements.txt 2>/dev/null | cut -d' ' -f1 || echo none)

git fetch --quiet origin main
git reset --hard --quiet origin/main
AFTER=$(git rev-parse HEAD)
REQ_AFTER=$(sha1sum requirements.txt | cut -d' ' -f1)

echo "commit $BEFORE -> $AFTER"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "already up to date; nothing to do"
  exit 0
fi

if [ "$REQ_BEFORE" != "$REQ_AFTER" ]; then
  echo "requirements changed, reinstalling"
  grep -v '^opencv-python==' requirements.txt > /tmp/req-headless.txt
  echo "opencv-python-headless==5.0.0.93" >> /tmp/req-headless.txt
  .venv/bin/pip install -q -r /tmp/req-headless.txt
fi

# Never restart into a build that cannot import. A failed check leaves the OLD
# process serving, so a bad commit degrades to "not updated" rather than "site down".
.venv/bin/python -c "import cv2, webapp.server" || {
  echo "FATAL: new revision does not import; leaving the running service untouched"
  git reset --hard --quiet "$BEFORE"
  exit 1
}

systemctl restart tremor.service
for i in $(seq 1 20); do
  if curl -s -m 5 http://127.0.0.1/api/health | grep -q '"ok":true'; then
    echo "UPDATE OK at $AFTER (healthy after ${i}s)"
    exit 0
  fi
  sleep 1
done
echo "FATAL: service did not become healthy after restart"
journalctl -u tremor.service --no-pager -n 20
exit 1
