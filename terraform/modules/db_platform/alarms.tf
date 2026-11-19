# Cluster-level signals that a schema change is hurting. Names start with var.name: the pipeline's bake gate lists
# alarms by that prefix (describe-alarms --alarm-name-prefix) and fails the stage if any is in ALARM.
locals {
  alarms = {
    blocked-transactions = { metric = "BlockedTransactions", stat = "Maximum", op = "GreaterThanThreshold", threshold = 5, periods = 3, desc = "Sessions blocked on locks: a migration is queueing" }
    deadlocks            = { metric = "Deadlocks", stat = "Sum", op = "GreaterThanThreshold", threshold = 0, periods = 2, desc = "Deadlocks after a deploy" }
    replica-lag          = { metric = "AuroraReplicaLagMaximum", stat = "Maximum", op = "GreaterThanThreshold", threshold = 2000, periods = 3, desc = "Reader lag (ms): stale reads or heavy writes from backfill" }
    cpu                  = { metric = "CPUUtilization", stat = "Average", op = "GreaterThanThreshold", threshold = 80, periods = 5, desc = "CPU: often a missing index or plan regression" }
    xid-age              = { metric = "MaximumUsedTransactionIDs", stat = "Maximum", op = "GreaterThanThreshold", threshold = 1000000000, periods = 1, desc = "Wraparound risk" }
  }
}

resource "aws_cloudwatch_metric_alarm" "this" {
  for_each            = local.alarms
  alarm_name          = "${var.name}-${each.key}"
  alarm_description   = each.value.desc
  namespace           = "AWS/RDS"
  metric_name         = each.value.metric
  statistic           = each.value.stat
  comparison_operator = each.value.op
  threshold           = each.value.threshold
  period              = 60
  evaluation_periods  = each.value.periods
  treat_missing_data  = "notBreaching"
  dimensions          = { DBClusterIdentifier = aws_rds_cluster.this.cluster_identifier }
  alarm_actions       = var.alarm_actions
}
