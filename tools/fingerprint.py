#!/usr/bin/env python3
"""Normalised schema fingerprint for drift detection.  dump | compare A.json B.json
Excludes owners, OIDs, attnum order, data and schema_migrations rows, so a Postgres container and Aurora compare equal."""
import json, os, sys, difflib, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from pgutil import rows

Q = {
 "columns": """SELECT c.relname||'.'||a.attname||' '||format_type(a.atttypid,a.atttypmod)||CASE WHEN a.attnotnull THEN ' NOT NULL' ELSE '' END
   ||COALESCE(' DEFAULT '||pg_get_expr(d.adbin,d.adrelid),'')||CASE WHEN a.attidentity<>'' THEN ' IDENTITY '||a.attidentity::text ELSE '' END
   ||CASE WHEN a.attgenerated<>'' THEN ' GENERATED' ELSE '' END
   FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
   LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
   WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped""",
 "constraints": """SELECT conrelid::regclass||' '||conname||' '||pg_get_constraintdef(oid)||CASE WHEN convalidated THEN '' ELSE ' [NOT VALIDATED]' END
   FROM pg_constraint WHERE connamespace='public'::regnamespace""",
 "indexes": """SELECT i.indexdef||CASE WHEN x.indisvalid THEN '' ELSE ' [INVALID]' END FROM pg_indexes i
   JOIN pg_class c ON c.relname=i.indexname AND c.relnamespace='public'::regnamespace JOIN pg_index x ON x.indexrelid=c.oid WHERE i.schemaname='public'""",
 "triggers": "SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace)",
 "functions": "SELECT pg_get_functiondef(p.oid) FROM pg_proc p WHERE p.pronamespace='public'::regnamespace AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=p.oid AND d.deptype='e')",
 "views": "SELECT viewname||' '||definition FROM pg_views WHERE schemaname='public'",
 "versions": "SELECT version||' '||checksum FROM public.schema_migrations",
}

def dump(): 
    fp = {k: sorted(" ".join(r[0].split()) for r in rows(q)) for k, q in Q.items()}
    fp["_hash"] = hashlib.sha256(json.dumps({k: v for k, v in fp.items()}, sort_keys=True).encode()).hexdigest()[:16]; return fp

def compare(a, b, an, bn):
    drift = False
    for k in Q:
        if a[k] != b[k]:
            drift = True; print(f"DRIFT in {k}:")
            for l in difflib.unified_diff(a[k], b[k], an, bn, lineterm="", n=0):
                if not l.startswith(("---", "+++", "@@")): print("  " + l)
    print(f"{an}={a['_hash']} {bn}={b['_hash']} -> {'DRIFT' if drift else 'identical'}"); return drift

if __name__ == "__main__":
    if sys.argv[1] == "dump": print(json.dumps(dump(), indent=1))
    else: sys.exit(1 if compare(json.load(open(sys.argv[2])), json.load(open(sys.argv[3])), sys.argv[2], sys.argv[3]) else 0)
