# Prompt Modul 21.5c: Compliance API Endpoints (Bagian B)

**STATUS: ❌ NEEDS DESIGN FIRST** | Est. 6-8 hours | ~600 LOC  
**Priority: 3 (After 21.5a + 21.5b DONE)**

---

## ⚠️ DEPENDENCIES

Must complete BEFORE starting this prompt:
- [ ] Modul 21.5b (DB Schema) — DONE & MIGRATED
- [ ] Modul 21.5a (Security) — DONE & TESTED
- [ ] CRITICAL DECISION 1: Alert mechanism (DB flag / separate table / Telegram webhook)
- [ ] CRITICAL DECISION 2: Auto-increment strategy (SEQUENCE / counter table)

---

## Tujuan

Implementasi 6 endpoint compliance dengan business logic, validation, dan auto-calculation untuk support higiene, suhu, sampel, sisa makanan, dan insiden.

---

## TUGAS 1: Model Definitions

**File:** `backend/models/compliance.py` (BARU)

```python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import date, datetime, time

# ─── Hygiene ───
class HygieneCheckItem(BaseModel):
    area: str
    status: str  # "baik" | "perlu_perbaikan"
    catatan: Optional[str] = None
    suhu: Optional[float] = None

class HygieneCheckCreate(BaseModel):
    check_date: date
    items: List[HygieneCheckItem]
    notes: Optional[str] = None

class HygieneCheckResponse(HygieneCheckCreate):
    id: str
    tenant_id: str
    checked_by: Optional[str] = None
    overall_status: str
    created_at: str

# ─── Temperature ───
class TemperatureLogCreate(BaseModel):
    log_date: date
    log_time: time
    area: str  # "gudang_kering" | "chiller" | "freezer"
    temperature: float
    notes: Optional[str] = None

class TemperatureLogResponse(TemperatureLogCreate):
    id: str
    is_normal: bool
    recorded_by: Optional[str] = None
    created_at: str

# ─── Food Samples ───
class FoodSampleCreate(BaseModel):
    sample_date: date
    menu_name: str
    taken_at: time
    weight_gram: float = 50.0
    storage_temp: Optional[float] = None

class FoodSampleResponse(FoodSampleCreate):
    id: str
    sample_code: str
    expires_at: str
    status: str
    created_at: str
    hours_remaining: Optional[float] = None

class FoodSampleDispose(BaseModel):
    reason: str = "normal_disposal"

# ─── Food Waste ───
class FoodWasteCreate(BaseModel):
    delivery_id: str
    school_id: str
    report_date: date
    portions_sent: int = Field(..., gt=0)
    portions_consumed: int = Field(..., ge=0)
    comstock_score: int = Field(..., ge=1, le=5)
    waste_reason: str
    notes: Optional[str] = None

class FoodWasteResponse(FoodWasteCreate):
    id: str
    waste_pct: float
    created_by: Optional[str] = None
    created_at: str

# ─── Incident ───
class IncidentCreate(BaseModel):
    school_id: Optional[str] = None
    incident_time: datetime
    location: str
    victim_count: int = Field(..., gt=0)
    symptoms: List[str]
    first_action: str
    sample_secured: bool = False
    sample_ids: Optional[List[str]] = None
    reported_to: Optional[List[str]] = None

class IncidentResponse(IncidentCreate):
    id: str
    incident_code: str
    status: str
    created_by: Optional[str] = None
    created_at: str
```

---

## TUGAS 2: Compliance Endpoints (Main Router)

**File:** `backend/routers/compliance.py` (BARU) — Part 1

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List
from decimal import Decimal

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.user import UserInDB
from models.compliance import (
    HygieneCheckCreate, HygieneCheckResponse,
    TemperatureLogCreate, TemperatureLogResponse,
    FoodSampleCreate, FoodSampleResponse, FoodSampleDispose,
    FoodWasteCreate, FoodWasteResponse,
    IncidentCreate, IncidentResponse
)

router = APIRouter(prefix="/compliance", tags=["compliance"])

