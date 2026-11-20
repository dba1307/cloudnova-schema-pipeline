-- irreversible: currency column replaced by multi-currency ledger (ticket DB-1402)
-- lint:allow R003 reason="currency column replaced by multi-currency ledger; verified zero readers in DB-1402"
ALTER TABLE orders DROP COLUMN currency;
