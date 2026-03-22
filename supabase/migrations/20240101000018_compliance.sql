-- ============================================================
-- Modul 19: Compliance, Anggaran & Audit Trail
-- Jalankan manual di Supabase SQL Editor
-- ============================================================

-- Pagu anggaran per bulan
CREATE TABLE IF NOT EXISTS budget_allocations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
  year            INTEGER NOT NULL,
  month           INTEGER NOT NULL,
  pagu_amount     DECIMAL(15,2) NOT NULL,
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, year, month)
);

-- Pencairan dana dari pemerintah (bisa berkali-kali per bulan)
CREATE TABLE IF NOT EXISTS fund_disbursements (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID REFERENCES tenants(id) ON DELETE CASCADE,
  year              INTEGER NOT NULL,
  month             INTEGER NOT NULL,
  disbursement_date DATE NOT NULL,
  amount            DECIMAL(15,2) NOT NULL,
  reference_number  TEXT,
  notes             TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Kas accounts (VA Bank + Kas Kecil)
CREATE TABLE IF NOT EXISTS kas_accounts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  type            TEXT NOT NULL,          -- va_bank / kas_kecil / rekening_lain
  current_balance DECIMAL(15,2) DEFAULT 0,
  is_active       BOOLEAN DEFAULT true,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, name)
);

-- Pemindahan dana antar kas
CREATE TABLE IF NOT EXISTS fund_transfers (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
  from_account_id UUID REFERENCES kas_accounts(id),
  to_account_id   UUID REFERENCES kas_accounts(id),
  amount          DECIMAL(15,2) NOT NULL,
  transfer_date   DATE NOT NULL,
  notes           TEXT,
  created_by      UUID REFERENCES users(id),
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Pengembalian sisa dana ke kas negara
CREATE TABLE IF NOT EXISTS fund_returns (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID REFERENCES tenants(id) ON DELETE CASCADE,
  year              INTEGER NOT NULL,
  month             INTEGER NOT NULL,
  amount            DECIMAL(15,2) NOT NULL,
  return_date       DATE NOT NULL,
  reference_number  TEXT,
  notes             TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, year, month)
);

-- Custom beneficiary types per tenant
CREATE TABLE IF NOT EXISTS beneficiary_types (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  description TEXT,
  sort_order  INTEGER DEFAULT 0,
  is_active   BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, name)
);

-- Jumlah penerima manfaat per sekolah
CREATE TABLE IF NOT EXISTS school_beneficiaries (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  school_id           UUID REFERENCES schools(id) ON DELETE CASCADE,
  beneficiary_type_id UUID REFERENCES beneficiary_types(id),
  jumlah              INTEGER NOT NULL DEFAULT 0,
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(school_id, beneficiary_type_id)
);

-- Tambah kolom di transactions
ALTER TABLE transactions
  ADD COLUMN IF NOT EXISTS juknis_category TEXT,
  ADD COLUMN IF NOT EXISTS kas_account_id UUID REFERENCES kas_accounts(id),
  ADD COLUMN IF NOT EXISTS transaction_type TEXT DEFAULT 'debit';

-- RLS semua tabel baru
ALTER TABLE budget_allocations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE fund_disbursements    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kas_accounts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE fund_transfers        ENABLE ROW LEVEL SECURITY;
ALTER TABLE fund_returns          ENABLE ROW LEVEL SECURITY;
ALTER TABLE beneficiary_types     ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_beneficiaries  ENABLE ROW LEVEL SECURITY;

-- RLS policies (tenant isolation) — semua tabel baru
DO $$ 
DECLARE tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'budget_allocations','fund_disbursements','kas_accounts',
    'fund_transfers','fund_returns','beneficiary_types','school_beneficiaries'
  ] LOOP
    EXECUTE format(
      'CREATE POLICY IF NOT EXISTS "tenant_iso_%s" ON %I FOR ALL USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()))',
      tbl, tbl
    );
  END LOOP;
END $$;

-- Auto-set juknis_category untuk data existing
UPDATE transactions
SET juknis_category = 'dana_masuk'
WHERE type = 'income'
  AND juknis_category IS NULL;

UPDATE transactions
SET juknis_category = 'bahan_pangan'
WHERE type = 'expense'
  AND source IN ('telegram_photo','telegram_manual','import_historis')
  AND juknis_category IS NULL;
