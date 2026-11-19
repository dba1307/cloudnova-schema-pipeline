-- migrate:no-transaction
DROP INDEX CONCURRENTLY IF EXISTS idx_orders_tenant_created;
