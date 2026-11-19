-- expect: R005
-- irreversible: fixture
ALTER TABLE orders ADD COLUMN ref uuid DEFAULT gen_random_uuid();
