"""
backend/services/budget_service.py
Kalkulasi anggaran bulanan MBG: pagu, pencairan, realisasi, sisa, breakdown 80:15:5.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from core.database import get_supabase

logger = logging.getLogger(__name__)


def _d(v, default=Decimal("0")) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return default


class BudgetService:

    def get_monthly_summary(
        self, tenant_id: str, year: int, month: int
    ) -> Dict[str, Any]:
        supabase = get_supabase()

        # ── Pagu ──
        pagu_resp = (
            supabase.table("budget_allocations")
            .select("pagu_amount, notes")
            .eq("tenant_id", tenant_id)
            .eq("year", year)
            .eq("month", month)
            .limit(1)
            .execute()
        )
        pagu_rows = getattr(pagu_resp, "data", None) or []
        pagu_amount = _d(pagu_rows[0]["pagu_amount"]) if pagu_rows else Decimal("0")

        # ── Pencairan ──
        disb_resp = (
            supabase.table("fund_disbursements")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("year", year)
            .eq("month", month)
            .order("disbursement_date")
            .execute()
        )
        disbursements = getattr(disb_resp, "data", None) or []
        total_disbursed = sum(_d(d.get("amount")) for d in disbursements)

        # ── Realisasi per juknis_category ──
        first = date(year, month, 1)
        if month == 12:
            last = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(year, month + 1, 1) - timedelta(days=1)

        trx_resp = (
            supabase.table("transactions")
            .select("total, juknis_category")
            .eq("tenant_id", tenant_id)
            .eq("status", "confirmed")
            .eq("type", "expense")
            .gte("date", first.isoformat())
            .lte("date", last.isoformat())
            .execute()
        )
        trx_rows = getattr(trx_resp, "data", None) or []

        realisasi: Dict[str, Decimal] = {}
        for t in trx_rows:
            cat = t.get("juknis_category") or "lainnya"
            realisasi[cat] = realisasi.get(cat, Decimal("0")) + _d(t.get("total"))

        total_spent = sum(realisasi.values())
        sisa = total_disbursed - total_spent

        # ── Alokasi settings ──
        alloc_resp = (
            supabase.table("mbg_allocation_settings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        alloc_rows = getattr(alloc_resp, "data", None) or [{}]
        alloc = alloc_rows[0] if alloc_rows else {}
        price_pp = _d(alloc.get("price_per_portion", 15000))

        # ── Total porsi bulan ini (dan aggregasi target per porsi) ──
        ba_resp = (
            supabase.table("mbg_budget_allocations")
            .select("total_portions, budget_raw_material, budget_food, operational_salary, budget_labor, operational_fuel, operational_utilities, budget_ops, budget_kitchen_rent")
            .eq("tenant_id", tenant_id)
            .gte("date", first.isoformat())
            .lte("date", last.isoformat())
            .execute()
        )
        ba_rows = getattr(ba_resp, "data", None) or []
        total_porsi = sum(r.get("total_portions", 0) for r in ba_rows)
        
        target_bahan = Decimal("0")
        target_upah = Decimal("0")
        target_ops = Decimal("0")
        target_rent = Decimal("0")

        for r in ba_rows:
            raw_mat = _d(r.get("budget_raw_material"))
            target_bahan += raw_mat if raw_mat > 0 else _d(r.get("budget_food"))
            
            # Upah can be either operational_salary or fallback to legacy budget_labor
            upah = _d(r.get("operational_salary"))
            target_upah += upah if upah > 0 else _d(r.get("budget_labor"))
            
            # Operational is fuel + utilities OR fallback to legacy budget_ops
            fuel = _d(r.get("operational_fuel"))
            utils = _d(r.get("operational_utilities"))
            total_ops_sub = fuel + utils
            target_ops += total_ops_sub if total_ops_sub > 0 else _d(r.get("budget_ops"))
            
            target_rent += _d(r.get("budget_kitchen_rent"))

        def _breakdown(cat_key: str, target: Decimal, label: str):
            real = realisasi.get(cat_key, Decimal("0"))
            pct = float(real / target * 100) if target > 0 else 0
            return {
                "realisasi": str(real),
                "target": str(target),
                "label": label,
                "pct": round(pct, 1),
                "over_budget": real > target,
            }

        # ── Kas balances ──
        kas_balances = self.get_kas_balances(tenant_id)

        # ── Fund return ──
        fr_resp = (
            supabase.table("fund_returns")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("year", year)
            .eq("month", month)
            .limit(1)
            .execute()
        )
        fr_rows = getattr(fr_resp, "data", None) or []
        fund_return = fr_rows[0] if fr_rows else None

        return {
            "year": year,
            "month": month,
            "pagu_amount": str(pagu_amount),
            "total_disbursed": str(total_disbursed),
            "total_spent": str(total_spent),
            "sisa_anggaran": str(sisa),
            "pct_terpakai": round(
                float(total_spent / total_disbursed * 100) if total_disbursed > 0 else 0, 1
            ),
            "total_porsi": total_porsi,
            "avg_harga_porsi": str(
                round(total_spent / total_porsi, 2) if total_porsi > 0 else 0
            ),
            "kas_balances": kas_balances,
            "juknis_breakdown": {
                "bahan_pangan": _breakdown("bahan_pangan", target_bahan, "Bahan Pangan"),
                "insentif": _breakdown("insentif", target_upah, "Gaji & Upah"),
                "operasional": _breakdown("operasional", target_ops, "Operasional"),
                "sewa_dapur": {
                    "realisasi": "0.00",
                    "target": str(target_rent),
                    "label": "Sewa Dapur (Laba Bersih)",
                    "pct": 0.0,
                    "over_budget": False,
                }
            },
            "disbursements": [
                {
                    "id": d["id"],
                    "date": d.get("disbursement_date"),
                    "amount": str(_d(d.get("amount"))),
                    "reference_number": d.get("reference_number"),
                    "notes": d.get("notes"),
                }
                for d in disbursements
            ],
            "fund_return": fund_return,
        }

    def get_kas_balances(self, tenant_id: str) -> List[Dict[str, Any]]:
        supabase = get_supabase()
        resp = (
            supabase.table("kas_accounts")
            .select("id, name, type, current_balance, is_active")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        rows = getattr(resp, "data", None) or []
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "type": r["type"],
                "balance": str(_d(r.get("current_balance"))),
            }
            for r in rows
        ]


budget_service = BudgetService()
