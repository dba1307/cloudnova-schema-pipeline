#!/usr/bin/env python3
"""Pre-deploy plan-regression check.  snapshot OUT.json  |  compare BEFORE.json AFTER.json
Runs EXPLAIN (FORMAT JSON) for each query in queries/critical.sql on the seeded CI database before and after the migration.
Fails if an index scan degrades to a sequential scan, a query is missing, or total cost grows beyond the ratio."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from pgutil import psql

def queries(path):
    return re.findall(r"--\s*name:\s*(\S+)\n(.*?;)", open(path).read(), re.S)

def shape(node):
    s = node["Node Type"] + (f"[{node.get('Index Name') or node.get('Relation Name','')}]")
    return [s] + [x for c in node.get("Plans", []) for x in shape(c)]

def has_index_scan(plan_shape):
    return any("Index" in step for step in plan_shape)

def has_seq_scan(plan_shape):
    return any(step.startswith("Seq Scan") for step in plan_shape)

def snapshot(out, qfile):
    psql(["-c", "ANALYZE"])
    res = {}
    for name, q in queries(qfile):
        raw = psql(["-At", "-c", "EXPLAIN (FORMAT JSON) " + q.strip().rstrip(";")]).stdout
        j = json.loads(raw)[0]["Plan"]
        res[name] = {"shape": shape(j), "cost": j["Total Cost"]}
    json.dump(res, open(out, "w"), indent=1)
    print(f"snapshot of {len(res)} queries -> {out}")

def compare(b, a, ratio=1.5):
    bad = 0
    for k in b:
        if k not in a:
            print(f"REGRESSION {k}\n  query missing from after snapshot")
            bad += 1
            continue
        notes = []
        b_shape, a_shape = b[k]["shape"], a[k]["shape"]
        if has_index_scan(b_shape) and not has_index_scan(a_shape) and has_seq_scan(a_shape):
            notes.append(f"index scan degraded to sequential scan:\n    before {b_shape}\n    after  {a_shape}")
        if a[k]["cost"] > b[k]["cost"] * ratio:
            notes.append(f"cost {b[k]['cost']:.0f} -> {a[k]['cost']:.0f} (> x{ratio})")
        status = "REGRESSION " if notes else ("improved   " if b_shape != a_shape else "ok         ")
        print(status + k + ("".join("\n  " + n for n in notes)))
        bad += bool(notes)
    return bad

if __name__ == "__main__":
    if sys.argv[1] == "snapshot":
        snapshot(sys.argv[2], os.environ.get("QUERIES", "queries/critical.sql"))
    else:
        sys.exit(1 if compare(json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))) else 0)
