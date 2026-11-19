-- irreversible: notes column unused after application cutover (ticket DB-1235)
-- lint:allow R003 reason="column unused after application cutover; see DB-1235"
ALTER TABLE orders DROP COLUMN notes;
