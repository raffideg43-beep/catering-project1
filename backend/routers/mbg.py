"""
backend/routers/mbg.py
Endpoints untuk MBG weekly menu management — Modul 6

Routes:
  GET  /mbg/weekly-menus          → list menu 1 minggu (Senin–Sabtu)
  POST /mbg/weekly-menus          → upsert menu 1 hari
  PUT  /mbg/weekly-menus/{date}   → update menu 1 hari
  DELETE /mbg/weekly-menus/{date} → hapus menu 1 hari
  POST /mbg/weekly-menus/validate → cek produk + BOM
  GET  /mbg/weekly-menus/today    → menu hari ini (shortcut bot /serah)
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.mbg import (
    BomIngredient,
    ValidateMenuRequest,
    ValidateMenuResponse,
    WeeklyMenuCreate,
    WeeklyMenuEntry,
    WeeklyMenuUpdate,
)
from models.user import UserInDB

router = APIRouter(prefix="/weekly-menus", tags=["mbg-menus"])

# ─── Helper: nama hari Bahasa Indonesia ───

HARI = {1: "Senin", 2: "Selasa", 3: "Rabu", 4: "Kamis", 5: "Jumat", 6: "Sabtu"}


def _get_week_start(target: date) -> date:
    """Kembalikan Senin dari minggu yang mengandung target date."""
    return target - timedelta(days=target.weekday())


def _build_week_frame(week_start: date) -> List[Dict[str, Any]]:
    """Bangun frame 6 hari (Senin–Sabtu) sebagai dict kosong."""
    return [
        {
            "date": (week_start + timedelta(days=i)).isoformat(),
            "day_of_week": i + 1,
            "day_name": HARI[i + 1],
        }
        for i in range(6)
    ]


# ─── GET /mbg/weekly-menus ───────────────────────────────────────────────────

@router.get("", response_model=Dict[str, Any])
def get_weekly_menus(
    week_start: str = Query(
        default=None,
        description="Senin awal minggu format YYYY-MM-DD. Default = Senin minggu ini.",
    ),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Kembalikan list 6 hari (Senin–Sabtu) beserta menu masing-masing.
    Hari yang belum diisi memiliki menu_name=null dan is_filled=false.
    """
    supabase = get_supabase()

    # Tentukan week_start
    if week_start:
        try:
            ws = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Format week_start harus YYYY-MM-DD",
            )
    else:
        ws = _get_week_start(date.today())

    # Paksa ws selalu Senin
    ws = _get_week_start(ws)
    week_end = ws + timedelta(days=5)  # Sabtu

    # Query mbg_weekly_menus untuk minggu ini
    resp = (
        supabase.table("mbg_weekly_menus")
        .select("*")
        .eq("tenant_id", current_user.tenant_id)
        .eq("week_start", ws.isoformat())
        .execute()
    )
    db_entries: List[Dict] = getattr(resp, "data", None) or []

    # Index by day_of_week
    db_map: Dict[int, Dict] = {e["day_of_week"]: e for e in db_entries}

    # Kumpulkan semua menu_id yang ada BOM-nya
    menu_ids_with_bom: set = set()
    if db_entries:
        product_ids = [e["menu_id"] for e in db_entries if e.get("menu_id")]
        if product_ids:
            bom_resp = (
                supabase.table("recipes")
                .select("menu_id")
                .eq("tenant_id", current_user.tenant_id)
                .in_("menu_id", product_ids)
                .execute()
            )
            bom_data: List[Dict] = getattr(bom_resp, "data", None) or []
            menu_ids_with_bom = {r["menu_id"] for r in bom_data}

    # Gabungkan frame dengan data DB
    result: List[WeeklyMenuEntry] = []
    for frame in _build_week_frame(ws):
        dow = frame["day_of_week"]
        db_entry = db_map.get(dow)

        if db_entry:
            menu_id = db_entry.get("menu_id")
            result.append(
                WeeklyMenuEntry(
                    date=frame["date"],
                    day_name=frame["day_name"],
                    day_of_week=dow,
                    menu_name=db_entry.get("menu_name"),
                    menu_id=menu_id,
                    has_bom=menu_id in menu_ids_with_bom if menu_id else False,
                    is_filled=True,
                    notes=db_entry.get("notes"),
                )
            )
        else:
            result.append(
                WeeklyMenuEntry(
                    date=frame["date"],
                    day_name=frame["day_name"],
                    day_of_week=dow,
                )
            )

    return {
        "success": True,
        "week_start": ws.isoformat(),
        "week_end": week_end.isoformat(),
        "data": [e.model_dump() for e in result],
    }


