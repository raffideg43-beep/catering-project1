# Prompt Modul 21.5b: Compliance Database Schema & Migration (Bagian A)

**STATUS: ⚠️ NEEDS SENIOR REVIEW** | Est. 4-5 hours | ~800 LOC  
**Priority: 2 (After 21.5a)**

---

## Tujuan

Implementasi database structure untuk compliance operasional SPPG (Higiene, Suhu, Bank Sampel, Sisa Makanan, Insiden, SLHS).

---

## ⚠️ CRITICAL DECISION QUESTIONS

Sebelum mulai, **jawab pertanyaan ini di team**:

### 1. Alert Storage
**Jika suhu abnormal atau sampel mau expire, di mana alert di-store?**
- Option A: Boolean flag di table `is_alert_sent`
- Option B: Separate `alerts` table
- Option C: Real-time ke Telegram (webhook)
- **DECISION**: ___________

### 2. Auto-Increment Strategy
**Bagaimana generate ID otomatis?**
- sample_code: SMP-{YYYYMMDD}-{increment:02d}
- bast_number: {increment:03d}/BAST/{bulan_romawi}/{year}
- incident_id: INC-{increment:03d}/{year}

**Use**: PostgreSQL SEQUENCE or Counter Table?
- **DECISION**: ___________

### 3. Migration Backfill
**Untuk ALTER TABLE mbg_deliveries +9 kolom, isi default apa?**
- NULL? 0? Auto-populate dari existing delivery_date?
- **DECISION**: ___________

---

## BAGIAN 1: Schema SQL Migration

**File:** `supabase/migrations/20260327000021_compliance_ops.sql`

**PENTING:**
- Jalankan manual di Supabase SQL Editor (jangan auto-run)
- Create tables dalam urutan ini (foreign key dependency)
- Test di staging DULU sebelum production

---

### 1.1 Hygiene Checks Table

```sql
CREATE TABLE IF NOT EXISTS hygiene_checks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  check_date      DATE NOT NULL,
  checked_by      UUID REFERENCES users(id) ON DELETE SET NULL,
  
  items           JSONB NOT NULL,
  -- Format: [{area: str, status: str, catatan: str, suhu?: float}, ...]
  -- Status values: "baik" | "perlu_perbaikan"
  
  overall_status  TEXT DEFAULT 'baik'
    CHECK (overall_status IN ('baik', 'perlu_perbaikan', 'tidak_layak')),
  -- "baik": SEMUA area baik
  -- "perlu_perbaikan": >= 1 area perlu perbaikan
  -- "tidak_layak": Ada suhu di luar batas safety
  
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(tenant_id, check_date),
  INDEX idx_hygiene_date (tenant_id, check_date DESC)
);

ALTER TABLE hygiene_checks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation_hygiene" ON hygiene_checks
  FOR ALL USING (
    tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid())
  );
```

---

### 1.2 Temperature Logs Table

```sql
CREATE TABLE IF NOT EXISTS temperature_logs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  log_date        DATE NOT NULL,
  log_time        TIME NOT NULL,
  area            TEXT NOT NULL
    CHECK (area IN ('gudang_kering', 'chiller', 'freezer')),
  
  temperature     DECIMAL(5, 2) NOT NULL,  -- dalam Celcius
  is_normal       BOOLEAN NOT NULL DEFAULT TRUE,
  -- Auto-set: gudang_kering < 25, chiller 10-15, freezer < -18
  
  notes           TEXT,
  recorded_by     UUID REFERENCES users(id) ON DELETE SET NULL,
  
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  
  INDEX idx_temp_date_area (tenant_id, log_date DESC, area)
);

ALTER TABLE temperature_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation_temp" ON temperature_logs
  FOR ALL USING (
    tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid())
  );
```

---

### 1.3 Food Samples Table

