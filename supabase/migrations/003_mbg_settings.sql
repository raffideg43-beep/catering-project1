-- 003_mbg_settings.sql
-- MBG allocation settings per tenant

CREATE TABLE IF NOT EXISTS mbg_allocation_settings (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  price_per_portion   DECIMAL(15,2) DEFAULT 15000,
  food_per_portion    DECIMAL(15,2) DEFAULT 10000,
  labor_per_portion   DECIMAL(15,2) DEFAULT 2250,
  ops_per_portion     DECIMAL(15,2) DEFAULT 2750,
  effective_date      DATE DEFAULT CURRENT_DATE,
  notes               TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mbg_allocation_settings_tenant_id ON mbg_allocation_settings(tenant_id);


