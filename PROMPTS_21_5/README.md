# Modul 21.5: Security & Compliance — Split Prompts

## 📋 Overview

Modul 21.5 dipecah menjadi **5 prompt independen** untuk clarity, testability, dan risk management. Setiap prompt siap di-copy ke Cursor/Gemini dengan scope yang jelas.

---

## 🚀 Execution Path (Recommended Order)

```
1. PROMPT_21_5a ✅ READY FOR AGENT
   └─ Bot Security & Role Protection
   └─ Duration: 2-3 hrs | Complexity: Low | Risk: 🟢 Low
   └─ Start: NOW

2. PROMPT_21_5b ⚠️ NEEDS SENIOR REVIEW
   └─ DB Schema & Migration
   └─ Duration: 4-5 hrs | Complexity: High | Risk: 🟡 Medium
   └─ Start: After 21.5a ✓
   └─ ⚠️ Must answer 3 critical questions BEFORE starting

3. PROMPT_21_5c ❌ NEEDS DESIGN FIRST
   └─ Compliance API Endpoints
   └─ Duration: 6-8 hrs | Complexity: High | Risk: 🟡 Medium
   └─ Start: After 21.5a + 21.5b ✓
   └─ ❌ BLOCKER: Define alert mechanism + auto-increment strategy first

4. PROMPT_21_5d ✅ READY FOR AGENT (Parallel with 21.5e)
   └─ Web Compliance Dashboard
   └─ Duration: 4-5 hrs | Complexity: Medium | Risk: 🟢 Low
   └─ Start: After 21.5c endpoints exist

5. PROMPT_21_5e ✅ READY FOR AGENT (Parallel with 21.5d)
   └─ Export Service - Add Compliance Sheets
   └─ Duration: 3-4 hrs | Complexity: Low | Risk: 🟢 Low
   └─ Start: After 21.5c endpoints exist
```

---

## 📊 Summary Table

| Prompt | Component | Duration | LOC | Ready? | Notes |
|--------|-----------|----------|-----|--------|-------|
| 21.5a | Bot Security | 2-3 hrs | ~200 | ✅ YES | Small, clear, highest confidence |
| 21.5b | DB Schema | 4-5 hrs | ~800 | ⚠️ REVIEW | Needs senior tech lead approval |
| 21.5c | Endpoints | 6-8 hrs | ~600 | ❌ NO | Requires design doc first |
| 21.5d | Web UI | 4-5 hrs | ~900 | ✅ YES | Can mock endpoints for UI dev |
| 21.5e | Export | 3-4 hrs | ~400 | ✅ YES | Pattern proven, straightforward |

---

## ⚡ Critical Decisions BEFORE Starting

### ❌ BLOCKER 1: Alert Mechanism (For 21.5b + 21.5c)

**Question:** When temperature is abnormal or food sample expires in 4h, where should alert be stored?

**Options:**
- [ ] Option A: Database boolean flag `is_alert_sent` per table
- [ ] Option B: Separate `alerts` table with timestamp + status
- [ ] Option C: Real-time Telegram webhook notification
- [ ] Option D: Combination (DB flag + Telegram)

**Decision:** ___________

---

### ❌ BLOCKER 2: Auto-Increment Strategy (For 21.5b + 21.5c)

**Question:** How to generate these auto-increment IDs?

- `sample_code`: SMP-{YYYYMMDD}-{increment:02d}
- `bast_number`: {increment:03d}/BAST/{bulan_romawi}/{year}
- `incident_id`: INC-{increment:03d}/{year}

**Options:**
- [ ] PostgreSQL SEQUENCE (cleaner, managed by DB)
- [ ] Counter table in app logic (flexible, manual)
- [ ] Simple query count + 1 (risky, race condition)

**Decision:** ___________

---

### ❌ BLOCKER 3: Driver Role Definition (For 21.5a)

**Question:** Add new role 'driver' atau use existing role?

**Current roles in `backend/models/user.py`:** owner, admin, kasir, viewer

**Options:**
- [ ] Add NEW role: 'driver' (separate from kasir)
- [ ] Rename 'kasir' → 'driver' (backward compat issue)
- [ ] Keep 'kasir' but extend permissions (no new role)

**Decision:** ___________

---

### ❌ BLOCKER 4: Existing Data Migration (For 21.5b)

**Question:** ALTER TABLE mbg_deliveries + 9 kolom baru, isi default value apa?

**Options:**
- [ ] NULL (safest, no assumption)
- [ ] 0 (numeric fields)
- [ ] Auto-populate from existing delivery_date (complex logic)
- [ ] Leave empty, backfill manually via script later

