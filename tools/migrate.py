#!/usr/bin/env python3
"""Forward-only-by-default migrator.  up | down | status | pending

Safety properties (each one is a decision, see docs/DECISIONS.md):
  * lock_timeout / statement_timeout are set by THIS tool via PGOPTIONS, never by migration authors.
  * Transactional migrations apply + record in ONE transaction, and are retried with backoff on lock timeout.
  * '-- migrate:no-transaction' files (CREATE INDEX CONCURRENTLY) are never auto-retried: a failure can
    leave an INVALID index, so a human (or the runbook) cleans up first.
  * Applied checksums are verified: editing a merged migration is a hard error.
  * Applied versions must be a prefix of the local list: no out-of-order or skipped migrations.
"""
import argparse, hashlib, os, re, sys, tempfile, time
sys.path.insert(0, os.path.dirname(__file__))
from pgutil import psql, rows

LOCK_TIMEOUT = os.environ.get("LOCK_TIMEOUT", "3s")
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))
DDL = """CREATE TABLE IF NOT EXISTS public.schema_migrations(
  version int PRIMARY KEY, name text NOT NULL, checksum text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now(), applied_by text NOT NULL DEFAULT current_user);"""

def local(d):
    out = []
    for fn in sorted(os.listdir(d)):
        m = re.fullmatch(r"(\d+)_(.+)\.sql", fn)
        if m and not fn.endswith(".down.sql"):
            body = open(os.path.join(d, fn), "rb").read()
            out.append({"version": int(m.group(1)), "name": m.group(2), "path": os.path.join(d, fn),
                        "down": os.path.join(d, fn[:-4] + ".down.sql"), "sum": hashlib.sha256(body).hexdigest(),
                        "text": body.decode()})
    vs = [x["version"] for x in out]
    if len(vs) != len(set(vs)): sys.exit("duplicate migration version numbers")
    return out

def applied():
    psql(["-c", DDL])
    return {int(v): c for v, c in rows("SELECT version, checksum FROM public.schema_migrations ORDER BY version")}

def opts(m):
    t = re.search(r"^--\s*migrate:statement-timeout=(\S+)", m["text"], re.M)
    return {"lock_timeout": LOCK_TIMEOUT, "statement_timeout": t.group(1) if t else "5min",
            "idle_in_transaction_session_timeout": "60s", "application_name": "schema-pipeline"}

def run(m, path, record_sql):
    no_tx = re.search(r"^--\s*migrate:no-transaction", open(path).read(), re.M)
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as rec: rec.write(record_sql)
    try:
        if no_tx:
            psql(["-f", path], options=opts(m)); psql(["-f", rec.name])
            return
        for attempt in range(MAX_RETRIES + 1):
            try:
                psql(["-1", "-f", path, "-f", rec.name], options=opts(m)); return
            except RuntimeError as e:
                if "lock timeout" in str(e) and attempt < MAX_RETRIES:
                    wait = 2 ** (attempt + 1); print(f"  lock timeout (attempt {attempt+1}); backoff {wait}s", flush=True); time.sleep(wait); continue
                raise
    finally: os.unlink(rec.name)

def cmd_up(a):
    mig, done = local(a.dir), applied()
    for m in mig:
        if m["version"] in done and done[m["version"]] != m["sum"]:
            sys.exit(f"CHECKSUM MISMATCH on {m['version']}_{m['name']}: a merged migration was edited. Write a new migration.")
    vs = [m["version"] for m in mig]
    if any(v not in vs for v in done) or sorted(done) != vs[:len(done)]:
        sys.exit(f"applied versions {sorted(done)} are not a prefix of local {vs}: refusing out-of-order apply")
    pending = [m for m in mig if m["version"] not in done and (a.target is None or m["version"] <= a.target)]
    print(f"{len(pending)} pending: {[m['version'] for m in pending]}")
    for m in pending:
        print(f"-> {m['version']}_{m['name']}", flush=True)
        if a.dry_run: continue
        t0 = time.time()
        rec = f"INSERT INTO public.schema_migrations(version,name,checksum) VALUES ({m['version']},'{m['name']}','{m['sum']}');"
        run(m, m["path"], rec); print(f"   ok {time.time()-t0:.1f}s", flush=True)

def cmd_down(a):
    mig, done = local(a.dir), applied()
    for m in [x for x in reversed(mig) if x["version"] in done][: a.steps]:
        if not os.path.exists(m["down"]):
            sys.exit(f"{m['version']}_{m['name']} has no .down.sql: IRREVERSIBLE. Roll forward with a fix, or restore (docs/ROLLBACK.md).")
        print(f"<- {m['version']}_{m['name']}", flush=True)
        run(m, m["down"], f"DELETE FROM public.schema_migrations WHERE version={m['version']};")

def cmd_status(a):
    done = applied(); print(f"applied={sorted(done)} local={[m['version'] for m in local(a.dir)]}")

def with_advisory_lock(fn, a):
    import subprocess
    LOCK_KEY = 84729103412
    proc = subprocess.Popen(
        ["psql", "-X", "-At", "-v", "ON_ERROR_STOP=1"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    proc.stdin.write(f"SELECT pg_try_advisory_lock({LOCK_KEY});\n")
    proc.stdin.flush()
    got = proc.stdout.readline().strip()
    if got != "t":
        proc.terminate()
        sys.exit("ANOTHER MIGRATION RUN IS IN PROGRESS (could not acquire pg_try_advisory_lock)")
    try:
        fn(a)
    finally:
        try:
            proc.stdin.write(f"SELECT pg_advisory_unlock({LOCK_KEY});\n\\q\n")
            proc.stdin.flush()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["up", "down", "status"])
    ap.add_argument("--dir", default="migrations"); ap.add_argument("--target", type=int); ap.add_argument("--steps", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    if a.cmd in ("up", "down") and not a.dry_run:
        with_advisory_lock({"up": cmd_up, "down": cmd_down}[a.cmd], a)
    else:
        {"up": cmd_up, "down": cmd_down, "status": cmd_status}[a.cmd](a)
