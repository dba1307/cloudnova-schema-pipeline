#!/usr/bin/env python3
"""Unit tests for tools/plan_check.py (8 scenarios including mixed join regressions and missing queries)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from plan_check import compare

def run():
    # 1. Identical index plan -> pass
    b = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 100.0}}
    a = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 105.0}}
    assert compare(b, a) == 0, "Case 1 failed: identical plan should pass"

    # 2. Sequential scan replaced by new index -> improvement (pass)
    b = {"q1": {"shape": ["Seq Scan[orders]"], "cost": 5000.0}}
    a = {"q1": {"shape": ["Index Scan[idx_orders_status]"], "cost": 12.0}}
    assert compare(b, a) == 0, "Case 2 failed: index addition improvement should pass"

    # 3. Index scan degrades to sequential scan -> regression (fail)
    b = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 50.0}}
    a = {"q1": {"shape": ["Seq Scan[orders]"], "cost": 60.0}}
    assert compare(b, a) == 1, "Case 3 failed: Index -> Seq Scan must fail"

    # 4. Mixed join: one table keeps index, second table degrades from Index Scan to Seq Scan -> regression (fail)
    b = {"q_join": {"shape": ["Nested Loop", "Index Scan[idx_orders_tenant]", "Index Scan[idx_items_order]"], "cost": 120.0}}
    a = {"q_join": {"shape": ["Hash Join", "Index Scan[idx_orders_tenant]", "Seq Scan[order_items]"], "cost": 140.0}}
    assert compare(b, a) == 1, "Case 4 failed: mixed join with new Seq Scan must fail"

    # 5. Mixed join where Seq Scan already existed before -> no new Seq Scan -> pass
    b = {"q_join": {"shape": ["Hash Join", "Index Scan[idx_orders_tenant]", "Seq Scan[tenants]"], "cost": 120.0}}
    a = {"q_join": {"shape": ["Hash Join", "Index Only Scan[idx_orders_tenant]", "Seq Scan[tenants]"], "cost": 110.0}}
    assert compare(b, a) == 0, "Case 5 failed: pre-existing Seq Scan with index upgrade should pass"

    # 6. Cost grows beyond 1.5x threshold even on same index -> regression (fail)
    b = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 100.0}}
    a = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 160.0}}
    assert compare(b, a) == 1, "Case 6 failed: >1.5x cost growth must fail"

    # 7. Cost grows within 1.5x threshold -> pass
    b = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 100.0}}
    a = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 149.0}}
    assert compare(b, a) == 0, "Case 7 failed: <=1.5x cost growth should pass"

    # 8. Query missing from after snapshot -> regression (fail)
    b = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 100.0}, "q2": {"shape": ["Index Scan[idx_b]"], "cost": 50.0}}
    a = {"q1": {"shape": ["Index Scan[idx_orders_tenant]"], "cost": 100.0}}
    assert compare(b, a) == 1, "Case 8 failed: missing query in after snapshot must fail"

    print("PASS all 8 plan_check unit test cases")

if __name__ == "__main__":
    run()
