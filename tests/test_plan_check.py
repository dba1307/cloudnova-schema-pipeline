#!/usr/bin/env python3
"""Unit tests for tools/plan_check.py (9 scenarios including mixed joins, newly joined lookup tables, and missing queries)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from plan_check import compare

def run():
    # 1. Identical index plan -> pass
    b = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 100.0}}
    a = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 105.0}}
    assert compare(b, a) == 0, "Case 1 failed"

    # 2. Sequential scan replaced by new index -> improvement (pass)
    b = {"q1": {"shape": ["Seq Scan[orders]"], "idx_rels": [], "seq_rels": ["orders"], "cost": 5000.0}}
    a = {"q1": {"shape": ["Index Scan[orders:idx_orders_status]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 12.0}}
    assert compare(b, a) == 0, "Case 2 failed"

    # 3. Index scan on orders degrades to sequential scan on orders -> regression (fail)
    b = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 50.0}}
    a = {"q1": {"shape": ["Seq Scan[orders]"], "idx_rels": [], "seq_rels": ["orders"], "cost": 60.0}}
    assert compare(b, a) == 1, "Case 3 failed"

    # 4. Mixed join: orders keeps index, order_items degrades from Index Scan to Seq Scan -> regression (fail)
    b = {"q_join": {"shape": ["Nested Loop", "Index Scan[orders:idx_orders_tenant]", "Index Scan[order_items:idx_items_order]"], "idx_rels": ["orders", "order_items"], "seq_rels": [], "cost": 120.0}}
    a = {"q_join": {"shape": ["Hash Join", "Index Scan[orders:idx_orders_tenant]", "Seq Scan[order_items]"], "idx_rels": ["orders"], "seq_rels": ["order_items"], "cost": 140.0}}
    assert compare(b, a) == 1, "Case 4 failed"

    # 5. Newly joined small lookup table uses Seq Scan while orders keeps its index -> NOT a regression (pass)
    b = {"q_lookup": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 100.0}}
    a = {"q_lookup": {"shape": ["Hash Join", "Index Scan[orders:idx_orders_tenant]", "Seq Scan[currencies]"], "idx_rels": ["orders"], "seq_rels": ["currencies"], "cost": 105.0}}
    assert compare(b, a) == 0, "Case 5 failed: newly joined small lookup table must not trigger false regression"

    # 6. Mixed join where Seq Scan already existed before -> pass
    b = {"q_join": {"shape": ["Hash Join", "Index Scan[orders:idx_orders_tenant]", "Seq Scan[tenants]"], "idx_rels": ["orders"], "seq_rels": ["tenants"], "cost": 120.0}}
    a = {"q_join": {"shape": ["Hash Join", "Index Only Scan[orders:idx_orders_tenant]", "Seq Scan[tenants]"], "idx_rels": ["orders"], "seq_rels": ["tenants"], "cost": 110.0}}
    assert compare(b, a) == 0, "Case 6 failed"

    # 7. Cost grows beyond 1.5x threshold even on same index -> regression (fail)
    b = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 100.0}}
    a = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 160.0}}
    assert compare(b, a) == 1, "Case 7 failed"

    # 8. Cost grows within 1.5x threshold -> pass
    b = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 100.0}}
    a = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 149.0}}
    assert compare(b, a) == 0, "Case 8 failed"

    # 9. Query missing from after snapshot -> regression (fail)
    b = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 100.0}, "q2": {"shape": ["Index Scan[b:idx_b]"], "idx_rels": ["b"], "seq_rels": [], "cost": 50.0}}
    a = {"q1": {"shape": ["Index Scan[orders:idx_orders_tenant]"], "idx_rels": ["orders"], "seq_rels": [], "cost": 100.0}}
    assert compare(b, a) == 1, "Case 9 failed"

    print("PASS all 9 plan_check unit test cases")

if __name__ == "__main__":
    run()
