# Rollback and recovery

**Policy: roll forward by default.** A bad migration is usually fixed fastest by a new migration, and a rollback that touches 3 regions is itself a risky change. Rollback exists for the reversible subset.

| Change | Reversible? | Path |
|---|---|---|
| Add table / nullable column / index / NOT VALID constraint | **Yes** | `.down.sql` (rehearsed on every PR: all migrations are taken down and up again) → run **Rollback** workflow (approved environment, shares the rollout lock) |
| Validate constraint | Effectively | no-op down; drop the constraint via 004.down |
| Failed `CREATE INDEX CONCURRENTLY` | Yes, cleanup | `verify.py` fails on INVALID indexes. `DROP INDEX CONCURRENTLY <name>;` then re-run. Never auto-retried |
| **Drop column/table, truncate** | **No** | Prevention: expand/contract (stop reading → stop writing → ship → *later* drop) + DBRE approval + `-- irreversible:` with ticket. Recovery: **Aurora PITR into a new cluster** (or fast clone taken before the stage), copy the data back with a targeted `INSERT … SELECT` via dblink/COPY; do not cut traffic over to the restore for a single table |
| **Type change / rewrite** | **Mostly no** (a reverse rewrite is another long lock) | Don't. Add new column, dual-write, backfill in batches, switch reads, drop later |
| **Destructive data change (UPDATE/DELETE)** | **No** | Blocked in migrations (R012). Backfills snapshot affected rows into a side table first |
| Role/grant/extension | Manual | DBRE |

**Before any waived (irreversible) change reaches prod**, the on-call takes a cluster snapshot or clone and records its identifier in the approval. **Aurora PostgreSQL has no Backtrack**: PITR (14-day retention, `backup_retention_period`) is the safety net, restoring to a *new* cluster. Expect minutes to tens of minutes; practise it quarterly.

**Mid-rollout failure:** `fail-fast` stops later regions. The failed region either rolled back its own transaction (nothing changed; fix and re-run) or finished (alarms/verify failed after): decide roll-forward vs rollback with the migration author, then re-run. Regions ahead of others are *expected* until the rollout completes; drift jobs only compare at equal versions.
