#!/usr/bin/env python3
"""Proves the gate works: good migrations pass, each bad fixture is blocked by the rule it names."""
import glob, os, re, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import lint_migration as L
root = os.path.join(os.path.dirname(__file__), "..")
fails = 0
def check(ok, msg):
    global fails; print(("PASS " if ok else "FAIL ") + msg); fails += (not ok)
assert L.main([os.path.join(root, "migrations")]) == 0, "real migrations must pass"
check(True, "migrations/ pass the linter (allowed)")
for p in sorted(glob.glob(os.path.join(root, "tests/bad_migrations/*.sql"))):
    want = re.search(r"expect:\s*(R\d+)", open(p).read()).group(1)
    f = L.lint_text(p, open(p).read(), has_down=False)
    check(any(x.rule == want and not x.waived for x in f), f"{os.path.basename(p)} blocked by {want}")
w = L.lint_text("w.sql", open(os.path.join(root, "tests/waiver_migrations/100_drop_legacy.sql")).read(), False)
check(w and all(x.waived for x in w), "waived destructive change passes lint but is flagged needs_approval")
# splitter edge cases: strings, comments and function bodies must not trigger rules
t = "-- DROP TABLE x;\nSELECT 'DROP TABLE y';\nCREATE FUNCTION f() RETURNS int AS $$ BEGIN DELETE FROM z; RETURN 1; END $$ LANGUAGE plpgsql;"
check(not L.lint_text("s.sql", t + "\n-- irreversible: test", False), "comments/strings/$$ bodies are masked")
check(not L.lint_text("c.sql", "CREATE TABLE n(a int); ALTER TABLE n ADD COLUMN b int NOT NULL; CREATE INDEX i ON n(a);\n-- irreversible: new table", False), "objects created in the same file are exempt")
sys.exit(1 if fails else 0)
