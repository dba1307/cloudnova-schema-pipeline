#!/usr/bin/env python3
"""Post-apply verification gate run between rollout stages. Non-zero exit stops the rollout."""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from pgutil import rows, scalar

def once(max_lag_ms):
    errs = []
    if scalar("SELECT 1") != "1": errs.append("smoke: SELECT 1 failed")
    bad = rows("SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid")
    if bad: errs.append(f"INVALID indexes (failed CONCURRENTLY build?): {bad}")
    blocked = rows("""SELECT pid, now()-query_start FROM pg_stat_activity WHERE wait_event_type='Lock' AND state='active'
                      AND now()-query_start > interval '10 seconds' AND datname=current_database()""")
    if blocked: errs.append(f"{len(blocked)} sessions waiting on locks > 10s: {blocked[:3]}")
    if scalar("SELECT to_regproc('aurora_replica_status') IS NOT NULL") == "t":
        lag = scalar("SELECT COALESCE(max(replica_lag_in_msec),0)::int FROM aurora_replica_status() WHERE session_id<>'MASTER_SESSION_ID'")
        if lag and int(float(lag)) > max_lag_ms: errs.append(f"replica lag {lag} ms > {max_lag_ms}")
    return errs

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--bake-seconds", type=int, default=0)
    ap.add_argument("--interval", type=int, default=10); ap.add_argument("--max-lag-ms", type=int, default=2000); a = ap.parse_args()
    nv = scalar("SELECT count(*) FROM public.schema_migrations"); print(f"migrations recorded: {nv}")
    end = time.time() + a.bake_seconds; n = 0
    while True:
        n += 1; errs = once(a.max_lag_ms)
        for e in errs: print("ERROR", e)
        if errs: sys.exit(1)
        print(f"check {n} ok"); 
        if time.time() >= end: break
        time.sleep(min(a.interval, max(0, end - time.time())))
    unvalidated = rows("SELECT conrelid::regclass, conname FROM pg_constraint WHERE NOT convalidated")
    if unvalidated: print(f"NOTE: NOT VALID constraints awaiting a VALIDATE migration: {unvalidated}")