```sql
CREATE TABLE IF NOT EXISTS food_samples (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  
  sample_date     DATE NOT NULL,
  sample_code     TEXT NOT NULL,  -- Auto: SMP-{YYYYMMDD}-{increment:02d}
  
  menu_name       TEXT NOT NULL,
  taken_at        TIME NOT NULL,  -- jam pengambilan
  weight_gram     DECIMAL(8, 2) DEFAULT 50,
  storage_temp    DECIMAL(5, 2),
  
  expires_at      TIMESTAMPTZ,  -- Auto: taken_at + 48 jam
  status          TEXT DEFAULT 'disimpan'
    CHECK (status IN ('disimpan', 'bisa_dibuang', 'dibuang', 'diamankan_investigasi')),
  
  disposed_at     TIMESTAMPTZ,
  is_alert_sent   BOOLEAN DEFAULT FALSE,  -- Alert jika < 4 jam sebelum expire
  
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(tenant_id, sample_code),
  INDEX idx_sample_date (tenant_id, sample_date DESC),
  INDEX idx_sample_expires (tenant_id, expires_at, status)
);

ALTER TABLE food_samples ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation_samples" ON food_samples
  FOR ALL USING (
    tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid())
  );
```

---

### 1.4 Food Waste Reports Table

```sql
CREATE TABLE IF NOT EXISTS food_waste_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  
  delivery_id     UUID REFERENCES mbg_deliveries(id) ON DELETE CASCADE,
  school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  
  report_date     DATE NOT NULL,
  portions_sent   INTEGER NOT NULL CHECK (portions_sent > 0),
  portions_consumed INTEGER CHECK (portions_consumed >= 0),
  
  waste_pct       DECIMAL(5, 2),  -- Auto: (sent - consumed) / sent × 100
  comstock_score  INTEGER CHECK (comstock_score BETWEEN 1 AND 5),
  -- 1 = Habis, 2 = <25%, 3 = 25-50%, 4 = 50-75%, 5 = >75%
  
  waste_reason    TEXT,  -- kenyang | tidak_suka | terlambat | lainnya
  notes           TEXT,
  
  created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(tenant_id, delivery_id, school_id),
  INDEX idx_waste_date (tenant_id, report_date DESC)
);

ALTER TABLE food_waste_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation_waste" ON food_waste_reports
  FOR ALL USING (
    tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid())
  );
```

---

### 1.5 Incident Reports Table

```sql
CREATE TABLE IF NOT EXISTS incident_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  
  incident_code   TEXT NOT NULL,  -- Auto: INC-{increment:03d}/{year}
  
  school_id       UUID REFERENCES schools(id) ON DELETE SET NULL,
  incident_time   TIMESTAMPTZ NOT NULL,
  location        TEXT NOT NULL,
  
  victim_count    INTEGER NOT NULL CHECK (victim_count > 0),
  symptoms        TEXT[],  -- ['mual', 'muntah', 'diare', 'pusing', 'sesak']
  first_action    TEXT NOT NULL,
  
  sample_secured  BOOLEAN DEFAULT FALSE,
  sample_ids      TEXT[],  -- daftar sample_code yang diamankan
  reported_to     TEXT[],  -- ['puskesmas', 'dinkes', 'bpom', 'bgn']
  
  status          TEXT DEFAULT 'investigasi'
    CHECK (status IN ('investigasi', 'selesai', 'ditutup')),
  investigation_result TEXT,
  
  created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(tenant_id, incident_code),
  INDEX idx_incident_date (tenant_id, incident_time DESC)
);

ALTER TABLE incident_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation_incident" ON incident_reports
  FOR ALL USING (
    tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid())
  );
```

---

### 1.6 SLHS Documents Table

```sql
CREATE TABLE IF NOT EXISTS slhs_documents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  
  cert_number     TEXT NOT NULL,
  issued_date     DATE NOT NULL,
  expires_date    DATE NOT NULL,  -- issued_date + 3 tahun
  label_expires   DATE,  -- issued_date + 2 tahun (label pengawasan)
  
  file_url        TEXT,  -- upload dokumen SLHS
  
  status          TEXT DEFAULT 'aktif'
    CHECK (status IN ('aktif', 'expiring_soon', 'expired', 'dalam_proses')),
  
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(tenant_id, cert_number),
  INDEX idx_slhs_status (tenant_id, status)
);

ALTER TABLE slhs_documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation_slhs" ON slhs_documents
  FOR ALL USING (
    tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid())
  );
```

