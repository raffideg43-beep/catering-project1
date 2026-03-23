import traceback
import sys

with open("out_trace.txt", "w") as f:
    try:
        from core.database import get_supabase
        from services.export_service import ExportService
        from services.spt_service import SPTService

        sb = get_supabase()
        res = sb.table('tenants').select('id').limit(1).execute()
        tid = res.data[0]['id']
        
        f.write("Testing Excel...\n")
        try:
            url = ExportService().regenerate_monthly_excel(tid, 2026, 3, sb)
            f.write(f"Excel success: {url}\n")
        except Exception as e:
            f.write("Excel Error:\n")
            traceback.print_exc(file=f)

    except Exception as e:
        traceback.print_exc(file=f)
