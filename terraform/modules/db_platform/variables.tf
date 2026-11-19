variable "name" { type = string } # e.g. cloudnova-prod-euw1; also the CloudWatch alarm prefix
variable "region" { type = string }
variable "account_id" { type = string }
variable "azs" { type = list(string) } # exactly 3
variable "vpc_cidr" { type = string }
variable "engine_version" {
  type    = string
  default = "16.4"
}
variable "parameter_family" {
  type    = string
  default = "aurora-postgresql16"
}
variable "instance_class" {
  type    = string
  default = "db.r6g.large"
}
variable "reader_count" {
  type    = number
  default = 1
  validation {
    condition     = var.reader_count >= 1
    error_message = "At least one reader is required (failover target and read scaling)."
  }
}
variable "deletion_protection" {
  type    = bool
  default = true
}
variable "github_repo" { type = string }        # ORG/REPO allowed to assume the pipeline role
variable "github_environment" { type = string } # the GitHub Environment name bound into the OIDC `sub` claim
variable "oidc_provider_arn" { type = string }
variable "pipeline_db_user" {
  type    = string
  default = "migrator"
}
variable "break_glass_principal_arns" {
  type    = list(string)
  default = []
}
variable "alarm_actions" {
  type    = list(string)
  default = []
}
