-- migrate:no-transaction
DROP INDEX CONCURRENTLY IF EXISTS idx_orders_external_ref;
