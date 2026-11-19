-- expect: R004
-- irreversible: fixture
ALTER TABLE orders ALTER COLUMN total_cents TYPE numeric(20,2);
