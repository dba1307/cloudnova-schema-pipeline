-- ALLOW: nullable column, no default => catalog-only change, ACCESS EXCLUSIVE held for milliseconds.
ALTER TABLE orders ADD COLUMN notes text;
