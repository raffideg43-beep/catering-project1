"""
backend/services/export_service.py
Export Excel Pembukuan MBG — Modul 12 (implementasi penuh)

Menggantikan placeholder Modul 9.
6 sheet: Ringkasan | Penyerahan MBG | Pembelian Bahan |
         Stok Bahan | Piutang | Hutang
PPh22 & PPN dihitung HANYA di sini.
Upload ke Supabase Storage, upsert excel_files.
"""

import io
import logging
import os
from copy import copy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BULAN = {
    1: "Januari", 2: "Februari", 3: "Maret",     4: "April",
    5: "Mei",     6: "Juni",     7: "Juli",        8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "pembukuan_template.xlsx"

# ─── Konstanta styling ────────────────────────────────────────────────────────
HDR_FILL_COLOR   = "1F4E79"
ALT_ROW_COLOR    = "F2F2F2"
TOTAL_FILL_COLOR = "D6E4F0"


def _d(v, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return default


class ExportService:
    """Generate Excel pembukuan bulanan dan upload ke Supabase Storage."""

    # ─── Public: dipanggil dari BackgroundTasks atau endpoint ────────────────

    async def regenerate_monthly_excel(
        self,
        tenant_id: str,
        year: int,
        month: int,
        supabase=None,
    ) -> Optional[str]:
        """
        Buat Excel 6 sheet untuk bulan year/month, upload ke Storage.
        Return: file_url (str) atau None jika gagal.
        """
        if supabase is None:
            from core.database import get_supabase
            supabase = get_supabase()

        from core.config import settings as cfg

        # Tandai sedang diproses
        period_key = f"{year:04d}-{month:02d}"
        self._upsert_excel_files(supabase, tenant_id, period_key, status="generating")

        try:
            # 1. Ambil semua data
            data = self._fetch_all(supabase, tenant_id, year, month, cfg)

            # 2. Hitung PPh22 & PPN, update payables
            self._calculate_and_update_taxes(supabase, tenant_id, data, cfg)

            # 3. Buat workbook
            wb = self._build_workbook(data, year, month)

            # 4. Save ke buffer
            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            # 5. Upload ke Storage
            file_url = self._upload_to_storage(
                supabase, tenant_id, year, month, buffer.getvalue()
            )

            # 6. Upsert excel_files
            self._upsert_excel_files(
                supabase, tenant_id, period_key,
                status="ready", file_url=file_url
            )

            logger.info(f"Excel {period_key} tenant {tenant_id} selesai: {file_url}")
            return file_url

        except Exception as e:
            logger.error(f"regenerate_monthly_excel GAGAL: {e}")
            self._upsert_excel_files(
                supabase, tenant_id, period_key,
                status="error", error_message=str(e)[:500]
            )
            return None

    # ─── Data fetching ────────────────────────────────────────────────────────

    def _fetch_all(self, supabase, tenant_id: str, year: int, month: int, cfg) -> Dict[str, Any]:
        first = date(year, month, 1)
        if month == 12:
            last = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(year, month + 1, 1) - timedelta(days=1)

        # Tenant info
        t_resp = (
            supabase.table("tenants")
            .select("id, name")
            .eq("id", tenant_id)
            .single()
            .execute()
        )
        tenant = getattr(t_resp, "data", None) or {"id": tenant_id, "name": "SPPG"}

        # Allocation settings
        alloc_resp = (
            supabase.table("mbg_allocation_settings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        alloc_cfg = (getattr(alloc_resp, "data", None) or [{}])[0]
        price_per_portion = float(alloc_cfg.get("price_per_portion") or 15000)

        # MBG deliveries + allocations
        del_resp = (
            supabase.table("mbg_deliveries")
            .select("*, schools(name)")
            .eq("tenant_id", tenant_id)
            .gte("delivery_date", first.isoformat())
            .lte("delivery_date", last.isoformat())
            .order("delivery_date")
            .execute()
        )
        deliveries = getattr(del_resp, "data", None) or []

        ba_resp = (
            supabase.table("mbg_budget_allocations")
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("date", first.isoformat())
            .lte("date", last.isoformat())
            .execute()
        )
        allocations = {r.get("date"): r for r in (getattr(ba_resp, "data", None) or [])}

        # Weekly menus (for menu names)
        wm_resp = (
            supabase.table("mbg_weekly_menus")
            .select("week_start, day_of_week, menu_name")
            .eq("tenant_id", tenant_id)
            .gte("week_start", (first - timedelta(days=7)).isoformat())
            .lte("week_start", last.isoformat())
            .execute()
        )
        weekly_menus = getattr(wm_resp, "data", None) or []

        # Transactions + items + suppliers
        trx_resp = (
            supabase.table("transactions")
            .select("id, date, suppliers(name), supplier_id, total, payment_method, status")
            .eq("tenant_id", tenant_id)
            .eq("type", "expense")
            .eq("status", "confirmed")
            .gte("date", first.isoformat())
            .lte("date", last.isoformat())
            .order("date")
            .execute()
        )
        transactions = getattr(trx_resp, "data", None) or []

        # Items per transaction
        trx_ids = [t["id"] for t in transactions]
        items_all: List[dict] = []
        if trx_ids:
            items_resp = (
                supabase.table("transaction_items")
                .select("*")
                .in_("transaction_id", trx_ids)
                .execute()
            )
            items_all = getattr(items_resp, "data", None) or []

        # Supplier is_pkp status
        sup_ids = list({t.get("supplier_id") for t in transactions if t.get("supplier_id")})
        supplier_pkp: Dict[str, bool] = {}
        if sup_ids:
            sup_resp = (
                supabase.table("suppliers")
                .select("id, is_pkp")
                .in_("id", sup_ids)
                .execute()
            )
            supplier_pkp = {s["id"]: bool(s.get("is_pkp")) for s in (getattr(sup_resp, "data", None) or [])}

        # Products + stock history
        prod_resp = (
            supabase.table("products")
            .select("id, name, category, unit, hpp, stock_qty, stock_min")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .order("category")
            .order("name")
            .execute()
        )
        products = getattr(prod_resp, "data", None) or []

        hist_resp = (
            supabase.table("stock_history")
            .select("product_id, change_qty, reason")
            .eq("tenant_id", tenant_id)
            .gte("created_at", first.isoformat())
            .lte("created_at", (last + timedelta(days=1)).isoformat())
            .execute()
        )
        stock_history = getattr(hist_resp, "data", None) or []

        # Receivables
        recv_resp = (
            supabase.table("receivables")
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("due_date", first.isoformat())
            .lte("due_date", (last + timedelta(days=60)).isoformat())
            .order("due_date")
            .execute()
        )
        receivables = getattr(recv_resp, "data", None) or []

        # Payables
        pay_resp = (
            supabase.table("payables")
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("due_date", first.isoformat())
            .lte("due_date", (last + timedelta(days=60)).isoformat())
            .order("due_date")
            .execute()
        )
        payables = getattr(pay_resp, "data", None) or []

        return {
            "tenant": tenant,
            "first": first,
            "last": last,
            "price_per_portion": price_per_portion,
            "deliveries": deliveries,
            "allocations": allocations,
            "weekly_menus": weekly_menus,
            "transactions": transactions,
            "items_all": items_all,
            "supplier_pkp": supplier_pkp,
            "products": products,
            "stock_history": stock_history,
            "receivables": receivables,
            "payables": payables,
        }

    # ─── Tax calculation ──────────────────────────────────────────────────────

    def _calculate_and_update_taxes(self, supabase, tenant_id: str, data: dict, cfg) -> None:
        """Hitung PPh22 & PPN untuk payables yang belum dihitung, lalu update DB."""
        pph22_rate = float(getattr(cfg, "mbg_pph22_rate", 0.015))
        ppn_rate   = float(getattr(cfg, "mbg_ppn_rate", 0.11))

        for pay in data["payables"]:
            if _d(pay.get("pph22_amount")) == 0:
                amount = _d(pay.get("amount"))
                # Cek is_pkp dari supplier
                sup_id = pay.get("supplier_id")
                is_pkp = data["supplier_pkp"].get(sup_id, False) if sup_id else False
                pph22 = (amount * Decimal(str(pph22_rate))).quantize(Decimal("0.01"), ROUND_HALF_UP) if is_pkp else Decimal("0")
                ppn   = (amount * Decimal(str(ppn_rate))).quantize(Decimal("0.01"), ROUND_HALF_UP) if is_pkp else Decimal("0")
                if pph22 > 0 or ppn > 0:
                    try:
                        supabase.table("payables").update({
                            "pph22_amount": str(pph22),
                            "ppn_amount": str(ppn),
                        }).eq("id", pay["id"]).execute()
                        pay["pph22_amount"] = str(pph22)
                        pay["ppn_amount"]   = str(ppn)
                    except Exception as e:
                        logger.warning(f"update payable tax gagal: {e}")

    # ─── Workbook builder ─────────────────────────────────────────────────────

    def _build_workbook(self, data: dict, year: int, month: int):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(str(TEMPLATE_PATH))
        except Exception:
            from openpyxl import Workbook
            wb = Workbook()
            # Buat 6 sheet jika template tidak ada
            for name in ["Ringkasan", "Penyerahan MBG", "Pembelian Bahan",
                         "Stok Bahan", "Piutang", "Hutang"]:
                if name not in wb.sheetnames:
                    wb.create_sheet(name)
            if "Sheet" in wb.sheetnames:
                del wb["Sheet"]

        sheet_map = {s: wb[s] for s in wb.sheetnames if s in
                     ["Ringkasan", "Penyerahan MBG", "Pembelian Bahan",
                      "Stok Bahan", "Piutang", "Hutang"]}

        # Pastikan semua sheet ada
        for name in ["Ringkasan", "Penyerahan MBG", "Pembelian Bahan",
                     "Stok Bahan", "Piutang", "Hutang"]:
            if name not in sheet_map:
                ws = wb.create_sheet(name)
                sheet_map[name] = ws

        self._fill_ringkasan(sheet_map["Ringkasan"], data, year, month)
        self._fill_penyerahan(sheet_map["Penyerahan MBG"], data, year)
        self._fill_pembelian(sheet_map["Pembelian Bahan"], data)
        self._fill_stok(sheet_map["Stok Bahan"], data)
        self._fill_piutang(sheet_map["Piutang"], data)
        self._fill_hutang(sheet_map["Hutang"], data)

        return wb

    # ─── Sheet 1: Ringkasan ───────────────────────────────────────────────────

    def _fill_ringkasan(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        pph22_rate = Decimal("0.015")

        ws.delete_rows(1, ws.max_row)

        bulan_str = BULAN[month]
        tenant_name = data["tenant"].get("name", "SPPG")

        # Header
        ws.merge_cells("A1:G1")
        ws["A1"] = f"PEMBUKUAN CATERING MBG — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=14, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws["A1"].alignment = Alignment(horizontal="center")

        ws["A2"] = "Nama SPPG:"; ws["B2"] = tenant_name
        ws["A3"] = "Periode:"
        ws["B3"] = f"{data['first'].strftime('%d/%m/%Y')} s/d {data['last'].strftime('%d/%m/%Y')}"

        # Kalkulasi ringkasan
        deliveries = data["deliveries"]
        total_portions = sum(d.get("portions_sent", 0) for d in deliveries)
        total_days = len({d["delivery_date"] for d in deliveries})
        price_pp = Decimal(str(data["price_per_portion"]))
        revenue_gross = price_pp * total_portions
        pph22 = (revenue_gross * pph22_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        revenue_net = revenue_gross - pph22

        transactions = data["transactions"]
        total_exp = sum(_d(t.get("total")) for t in transactions)
        gross_profit = revenue_net - total_exp

        rows = [
            ("Total Porsi MBG",   f"{total_portions:,} porsi"),
            ("Total Hari Kirim",  f"{total_days} hari"),
            ("Pendapatan Kotor",  float(revenue_gross)),
            ("PPh 22 (1,5%)",    float(pph22)),
            ("Pendapatan Bersih", float(revenue_net)),
            ("Total Pengeluaran", float(total_exp)),
            ("Laba Kotor",        float(gross_profit)),
        ]

        ws["A5"] = "Keterangan"; ws["B5"] = "Jumlah"
        self._apply_header_style(ws, 5)

        for i, (label, val) in enumerate(rows, start=6):
            ws[f"A{i}"] = label
            ws[f"B{i}"] = val
            if isinstance(val, float):
                ws[f"B{i}"].number_format = '"Rp "#,##0'

        last_row = 6 + len(rows)
        ws[f"A{last_row}"] = "Catatan:"
        ws[f"B{last_row}"] = "PPh 22 dipotong langsung oleh pemerintah"
        ws[f"B{last_row}"].font = Font(italic=True, color="FF0000")

        self._set_column_widths(ws)
        ws.freeze_panes = "A6"

    # ─── Sheet 2: Penyerahan MBG ──────────────────────────────────────────────

    def _fill_penyerahan(self, ws, data: dict, year: int) -> None:
        pph22_rate = Decimal("0.015")
        ws.delete_rows(1, ws.max_row)

        headers = ["No", "Tanggal", "Sekolah", "Menu", "Porsi",
                   "Harga/Porsi", "Gross", "PPh22 (1,5%)", "Bersih"]
        self._write_headers(ws, 1, headers)

        # Build menu lookup: delivery_date → menu_name via weekly_menus
        menu_by_date: Dict[str, str] = {}
        for wm in data["weekly_menus"]:
            try:
                ws_date = date.fromisoformat(wm["week_start"])
                d = ws_date + timedelta(days=wm["day_of_week"] - 1)
                menu_by_date[d.isoformat()] = wm.get("menu_name", "—")
            except Exception:
                pass

        # Group by delivery_date + school
        row = 2
        total_gross = Decimal("0")
        total_pph22 = Decimal("0")
        total_bersih = Decimal("0")
        price_pp = Decimal(str(data["price_per_portion"]))

        for n, d in enumerate(data["deliveries"], 1):
            portions = d.get("portions_sent", 0)
            school_name = (d.get("schools") or {}).get("name", "?")
            del_date = d.get("delivery_date", "")
            menu_name = menu_by_date.get(del_date, "—")
            gross = price_pp * portions
            pph22 = (gross * pph22_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
            bersih = gross - pph22

            total_gross  += gross
            total_pph22  += pph22
            total_bersih += bersih

            ws.cell(row, 1, n)
            ws.cell(row, 2, del_date).number_format = "DD/MM/YYYY"
            ws.cell(row, 3, school_name)
            ws.cell(row, 4, menu_name)
            ws.cell(row, 5, portions)
            ws.cell(row, 6, float(price_pp)).number_format = '"Rp "#,##0'
            ws.cell(row, 7, float(gross)).number_format = '"Rp "#,##0'
            ws.cell(row, 8, float(pph22)).number_format = '"Rp "#,##0'
            ws.cell(row, 9, float(bersih)).number_format = '"Rp "#,##0'
            self._alt_row(ws, row, 2)
            row += 1

        # Total row
        self._write_total_row(ws, row, {
            5: None, 7: float(total_gross), 8: float(total_pph22), 9: float(total_bersih)
        })
        self._set_column_widths(ws)
        ws.freeze_panes = "A2"

    # ─── Sheet 3: Pembelian Bahan ─────────────────────────────────────────────

    def _fill_pembelian(self, ws, data: dict) -> None:
        pph22_rate = Decimal("0.015")
        ppn_rate   = Decimal("0.11")
        ws.delete_rows(1, ws.max_row)

        headers = ["No", "Tanggal", "Supplier", "Item", "Qty", "Satuan",
                   "Harga Satuan", "Subtotal", "PPh22", "PPN",
                   "Total Bayar", "Metode Bayar"]
        self._write_headers(ws, 1, headers)

        # Index items by transaction_id
        items_by_trx: Dict[str, List[dict]] = {}
        for item in data["items_all"]:
            tid = item.get("transaction_id", "")
            items_by_trx.setdefault(tid, []).append(item)

        row = 2
        n = 0
        tot_sub = tot_pph = tot_ppn = tot_pay = Decimal("0")

        for trx in data["transactions"]:
            tid = trx["id"]
            del_date = trx.get("date", "")
            supplier = trx.get("nama_toko") or "Tanpa Supplier"
            method = trx.get("payment_method", "tunai")
            sup_id = trx.get("supplier_id")
            is_pkp = data["supplier_pkp"].get(sup_id, False) if sup_id else False

            for item in items_by_trx.get(tid, []):
                n += 1
                nama = item.get("product_name", "?")
                qty  = float(_d(item.get("qty")))
                sat  = item.get("unit", "pcs")
                harga = float(_d(item.get("price")))
                subtotal = _d(item.get("subtotal")) or (_d(item.get("qty")) * _d(item.get("price")))
                pph22 = (subtotal * pph22_rate).quantize(Decimal("0.01")) if is_pkp else Decimal("0")
                ppn   = (subtotal * ppn_rate).quantize(Decimal("0.01")) if is_pkp else Decimal("0")
                bayar = subtotal + ppn - pph22

                tot_sub += subtotal
                tot_pph += pph22
                tot_ppn += ppn
                tot_pay += bayar

                ws.cell(row, 1, n)
                ws.cell(row, 2, del_date).number_format = "DD/MM/YYYY"
                ws.cell(row, 3, supplier)
                ws.cell(row, 4, nama)
                ws.cell(row, 5, qty)
                ws.cell(row, 6, sat)
                ws.cell(row, 7, harga).number_format = '"Rp "#,##0'
                ws.cell(row, 8, float(subtotal)).number_format = '"Rp "#,##0'
                ws.cell(row, 9, float(pph22)).number_format = '"Rp "#,##0'
                ws.cell(row, 10, float(ppn)).number_format = '"Rp "#,##0'
                ws.cell(row, 11, float(bayar)).number_format = '"Rp "#,##0'
                ws.cell(row, 12, method)
                self._alt_row(ws, row, 2)
                row += 1

        self._write_total_row(ws, row, {
            8: float(tot_sub), 9: float(tot_pph),
            10: float(tot_ppn), 11: float(tot_pay),
        })
        self._set_column_widths(ws)
        ws.freeze_panes = "A2"

    # ─── Sheet 4: Stok Bahan ──────────────────────────────────────────────────

    def _fill_stok(self, ws, data: dict) -> None:
        ws.delete_rows(1, ws.max_row)
        headers = ["No", "Nama Bahan", "Kategori", "Satuan",
                   "HPP", "Stok Awal Bulan", "Masuk", "Keluar",
                   "Stok Akhir", "Nilai Stok"]
        self._write_headers(ws, 1, headers)

        # Build net change per product
        in_by_prod:  Dict[str, Decimal] = {}
        out_by_prod: Dict[str, Decimal] = {}
        for h in data["stock_history"]:
            pid = h.get("product_id", "")
            delta = _d(h.get("change_qty"))
            if delta >= 0:
                in_by_prod[pid]  = in_by_prod.get(pid, Decimal("0"))  + delta
            else:
                out_by_prod[pid] = out_by_prod.get(pid, Decimal("0")) + abs(delta)

        row = 2
        for n, p in enumerate(data["products"], 1):
            pid = p.get("id", "")
            hpp = _d(p.get("hpp"))
            stk_akhir = _d(p.get("stock_qty"))
            masuk  = in_by_prod.get(pid, Decimal("0"))
            keluar = out_by_prod.get(pid, Decimal("0"))
            stk_awal = stk_akhir - masuk + keluar
            nilai = stk_akhir * hpp

            ws.cell(row, 1, n)
            ws.cell(row, 2, p.get("name"))
            ws.cell(row, 3, p.get("category"))
            ws.cell(row, 4, p.get("unit"))
            ws.cell(row, 5, float(hpp)).number_format = '"Rp "#,##0'
            ws.cell(row, 6, float(stk_awal))
            ws.cell(row, 7, float(masuk))
            ws.cell(row, 8, float(keluar))
            ws.cell(row, 9, float(stk_akhir))
            ws.cell(row, 10, float(nilai)).number_format = '"Rp "#,##0'
            self._alt_row(ws, row, 2)
            row += 1

        self._set_column_widths(ws)
        ws.freeze_panes = "A2"

    # ─── Sheet 5: Piutang ─────────────────────────────────────────────────────

    def _fill_piutang(self, ws, data: dict) -> None:
        pph22_rate = Decimal("0.015")
        ws.delete_rows(1, ws.max_row)
        headers = ["No", "Debitur", "Tanggal", "Jatuh Tempo",
                   "Gross", "PPh22 (1,5%)", "Bersih", "Status", "Terlambat (Hari)"]
        self._write_headers(ws, 1, headers)

        today = date.today()
        row = 2
        tot_gross = tot_pph = tot_bersih = Decimal("0")
        for n, r in enumerate(data["receivables"], 1):
            amount = _d(r.get("amount"))
            pph22  = (amount * pph22_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
            bersih = amount - pph22
            due_str = r.get("due_date", "")
            terlambat = 0
            if due_str and r.get("status") != "paid":
                try:
                    terlambat = max(0, (today - date.fromisoformat(due_str)).days)
                except Exception:
                    pass

            tot_gross  += amount
            tot_pph    += pph22
            tot_bersih += bersih

            ws.cell(row, 1, n)
            ws.cell(row, 2, r.get("debtor_name", "?"))
            ws.cell(row, 3, r.get("created_at", "")[:10]).number_format = "DD/MM/YYYY"
            ws.cell(row, 4, due_str).number_format = "DD/MM/YYYY"
            ws.cell(row, 5, float(amount)).number_format = '"Rp "#,##0'
            ws.cell(row, 6, float(pph22)).number_format = '"Rp "#,##0'
            ws.cell(row, 7, float(bersih)).number_format = '"Rp "#,##0'
            ws.cell(row, 8, r.get("status", ""))
            ws.cell(row, 9, terlambat)
            self._alt_row(ws, row, 2)
            row += 1

        self._write_total_row(ws, row, {
            5: float(tot_gross), 6: float(tot_pph), 7: float(tot_bersih)
        })
        self._set_column_widths(ws)
        ws.freeze_panes = "A2"

    # ─── Sheet 6: Hutang ──────────────────────────────────────────────────────

    def _fill_hutang(self, ws, data: dict) -> None:
        ws.delete_rows(1, ws.max_row)
        headers = ["No", "Supplier", "Tanggal", "Jatuh Tempo",
                   "Pokok", "PPh22", "PPN", "Total Bayar", "Status", "Terlambat (Hari)"]
        self._write_headers(ws, 1, headers)

        today = date.today()
        row = 2
        tot_pokok = tot_pph = tot_ppn = tot_bayar = Decimal("0")
        for n, p in enumerate(data["payables"], 1):
            amount = _d(p.get("amount"))
            pph22  = _d(p.get("pph22_amount"))
            ppn    = _d(p.get("ppn_amount"))
            bayar  = amount + ppn - pph22
            due_str = p.get("due_date", "")
            terlambat = 0
            if due_str and p.get("status") != "paid":
                try:
                    terlambat = max(0, (today - date.fromisoformat(due_str)).days)
                except Exception:
                    pass

            tot_pokok  += amount
            tot_pph    += pph22
            tot_ppn    += ppn
            tot_bayar  += bayar

            ws.cell(row, 1, n)
            ws.cell(row, 2, p.get("supplier_name", "?"))
            ws.cell(row, 3, p.get("created_at", "")[:10]).number_format = "DD/MM/YYYY"
            ws.cell(row, 4, due_str).number_format = "DD/MM/YYYY"
            ws.cell(row, 5, float(amount)).number_format = '"Rp "#,##0'
            ws.cell(row, 6, float(pph22)).number_format = '"Rp "#,##0'
            ws.cell(row, 7, float(ppn)).number_format = '"Rp "#,##0'
            ws.cell(row, 8, float(bayar)).number_format = '"Rp "#,##0'
            ws.cell(row, 9, p.get("status", ""))
            ws.cell(row, 10, terlambat)
            self._alt_row(ws, row, 2)
            row += 1

        self._write_total_row(ws, row, {
            5: float(tot_pokok), 6: float(tot_pph),
            7: float(tot_ppn), 8: float(tot_bayar),
        })
        self._set_column_widths(ws)
        ws.freeze_panes = "A2"

    # ─── Styling helpers ──────────────────────────────────────────────────────

    def _write_headers(self, ws, row: int, headers: List[str]) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        font = Font(bold=True, color="FFFFFF", size=10)
        for col, h in enumerate(headers, 1):
            c = ws.cell(row, col, h)
            c.fill = fill
            c.font = font
            c.alignment = Alignment(horizontal="center", wrap_text=True)

    def _apply_header_style(self, ws, row: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        font = Font(bold=True, color="FFFFFF")
        for cell in ws[row]:
            if cell.value is not None:
                cell.fill = fill
                cell.font = font
                cell.alignment = Alignment(horizontal="center")

    def _alt_row(self, ws, row: int, start_row: int) -> None:
        from openpyxl.styles import PatternFill
        if (row - start_row) % 2 == 1:
            fill = PatternFill("solid", fgColor=ALT_ROW_COLOR)
            for cell in ws[row]:
                cell.fill = fill

    def _write_total_row(self, ws, row: int, col_values: Dict[int, Optional[float]]) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        fill = PatternFill("solid", fgColor=TOTAL_FILL_COLOR)
        font = Font(bold=True)
        ws.cell(row, 1, "TOTAL").font = font
        ws.cell(row, 1).fill = fill
        for col, val in col_values.items():
            c = ws.cell(row, col)
            c.fill = fill
            c.font = font
            if val is not None:
                c.value = val
                c.number_format = '"Rp "#,##0'

    def _set_column_widths(self, ws) -> None:
        from openpyxl.utils import get_column_letter
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    length = len(str(cell.value or ""))
                    max_len = max(max_len, length)
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    # ─── Storage + DB ─────────────────────────────────────────────────────────

    def _upload_to_storage(
        self, supabase, tenant_id: str, year: int, month: int, content: bytes
    ) -> Optional[str]:
        file_name = f"{year}-{month:02d}_pembukuan.xlsx"
        storage_path = f"{tenant_id}/excel/{file_name}"
        bucket = "nota-photos"

        try:
            # Coba hapus dulu (overwrite)
            try:
                supabase.storage.from_(bucket).remove([storage_path])
            except Exception:
                pass

            supabase.storage.from_(bucket).upload(
                path=storage_path,
                file=content,
                file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            )
            url = supabase.storage.from_(bucket).get_public_url(storage_path)
            return url if isinstance(url, str) else str(url)
        except Exception as e:
            logger.error(f"Upload Excel gagal: {e}")
            return None

    def _upsert_excel_files(
        self, supabase, tenant_id: str, period: str,
        status: str = "generating",
        file_url: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "period": period,
            "status": status,
            "last_updated": now,
        }
        if file_url:
            row["file_url"] = file_url
        if status == "ready":
            row["generated_at"] = now
        if error_message:
            row["error_message"] = error_message

        try:
            supabase.table("excel_files").upsert(
                row, on_conflict="tenant_id,period"
            ).execute()
        except Exception as e:
            logger.warning(f"upsert excel_files gagal: {e}")


export_service = ExportService()
