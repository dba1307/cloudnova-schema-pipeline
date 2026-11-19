# --- Pipeline identity: GitHub OIDC -> IAM role -> rds-db:connect as the least-privileged DB user -------------------
data "aws_iam_policy_document" "pipeline_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition { # only THIS repo, only THIS GitHub Environment (so only after that environment's approval rules passed)
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "pipeline" {
  name                 = "${var.name}-schema-pipeline"
  assume_role_policy   = data.aws_iam_policy_document.pipeline_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "pipeline" {
  statement {
    sid       = "ConnectAsMigratorOnly"
    actions   = ["rds-db:connect"]
    resources = ["arn:aws:rds-db:${var.region}:${var.account_id}:dbuser:${aws_rds_cluster.this.cluster_resource_id}/${var.pipeline_db_user}"]
  }
  statement {
    sid       = "PreChangeClusterSnapshot"
    actions   = ["rds:CreateDBClusterSnapshot", "rds:DescribeDBClusterSnapshots"]
    resources = [
      aws_rds_cluster.this.arn,
      "arn:aws:rds:${var.region}:${var.account_id}:cluster-snapshot:${aws_rds_cluster.this.cluster_identifier}-pre-*"
    ]
  }
  statement {
    sid       = "ReadAlarmsForBakeGate"
    actions   = ["cloudwatch:DescribeAlarms"] # does not support resource-level permissions
    resources = ["*"]
  }
  # Deliberately absent: secretsmanager:GetSecretValue on the master secret, kms:*, rds:Modify*, ec2:*.
}

resource "aws_iam_role_policy" "pipeline" {
  role   = aws_iam_role.pipeline.id
  policy = data.aws_iam_policy_document.pipeline.json
}

# --- Break-glass: the ONLY path to the master credential, for humans, and only when someone is paged ------------------
data "aws_iam_policy_document" "break_glass_trust" {
  count = length(var.break_glass_principal_arns) > 0 ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = var.break_glass_principal_arns
    }
    condition {
      test     = "Bool"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["true"]
    }
  }
}

resource "aws_iam_role" "break_glass" {
  count              = length(var.break_glass_principal_arns) > 0 ? 1 : 0
  name               = "${var.name}-break-glass"
  assume_role_policy = data.aws_iam_policy_document.break_glass_trust[0].json
}

data "aws_iam_policy_document" "break_glass" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_rds_cluster.this.master_user_secret[0].secret_arn]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.db.arn]
  }
}

resource "aws_iam_role_policy" "break_glass" {
  count  = length(var.break_glass_principal_arns) > 0 ? 1 : 0
  role   = aws_iam_role.break_glass[0].id
  policy = data.aws_iam_policy_document.break_glass.json
}
