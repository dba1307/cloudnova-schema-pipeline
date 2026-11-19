-- expect: R007
-- irreversible: fixture
ALTER TABLE orders ADD CONSTRAINT fk_t FOREIGN KEY (tenant_id) REFERENCES tenants(id);
