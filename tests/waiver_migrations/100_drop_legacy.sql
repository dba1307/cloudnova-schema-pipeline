-- irreversible: legacy column, data archived to S3 on 2026-11-01 (ticket DB-1234)
-- lint:allow R003 reason="column unused since release 4.12; archived; see DB-1234"
ALTER TABLE orders DROP COLUMN legacy_ref;
