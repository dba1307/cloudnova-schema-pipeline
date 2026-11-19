#!/usr/bin/env python3
"""Unit tests for migrate.py, fingerprint.py, verify.py, and dynamic_check.py."""
import os, subprocess, sys, tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import migrate, fingerprint, verify, dynamic_check

def test_migrate():
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "001_init.sql"), "w").write("CREATE TABLE t(id int);")
        open(os.path.join(d, "001_init.down.sql"), "w").write("DROP TABLE t;")
        open(os.path.join(d, "002_idx.sql"), "w").write("-- migrate:no-transaction\n-- migrate:statement-timeout=45min\nCREATE INDEX CONCURRENTLY idx_t ON t(id);")
        items = migrate.local(d)
        assert tuple(x["version"] for x in items) == (1, 2), f"Unexpected versions: {items}"
        first, second = items
        assert migrate.opts(first)["statement_timeout"] == "5min"
        assert migrate.opts(second)["statement_timeout"] == "45min"

        # Duplicate version number must exit non-zero
        open(os.path.join(d, "002_dup.sql"), "w").write("SELECT 1;")
        try:
            migrate.local(d)
            assert False, "Expected duplicate version exit"
        except SystemExit as e:
            assert "duplicate migration version" in str(e)
    print("PASS migrate.py unit tests")

def test_fingerprint():
    base = {k: [] for k in fingerprint.Q}
    base["columns"] = list(("orders.id bigint NOT NULL", "orders.status text"))
    base["indexes"] = list(("CREATE INDEX idx_orders_status ON public.orders USING btree (status)",))
    base["_hash"] = "aaaa1111bbbb2222"

    same = {k: list(v) if isinstance(v, list) else v for k, v in base.items()}
    assert fingerprint.compare(base, same, "golden", "live") is False, "Identical fingerprints should return False"

    drifted = {k: list(v) if isinstance(v, list) else v for k, v in base.items()}
    drifted["columns"].append("orders.hotfix_flag integer")
    drifted["_hash"] = "cccc3333dddd4444"
    assert fingerprint.compare(base, drifted, "golden", "live") is True, "Drifted column should return True"
    print("PASS fingerprint.py unit tests")

def test_verify():
    # Healthy database
    with patch.object(verify, "scalar", side_effect=("1", "f")), patch.object(verify, "rows", side_effect=((), ())):
        assert verify.once(2000) == []

    # INVALID index + lock waiter + high Aurora replica lag
    with patch.object(verify, "scalar", side_effect=("1", "t", "4500")), \
         patch.object(verify, "rows", side_effect=((("idx_broken",),), (("12345", "00:00:15"),))):
        errs = verify.once(2000)
        assert len(errs) == 3, f"Expected 3 errors, got: {errs}"
        e0, e1, e2 = errs
        assert "INVALID indexes" in e0
        assert "waiting on locks" in e1
        assert "replica lag 4500 ms > 2000" in e2
    print("PASS verify.py unit tests")

def test_dynamic_check():
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as tf:
        tf.write("ALTER TABLE orders ADD COLUMN note text;")
        path = tf.name
    try:
        # 1. Clean migration: 12ms, no rewrite
        fake_ok = subprocess.CompletedProcess((), 0, stdout="DYN_MS 12\nDYN_AEL orders\n", stderr="")
        with patch.object(dynamic_check, "psql", return_value=fake_ok):
            assert dynamic_check.check(path, 1500) == []

        # 2. Table rewrite detected via relfilenode change
        fake_rw = subprocess.CompletedProcess((), 0, stdout="DYN_MS 45\nDYN_REWRITE orders\nDYN_AEL orders\n", stderr="")
        with patch.object(dynamic_check, "psql", return_value=fake_rw):
            errs = dynamic_check.check(path, 1500)
            assert len(errs) == 1 and "TABLE REWRITE detected" in errs.pop()

        # 3. Lock hold exceeds budget
        fake_slow = subprocess.CompletedProcess((), 0, stdout="DYN_MS 2200\nDYN_AEL orders\n", stderr="")
        with patch.object(dynamic_check, "psql", return_value=fake_slow):
            errs = dynamic_check.check(path, 1500)
            assert len(errs) == 1 and "held ACCESS EXCLUSIVE ~2200 ms" in errs.pop()
    finally:
        os.unlink(path)
    print("PASS dynamic_check.py unit tests")

if __name__ == "__main__":
    test_migrate()
    test_fingerprint()
    test_verify()
    test_dynamic_check()
