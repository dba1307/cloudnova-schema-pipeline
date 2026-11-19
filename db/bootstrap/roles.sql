-- Run ONCE per cluster by a break-glass admin (never by the pipeline). Creates the pipeline's least-privilege role.
-- migrator: owns app objects so it can ALTER them; NOT superuser/rds_superuser, cannot create roles/DBs, cannot read the master secret.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='migrator') THEN
    CREATE ROLE migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='app_runtime') THEN CREATE ROLE app_runtime NOLOGIN; END IF;
  IF EXISTS (SELECT FROM pg_roles WHERE rolname='rds_iam') THEN EXECUTE 'GRANT rds_iam TO migrator'; END IF;  -- IAM auth on Aurora: no password exists
END $$;
-- Backstop timeouts at role level: apply even if someone runs psql as migrator by hand.
ALTER ROLE migrator SET lock_timeout='3s';
ALTER ROLE migrator SET statement_timeout='5min';
ALTER ROLE migrator SET idle_in_transaction_session_timeout='60s';
GRANT pg_monitor TO migrator;  -- read-only visibility for verify.py (pg_stat_activity, pg_stat_statements)
GRANT CONNECT ON DATABASE cloudnova TO migrator;
GRANT USAGE, CREATE ON SCHEMA public TO migrator;
GRANT USAGE ON SCHEMA public TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;