---

### 1.7 ALTER mbg_deliveries (BAST Extensions)

```sql
-- ⚠️ CAREFUL: Jalankan beda session jika perlu, jangan dalam transaction dengan table creation

ALTER TABLE mbg_deliveries
  ADD COLUMN IF NOT EXISTS bast_number TEXT UNIQUE,
    -- Auto: {increment:03d}/BAST/{bulan_romawi}/{year}
  ADD COLUMN IF NOT EXISTS vehicle_number TEXT,
    -- Nomor kendaraan pengemudi
  ADD COLUMN IF NOT EXISTS cooked_at TIME,
    -- Jam makanan selesai dimasak
  ADD COLUMN IF NOT EXISTS departed_at TIME,
    -- Jam berangkat dari dapur
  ADD COLUMN IF NOT EXISTS arrived_at TIME,
    -- Jam tiba di sekolah
  ADD COLUMN IF NOT EXISTS food_temp_arrival DECIMAL(5, 2),
    -- Suhu makanan saat tiba (Celsius)
  ADD COLUMN IF NOT EXISTS seal_condition TEXT DEFAULT 'utuh'
    CHECK (seal_condition IN ('utuh', 'terbuka', 'rusak')),
    -- Kondisi seal makanan
  ADD COLUMN IF NOT EXISTS tray_sent INTEGER DEFAULT 0,
    -- Jumlah food tray dikirim
  ADD COLUMN IF NOT EXISTS tray_returned INTEGER DEFAULT 0,
    -- Jumlah food tray dikembalikan
  ADD COLUMN IF NOT EXISTS portions_received INTEGER,
    -- Porsi yang diterima pihak sekolah (bisa berbeda dari portions_sent)
  ADD COLUMN IF NOT EXISTS damaged_portions INTEGER DEFAULT 0,
    -- Porsi rusak/tidak layak
  ADD COLUMN IF NOT EXISTS receiver_signature_name TEXT,
    -- Nama lengkap penerima di sekolah
  ADD COLUMN IF NOT EXISTS hours_since_cooking DECIMAL(4, 2);
    -- Auto-calc: (arrived_at - cooked_at) dalam jam

CREATE INDEX IF NOT EXISTS idx_bast_number ON mbg_deliveries(bast_number);
CREATE INDEX IF NOT EXISTS idx_delivery_bast_fields ON mbg_deliveries(
  tenant_id, delivery_date DESC, bast_number
);
```

---

## BAGIAN 2: Migration Validation

Sebelum deploy, verify:

```sql
-- 1. Check table structure
SELECT tablename FROM pg_tables WHERE schemaname = 'public' 
WHERE tablename LIKE 'hygiene%' OR tablename LIKE 'temperature%';

-- 2. Check RLS policies
SELECT * FROM pg_policies 
WHERE tablename IN ('hygiene_checks', 'temperature_logs', 'food_samples');

-- 3. Check mbg_deliveries new columns
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'mbg_deliveries' AND column_name IN 
('bast_number', 'vehicle_number', 'cooked_at');
```

---

## BAGIAN 3: To-Do Before Code Implementation

- [ ] Answer 3 CRITICAL questions di atas (Alert, Increment, Backfill)
- [ ] Run migration di staging DB → verify no errors
- [ ] Backup production DB sebelum migration
- [ ] Design trigger/job untuk auto-set `is_normal` di temperature_logs
- [ ] Clarify RLS policy untuk setiap table (role-based akses?)

---

## GIT COMMIT

```bash
git add supabase/migrations/20260327000021_compliance_ops.sql
git commit -m "migration: compliance ops tables + mbg_deliveries BAST fields (Modul 21.5b)"
```

---

**NEXT**: Tunggu 21.5b approved sebelum mulai 21.5c (Endpoints).
