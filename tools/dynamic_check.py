#!/usr/bin/env python3
"""Run a migration against a SEEDED database inside a transaction, observe what it actually did, roll back.
Catches what regex cannot: table rewrites (relfilenode changed) and long ACCESS EXCLUSIVE holds.
No-transaction migrations (CONCURRENTLY) are applied for real on the CI container, then checked for INVALID indexes."""
import argparse, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from pgutil import psql, rows

HARNESS = r"""
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout='3s'; SET LOCAL statement_timeout='120s';
CREATE TEMP TABLE _pre AS SELECT c.oid, c.relname, c.relfilenode FROM pg_class c
  JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','m','i');
SELECT clock_timestamp() AS t0 \gset
\i {path}
SELECT round(extract(epoch FROM clock_timestamp()-:'t0'::timestamptz)*1000) AS ms \gset
\echo DYN_MS :ms
SELECT 'DYN_REWRITE ' || p.relname FROM _pre p JOIN pg_class c ON c.oid=p.oid WHERE c.relfilenode<>p.relfilenode AND p.relname NOT LIKE '%_pkey';
SELECT 'DYN_AEL ' || relation::regclass FROM pg_locks WHERE pid=pg_backend_pid() AND mode='AccessExclusiveLock' AND locktype='relation' AND relation IN (SELECT oid FROM _pre);
ROLLBACK;
"""

def check(path, max_ms, apply=False):
    text = open(path).read(); name = os.path.basename(path)
    if re.search(r"^--\s*migrate:no-transaction", text, re.M):
        psql(["-f", path]); bad = rows("SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid")
        if bad: return [f"{name}: INVALID index left behind: {bad}"]
        print(f"  {name}: applied outside txn, no invalid indexes"); return []
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f: f.write(HARNESS.format(path=os.path.abspath(path)))
    out = psql(["-At", "-f", f.name]).stdout; os.unlink(f.name)
    ms = int(re.search(r"DYN_MS (\d+)", out).group(1)); rw = re.findall(r"DYN_REWRITE (\S+)", out); ael = sorted(set(re.findall(r"DYN_AEL (\S+)", out)))
    print(f"  {name}: {ms} ms inside txn; ACCESS EXCLUSIVE on {ael or 'nothing'}; rewritten: {rw or 'none'}")
    errs = []
    if apply: psql(["-1", "-f", path])  # keep the throwaway DB in step so dependent migrations can be rehearsed in order
    if rw: errs.append(f"{name}: TABLE REWRITE detected on {rw}")
    if ael and ms > max_ms: errs.append(f"{name}: held ACCESS EXCLUSIVE ~{ms} ms (> {max_ms} ms budget) on seeded data")
    return errs

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--max-lock-ms", type=int, default=1500); ap.add_argument("--apply", action="store_true", help="apply each migration after checking it (use ONLY on a throwaway clone)")
    a = ap.parse_args(); errs = []
    for p in a.files: errs += check(p, a.max_lock_ms, a.apply)
    for e in errs: print("ERROR", e)
    sys.exit(1 if errs else 0)
