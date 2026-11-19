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
  alias                       = "euw1"
  region                      = "eu-west-1"
  skip_credentials_validation = var.offline
  skip_requesting_account_id  = var.offline
  skip_metadata_api_check     = var.offline
  access_key                  = var.offline ? "offline" : null
  secret_key                  = var.offline ? "offline" : null
}

provider "aws" {
  alias                       = "use1"
  region                      = "us-east-1"
  skip_credentials_validation = var.offline
  skip_requesting_account_id  = var.offline
  skip_metadata_api_check     = var.offline
  access_key                  = var.offline ? "offline" : null
  secret_key                  = var.offline ? "offline" : null
}

provider "aws" {
  alias                       = "apse1"
  region                      = "ap-southeast-1"
  skip_credentials_validation = var.offline
  skip_requesting_account_id  = var.offline
  skip_metadata_api_check     = var.offline
  access_key                  = var.offline ? "offline" : null
  secret_key                  = var.offline ? "offline" : null
}

# production-canary = lowest-traffic region; it receives every change first
module "db_euw1" {
  source                     = "../../modules/db_platform"
  providers                  = { aws = aws.euw1 }
  name                       = "cloudnova-prod-euw1"
  region                     = "eu-west-1"
  account_id                 = var.account_id
  azs                        = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
  vpc_cidr                   = "10.20.0.0/16"
  instance_class             = "db.r6g.2xlarge"
  reader_count               = 2
  deletion_protection        = true
  github_repo                = var.github_repo
  github_environment         = "production-canary"
  oidc_provider_arn          = var.oidc_provider_arn
  alarm_actions              = var.alarm_actions
  break_glass_principal_arns = var.break_glass_principal_arns
}

module "db_use1" {
  source                     = "../../modules/db_platform"
  providers                  = { aws = aws.use1 }
  name                       = "cloudnova-prod-use1"
  region                     = "us-east-1"
  account_id                 = var.account_id
  azs                        = ["us-east-1a", "us-east-1b", "us-east-1c"]
  vpc_cidr                   = "10.21.0.0/16"
  instance_class             = "db.r6g.2xlarge"
  reader_count               = 2
  deletion_protection        = true
  github_repo                = var.github_repo
  github_environment         = "production-us-east-1"
  oidc_provider_arn          = var.oidc_provider_arn
  alarm_actions              = var.alarm_actions
  break_glass_principal_arns = var.break_glass_principal_arns
}

module "db_apse1" {
  source                     = "../../modules/db_platform"
  providers                  = { aws = aws.apse1 }
  name                       = "cloudnova-prod-apse1"
  region                     = "ap-southeast-1"
  account_id                 = var.account_id
  azs                        = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
  vpc_cidr                   = "10.22.0.0/16"
  instance_class             = "db.r6g.2xlarge"
  reader_count               = 2
  deletion_protection        = true
  github_repo                = var.github_repo
  github_environment         = "production-ap-southeast-1"
  oidc_provider_arn          = var.oidc_provider_arn
  alarm_actions              = var.alarm_actions
  break_glass_principal_arns = var.break_glass_principal_arns
}

output "pipeline_roles" {
  value = {
    euw1  = module.db_euw1.pipeline_role_arn
    use1  = module.db_use1.pipeline_role_arn
    apse1 = module.db_apse1.pipeline_role_arn
  }
}
