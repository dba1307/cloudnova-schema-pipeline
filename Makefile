.PHONY: test lint db demo demo-block tf-plan down

export PGHOST ?= localhost
export PGPORT ?= 5432
export PGDATABASE ?= cloudnova
export PGUSER ?= postgres
export PGPASSWORD ?= postgres

test lint:   ## no database needed: gate self-test (good passes, 11 bad fixtures blocked, waiver, parser edge cases)
	python3 tests/test_lint.py
	python3 tests/test_plan_check.py
	python3 tests/test_tools.py

db:          ## start Postgres 16
	docker compose up -d --wait

demo: db     ## full local rehearsal: apply, verify, drift, rollback, plan-regression
	python3 tools/migrate.py up && psql -X -f db/seed_ci.sql
	python3 tools/verify.py
	python3 tools/plan_check.py snapshot /tmp/plans_before.json
	python3 tools/fingerprint.py dump > /tmp/live.json && python3 tools/fingerprint.py compare /tmp/live.json /tmp/live.json
	python3 tools/migrate.py down --steps 99 && python3 tools/migrate.py up
	python3 tools/plan_check.py snapshot /tmp/plans_after.json && python3 tools/plan_check.py compare /tmp/plans_before.json /tmp/plans_after.json

demo-block:  ## watch the gate refuse a dangerous migration
	python3 tools/lint_migration.py tests/bad_migrations || true

down:
	docker compose down -v

tf-plan:     ## generate offline Terraform plans for staging, prod, and global
	@for env in staging prod global; do \
		echo "=== Planning $$env ==="; \
		( \
			cd terraform/envs/$$env && \
			printf 'terraform {\n  backend "local" {}\n}\n' > backend_override.tf && \
			terraform init -reconfigure -input=false >/dev/null && \
			terraform plan -var offline=true -no-color > ../../../$${env}_plan.txt && \
			rm -f backend_override.tf terraform.tfstate* \
		) || exit 1; \
	done
	@echo "Generated staging_plan.txt, prod_plan.txt, and global_plan.txt"