# ─── GET /mbg/weekly-menus/today ─────────────────────────────────────────────

@router.get("/today", response_model=Dict[str, Any])
def get_today_menu(current_user: UserInDB = Depends(get_current_user)):
    """Shortcut: kembalikan menu hari ini. Digunakan bot saat /serah."""
    supabase = get_supabase()

    today = date.today()
    dow = today.weekday() + 1  # 1=Senin … 7=Minggu

    if dow > 6:
        return {
            "success": True,
            "data": None,
            "message": "Hari Minggu — tidak ada jadwal MBG",
        }

    ws = _get_week_start(today)

    resp = (
        supabase.table("mbg_weekly_menus")
        .select("*")
        .eq("tenant_id", current_user.tenant_id)
        .eq("week_start", ws.isoformat())
        .eq("day_of_week", dow)
        .limit(1)
        .execute()
    )
    entries: List[Dict] = getattr(resp, "data", None) or []

    if not entries:
        return {
            "success": True,
            "data": None,
            "message": f"Menu {HARI.get(dow, 'hari ini')} belum diisi",
        }

    entry = entries[0]
    menu_id = entry.get("menu_id")

    # Cek BOM
    has_bom = False
    if menu_id:
        bom_resp = (
            supabase.table("recipes")
            .select("id")
            .eq("tenant_id", current_user.tenant_id)
            .eq("menu_id", menu_id)
            .limit(1)
            .execute()
        )
        has_bom = bool(getattr(bom_resp, "data", None))

    return {
        "success": True,
        "data": WeeklyMenuEntry(
            date=today.isoformat(),
            day_name=HARI.get(dow, ""),
            day_of_week=dow,
            menu_name=entry.get("menu_name"),
            menu_id=menu_id,
            has_bom=has_bom,
            is_filled=True,
            notes=entry.get("notes"),
        ).model_dump(),
    }


# ─── POST /mbg/weekly-menus/validate ─────────────────────────────────────────

