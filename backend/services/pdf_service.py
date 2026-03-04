"""
backend/services/pdf_service.py
Generate nota pengiriman MBG harian via ReportLab — Modul 10

generate_mbg_delivery_note():
  - Buat PDF dengan header SPPG, tabel distribusi, ringkasan alokasi
  - Upload ke Supabase Storage
  - Return: file URL
"""

import io
import logging
import uuid
from datetime import date as _date
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _fmt_rp(amount) -> str:
    try:
        return f"Rp {int(Decimal(str(amount or 0))):,}".replace(",", ".")
    except Exception:
        return f"Rp {amount}"


class PDFService:
    """Generate nota pengiriman MBG via ReportLab dan upload ke Supabase Storage."""

    def generate_mbg_delivery_note(
        self,
        deliveries: List[dict],
        tenant_info: dict,
        menu_info: dict,
        allocation: dict,
        delivery_date: str,
        supabase,
    ) -> Optional[str]:
        """
        Buat PDF nota pengiriman MBG, upload ke Storage, return public URL.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable,
            )
        except ImportError:
            logger.error("ReportLab tidak terinstall")
            return None

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "title", parent=styles["Heading1"],
            fontSize=14, alignment=1, spaceAfter=4,
        )
        sub_style = ParagraphStyle(
            "sub", parent=styles["Normal"],
            fontSize=10, alignment=1, spaceAfter=2,
        )
        normal = styles["Normal"]

        tenant_name = tenant_info.get("name", "SPPG")
        menu_name = menu_info.get("name", "—")
        nota_number = f"MBG/{delivery_date.replace('-', '')}/{uuid.uuid4().hex[:6].upper()}"
        total_portions = sum(d.get("portions_sent", 0) for d in deliveries)

        story = [
            Paragraph("NOTA PENGIRIMAN MAKANAN BERGIZI GRATIS (MBG)", title_style),
            Paragraph(tenant_name, sub_style),
            Spacer(1, 0.3 * cm),
            Paragraph(f"No. Nota : {nota_number}", normal),
            Paragraph(f"Tanggal  : {delivery_date}", normal),
            Paragraph(f"Menu     : {menu_name}", normal),
            Spacer(1, 0.4 * cm),
            HRFlowable(width="100%", thickness=1, color=colors.black),
            Spacer(1, 0.3 * cm),
        ]

        # ─── Tabel distribusi ─────────────────────────────────────────
        table_data = [["No.", "Nama Sekolah", "Porsi Dikirim", "Penerima", "TTD"]]
        for n, d in enumerate(deliveries, 1):
            table_data.append([
                str(n),
                d.get("school_name") or d.get("school_id", "?"),
                str(d.get("portions_sent", 0)),
                d.get("receiver_name") or "",
                "",
            ])

        table = Table(table_data, colWidths=[1*cm, 6*cm, 3*cm, 4*cm, 3*cm])
        table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#2563eb")),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("ALIGN",        (2, 0), (2, -1), "CENTER"),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.5 * cm))

        # ─── Ringkasan alokasi ────────────────────────────────────────
        total_rev = allocation.get("total_revenue", 0)
        food_pct  = int(round(allocation.get("food_pct", 80)))
        labor_pct = int(round(allocation.get("labor_pct", 15)))
        ops_pct   = int(round(allocation.get("ops_pct", 5)))

        alloc_data = [
            ["Total Porsi", str(total_portions)],
            ["Total Pendapatan", _fmt_rp(total_rev)],
            [f"Alokasi Bahan Makanan ({food_pct}%)", _fmt_rp(allocation.get("budget_food", 0))],
            [f"Alokasi Upah ({labor_pct}%)", _fmt_rp(allocation.get("budget_labor", 0))],
            [f"Alokasi Operasional ({ops_pct}%)", _fmt_rp(allocation.get("budget_ops", 0))],
        ]
        alloc_table = Table(alloc_data, colWidths=[9*cm, 8*cm])
        alloc_table.setStyle(TableStyle([
            ("FONTSIZE",  (0, 0), (-1, -1), 9),
            ("GRID",      (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(Paragraph("<b>Ringkasan Alokasi</b>", normal))
        story.append(Spacer(1, 0.2 * cm))
        story.append(alloc_table)
        story.append(Spacer(1, 1 * cm))

        # ─── TTD Penanggung Jawab ─────────────────────────────────────
        ttd_data = [
            ["Penyerah", "Penerima/Verifikator"],
            ["", ""],
            ["", ""],
            ["(Penanggung Jawab SPPG)", "(Pemerintah/Sekolah)"],
        ]
        ttd_table = Table(ttd_data, colWidths=[8.5*cm, 8.5*cm])
        ttd_table.setStyle(TableStyle([
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEABOVE",  (0, 2), (1, 2), 0.5, colors.black),
        ]))
        story.append(ttd_table)
        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Paragraph(
            "<i>* PPh 22 akan dipotong oleh Pemerintah saat pembayaran. "
            "Nilai pada nota ini adalah gross sebelum potongan.</i>",
            ParagraphStyle("footer", parent=normal, fontSize=7, textColor=colors.grey),
        ))

        doc.build(story)
        pdf_bytes = buffer.getvalue()

        # ─── Upload ke Supabase Storage ───────────────────────────────
        try:
            tenant_id = tenant_info.get("id", "unknown")
            period = delivery_date[:7]  # "YYYY-MM"
            file_name = f"{delivery_date}_draft_{uuid.uuid4().hex[:6]}.pdf"
            storage_path = f"{tenant_id}/notas-mbg/{period}/{file_name}"

            supabase.storage.from_("nota-photos").upload(
                path=storage_path,
                file=pdf_bytes,
                file_options={"content-type": "application/pdf"},
            )
            url_resp = supabase.storage.from_("nota-photos").get_public_url(storage_path)
            return url_resp if isinstance(url_resp, str) else str(url_resp)
        except Exception as e:
            logger.error(f"Upload PDF nota MBG gagal: {e}")
            return None


pdf_service = PDFService()
