#!/usr/bin/env python3
"""Pre-deploy plan-regression check.  snapshot OUT.json  |  compare BEFORE.json AFTER.json
Runs EXPLAIN (FORMAT JSON) for each query in queries/critical.sql on the seeded CI database before and after the migration.
Fails if any relation degrades from an index scan to a sequential scan, a query is missing, or total cost grows beyond the ratio."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from pgutil import psql

def queries(path):
    return re.findall(r"--\s*name:\s*(\S+)\n(.*?;)", open(path).read(), re.S)

def shape(node):
    s = node["Node Type"] + (f"[{node.get('Index Name') or node.get('Relation Name','')}]")
    return [s] + [x for c in node.get("Plans", []) for x in shape(c)]

def scan_relations(plan_shape):
    idx_rels, seq_rels = set(), set()
    for step in plan_shape:
        m = re.match(r"^([^\[]+)\[([^\]]*)\]$", step)
        if not m:
            continue
        node_type, target = m.group(1), m.group(2)
        if "Index" in node_type and target:
            idx_rels.add(target)
        elif node_type == "Seq Scan" and target:
            seq_rels.add(target)
    return idx_rels, seq_rels

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
        b_idx, b_seq = scan_relations(b_shape)
        a_idx, a_seq = scan_relations(a_shape)
        new_seq = a_seq - b_seq
        if b_idx and new_seq:
            notes.append(f"relation(s) {sorted(new_seq)} newly using Seq Scan (had index usage {sorted(b_idx)}):\n    before {b_shape}\n    after  {a_shape}")
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