TEMP_LIMITS = {
    "gudang_kering": {"max": 25, "min": 0},
    "chiller":       {"max": 15, "min": 10},
    "freezer":       {"max": -18, "min": -30}
}

AREA_CHECKS = [
    "Kebersihan Lantai & Dinding",
    "Suhu Penyimpanan (Chiller/Freezer)",
    "Kebersihan Peralatan Masak",
    "Atribut Personel (Masker/Apron/Hairnet)",
    "Kualitas Air Bersih",
    "Kebersihan Area Penyimpanan",
    "Kondisi Tempat Sampah",
]

# ─── ENDPOINT 1: Higiene ───

@router.get("/hygiene/template", response_model=Dict[str, Any], 
            dependencies=[Depends(require_role(["owner", "admin"]))])
async def get_hygiene_template(current_user: UserInDB = Depends(get_current_user)):
    """Ambil template area yang perlu dicek."""
    return {
        "success": True,
        "areas": AREA_CHECKS,
        "statuses": ["baik", "perlu_perbaikan"]
    }

@router.post("/hygiene", response_model=Dict[str, Any],
             dependencies=[Depends(require_role(["owner", "admin"]))])
async def create_hygiene_check(
    body: HygieneCheckCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """Simpan checklist higiene untuk hari tertentu."""
    supabase = get_supabase()
    
    if not body.items or len(body.items) == 0:
        raise HTTPException(400, detail="Items tidak boleh kosong")
    
    # Auto-determine overall_status
    has_perlu_perbaikan = any(i.status == "perlu_perbaikan" for i in body.items)
    has_tidak_layak = any(
        i.suhu and (
            (i.area == "gudang_kering" and i.suhu >= 25) or
            (i.area == "chiller" and (i.suhu < 10 or i.suhu > 15)) or
            (i.area == "freezer" and i.suhu > -18)
        )
        for i in body.items if i.suhu
    )
    
    if has_tidak_layak:
        overall_status = "tidak_layak"
    elif has_perlu_perbaikan:
        overall_status = "perlu_perbaikan"
    else:
        overall_status = "baik"
    
    # Insert
    insert_data = {
        "tenant_id": current_user.tenant_id,
        "check_date": body.check_date.isoformat(),
        "checked_by": current_user.id,
        "items": [item.dict() for item in body.items],
        "overall_status": overall_status,
        "notes": body.notes
    }
    
    resp = supabase.table("hygiene_checks").insert(insert_data).execute()
    data = (getattr(resp, "data", None) or [{}])[0]
    
    if not data.get("id"):
        raise HTTPException(500, detail="Gagal simpan higiene check")
    
    return {
        "success": True,
        "data": HygieneCheckResponse(**data)
    }

@router.get("/hygiene", response_model=Dict[str, Any],
            dependencies=[Depends(require_role(["owner", "admin"]))])
async def get_hygiene_checks(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...),
    current_user: UserInDB = Depends(get_current_user)
):
    """Ambil checklist higiene per bulan."""
    supabase = get_supabase()
    
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    
    resp = supabase.table("hygiene_checks").select("*").eq(
        "tenant_id", current_user.tenant_id
    ).gte("check_date", first.isoformat()).lte(
        "check_date", last.isoformat()
    ).order("check_date", desc=True).execute()
    
    checks = getattr(resp, "data", None) or []
    
    return {
        "success": True,
        "count": len(checks),
        "month": month,
        "year": year,
        "data": [HygieneCheckResponse(**c) for c in checks]
    }

# ─── ENDPOINT 2: Suhu ───

@router.post("/temperature", response_model=Dict[str, Any],
             dependencies=[Depends(require_role(["owner", "admin", "kasir"]))])
