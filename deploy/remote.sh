#!/usr/bin/env bash
# Run a command on the demo instance via SSM. Exists because this project cannot SSH:
# the developer's ISP intercepts port 22 and returns a forged banner, so a normal
# `ssh` never completes the key exchange. SSM needs no inbound port at all.
#
#   ./deploy/remote.sh update           pull + restart in place
#   ./deploy/remote.sh status           service status and health
#   ./deploy/remote.sh logs             recent journal
#   ./deploy/remote.sh '<shell>'        anything else
set -euo pipefail
export AWS_PAGER=""
REGION="${AWS_REGION:-us-east-1}"
IID="${TREMOR_INSTANCE:-$(aws ec2 describe-instances --region "$REGION" \
  --filters 'Name=tag:Name,Values=tremor-web' 'Name=instance-state-name,Values=running' \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)}"
[ -z "$IID" ] || [ "$IID" = "None" ] && { echo "no running tremor-web instance"; exit 1; }

case "${1:-status}" in
  update) CMD='cd /opt/tremor && ./deploy/update.sh' ;;
  status) CMD='systemctl is-active tremor.service; systemctl show tremor.service -p NRestarts --value | sed "s/^/restarts: /"; curl -s -m 5 http://127.0.0.1/api/health; echo; cd /opt/tremor && git log --oneline -1' ;;
  logs)   CMD='journalctl -u tremor.service --no-pager -n 40' ;;
  *)      CMD="$1" ;;
esac

CID=$(aws ssm send-command --region "$REGION" --instance-ids "$IID" \
  --document-name AWS-RunShellScript --comment "tremor ${1:-status}" \
  --parameters "commands=[\"$(printf '%s' "$CMD" | sed 's/"/\\"/g')\"]" \
  --query 'Command.CommandId' --output text)

for _ in $(seq 1 60); do
  ST=$(aws ssm get-command-invocation --region "$REGION" --command-id "$CID" \
        --instance-id "$IID" --query Status --output text 2>/dev/null || echo Pending)
  case "$ST" in Success|Failed|TimedOut|Cancelled) break ;; esac
  sleep 2
done
echo "--- $ST ---"
aws ssm get-command-invocation --region "$REGION" --command-id "$CID" --instance-id "$IID" \
  --query 'StandardOutputContent' --output text
ERR=$(aws ssm get-command-invocation --region "$REGION" --command-id "$CID" --instance-id "$IID" \
      --query 'StandardErrorContent' --output text)
[ -n "$ERR" ] && [ "$ERR" != "None" ] && { echo "--- stderr ---"; echo "$ERR"; }
[ "$ST" = "Success" ] || exit 1
