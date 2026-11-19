output "cluster_endpoint" { value = aws_rds_cluster.this.endpoint }
output "reader_endpoint" { value = aws_rds_cluster.this.reader_endpoint }
output "cluster_resource_id" { value = aws_rds_cluster.this.cluster_resource_id }
output "master_secret_arn" { value = aws_rds_cluster.this.master_user_secret[0].secret_arn }
output "pipeline_role_arn" { value = aws_iam_role.pipeline.arn }
output "pipeline_security_group" { value = aws_security_group.pipeline.id }
output "alarm_prefix" { value = var.name }
