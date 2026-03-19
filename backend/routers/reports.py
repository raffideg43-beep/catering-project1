"""
backend/routers/reports.py
Endpoints laporan/dashboard — Modul 11

GET /reports/daily        → ringkasan hari ini
GET /reports/monthly      → laporan bulan ini
GET /reports/stock        → status stok semua produk
GET /reports/receivables  → piutang ke pemerintah
GET /reports/payables     → hutang ke supplier
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.database import get_supabase
from core.dependencies import get_current_user, require_role
from models.user import UserInDB

router = APIRouter(prefix="/reports", tags=["reports"])

BULAN = {
    1: "Januari", 2: "Februari", 3: "Maret",     4: "April",
    5: "Mei",     6: "Juni",     7: "Juli",        8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def _d(v, default=Decimal("0")) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return default


# ─── GET /reports/daily ───────────────────────────────────────────────────────

@router.get("/daily", response_model=Dict[str, Any])
def get_daily_report(
    date_param: str = Query(default=None, alias="date"),
    current_user: UserInDB = Depends(get_current_user),
):
    """Ringkasan hari ini: MBG, belanja, arus kas, stok alert."""
    supabase = get_supabase()
    tid = current_user.tenant_id

    try:
        target = date.fromisoformat(date_param) if date_param else date.today()
    except ValueError:
        raise HTTPException(422, detail="Format date harus YYYY-MM-DD")

    date_str = target.isoformat()

    # ─── MBG: allokasi + deliveries ──────────────────────────────────
    alloc_resp = (
        supabase.table("mbg_budget_allocations")
        .select("total_portions, total_revenue, budget_food, budget_labor, budget_ops")
        .eq("tenant_id", tid)
        .eq("date", date_str)
        .limit(1)
        .execute()
    )
    alloc_rows = getattr(alloc_resp, "data", None) or []
    alloc = alloc_rows[0] if alloc_rows else None

    del_resp = (
        supabase.table("mbg_deliveries")
        .select("id, school_id, portions_sent")
        .eq("tenant_id", tid)
        .eq("delivery_date", date_str)
        .execute()
    )
    deliveries = getattr(del_resp, "data", None) or []

    # Menu hari ini
    dow = target.weekday() + 1
    ws = target - timedelta(days=target.weekday())
    menu_resp = (
        supabase.table("mbg_weekly_menus")
        .select("menu_name")
        .eq("tenant_id", tid)
        .eq("week_start", ws.isoformat())
        .eq("day_of_week", dow)
        .limit(1)
        .execute()
    )
    menu_rows = getattr(menu_resp, "data", None) or []
    menu_name = (menu_rows[0] if menu_rows else {}).get("menu_name")

    has_delivery = bool(deliveries)
    mbg = {
        "total_portions": (alloc or {}).get("total_portions", 0),
        "total_schools": len(deliveries),
        "menu_name": menu_name,
        "revenue_gross": str(_d((alloc or {}).get("total_revenue"))),
        "budget_food": str(_d((alloc or {}).get("budget_food"))),
        "budget_labor": str(_d((alloc or {}).get("budget_labor"))),
        "budget_ops": str(_d((alloc or {}).get("budget_ops"))),
        "has_delivery": has_delivery,
    }

    # ─── Expenses: transaksi hari ini ────────────────────────────────
    exp_resp = (
        supabase.table("transactions")
        .select("id, total, suppliers(name)")
        .eq("tenant_id", tid)
        .eq("date", date_str)
        .eq("type", "expense")
        .eq("status", "confirmed")
        .execute()
    )
    exp_rows = getattr(exp_resp, "data", None) or []
    exp_total = sum(_d(r.get("total")) for r in exp_rows)

    # Group by supplier
    sup_map: Dict[str, dict] = {}
    for r in exp_rows:
        name = (r.get("suppliers") or {}).get("name") or "Tanpa Supplier"
        if name not in sup_map:
            sup_map[name] = {"supplier_name": name, "total": Decimal("0"), "count": 0}
        sup_map[name]["total"] += _d(r.get("total"))
        sup_map[name]["count"] += 1

    by_supplier = [
        {**v, "total": str(v["total"])}
        for v in sorted(sup_map.values(), key=lambda x: x["total"], reverse=True)
    ]

    expenses = {
        "total": str(exp_total),
        "count": len(exp_rows),
        "by_supplier": by_supplier,
    }

    # ─── Cashflow ─────────────────────────────────────────────────────
    cf_resp = (
        supabase.table("cashflow_log")
        .select("flow_type, amount")
        .eq("tenant_id", tid)
        .eq("date", date_str)
        .execute()
    )
    cf_rows = getattr(cf_resp, "data", None) or []
    income  = sum(_d(r["amount"]) for r in cf_rows if r.get("flow_type") == "in")
    outcome = sum(_d(r["amount"]) for r in cf_rows if r.get("flow_type") == "out")

    cashflow = {
        "income": str(income),
        "outcome": str(outcome),
        "net": str(income - outcome),
    }

    # ─── Stock alerts ─────────────────────────────────────────────────
    prod_resp = (
        supabase.table("products")
        .select("name, stock_qty, stock_min, unit")
        .eq("tenant_id", tid)
        .eq("is_active", True)
        .execute()
    )
    prod_rows = getattr(prod_resp, "data", None) or []
    stock_alerts = [
        {
            "product_name": p["name"],
            "stock_qty": float(p.get("stock_qty") or 0),
            "stock_min": float(p.get("stock_min") or 0),
            "unit": p.get("unit", ""),
            "deficit": float(max(
                _d(p.get("stock_min")) - _d(p.get("stock_qty")), Decimal("0")
            )),
        }
        for p in prod_rows
        if _d(p.get("stock_qty")) < _d(p.get("stock_min"))
    ]

    return {
        "success": True,
        "data": {
            "date": date_str,
            "mbg": mbg,
            "expenses": expenses,
            "stock_alerts": stock_alerts,
            "cashflow": cashflow,
        },
    }


# ─── GET /reports/monthly ─────────────────────────────────────────────────────

@router.get("/monthly", response_model=Dict[str, Any])
def get_monthly_report(
    year: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
):
    """Laporan bulan: MBG, pengeluaran, profit estimate, stok, status Excel."""
    supabase = get_supabase()
    tid = current_user.tenant_id
    today = date.today()
    y = year or today.year
    m = month or today.month

    # Rentang bulan
    first = date(y, m, 1)
    if m == 12:
        last = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(y, m + 1, 1) - timedelta(days=1)

    period_label = f"{BULAN[m]} {y}"

    # ─── MBG bulanan ─────────────────────────────────────────────────
    alloc_resp = (
        supabase.table("mbg_budget_allocations")
        .select("total_portions, total_revenue, date")
        .eq("tenant_id", tid)
        .gte("date", first.isoformat())
        .lte("date", last.isoformat())
        .execute()
    )
    alloc_rows = getattr(alloc_resp, "data", None) or []
    total_portions = sum(r.get("total_portions", 0) for r in alloc_rows)
    total_delivery_days = len(alloc_rows)
    revenue_gross = sum(_d(r.get("total_revenue")) for r in alloc_rows)
    avg_ppd = round(total_portions / total_delivery_days, 1) if total_delivery_days else 0

    # ─── Expenses bulanan ─────────────────────────────────────────────
    exp_resp = (
        supabase.table("transactions")
        .select("id, total, suppliers(name)")
        .eq("tenant_id", tid)
        .eq("type", "expense")
        .eq("status", "confirmed")
        .gte("date", first.isoformat())
        .lte("date", last.isoformat())
        .execute()
    )
    exp_rows = getattr(exp_resp, "data", None) or []
    exp_total = sum(_d(r.get("total")) for r in exp_rows)

    # Top suppliers
    sup_map: Dict[str, Decimal] = {}
    for r in exp_rows:
        name = (r.get("suppliers") or {}).get("name") or "Tanpa Supplier"
        sup_map[name] = sup_map.get(name, Decimal("0")) + _d(r.get("total"))
    top_suppliers = [
        {"name": k, "total": str(v)}
        for k, v in sorted(sup_map.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # Hutang outstanding bulan ini
    payable_resp = (
        supabase.table("payables")
        .select("amount")
        .eq("tenant_id", tid)
        .eq("status", "unpaid")
        .execute()
    )
    payable_rows = getattr(payable_resp, "data", None) or []
    hutang_outstanding = sum(_d(r.get("amount")) for r in payable_rows)

    # ─── Profit estimate ──────────────────────────────────────────────
    gross_profit = revenue_gross - exp_total

    # ─── Stock summary ────────────────────────────────────────────────
    prod_resp = (
        supabase.table("products")
        .select("name, stock_qty, stock_min, unit")
        .eq("tenant_id", tid)
        .eq("is_active", True)
        .execute()
    )
    prod_rows = getattr(prod_resp, "data", None) or []
    low_items = [
        {"name": p["name"], "stock_qty": float(p.get("stock_qty") or 0), "unit": p.get("unit", "")}
        for p in prod_rows
        if _d(p.get("stock_qty")) < _d(p.get("stock_min"))
    ]

    # ─── Excel status ─────────────────────────────────────────────────
    period_key = f"{y:04d}-{m:02d}"
    excel_status = "not_generated"
    try:
        excel_resp = (
            supabase.table("excel_files")
            .select("file_url")
            .eq("tenant_id", tid)
            .eq("period", period_key)
            .limit(1)
            .execute()
        )
        excel_rows = getattr(excel_resp, "data", None) or []
        excel_status = "generated" if excel_rows else "not_generated"
    except Exception as e:
        import logging
        logging.warning("Failed to fetch excel_files status: %s", e)

    return {
        "success": True,
        "data": {
            "year": y,
            "month": m,
            "period_label": period_label,
            "mbg": {
                "total_portions": total_portions,
                "total_delivery_days": total_delivery_days,
                "revenue_gross": str(revenue_gross),
                "pph22_note": "Dihitung saat generate laporan",
                "avg_portions_per_day": avg_ppd,
            },
            "expenses": {
                "total": str(exp_total),
                "count": len(exp_rows),
                "hutang_outstanding": str(hutang_outstanding),
                "top_suppliers": top_suppliers,
            },
            "profit_estimate": {
                "revenue": str(revenue_gross),
                "expenses": str(exp_total),
                "gross_profit": str(gross_profit),
                "note": "Estimasi sebelum PPh22",
            },
            "stock_summary": {
                "low_stock_count": len(low_items),
                "items": low_items,
            },
            "excel_status": excel_status,
        },
    }


# ─── GET /reports/stock ───────────────────────────────────────────────────────

@router.get("/stock", response_model=Dict[str, Any])
def get_stock_report(
    category: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
):
    """Status stok semua produk. Filter opsional by category."""
    supabase = get_supabase()
    tid = current_user.tenant_id

    q = (
        supabase.table("products")
        .select("id, name, category, unit, stock_qty, stock_min, hpp, is_active, conversion_factor")
        .eq("tenant_id", tid)
        .eq("is_active", True)
    )
    if category:
        q = q.eq("category", category)
    else:
        q = q.neq("category", "komponen").neq("category", "produk_jadi")

    resp = q.order("name").execute()
    rows = getattr(resp, "data", None) or []

    items = []
    low_count = 0
    for p in rows:
        stk = _d(p.get("stock_qty"))
        stk_min = _d(p.get("stock_min"))
        factor = float(p.get("conversion_factor") or 1)
        
        is_low = stk < stk_min
        if is_low:
            low_count += 1
            
        stk_display = float(stk / Decimal(str(factor))) if factor else float(stk)
        min_display = float(stk_min / Decimal(str(factor))) if factor else float(stk_min)

        items.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "category": p.get("category"),
            "unit": p.get("unit"),
            "stock_qty": float(stk),
            "stock_qty_display": stk_display,
            "stock_min": float(stk_min),
            "stock_min_display": min_display,
            "hpp": str(_d(p.get("hpp"))),
            "is_low_stock": is_low,
            "conversion_factor": factor,
        })

    return {
        "success": True,
        "data": {
            "total_items": len(items),
            "low_stock_count": low_count,
            "items": items,
        },
    }


# ─── GET /reports/receivables ─────────────────────────────────────────────────

@router.get(
    "/receivables",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def get_receivables_report(
    status: str = Query(default="unpaid"),
    month: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
):
    """Piutang ke pemerintah. Filter opsional by status / month / year."""
    supabase = get_supabase()
    tid = current_user.tenant_id
    today = date.today()

    q = (
        supabase.table("receivables")
        .select("id, debtor_name, amount, due_date, status, created_at")
        .eq("tenant_id", tid)
    )
    if status != "all":
        q = q.eq("status", status)
    if month and year:
        first = date(year, month, 1)
        last = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
        q = q.gte("created_at", first.isoformat()).lte("created_at", (last + timedelta(days=1)).isoformat())

    resp = q.order("due_date").execute()
    rows = getattr(resp, "data", None) or []

    total_all     = sum(_d(r.get("amount")) for r in rows)
    total_paid    = sum(_d(r.get("amount")) for r in rows if r.get("status") == "paid")
    total_unpaid  = sum(_d(r.get("amount")) for r in rows if r.get("status") != "paid")
    total_overdue_sum = Decimal("0")
    for r in rows:
        if r.get("status") != "paid" and r.get("due_date"):
            try:
                if (today - date.fromisoformat(r["due_date"])).days > 0:
                    total_overdue_sum += _d(r.get("amount"))
            except Exception:
                pass

    receivables = []
    for r in rows:
        due = r.get("due_date")
        days_overdue = 0
        if due and r.get("status") != "paid":
            try:
                diff = (today - date.fromisoformat(due)).days
                days_overdue = max(0, diff)
            except Exception:
                pass
        receivables.append({
            "id": r.get("id"),
            "debtor_name": r.get("debtor_name"),
            "amount": str(_d(r.get("amount"))),
            "pph22_note": "Belum dihitung",
            "due_date": due,
            "created_at": r.get("created_at", "")[:10],
            "status": r.get("status"),
            "days_overdue": days_overdue,
        })

    return {
        "success": True,
        "data": {
            "total_outstanding": str(total_unpaid),
            "total_all": str(total_all),
            "total_paid": str(total_paid),
            "total_overdue": str(total_overdue_sum),
            "count": len(receivables),
            "receivables": receivables,
        },
    }



# ─── GET /reports/payables ────────────────────────────────────────────────────

@router.get(
    "/payables",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
def get_payables_report(
    status: str = Query(default="unpaid"),
    month: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    supplier: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
):
    """Hutang ke supplier. Filter by status / month / year / supplier."""
    supabase = get_supabase()
    tid = current_user.tenant_id
    today = date.today()

    q = (
        supabase.table("payables")
        .select("id, supplier_name, amount, due_date, status, created_at")
        .eq("tenant_id", tid)
    )
    if status != "all":
        q = q.eq("status", status)
    if supplier:
        q = q.ilike("supplier_name", f"%{supplier}%")
    if month and year:
        first = date(year, month, 1)
        last = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
        q = q.gte("created_at", first.isoformat()).lte("created_at", (last + timedelta(days=1)).isoformat())

    try:
        resp = q.order("due_date").execute()
    except Exception as e:
        import logging
        logging.error(f"Failed to fetch payables: {e}")
        resp = None
    
    rows = getattr(resp, "data", None) or []

    total_all     = sum(_d(r.get("amount")) for r in rows)
    total_paid    = sum(_d(r.get("amount")) for r in rows if r.get("status") == "paid")
    total_unpaid  = sum(_d(r.get("amount")) for r in rows if r.get("status") != "paid")
    total_overdue_sum = Decimal("0")
    for r in rows:
        if r.get("status") != "paid" and r.get("due_date"):
            try:
                if (today - date.fromisoformat(r["due_date"])).days > 0:
                    total_overdue_sum += _d(r.get("amount"))
            except Exception:
                pass

    payables = []
    for r in rows:
        due = r.get("due_date")
        days_overdue = 0
        if due and r.get("status") != "paid":
            try:
                diff = (today - date.fromisoformat(due)).days
                days_overdue = max(0, diff)
            except Exception:
                pass
        amount = _d(r.get("amount"))
        # Fields don't exist in DB schema
        pph22  = Decimal("0")
        ppn    = Decimal("0")
        payables.append({
            "id": r.get("id"),
            "supplier_name": r.get("supplier_name"),
            "amount": str(amount),
            "pph22_amount": str(pph22),
            "ppn_amount": str(ppn),
            "total_bayar": str(amount + ppn - pph22),
            "due_date": due,
            "created_at": r.get("created_at", "")[:10],
            "status": r.get("status"),
            "days_overdue": days_overdue,
        })

    return {
        "success": True,
        "data": {
            "total_outstanding": str(total_unpaid),
            "total_all": str(total_all),
            "total_paid": str(total_paid),
            "total_overdue": str(total_overdue_sum),
            "count": len(payables),
            "payables": payables,
        },
    }


# ─── GET /reports/excel/download ──────────────────────────────────────────────

@router.get(
    "/excel/download",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
async def download_excel(
    year: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Cek status excel_files:
    - ready              → return file_url
    - pending_regenerate → generate sync → return file_url
    - not_generated      → generate sync → return file_url
    """
    import asyncio
    from services.export_service import ExportService
    supabase = get_supabase()
    tid = current_user.tenant_id
    today = date.today()
    y = year or today.year
    m = month or today.month
    period_key = f"{y:04d}-{m:02d}"

    # Hapus logika return cached file URL sesuai instruksi user
    # file_url = excel_row.get("file_url")
    # if status == "ready" and file_url:
    #     import time
    #     buster = int(time.time())
    #     file_url = f"{file_url}?t={buster}" if "?" not in file_url else f"{file_url}&t={buster}"
    #     return {"success": True, "data": {"file_url": file_url, "status": "ready"}}

    # Generate (sync — user menunggu)
    svc = ExportService()
    file_url = await svc.regenerate_monthly_excel(tid, y, m, supabase)

    if not file_url:
        raise HTTPException(500, detail="Gagal generate Excel. Cek server logs.")

    from datetime import datetime, timezone
    return {
        "success": True,
        "data": {
            "file_url": f"{file_url}?t={int(datetime.now().timestamp())}",
            "status": "ready",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


# ─── POST /reports/excel/regenerate ──────────────────────────────────────────

@router.post(
    "/excel/regenerate",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role(["owner", "admin"]))],
)
async def regenerate_excel(
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: UserInDB = Depends(get_current_user),
):
    """Generate ulang Excel bulan ini secara sync (user nunggu)."""
    from datetime import datetime, timezone
    from services.export_service import ExportService
    supabase = get_supabase()
    tid = current_user.tenant_id
    today = date.today()
    y = year or today.year
    m = month or today.month

    svc = ExportService()
    file_url = await svc.regenerate_monthly_excel(tid, y, m, supabase)

    if not file_url:
        raise HTTPException(500, detail="Gagal generate Excel. Cek server logs.")

    return {
        "success": True,
        "data": {
            "file_url": file_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }

