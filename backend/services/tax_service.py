from decimal import Decimal
from typing import Any, Dict

from core.config import settings


class TaxService:
    """
    Perhitungan pajak dasar (PPh22, PPN) dan alokasi harian MBG.
    Semua perhitungan uang menggunakan Decimal.
    """

    def __init__(self) -> None:
        # Konversi rate float dari settings menjadi Decimal agar perhitungan presisi.
        self._pph22_rate = Decimal(str(settings.mbg_pph22_rate))
        self._ppn_rate = Decimal(str(settings.mbg_ppn_rate))

    def calculate_pph22(self, gross_revenue: Decimal) -> Dict[str, Any]:
        pph22_amount = (gross_revenue * self._pph22_rate).quantize(Decimal("0.01"))
        net_revenue = gross_revenue - pph22_amount
        return {
            "gross_revenue": gross_revenue,
            "pph22_amount": pph22_amount,
            "net_revenue": net_revenue,
        }

    def calculate_ppn(self, amount: Decimal, is_pkp: bool) -> Dict[str, Any]:
        if is_pkp:
            ppn_amount = (amount * self._ppn_rate).quantize(Decimal("0.01"))
        else:
            ppn_amount = Decimal("0.00")
        total_with_ppn = amount + ppn_amount
        return {
            "subtotal": amount,
            "ppn_amount": ppn_amount,
            "total_with_ppn": total_with_ppn,
        }

    def calculate_daily_allocation(
        self,
        total_portions: int,
        tenant_id: str,
        supabase,
    ) -> Dict[str, Any]:
        """
        Hitung alokasi harian MBG untuk satu tenant berdasarkan mbg_allocation_settings
        terbaru; fallback ke default dari settings jika tidak ada.
        """
        # Ambil setting terbaru dari Supabase
        response = (
            supabase.table("mbg_allocation_settings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("effective_date", desc=True)
            .limit(1)
            .execute()
        )
        data = getattr(response, "data", []) or []
        row = data[0] if data else None

        if row:
            price_per_portion = Decimal(str(row.get("price_per_portion")))
            food_per_portion = Decimal(str(row.get("food_per_portion")))
            labor_per_portion = Decimal(str(row.get("labor_per_portion")))
            ops_per_portion = Decimal(str(row.get("ops_per_portion")))
        else:
            price_per_portion = Decimal(str(settings.mbg_price_per_portion))
            food_per_portion = Decimal(str(settings.mbg_price_per_portion * settings.mbg_food_allocation))
            labor_per_portion = Decimal(str(settings.mbg_price_per_portion * settings.mbg_labor_allocation))
            ops_per_portion = Decimal(str(settings.mbg_price_per_portion * settings.mbg_ops_allocation))

        portions_dec = Decimal(total_portions)
        total_revenue = (portions_dec * price_per_portion).quantize(Decimal("0.01"))
        pph22_info = self.calculate_pph22(total_revenue)
        pph22_amount = pph22_info["pph22_amount"]
        net_revenue = total_revenue - pph22_amount

        budget_food = (portions_dec * food_per_portion).quantize(Decimal("0.01"))
        budget_labor = (portions_dec * labor_per_portion).quantize(Decimal("0.01"))
        budget_ops = (portions_dec * ops_per_portion).quantize(Decimal("0.01"))

        return {
            "total_portions": total_portions,
            "price_per_portion": price_per_portion,
            "total_revenue": total_revenue,
            "pph22_amount": pph22_amount,
            "net_revenue": net_revenue,
            "budget_food": budget_food,
            "budget_labor": budget_labor,
            "budget_ops": budget_ops,
        }


tax_service = TaxService()



















