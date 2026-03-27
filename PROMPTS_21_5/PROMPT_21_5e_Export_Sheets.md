# Prompt Modul 21.5e: Export Excel Sheets (Bagian D)

**STATUS: ✅ READY** | Est. 3-4 hours | ~400 LOC  
**Priority: 5 (Parallel dengan 21.5d)**

---

## ⚠️ DEPENDENCIES

Must complete BEFORE starting:
- [ ] Modul 21.5b (DB Schema) — DONE
- [ ] Modul 21.5c (Endpoints) — DEPLOYED

---

## Tujuan

Tambah 5 sheet compliance ke existing Excel export service (higiene, suhu, sampel, sisa makanan, insiden).

---

## TUGAS 1: Update Export Service

**File:** `backend/services/export_service.py`

Tambake ke fungsi-fungsi yang ada (jangan ganti yang existing):

```python
# ─── NEW SECTION: Compliance Sheets ───

def _add_hygiene_sheet(wb, supabase, tenant_id: str, month: int, year: int):
    """Sheet: Higiene Bulanan"""
    ws = wb.create_sheet("Higiene", index=15)
    
    # Header
    ws['A1'] = "LAPORAN CHECKLIST HIGIENE"
    ws.merge_cells('A1:J1')
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f"{calendar.month_name[month]} {year}"
    ws.merge_cells('A2:J2')
    
    # Column headers
    headers = ['Tanggal', 'Lantai/Dinding', 'Suhu', 'Peralatan', 'Personel', 
               'Air Bersih', 'Area Penyimpanan', 'Tempat Sampah', 'Status', 'Catatan']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    
    # Query data
    date_start = date(year, month, 1)
    if month == 12:
        date_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        date_end = date(year, month + 1, 1) - timedelta(days=1)
    
    resp = supabase.table("hygiene_checks").select("*").eq(
        "tenant_id", tenant_id
    ).gte("check_date", date_start.isoformat()).lte(
        "check_date", date_end.isoformat()
    ).order("check_date", desc=False).execute()
    
    checks = getattr(resp, "data", None) or []
    
    # Populate rows
    for idx, check in enumerate(checks, start=5):
        ws.cell(row=idx, column=1).value = check.get("check_date")
        
        items = check.get("items", [])
        statuses = ["Lantai/Dinding", "Suhu", "Peralatan", "Personel", "Air Bersih", "Area Penyimpanan", "Tempak Sampah"]
        
        for col_offset, area_name in enumerate(statuses, start=2):
            matching = [i for i in items if area_name in i.get("area", "")]
            if matching:
                status_icon = "✓" if matching[0]["status"] == "baik" else "⚠️" if matching[0]["status"] == "perlu_perbaikan" else "✗"
                ws.cell(row=idx, column=col_offset).value = status_icon
            else:
                ws.cell(row=idx, column=col_offset).value = "-"
        
        ws.cell(row=idx, column=9).value = check.get("overall_status", "").upper()
        ws.cell(row=idx, column=10).value = check.get("notes", "")
    
    # Format columns
    ws.column_dimensions['A'].width = 12
    for col in ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']:
        ws.column_dimensions[col].width = 14
    ws.column_dimensions['J'].width = 20

def _add_temperature_sheet(wb, supabase, tenant_id: str, month: int, year: int):
    """Sheet: Monitoring Suhu"""
    ws = wb.create_sheet("Suhu", index=16)
    
    ws['A1'] = "LAPORAN MONITORING SUHU"
    ws.merge_cells('A1:F1')
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f"{calendar.month_name[month]} {year}"
    ws.merge_cells('A2:F2')
    
    headers = ['Tanggal', 'Jam', 'Area', 'Suhu (°C)', 'Status', 'Catatan']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    
    # Query data
    date_start = date(year, month, 1)
    if month == 12:
        date_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        date_end = date(year, month + 1, 1) - timedelta(days=1)
    
    resp = supabase.table("temperature_logs").select("*").eq(
        "tenant_id", tenant_id
    ).gte("log_date", date_start.isoformat()).lte(
        "log_date", date_end.isoformat()
    ).order("log_date", "log_time").execute()
    
    logs = getattr(resp, "data", None) or []
    
    # Populate rows + anomaly highlighting
    for idx, log in enumerate(logs, start=5):
        ws.cell(row=idx, column=1).value = log.get("log_date")
        ws.cell(row=idx, column=2).value = log.get("log_time")
        ws.cell(row=idx, column=3).value = log.get("area")
        
        temp_cell = ws.cell(row=idx, column=4)
        temp_cell.value = log.get("temperature")
        temp_cell.number_format = '0.0°C'
        
        status_cell = ws.cell(row=idx, column=5)
        if not log.get("is_normal"):
            status_cell.value = "⚠️ ABNORMAL"
            status_cell.fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
            status_cell.font = Font(color="FFFFFF", bold=True)
        else:
            status_cell.value = "✓ Normal"
            status_cell.fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            status_cell.font = Font(color="FFFFFF")
        
        ws.cell(row=idx, column=6).value = log.get("notes", "")
    
    # Format columns
    for col in ['A', 'B', 'C', 'D', 'E', 'F']:
        ws.column_dimensions[col].width = 16

def _add_samples_sheet(wb, supabase, tenant_id: str):
    """Sheet: Bank Sampel Makanan (Ongoing)"""
    ws = wb.create_sheet("Bank Sampel", index=17)
    
    ws['A1'] = "DAFTAR BANK SAMPEL MAKANAN"
    ws.merge_cells('A1:H1')
    ws['A1'].font = Font(bold=True, size=14)
    
    headers = ['Kode Sampel', 'Menu', 'Tanggal Ambil', 'Jam Ambil', 'Berat (g)', 'Kadaluarsa', 'Status', 'Catatan']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
    
    # Query active samples
    resp = supabase.table("food_samples").select("*").eq(
        "tenant_id", tenant_id
    ).eq("status", "disimpan").order("expires_at").execute()
    
    samples = getattr(resp, "data", None) or []
    
    # Populate rows
    now = datetime.now(timezone.utc)
    for idx, sample in enumerate(samples, start=4):
        ws.cell(row=idx, column=1).value = sample.get("sample_code")
        ws.cell(row=idx, column=2).value = sample.get("menu_name")
        ws.cell(row=idx, column=3).value = sample.get("sample_date")
        ws.cell(row=idx, column=4).value = sample.get("taken_at")
        ws.cell(row=idx, column=5).value = sample.get("weight_gram")
        ws.cell(row=idx, column=6).value = sample.get("expires_at")
        
        status_cell = ws.cell(row=idx, column=7)
        expires_dt = datetime.fromisoformat(sample.get("expires_at", ""))
        hours_left = (expires_dt - now).total_seconds() / 3600
        
        if hours_left < 0:
            status_cell.value = "❌ KADALUARSA"
            status_cell.fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
            status_cell.font = Font(color="FFFFFF")
        elif hours_left <= 4:
            status_cell.value = f"⚠️ {hours_left:.1f}h"
            status_cell.fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
        else:
            status_cell.value = f"✓ {hours_left:.1f}h"
            status_cell.fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
        
        ws.cell(row=idx, column=8).value = ""
    
    # Format columns
    ws.column_dimensions['A'].width = 16
    for col in ['B', 'C', 'D', 'E', 'F', 'G', 'H']:
        ws.column_dimensions[col].width = 14

def _add_food_waste_sheet(wb, supabase, tenant_id: str, month: int, year: int):
    """Sheet: Laporan Sisa Makanan"""
    ws = wb.create_sheet("Sisa Makanan", index=18)
    
    ws['A1'] = "LAPORAN SISA MAKANAN"
    ws.merge_cells('A1:J1')
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f"{calendar.month_name[month]} {year}"
    ws.merge_cells('A2:J2')
    
    headers = ['Tanggal', 'Sekolah', 'Porsi Kirim', 'Porsi Konsumsi', '% Sisa', 'Skor Comstock', 'Alasan', 'Total', 'Persen', 'KET']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    
    # Query data
    date_start = date(year, month, 1)
    if month == 12:
        date_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        date_end = date(year, month + 1, 1) - timedelta(days=1)
    
    resp = supabase.table("food_waste_reports").select("*").eq(
        "tenant_id", tenant_id
    ).gte("report_date", date_start.isoformat()).lte(
        "report_date", date_end.isoformat()
    ).order("report_date").execute()
    
    reports = getattr(resp, "data", None) or []
    
    # Aggregate by date
    daily_aggregates = {}
    for r in reports:
        key = r["report_date"]
        if key not in daily_aggregates:
            daily_aggregates[key] = {
                "total_sent": 0,
                "total_consumed": 0,
                "count": 0,
                "reports": []
            }
        daily_aggregates[key]["total_sent"] += r["portions_sent"]
        daily_aggregates[key]["total_consumed"] += r["portions_consumed"]
        daily_aggregates[key]["reports"].append(r)
    
    # Populate rows
    row_num = 5
    for report_date in sorted(daily_aggregates.keys()):
        agg = daily_aggregates[report_date]
        
        for idx, rep in enumerate(agg["reports"]):
            if idx == 0:
                ws.cell(row=row_num, column=1).value = report_date
            
            ws.cell(row=row_num, column=2).value = rep.get("school_id", "")[:8]
            ws.cell(row=row_num, column=3).value = rep["portions_sent"]
            ws.cell(row=row_num, column=4).value = rep["portions_consumed"]
            
            waste_pct_cell = ws.cell(row=row_num, column=5)
            waste_pct_cell.value = rep.get("waste_pct", 0)
            waste_pct_cell.number_format = '0.0"%"'
            
            ws.cell(row=row_num, column=6).value = f"⭐{rep['comstock_score']}"
            ws.cell(row=row_num, column=7).value = rep.get("waste_reason", "")
            
            row_num += 1
        
        # Subtotal row
        daily_waste = (
            (agg["total_sent"] - agg["total_consumed"]) / agg["total_sent"] * 100
            if agg["total_sent"] > 0 else 0
        )
        
        ws.cell(row=row_num, column=3).value = agg["total_sent"]
        ws.cell(row=row_num, column=4).value = agg["total_consumed"]
        
        total_cell = ws.cell(row=row_num, column=9)
        total_cell.value = daily_waste
        total_cell.number_format = '0.0"%"'
        total_cell.font = Font(bold=True)
        total_cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        
        row_num += 2
    
    # Format columns
    for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        ws.column_dimensions[col].width = 14

def _add_incidents_sheet(wb, supabase, tenant_id: str, month: int, year: int):
    """Sheet: Laporan Insiden KLB"""
    ws = wb.create_sheet("Insiden", index=19)
    
    ws['A1'] = "LAPORAN INSIDEN KLB/KERACUNAN"
    ws.merge_cells('A1:J1')
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f"{calendar.month_name[month]} {year}"
    ws.merge_cells('A2:J2')
    
    headers = ['Kode Insiden', 'Tanggal', 'Sekolah', 'Lokasi', 'Korban', 'Gejala', 'Tindakan', 'Sampel', 'Status', 'Hasil']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
    
    # Query data
    date_start = date(year, month, 1)
    if month == 12:
        date_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        date_end = date(year, month + 1, 1) - timedelta(days=1)
    
    resp = supabase.table("incident_reports").select("*").eq(
        "tenant_id", tenant_id
    ).gte("incident_time", f"{date_start}T00:00:00").lte(
        "incident_time", f"{date_end}T23:59:59"
    ).order("incident_time", desc=True).execute()
    
    incidents = getattr(resp, "data", None) or []
    
    # Populate rows
    for idx, incident in enumerate(incidents, start=5):
        ws.cell(row=idx, column=1).value = incident.get("incident_code")
        ws.cell(row=idx, column=2).value = incident.get("incident_time", "")[:10]
        ws.cell(row=idx, column=3).value = incident.get("school_id", "")[:8]
        ws.cell(row=idx, column=4).value = incident.get("location")
        ws.cell(row=idx, column=5).value = incident.get("victim_count")
        ws.cell(row=idx, column=6).value = ", ".join(incident.get("symptoms", []))
        ws.cell(row=idx, column=7).value = incident.get("first_action")
        
        sample_cell = ws.cell(row=idx, column=8)
        sample_cell.value = "✓ Ya" if incident.get("sample_secured") else "✗ Tidak"
        if incident.get("sample_secured"):
            sample_cell.fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
        
        status_cell = ws.cell(row=idx, column=9)
        status_cell.value = incident.get("status", "").upper()
        if incident.get("status") == "investigasi":
            status_cell.fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
        elif incident.get("status") == "selesai":
            status_cell.fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
        
        ws.cell(row=idx, column=10).value = incident.get("investigation_result", "")
    
    # Format columns
    for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        ws.column_dimensions[col].width = 14

# Call these functions untuk add sheets
# Di dalam async def export_monthly_report(...):

def export_monthly_report(supabase, tenant_id: str, month: int, year: int) -> BytesIO:
    """Generate workbook with all 15 sheets"""
    wb = Workbook()
    
    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])
    
    # Existing 10 sheets (Ringkasan, Bulanan, Stok, Laporan Pemerintah, dll)
    # ... existing code ...
    
    # NEW: 5 Compliance sheets
    _add_hygiene_sheet(wb, supabase, tenant_id, month, year)
    _add_temperature_sheet(wb, supabase, tenant_id, month, year)
    _add_samples_sheet(wb, supabase, tenant_id)
    _add_food_waste_sheet(wb, supabase, tenant_id, month, year)
    _add_incidents_sheet(wb, supabase, tenant_id, month, year)
    
    # Convert to bytes
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
```

