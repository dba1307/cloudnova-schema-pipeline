#!/usr/bin/env python3
"""Pre-deploy plan-regression check.  snapshot OUT.json  |  compare BEFORE.json AFTER.json
Runs EXPLAIN (FORMAT JSON) for each query in queries/critical.sql on the seeded CI database before and after the migration.
Fails if an index scan degrades to a sequential scan, a query is missing, or total cost grows beyond the ratio."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from pgutil import psql, rows

def queries(path):
    return re.findall(r"--\s*name:\s*(\S+)\n(.*?;)", open(path).read(), re.S)

def shape(node):
    s = node["Node Type"] + (f"[{node.get('Index Name') or node.get('Relation Name','')}]")
    return [s] + [x for c in node.get("Plans", []) for x in shape(c)]

def has_index_scan(plan_shape):
    return any("Index" in step for step in plan_shape)

def has_seq_scan(plan_shape):
    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret   fo    ret    ret    ret    ret    r      ret    ret    rel([    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    r      ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    {    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret    ret       ret    ret    ret  IO    ret    ret    ret    ret    ret    ret )
                                                  n                                                  n                          ha               sh                                                  n                                    d(f"i                                                  n                fter                            ]["c                                                  n nd(f                            {a[k]['cost']:.0f} (> x{ratio})")
        status = "REGRESSION " if notes else ("improved   " if b_shape != a_shape else "ok         ")
        print(status + k + ("".join("\n  " + n for n in notes)))
        bad += bool(notes)
    return bad

if __name__ == "__main__":
    if sys.argv[1] == "snapshot": snapshot(sys.argv[2], os.environ.get("QUERIES", "queries/critical.sql"))
    else: sys.exit(1 if compare(json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))) else 0)
