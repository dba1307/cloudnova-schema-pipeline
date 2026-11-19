-- expect: R002
-- irreversible: fixture
CREATE INDEX CONCURRENTLY idx_x ON orders (status);
