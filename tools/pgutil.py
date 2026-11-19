"""Thin psql wrapper. Connection comes from standard PG* env vars (PGHOST, PGUSER, PGPASSWORD...).
We shell out to psql rather than use a driver: zero Python deps, identical behaviour to what a human runs."""
import os, subprocess

def psql(args, sql=None, options=None, check=True):
    env = dict(os.environ)
    if options: env["PGOPTIONS"] = " ".join(f"-c {k}={v}" for k, v in options.items())
    p = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", *args], input=sql, text=True, capture_output=True, env=env)
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"psql exited {p.returncode}")
    return p

def rows(sql, options=None):
    p = psql(["-At", "-F", "\t", "-c", sql], options=options)
    return [r.split("\t") for r in p.stdout.splitlines() if r != ""]

def scalar(sql): 
    r = rows(sql); return r[0][0] if r else None
