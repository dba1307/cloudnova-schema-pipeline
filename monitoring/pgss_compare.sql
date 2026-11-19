-- Production plan-regression detector (per-query latency/IO deltas across a deploy), run by the pipeline or an on-call.
-- Needs pg_stat_statements (preloaded via the parameter group) and pg_monitor (granted to migrator).
-- 1) BEFORE the rollout stage:
CREATE SCHEMA IF NOT EXISTS dbre;
CREATE TABLE IF NOT EXISTS dbre.pgss_snap(taken timestamptz, queryid bigint, calls bigint, total_exec_time double precision, shared_blks_read bigint, rows bigint);
INSERT INTO dbre.pgss_snap SELECT now(), queryid, calls, total_exec_time, shared_blks_read, rows FROM pg_stat_statements WHERE calls > 0;
-- 2) AFTER the bake window: per-query mean latency in the bake window vs the same query's lifetime mean before it.
WITH b AS (SELECT DISTINCT ON (queryid) queryid, calls, total_exec_time, shared_blks_read FROM dbre.pgss_snap ORDER BY queryid, taken DESC),
     a AS (SELECT queryid, calls, total_exec_time, shared_blks_read, left(query, 120) AS q FROM pg_stat_statements)
SELECT a.q,
       round((b.total_exec_time / NULLIF(b.calls,0))::numeric, 2)                                            AS mean_ms_before,
       round(((a.total_exec_time - b.total_exec_time) / NULLIF(a.calls - b.calls,0))::numeric, 2)           AS mean_ms_during_bake,
       round((((a.total_exec_time - b.total_exec_time) / NULLIF(a.calls - b.calls,0)) / NULLIF(b.total_exec_time / NULLIF(b.calls,0),0))::numeric, 1) AS ratio,
       a.calls - b.calls AS calls_in_window
FROM a JOIN b USING (queryid)
WHERE a.calls - b.calls >= 50 AND b.calls >= 100
  AND ((a.total_exec_time - b.total_exec_time) / (a.calls - b.calls)) > 2 * (b.total_exec_time / b.calls)   -- >2x slower
ORDER BY ratio DESC LIMIT 20;
-- A hit is a SUSPECT, not a verdict: find the plan in the postgresql log (auto_explain) or Performance Insights, compare to the CI plan snapshot.
