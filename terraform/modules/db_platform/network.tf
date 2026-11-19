# Private-only network. No internet gateway, no NAT: the database has no route to or from the internet.
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = var.name }
}

resource "aws_subnet" "db" {
  count             = 3
  vpc_id            = aws_vpc.this.id
  availability_zone = var.azs[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index)
  tags              = { Name = "${var.name}-db-${count.index}" }
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = aws_subnet.db[*].id
}

# Two source security groups are the ONLY things allowed to reach 5432.
resource "aws_security_group" "app" {
  name_prefix = "${var.name}-app-"
  description = "Application tier (attach to app workloads)"
  vpc_id      = aws_vpc.this.id
}

resource "aws_security_group" "pipeline" {
  name_prefix = "${var.name}-pipeline-"
  description = "VPC-attached GitHub runners that execute migrations"
  vpc_id      = aws_vpc.this.id
}

resource "aws_security_group" "db" {
  name_prefix = "${var.name}-db-"
  description = "Aurora: 5432 from app and pipeline SGs only; no egress"
  vpc_id      = aws_vpc.this.id
}

resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "db_from_pipeline" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = aws_security_group.pipeline.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}