async def create_temperature_log(
    body: TemperatureLogCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """Catat suhu penyimpanan."""
    supabase = get_supabase()
    
    limits = TEMP_LIMITS.get(body.area)
    if not limits:
        raise HTTPException(400, detail=f"Area {body.area} tidak valid")
    
    is_normal = limits["min"] <= body.temperature <= limits["max"]
    
    insert_data = {
        "tenant_id": current_user.tenant_id,
        "log_date": body.log_date.isoformat(),
        "log_time": str(body.log_time),
        "area": body.area,
        "temperature": float(body.temperature),
        "is_normal": is_normal,
        "notes": body.notes,
        "recorded_by": current_user.id
    }
    
    resp = supabase.table("temperature_logs").insert(insert_data).execute()
    data = (getattr(resp, "data", None) or [{}])[0]
    
    if not data.get("id"):
        raise HTTPException(500, detail="Gagal simpan temperature log")
    
    result = {
        "success": True,
        "data": TemperatureLogResponse(**data)
    }
    
    # Alert jika tidak normal
    if not is_normal:
        result["alert"] = {
            "severity": "high",
            "message": f"⚠️ Suhu {body.area} abnormal: {body.temperature}°C "
                      f"(Seharusnya {limits['min']}-{limits['max']}°C)"
        }
    
    return result

@router.get("/temperature", response_model=Dict[str, Any],
            dependencies=[Depends(require_role(["owner", "admin"]))])
async def get_temperature_logs(
    log_date: date = Query(...),
    area: str = Query(None),
    current_user: UserInDB = Depends(get_current_user)
):
    """Ambil log suhu untuk tanggal tertentu."""
    supabase = get_supabase()
    
    query = supabase.table("temperature_logs").select("*").eq(
        "tenant_id", current_user.tenant_id
    ).eq("log_date", log_date.isoformat())
    
    if area:
        query = query.eq("area", area)
    
    resp = query.order("log_time", desc=True).execute()
    logs = getattr(resp, "data", None) or []
    
    anomalies = [l for l in logs if not l.get("is_normal")]
    
    return {
        "success": True,
        "log_date": log_date.isoformat(),
        "count": len(logs),
        "anomalies": len(anomalies),
        "data": [TemperatureLogResponse(**l) for l in logs],
        "alert": {
            "anomaly_count": len(anomalies)
        } if anomalies else None
    }

# ─── ENDPOINT 3: Bank Sampel ───

@router.post("/food-samples", response_model=Dict[str, Any],
             dependencies=[Depends(require_role(["owner", "admin", "kasir"]))])
async def create_food_sample(
    body: FoodSampleCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """Catat bank sampel makanan."""
    supabase = get_supabase()
    
    # Auto-generate sample_code: SMP-{YYYYMMDD}-{increment:02d}
    date_str = body.sample_date.isoformat().replace("-", "")
    
    existing = supabase.table("food_samples").select("sample_code").eq(
        "tenant_id", current_user.tenant_id
    ).eq("sample_date", body.sample_date.isoformat()).execute()
    
    last_samples = getattr(existing, "data", None) or []
    if last_samples:
        last_code = last_samples[-1]["sample_code"]
        increment = int(last_code.split("-")[-1]) + 1
    else:
        increment = 1
    
    sample_code = f"SMP-{date_str}-{increment:02d}"
    
    # Auto-set expires_at = taken_at + 48 jam
    taken_datetime = datetime.combine(body.sample_date, body.taken_at)
    expires_at = (taken_datetime + timedelta(hours=48)).isoformat()
    
    insert_data = {
        "tenant_id": current_user.tenant_id,
        "sample_date": body.sample_date.isoformat(),
        "sample_code": sample_code,
        "menu_name": body.menu_name,
        "taken_at": str(body.taken_at),
        "weight_gram": float(body.weight_gram),
        "storage_temp": float(body.storage_temp) if body.storage_temp else None,
        "expires_at": expires_at,
        "status": "disimpan"
    }
    
    resp = supabase.table("food_samples").insert(insert_data).execute()
    data = (getattr(resp, "data", None) or [{}])[0]
    
    if not data.get("id"):
        raise HTTPException(500, detail="Gagal simpan sampel")
    
    return {
        "success": True,
        "data": FoodSampleResponse(**data)
    }

@router.get("/food-samples", response_model=Dict[str, Any],
            dependencies=[Depends(require_role(["owner", "admin"]))])
async def get_food_samples(
    sample_date: date = Query(None),
    status: str = Query(None),
    current_user: UserInDB = Depends(get_current_user)
):
    """Ambil daftar sampel makanan."""
    supabase = get_supabase()
    
    query = supabase.table("food_samples").select("*").eq(
        "tenant_id", current_user.tenant_id
    )
    
    if sample_date:
        query = query.eq("sample_date", sample_date.isoformat())
    
    if status:
        query = query.eq("status", status)
    
    resp = query.order("expires_at", desc=False).execute()
    samples = getattr(resp, "data", None) or []
    
    # Calculate hours_remaining
    alerts = []
    now = datetime.now(timezone.utc)
    
    for s in samples:
        if s.get("expires_at"):
            expires = datetime.fromisoformat(s["expires_at"])
            hours_left = (expires - now).total_seconds() / 3600
            s["hours_remaining"] = round(hours_left, 1)
            
            if hours_left <= 4:
                alerts.append({
                    "sample_code": s["sample_code"],
                    "menu": s["menu_name"],
                    "hours_left": round(hours_left, 1)
                })
    
    return {
        "success": True,
        "count": len(samples),
        "alerts_count": len(alerts),
        "data": [FoodSampleResponse(**s) for s in samples],
        "alerts": alerts if alerts else None
    }

@router.patch("/food-samples/{sample_id}/dispose", response_model=Dict[str, Any],
              dependencies=[Depends(require_role(["owner", "admin"]))])
async def dispose_food_sample(
    sample_id: str,
    body: FoodSampleDispose,
    current_user: UserInDB = Depends(get_current_user)
):
    """Tandai sampel sebagai dibuang."""
    supabase = get_supabase()
    
    resp = supabase.table("food_samples").update({
        "status": "dibuang",
        "disposed_at": datetime.now().isoformat()
    }).eq("id", sample_id).eq("tenant_id", current_user.tenant_id).execute()
    
    data = (getattr(resp, "data", None) or [{}])[0]
    
    if not data.get("id"):
        raise HTTPException(404, detail="Sampel tidak ditemukan")
    
    return {"success": True, "message": "Sampel ditandai dibuang"}

# ─── ENDPOINT 4: Sisa Makanan ───

@router.post("/food-waste", response_model=Dict[str, Any],
             dependencies=[Depends(require_role(["owner", "admin", "kasir"]))])
async def create_food_waste_report(
    body: FoodWasteCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """Input laporan sisa makanan per sekolah."""
    supabase = get_supabase()
    
    if body.portions_consumed > body.portions_sent:
        raise HTTPException(400, detail="Porsi dikonsumsi tidak boleh > porsi kirim")
    
    waste_pct = round(
        (body.portions_sent - body.portions_consumed) / body.portions_sent * 100, 2
    ) if body.portions_sent > 0 else 0
    
    insert_data = {
        "tenant_id": current_user.tenant_id,
        "delivery_id": body.delivery_id,
        "school_id": body.school_id,
        "report_date": body.report_date.isoformat(),
        "portions_sent": body.portions_sent,
        "portions_consumed": body.portions_consumed,
        "waste_pct": waste_pct,
        "comstock_score": body.comstock_score,
        "waste_reason": body.waste_reason,
        "notes": body.notes,
        "created_by": current_user.id
    }
    
    resp = supabase.table("food_waste_reports").insert(insert_data).execute()
    data = (getattr(resp, "data", None) or [{}])[0]
    
    if not data.get("id"):
        raise HTTPException(500, detail="Gagal simpan laporan sisa")
    
    return {
        "success": True,
        "data": FoodWasteResponse(**data)
    }

@router.get("/food-waste", response_model=Dict[str, Any],
            dependencies=[Depends(require_role(["owner", "admin"]))])
async def get_food_waste_reports(
    month: int = Query(...),
    year: int = Query(...),
    school_id: str = Query(None),
    current_user: UserInDB = Depends(get_current_user)
):
    """Ambil laporan sisa makanan per bulan."""
    supabase = get_supabase()
    
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    
    query = supabase.table("food_waste_reports").select("*, schools(name)").eq(
        "tenant_id", current_user.tenant_id
    ).gte("report_date", first.isoformat()).lte("report_date", last.isoformat())
    
    if school_id:
        query = query.eq("school_id", school_id)
    
    resp = query.order("report_date", desc=True).execute()
    reports = getattr(resp, "data", None) or []
    
    # Summary per school
    summary = {}
    for r in reports:
        sch_id = r.get("school_id")
        if sch_id not in summary:
            summary[sch_id] = {"avg_waste_pct": 0, "avg_comstock": 0, "count": 0}
        summary[sch_id]["count"] += 1
        summary[sch_id]["avg_waste_pct"] += r.get("waste_pct", 0)
        summary[sch_id]["avg_comstock"] += r.get("comstock_score", 0)
    
    for s in summary.values():
        if s["count"] > 0:
            s["avg_waste_pct"] = round(s["avg_waste_pct"] / s["count"], 1)
            s["avg_comstock"] = round(s["avg_comstock"] / s["count"], 1)
    
    return {
        "success": True,
        "month": month,
        "year": year,
        "count": len(reports),
        "summary": summary,
        "data": [FoodWasteResponse(**r) for r in reports]
    }

# ─── ENDPOINT 5: Insiden ───

@router.post("/incidents", response_model=Dict[str, Any],
             dependencies=[Depends(require_role(["owner", "admin"]))])
async def create_incident_report(
    body: IncidentCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """Laporkan insiden (dugaan keracunan/KLB)."""
    supabase = get_supabase()
    
    # Auto-generate incident_code
    year = datetime.now().year
    existing = supabase.table("incident_reports").select("incident_code").eq(
        "tenant_id", current_user.tenant_id
    ).ilike("incident_code", f"%/{year}").execute()
    
    last_incidents = getattr(existing, "data", None) or []
    if last_incidents:
        last_code = last_incidents[-1]["incident_code"]
        increment = int(last_code.split("-")[1].split("/")[0]) + 1
    else:
        increment = 1
    
    incident_code = f"INC-{increment:03d}/{year}"
    
    # Insert
    insert_data = {
        "tenant_id": current_user.tenant_id,
        "incident_code": incident_code,
        "school_id": body.school_id,
        "incident_time": body.incident_time.isoformat(),
        "location": body.location,
        "victim_count": body.victim_count,
        "symptoms": body.symptoms,
        "first_action": body.first_action,
        "sample_secured": body.sample_secured,
        "sample_ids": body.sample_ids,
        "reported_to": body.reported_to,
        "status": "investigasi",
        "created_by": current_user.id
    }
    
    resp = supabase.table("incident_reports").insert(insert_data).execute()
    data = (getattr(resp, "data", None) or [{}])[0]
    
    # Update sample status jika ada
    if body.sample_secured and body.sample_ids:
        for sample_code in body.sample_ids:
            supabase.table("food_samples").update({
                "status": "diamankan_investigasi"
            }).eq("sample_code", sample_code).eq(
                "tenant_id", current_user.tenant_id
            ).execute()
    
    return {
        "success": True,
        "data": IncidentResponse(**data)
    }

@router.get("/incidents", response_model=Dict[str, Any],
            dependencies=[Depends(require_role(["owner", "admin"]))])
async def get_incidents(
    month: int = Query(None),
    year: int = Query(None),
    current_user: UserInDB = Depends(get_current_user)
):
    """Ambil laporan insiden."""
    supabase = get_supabase()
    
    query = supabase.table("incident_reports").select("*, schools(name)").eq(
        "tenant_id", current_user.tenant_id
    )
    
    if month and year:
        first = date(year, month, 1)
        if month == 12:
            last = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(year, month + 1, 1) - timedelta(days=1)
        
        query = query.gte("incident_time", f"{first}T00:00:00").lte(
            "incident_time", f"{last}T23:59:59"
        )
    
    resp = query.order("incident_time", desc=True).execute()
    incidents = getattr(resp, "data", None) or []
    
    return {
        "success": True,
        "count": len(incidents),
        "data": [IncidentResponse(**i) for i in incidents]
    }

@router.put("/incidents/{incident_id}", response_model=Dict[str, Any],
            dependencies=[Depends(require_role(["owner"]))])
async def update_incident_report(
    incident_id: str,
    body: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_user)
):
    """Update status + hasil investigasi (owner only)."""
    supabase = get_supabase()
    
    update_data = {}
    if "status" in body:
        update_data["status"] = body["status"]
    if "investigation_result" in body:
        update_data["investigation_result"] = body["investigation_result"]
    
    resp = supabase.table("incident_reports").update(
        update_data
    ).eq("id", incident_id).eq("tenant_id", current_user.tenant_id).execute()
    
    data = (getattr(resp, "data", None) or [{}])[0]
    
    if not data.get("id"):
        raise HTTPException(404, detail="Insiden tidak ditemukan")
    
    return {"success": True, "message": "Insiden berhasil diupdate"}

# ─── ENDPOINT 6: SLHS ───

@router.get("/slhs", response_model=Dict[str, Any],
            dependencies=[Depends(require_role(["owner", "admin"]))])
async def get_slhs_documents(
    current_user: UserInDB = Depends(get_current_user)
):
    """Ambil status SLHS aktif."""
    supabase = get_supabase()
    
    resp = supabase.table("slhs_documents").select("*").eq(
        "tenant_id", current_user.tenant_id
    ).eq("status", "aktif").execute()
    
    slhs_list = getattr(resp, "data", None) or []
    
    # Flag expiring soon
    alerts = []
    now = datetime.now().date()
    for s in slhs_list:
        expires = datetime.fromisoformat(s["expires_date"]).date()
        days_left = (expires - now).days
        
        if days_left <= 30:
            alerts.append({
                "cert_number": s["cert_number"],
                "days_left": days_left
            })
    
    return {
        "success": True,
        "count": len(slhs_list),
        "alerts": alerts if alerts else None,
        "data": slhs_list
    }

@router.post("/slhs", response_model=Dict[str, Any],
             dependencies=[Depends(require_role(["owner", "admin"]))])
async def create_slhs_document(
    body: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_user)
):
    """Simpan dokumen SLHS baru."""
    supabase = get_supabase()
    
    insert_data = {
        "tenant_id": current_user.tenant_id,
        "cert_number": body.get("cert_number"),
        "issued_date": body.get("issued_date"),
        "expires_date": body.get("expires_date"),
        "label_expires": body.get("label_expires"),
        "file_url": body.get("file_url"),
        "status": "aktif",
        "notes": body.get("notes")
    }
    
    resp = supabase.table("slhs_documents").insert(insert_data).execute()
    data = (getattr(resp, "data", None) or [{}])[0]
    
    if not data.get("id"):
        raise HTTPException(500, detail="Gagal simpan SLHS")
    
    return {"success": True, "data": data}
```

---

##TUGAS 3: Register Router

**File:** `backend/main.py`

Tambah import + register:

```python
from routers import compliance  # ← TAMBAH

# Di bagian app.include_router():
app.include_router(compliance.router)
```

---

## TESTING CHECKLIST

- [ ] POST /compliance/hygiene → create check ✓
- [ ] GET /compliance/hygiene → list checks ✓
- [ ] POST /compliance/temperature → auto-set is_normal ✓
- [ ] GET /compliance/temperature → show alerts ✓
- [ ] POST /compliance/food-samples → auto-gen sample_code ✓
- [ ] GET /compliance/food-samples → alert hours_remaining ✓
- [ ] PATCH /compliance/food-samples/{id}/dispose ✓
- [ ] POST /compliance/food-waste → auto-calc waste_pct ✓
- [ ] GET /compliance/food-waste → summary per school ✓
- [ ] POST /compliance/incidents → auto-gen incident_code ✓
- [ ] PUT /compliance/incidents/{id} → update status ✓
- [ ] GET /compliance/slhs → check expiration ✓

---

## GIT COMMIT

```bash
git add backend/routers/compliance.py backend/models/compliance.py backend/main.py
git commit -m "feat: compliance endpoints — higiene, suhu, sampel, sisa, insiden (Modul 21.5c)"
```

**NEXT**: Tunggu 21.5c approved, lalu jalankan 21.5d + 21.5e parallel.
