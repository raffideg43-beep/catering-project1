-- Modul 19: Compliance & Audit Trail
-- Tambah kolom juknis, sumber dana, tanggal bayar, dan data penerima manfaat

-- ═══ TRANSACTIONS ═══
ALTER TABLE transactions
  ADD COLUMN IF NOT EXISTS payment_date DATE,
  ADD COLUMN IF NOT EXISTS juknis_category TEXT,
  ADD COLUMN IF NOT EXISTS fund_source TEXT DEFAULT 'kas_umum',
  ADD COLUMN IF NOT EXISTS transaction_type TEXT DEFAULT 'debit';

-- ═══ SCHOOLS ═══
ALTER TABLE schools
  ADD COLUMN IF NOT EXISTS jumlah_siswa_l INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS jumlah_siswa_p INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS jumlah_pendidik INTEGER DEFAULT 0;

-- ═══ BACKFILL EXISTING DATA ═══

-- Income → dana_masuk
UPDATE transactions
SET juknis_category = 'dana_masuk'
WHERE type = 'income'
  AND juknis_category IS NULL;

-- Expense dari telegram/import → bahan_pangan
UPDATE transactions
SET juknis_category = 'bahan_pangan'
WHERE type = 'expense'
  AND source IN ('telegram_photo', 'telegram_manual', 'import_historis')
  AND juknis_category IS NULL;

-- Set payment_date = date untuk data existing
UPDATE transactions
SET payment_date = date
WHERE payment_date IS NULL;

-- Set transaction_type
UPDATE transactions
SET transaction_type = 'credit'
WHERE type = 'income'
  AND transaction_type IS NULL;

UPDATE transactions
SET transaction_type = 'debit'
WHERE type = 'expense'
  AND transaction_type IS NULL;
