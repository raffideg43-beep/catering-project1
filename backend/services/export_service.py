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

        print(f"DEBUG: Fetching data for {year}-{month} (Range: {first} to {last}), tenant={tenant_id}")

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

        # MBG deliveries + schools
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
            .select("id, name, category, unit, display_unit, conversion_factor, hpp, stock_qty, stock_min")
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
        # Period date must overlap or we just get items by date?
        # Actually, period has start_date / end_date. Just fetch periods and their items.
        period_resp = (
            supabase.table("payroll_periods")
            .select("id, name, start_date")
            .eq("tenant_id", tenant_id)
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
                .select("*, employees(name), payroll_periods(name, start_date)")
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

        # School Beneficiaries (for Sheet 9)
        sb_res = (
            supabase.table("school_beneficiaries")
            .select("*, schools(name), beneficiary_types(name)")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        school_beneficiaries = getattr(sb_res, "data", None) or []

        # Budget Summary
        from services.budget_service import budget_service
        budget_summary = budget_service.get_monthly_summary(tenant_id, year, month)

        return {
            "tenant": tenant,
            "first": first,
            "last": last,
            "price_per_portion": price_per_portion,
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

        return wb

    # ─── Sheet 1: Ringkasan ───────────────────────────────────────────────────

    def _fill_bku(self, ws, data: dict, year: int, month: int, kas_type: str, title: str) -> None:
        from openpyxl.styles import Font, Alignment
        bulan_str = BULAN[month]
        
        ws.merge_cells("A1:G1")
        ws["A1"] = f"{title} — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = ["No", "Tanggal", "Akun Kas", "Keterangan", "Masuk (Debit)", "Keluar (Kredit)", "Saldo Akhir"]
        self._write_headers(ws, 3, headers)

        filtered_ledger = []
        for e in data.get("kas_ledger", []):
            acc_info = e.get("kas_accounts")
            if isinstance(acc_info, dict) and acc_info.get("type") == kas_type:
                filtered_ledger.append(e)

        row = 4
        if not filtered_ledger:
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada transaksi pada kas ini")
            self._set_column_widths(ws)
            return

        for i, entry in enumerate(filtered_ledger, 1):
            is_debit = entry.get("entry_type") == "debit"
            masuk = entry.get("amount") if is_debit else 0
            keluar = 0 if is_debit else entry.get("amount")
            
            ws.cell(row, 1, i)
            ws.cell(row, 2, entry.get("entry_date", ""))
            
            # Safe access for kas_account inner join
            acc_info = entry.get("kas_accounts")
            acc_name = acc_info.get("name", "") if isinstance(acc_info, dict) else ""
            ws.cell(row, 3, acc_name)
            
            ws.cell(row, 4, entry.get("description", ""))
            
            ws.cell(row, 5, float(masuk)).number_format = '"Rp "#,##0'
            ws.cell(row, 6, float(keluar)).number_format = '"Rp "#,##0'
            ws.cell(row, 7, float(entry.get("balance_after", 0))).number_format = '"Rp "#,##0'
            
            self._alt_row(ws, row, 3)
            row += 1

        self._set_column_widths(ws)

    def _fill_penerima_manfaat(self, ws, data: dict) -> None:
        from openpyxl.styles import Font, Alignment
        ws.merge_cells("A1:D1")
        ws["A1"] = "DATA PENERIMA MANFAAT MBG"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        headers = ["No", "Sekolah", "Jenis Penerima", "Jumlah Porsi (Target)"]
        self._write_headers(ws, 3, headers)
        
        sb_data = data.get("school_beneficiaries", [])
        row = 4
        if not sb_data:
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Data Kosong")
        else:
            for i, sb in enumerate(sb_data, 1):
                sch_name = sb.get("schools", {}).get("name", "") if isinstance(sb.get("schools"), dict) else ""
                bt_name = sb.get("beneficiary_types", {}).get("name", "") if isinstance(sb.get("beneficiary_types"), dict) else ""
                ws.cell(row, 1, i)
                ws.cell(row, 2, sch_name)
                ws.cell(row, 3, bt_name)
                ws.cell(row, 4, sb.get("target_portions", 0))
                self._alt_row(ws, row, 3)
                row += 1
                
        self._set_column_widths(ws)

    def _fill_rekapitulasi_juknis(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, Alignment, PatternFill
        bulan_str = BULAN[month]
        
        ws.merge_cells("A1:E1")
        ws["A1"] = f"REKAPITULASI JUKNIS 80:15:5 — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")
        
        headers = ["Keterangan", "Anggaran (Target)", "Realisasi (Aktual)", "Selisih", "%"]
        self._write_headers(ws, 3, headers)
        
        deliveries = data.get("deliveries", [])
        transactions = data.get("transactions", [])
        budget = data.get("budget_summary", {})
        
        # Gunakan Pencairan aktual dari budget_service alih-alih estimasi porsi
        total_disbursed = Decimal(budget.get("total_disbursed", 0))
        
        exp_bahan = sum(_d(t.get("total")) for t in transactions if str(t.get("juknis_category")).lower() not in ("insentif", "operasional"))
        exp_upah = sum(_d(t.get("total")) for t in transactions if str(t.get("juknis_category")).lower() == "insentif")
        exp_ops = sum(_d(t.get("total")) for t in transactions if str(t.get("juknis_category")).lower() == "operasional")
        total_exp = exp_bahan + exp_upah + exp_ops
        
        # Target mengikuti persentase dari Pagu/Pencairan aktual
        target_bahan = total_disbursed * Decimal("0.80")
        target_upah = total_disbursed * Decimal("0.15")
        target_ops = total_disbursed * Decimal("0.05")
        
        def pct(aktual, target):
            return f"{round(float(aktual/target*100), 1)}%" if target > 0 else "0%"
            
        rows_data = [
            ("Dana Masuk (Pencairan MBG)", total_disbursed, total_disbursed, 0, "100%"),
            ("-", "-", "-", "-", "-"),
            ("Bahan Pangan (80%)", target_bahan, exp_bahan, target_bahan - exp_bahan, pct(exp_bahan, target_bahan)),
            ("Insentif/Upah (15%)", target_upah, exp_upah, target_upah - exp_upah, pct(exp_upah, target_upah)),
            ("Operasional (5%)", target_ops, exp_ops, target_ops - exp_ops, pct(exp_ops, target_ops)),
            ("-", "-", "-", "-", "-"),
            ("Total Pengeluaran", total_disbursed, total_exp, total_disbursed - total_exp, pct(total_exp, total_disbursed))
        ]
        
        row = 4
        for rd in rows_data:
            ws.cell(row, 1, rd[0])
            if rd[0] == "-":
                row += 1
                continue
            ws.cell(row, 2, float(rd[1])).number_format = '"Rp "#,##0'
            ws.cell(row, 3, float(rd[2])).number_format = '"Rp "#,##0'
            ws.cell(row, 4, float(rd[3])).number_format = '"Rp "#,##0'
            ws.cell(row, 5, rd[4])
            row += 1
            
        self._set_column_widths(ws)

    def _fill_ringkasan(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        logger.info(f"Fill ringkasan: transactions={len(data.get('transactions', []))}, deliveries={len(data.get('deliveries', []))}")

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
        transactions = data["transactions"]
        budget = data.get("budget_summary", {})
        total_portions = sum(d.get("portions_sent", 0) for d in deliveries)
        total_days = len({d["delivery_date"] for d in deliveries})
        price_pp = Decimal(str(data["price_per_portion"]))
        
        # Pagu dan Dana Pencairan (Real dari UI Anggaran)
        pagu_amount = Decimal(budget.get("pagu_amount", 0))
        total_disbursed = Decimal(budget.get("total_disbursed", 0))
        sisa_anggaran = Decimal(budget.get("sisa_anggaran", 0))

        # Menghitung estimasi jika menggunakan portion based vs actual pencairan
        revenue_net = total_disbursed
        exp_bahan = sum(_d(t.get("total")) for t in transactions if str(t.get("juknis_category")).lower() not in ("insentif", "operasional"))
        exp_upah = sum(_d(t.get("total")) for t in transactions if str(t.get("juknis_category")).lower() == "insentif")
        exp_ops = sum(_d(t.get("total")) for t in transactions if str(t.get("juknis_category")).lower() == "operasional")
        total_exp = exp_bahan + exp_upah + exp_ops
        
        gross_profit = revenue_net - total_exp

        rows = [
            ("Pagu Anggaran",     float(pagu_amount)),
            ("Dana Masuk / Cair", float(total_disbursed)),
            ("Sisa Anggaran",     float(sisa_anggaran)),
            ("Total Porsi (Terkirim)", f"{total_portions:,} porsi"),
            ("Total Hari Kirim",  f"{total_days} hari"),
            ("Total Transaksi",   f"{len(transactions)} nota"),
            ("Pengeluaran Bahan Pangan", float(exp_bahan)),
            ("Pengeluaran Insentif/Upah", float(exp_upah)),
            ("Pengeluaran Operasional", float(exp_ops)),
            ("Total Pengeluaran", float(total_exp)),
            ("Laba Kotor / Sisa Dana", float(gross_profit)),
        ]

        ws["A5"] = "Keterangan"; ws["B5"] = "Jumlah"
        self._apply_header_style(ws, 5)

        for i, (label, val) in enumerate(rows, start=6):
            ws[f"A{i}"] = label
            ws[f"B{i}"] = val
            if isinstance(val, float):
                ws[f"B{i}"].number_format = '"Rp "#,##0'

        # Piutang & Hutang summary
        receivables = data.get("receivables", [])
        payables = data.get("payables", [])
        total_piutang = sum(_d(r.get("amount")) for r in receivables)
        total_hutang = sum(_d(p.get("amount")) for p in payables)

        last_row = 6 + len(rows)
        ws[f"A{last_row}"] = "Total Piutang"
        ws[f"B{last_row}"] = float(total_piutang)
        ws[f"B{last_row}"].number_format = '"Rp "#,##0'
        last_row += 1
        ws[f"A{last_row}"] = "Total Hutang"
        ws[f"B{last_row}"] = float(total_hutang)
        ws[f"B{last_row}"].number_format = '"Rp "#,##0'

        self._set_column_widths(ws)
        ws.freeze_panes = "A6"

    # ─── Sheet 2: Bulanan (gabungan semua transaksi + penyerahan) ─────────────

    def _fill_bulanan(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        ppn_rate   = Decimal("0.11")
        logger.info(
            f"Fill bulanan: {len(data.get('deliveries', []))} deliveries, "
            f"{len(data.get('transactions', []))} transactions, "
            f"{len(data.get('items_all', []))} items"
        )

        bulan_str = BULAN[month]

        # ── Section A: PENYERAHAN MBG ──
        ws.merge_cells("A1:I1")
        ws["A1"] = f"PENYERAHAN MBG — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws["A1"].alignment = Alignment(horizontal="center")

        penyerahan_headers = ["No", "Tanggal", "Sekolah", "Menu", "Porsi",
                              "Harga/Porsi", "Gross", "Bersih"]
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
        total_gross = total_bersih = Decimal("0")
        price_pp = Decimal(str(data["price_per_portion"]))

        for n, d in enumerate(data.get("deliveries", []), 1):
            portions = d.get("portions_sent", 0)
            school_name = (d.get("schools") or {}).get("name", "?")
            del_date = d.get("delivery_date", "")
            menu_name = menu_by_date.get(del_date, d.get("menu_name", "—"))
            gross = price_pp * portions
            bersih = gross

            total_gross  += gross
            total_bersih += bersih

            ws.cell(row, 1, n)
            ws.cell(row, 2, del_date)
            ws.cell(row, 3, school_name)
            ws.cell(row, 4, menu_name)
            ws.cell(row, 5, portions)
            ws.cell(row, 6, float(price_pp)).number_format = '"Rp "#,##0'
            ws.cell(row, 7, float(gross)).number_format = '"Rp "#,##0'
            ws.cell(row, 8, float(bersih)).number_format = '"Rp "#,##0'
            self._alt_row(ws, row, 2)
            row += 1

        if not data.get("deliveries"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada penyerahan MBG bulan ini")
            row += 1

        # Total penyerahan
        self._write_total_row(ws, row, {
            5: sum(d.get("portions_sent", 0) for d in data.get("deliveries", [])),
            7: float(total_gross), 8: float(total_bersih)
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
        })

        self._set_column_widths(ws)
        ws.freeze_panes = "A3"

    # ─── Sheet 3: Stok ────────────────────────────────────────────────────────

    def _fill_stok(self, ws, data: dict) -> None:
        logger.info(f"Fill stok: {len(data.get('products', []))} products, {len(data.get('stock_history', []))} history records")
        headers = ["No", "Nama Bahan", "Kategori", "Satuan",
                   "HPP", "Stok Awal Bulan", "Masuk", "Keluar",
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
        for n, p in enumerate(data.get("products", []), 1):
            pid = p.get("id", "")
            hpp = _d(p.get("hpp"))
            stk_akhir = _d(p.get("stock_qty"))
            masuk  = in_by_prod.get(pid, Decimal("0"))
            keluar = out_by_prod.get(pid, Decimal("0"))
            stk_awal = stk_akhir - masuk + keluar
            nilai = stk_akhir * hpp
            factor = float(p.get("conversion_factor") or 1) or 1

            ws.cell(row, 1, n)
            ws.cell(row, 2, p.get("name"))
            ws.cell(row, 3, p.get("category"))
            ws.cell(row, 4, p.get("display_unit") or p.get("unit"))
            ws.cell(row, 5, float(hpp)).number_format = '"Rp "#,##0'
            ws.cell(row, 6, round(float(stk_awal) / factor, 3))
            ws.cell(row, 7, round(float(masuk) / factor, 3))
            ws.cell(row, 8, round(float(keluar) / factor, 3))
            ws.cell(row, 9, round(float(stk_akhir) / factor, 3))
            ws.cell(row, 10, float(nilai)).number_format = '"Rp "#,##0'
            self._alt_row(ws, row, 2)
            row += 1

        if not data.get("products"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada data produk/bahan")

        self._set_column_widths(ws)
        ws.freeze_panes = "A2"

    # ─── Sheet 4: Laporan Pemerintah ──────────────────────────────────────────

    def _fill_laporan_pemerintah(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        logger.info(f"Fill laporan pemerintah")
        bulan_str = BULAN[month]
        tenant_name = data["tenant"].get("name", "SPPG")

        # Section A: Identitas
        ws.merge_cells("A1:E1")
        ws["A1"] = f"LAPORAN PEMERINTAH MBG — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws["A1"].alignment = Alignment(horizontal="center")

        ws["A3"] = "Identitas SPPG"
        ws["A3"].font = Font(bold=True, size=11)
        ws["A4"] = "Nama SPPG"; ws["B4"] = tenant_name
        ws["A5"] = "Periode"; ws["B5"] = f"{bulan_str} {year}"

        # Section B: Logistik & Distribusi
        deliveries = data.get("deliveries", [])
        total_portions = sum(d.get("portions_sent", 0) for d in deliveries)
        total_days = len({d["delivery_date"] for d in deliveries})
        price_pp = Decimal(str(data["price_per_portion"]))
        revenue_gross = price_pp * total_portions

        ws["A7"] = "Logistik & Distribusi"
        ws["A7"].font = Font(bold=True, size=11)
        ws["A8"] = "Total Porsi"; ws["B8"] = total_portions
        ws["A9"] = "Total Hari Kirim"; ws["B9"] = total_days
        ws["A10"] = "Rata-rata Porsi/Hari"; ws["B10"] = round(total_portions / max(total_days, 1))
        ws["A11"] = "Jumlah Sekolah"; ws["B11"] = len({d.get("school_id") for d in deliveries})

        # Section C: Komposisi Biaya 80:15:5
        transactions = data.get("transactions", [])
        total_exp = sum(_d(t.get("total")) for t in transactions)
        bahan_pct = float(total_exp / revenue_gross * 100) if revenue_gross > 0 else 0
        target_bahan = float(revenue_gross) * 0.80
        target_upah = float(revenue_gross) * 0.15
        target_ops = float(revenue_gross) * 0.05

        ws["A13"] = "Komposisi Biaya 80:15:5"
        ws["A13"].font = Font(bold=True, size=11)
        headers_biaya = ["Kategori", "Target (%)", "Target (Rp)", "Realisasi (Rp)", "Selisih"]
        for i, h in enumerate(headers_biaya, 1):
            ws.cell(14, i, h).font = Font(bold=True)

        # Bahan (80%)
        ws.cell(15, 1, "Bahan Baku (80%)")
        ws.cell(15, 2, "80%")
        ws.cell(15, 3, target_bahan).number_format = '"Rp "#,##0'
        ws.cell(15, 4, float(total_exp)).number_format = '"Rp "#,##0'
        ws.cell(15, 5, target_bahan - float(total_exp)).number_format = '"Rp "#,##0'

        # Upah (15%)
        ws.cell(16, 1, "Upah Pekerja (15%)")
        ws.cell(16, 2, "15%")
        ws.cell(16, 3, target_upah).number_format = '"Rp "#,##0'
        ws.cell(16, 4, "Belum tercatat")
        ws.cell(16, 5, "—")

        # Operasional (5%)
        ws.cell(17, 1, "Operasional (5%)")
        ws.cell(17, 2, "5%")
        ws.cell(17, 3, target_ops).number_format = '"Rp "#,##0'
        ws.cell(17, 4, "Belum tercatat")
        ws.cell(17, 5, "—")

        # Section D: Detail Pendapatan
        ws["A19"] = "Detail Pendapatan"
        ws["A19"].font = Font(bold=True, size=11)
        ws["A20"] = "Pendapatan Bruto"; ws["B20"] = float(revenue_gross); ws["B20"].number_format = '"Rp "#,##0'
        ws["A21"] = "Pendapatan Netto"; ws["B21"] = float(revenue_gross); ws["B21"].number_format = '"Rp "#,##0'

        self._set_column_widths(ws)

    # ─── Sheet 5: Riwayat Nota ────────────────────────────────────────────────

    def _fill_riwayat_nota(self, ws, data: dict) -> None:
        logger.info(f"Fill riwayat nota: {len(data.get('transactions', []))} transactions, {len(data.get('items_all', []))} items")
        headers = ["No", "Tanggal", "Supplier", "Item", "Qty", "Satuan",
                   "Harga", "PPN", "Subtotal", "Total Nota", "Metode Bayar"]
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
                ws.cell(row, 10, total_nota).number_format = '"Rp "#,##0'
                ws.cell(row, 11, method)
                self._alt_row(ws, row, 2)
                row += 1
                continue

            for item in trx_items:
                n += 1
                nama = item.get("product_name", "?")
                qty = float(_d(item.get("qty")))
                sat = item.get("unit", "pcs")
                harga = float(_d(item.get("price")))
                subtotal = float(_d(item.get("subtotal")) or (_d(item.get("qty")) * _d(item.get("price"))))
                ppn = 0  # PPN dihitung hanya untuk PKP

                ws.cell(row, 1, n)
                ws.cell(row, 2, del_date)
                ws.cell(row, 3, supplier)
                ws.cell(row, 4, nama)
                ws.cell(row, 5, qty)
                ws.cell(row, 6, sat)
                ws.cell(row, 7, harga).number_format = '"Rp "#,##0'
                ws.cell(row, 8, ppn)
                ws.cell(row, 9, subtotal).number_format = '"Rp "#,##0'
                ws.cell(row, 10, total_nota).number_format = '"Rp "#,##0'
                ws.cell(row, 11, method)
                self._alt_row(ws, row, 2)
                row += 1

        if not data.get("transactions"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada riwayat nota bulan ini")

        self._set_column_widths(ws)
        ws.freeze_panes = "A2"

    # ─── Sheet 6: Operasional & Upah ──────────────────────────────────────────

    def _fill_ops_upah(self, ws, data: dict, year: int, month: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        bulan_str = BULAN[month]

        # ── Section A: BIAYA OPERASIONAL ──
        ws.merge_cells("A1:G1")
        ws["A1"] = f"BIAYA OPERASIONAL — {bulan_str} {year}"
        ws["A1"].font = Font(bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws["A1"].alignment = Alignment(horizontal="center")

        ops_headers = ["No", "Tanggal", "Nama Biaya", "Kategori", "Nominal", "Rutin?", "Catatan"]
        self._write_headers(ws, 2, ops_headers)

        row = 3
        total_ops = Decimal("0")
        
        for n, cost in enumerate(data.get("operational_costs", []), 1):
            amt = float(_d(cost.get("amount")))
            total_ops += _d(cost.get("amount"))
            
            ws.cell(row, 1, n)
            ws.cell(row, 2, cost.get("cost_date", ""))
            ws.cell(row, 3, cost.get("name", ""))
            ws.cell(row, 4, cost.get("category", ""))
            ws.cell(row, 5, amt).number_format = '"Rp "#,##0'
            ws.cell(row, 6, "Ya" if cost.get("is_recurring") else "Tidak")
            ws.cell(row, 7, cost.get("notes", ""))
            self._alt_row(ws, row, 2)
            row += 1

        if not data.get("operational_costs"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada biaya operasional bulan ini")
            row += 1

        self._write_total_row(ws, row, {5: float(total_ops)})
        row += 2

        # ── Section B: GAJI & UPAH ──
        ws.merge_cells(f"A{row}:J{row}")
        ws[f"A{row}"] = f"GAJI & UPAH (BERDASARKAN PERIODE) — {bulan_str} {year}"
        ws[f"A{row}"].font = Font(bold=True, size=12, color="FFFFFF")
        ws[f"A{row}"].fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        ws[f"A{row}"].alignment = Alignment(horizontal="center")
        row += 1

        upah_headers = ["No", "Periode", "Mulai", "Nama", "Jabatan", "Hadir", "Alpa", "Gaji/Hari", "Potongan", "Total Terima"]
        self._write_headers(ws, row, upah_headers)
        row += 1

        total_upah = Decimal("0")
        n = 0
        
        for item in data.get("payroll_items", []):
            n += 1
            period = item.get("payroll_periods", {})
            emp = item.get("employees", {})
            net = float(_d(item.get("net_amount")))
            total_upah += _d(item.get("net_amount"))
            
            ws.cell(row, 1, n)
            ws.cell(row, 2, period.get("name", ""))
            ws.cell(row, 3, period.get("start_date", ""))
            ws.cell(row, 4, emp.get("name", ""))
            ws.cell(row, 5, item.get("position_name", ""))
            ws.cell(row, 6, item.get("present_days", 0))
            ws.cell(row, 7, item.get("absent_days", 0))
            ws.cell(row, 8, float(_d(item.get("base_salary")))).number_format = '"Rp "#,##0'
            ws.cell(row, 9, float(_d(item.get("deductions")))).number_format = '"Rp "#,##0'
            ws.cell(row, 10, net).number_format = '"Rp "#,##0'
            self._alt_row(ws, row, 2)
            row += 1
            
        if not data.get("payroll_items"):
            ws.cell(row, 1, "—")
            ws.cell(row, 2, "Tidak ada data gaji bulan ini")
            row += 1
            
        self._write_total_row(ws, row, {10: float(total_upah)})
        
        self._set_column_widths(ws)
        ws.freeze_panes = "A3"

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _write_headers(self, ws, row: int, headers: list) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        font = Font(bold=True, color="FFFFFF", size=10)
        for i, h in enumerate(headers, 1):
            c = ws.cell(row, i, h)
            c.font = font
            c.fill = fill
            c.alignment = Alignment(horizontal="center")

    def _apply_header_style(self, ws, row: int) -> None:
        from openpyxl.styles import Font, PatternFill, Alignment
        fill = PatternFill("solid", fgColor=HDR_FILL_COLOR)
        font = Font(bold=True, color="FFFFFF", size=10)
        for cell in ws[row]:
            cell.font = font
            cell.fill = fill
            cell.alignment = Alignment(horizontal="center")

    def _alt_row(self, ws, row: int, min_col: int = 1) -> None:
        if row % 2 == 0:
            from openpyxl.styles import PatternFill
            fill = PatternFill("solid", fgColor=ALT_ROW_COLOR)
            for cell in ws[row]:
                cell.fill = fill

    def _write_total_row(self, ws, row: int, col_values: dict) -> None:
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
                if isinstance(val, (int, float)):
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
