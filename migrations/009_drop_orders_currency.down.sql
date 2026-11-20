-- Schema-only rollback: re-adds an empty column; dropped data can only be restored from the pre-change Aurora snapshot / PITR (see docs/ROLLBACK.md).
ALTER TABLE orders ADD COLUMN currency text;
