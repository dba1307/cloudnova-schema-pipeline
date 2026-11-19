-- expect: R001
-- irreversible: fixture
CREATE INDEX idx_orders_status ON orders (status);
