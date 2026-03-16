"""
backend/routers/schedules.py
AI Jadwal Pengiriman MBG (Modul 17)

GET  /schedules/ai-draft     → draft jadwal dari Gemini (belum tersimpan)
POST /schedules/approve-draft → simpan draft ke DB
GET  /schedules/week         → ambil jadwal dari DB per minggu
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from core.config import settings
from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.user import UserInDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedules", tags=["schedules"])

# Hari libur nasional 2025-2026 (hardcoded)
NATIONAL_HOLIDAYS = {
    "2025-01-01": "Tahun Baru",
    "2025-01-27": "Isra Mikraj",
    "2025-01-29": "Tahun Baru Imlek",
    "2025-03-29": "Hari Raya Nyepi",
    "2025-03-31": "Idul Fitri",
    "2025-04-01": "Idul Fitri",
    "2025-04-18": "Wafat Isa Almasih",
    "2025-04-20": "Paskah",
    "2025-05-01": "Hari Buruh",
    "2025-05-12": "Hari Raya Waisak",
    "2025-05-29": "Kenaikan Isa Almasih",
    "2025-06-01": "Hari Lahir Pancasila",
    "2025-06-06": "Idul Adha",
    "2025-06-27": "Tahun Baru Islam",
    "2025-08-17": "HUT RI",
    "2025-09-05": "Maulid Nabi",
    "2025-12-25": "Natal",
    "2026-01-01": "Tahun Baru",
    "2026-02-17": "Isra Mikraj",
    "2026-02-18": "Tahun Baru Imlek",
    "2026-03-19": "Hari Raya Nyepi",
    "2026-03-20": "Idul Fitri",
    "2026-03-21": "Idul Fitri",
    "2026-04-03": "Wafat Isa Almasih",
    "2026-05-01": "Hari Buruh",
    "2026-05-27": "Idul Adha",
    "2026-06-01": "Hari Lahir Pancasila",
    "2026-08-17": "HUT RI",
    "2026-12-25": "Natal",
}

DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# ─── GET /schedules/week ──────────────────────────────────────────────────────

@router.get("/week", response_model=Dict[str, Any])
def get_week_schedule(
    week_start: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
):
    """Ambil jadwal minggu ini dari DB schedules."""
    supabase = get_supabase()
    tid = current_user.tenant_id
    today = date.today()

    if week_start:
        try:
            monday = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(422, "Format week_start harus YYYY-MM-DD")
    else:
        monday = today - timedelta(days=today.weekday())

    sunday = monday + timedelta(days=6)

    resp = (
        supabase.table("schedules")
        .select("*")
        .eq("tenant_id", tid)
        .eq("type", "mbg_daily")
        .gte("scheduled_date", monday.isoformat())
        .lte("scheduled_date", sunday.isoformat())
        .order("scheduled_date")
        .execute()
    )
    rows = getattr(resp, "data", None) or []

    # Group by day
    by_day: Dict[str, list] = {}
    for row in rows:
        d = row["scheduled_date"]
        by_day.setdefault(d, []).append(row)

    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        d_str = d.isoformat()
        holiday = NATIONAL_HOLIDAYS.get(d_str)
        days.append({
            "date": d_str,
            "day_name": DAY_NAMES[i],
            "is_holiday": bool(holiday),
            "holiday_name": holiday,
            "deliveries": by_day.get(d_str, []),
        })

    return {
        "success": True,
        "data": {
            "week_start": monday.isoformat(),
            "days": days,
        },
    }


# ─── GET /schedules/ai-draft ──────────────────────────────────────────────────

@router.get(
    "/ai-draft",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def get_ai_draft_schedule(
    week_start: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
):
    """Generate draft jadwal pengiriman minggu depan pakai Gemini."""
    supabase = get_supabase()
    tid = current_user.tenant_id
    today = date.today()

    if week_start:
        try:
            monday = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(422, "Format week_start harus YYYY-MM-DD (Senin)")
    else:
        # Default: Senin minggu depan
        days_ahead = (7 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        monday = today + timedelta(days=days_ahead)

    if not settings.gemini_api_key:
        return _build_fallback_draft(supabase, tid, monday)

    try:
        # Ambil data untuk Gemini
        schools_resp = (
            supabase.table("schools")
            .select("id, name, default_portions, address")
            .eq("tenant_id", tid)
            .eq("is_active", True)
            .execute()
        )
        schools = getattr(schools_resp, "data", None) or []

        if not schools:
            return _build_fallback_draft(supabase, tid, monday)

        # Ambil delivery 4 minggu terakhir
        four_weeks_ago = (today - timedelta(weeks=4)).isoformat()
        del_resp = (
            supabase.table("mbg_deliveries")
            .select("delivery_date, school_id, portions_sent")
            .eq("tenant_id", tid)
            .gte("delivery_date", four_weeks_ago)
            .order("delivery_date", desc=True)
            .execute()
        )
        deliveries = getattr(del_resp, "data", None) or []

        # Ambil menu minggu ini sebagai referensi
        this_monday = today - timedelta(days=today.weekday())
        menu_resp = (
            supabase.table("mbg_weekly_menus")
            .select("day_of_week, menu_name")
            .eq("tenant_id", tid)
            .eq("week_start", this_monday.isoformat())
            .execute()
        )
        menus = getattr(menu_resp, "data", None) or []

        # Hari libur untuk minggu depan
        week_holidays = {}
        for i in range(7):
            d = (monday + timedelta(days=i)).isoformat()
            h = NATIONAL_HOLIDAYS.get(d)
            if h:
                week_holidays[d] = h

        # Build prompt
        schools_json = json.dumps([{
            "id": s["id"], "name": s["name"], "default_portions": s.get("default_portions", 0)
        } for s in schools], ensure_ascii=False)

        data_json = json.dumps({
            "minggu_target": monday.isoformat(),
            "hari_libur": week_holidays,
            "sekolah": json.loads(schools_json),
            "menu_referensi": menus,
            "delivery_historis_ringkasan": f"{len(deliveries)} pengiriman dalam 4 minggu terakhir",
        }, ensure_ascii=False)

        prompt = f"""Buat draft jadwal pengiriman MBG minggu {monday.isoformat()}.
