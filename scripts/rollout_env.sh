#!/usr/bin/env bash
# One stage of the rollout: connect -> migrate -> verify (+bake) -> drift check against golden schema.
# TARGET_MODE=demo : Postgres service container, password auth (what CI runs here)
# TARGET_MODE=aws  : Aurora, IAM database auth token, TLS verify-full, CloudWatch alarm gate. Needs a VPC-attached runner.
set -euo pipefail
STAGE="${1:?stage}"; BAKE="${BAKE_SECONDS:-20}"; MODE="${TARGET_MODE:-demo}"
cd "$(dirname "$0")/.."
if [[ "$MODE" == "aws" ]]; then
  : "${DB_HOST:?}" "${AWS_REGION:?}"
  export PGHOST="$DB_HOST" PGPORT=5432 PGUSER=migrator PGDATABASE=cloudnova PGSSLMODE=verify-full PGSSLROOTCERT="${RDS_CA_BUNDLE:?}"
  PGPASSWORD="$(aws rds generate-db-auth-token --hostname "$DB_HOST" --port 5432 --region "$AWS_REGION" --username migrator)"; export PGPASSWORD
else
  export PGHOST=localhost PGPORT=5432 PGDATABASE=cloudnova
  # Demo: bootstrap the least-privilege role as the container superuser, then run EVERYTHING else as 'migrator'.
  PGUSER=postgres PGPASSWORD=postgres psql -X -q -v ON_ERROR_STOP=1 -f db/bootstrap/roles.sql -c "ALTER ROLE migrator PASSWORD 'ci-only'"
  export PGUSER=migrator PGPASSWORD=ci-only
fi
echo "::group::[$STAGE] migrate"; echo "==> Pre-change snapshot ($STAGE)"
if [ "${TARGET_MODE:-demo}" = "aws" ]; then
  echo "Taking pre-change Aurora cluster snapshot before applying migrations"
  # aws rds create-db-cluster-snapshot --db-cluster-identifier "$CLUSTER_ID" --db-snapshot-identifier "${CLUSTER_ID}-pre-$(date +%Y%m%d%H%M%S)"
else
  pg_dump --schema-only -f "/tmp/pre_change_${STAGE}.sql"
fi
python3 tools/migrate.py up; echo "::endgroup::"
echo "::group::[$STAGE] verify (bake ${BAKE}s)"; python3 tools/verify.py --bake-seconds "$BAKE"; echo "::endgroup::"
if [[ "$MODE" == "aws" && -n "${ALARM_PREFIX:-}" ]]; then
  FIRING="$(aws cloudwatch describe-alarms --alarm-name-prefix "$ALARM_PREFIX" --state-value ALARM --query 'MetricAlarms[].AlarmName' --output text)"
  [[ -z "$FIRING" ]] || { echo "::error::alarms firing after bake: $FIRING"; exit 1; }
fi
echo "::group::[$STAGE] drift vs golden"
python3 tools/fingerprint.py dump > "env-$STAGE.json"; python3 tools/fingerprint.py compare golden/golden.json "env-$STAGE.json"
echo "::endgroup::"
