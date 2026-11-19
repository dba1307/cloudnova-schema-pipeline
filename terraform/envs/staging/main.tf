terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
  backend "s3" {}
}

variable "offline" {
  type    = bool
  default = false
}
variable "account_id" {
  type    = string
  default = "111111111111" # placeholder so an offline plan works
}
variable "oidc_provider_arn" {
  type    = string
  default = "arn:aws:iam::111111111111:oidc-provider/token.actions.githubusercontent.com"
}
variable "github_repo" {
  type    = string
  default = "cloudnova/schema-pipeline"
}
variable "alarm_actions" {
  type    = list(string)
  default = []
}
variable "break_glass_principal_arns" {
  type    = list(string)
  default = []
}

provider "aws" {
  region                      = "eu-west-1"
  skip_credentials_validation = var.offline
  skip_requesting_account_id  = var.offline
  skip_metadata_api_check     = var.offline
  access_key                  = var.offline ? "offline" : null
  secret_key                  = var.offline ? "offline" : null
}

module "db_staging" {
  source = "../../modules/db_platform"

  name                       = "cloudnova-staging"
  region                     = "eu-west-1"
  account_id                 = var.account_id
  azs                        = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
  vpc_cidr                   = "10.10.0.0/16"
  instance_class             = "db.r6g.large"
  reader_count               = 1
  deletion_protection        = false
  github_repo                = var.github_repo
  github_environment         = "staging"
  oidc_provider_arn          = var.oidc_provider_arn
  alarm_actions              = var.alarm_actions
  break_glass_principal_arns = var.break_glass_principal_arns
}

output "pipeline_role_arn" { value = module.db_staging.pipeline_role_arn }
