-- Seeds enough rows that a table rewrite or index build is measurable in CI. Idempotent; no-op if tables are absent.
DO $$ BEGIN
  IF to_regclass('public.orders') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM tenants) THEN
    INSERT INTO tenants(slug) SELECT 'tenant-'||g FROM generate_series(1,100) g;
    INSERT INTO orders(tenant_id,status,total_cents,created_at)
      SELECT 1+(g%100), (ARRAY['new','paid','shipped','cancelled'])[1+(g%4)], g%10000, now()-(g||' seconds')::interval FROM generate_series(1,300000) g;
  END IF; END $$;
