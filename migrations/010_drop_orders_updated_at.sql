-- lint:allow R003 reason="updated_at replaced by event audit log; verified zero readers in DB-1405"
ALTER TABLE orders DROP COLUMN updated_at;
