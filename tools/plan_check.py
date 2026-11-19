#!/usr/bin/env python3
"""Pre-deploy plan-regression check.  snapshot OUT.json  |  compare BEFORE.json AFTER.json
Runs EXPLAIN (FORMAT JSON) for each query in queries/critical.sql on the seeded CI database before and after the migration.
Fails if a relation that previously used an index degrades to a sequential scan, a query is missing, or total cost grows beyond the ratio."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from pgutil import psql

def queries(path):
    return re.findall(r"--\s*name:\s*(\S+)\n(.*?;)", open(path).read(), re.S)

def shape(node):
    rel = node.get("Relation Name", "")
    idx = node.get("Index Name", "")
    label = f"{rel}:{idx}" if (rel and idx) else (idx or rel)
    s = node["Node Type"] + (f"[{label}]" if label else "")
    return [s] + [x for c in node.get("Plans", []) for x in shape(c)]

def collect_rels(node, idx_rels=None, seq_rels=None):
    if idx_rels is None:
        idx_rels, seq_rels = set(), set()
    nt = node.get("Node Type", "")
    rel = node.get("Relation Name", "")
    if rel:
        if "Index" in nt:
            idx_rels.add(rel)
        elif nt == "Seq Scan":
            seq_rels.add(rel)
    for c in node.get("Plans", []):
        collect_rels(c, idx_rels, seq_rels)
    return sorted(idx_rels), sorted(seq_rels)

def scan_relations(entry):
    if "idx_rels" in entry or "seq_rels" in entry:
        return set(entry.get("idx_rels", [])), set(entry.get("seq_rels", []))
    idx_rels, seq_rels = set(), set()
    for step in entry.get("shape", []):
        m = re.match(r"^([^\[]+)\[([^\]]*)\]$", step)
        if not m:
            continue
        node_type, target = m.group(1), m.group(2)
        rel = target.split(":", 1)[0] if ":" in target else target
        if "Index" in node_type and rel:
            idx_rels.add(rel)
        elif node_type == "Seq Scan" and rel:
            seq_rels.add(rel)
    return idx_rels, seq_rels

def snapshot(out, qfile):
    psql(["-c", "ANALYZE"])
    res = {}
    for name, q in queries(qfile):
        raw = psql(["-At", "-c", "EXPLAIN (FORMAT JSON) " + q.strip().rstrip(";")]).stdout
        j = json.loads(raw)[0]["Plan"]
        idx_rels, seq_rels = collect_rels(j)
        res[name] = {
            "shape": shape(j),
            "cost": j["Total Cost"],
            "idx_rels": idx_rels,
            "seq_rels": seq_rels,
        }
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
        b_idx, _ = scan_relations(b[k])
        _, a_seq = scan_relations(a[k])
        degraded = sorted(b_idx & a_seq)
        if degraded:
            notes.append(f"relation(s) {degraded} degraded from index scan to Seq Scan:\n    before {b_shape}\n    after  {a_shape}")
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
