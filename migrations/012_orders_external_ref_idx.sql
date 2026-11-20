-- migrate:no-transaction
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_external_ref ON orders (external_ref);
