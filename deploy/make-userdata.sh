#!/usr/bin/env bash
# Emit cloud-init user-data that runs the benchmark unattended and uploads results.
#
# Exists because hand-writing the remote script is how the first run produced a
# void comparison: it re-implemented run_all.sh, dropped `set -e`, and ignored a
# failing isolation assert. This wrapper CALLS run_all.sh so there is one
# implementation of the benchmark sequence, not two.
#
#   ./deploy/make-userdata.sh <results-put-url> <log-put-url> [repo-tarball-url]
set -euo pipefail
PUT_URL="${1:?results presigned PUT url}"
LOG_URL="${2:?log presigned PUT url}"
REPO="${3:-https://github.com/TusharTechs/tremorcv/archive/refs/heads/main.tar.gz}"

cat <<UD
#!/bin/bash
# tee, not redirect: a plain redirect hides all progress from the EC2 console, and
# with no SSH there is then no way to see where a run is stuck. /dev/console makes
# it readable via get-console-output while the run is live.
exec > >(tee /var/log/tremor.log > /dev/console) 2>&1
set -x
upload() {
  tar czf /tmp/results.tgz -C /home/ubuntu/tremorcv-main results 2>/dev/null || echo "NO RESULTS DIR"
  curl -s -X PUT --upload-file /tmp/results.tgz "${PUT_URL}" -o /dev/null -w 'results upload: %{http_code}\n' || true
  curl -s -X PUT --upload-file /var/log/tremor.log "${LOG_URL}" -o /dev/null -w 'log upload: %{http_code}\n' || true
}
trap 'rc=\$?; echo "=== EXIT rc=\$rc ==="; upload; shutdown -h now' EXIT

# Watchdog. A deadlock produced 0% CPU for 15 minutes with the run apparently
# alive; without this the instance bills until someone notices.
( sleep ${WATCHDOG_S:-1800}; echo "=== WATCHDOG FIRED: exceeded ${WATCHDOG_S:-1800}s ==="; \
  upload; shutdown -h now ) &

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3-venv || echo "apt warn"

cd /home/ubuntu
curl -sL "${REPO}" | tar xz
cd tremorcv-main
chmod +x deploy/*.sh

# One implementation of the sequence. It is set -euo pipefail and aborts on a
# failed provenance or isolation check rather than mislabelling data.
./deploy/run_all.sh c8g.2xlarge
UD