**Decision:** ___________

---

## 📂 File Structure After Implementation

```
backend/
├── routers/
│   ├── compliance.py                 ← NEW (21.5c)
│   └── auth.py                       ← UPDATE (21.5a)
├── models/
│   ├── compliance.py                 ← NEW (21.5c)
│   └── user.py                       ← UPDATE (21.5a)
├── services/
│   └── export_service.py            ← UPDATE (21.5e)
└── main.py                          ← UPDATE (21.5c, 21.5e)

bot/
├── handlers/
│   ├── security.py                  ← NEW (21.5a)
│   ├── auth_handler.py              ← UPDATE (21.5a)
│   ├── financial_handler.py         ← UPDATE (21.5a)
│   ├── stok_handler.py              ← UPDATE (21.5a)
│   ├── nota_handler.py              ← UPDATE (21.5a)
│   └── serah_handler.py             ← UPDATE (21.5a)
└── utils/
    └── session.py                   ← No change needed

supabase/
└── migrations/
    └── 20260327000021_compliance_ops.sql  ← NEW (21.5b)

web/app/(dashboard)/
├── compliance/
│   ├── page.tsx                     ← NEW (21.5d)
│   └── _tabs/
│       ├── HygieneTab.tsx
│       ├── BASTTab.tsx
│       ├── WasteTab.tsx
│       ├── SampleTab.tsx
│       └── IncidentTab.tsx
└── layout.tsx                       ← UPDATE (21.5d)
```

---

## 🎬 How to Use These Prompts

### Step 1: Choose Agent
Switch VS Code Copilot to **Default ("Copilot")** mode (not "Ask" mode).

### Step 2: Copy Prompt
1. Open file (e.g., `PROMPT_21_5a_Bot_Security.md`)
2. Select all (Ctrl+A)
3. Copy (Ctrl+C)

### Step 3: Paste to Cursor/Gemini
Open Cursor IDE or Gemini web:
- Paste full prompt
- Let AI implement end-to-end
- Review + modify if needed

### Step 4: Test
- Run unit tests
- Test locally
- Commit to git

### Step 5: Next Prompt
Move to next prompt file, repeat.

---

## ✅ Prerequisites Before Each Prompt

### Before 21.5a (Bot Security)
- [ ] Answer BLOCKER 3 (Driver Role)
- [ ] Confirm `@requires_role` decorator pattern acceptable

### Before 21.5b (DB Schema)
- [ ] Answer BLOCKER 1 (Alert Mechanism)
- [ ] Answer BLOCKER 2 (Auto-Increment Strategy)
- [ ] Answer BLOCKER 4 (Existing Data Strategy)
- [ ] Backup production database
- [ ] Staging DB ready for migration test

### Before 21.5c (Endpoints)
- [ ] 21.5a ✅ COMPLETED
- [ ] 21.5b ✅ COMPLETED & MIGRATED
- [ ] Answer BLOCKER 1 (Alert Mechanism) - FINAL DECISION
- [ ] Answer BLOCKER 2 (Auto-Increment) - FINAL DECISION
- [ ] Design doc for alert flow (where stored, how triggered, who notified)

### Before 21.5d (Web UI)
- [ ] 21.5c ✅ COMPLETED & DEPLOYED
- [ ] API endpoints tested + returning real data
- [ ] Decide UI component library (Shadcn/UI assumed in prompt)

### Before 21.5e (Export Sheets)
- [ ] 21.5b ✅ COMPLETED & MIGRATED
- [ ] 21.5c ✅ COMPLETED & DEPLOYED
- [ ] Data flowing into compliance tables

---

## 🐛 Testing Strategy

Each prompt includes testing checklist. Flow:

```
Write Code → Run Tests → Fix Issues → Commit → Move to Next Prompt
```

No cross-prompt work until previous prompt fully tested & approved.

---

## 🔗 References

**MASTER_PLAN.md Status:**
- Modul 1-21: ✅ COMPLETED
- Modul 21.5a: ⬅️ START HERE
- Modul 21.5b-e: PENDING

**Estimated Total Time:** 20-27 hours (including testing + reviews)

---

## 📞 Support

**Issues during implementation?**
1. Check testing checklist in each prompt
2. Verify prerequisites met before prompt
3. Review critical decision blockers
4. Git stash, rollback migration, try again

**Questions about design?**
Refer to the analysis document `/memories/session/modul_21_5_prompt_analysis.md`

---

**Ready?** Start with `PROMPT_21_5a_Bot_Security.md` 🚀
