# Knowing afterwards that a change did not cause harm

## Immediately (inside the pipeline, per stage)
`verify.py` + bake loop: smoke query · no INVALID indexes · no session waiting on a lock > 10 s · replica lag < 2 s · then CloudWatch alarms with prefix `cloudnova-prod-<region>-` must all be OK · then fingerprint == golden. Any failure stops the rollout.

## Alarms (Terraform: `alarms.tf`), page vs ticket
| Signal | Why a schema change moves it | Action |
|---|---|---|
| `BlockedTransactions` > 5 for 3 min | migration queued behind/in front of a lock | **page**; `pg_blocking_pids()`, cancel the migration pid (the transaction rolls back safely) |
| `Deadlocks` > 0 | new FK/lock ordering | page if sustained |
| `AuroraReplicaLagMaximum` > 2 s | big write/backfill, index build | ticket → throttle |
| `CPUUtilization` > 80% 5 min | missing index / seq scan after change | page; check plan regression below |
| `MaximumUsedTransactionIDs` | long txns, vacuum blocked | ticket |
Also dashboards, not alarms: Performance Insights `db.load` by wait event (`Lock:*`, `IO:*`), app p95/p99 and 5xx per region, connection count, `log_lock_waits` lines (CloudWatch Logs metric filter on "still waiting for"), slow-statement log.

## Plan regression
1. **Before** (CI): `plan_check.py` EXPLAINs the hot queries in `queries/critical.sql` on seeded, ANALYZEd data before and after; fails on node/index changes or cost > 1.5×. Backend teams add their queries in the same PR.
2. **After** (prod): `monitoring/pgss_compare.sql` snapshots `pg_stat_statements` before the stage and flags queries whose mean time in the bake window is > 2× their prior mean. A hit is a suspect: pull the real plan from `auto_explain` output in the log (>3 s) or Performance Insights and diff it with the CI snapshot. Remember `ANALYZE` after large changes: stale stats are a classic "regression".
3. Limitation: CI plans on 300k rows can differ from prod's distribution; prod data is the final judge, hence the canary.

## On-call quick reference
* Stage red in Actions → read the `verify`/`drift` group. *Nothing applied yet* if the migrate step failed on lock timeout (transactional rollback).
* Migration stuck: `SELECT pid, wait_event_type, state, left(query,80) FROM pg_stat_activity WHERE application_name='schema-pipeline';` then `SELECT pg_cancel_backend(pid)`.
* INVALID index → drop concurrently, re-run. Drift issue opened → diff in the issue body; decide whether to codify the hand-fix as a migration or revert it.
