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
exec > /var/log/tremor.log 2>&1
set -x
upload() {
  tar czf /tmp/results.tgz -C /home/ubuntu/tremorcv-main results 2>/dev/null || echo "NO RESULTS DIR"
  curl -s -X PUT --upload-file /tmp/results.tgz "${PUT_URL}" -o /dev/null -w 'results upload: %{http_code}\n' || true
  curl -s -X PUT --upload-file /var/log/tremor.log "${LOG_URL}" -o /dev/null -w 'log upload: %{http_code}\n' || true
}
trap 'rc=\$?; echo "=== EXIT rc=\$rc ==="; upload; shutdown -h now' EXIT

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
