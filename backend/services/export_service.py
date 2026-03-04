"""
backend/services/export_service.py
Placeholder regenerate Excel — implementasi penuh di Modul 12.

Dipanggil sebagai FastAPI BackgroundTask setelah setiap konfirmasi
transaksi agar laporan Excel otomatis diperbarui.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ExportService:
    """Placeholder — Modul 12 akan implementasi generate Excel penuh."""

    async def regenerate_monthly_excel(
        self,
        tenant_id: str,
        year: int,
        month: int,
    ) -> bool:
        """
        Trigger regenerasi Excel bulan ini.

        Sekarang: tandai status 'pending_regenerate' di DB.
        Modul 12:
          - load_workbook("templates/pembukuan_template.xlsx")
          - Isi 6 sheet dari data DB
          - Upload ke Supabase Storage
        """
        logger.info(f"TODO: regenerate Excel {year}/{month} untuk tenant {tenant_id}")

        try:
            from core.database import get_supabase
            supabase = get_supabase()
            period = f"{year:04d}-{month:02d}"

            # Upsert excel_files: tandai perlu regenerasi
            supabase.table("excel_files").upsert({
                "tenant_id": tenant_id,
                "period": period,
                "status": "pending_regenerate",
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="tenant_id,period").execute()
        except Exception as e:
            logger.warning(f"excel_files upsert gagal (non-fatal): {e}")

        return True


export_service = ExportService()
