import sys
import asyncio
import traceback
from core.database import get_supabase
from services.export_service import ExportService
from services.spt_service import SPTService

async def run_tests():
    try:
        sb = get_supabase()
        res = sb.table('tenants').select('id').limit(1).execute()
        tid = res.data[0]['id']
        
        print("--- Testing Excel ---")
        try:
            url = await ExportService().regenerate_monthly_excel(tid, 2026, 3, sb)
            print("Excel result:", url)
        except Exception as e:
            traceback.print_exc()
            
        print("--- Testing SPT ---")
        try:
            res_spt = await SPTService.generate_spt(tid, 2026, 3, sb)
            print("SPT result:", res_spt)
        except Exception as e:
            traceback.print_exc()

        print("--- Testing BAP ---")
        try:
            res_bap = await SPTService.generate_bap(tid, 2026, 3, sb)
            print("BAP result:", res_bap)
        except Exception as e:
            traceback.print_exc()
            
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_tests())
