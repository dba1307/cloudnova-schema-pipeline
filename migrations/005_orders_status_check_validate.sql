-- ALLOW: VALIDATE takes SHARE UPDATE EXCLUSIVE (reads and writes continue). Second half of the safe constraint pattern.
ALTER TABLE orders VALIDATE CONSTRAINT orders_status_chk;
