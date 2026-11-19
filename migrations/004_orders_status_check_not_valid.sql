-- ALLOW: expand step. NOT VALID skips the table scan; only new writes are checked.
ALTER TABLE orders ADD CONSTRAINT orders_status_chk CHECK (status IN ('new','paid','shipped','cancelled')) NOT VALID;
