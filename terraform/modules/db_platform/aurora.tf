resource "aws_kms_key" "db" {
  description             = "${var.name} storage, Performance Insights and master-secret encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_rds_cluster" "this" {
  cluster_identifier = var.name
  engine             = "aurora-postgresql"
  engine_version     = var.engine_version
  database_name      = "cloudnova"

  master_username               = "dbadmin"
  manage_master_user_password   = true # RDS creates and rotates the secret in Secrets Manager; it never enters Terraform state
  master_user_secret_kms_key_id = aws_kms_key.db.arn

  iam_database_authentication_enabled = true # the pipeline logs in with a 15-min IAM token: no stored DB password
  storage_encrypted                   = true
  kms_key_id                          = aws_kms_key.db.arn

  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.this.name

  backup_retention_period         = 14 # PITR window: the recovery path for irreversible changes
  preferred_backup_window         = "02:00-03:00"
  copy_tags_to_snapshot           = true
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = !var.deletion_protection
  final_snapshot_identifier       = var.deletion_protection ? "${var.name}-final" : null
  enabled_cloudwatch_logs_exports = ["postgresql"]
  apply_immediately               = false

}

resource "aws_iam_role" "monitoring" {
  name_prefix        = "${var.name}-rds-mon-"
  assume_role_policy = data.aws_iam_policy_document.monitoring_trust.json
}
data "aws_iam_policy_document" "monitoring_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
  }
}
resource "aws_iam_role_policy_attachment" "monitoring" {
  role       = aws_iam_role.monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Aurora elects the writer; promotion_tier 0 prefers the first instance, the rest are failover targets and readers.
resource "aws_rds_cluster_instance" "this" {
  count                                 = 1 + var.reader_count
  identifier                            = "${var.name}-${count.index}"
  cluster_identifier                    = aws_rds_cluster.this.id
  engine                                = aws_rds_cluster.this.engine
  engine_version                        = aws_rds_cluster.this.engine_version
  instance_class                        = var.instance_class
  promotion_tier                        = count.index
  availability_zone                     = var.azs[count.index % 3]
  db_subnet_group_name                  = aws_db_subnet_group.this.name
  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.db.arn
  performance_insights_retention_period = 31
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.monitoring.arn
  auto_minor_version_upgrade            = true
}