---

## TUGAS 2: API Endpoint untuk Export

**File:** `backend/routers/reports.py`

Tambah endpoint (atau edit jika sudah ada):

```python
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from services.export_service import export_monthly_report
from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.user import UserInDB

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/export/monthly", 
            dependencies=[Depends(require_role(["owner", "admin"]))])
async def export_monthly(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2023, le=2099),
    current_user: UserInDB = Depends(get_current_user)
):
    """Export pembukuan + compliance bulanan ke Excel."""
    supabase = get_supabase()
    
    workbook = export_monthly_report(
        supabase=supabase,
        tenant_id=current_user.tenant_id,
        month=month,
        year=year
    )
    
    filename = f"Pembukuan_Compliance_{month:02d}_{year}.xlsx"
    
    return StreamingResponse(
        iter([workbook.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
```

---

## TUGAS 3: Frontend Export Button

**File:** `web/app/reports/page.tsx` (UPDATE)

Tambah section untuk Export Bulanan:

```tsx
'use client'

import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Download, FileText } from 'lucide-react'

export default function ReportsPage() {
  const [isExporting, setIsExporting] = useState(false)

  const handleExportMonthly = async (month: number, year: number) => {
    setIsExporting(true)
    try {
      const response = await fetch(
        `/api/reports/export/monthly?month=${month}&year=${year}`
      )
      
      if (!response.ok) throw new Error('Export gagal')
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Pembukuan_Compliance_${month:02d}_${year}.xlsx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } finally {
      setIsExporting(false)
    }
  }

  const currentDate = new Date()
  const months = Array.from({ length: 12 }).map((_, i) => i + 1)
  const years = [currentDate.getFullYear() - 1, currentDate.getFullYear()]

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-3xl font-bold">Laporan & Export</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Export Bulanan (Pembukuan + Compliance)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-4">
            Download pembukuan lengkap (15 sheets) dengan data compliance: Higiene, Suhu, 
            Bank Sampel, Sisa Makanan, dan Insiden.
          </p>
          
          <div className="space-y-3">
            {years.map(year => (
              <div key={year}>
                <h3 className="font-semibold mb-2">{year}</h3>
                <div className="grid grid-cols-4 gap-2">
                  {months.map(month => (
                    <Button
                      key={`${year}-${month}`}
                      variant="outline"
                      size="sm"
                      onClick={() => handleExportMonthly(month, year)}
                      disabled={isExporting}
                    >
                      <Download className="h-4 w-4 mr-1" />
                      {new Date(2024, month - 1).toLocaleString('id-ID', { month: 'short' })}
                    </Button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## TESTING CHECKLIST

- [ ] Export endpoint accepts month/year ✓
- [ ] Excel workbook creates 15 sheets ✓
- [ ] Higiene sheet populates correctly ✓
- [ ] Suhu sheet shows anomaly highlighting ✓
- [ ] Bank Sampel sheet shows hours_remaining ✓
- [ ] Sisa Makanan sheet aggregates by date ✓
- [ ] Insiden sheet colors by status ✓
- [ ] Download works in browser ✓
- [ ] File naming includes month/year ✓
- [ ] All sheets formatted consistently ✓

---

## IMPORT STATEMENTS

Pastikan di file `export_service.py` sudah ada:

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from io import BytesIO
from datetime import date, datetime, timedelta, timezone
import calendar
```

