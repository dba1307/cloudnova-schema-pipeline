terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
  backend "s3" {} # partial config supplied at init time; CI plans use -backend=false
}

variable "offline" {
  type    = bool
  default = false
}

provider "aws" {
  region                      = "eu-west-1"
  skip_credentials_validation = var.offline
  skip_requesting_account_id  = var.offline
  skip_metadata_api_check     = var.offline
  access_key                  = var.offline ? "offline" : null
  secret_key                  = var.offline ? "offline" : null
}

# One GitHub OIDC provider per AWS account. Thumbprints are kept for older provider behaviour; AWS validates the chain itself.
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1", "1c58a3a8518e8759bf075b76b750d4f2df264fcd"]
}

output "oidc_provider_arn" { value = aws_iam_openid_connect_provider.github.arn }
