-- migrate:no-transaction
-- migrate:statement-timeout=30min
-- ALLOW: concurrent index build, single statement, runs outside a transaction.
CREATE INDEX CONCURRENTLY idx_orders_tenant_created ON orders (tenant_id, created_at);