@router.post("/validate", response_model=Dict[str, Any])
def validate_menu(
    body: ValidateMenuRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Cari produk by name (ILIKE) category=produk_jadi, lalu cek BOM.
    Return: found, product {id,name}, has_bom, bom_ingredients[].
    """
    supabase = get_supabase()

    # Cari produk (case-insensitive, partial match)
    prod_resp = (
        supabase.table("products")
        .select("id, name, unit")
        .eq("tenant_id", current_user.tenant_id)
        .eq("category", "produk_jadi")
        .eq("is_active", True)
        .ilike("name", f"%{body.menu_name}%")
        .limit(1)
        .execute()
    )
    products: List[Dict] = getattr(prod_resp, "data", None) or []

    if not products:
        return {
            "success": True,
            "data": ValidateMenuResponse(
                found=False,
                product=None,
                has_bom=False,
                bom_ingredients=[],
            ).model_dump(),
        }

    product = products[0]
    product_id = product["id"]

    # Cek BOM / resep
    bom_resp = (
        supabase.table("recipes")
        .select("qty_needed, unit, products!ingredient_id(name)")
        .eq("tenant_id", current_user.tenant_id)
        .eq("menu_id", product_id)
        .execute()
    )
    bom_rows: List[Dict] = getattr(bom_resp, "data", None) or []

    bom_ingredients: List[BomIngredient] = []
    for row in bom_rows:
        ing_name = (row.get("products") or {}).get("name", "?")
        bom_ingredients.append(
            BomIngredient(
                name=ing_name,
                qty=float(row.get("qty_needed", 0)),
                unit=row.get("unit", ""),
            )
        )

    return {
        "success": True,
        "data": ValidateMenuResponse(
            found=True,
            product={"id": product_id, "name": product["name"]},
            has_bom=len(bom_ingredients) > 0,
            bom_ingredients=bom_ingredients,
        ).model_dump(),
    }


# ─── POST /mbg/weekly-menus ───────────────────────────────────────────────────

@router.post(
    "",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def upsert_weekly_menu(
    body: WeeklyMenuCreate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Upsert (insert or update) menu untuk satu hari."""
    supabase = get_supabase()

    try:
        target_date = date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Format date harus YYYY-MM-DD",
        )

    dow = target_date.weekday() + 1
    if dow > 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hari Minggu tidak termasuk jadwal MBG",
        )

    ws = _get_week_start(target_date)

    upsert_data = {
        "tenant_id": current_user.tenant_id,
        "week_start": ws.isoformat(),
        "day_of_week": dow,
        "menu_name": body.menu_name.strip(),
        "menu_id": body.menu_id,
        "notes": body.notes,
    }

    resp = (
        supabase.table("mbg_weekly_menus")
        .upsert(upsert_data, on_conflict="tenant_id,week_start,day_of_week")
        .execute()
    )

    data = getattr(resp, "data", None) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal menyimpan menu",
        )

    entry = data[0]
    return {
        "success": True,
        "data": WeeklyMenuEntry(
            date=body.date,
            day_name=HARI.get(dow, ""),
            day_of_week=dow,
            menu_name=entry.get("menu_name"),
            menu_id=entry.get("menu_id"),
            is_filled=True,
        ).model_dump(),
    }


# ─── PUT /mbg/weekly-menus/{date} ────────────────────────────────────────────

@router.put(
    "/{entry_date}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def update_weekly_menu(
    entry_date: str,
    body: WeeklyMenuUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update menu untuk satu hari yang sudah ada."""
    supabase = get_supabase()

    try:
        target_date = date.fromisoformat(entry_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Format date harus YYYY-MM-DD",
        )

    dow = target_date.weekday() + 1
    ws = _get_week_start(target_date)

    resp = (
        supabase.table("mbg_weekly_menus")
        .update({"menu_name": body.menu_name.strip(), "menu_id": body.menu_id, "notes": body.notes})
        .eq("tenant_id", current_user.tenant_id)
        .eq("week_start", ws.isoformat())
        .eq("day_of_week", dow)
        .execute()
    )

    data = getattr(resp, "data", None) or []
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry menu tidak ditemukan untuk tanggal tersebut",
        )

    entry = data[0]
    return {
        "success": True,
        "data": WeeklyMenuEntry(
            date=entry_date,
            day_name=HARI.get(dow, ""),
            day_of_week=dow,
            menu_name=entry.get("menu_name"),
            menu_id=entry.get("menu_id"),
            is_filled=True,
        ).model_dump(),
    }


# ─── DELETE /mbg/weekly-menus/{date} ─────────────────────────────────────────

@router.delete(
    "/{entry_date}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def delete_weekly_menu(
    entry_date: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """Hapus entry menu untuk satu hari."""
    supabase = get_supabase()

    try:
        target_date = date.fromisoformat(entry_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Format date harus YYYY-MM-DD",
        )

    dow = target_date.weekday() + 1
    ws = _get_week_start(target_date)

    supabase.table("mbg_weekly_menus").delete().eq(
        "tenant_id", current_user.tenant_id
    ).eq("week_start", ws.isoformat()).eq("day_of_week", dow).execute()

    return {"success": True, "message": f"Menu tanggal {entry_date} dihapus"}
