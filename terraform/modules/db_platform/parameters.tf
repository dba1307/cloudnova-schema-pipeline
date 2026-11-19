# Non-default parameters. Each one earns its place by serving the migration pipeline or its safety net.
resource "aws_rds_cluster_parameter_group" "this" {
  name_prefix = "${var.name}-"
  family      = var.parameter_family
  description = "CloudNova ${var.name}"

  # 1. Credentials and migration traffic are never sent in clear text. Dynamic, immediate.
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  # 2. Lock waits longer than deadlock_timeout (1s) get logged with the blocking statement. This is the primary
  #    forensic evidence when a migration queues behind a long transaction and starts blocking app traffic.
  parameter {
    name  = "log_lock_waits"
    value = "1"
  }
  # 3. Idle-in-transaction sessions hold locks and old snapshots; a migration's lock request queues behind them and
  #    then blocks everyone behind IT. 5 min reaps leaks without killing legitimate transactions. (ms)
  parameter {
    name  = "idle_in_transaction_session_timeout"
    value = "300000"
  }
  # 4. Slow-statement log: the cheap, always-on signal for post-deploy regressions (queries slower than 1s). (ms)
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }
  # 5. Plan-regression forensics in production: pg_stat_statements for per-query trends, auto_explain to capture the
  #    actual plan of slow queries. Static: applied on next reboot (Terraform marks pending-reboot).
  #    CHECK the engine default first: aws rds describe-engine-default-cluster-parameters --db-parameter-group-family <family>
  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements,auto_explain"
    apply_method = "pending-reboot"
  }
  parameter {
    name  = "auto_explain.log_min_duration"
    value = "3000"
  }
}