---

## GIT COMMIT

```bash
git add backend/services/export_service.py backend/routers/reports.py web/app/reports/page.tsx
git commit -m "feat: compliance export sheets — higiene, suhu, sampel, sisa, insiden (Modul 21.5e)"
```

---

## SUMMARY: Modul 21.5 COMPLETE ✅

**All 5 Prompts Delivered:**
1. ✅ 21.5a: Bot Security (2-3 hrs, 200 LOC) — Ready NOW
2. ✅ 21.5b: DB Schema (4-5 hrs, 800 LOC) — After 3 decisions
3. ✅ 21.5c: Endpoints (6-8 hrs, 600 LOC) — After alerts design
4. ✅ 21.5d: Web Dashboard (4-5 hrs, 900 LOC) — With 21.5c
5. ✅ 21.5e: Export Sheets (3-4 hrs, 400 LOC) — Parallel with 21.5d

**Total Effort:** ~20-25 hours | ~2900 LOC

**Execution Order:**
```
21.5a ✓ (Immediate, no blockers)
    ↓
21.5b ⚠️ (Needs 3 decisions resolved)
    ↓
21.5c ↔️ 21.5d + 21.5e (Parallel, after 21.5b)
```

**4 Critical Decisions Still Required:**
1. Alert mechanism (DB flag / table / webhook)
2. Auto-increment strategy (SEQUENCE / counter)
3. Driver role definition
4. Data migration approach

**Next Steps for Team:**
1. Resolve 4 blockers via team meeting
2. Start 21.5a immediately (no dependencies)
3. Prepare 21.5b with senior tech review once blockers done
4. Run 21.5c-21.5e in parallel after 21.5b deploys
