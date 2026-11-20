# Decisions, trade-offs, and what is (not) automated

## Automate vs keep human
| Class | Decision | Why |
|---|---|---|
| Add nullable column, add table, add/drop-if-unused-by-name non-unique index **concurrently**, CHECK/FK `NOT VALID`+`VALIDATE`, new functions/views | **Fully automated** | Metadata-only or non-blocking by construction; the gate proves it dynamically on seeded data. Human review here is slow and inconsistent: the problem we are fixing. |
| Anything the linter flags but the author can justify (`lint:allow Rxxx reason=…`) | **Automated up to prod, then DBRE approval** (`dba-approval` environment) | Staging and canary still run it; a human sees the reason and the dynamic numbers before the blast radius widens. |
| Drop table/column, truncate, type change, rename, SET NOT NULL | **Blocked by default; waiver + approval** | Irreversible or app-breaking; needs expand/contract across releases, which is a design conversation, not a lint fix. |
| Bulk data backfills | **Not in this pipeline** | A migration is one short txn. Backfills run as batched, throttled, resumable jobs (small batches, sleep, replica-lag aware) owned by the service team. |
| Roles, grants, `ALTER SYSTEM`, extensions | **Manual (DBRE)** | Privilege boundary and rds_superuser territory. Linter blocks R017/R018 with no waiver path intended. |
| Parameter group / instance class / failover / restore | **Terraform PR + human** | Not schema changes; different blast radius. |

## Key trade-offs
* **Fail on uncertainty.** Static rules over-block (e.g. `varchar(50)→varchar(100)` is binary-coercible and doesn't rewrite, but R004 still fires). False positives cost a waiver line; false negatives cost an outage. The dynamic check shows the truth, which makes the waiver reviewable.
* **`lock_timeout` is the real safety net, not the linter.** Even a "safe" `ALTER` needs ACCESS EXCLUSIVE momentarily; if it queues behind a long transaction, everyone queues behind *it*. Pipeline sets 3s + exponential retry (5×), so a migration gives up instead of blocking traffic. Authors cannot override it (R010). Role-level defaults on `migrator` backstop manual runs.
* **Stage order by risk, not geography.** Staging → lowest-traffic region → others one at a time, `fail-fast`, shared `concurrency` group so two rollouts can't interleave. Cost: a rollout takes ~(bake × 4); acceptable because schema changes are rarer than deploys. Bake times are tunable per stage.
* **Expand/contract is the contract with backend teams.** Rolling app deploys mean old and new code both run against the new schema; hence R009 (rename) and R015.
* **One migration per transaction, record in the same txn.** No state where DDL applied but not recorded. Exception: CONCURRENTLY, which cannot run in a txn, therefore exactly one statement per file (R002) and no auto-retry (leftover INVALID index; verify.py fails on it).
* **Region skew is allowed mid-rollout, not at rest.** Drift jobs compare each region to golden *at that region's version*.

## Tool choices
| Chosen | Why | Considered & rejected |
|---|---|---|
| **Plain `.sql` files + ~100-line migrator** | Authors write exactly what runs; psql is the same tool humans use in an incident; checksum/ordering/timeout behaviour is explicit and testable | **Flyway/Liquibase**: no native lock_timeout/retry/no-txn-per-file semantics without wrapping; heavier. **Atlas**: excellent declarative diff + lint, but declarative auto-planning is the thing we *don't* want to trust on prod; revisit its linter. **Sqitch**: fine, but Perl dependency and no advantage here. **ORM auto-migrations**: no review surface. |
| **Own linter (stdlib Python)** for the policy + **dynamic check** for ground truth | Rules are ours (tenancy, expand/contract), tests are fixtures, zero dependencies | **Squawk**: active in `pr-checks.yml` (`squawk-cli@2.72.0`) as a blocking second opinion on unwaived new migrations (excluding `require-timeout-settings` and `prefer-robust-stmts`, already covered by `migrate.py`'s timeouts and once-only checksummed migrations) (it uses the real PG parser, mine is regex over masked statements, a known limitation: dynamic SQL in `DO` blocks is invisible). **pgroll/pg-osc/gh-ost-style online tools**: valuable for table rewrites at scale; deliberately out of scope, rewrites are blocked and routed to a human instead. |
| **GitHub Environments + OIDC** | Approval rules and trust policy bind to the *same* environment name; no stored AWS keys | Long-lived IAM keys in secrets; a separate deploy tool (ArgoCD etc.) for something that is 5 shell commands. |
| **IAM DB auth for `migrator`** | No password to leak or rotate; token lives 15 min | Secrets Manager password for the pipeline. Master secret is RDS-managed and readable only by a break-glass role with MFA. |
| **Aurora recovery = PITR + clone, not Backtrack** | Backtrack exists only for Aurora MySQL | See ROLLBACK. |

## Parameter group (non-default) reasoning
`rds.force_ssl=1`; `log_lock_waits=1`; `idle_in_transaction_session_timeout=5min`; `log_min_duration_statement=1s`; `shared_preload_libraries += auto_explain` (+`log_min_duration=3s`). Each ties to a pipeline risk (see comments in `parameters.tf`). Unverified assumption: whether the engine default `shared_preload_libraries` includes entries beyond `pg_stat_statements`; check `describe-engine-default-cluster-parameters` before first apply, because setting this parameter replaces the default.

## Known limitations
Regex-based parsing; seeded data is 300k rows, not production scale (lock-hold numbers are directional); the rewrite check catches only transactional migrations; multi-tenant per-tenant schemas are not handled (shared-schema assumption); demo mode doesn't carry state between stages; `aws`-mode drift job is stubbed.
