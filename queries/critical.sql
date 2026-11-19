-- Hot-path queries whose plans must not regress. Owned by the backend teams; add yours in the same PR as the schema change.
-- name: orders_by_tenant_recent
SELECT * FROM orders WHERE tenant_id = 42 ORDER BY created_at DESC LIMIT 50;
-- name: orders_status_count
SELECT status, count(*) FROM orders WHERE tenant_id = 42 GROUP BY status;
-- name: tenant_lookup
SELECT * FROM tenants WHERE slug = 'tenant-42';
