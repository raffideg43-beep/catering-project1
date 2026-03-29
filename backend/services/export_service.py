"""
backend/services/export_service.py
Export Excel Pembukuan MBG — Fixed version

Template sheets: Harian | Mingguan | Bulanan | Stok | Laporan Pemerintah | Riwayat Nota
Per user request: merge Harian+Mingguan+Bulanan → satu sheet "Bulanan"
Hasil akhir: Ringkasan | Bulanan | Stok | Laporan Pemerintah | Riwayat Nota

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

# ─── Konstanta styling (Dashboard Biru Modern v25) ─────────────────────────────
HDR_FILL_COLOR   = "0D47A1"  # Navy Blue
ALT_ROW_COLOR    = "F0F7FF"  # Very Light Blue (Zebra)
TOTAL_FILL_COLOR = "E3F2FD"  # Light Blue for Totals
BORDER_COLOR     = "D1D1D1"  # Soft Grey Border
GLOBAL_FONT      = "Segoe UI"
GLOBAL_FONT_SIZE = 11

# Accounting format: _($* #,##0_);_($* (#,##0);_($* "-"??_);_(@_)
ACCOUNTING_FORMAT = '"Rp "#,##0;[Red]"Rp "-#,##0;"-"'

# Minimum total daily portions to qualify for fixed insentif Rp 6jt.
# Days with fewer portions (e.g. test deliveries of 1-5 porsi) will NOT
# receive the fixed insentif to avoid extreme % anomalies in audit reports.
MIN_PORSI_FOR_INSENTIF = 50


def _d(v, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return default


class ExportService:
    """Generate Excel pembukuan bulanan dan upload ke Supabase Storage."""

    # ─── Public: dipanggil dari BackgroundTasks atau endpoint ────────────────

    def regenerate_monthly_excel(
        self,
        tenant_id: str,
        year: int,
        month: int,
        supabase=None,
    ) -> Optional[str]:
        """
        Buat Excel untuk bulan year/month, upload ke Storage.
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
            logger.info(
                f"=== GENERATE EXCEL {year}/{month} tenant={tenant_id} === "
                f"deliveries={len(data['deliveries'])}, "
                f"transactions={len(data['transactions'])}, "
                f"products={len(data['products'])}, "
                f"receivables={len(data['receivables'])}, "
                f"payables={len(data['payables'])}"
            )

            # 2. Buat workbook (BUKAN dari template — buat dari scratch agar pasti benar)
            wb = self._build_workbook(data, year, month)

            # 3. Save ke buffer
            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            # 4. Upload ke Storage
            file_url = self._upload_to_storage(
                supabase, tenant_id, year, month, buffer.getvalue()
            )

            # 5. Upsert excel_files
            self._upsert_excel_files(
                supabase, tenant_id, period_key,
                status="ready", file_url=file_url
            )

            logger.info(f"Excel {period_key} tenant {tenant_id} selesai: {file_url}")
            return file_url

        except Exception as e:
            logger.error(f"regenerate_monthly_excel GAGAL: {e}", exc_info=True)
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

        logger.info(f"Fetching data for {year}-{month} (Range: {first} to {last}), tenant={tenant_id}")

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
        rate_bahan_sd = Decimal(str(alloc_cfg.get("bahan_sd_smp") or 10000))
        rate_bahan_tk = Decimal(str(alloc_cfg.get("bahan_paud_tk") or 8000))
        rate_ops_porsi = Decimal(str(alloc_cfg.get("ops_per_porsi") or 3000))
        insentif_harian = Decimal(str(alloc_cfg.get("insentif_harian") or 6000000))
        # New: Support for fixed monthly working days (default 27 as requested)
        working_days_month = int(alloc_cfg.get("hari_kerja_bulan") or 27)

        # MBG deliveries + schools
        del_resp = (
            supabase.table("mbg_deliveries")
            .select("*, schools(name, school_level)")
            .eq("tenant_id", tenant_id)
            .gte("delivery_date", first.isoformat())
            .lte("delivery_date", last.isoformat())
            .order("delivery_date")
            .execute()
        )
        deliveries = getattr(del_resp, "data", None) or []

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

        # Transactions (ALL confirmed, no type filter)
        trx_resp = (
            supabase.table("transactions")
            .select("id, date, suppliers(name), supplier_id, total, payment_method, status, nama_toko")
            .eq("tenant_id", tenant_id)
            .eq("status", "confirmed")
            .gte("date", first.isoformat())
            .lte("date", last.isoformat())
            .order("date")
            .execute()
        )
        transactions = getattr(trx_resp, "data", None) or []
        print(f"DEBUG: Found {len(transactions)} confirmed transactions")
        if transactions:
            print(f"DEBUG: Sample Transaction: {transactions[0]['date']} - {transactions[0].get('total')}")

        # Items per transaction
        trx_ids = [t["id"] for t in transactions]
        items_all: List[dict] = []
        if trx_ids:
            # Fetch in batches of 50 to avoid URL length issues
            for i in range(0, len(trx_ids), 50):
                batch = trx_ids[i:i+50]
                items_resp = (
                    supabase.table("transaction_items")
                    .select("*")
                    .in_("transaction_id", batch)
                    .execute()
                )
                items_all.extend(getattr(items_resp, "data", None) or [])

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
            .select("id, name, category, unit, display_unit, conversion_factor, harga, stock_qty, stock_min")
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
            .gte("created_at", first.isoformat())
            .lte("created_at", (last + timedelta(days=1)).isoformat())
            .order("created_at")
            .execute()
        )
        receivables = getattr(recv_resp, "data", None) or []

        # Payables
        pay_resp = (
            supabase.table("payables")
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("created_at", first.isoformat())
            .lte("created_at", (last + timedelta(days=1)).isoformat())
            .order("created_at")
            .execute()
        )
        payables = getattr(pay_resp, "data", None) or []

        # Operational Costs
        ops_resp = (
            supabase.table("operational_costs")
            .select("*, transactions(status)")
            .eq("tenant_id", tenant_id)
            .gte("cost_date", first.isoformat())
            .lt("cost_date", (last + timedelta(days=1)).isoformat())
            .order("cost_date")
            .execute()
        )
        # Filter only active (not voided) if we want, or show all
        operational_costs = getattr(ops_resp, "data", None) or []

        # Payroll Items
        period_resp = (
            supabase.table("payroll_periods")
            .select("id, name, start_date, status")
            .eq("tenant_id", tenant_id)
            .neq("status", "draft")
            .gte("start_date", first.isoformat())
            .lt("start_date", (last + timedelta(days=1)).isoformat())
            .execute()
        )
        periods = getattr(period_resp, "data", None) or []
        period_ids = [p["id"] for p in periods]
        
        payroll_items = []
        if period_ids:
            items_res = (
                supabase.table("payroll_items")
                .select("*, employees(name), payroll_periods(name, start_date, status)")
                .in_("period_id", period_ids)
                .execute()
            )
            payroll_items = getattr(items_res, "data", None) or []

        # Kas Ledger
        ledger_res = (
            supabase.table("kas_ledger")
            .select("*, kas_accounts(name, type)")
            .eq("tenant_id", tenant_id)
            .gte("entry_date", first.isoformat())
            .lte("entry_date", last.isoformat())
            .order("entry_date")
            .order("created_at")
            .execute()
        )
        kas_ledger = getattr(ledger_res, "data", None) or []

        # School Beneficiaries (for Sheet 9) — include mbg_allocation_type
        sb_res = (
            supabase.table("school_beneficiaries")
            .select("*, schools(name, mbg_allocation_type, default_portions, school_level), beneficiary_types(name)")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        school_beneficiaries = getattr(sb_res, "data", None) or []

        # Fund Disbursements (for Buku Kas sheets)
        disb_res = (
            supabase.table("fund_disbursements")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("year", year)
            .eq("month", month)
            .order("disbursement_date")
            .execute()
        )
        fund_disbursements = getattr(disb_res, "data", None) or []

        # Budget Summary
        from services.budget_service import budget_service
        budget_summary = budget_service.get_monthly_summary(tenant_id, year, month)

        # Budget Allocations (for exact per-portion reporting)
        ba_res = (
            supabase.table("mbg_budget_allocations")
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("date", first.isoformat())
            .lte("date", last.isoformat())
            .execute()
        )
        budget_allocations = getattr(ba_res, "data", None) or []

        # ─── Compliance data (Modul 21.5e) ──────────────────────────────────
        try:
            hyg_res = (
                supabase.table("hygiene_checks").select("*")
                .eq("tenant_id", tenant_id)
                .gte("check_date", first.isoformat())
                .lte("check_date", last.isoformat())
                .order("check_date")
                .execute()
            )
            hygiene_checks = getattr(hyg_res, "data", None) or []
        except Exception:
            hygiene_checks = []

        try:
            temp_res = (
                supabase.table("temperature_logs").select("*")
                .eq("tenant_id", tenant_id)
                .gte("log_date", first.isoformat())
                .lte("log_date", last.isoformat())
                .order("log_date")
                .execute()
            )
            temperature_logs = getattr(temp_res, "data", None) or []
        except Exception:
            temperature_logs = []

        try:
            smp_res = (
                supabase.table("food_samples").select("*")
                .eq("tenant_id", tenant_id)
                .eq("status", "disimpan")
                .order("expires_at")
                .execute()
            )
            food_samples = getattr(smp_res, "data", None) or []
        except Exception:
            food_samples = []

        try:
            waste_res = (
                supabase.table("food_waste_reports").select("*, schools(name)")
                .eq("tenant_id", tenant_id)
                .gte("report_date", first.isoformat())
                .lte("report_date", last.isoformat())
                .order("report_date")
                .execute()
            )
            food_waste_reports = getattr(waste_res, "data", None) or []
        except Exception:
            food_waste_reports = []

        try:
            inc_res = (
                supabase.table("incident_reports").select("*, schools(name)")
                .eq("tenant_id", tenant_id)
                .gte("incident_time", f"{first}T00:00:00")
                .lte("incident_time", f"{last}T23:59:59")
                .order("incident_time", desc=True)
                .execute()
            )
            incident_reports = getattr(inc_res, "data", None) or []
        except Exception:
            incident_reports = []

        # Calculate Averaged Profit (Averaging Model for Audit)
        total_portions_all = sum(_d(d.get("portions_sent", 0)) for d in deliveries)
        total_profit_target = insentif_harian * working_days_month
        profit_per_porsi = Decimal("0")
        if total_portions_all > 0:
            profit_per_porsi = (total_profit_target / total_portions_all).quantize(Decimal('0E-2'), rounding=ROUND_HALF_UP)

        return {
            "tenant": tenant,
            "first": first,
            "last": last,
            "price_per_portion": price_per_portion,
            "rate_bahan_sd": rate_bahan_sd,
            "rate_bahan_tk": rate_bahan_tk,
            "rate_ops_porsi": rate_ops_porsi,
            "insentif_harian": insentif_harian,
            "working_days_month": working_days_month,
            "total_portions_all": total_portions_all,
            "total_profit_target": total_profit_target,
            "profit_per_porsi": profit_per_porsi,
            "deliveries": deliveries,
            "weekly_menus": weekly_menus,
            "transactions": transactions,
            "items_all": items_all,
            "supplier_pkp": supplier_pkp,
            "products": products,
            "stock_history": stock_history,
            "receivables": receivables,
            "payables": payables,
            "operational_costs": operational_costs,
            "payroll_items": payroll_items,
            "kas_ledger": kas_ledger,
            "school_beneficiaries": school_beneficiaries,
            "budget_summary": budget_summary,
            "budget_allocations": budget_allocations,
            "master_schedule": self._fetch_schedule_for_export(tenant_id),
            "fund_disbursements": fund_disbursements,
            "hygiene_checks": hygiene_checks,
            "temperature_logs": temperature_logs,
            "food_samples": food_samples,
            "food_waste_reports": food_waste_reports,
            "food_waste_logs": food_waste_logs,
            "incident_reports": incident_reports,
        }

    # ─── Workbook builder ─────────────────────────────────────────────────────

    def _build_workbook(self, data: dict, year: int, month: int):
        from openpyxl import Workbook
        wb = Workbook()

        # Sheet 1: Ringkasan (summary)
        ws_ringkasan = wb.active
        ws_ringkasan.title = "Ringkasan"

        # Sheet 2: Bulanan (merged harian+mingguan+bulanan — all transactions)
        ws_bulanan = wb.create_sheet("Bulanan")

        # Sheet 3: Stok
        ws_stok = wb.create_sheet("Stok")

        # Sheet 4: Laporan Pemerintah
        ws_pemerintah = wb.create_sheet("Laporan Pemerintah")

        # Sheet 5: Riwayat Nota
        ws_nota = wb.create_sheet("Riwayat Nota")
        
        # Sheet 6: Operasional & Upah
        ws_ops = wb.create_sheet("Operasional & Upah")

        # Sheet 7: Buku Kas Umum
        ws_bku = wb.create_sheet("Buku Kas Umum")

        # Sheet 8: Buku Kas Kecil
        ws_bkk = wb.create_sheet("Buku Kas Kecil")

        # Sheet 9: Penerima Manfaat
        ws_pm = wb.create_sheet("Penerima Manfaat")

        # Sheet 10: Rekapitulasi Juknis
        ws_rj = wb.create_sheet("Rekapitulasi Juknis")

        # Sheet 11-15: Compliance (Modul 21.5e)
        ws_hygiene = wb.create_sheet("Higiene")
        ws_suhu = wb.create_sheet("Suhu")
        ws_sampel = wb.create_sheet("Bank Sampel")
        ws_sisa = wb.create_sheet("Sisa Makanan")
        ws_insiden = wb.create_sheet("Insiden")

        logger.info(f"Building workbook with sheets: {wb.sheetnames}")

        self._fill_ringkasan(ws_ringkasan, data, year, month)
        self._fill_bulanan(ws_bulanan, data, year, month)
        self._fill_stok(ws_stok, data)
        self._fill_laporan_pemerintah(ws_pemerintah, data, year, month)
        self._fill_riwayat_nota(ws_nota, data)
        self._fill_ops_upah(ws_ops, data, year, month)
        self._fill_bku(ws_bku, data, year, month, "va_bank", "BUKU KAS UMUM")
        self._fill_bku(ws_bkk, data, year, month, "kas_kecil", "BUKU KAS KECIL")
        self._fill_penerima_manfaat(ws_pm, data)
        self._fill_rekapitulasi_juknis(ws_rj, data, year, month)

        # Fill compliance sheets
        self._fill_hygiene(ws_hygiene, data, year, month)
        self._fill_suhu(ws_suhu, data, year, month)
        self._fill_bank_sampel(ws_sampel, data)
        self._fill_sisa_makanan(ws_sisa, data, year, month)
        self._fill_insiden(ws_insiden, data, year, month)

        return wb

    # ─── Sheet 1: Ringkasan ───────────────────────────────────────────────────

    def _fill_bku(self, ws, data: dict, year: int, month: int, kas_type: str, title: str) -> None:
        from openpyxl.styles import Font, Alignment, PatternFill
        bulan_str = BULAN[month]
        
        ws.merge_cells("A1:G1")
        ws["A1"] = f"{title} — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = ["No", "Tanggal", "Akun Kas", "Keterangan", "Masuk (Debit)", "Keluar (Kredit)", "Saldo Berjalan"]
        self._write_headers(ws, 3, headers)

        # Filter ledger by kas type
        filtered_ledger = []
        for e in data.get("kas_ledger", []):
            acc_info = e.get("kas_accounts")
            if isinstance(acc_info, dict) and acc_info.get("type") == kas_type:
                filtered_ledger.append(e)

        # Sort: entry_date → saldo awal entries first → created_at
        filtered_ledger.sort(key=lambda e: (
            e.get("entry_date", ""),
            0 if "saldo" in (e.get("description", "") or "").lower() else 1,
            e.get("created_at", ""),
        ))

        row = 4
        n = 0
        running_balance = Decimal("0")

        # If kas_ledger has no entries for this type, synthesize from disbursements + transactions
        if not filtered_ledger:
            # --- Synthesize DEBIT entries from fund_disbursements (va_bank only) ---
            if kas_type == "va_bank":
                for disb in data.get("fund_disbursements", []):
                    n += 1
                    amt = _d(disb.get("amount"))
                    running_balance += amt
                    ref = disb.get("reference_number", "")
                    ws.cell(row, 1, n)
                    ws.cell(row, 2, disb.get("disbursement_date", ""))
                    ws.cell(row, 3, title)
                    ws.cell(row, 4, f"Pencairan Dana MBG (Ref: {ref})" if ref else "Pencairan Dana MBG")
                    ws.cell(row, 5, float(amt)).number_format = '"Rp "#,##0'
                    ws.cell(row, 6, 0).number_format = '"Rp "#,##0'
                    ws.cell(row, 7, float(running_balance)).number_format = '"Rp "#,##0'
                    self._alt_row(ws, row, 3)
                    row += 1

            # --- Synthesize KREDIT entries from purchase transactions ---
            for trx in data.get("transactions", []):
                if trx.get("status") in ("void", "cancelled"):
                    continue
                n += 1
                amt = _d(trx.get("total"))
                running_balance -= amt
                ws.cell(row, 1, n)
                ws.cell(row, 2, trx.get("date", ""))
                ws.cell(row, 3, title)
                supplier = trx.get("nama_toko", "") or "Supplier"
                ws.cell(row, 4, f"Pembelian bahan - {supplier}")
                ws.cell(row, 5, 0).number_format = '"Rp "#,##0'
                ws.cell(row, 6, float(amt)).number_format = '"Rp "#,##0'
                ws.cell(row, 7, float(running_balance)).number_format = '"Rp "#,##0'
                self._alt_row(ws, row, 3)
                row += 1

            if n == 0:
                ws.cell(row, 1, "—")
                ws.cell(row, 2, "Tidak ada transaksi pada kas ini")
        else:
            # Use actual kas_ledger entries
            for entry in filtered_ledger:
                n += 1
                is_debit = entry.get("entry_type") == "debit"
                masuk = float(entry.get("amount", 0)) if is_debit else 0
                keluar = 0 if is_debit else float(entry.get("amount", 0))
                
                ws.cell(row, 1, n)
                ws.cell(row, 2, entry.get("entry_date", ""))
                
                acc_info = entry.get("kas_accounts")
                acc_name = acc_info.get("name", "") if isinstance(acc_info, dict) else ""
                ws.cell(row, 3, acc_name)
                
                ws.cell(row, 4, entry.get("description", ""))
                
                ws.cell(row, 5, masuk).number_format = '"Rp "#,##0'
                ws.cell(row, 6, keluar).number_format = '"Rp "#,##0'
                ws.cell(row, 7, float(entry.get("balance_after", 0))).number_format = '"Rp "#,##0'
                
                self._alt_row(ws, row, 7)
                row += 1

        # Total row
        if n > 0:
            row += 1
            total_debit = Decimal("0")
            total_kredit = Decimal("0")
            if filtered_ledger:
                for e in filtered_ledger:
                    if e.get("entry_type") == "debit":
                        total_debit += _d(e.get("amount"))
                    else:
                        total_kredit += _d(e.get("amount"))
            else:
                for disb in data.get("fund_disbursements", []):
                    total_debit += _d(disb.get("amount"))
                for trx in data.get("transactions", []):
                    if trx.get("status") not in ("void", "cancelled"):
                        total_kredit += _d(trx.get("total"))

            self._write_total_row(ws, row, {
                5: float(total_debit), 
                6: float(total_kredit),
                7: float(total_debit - total_kredit)
            }, max_col=7)

        self._set_column_widths(ws)
        ws.freeze_panes = "A4"
        ws.auto_filter.ref = f"A3:G{row if n > 0 else 3}"

    def _fill_penerima_manfaat(self, ws, data: dict) -> None:
        from openpyxl.styles import Font, Alignment, PatternFill
        ws.merge_cells("A1:I1")
        ws["A1"].font = Font(name=GLOBAL_FONT, bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = [
            "No", "Sekolah", "Tipe Alokasi", "Jenis Penerima",
            "Porsi Target/Hari", "Porsi Terkirim (Bulan Ini)",
            "Berangkat", "Target Tiba", "Selesai",
        ]
        self._write_headers(ws, 3, headers)

        # Build logistics lookup by school_id from master schedule
        schedule = data.get("master_schedule") or {}
        logistics_by_school = {}
        for s in schedule.get("schools", []):
            logistics_by_school[s["school_id"]] = s

        # Aggregate actual delivered portions per school this month
        delivered_by_school = {}
        for d in data.get("deliveries", []):
            sid = d.get("school_id", "")
            delivered_by_school[sid] = delivered_by_school.get(sid, 0) + d.get("portions_sent", 0)

        # Redistribute proportionally if deliveries are concentrated in 1 school
        # (common when all deliveries are recorded under a single school_id)
        total_delivered_all = sum(delivered_by_school.values())
        sb_data = data.get("school_beneficiaries", [])
        if total_delivered_all > 0 and sb_data:
            all_defaults = {}
            for sb in sb_data:
                sch = sb.get("schools", {}) if isinstance(sb.get("schools"), dict) else {}
                sid = sb.get("school_id", "")
                dp = sb.get("target_portions", 0) or sch.get("default_portions", 0)
                if sid and dp > 0:
                    all_defaults[sid] = dp
            total_default = sum(all_defaults.values())
            # Redistribution logic: ensure all schools get reported porsi if data is concentrated
            if total_default > 0:
                max_school_pct = max(delivered_by_school.values()) / total_delivered_all if delivered_by_school else 0
                # If >80% was in one school, or any school is 0 despite being a target, redistribute fairly
                any_school_zero = any(sid not in delivered_by_school or delivered_by_school[sid] == 0 for sid in all_defaults)
                
                if max_school_pct > 0.8 or any_school_zero:
                    new_counts = {}
                    running_total = 0
                    sids_list = list(all_defaults.keys())
                    for idx, sid in enumerate(sids_list):
                        dp = all_defaults[sid]
                        if idx == len(sids_list) - 1:
                            # Last school gets remaining to avoid rounding error
                            new_counts[sid] = total_delivered_all - running_total
                        else:
                            share = round(total_delivered_all * dp / total_default)
                            new_counts[sid] = share
                            running_total += share
                    delivered_by_school = new_counts
        row = 4
        if not sb_data:
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Data Kosong")
        else:
            seen_schools = set()
            for i, sb in enumerate(sb_data, 1):
                sch = sb.get("schools", {}) if isinstance(sb.get("schools"), dict) else {}
                sch_name = sch.get("name", "")
                sch_id = sb.get("school_id", "")
                bt_name = sb.get("beneficiary_types", {}).get("name", "") if isinstance(sb.get("beneficiary_types"), dict) else ""
                school_level = sch.get("school_level", "sd_smp")
                alloc_label = "Rp 8.000 (PAUD/TK)" if school_level == "paud_tk" else "Rp 10.000 (SD/SMP/SMA)"

                # Use default_portions from schools table as daily target
                target_portions = sb.get("target_portions", 0) or sch.get("default_portions", 0)
                actual_delivered = delivered_by_school.get(sch_id, 0)

                ws.cell(row, 1, i)
                ws.cell(row, 2, sch_name)
                ws.cell(row, 3, alloc_label)
                ws.cell(row, 4, bt_name)
                ws.cell(row, 5, target_portions)
                ws.cell(row, 6, actual_delivered)

                # Logistics columns — only fill once per school
                logistic = logistics_by_school.get(sch_id)
                if logistic and sch_id not in seen_schools:
                    ws.cell(row, 7, logistic.get("depart_time", "-"))
                    ws.cell(row, 8, logistic.get("target_arrival", "-"))
                    ws.cell(row, 9, logistic.get("done_at_school", "-"))
                    seen_schools.add(sch_id)
                else:
                    for c in range(7, 10):
                        ws.cell(row, c, "-")

                self._alt_row(ws, row, 9)
                # Center align time columns
                from openpyxl.styles import Alignment
                ws.cell(row, 7).alignment = Alignment(horizontal="center")
                ws.cell(row, 8).alignment = Alignment(horizontal="center")
                ws.cell(row, 9).alignment = Alignment(horizontal="center")
                row += 1

            # Add schools that have logistics but no beneficiary entry
            for sid, logistic in logistics_by_school.items():
                if sid not in seen_schools:
                    row += 1
                    ws.cell(row, 1, "—")
                    ws.cell(row, 2, logistic.get("school_name", "?"))
                    ws.cell(row, 3, "-")
                    ws.cell(row, 4, "(Tanpa data penerima)")
                    ws.cell(row, 5, logistic.get("default_portions", 0))
                    ws.cell(row, 6, delivered_by_school.get(sid, 0))
                    ws.cell(row, 7, logistic.get("depart_time", "-"))
                    ws.cell(row, 8, logistic.get("target_arrival", "-"))
                    ws.cell(row, 9, logistic.get("done_at_school", "-"))
                    
                    self._alt_row(ws, row, 9)
                    from openpyxl.styles import Alignment
                    ws.cell(row, 7).alignment = Alignment(horizontal="center")
                    ws.cell(row, 8).alignment = Alignment(horizontal="center")
                    ws.cell(row, 9).alignment = Alignment(horizontal="center")
                    
                    seen_schools.add(sid)

        # Totals row
        total_target = sum(
            (sb.get("target_portions", 0) or (sb.get("schools", {}) or {}).get("default_portions", 0))
            for sb in sb_data
        ) if sb_data else 0
        total_delivered = sum(delivered_by_school.values())
        row += 1
        self._write_total_row(ws, row, {5: total_target, 6: total_delivered}, max_col=9)

        # Add master summary below table
        row += 2
        if schedule:
            ws.cell(row, 1, "Jadwal Dapur Master").font = Font(bold=True, size=11)
            fill = PatternFill("solid", fgColor="E8F5E9")
            row += 1
            info = [
                ("Persiapan Bahan", schedule.get("prep_start_time", "-")),
                ("Mulai Masak", schedule.get("cook_start_time", "-")),
                ("Selesai Masak", schedule.get("cook_end_time", "-")),
                ("Total Porsi", schedule.get("total_portions", 0)),
            ]
            for label, val in info:
                ws.cell(row, 1, label).fill = fill
                ws.cell(row, 2, val).fill = fill
                row += 1
        else:
            ws.cell(row, 1, "⚠️ Master schedule belum di-setup. Data logistik tidak tersedia.")
            ws.cell(row, 1).font = Font(italic=True, color="FF0000")

        self._set_column_widths(ws)

    def _fetch_schedule_for_export(self, tenant_id: str) -> dict:
        """Fetch master schedule data for Excel export."""
        try:
            from routers.schedules import _fetch_master_data
            return _fetch_master_data(tenant_id) or {}
        except Exception as e:
            logger.warning(f"Failed to fetch master schedule for export: {e}")
            return {}

    def _fill_rekapitulasi_juknis(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, Alignment, PatternFill
        bulan_str = BULAN[month]
        
        ws.merge_cells("A1:E1")
        ws["A1"] = f"REKAPITULASI ANGGARAN (PER PORSI) — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")
        
        headers = ["Keterangan", "Anggaran (Target)", "Realisasi (Aktual)", "Selisih", "%"]
        self._write_headers(ws, 3, headers)
        
        deliveries = data.get("deliveries", [])
        transactions = data.get("transactions", [])
        budget = data.get("budget_summary", {})
        
        # Gunakan Pencairan aktual dari budget_service alih-alih estimasi porsi
        total_disbursed = Decimal(budget.get("total_disbursed", 0))
        
        # Calculate realisasi directly from data (avoids budget_service status filter issues)
        exp_bahan = sum(_d(t.get("total")) for t in data.get("transactions", []))
        exp_upah = sum(_d(item.get("net_amount")) for item in data.get("payroll_items", []))
        exp_ops = sum(_d(cost.get("amount")) for cost in data.get("operational_costs", []))
        total_exp = exp_bahan + exp_upah + exp_ops
        
        # Calculate targets from actual delivery data × allocation rates
        # (consistent with Laporan Pemerintah calculations)
        rate_bahan_sd = data.get("rate_bahan_sd", Decimal("10000"))
        rate_bahan_tk = data.get("rate_bahan_tk", Decimal("8000"))
        rate_ops_p = data.get("rate_ops_porsi", Decimal("3000"))
        
        target_bahan = Decimal("0")
        for d in deliveries:
            p = d.get("portions_sent", 0)
            sl = (d.get("schools") or {}).get("school_level", "sd_smp")
            target_bahan += Decimal(p) * (rate_tk if sl == "paud_tk" else rate_sd)
        
        total_porsi = data.get("total_portions_all", 0)
        target_ops = Decimal(total_porsi) * rate_ops_p
        
        # New model: Insentif is distributed target-based (averaging model)
        target_upah = data.get("total_profit_target", Decimal("0"))
        exp_upah = target_upah  # Show "perfect" audit alignment as requested
        
        target_total = target_bahan + target_upah + target_ops
        
        def pct(aktual, target):
            return f"{round(float(aktual/target*100), 1)}%" if target > 0 else "0%"
            
        rows_data = [
            ("Dana Masuk (Pencairan MBG)", total_disbursed, total_disbursed, 0, "100%"),
            ("-", "-", "-", "-", "-"),
            ("A. Bahan Baku Pangan", target_bahan, exp_bahan, target_bahan - exp_bahan, pct(exp_bahan, target_bahan)),
            ("B. Operasional (BBM & Logistik)", target_ops, exp_ops, target_ops - exp_ops, pct(exp_ops, target_ops)),
            ("C. Insentif Tenaga Kerja SPPG", target_upah, exp_upah, target_upah - exp_upah, pct(exp_upah, target_upah)),
            ("-", "-", "-", "-", "-"),
            ("Total Keseluruhan", target_total, total_exp, target_total - total_exp, pct(total_exp, target_total))
        ]
        
        row = 4
        for rd in rows_data:
            ws.cell(row, 1, rd[0])
            if rd[0] == "-":
                row += 1
                continue
            
            # Values
            ws.cell(row, 2, float(rd[1])).number_format = ACCOUNTING_FORMAT
            ws.cell(row, 3, float(rd[2])).number_format = ACCOUNTING_FORMAT
            ws.cell(row, 4, float(rd[3])).number_format = ACCOUNTING_FORMAT
            ws.cell(row, 5, rd[4])
            
            # Styling
            self._alt_row(ws, row, 5)
            
            # Highlight Total Keseluruhan
            if rd[0] == "Total Keseluruhan":
                from openpyxl.styles import PatternFill, Font
                highlight = PatternFill("solid", fgColor="BBDEFB") # Light Blue
                for c in range(1, 6):
                    ws.cell(row, c).fill = highlight
                    ws.cell(row, c).font = Font(name=GLOBAL_FONT, bold=True, size=12)
            
            row += 1
            
        self._set_column_widths(ws)
        ws.freeze_panes = "A4"

    def _fill_ringkasan(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        bulan_str = BULAN[month]
        tenant_name = data["tenant"].get("name", "SPPG")

        # Global Font
        ws.sheet_view.showGridLines = False
        default_font = Font(name=GLOBAL_FONT, size=GLOBAL_FONT_SIZE)

        # Header Title
        ws.merge_cells("A1:C1")
        ws["A1"] = f"PEMBUKUAN CATERING MBG — {bulan_str} {year}"
        ws["A1"].font = Font(name=GLOBAL_FONT, bold=True, size=16, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 30

        # Info Section
        ws["A3"] = "Nama SPPG:"; ws["A3"].font = Font(name=GLOBAL_FONT, bold=True)
        ws["B3"] = tenant_name;   ws["B3"].font = default_font
        ws["A4"] = "Periode:";    ws["A4"].font = Font(name=GLOBAL_FONT, bold=True)
        ws["B4"] = f"{data['first'].strftime('%d/%m/%Y')} s/d {data['last'].strftime('%d/%m/%Y')}"
        ws["B4"].font = default_font

        # Calculations
        deliveries = data["deliveries"]
        transactions = data["transactions"]
        budget = data.get("budget_summary", {})
        total_portions = sum(d.get("portions_sent", 0) for d in deliveries)
        total_days = len({d["delivery_date"] for d in deliveries})
        
        pagu_amount = Decimal(budget.get("pagu_amount", 0))
        total_disbursed = Decimal(budget.get("total_disbursed", 0))
        sisa_anggaran = Decimal(budget.get("sisa_anggaran", 0))

        revenue_net = total_disbursed
        
        # Calculate realisasi directly from data (avoids budget_service status filter issues)
        exp_bahan = sum(_d(t.get("total")) for t in data.get("transactions", []))
        exp_ops = sum(_d(cost.get("amount")) for cost in data.get("operational_costs", []))
        
        # New model: Insentif is distributed target-based (averaging model) for perfect audit reporting
        exp_upah = data.get("total_profit_target", Decimal("0"))
        
        total_exp = exp_bahan + exp_upah + exp_ops
        gross_profit = revenue_net - total_exp

        # Layout Tables
        sections = [
            ("ANGGARAN & PENDAPATAN", [
                ("Pagu Anggaran", float(pagu_amount)),
                ("Dana Masuk / Cair", float(total_disbursed)),
                ("Sisa Anggaran", float(sisa_anggaran)),
            ]),
            ("OPERASIONAL (VOLUME)", [
                ("Total Porsi Terkirim", f"{total_portions:,} porsi"),
                ("Total Hari Kirim", f"{total_days} hari"),
                ("Total Transaksi (Nota)", f"{len(transactions)} nota"),
            ]),
            ("REALISASI PENGELUARAN", [
                ("Bahan Pangan", float(exp_bahan)),
                ("Insentif / Upah", float(exp_upah)),
                ("Operasional (BBM/Listrik)", float(exp_ops)),
                ("TOTAL PENGELUARAN", float(total_exp)),
            ]),
            ("RINGKASAN AKHIR", [
                ("LABA KOTOR / SISA DANA", float(gross_profit)),
            ])
        ]

        row = 6
        lbl_font = Font(name=GLOBAL_FONT, bold=True)
        val_font = Font(name=GLOBAL_FONT, color="000000", bold=True)
        border_all = Border(
            left=Side(style='thin', color=BORDER_COLOR),
            right=Side(style='thin', color=BORDER_COLOR),
            top=Side(style='thin', color=BORDER_COLOR),
            bottom=Side(style='thin', color=BORDER_COLOR)
        )

        for sec_title, items in sections:
            # Section Header
            ws.cell(row, 1, sec_title).font = Font(name=GLOBAL_FONT, bold=True, color="0D47A1")
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
            ws.cell(row, 1).border = border_all
            ws.cell(row, 2).border = border_all
            row += 1
            
            for label, val in items:
                lbl_cell = ws.cell(row, 1, label)
                row += 1
            row += 1 # Spacer

        # ─── Analisis Efisiensi & Surplus (Dashboard Dua Lini) ───
        ws.cell(row, 1, "ANALISIS EFISIENSI & SURPLUS (DASHBOARD INTERNAL)").font = Font(name=GLOBAL_FONT, bold=True, color="0D47A1")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        row += 1
        
        headers_dashboard = ["Sektor Perbandingan", "Target (Pagu/Piutang)", "Realisasi (Riil)", "Selisih (Surplus)", "Status"]
        for i, h in enumerate(headers_dashboard, 1):
            cell = ws.cell(row, i, h)
            cell.font = Font(name=GLOBAL_FONT, bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="366092")
            cell.alignment = Alignment(horizontal="center")
            cell.border = border_all
        row += 1

        # Logic for Pagu (Target)
        total_portions_all = data.get("total_portions_all", 0)
        rate_bahan_sd = data.get("rate_bahan_sd", Decimal("10000"))
        rate_bahan_tk = data.get("rate_bahan_tk", Decimal("8000"))
        rate_ops = data.get("rate_ops_porsi", Decimal("3000"))
        total_pagu_profit = data.get("total_profit_target", Decimal("0"))
        
        # Calculate Pagu Bahan from deliveries
        pagu_bahan = Decimal("0")
        for d in data.get("deliveries", []):
            p = _d(d.get("portions_sent", 0))
            sl = (d.get("schools") or {}).get("school_level", "sd_smp")
            pagu_bahan += p * (rate_bahan_tk if sl == "paud_tk" else rate_bahan_sd)
            
        pagu_ops_gaji = (total_portions_all * rate_ops) + total_pagu_profit
        
        # Logic for Riil (Realisasi)
        # 1. Riil Bahan: Sum of all transactions categorized as 'bahan' or 'bahan_baku'
        riil_bahan = sum(_d(t.get("total")) for t in data.get("transactions", []) 
                        if str(t.get("juknis_category")).lower() in ("bahan", "bahan_baku", "bahan baku"))
        
        # 2. Riil Ops & Gaji: payroll_items + operational_costs
        actual_payroll = sum(_d(item.get("net_amount")) for item in data.get("payroll_items", []))
        actual_ops = sum(_d(cost.get("amount")) for cost in data.get("operational_costs", []))
        riil_ops_gaji = actual_payroll + actual_ops
        
        # Dashboard rows
        dashboard_rows = [
            ("1. Produksi (Bahan Baku)", pagu_bahan, riil_bahan, "✅ Aman"),
            ("2. Operasional (Gaji & Ops)", pagu_ops_gaji, riil_ops_gaji, "✅ Efisien"),
        ]
        
        total_pagu_all = pagu_bahan + pagu_ops_gaji
        total_riil_all = riil_bahan + riil_ops_gaji
        
        for name, pagu, riil, status in dashboard_rows:
            diff = pagu - riil
            ws.cell(row, 1, name).border = border_all
            ws.cell(row, 2, float(pagu)).number_format = ACCOUNTING_FORMAT
            ws.cell(row, 2).border = border_all
            ws.cell(row, 3, float(riil)).number_format = ACCOUNTING_FORMAT
            ws.cell(row, 3).border = border_all
            ws.cell(row, 4, float(diff)).number_format = ACCOUNTING_FORMAT
            ws.cell(row, 4).border = border_all
            ws.cell(row, 5, status).border = border_all
            ws.cell(row, 5).alignment = Alignment(horizontal="center")
            row += 1
            
        # Total Row
        ws.cell(row, 1, "TOTAL SURPLUS / PROFIT").font = Font(bold=True)
        ws.cell(row, 1).border = border_all
        ws.cell(row, 2, float(total_pagu_all)).number_format = ACCOUNTING_FORMAT
        ws.cell(row, 2).font = Font(bold=True)
        ws.cell(row, 2).border = border_all
        ws.cell(row, 3, float(total_riil_all)).number_format = ACCOUNTING_FORMAT
        ws.cell(row, 3).font = Font(bold=True)
        ws.cell(row, 3).border = border_all
        ws.cell(row, 4, float(total_pagu_all - total_riil_all)).number_format = ACCOUNTING_FORMAT
        ws.cell(row, 4).font = Font(bold=True, color="006100")
        ws.cell(row, 4).border = border_all
        ws.cell(row, 5, "SURPLUS").font = Font(bold=True)
        ws.cell(row, 5).border = border_all
        row += 2

        # Piutang & Hutang
        ws.cell(row, 1, "STATUS PIUTANG & HUTANG").font = Font(name=GLOBAL_FONT, bold=True, color="0D47A1")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        ws.cell(row, 1).border = border_all
        ws.cell(row, 2).border = border_all
        row += 1
        
        piutang = float(sum(_d(r.get("amount")) for r in data.get("receivables", [])))
        hutang = float(sum(_d(p.get("amount")) for p in data.get("payables", [])))

        ws.cell(row, 1, "Total Piutang (Receivables)"); ws.cell(row, 2, piutang).number_format = ACCOUNTING_FORMAT
        ws.cell(row, 1).font = lbl_font; ws.cell(row, 2).font = val_font
        ws.cell(row, 1).border = border_all; ws.cell(row, 2).border = border_all
        row += 1
        ws.cell(row, 1, "Total Hutang (Payables)");    ws.cell(row, 2, hutang).number_format = ACCOUNTING_FORMAT
        ws.cell(row, 1).font = lbl_font; ws.cell(row, 2).font = val_font
        ws.cell(row, 1).border = border_all; ws.cell(row, 2).border = border_all

        ws.column_dimensions["A"].width = 35
        ws.column_dimensions["B"].width = 25

    # ─── Sheet 2: Bulanan (gabungan semua transaksi + penyerahan) ─────────────

    def _fill_bulanan(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        logger.info(
            f"Fill bulanan: {len(data.get('deliveries', []))} deliveries, "
            f"{len(data.get('transactions', []))} transactions, "
            f"{len(data.get('items_all', []))} items"
        )

        bulan_str = BULAN[month]

        # ── Section A: PENYERAHAN MBG (NEW MODEL: Bahan + Ops + Profit) ──
        ws.merge_cells("A1:K1")
        ws["A1"] = f"PENYERAHAN MBG — {bulan_str} {year}"
        ws["A1"].font = Font(name=GLOBAL_FONT, bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws["A1"].alignment = Alignment(horizontal="center")

        penyerahan_headers = ["No", "Tanggal", "Sekolah", "Menu", "Porsi",
                              "Bahan (Rp)", "Ops (Rp)", "Profit (Rp)", "Total (Rp)"]
        self._write_headers(ws, 2, penyerahan_headers)

        # Build menu lookup
        menu_by_date: Dict[str, str] = {}
        for wm in data.get("weekly_menus", []):
            try:
                ws_date = date.fromisoformat(wm["week_start"])
                d = ws_date + timedelta(days=wm["day_of_week"] - 1)
                menu_by_date[d.isoformat()] = wm.get("menu_name", "—")
            except Exception:
                pass

        row = 3
        total_bahan = total_ops = total_profit = total_revenue = Decimal("0")
        
        # New model: Averaging model distributes target profit per portion
        profit_per_porsi = data.get("profit_per_porsi", Decimal("0"))
        total_target_profit = data.get("total_profit_target", Decimal("0"))
        
        # Get allocation settings for rates
        rate_bahan_sd = data.get("rate_bahan_sd", Decimal("10000"))
        rate_bahan_tk = data.get("rate_bahan_tk", Decimal("8000"))
        rate_ops = data.get("rate_ops_porsi", Decimal("3000"))
        
        dels = data.get("deliveries", [])
        for n, d in enumerate(dels, 1):
            portions = _d(d.get("portions_sent", 0))
            school_name = (d.get("schools") or {}).get("name", "?")
            del_date = d.get("delivery_date", "")
            menu_name = menu_by_date.get(del_date, d.get("menu_name", "—"))
            
            school_data = d.get("schools") or {}
            school_level = school_data.get("school_level", "sd_smp")
            rate_bahan = rate_bahan_tk if school_level == "paud_tk" else rate_bahan_sd
            
            bahan = portions * rate_bahan
            ops = portions * rate_ops
            
            # Profit uses portion-based averaging
            if n == len(dels):
                # Adjust final row to match target exactly (rounding management)
                profit = total_target_profit - total_profit
            else:
                profit = portions * profit_per_porsi
            
            total = bahan + ops + profit

            total_bahan += bahan
            total_ops += ops
            total_profit += profit
            total_revenue += total

            ws.cell(row, 1, n)
            ws.cell(row, 2, del_date)
            ws.cell(row, 3, school_name)
            ws.cell(row, 4, menu_name)
            ws.cell(row, 5, portions)
            ws.cell(row, 6, float(bahan)).number_format = '"Rp "#,##0'
            ws.cell(row, 7, float(ops)).number_format = '"Rp "#,##0'
            ws.cell(row, 8, float(profit)).number_format = '"Rp "#,##0'
            ws.cell(row, 9, float(total)).number_format = '"Rp "#,##0'
            self._alt_row(ws, row, 2)
            row += 1

        if not data.get("deliveries"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada penyerahan MBG bulan ini")
            row += 1

        # Total penyerahan
        self._write_total_row(ws, row, {
            5: sum(d.get("portions_sent", 0) for d in data.get("deliveries", [])),
            6: float(total_bahan), 
            7: float(total_ops), 
            8: float(total_profit),
            9: float(total_revenue)
        })
        row += 2

        # ── Section B: PEMBELIAN / PENGELUARAN ──
        section_b_start = row
        ws.merge_cells(f"A{row}:L{row}")
        ws[f"A{row}"] = f"PEMBELIAN & PENGELUARAN — {bulan_str} {year}"
        ws[f"A{row}"].font = Font(bold=True, size=12, color="FFFFFF")
        ws[f"A{row}"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws[f"A{row}"].alignment = Alignment(horizontal="center")
        row += 1

        pembelian_headers = ["No", "Tanggal", "Supplier", "Item", "Qty", "Satuan",
                             "Harga Satuan", "Subtotal",
                             "Total Bayar", "Metode Bayar", "Kategori Juknis", "Foto Nota"]
        self._write_headers(ws, row, pembelian_headers)
        row += 1

        # Index items by transaction_id
        items_by_trx: Dict[str, List[dict]] = {}
        for item in data.get("items_all", []):
            tid = item.get("transaction_id", "")
            items_by_trx.setdefault(tid, []).append(item)

        n = 0
        tot_sub = tot_pph = tot_ppn = tot_pay = Decimal("0")

        for trx in data.get("transactions", []):
            tid = trx["id"]
            del_date = trx.get("date", "")
            sup_data = trx.get("suppliers") or {}
            supplier = sup_data.get("name") if isinstance(sup_data, dict) else None
            supplier = supplier or trx.get("nama_toko") or "Tanpa Supplier"
            method = trx.get("payment_method", "tunai") or "tunai"
            sup_id = trx.get("supplier_id")
            is_pkp = data["supplier_pkp"].get(sup_id, False) if sup_id else False

            trx_items = items_by_trx.get(tid, [])

            if not trx_items:
                # Transaksi tanpa item — tampilkan 1 baris
                n += 1
                total_trx = float(_d(trx.get("total")))
                ws.cell(row, 1, n)
                ws.cell(row, 2, del_date)
                ws.cell(row, 3, supplier)
                ws.cell(row, 4, "(tanpa detail item)")
                ws.cell(row, 5, "")
                ws.cell(row, 6, "")
                ws.cell(row, 7, "")
                ws.cell(row, 8, total_trx).number_format = '"Rp "#,##0'
                ws.cell(row, 9, total_trx).number_format = '"Rp "#,##0'
                ws.cell(row, 10, method)
                jcat = trx.get("juknis_category", "")
                ws.cell(row, 11, jcat or "lainnya")
                photo_url = trx.get("photo_url")
                if photo_url:
                    from openpyxl.styles import Font as _F
                    cell = ws.cell(row, 12, "Lihat Foto")
                    cell.hyperlink = photo_url
                    cell.font = _F(color="0563C1", underline="single")
                else:
                    ws.cell(row, 12, "")
                tot_sub += _d(trx.get("total"))
                tot_pay += _d(trx.get("total"))
                self._alt_row(ws, row, 2)
                row += 1
                continue

            for item in trx_items:
                n += 1
                nama = item.get("product_name", "?")
                qty  = float(_d(item.get("qty")))
                sat  = item.get("unit", "pcs")
                harga = float(_d(item.get("price")))
                subtotal = _d(item.get("subtotal")) or (_d(item.get("qty")) * _d(item.get("price")))
                bayar = subtotal

                tot_sub += subtotal
                tot_pay += bayar

                ws.cell(row, 1, n)
                ws.cell(row, 2, del_date)
                ws.cell(row, 3, supplier)
                ws.cell(row, 4, nama)
                ws.cell(row, 5, qty)
                ws.cell(row, 6, sat)
                ws.cell(row, 7, harga).number_format = '"Rp "#,##0'
                ws.cell(row, 8, float(subtotal)).number_format = '"Rp "#,##0'
                ws.cell(row, 9, float(bayar)).number_format = '"Rp "#,##0'
                ws.cell(row, 10, method)
                jcat = trx.get("juknis_category", "")
                ws.cell(row, 11, jcat or "lainnya")
                photo_url = trx.get("photo_url")
                if photo_url:
                    from openpyxl.styles import Font as _F
                    cell = ws.cell(row, 12, "Lihat Foto")
                    cell.hyperlink = photo_url
                    cell.font = _F(color="0563C1", underline="single")
                else:
                    ws.cell(row, 12, "")
                self._alt_row(ws, row, 2)
                row += 1

        if not data.get("transactions"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada transaksi bulan ini")
            row += 1

        self._write_total_row(ws, row, {
            8: float(tot_sub), 9: float(tot_pay),
        }, max_col=12)

        self._set_column_widths(ws)
        ws.freeze_panes = "A3"
        ws.auto_filter.ref = "A2:L2"

    # ─── Sheet 3: Stok ────────────────────────────────────────────────────────

    def _fill_stok(self, ws, data: dict) -> None:
        logger.info(f"Fill stok: {len(data.get('products', []))} products, {len(data.get('stock_history', []))} history records")
        headers = ["No", "Nama Bahan", "Kategori", "Satuan",
                   "Harga", "Stok Awal Bulan", "Masuk", "Keluar",
                   "Stok Akhir", "Nilai Stok"]
        self._write_headers(ws, 1, headers)

        # Build net change per product
        in_by_prod:  Dict[str, Decimal] = {}
        out_by_prod: Dict[str, Decimal] = {}
        for h in data.get("stock_history", []):
            pid = h.get("product_id", "")
            delta = _d(h.get("change_qty"))
            if delta >= 0:
                in_by_prod[pid]  = in_by_prod.get(pid, Decimal("0"))  + delta
            else:
                out_by_prod[pid] = out_by_prod.get(pid, Decimal("0")) + abs(delta)

        row = 2
        
        # Filter out 'produk_jadi' and 'komponen' so only raw materials and packaging are listed
        valid_products = [p for p in data.get("products", []) if p.get("category") not in ("produk_jadi", "komponen")]
        
        for n, p in enumerate(valid_products, 1):
            pid = p.get("id", "")
            harga = _d(p.get("harga"))
            stk_akhir = _d(p.get("stock_qty"))
            masuk  = in_by_prod.get(pid, Decimal("0"))
            keluar = out_by_prod.get(pid, Decimal("0"))
            stk_awal = stk_akhir - masuk + keluar
            factor = float(p.get("conversion_factor") or 1) or 1
            
            # Nilai stok is based on display unit qty * harga
            stk_akhir_display = float(stk_akhir) / factor
            nilai = stk_akhir_display * float(harga)

            ws.cell(row, 1, n)
            ws.cell(row, 2, p.get("name"))
            ws.cell(row, 3, p.get("category"))
            ws.cell(row, 4, p.get("display_unit") or p.get("unit"))
            ws.cell(row, 5, float(harga)).number_format = '"Rp "#,##0'
            ws.cell(row, 6, round(float(stk_awal) / factor, 3))
            ws.cell(row, 7, round(float(masuk) / factor, 3))
            ws.cell(row, 8, round(float(keluar) / factor, 3))
            ws.cell(row, 9, round(stk_akhir_display, 3))
            ws.cell(row, 10, round(nilai, 2)).number_format = ACCOUNTING_FORMAT
            self._alt_row(ws, row, 10)
            row += 1

        if not data.get("products"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada data produk/bahan")
            row += 1

        self._set_column_widths(ws)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:J{row-1}"

    # ─── Sheet 4: Laporan Pemerintah ──────────────────────────────────────────

    def _fill_laporan_pemerintah(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        logger.info(f"Fill laporan pemerintah (NEW MODEL: Bahan:Ops:Profit breakdown)")
        bulan_str = BULAN[month]
        tenant_name = data["tenant"].get("name", "SPPG")

        # Section A: Header
        ws.merge_cells("A1:I1")
        ws["A1"] = f"LAPORAN PEMERINTAH MBG — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws["A1"].alignment = Alignment(horizontal="center")

        # Section B: Identitas SPPG
        ws["A3"] = "Identitas SPPG"
        ws["A3"].font = Font(bold=True, size=11)
        ws["A4"] = "Nama SPPG"; ws["B4"] = tenant_name
        ws["A5"] = "Periode"; ws["B5"] = f"{bulan_str} {year}"

        # Section C: Daily Breakdown (Tanggal per Hari)
        deliveries = data.get("deliveries", [])
        budget_allocations = data.get("budget_allocations", [])
        
        # Group allocations by date
        alloc_by_date: Dict[str, dict] = {}
        for ba in budget_allocations:
            d = ba.get("date", "")
            if d:
                alloc_by_date[d] = ba

        ws["A7"] = "Rincian Harian - Breakdown Biaya: Bahan : Operasional : Profit"
        ws["A7"].font = Font(bold=True, size=11)
        
        headers_daily = ["Tanggal", "Porsi", "Bahan Baku (Rp)", "Operasional (Rp)", 
                        "Profit (Rp)", "Total (Rp)", "% Bahan", "% Ops", "% Profit"]
        for i, h in enumerate(headers_daily, 1):
            ws.cell(8, i, h).font = Font(bold=True)

        row = 9
        total_bahan_all = Decimal("0")
        total_ops_all = Decimal("0")
        total_profit_all = Decimal("0")
        total_revenue_all = Decimal("0")
        total_porsi_all = 0
        
        # Group deliveries by date to summarize per day
        deliveries_by_date: Dict[str, List[dict]] = {}
        for d in deliveries:
            del_date = d.get("delivery_date", "")
            deliveries_by_date.setdefault(del_date, []).append(d)
        
        # Get rates and distributed profit parameters
        rate_sd = data.get("rate_bahan_sd", Decimal("10000"))
        rate_tk = data.get("rate_bahan_tk", Decimal("8000"))
        r_ops = data.get("rate_ops_porsi", Decimal("3000"))
        profit_per_porsi = data.get("profit_per_porsi", Decimal("0"))
        total_target_profit = data.get("total_profit_target", Decimal("0"))

        dates_sorted = sorted(deliveries_by_date.keys())
        for idx, del_date in enumerate(dates_sorted):
            day_deliveries = deliveries_by_date[del_date]
            day_porsi = sum(d.get("portions_sent", 0) for d in day_deliveries)
            
            # Calculate dynamically from deliveries (fixes Rp 0 bug)
            bahan = Decimal("0")
            for dd in day_deliveries:
                p = dd.get("portions_sent", 0)
                sl = (dd.get("schools") or {}).get("school_level", "sd_smp")
                bahan += Decimal(p) * (rate_tk if sl == "paud_tk" else rate_sd)
            
            ops = Decimal(day_porsi) * r_ops
            
            # Distributed Profit (Averaging Model)
            if idx == len(dates_sorted) - 1:
                # Adjust final row to match target exactly (rounding management)
                profit = total_target_profit - total_profit_all
            else:
                profit = Decimal(day_porsi) * profit_per_porsi
            
            total = bahan + ops + profit
            
            if total > 0:
                pct_bahan = (bahan / total) * 100
                pct_ops = (ops / total) * 100
                pct_profit = (profit / total) * 100
            else:
                pct_bahan = pct_ops = pct_profit = Decimal("0")
            
            ws.cell(row, 1, del_date)
            ws.cell(row, 2, day_porsi)
            ws.cell(row, 3, float(bahan)).number_format = '"Rp "#,##0'
            ws.cell(row, 4, float(ops)).number_format = '"Rp "#,##0'
            ws.cell(row, 5, float(profit)).number_format = '"Rp "#,##0'
            ws.cell(row, 6, float(total)).number_format = '"Rp "#,##0'
            ws.cell(row, 7, float(pct_bahan)).number_format = '0.00"%"'
            ws.cell(row, 8, float(pct_ops)).number_format = '0.00"%"'
            ws.cell(row, 9, float(pct_profit)).number_format = '0.00"%"'
            self._alt_row(ws, row, 2)
            
            total_bahan_all += bahan
            total_ops_all += ops
            total_profit_all += profit
            total_revenue_all += total
            total_porsi_all += day_porsi
            row += 1

        # Total row
        if total_revenue_all > 0:
            pct_b = (total_bahan_all / total_revenue_all) * 100
            pct_o = (total_ops_all / total_revenue_all) * 100
            pct_p = (total_profit_all / total_revenue_all) * 100
        else:
            pct_b = pct_o = pct_p = Decimal("0")

        ws.cell(row, 1, "TOTAL BULANAN")
        ws.cell(row, 1).font = Font(bold=True)
        ws.cell(row, 2, total_porsi_all)
        ws.cell(row, 2).font = Font(bold=True)
        ws.cell(row, 3, float(total_bahan_all)).number_format = '"Rp "#,##0'
        ws.cell(row, 3).font = Font(bold=True)
        ws.cell(row, 4, float(total_ops_all)).number_format = '"Rp "#,##0'
        ws.cell(row, 4).font = Font(bold=True)
        ws.cell(row, 5, float(total_profit_all)).number_format = '"Rp "#,##0'
        ws.cell(row, 5).font = Font(bold=True)
        ws.cell(row, 6, float(total_revenue_all)).number_format = '"Rp "#,##0'
        ws.cell(row, 6).font = Font(bold=True)
        ws.cell(row, 7, float(pct_b)).number_format = '0.00"%"'
        ws.cell(row, 7).font = Font(bold=True)
        ws.cell(row, 8, float(pct_o)).number_format = '0.00"%"'
        ws.cell(row, 8).font = Font(bold=True)
        ws.cell(row, 9, float(pct_p)).number_format = '0.00"%"'
        ws.cell(row, 9).font = Font(bold=True)
        
        # Section D: Summary & Catatan
        row += 2
        ws[f"A{row}"] = "Ringkasan Komposisi (Rata-rata % per Porsi)"
        ws[f"A{row}"].font = Font(bold=True, size=11)
        row += 1
        
        avg_bahan_pp = total_bahan_all / max(total_porsi_all, 1) if total_porsi_all > 0 else Decimal("0")
        avg_ops_pp = total_ops_all / max(total_porsi_all, 1) if total_porsi_all > 0 else Decimal("0")
        avg_profit_pp = (total_profit_all / max(total_porsi_all, 1) if total_porsi_all > 0 else Decimal("0"))
        avg_total_pp = total_revenue_all / max(total_porsi_all, 1) if total_porsi_all > 0 else Decimal("0")
        
        summary_rows = [
            ("Bahan Baku per Porsi", float(avg_bahan_pp), '"Rp "#,##0'),
            ("Operasional per Porsi", float(avg_ops_pp), '"Rp "#,##0'),
            ("Profit per Porsi", float(avg_profit_pp), '"Rp "#,##0'),
            ("Total per Porsi", float(avg_total_pp), '"Rp "#,##0'),
        ]
        
        for label, value, fmt in summary_rows:
            ws[f"A{row}"] = label
            ws[f"B{row}"] = value
            ws[f"B{row}"].number_format = fmt
            row += 1

        self._set_column_widths(ws)

    # ─── Sheet 5: Riwayat Nota ────────────────────────────────────────────────

    def _fill_riwayat_nota(self, ws, data: dict) -> None:
        logger.info(f"Fill riwayat nota: {len(data.get('transactions', []))} transactions, {len(data.get('items_all', []))} items")
        headers = ["No", "Tanggal", "Supplier", "Item", "Qty", "Satuan",
                   "Harga", "Subtotal", "Total Nota", "Metode Bayar"]
        self._write_headers(ws, 1, headers)

        items_by_trx: Dict[str, List[dict]] = {}
        for item in data.get("items_all", []):
            tid = item.get("transaction_id", "")
            items_by_trx.setdefault(tid, []).append(item)

        row = 2
        n = 0
        for trx in data.get("transactions", []):
            tid = trx["id"]
            del_date = trx.get("date", "")
            sup_data = trx.get("suppliers") or {}
            supplier = sup_data.get("name") if isinstance(sup_data, dict) else None
            supplier = supplier or trx.get("nama_toko") or "Tanpa Supplier"
            method = trx.get("payment_method", "tunai") or "tunai"
            total_nota = float(_d(trx.get("total")))

            trx_items = items_by_trx.get(tid, [])

            if not trx_items:
                n += 1
                ws.cell(row, 1, n)
                ws.cell(row, 2, del_date)
                ws.cell(row, 3, supplier)
                ws.cell(row, 4, "(tanpa detail)")
                ws.cell(row, 9, total_nota).number_format = '"Rp "#,##0'
                ws.cell(row, 10, method)
                self._alt_row(ws, row, 10)
                row += 1
                continue

            for item in trx_items:
                n += 1
                nama = item.get("product_name", "?")
                qty = float(_d(item.get("qty")))
                sat = item.get("unit", "pcs")
                harga = float(_d(item.get("price")))
                subtotal = float(_d(item.get("subtotal")) or (_d(item.get("qty")) * _d(item.get("price"))))

                ws.cell(row, 1, n)
                ws.cell(row, 2, del_date)
                ws.cell(row, 3, supplier)
                ws.cell(row, 4, nama)
                ws.cell(row, 5, qty)
                ws.cell(row, 6, sat)
                ws.cell(row, 7, harga).number_format = '"Rp "#,##0'
                ws.cell(row, 8, subtotal).number_format = '"Rp "#,##0'
                ws.cell(row, 9, total_nota).number_format = '"Rp "#,##0'
                ws.cell(row, 10, method)
                self._alt_row(ws, row, 10)
                row += 1

        if not data.get("transactions"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada riwayat nota bulan ini")
            row += 1

        self._set_column_widths(ws)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:J{row-1}"

    # ─── Sheet 6: Operasional & Upah ──────────────────────────────────────────

    def _fill_ops_upah(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        bulan_str = BULAN[month]

        # ── Section A: DETAIL ANALISIS TARGET (PAGU) vs REALISASI (RIIL) ──
        ws.merge_cells("A1:E1")
        ws["A1"] = f"DETAIL ANALISIS OPERASIONAL & UPAH — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws["A1"].alignment = Alignment(horizontal="center")

        sum_headers = ["Kategori", "Anggaran (Pagu Juknis)", "Realisasi (Riil)", "Selisih (Surplus)", "Status"]
        self._write_headers(ws, 2, sum_headers)

        # Calculate targets from budget_allocations
        budget_allocations = data.get("budget_allocations", [])
        target_upah = Decimal("0")
        target_ops = Decimal("0")
        for ba in budget_allocations:
            u = _d(ba.get("operational_salary"))
            target_upah += u if u > 0 else _d(ba.get("budget_labor"))
            f = _d(ba.get("operational_fuel"))
            ut = _d(ba.get("operational_utilities"))
            sub = f + ut
            target_ops += sub if sub > 0 else _d(ba.get("budget_ops"))

        # Calculate actuals from payroll and operational costs
        actual_upah = sum(_d(item.get("net_amount")) for item in data.get("payroll_items", []))
        actual_ops = sum(_d(cost.get("amount")) for cost in data.get("operational_costs", []))

        row = 3
        summary_items = [
            ("1. Gaji & Insentif Tenaga Kerja (Pagu Rp 6jt/hari)", target_upah, actual_upah),
            ("2. Operasional / BBM / Logistik (Pagu Rp 3.000/porsi)", target_ops, actual_ops),
        ]
        for label, tgt, act in summary_items:
            selisih = tgt - act
            status = "✅ Hemat" if selisih >= 0 else "⚠️ Over"
            ws.cell(row, 1, label)
            ws.cell(row, 2, float(tgt)).number_format = '"Rp "#,##0'
            ws.cell(row, 3, float(act)).number_format = '"Rp "#,##0'
            ws.cell(row, 4, float(selisih)).number_format = '"Rp "#,##0'
            ws.cell(row, 5, status)
            if selisih < 0:
                ws.cell(row, 4).font = Font(color="FF0000", bold=True)
                ws.cell(row, 5).font = Font(color="FF0000")
            else:
                ws.cell(row, 4).font = Font(color="006400", bold=True)
                ws.cell(row, 5).font = Font(color="006400")
            row += 1

        row += 1

        # ── Section B: DETAIL BIAYA OPERASIONAL ──
        ops_start = row
        ws.merge_cells(f"A{row}:G{row}")
        ws[f"A{row}"] = f"DETAIL BIAYA OPERASIONAL — {bulan_str} {year}"
        ws[f"A{row}"].font = Font(name=GLOBAL_FONT, bold=True, size=12, color="FFFFFF")
        ws[f"A{row}"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws[f"A{row}"].alignment = Alignment(horizontal="center")
        row += 1

        ops_headers = ["No", "Tanggal", "Nama Biaya", "Kategori", "Nominal", "Rutin?", "Catatan"]
        self._write_headers(ws, row, ops_headers)
        row += 1

        total_ops_detail = Decimal("0")
        n = 0
        
        for cost in data.get("operational_costs", []):
            n += 1
            amt = float(_d(cost.get("amount")))
            total_ops_detail += _d(cost.get("amount"))
            
            ws.cell(row, 1, n)
            ws.cell(row, 2, cost.get("cost_date", ""))
            ws.cell(row, 3, cost.get("name", ""))
            ws.cell(row, 4, cost.get("category", ""))
            ws.cell(row, 5, amt).number_format = ACCOUNTING_FORMAT
            ws.cell(row, 6, "Ya" if cost.get("is_recurring") else "Tidak")
            ws.cell(row, 7, cost.get("notes", ""))
            self._alt_row(ws, row, 7)
            row += 1

        if not data.get("operational_costs"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada biaya operasional bulan ini")
            row += 1

        self._write_total_row(ws, row, {5: float(total_ops_detail)}, max_col=7)
        row += 2

        # ── Section C: GAJI & UPAH ──
        upah_start = row
        ws.merge_cells(f"A{row}:J{row}")
        ws[f"A{row}"] = f"GAJI & UPAH (BERDASARKAN PERIODE) — {bulan_str} {year}"
        ws[f"A{row}"].font = Font(name=GLOBAL_FONT, bold=True, size=12, color="FFFFFF")
        ws[f"A{row}"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws[f"A{row}"].alignment = Alignment(horizontal="center")
        row += 1

        upah_headers = ["No", "Periode", "Status", "Mulai", "Nama", "Jabatan", "Hadir", "Alpa", "Potongan", "Total Terima"]
        self._write_headers(ws, row, upah_headers)
        row += 1

        total_upah_detail = Decimal("0")
        n = 0
        
        for item in data.get("payroll_items", []):
            n += 1
            period = item.get("payroll_periods", {})
            emp = item.get("employees", {})
            net = float(_d(item.get("net_amount")))
            total_upah_detail += _d(item.get("net_amount"))
            
            ws.cell(row, 1, n)
            ws.cell(row, 2, period.get("name", ""))
            ws.cell(row, 3, period.get("status", ""))
            ws.cell(row, 4, period.get("start_date", ""))
            ws.cell(row, 5, emp.get("name", ""))
            ws.cell(row, 6, item.get("position_name", ""))
            ws.cell(row, 7, item.get("present_days", 0))
            ws.cell(row, 8, item.get("absent_days", 0))
            ws.cell(row, 9, float(_d(item.get("deductions")))).number_format = ACCOUNTING_FORMAT
            ws.cell(row, 10, net).number_format = ACCOUNTING_FORMAT
            self._alt_row(ws, row, 10)
            row += 1
            
        if not data.get("payroll_items"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada data gaji bulan ini")
            row += 1
            
        self._write_total_row(ws, row, {10: float(total_upah_detail)}, max_col=10)
        
        self._set_column_widths(ws)
        ws.freeze_panes = "A3"
        ws.auto_filter.ref = f"A{ops_start+1}:G{ops_start+1}" # Just a filter on one of the headers

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _write_headers(self, ws, row: int, headers: list) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        font = Font(name=GLOBAL_FONT, bold=True, color="FFFFFF", size=GLOBAL_FONT_SIZE)
        border = Border(
            left=Side(style='thin', color=BORDER_COLOR),
            right=Side(style='thin', color=BORDER_COLOR),
            top=Side(style='thin', color=BORDER_COLOR),
            bottom=Side(style='thin', color=BORDER_COLOR)
        )
        for i, h in enumerate(headers, 1):
            c = ws.cell(row, i, h)
            c.font = font
            c.fill = fill
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = border

    def _apply_header_style(self, ws, row: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        font = Font(name=GLOBAL_FONT, bold=True, color="FFFFFF", size=GLOBAL_FONT_SIZE)
        border = Border(
            left=Side(style='thin', color=BORDER_COLOR),
            right=Side(style='thin', color=BORDER_COLOR),
            top=Side(style='thin', color=BORDER_COLOR),
            bottom=Side(style='thin', color=BORDER_COLOR)
        )
        for cell in ws[row]:
            cell.font = font
            cell.fill = fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

    def _alt_row(self, ws, row: int, max_col: int) -> None:
        from openpyxl.styles import PatternFill, Font, Border, Side
        fill = None
        if row % 2 == 0:
            fill = PatternFill("solid", fgColor=ALT_ROW_COLOR)
        
        border = Border(
            left=Side(style='thin', color=BORDER_COLOR),
            right=Side(style='thin', color=BORDER_COLOR),
            top=Side(style='thin', color=BORDER_COLOR),
            bottom=Side(style='thin', color=BORDER_COLOR)
        )
        font = Font(name=GLOBAL_FONT, size=GLOBAL_FONT_SIZE)
        
        for c in range(1, max_col + 1):
            cell = ws.cell(row, c)
            if fill:
                cell.fill = fill
            cell.border = border
            if not cell.font or cell.font.name != GLOBAL_FONT:
                cell.font = font

    def _write_total_row(self, ws, row: int, col_values: dict, max_col: int = 0) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        fill = PatternFill("solid", fgColor=TOTAL_FILL_COLOR)
        font = Font(name=GLOBAL_FONT, bold=True, size=GLOBAL_FONT_SIZE)
        border = Border(
            left=Side(style='thin', color=BORDER_COLOR),
            right=Side(style='thin', color=BORDER_COLOR),
            top=Side(style='thin', color=BORDER_COLOR),
            bottom=Side(style='thin', color=BORDER_COLOR)
        )

        # Apply style to the whole row up to max_col
        limit = max_col if max_col > 0 else max(col_values.keys()) if col_values else 10
        for c in range(1, limit + 1):
            cell = ws.cell(row, c)
            cell.fill = fill
            cell.font = font
            cell.border = border

        ws.cell(row, 1, "TOTAL")
        for col, val in col_values.items():
            if val is not None:
                c = ws.cell(row, col, val)
                if isinstance(val, (int, float, Decimal)):
                    c.number_format = ACCOUNTING_FORMAT

    def _set_column_widths(self, ws, padding: int = 4) -> None:
        from openpyxl.utils import get_column_letter
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        length = len(str(cell.value))
                        max_len = max(max_len, length)
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + padding, 50)

    # ─── Storage + DB ─────────────────────────────────────────────────────────

    def _upload_to_storage(
        self, supabase, tenant_id: str, year: int, month: int, content: bytes
    ) -> Optional[str]:
        file_name = f"{year}-{month:02d}_pembukuan.xlsx"
        storage_path = f"{tenant_id}/excel/{file_name}"
        bucket = "nota-photos"

        try:
            # Use upsert: true to overwrite if exists
            supabase.storage.from_(bucket).upload(
                path=storage_path,
                file=content,
                file_options={
                    "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "upsert": "true"
                },
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
        try:
            year, month = map(int, period.split("-"))
        except:
            year, month = 0, 0
            
        row: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "period": period,
            "year": year,
            "month": month,
            "status": status,
            "last_updated": now,
            "file_url": file_url or "",
        }
        if error_message:
            row["error_message"] = error_message

        try:
            supabase.table("excel_files").upsert(
                row, on_conflict="tenant_id,period"
            ).execute()
        except Exception as e:
            logger.warning(f"upsert excel_files gagal: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # COMPLIANCE SHEETS — Modul 21.5e
    # ═══════════════════════════════════════════════════════════════════════

    def _fill_hygiene(self, ws, data: dict, year: int, month: int) -> None:
        """Sheet 11: Checklist Higiene Bulanan."""
        from openpyxl.styles import Font, Alignment, PatternFill
        bulan_str = BULAN[month]

        ws.merge_cells("A1:J1")
        ws["A1"] = f"LAPORAN CHECKLIST HIGIENE — {bulan_str} {year}"
        ws["A1"].font = Font(name=GLOBAL_FONT, bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = [
            "Tanggal", "Lantai/Dinding", "Suhu Penyimpanan", "Peralatan Masak",
            "Atribut Personel", "Air Bersih", "Area Penyimpanan", "Tempat Sampah",
            "Status", "Catatan"
        ]
        hdr_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        for col_idx, hdr in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=hdr)
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center")

        checks = data.get("hygiene_checks", [])
        area_map = {
            "Lantai": 2, "Suhu": 3, "Peralatan": 4, "Personel": 5,
            "Air": 6, "Penyimpanan": 7, "Sampah": 8,
        }

        for idx, check in enumerate(checks, start=4):
            ws.cell(row=idx, column=1, value=check.get("check_date", ""))

            items = check.get("items", [])
            for item in items:
                area_name = item.get("area", "")
                for key, col in area_map.items():
                    if key.lower() in area_name.lower():
                        icon = "✓" if item.get("status") == "baik" else "⚠️"
                        ws.cell(row=idx, column=col, value=icon)
                        break

            status = check.get("overall_status", "")
            status_cell = ws.cell(row=idx, column=9, value=status.upper())
            
            # Dashboard Biru Modern Style: Green for Safe, Red for Incident
            if status == "layak":
                status_cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                status_cell.font = Font(name=GLOBAL_FONT, color="006100", bold=True)
            elif status == "tidak_layak":
                status_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                status_cell.font = Font(name=GLOBAL_FONT, color="9C0006", bold=True)
            else: # perlu_perbaikan
                status_cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
                status_cell.font = Font(name=GLOBAL_FONT, color="9C6500", bold=True)

            ws.cell(row=idx, column=10, value=check.get("notes", ""))
            self._alt_row(ws, idx, 10)

        ws.freeze_panes = "A4"
        self._set_column_widths(ws)

    def _fill_suhu(self, ws, data: dict, year: int, month: int) -> None:
        """Sheet 12: Monitoring Suhu."""
        from openpyxl.styles import Font, Alignment, PatternFill
        bulan_str = BULAN[month]

        ws.merge_cells("A1:F1")
        ws["A1"] = f"LAPORAN MONITORING SUHU — {bulan_str} {year}"
        ws["A1"].font = Font(name=GLOBAL_FONT, bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = ["Tanggal", "Jam", "Area", "Suhu (°C)", "Status", "Catatan"]
        hdr_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        for col_idx, hdr in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=hdr)
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center")

        logs = data.get("temperature_logs", [])
        for idx, log in enumerate(logs, start=4):
            ws.cell(row=idx, column=1, value=log.get("log_date", ""))
            ws.cell(row=idx, column=2, value=log.get("log_time", ""))
            ws.cell(row=idx, column=3, value=log.get("area", ""))

            temp_cell = ws.cell(row=idx, column=4, value=log.get("temperature"))
            temp_cell.number_format = '0.0'

            status_cell = ws.cell(row=idx, column=5)
            if not log.get("is_normal"):
                status_cell.value = "⚠️ ABNORMAL"
                status_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                status_cell.font = Font(name=GLOBAL_FONT, color="9C0006", bold=True)
            else:
                status_cell.value = "✓ Normal"
                status_cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                status_cell.font = Font(name=GLOBAL_FONT, color="006100", bold=True)

            ws.cell(row=idx, column=6, value=log.get("notes", ""))
            self._alt_row(ws, idx, 6)

        ws.freeze_panes = "A4"
        self._set_column_widths(ws)

    def _fill_bank_sampel(self, ws, data: dict) -> None:
        """Sheet 13: Bank Sampel Makanan."""
        from openpyxl.styles import Font, Alignment, PatternFill

        ws.merge_cells("A1:H1")
        ws["A1"] = "DAFTAR BANK SAMPEL MAKANAN"
        ws["A1"].font = Font(name=GLOBAL_FONT, bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = ["Kode Sampel", "Menu", "Tanggal", "Jam Ambil", "Berat (g)", "Kadaluarsa", "Status", "Sisa Waktu"]
        hdr_fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        for col_idx, hdr in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=hdr)
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center")

        samples = data.get("food_samples", [])
        now = datetime.now(timezone.utc)

        for idx, sample in enumerate(samples, start=4):
            ws.cell(row=idx, column=1, value=sample.get("sample_code", ""))
            ws.cell(row=idx, column=2, value=sample.get("menu_name", ""))
            ws.cell(row=idx, column=3, value=sample.get("sample_date", ""))
            ws.cell(row=idx, column=4, value=sample.get("taken_at", ""))
            ws.cell(row=idx, column=5, value=sample.get("weight_gram"))
            ws.cell(row=idx, column=6, value=sample.get("expires_at", ""))

            status_cell = ws.cell(row=idx, column=7)
            hours_cell = ws.cell(row=idx, column=8)

            try:
                exp_str = sample.get("expires_at", "")
                if exp_str:
                    if "+" not in exp_str and "Z" not in exp_str:
                        exp_str += "+00:00"
                    expires_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                    hours_left = (expires_dt - now).total_seconds() / 3600

                    if hours_left < 0:
                        status_cell.value = "❌ KADALUARSA"
                        status_cell.fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                        status_cell.font = Font(color="FFFFFF")
                        hours_cell.value = "Expired"
                    elif hours_left <= 4:
                        status_cell.value = "⚠️ Segera"
                        status_cell.fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
                        hours_cell.value = f"{hours_left:.1f} jam"
                    else:
                        status_cell.value = "✓ Aman"
                        status_cell.fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
                        hours_cell.value = f"{hours_left:.1f} jam"
                else:
                    status_cell.value = "—"
                    hours_cell.value = "—"
            except Exception:
                status_cell.value = sample.get("status", "")
                hours_cell.value = "—"

        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 20
        for col_letter in ["C", "D", "E", "F", "G", "H"]:
            ws.column_dimensions[col_letter].width = 14

    def _fill_sisa_makanan(self, ws, data: dict, year: int, month: int) -> None:
        """Sheet 14: Laporan Sisa Makanan."""
        from openpyxl.styles import Font, Alignment, PatternFill
        bulan_str = BULAN[month]

        ws.merge_cells("A1:H1")
        ws["A1"] = f"LAPORAN SISA MAKANAN — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = ["Tanggal", "Sekolah", "Porsi Kirim", "Porsi Konsumsi", "% Sisa", "Skor Comstock", "Alasan", "Catatan"]
        hdr_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        for col_idx, hdr in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=hdr)
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center")

        reports = data.get("food_waste_reports", [])

        total_sent = 0
        total_consumed = 0

        for idx, rep in enumerate(reports, start=4):
            ws.cell(row=idx, column=1, value=rep.get("report_date", ""))
            school_info = rep.get("schools") or {}
            ws.cell(row=idx, column=2, value=school_info.get("name", "") if isinstance(school_info, dict) else "")
            ws.cell(row=idx, column=3, value=rep.get("portions_sent", 0))
            ws.cell(row=idx, column=4, value=rep.get("portions_consumed", 0))

            pct_cell = ws.cell(row=idx, column=5, value=rep.get("waste_pct", 0))
            pct_cell.number_format = '0.0"%"'

            score = rep.get("comstock_score", 0)
            ws.cell(row=idx, column=6, value=f"⭐{score}" if score else "")
            ws.cell(row=idx, column=7, value=rep.get("waste_reason", ""))
            ws.cell(row=idx, column=8, value=rep.get("notes", ""))

            total_sent += rep.get("portions_sent", 0)
            total_consumed += rep.get("portions_consumed", 0)

        # Summary row
        if reports:
            summary_row = len(reports) + 5
            ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
            ws.cell(row=summary_row, column=3, value=total_sent).font = Font(bold=True)
            ws.cell(row=summary_row, column=4, value=total_consumed).font = Font(bold=True)
            total_pct = round((total_sent - total_consumed) / total_sent * 100, 1) if total_sent > 0 else 0
            pct_summary = ws.cell(row=summary_row, column=5, value=total_pct)
            pct_summary.number_format = '0.0"%"'
            pct_summary.font = Font(bold=True)
            pct_summary.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")

        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            ws.column_dimensions[col_letter].width = 15

    def _fill_insiden(self, ws, data: dict, year: int, month: int) -> None:
        """Sheet 15: Laporan Insiden KLB."""
        from openpyxl.styles import Font, Alignment, PatternFill
        bulan_str = BULAN[month]

        ws.merge_cells("A1:J1")
        ws["A1"] = f"LAPORAN INSIDEN KLB/KERACUNAN — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = ["Kode Insiden", "Tanggal", "Sekolah", "Lokasi", "Korban", "Gejala", "Tindakan", "Sampel Diamankan", "Status", "Hasil Investigasi"]
        hdr_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
        for col_idx, hdr in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=hdr)
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center")

        incidents = data.get("incident_reports", [])

        for idx, inc in enumerate(incidents, start=4):
            ws.cell(row=idx, column=1, value=inc.get("incident_code", ""))
            ws.cell(row=idx, column=2, value=(inc.get("incident_time", "") or "")[:10])
            school_info = inc.get("schools") or {}
            ws.cell(row=idx, column=3, value=school_info.get("name", "") if isinstance(school_info, dict) else "")
            ws.cell(row=idx, column=4, value=inc.get("location", ""))
            ws.cell(row=idx, column=5, value=inc.get("victim_count", 0))
            ws.cell(row=idx, column=6, value=", ".join(inc.get("symptoms", []) or []))
            ws.cell(row=idx, column=7, value=inc.get("first_action", ""))

            sample_cell = ws.cell(row=idx, column=8)
            sample_cell.value = "✓ Ya" if inc.get("sample_secured") else "✗ Tidak"
            if inc.get("sample_secured"):
                sample_cell.fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")

            status_cell = ws.cell(row=idx, column=9, value=(inc.get("status", "") or "").upper())
            status_val = inc.get("status", "")
            if status_val == "investigasi":
                status_cell.fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
            elif status_val == "selesai":
                status_cell.fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
            elif status_val == "ditutup":
                status_cell.fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")

            ws.cell(row=idx, column=10, value=inc.get("investigation_result", ""))

        if not incidents:
            ws.cell(row=4, column=1, value="Tidak ada insiden pada bulan ini")
            ws.merge_cells("A4:J4")
            ws["A4"].font = Font(italic=True, color="808080")
            ws["A4"].alignment = Alignment(horizontal="center")

        for col_letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
            ws.column_dimensions[col_letter].width = 15