Data: {data_json}

Return HANYA JSON valid (tanpa teks lain):
{{
  "week_start": "{monday.isoformat()}",
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "day_name": "Senin",
      "is_holiday": false,
      "holiday_name": null,
      "deliveries": [
        {{
          "school_id": "uuid",
          "school_name": "nama sekolah",
          "portions": 100,
          "suggested_depart": "06:00",
          "suggested_arrive": "07:00",
          "notes": null
        }}
      ],
      "total_portions": 100
    }}
  ],
  "ai_notes": "catatan singkat tentang draft jadwal ini"
}}"""

        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_text_model)
        response = model.generate_content(prompt)
        raw = response.text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        if raw.endswith("```"):
            raw = raw[:-3]

        draft = json.loads(raw.strip())
        draft["from_ai"] = True
        return {"success": True, "data": draft}

    except Exception as e:
        logger.error("AI draft schedule error: %s", e)
        return _build_fallback_draft(supabase, tid, monday)


def _build_fallback_draft(supabase, tid: str, monday: date) -> Dict[str, Any]:
    """Fallback: draft dari data historis tanpa AI."""
    schools_resp = (
        supabase.table("schools")
        .select("id, name, default_portions")
        .eq("tenant_id", tid)
        .eq("is_active", True)
        .execute()
    )
    schools = getattr(schools_resp, "data", None) or []

    days = []
    for i in range(5):  # Senin-Jumat
        d = monday + timedelta(days=i)
        d_str = d.isoformat()
        holiday = NATIONAL_HOLIDAYS.get(d_str)
        deliveries = [] if holiday else [
            {
                "school_id": s["id"],
                "school_name": s["name"],
                "portions": s.get("default_portions", 0),
                "suggested_depart": "06:00",
                "suggested_arrive": "07:00",
                "notes": None,
            }
            for s in schools
        ]
        total = sum(d["portions"] for d in deliveries)
        days.append({
            "date": d_str,
            "day_name": DAY_NAMES[i],
            "is_holiday": bool(holiday),
            "holiday_name": holiday,
            "deliveries": deliveries,
            "total_portions": total,
        })

    return {
        "success": True,
        "data": {
            "week_start": monday.isoformat(),
            "days": days,
            "ai_notes": "Draft dibuat otomatis dari data sekolah. AI tidak tersedia.",
            "from_ai": False,
        },
    }


# ─── POST /schedules/approve-draft ────────────────────────────────────────────

@router.post(
    "/approve-draft",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def approve_draft_schedule(
    body: Dict[str, Any] = Body(...),
    current_user: UserInDB = Depends(get_current_user),
):
    """Simpan draft jadwal yang sudah disetujui ke tabel schedules."""
    supabase = get_supabase()
    tid = current_user.tenant_id
    uid = current_user.id

    days = body.get("days", [])
    if not days:
        raise HTTPException(400, "Tidak ada data hari dalam draft")

    # Hapus jadwal minggu yang sama dulu untuk idempotency
    week_start = body.get("week_start")
    if week_start:
        try:
            monday = date.fromisoformat(week_start)
            sunday = monday + timedelta(days=6)
            supabase.table("schedules").delete().eq("tenant_id", tid).eq("type", "mbg_daily").gte("scheduled_date", monday.isoformat()).lte("scheduled_date", sunday.isoformat()).execute()
        except Exception as e:
            logger.warning("Delete existing schedule error: %s", e)

    rows_to_insert = []
    for day in days:
        if day.get("is_holiday"):
            continue
        day_date = day.get("date")
        day_name = day.get("day_name", "")
        for delivery in day.get("deliveries", []):
            if not delivery.get("school_id"):
                continue
            depart = delivery.get("suggested_depart") or delivery.get("depart")
            title = f"MBG {day_name} - {delivery.get('school_name', '')}"
            rows_to_insert.append({
                "tenant_id": tid,
                "user_id": uid,
                "type": "mbg_daily",
                "title": title,
                "customer_name": delivery.get("school_name"),
                "description": delivery.get("notes"),
                "scheduled_date": day_date,
                "scheduled_time": depart,
                "qty": delivery.get("portions", 0),
                "status": "scheduled",
                "notes": delivery.get("notes"),
            })

    saved_count = 0
    if rows_to_insert:
        insert_resp = supabase.table("schedules").insert(rows_to_insert).execute()
        inserted = getattr(insert_resp, "data", None) or []
        saved_count = len(inserted)

    return {
        "success": True,
        "data": {
            "saved_count": saved_count,
            "week_start": week_start,
        },
    }
